"""Assessments by a decision model: in shadow mode they only record what the model suggests.

Each feature asks the Decider through OpenRouter and writes its suggestion to a local log:

- tasks: risk, importance and complexity of a request, turned into an execution path by a fixed rule;
  facts from the git diff set a floor for risk that the model cannot lower.
- impasse: whether a new correction attempt repeats an earlier one in other words.

With the tasks feature on, each request reaches the agent with its path (ADR-0036, ADR-0037). The
other features stay in shadow mode; a person may record whether they agree with any of them.
"""

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request

from .common import AifwError, digest, now, read_yaml, require

URL = "https://openrouter.ai/api/alpha/decisions"
DEFAULT_MODEL = "perplexity/pplx-decider-v1.2"
FEATURES = ("tasks", "impasse", "context", "intake", "traceability", "decisions")
LOGS = {
    "tasks": (".aifw/assessments/shadow.jsonl", ".aifw/assessments/verdicts.jsonl"),
    "impasse": (".aifw/assessments/impasse.jsonl", ".aifw/assessments/impasse-verdicts.jsonl"),
    "context": (".aifw/assessments/context.jsonl", ".aifw/assessments/context-verdicts.jsonl"),
    "intake": (".aifw/assessments/intake.jsonl", ".aifw/assessments/intake-verdicts.jsonl"),
    "traceability": (".aifw/assessments/traceability.jsonl", ".aifw/assessments/traceability-verdicts.jsonl"),
    "decisions": (".aifw/assessments/decisions.jsonl", ".aifw/assessments/decisions-verdicts.jsonl"),
}
SHADOW_LOG, VERDICTS = LOGS["tasks"]
ACTIVATION = dict(requests=50, agreement=0.9)
MIN_TASK_WORDS = 5  # shorter prompts are replies, not tasks, and are not assessed automatically
# Messages the session receives without the person typing them: subagent reports, notices from
# other sessions, background tasks and hooks, and the brief of a session another one started.
AUTOMATIC_PROMPT = re.compile(r"\s*(<[a-z][\w-]*[\s>]|Background \(from the session|Stop hook feedback)")


def is_request(prompt):
    """A request the person typed: not a slash command, a short reply or an automatic message."""
    text = prompt.strip()
    return (
        not text.startswith("/") and len(text.split()) >= MIN_TASK_WORDS and not AUTOMATIC_PROMPT.match(text)
    )


REPEAT_THRESHOLD = 0.7
SUGGEST_THRESHOLD = 0.5  # add a document the keywords missed
DOUBT_THRESHOLD = 0.1  # question a document chosen only by a shared word
LEVELS = ["L0", "L1", "L2", "L3"]
IMPORTANCE = ["baixa", "média", "alta", "crítica"]
COMPLEXITY = ["trivial", "simples", "moderada", "alta"]
PATHS = ["FAST", "WORK", "PLANNED", "CRITICAL"]
VALUES = {
    "tasks": PATHS,
    "impasse": ["repeat", "distinct"],
    "context": ["model", "keyword"],
    "intake": ["right", "wrong"],
    "traceability": ["right", "wrong"],
    "decisions": ["right", "wrong"],
}
WEAK_TRACE_THRESHOLD = 0.5
SIGNAL_CONFIDENCE = 0.6  # suggest a decision signal only above this confidence
UNKNOWN_SIGNAL = "unknown"
SPECIFICITY = ["vaga", "parcial", "específica"]
INTAKE_FIELDS = ("problem", "audiences", "outcomes", "scope.in", "scope.out")
QUESTIONS = {
    "risk": dict(
        type="choice",
        instructions="Qual o nível de risco desta mudança?",
        criteria={
            "L0": "só documentação ou leitura, sem mudar comportamento",
            "L1": "muda comportamento dentro de um único módulo, sem contrato compartilhado, dados sensíveis, autorização, produção ou custo externo",
            "L2": "atravessa módulos, muda contrato compartilhado, dados sensíveis, design system global, custo externo, produção ou autorização",
            "L3": "núcleo do framework ou constituição, fronteira de segurança, migração destrutiva, quebra de contrato público ou efeito irreversível em produção",
        },
    ),
    "importance": dict(
        type="score",
        instructions="Qual a importância desta tarefa para o negócio?",
        criteria=[
            "baixa: pode esperar, efeito pequeno",
            "média: útil, prazo normal",
            "alta: afeta usuários ou receita",
            "crítica: bloqueia a operação ou tem prazo inadiável",
        ],
    ),
    "complexity": dict(
        type="score",
        instructions="Qual a dificuldade técnica desta tarefa?",
        criteria=[
            "trivial: uma alteração óbvia",
            "simples: poucos arquivos, solução conhecida",
            "moderada: vários passos ou alguma investigação",
            "alta: desenho novo, várias partes ou causa desconhecida",
        ],
    ),
}
SAME_ATTEMPT = dict(
    type="noul",
    instructions="A nova tentativa repete, na prática, a estratégia da tentativa anterior?",
    criteria={
        "true": "mesma hipótese e mesma intervenção, ainda que escritas com outras palavras",
        "false": "a hipótese ou a intervenção é realmente diferente",
    },
)
RELEVANT_DOC = dict(
    type="noul",
    instructions="Este documento é relevante para executar a tarefa?",
    criteria={
        "true": "o documento traz regras, contexto ou decisões que a tarefa precisa seguir",
        "false": "o documento trata de outro assunto",
    },
)
SPECIFIC_ANSWER = dict(
    type="score",
    instructions="A resposta é específica o bastante para guiar decisões de produto?",
    criteria=[
        "vaga: genérica, adiada ou sem conteúdo verificável (por exemplo, a definir, todos, melhorar o sistema)",
        "parcial: dá uma direção, mas falta quem, quanto ou o limite",
        "específica: concreta e verificável, dá para decidir com ela",
    ],
)
COVERS = dict(
    type="noul",
    instructions="Este cenário verifica o comportamento exigido por este requisito?",
    criteria={
        "true": "passar no cenário mostra que o requisito foi cumprido",
        "false": "o cenário testa outra coisa, ou só uma parte irrelevante do requisito",
    },
)
# Each path names the role subagent that takes it (ADR-0038).
PATH_RULE = {
    "FAST": "risco L0, complexidade trivial ou simples, importância baixa ou média: aifw-quick (Haiku) executa",
    "WORK": (
        "risco L1, ou L0 com complexidade moderada ou alta, ou com importância alta ou crítica: "
        "aifw-executor (Sonnet) executa"
    ),
    "PLANNED": (
        "risco L2, ou L1 com complexidade alta: Opus planeja, aifw-executor (Sonnet) executa, "
        "aifw-adversary e depois aifw-qa revisam"
    ),
    "CRITICAL": "risco L3: Opus planeja e executa, aifw-adversary e depois aifw-qa revisam, com aprovação humana",
}


def settings(root):
    spec = read_yaml(Path(root) / "aifw.yaml")["spec"]
    config = spec.get("assessment") or {}
    return dict(
        mode=config.get("mode", "off"),
        model=config.get("model", DEFAULT_MODEL),
        features=config.get("features", ["tasks"]),
        allowlist=spec.get("externalAllowlist", []),
        classification=spec.get("dataClassification", "internal"),
    )


def enabled(root, feature):
    """The project turned this shadow assessment on; outputs stay unchanged otherwise."""
    if not (Path(root) / "aifw.yaml").is_file():
        return False
    config = settings(root)
    return config["mode"] == "shadow" and feature in config["features"]


def blocker(config, feature="tasks"):
    """Why this feature must not call the API, or None."""
    if config["mode"] != "shadow":
        return "assessment is off: set spec.assessment.mode to shadow in aifw.yaml"
    if feature not in config["features"]:
        return f"the {feature} assessment is not in spec.assessment.features"
    if "openrouter" not in config["allowlist"]:
        return "openrouter is not in spec.externalAllowlist; the text would leave the machine"
    if config["classification"] in {"confidential", "restricted"}:
        return f"{config['classification']} projects never send text to an external model"
    if not os.environ.get("OPENROUTER_API_KEY"):
        return "OPENROUTER_API_KEY is not set"
    return None


def decide(model, state, questions):
    """Questions about one state; returns the answers and the cost. Raises AifwError when the service fails."""
    body = json.dumps(dict(model=model, state=state, questions=questions)).encode()
    request = urllib.request.Request(
        URL,
        data=body,
        headers={
            "Authorization": "Bearer " + os.environ["OPENROUTER_API_KEY"],
            "Content-Type": "application/json",
        },
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                data = json.load(response)
            return data["answers"], data.get("usage", {}).get("cost", 0)
        except (urllib.error.URLError, OSError, ValueError, KeyError) as error:
            if attempt == 2:
                raise AifwError("NOT_READY", f"Decision model unavailable: {error}") from error
            time.sleep(1 + attempt)


def ask(model, state, key):
    """One task question; separate requests keep the questions from influencing each other."""
    answers, cost = decide(model, state, {key: QUESTIONS[key]})
    return answers[key], cost


def most_likely(answer, names):
    probabilities = list(answer["probabilities"].values())
    return names[max(range(len(names)), key=lambda i: probabilities[i])]


def path_for(risk, importance, complexity):
    """The execution path for these evaluations; the same table the skill follows."""
    if risk == "L3":
        return "CRITICAL"
    if risk == "L2" or (risk == "L1" and complexity == "alta"):
        return "PLANNED"
    if risk == "L1" or complexity in {"moderada", "alta"} or importance in {"alta", "crítica"}:
        return "WORK"
    return "FAST"


def diff_floor(root, base=None):
    """The risk level verifiable facts in the diff already imply; None without git."""
    from .routing import classify_change, derive_signals

    try:
        derived = derive_signals(root, base)
    except AifwError:
        return None, []
    return classify_change(derived["signals"])["level"], derived["reasons"]


def assess(root, task, use_diff=False, base=None, call=ask, source="manual"):
    require(isinstance(task, str) and task.strip(), "Describe the task with --task.")
    config = settings(root)
    reason = blocker(config)
    if reason:
        return dict(status="unavailable", reason=reason, recorded=False)
    with ThreadPoolExecutor(3) as pool:
        results = dict(zip(QUESTIONS, pool.map(lambda key: call(config["model"], task, key), QUESTIONS)))
    risk = results["risk"][0]
    importance = results["importance"][0]
    complexity = results["complexity"][0]
    floor, floor_reasons = diff_floor(root, base) if use_diff else (None, [])
    model_risk = risk["choice"]
    final_risk = max(model_risk, floor or "L0", key=LEVELS.index)
    record = dict(
        at=now(),
        model=config["model"],
        task=task.strip(),
        source=source,
        risk=dict(value=model_risk, confidence=round(risk.get("confidence", 0), 3)),
        importance=dict(value=most_likely(importance, IMPORTANCE), level=round(importance["score"], 2)),
        complexity=dict(value=most_likely(complexity, COMPLEXITY), level=round(complexity["score"], 2)),
        floor=dict(level=floor, reasons=floor_reasons),
        finalRisk=final_risk,
        cost=round(sum(cost for _, cost in results.values()), 8),
        mode="active",
    )
    record["path"] = path_for(final_risk, record["importance"]["value"], record["complexity"]["value"])
    return dict(status="recorded", recorded=True, **store(root, "tasks", record))


def active(root, feature="tasks"):
    """The tasks assessor hands each request its path whenever the feature is on (ADR-0037)."""
    try:
        return feature == "tasks" and enabled(root, feature)
    except (OSError, KeyError, TypeError, AifwError):
        return False


def path_context(result):
    """What the agent reads with the request in active mode."""
    if result.get("status") != "recorded":
        return f"AIFW: avaliador de tarefas indisponível ({result.get('reason')}); siga a classificação de sempre."
    risk = result["risk"]["value"]
    floor = f", elevado pelo diff a {result['finalRisk']}" if result["finalRisk"] != risk else ""
    return (
        f"AIFW, avaliador de tarefas (modo ativo): caminho {result['path']}. Risco {risk}{floor}, "
        f"importância {result['importance']['value']}, complexidade {result['complexity']['value']}. "
        f"{PATH_RULE[result['path']]}. Siga esse caminho com a tabela de modelos da skill aifw-workflow; "
        "subir de caminho é sempre permitido, descer nunca."
    )


def fingerprint(attempt):
    """Same normalization as impasse.record_attempt, kept here so this module never changes the hook's imports."""
    text = "\n".join(" ".join(attempt[k].lower().split()) for k in ("hypothesis", "intervention"))
    return sha256(text.encode()).hexdigest()


def attempt_text(attempt):
    return f"Hipótese: {attempt['hypothesis']}\nIntervenção: {attempt['intervention']}"


def pair_state(earlier, attempt):
    return f"Tentativa anterior:\n{attempt_text(earlier)}\n\nNova tentativa:\n{attempt_text(attempt)}"


def doc_state(task, doc):
    return f"Tarefa: {task}\n\nDocumento: {doc['path']}\nAssunto: {doc['scope']}"


def answer_state(field, answer):
    from .intake import PROMPTS

    return f"Pergunta: {PROMPTS[field]}\nResposta: {answer}"


def driver_question(driver):
    """A decision driver as a choice question, with an explicit way out when the text says nothing."""
    criteria = {s: s.split(":", 1)[-1].replace("-", " ") for s in driver["signals"]}
    criteria[UNKNOWN_SIGNAL] = "o texto não dá base para responder"
    return dict(type="choice", instructions=driver["prompt"], criteria=criteria)


def compare_attempt(root, case, attempt, call=None):
    """Shadow check: how likely the new attempt repeats each earlier one. Never changes the case."""
    call = call or decide
    config = settings(root)
    reason = blocker(config, "impasse")
    previous = case["attempts"]
    if reason or not previous:
        return dict(status="unavailable" if reason else "nothing-to-compare", reason=reason, recorded=False)

    def same(earlier):
        answers, cost = call(config["model"], pair_state(earlier, attempt), {"same": SAME_ATTEMPT})
        return answers["same"]["noul"], cost

    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(same, previous))
    comparisons = [
        dict(attempt=earlier["id"], probability=round(p, 3)) for earlier, (p, _) in zip(previous, results)
    ]
    top = max(c["probability"] for c in comparisons)
    record = dict(
        at=now(),
        model=config["model"],
        case=case["id"],
        attempt=dict(hypothesis=attempt["hypothesis"], intervention=attempt["intervention"]),
        comparisons=comparisons,
        maxProbability=top,
        wouldRepeat=top >= REPEAT_THRESHOLD,
        exactRepeat=fingerprint(attempt) in case["attemptFingerprints"],
        cost=round(sum(cost for _, cost in results), 8),
    )
    return dict(status="recorded", mode="shadow", recorded=True, **store(root, "impasse", record))


def review_context(root, task, selection, call=None):
    """Shadow check of `context select`: documents the keywords missed and ones chosen by a word only."""
    from .context import check_context

    call = call or decide
    if not (Path(root) / "aifw.yaml").is_file():  # context select also works outside AIFW projects
        return dict(status="unavailable", reason="not an AIFW project", recorded=False)
    config = settings(root)
    reason = blocker(config, "context")
    if reason:
        return dict(status="unavailable", reason=reason, recorded=False)
    docs = check_context(root)["documents"]

    def relevant(doc):
        answers, cost = call(config["model"], doc_state(task, doc), {"relevant": RELEVANT_DOC})
        return answers["relevant"]["noul"], cost

    with ThreadPoolExecutor(16) as pool:
        results = list(pool.map(relevant, docs))
    probability = {doc["path"]: round(p, 3) for doc, (p, _) in zip(docs, results)}
    chosen = {s["path"]: s["reasons"] for s in selection["selected"]}
    record = dict(
        at=now(),
        model=config["model"],
        task=task,
        keywordSelection=sorted(chosen),
        suggested=sorted(p for p, v in probability.items() if v >= SUGGEST_THRESHOLD and p not in chosen),
        doubtful=sorted(
            p for p, why in chosen.items() if why == ["task"] and probability.get(p, 1) < DOUBT_THRESHOLD
        ),
        probabilities=probability,
        cost=round(sum(cost for _, cost in results), 8),
    )
    return dict(status="recorded", mode="shadow", recorded=True, **store(root, "context", record))


def charter_answer(charter, field):
    value = charter
    for key in field.split("."):
        value = value.get(key) if isinstance(value, dict) else None
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    return str(value or "").strip()


def review_intake(root, charter, call=None):
    """Shadow check of `intake status`: Charter answers too vague to guide decisions. Never blocks.

    The result is cached by the Charter's content, so the model runs only when the Charter changes.
    """
    from .intake import PROMPTS

    call = call or decide
    config = settings(root)
    reason = blocker(config, "intake")
    if reason:
        return dict(status="unavailable", reason=reason, recorded=False)
    content = digest({k: v for k, v in charter.items() if k not in {"approval", "state"}})
    previous = next(
        (e for e in reversed(read_lines(Path(root) / LOGS["intake"][0])) if e["charter"] == content), None
    )
    if previous:
        return dict(status="cached", mode="shadow", recorded=False, **previous)
    fields = [f for f in INTAKE_FIELDS if charter_answer(charter, f)]

    def judge(field):
        state = answer_state(field, charter_answer(charter, field))
        answers, cost = call(config["model"], state, {"specific": SPECIFIC_ANSWER})
        return most_likely(answers["specific"], SPECIFICITY), cost

    with ThreadPoolExecutor(5) as pool:
        results = list(pool.map(judge, fields))
    levels = {field: level for field, (level, _) in zip(fields, results)}
    record = dict(
        at=now(),
        model=config["model"],
        charter=content,
        levels=levels,
        weakAnswers=[
            dict(field=f, level=v, prompt=PROMPTS[f]) for f, v in levels.items() if v != "específica"
        ],
        cost=round(sum(cost for _, cost in results), 8),
    )
    return dict(status="recorded", mode="shadow", recorded=True, **store(root, "intake", record))


def trace_text(requirement, scenario):
    steps = "\n".join(
        f"{label}: {'; '.join(scenario.get(key, []))}"
        for label, key in (("Dado", "given"), ("Quando", "when"), ("Então", "then"))
    )
    return (
        f"Requisito ({requirement.get('strength', 'MUST')}): {requirement['statement']}\n\nCenário:\n{steps}"
    )


def review_traces(root, change_id, call=None):
    """Shadow check of `spec analyze`: requirement and scenario pairs where the scenario may not verify it.

    Cached by the text of the pairs, so the model runs again only when the spec changes.
    """
    from .specs import load_artifacts

    call = call or decide
    config = settings(root)
    reason = blocker(config, "traceability")
    if reason:
        return dict(status="unavailable", reason=reason, recorded=False)
    _, deltas, _, _ = load_artifacts(root, change_id)
    pairs = [
        (requirement, scenario)
        for delta in deltas
        for requirement in delta["operations"]["added"] + delta["operations"]["modified"]
        for scenario in requirement["scenarios"]
    ]
    content = digest([trace_text(r, s) for r, s in pairs])
    log = read_lines(Path(root) / LOGS["traceability"][0])
    previous = next((e for e in reversed(log) if e["change"] == change_id and e["specs"] == content), None)
    if previous:
        return dict(status="cached", mode="shadow", recorded=False, **previous)

    def covers(pair):
        answers, cost = call(config["model"], trace_text(*pair), {"covers": COVERS})
        return answers["covers"]["noul"], cost

    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(covers, pairs))
    checked = [
        dict(requirement=r["id"], scenario=s["id"], probability=round(p, 3))
        for (r, s), (p, _) in zip(pairs, results)
    ]
    record = dict(
        at=now(),
        model=config["model"],
        change=change_id,
        specs=content,
        pairs=checked,
        weakTraces=[c for c in checked if c["probability"] < WEAK_TRACE_THRESHOLD],
        cost=round(sum(cost for _, cost in results), 8),
    )
    return dict(status="recorded", mode="shadow", recorded=True, **store(root, "traceability", record))


def project_summary(charter, context=""):
    """What the Charter says about the project, plus the request, as the state for decision drivers."""
    lines = [f"{label}: {charter_answer(charter, field)}" for label, field in CHARTER_LABELS]
    preference = (charter.get("technicalPreference") or {}).get("values") or []
    if preference:
        lines.append("Preferências técnicas: " + "; ".join(preference))
    if context:
        lines.append(f"Pedido atual: {context}")
    return "\n".join(line for line in lines if not line.endswith(": "))


CHARTER_LABELS = (
    ("Problema", "problem"),
    ("Públicos", "audiences"),
    ("Resultados", "outcomes"),
    ("Dentro do escopo", "scope.in"),
    ("Fora do escopo", "scope.out"),
    ("Restrições", "constraints"),
)


def suggest_signals(root, category, context="", call=None):
    """Shadow suggestion of decision signals from the Charter and the request. The person confirms them."""
    from .catalogs import load_decision_catalogs, recommend_decision
    from .intake import load_charter

    call = call or decide
    config = settings(root)
    reason = blocker(config, "decisions")
    if reason:
        return dict(status="unavailable", reason=reason, recorded=False)
    catalogs = load_decision_catalogs(root)
    drivers = {
        d["id"]: d for c in catalogs if c["metadata"]["category"] == category for d in c["spec"]["drivers"]
    }
    require(drivers, f"No decision catalog exists for category {category}.")
    state = project_summary(load_charter(root), context)

    def answer(driver):
        answers, cost = call(config["model"], state, {"driver": driver_question(driver)})
        return answers["driver"], cost

    with ThreadPoolExecutor(8) as pool:
        results = dict(zip(drivers, pool.map(answer, drivers.values())))
    answers = {
        driver: dict(signal=a["choice"], confidence=round(a.get("confidence", 0), 3))
        for driver, (a, _) in results.items()
    }
    suggested = sorted(
        a["signal"]
        for a in answers.values()
        if a["signal"] != UNKNOWN_SIGNAL and a["confidence"] >= SIGNAL_CONFIDENCE
    )
    ranking = recommend_decision(catalogs, category, suggested)["rankings"]
    record = dict(
        at=now(),
        model=config["model"],
        category=category,
        context=context,
        answers=answers,
        suggestedSignals=suggested,
        ranking=[{k: r[k] for k in ("optionId", "score", "eligible")} for r in ranking[:3]],
        cost=round(sum(cost for _, cost in results.values()), 8),
    )
    return dict(status="recorded", mode="shadow", recorded=True, **store(root, "decisions", record))


def store(root, feature, record):
    log = Path(root) / LOGS[feature][0]
    record["id"] = len(read_lines(log)) + 1
    append(log, record)
    return record


def read_lines(file):
    if not file.is_file():
        return []
    return [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines() if line.strip()]


def append(file, entry):
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + "\n")


def suggestion(feature, entry):
    """What the model suggested for this entry, in the vocabulary of its verdicts."""
    if feature == "tasks":
        return entry["path"]
    if feature == "context":
        return "model"
    if feature in {"intake", "traceability", "decisions"}:
        return "right"
    return "repeat" if entry["wouldRepeat"] else "distinct"


def record_verdicts(root, ids, by, value=None, note="", feature="tasks"):
    """The person's view on recorded assessments: agree with the suggestion, or name the right answer."""
    require(feature in FEATURES, f"--feature must be one of {', '.join(FEATURES)}.")
    log, verdicts = LOGS[feature]
    entries = {e["id"]: e for e in read_lines(Path(root) / log)}
    missing = sorted(set(ids) - set(entries))
    require(not missing, f"No recorded {feature} assessment with id {missing}.", "NOT_READY")
    choices = VALUES[feature]
    require(value is None or value in choices, f"The answer must be one of {', '.join(choices)}.")
    written = []
    for assessment_id in ids:
        verdict = dict(
            id=assessment_id,
            value=value or suggestion(feature, entries[assessment_id]),
            by=by,
            at=now(),
            note=note,
        )
        append(Path(root) / verdicts, verdict)
        written.append(verdict)
    return dict(status="recorded", feature=feature, verdicts=written)


def report(root, feature="tasks"):
    """Every assessment with the person's latest verdict, and whether the activation criteria hold."""
    require(feature in FEATURES, f"--feature must be one of {', '.join(FEATURES)}.")
    log, verdict_log = LOGS[feature]
    # Automatic messages recorded before the hook ignored them are not requests; ids stay as recorded.
    entries = [
        e
        for e in read_lines(Path(root) / log)
        if feature != "tasks" or e.get("source") != "prompt" or is_request(e.get("task", ""))
    ]
    verdicts = {v["id"]: v for v in read_lines(Path(root) / verdict_log)}
    rows = [dict(e, suggestion=suggestion(feature, e), verdict=verdicts.get(e["id"])) for e in entries]
    judged = [r for r in rows if r["verdict"]]
    agreed = [r for r in judged if r["verdict"]["value"] == r["suggestion"]]
    demoted = [r for r in judged if r["verdict"]["value"] == "CRITICAL" and r["suggestion"] != "CRITICAL"]
    agreement = len(agreed) / len(judged) if judged else 0
    ready = len(judged) >= ACTIVATION["requests"] and agreement >= ACTIVATION["agreement"] and not demoted
    return dict(
        feature=feature,
        questions=SHAPES[feature]["questions"],
        rule=SHAPES[feature]["rule"],
        rows=rows,
        summary=dict(
            assessments=len(rows),
            judged=len(judged),
            agreement=round(agreement, 3),
            criticalDemoted=[r["id"] for r in demoted],
            cost=round(sum(r.get("cost", 0) for r in rows), 6),
            criteria=dict(ACTIVATION, criticalDemoted=0),
            criteriaMet=ready,
            active=active(root, feature),
        ),
    )


def cell(text, size=90):
    return text.replace("|", "/").replace("\n", " ")[:size]


def render_report(value):
    """The report as Markdown, in the same shape as the manual review."""
    s, feature = value["summary"], value["feature"]
    shape = SHAPES[feature]
    title = shape["title"]
    lines = [
        f"# {title}: relatório da sombra",
        "",
        f"- Avaliações: {s['assessments']} (meta: {s['criteria']['requests']})",
        f"- Com seu veredito: {s['judged']}",
        f"- Concordância: {s['agreement']:.0%} (meta: {s['criteria']['agreement']:.0%})",
    ]
    if feature == "tasks":
        lines.append(
            f"- CRITICAL rebaixados: {len(s['criticalDemoted'])} {s['criticalDemoted'] or ''}".rstrip()
        )
    lines += [
        f"- Critério de ativação atingido: {'sim' if s['criteriaMet'] else 'não'}",
        f"- Modo ativo: {'sim' if s.get('active') else 'não'}",
        f"- Custo total: US$ {s['cost']:.6f}",
        "",
        "## Perguntas",
        "",
    ]
    for question in value["questions"].values():
        options = question["criteria"]
        items = options.items() if isinstance(options, dict) else (o.split(": ", 1) for o in options)
        lines.append(f"**{question['instructions']}**")
        lines += [f"- {name}: {text}" for name, text in items]
        lines.append("")
    lines += ["## Regra", ""]
    lines += [f"- {name}: {text}" for name, text in value["rule"].items()]
    lines += ["", "## Avaliações", ""]
    lines += ["| " + " | ".join(shape["columns"]) + " |", "|" + " --- |" * len(shape["columns"])]
    for r in value["rows"]:
        verdict = r["verdict"]
        mark = (
            "" if not verdict else ("concorda" if verdict["value"] == r["suggestion"] else verdict["value"])
        )
        lines.append("| " + " | ".join([*shape["row"](r), mark or "pendente"]) + " |")
    example = shape["example"]
    lines += [
        "",
        f"Para registrar: `aifw assess verdict --feature {feature} --id 1,2,3 --agree --by human:<nome>` "
        f"ou `aifw assess verdict --feature {feature} --id 4 {example} --by human:<nome>`, no seu terminal.",
    ]
    return "\n".join(lines) + "\n"


def short(paths):
    return ", ".join(p.removeprefix("docs/") for p in paths) or "—"


# How each feature appears in the report: questions, rule, table columns and one row per assessment.
SHAPES = {
    "tasks": dict(
        title="Avaliador de tarefas",
        questions=QUESTIONS,
        rule=PATH_RULE,
        columns=["#", "Pedido", "Risco (confiança)", "Piso do diff", "Importância", "Complexidade", "Caminho"]
        + ["Seu veredito"],
        row=lambda r: [
            str(r["id"]),
            cell(r["task"]),
            f"{r['risk']['value']} ({r['risk']['confidence']:.0%})",
            r["floor"]["level"] or "—",
            r["importance"]["value"],
            r["complexity"]["value"],
            r["path"],
        ],
        example="--value WORK",
    ),
    "impasse": dict(
        title="Impasse: tentativa repetida",
        questions={"same": SAME_ATTEMPT},
        rule={"repeat": f"probabilidade de {REPEAT_THRESHOLD} ou mais"},
        columns=[
            "#",
            "Caso",
            "Nova tentativa",
            "Mais parecida",
            "Probabilidade",
            "Sugestão",
            "Texto idêntico",
        ]
        + ["Seu veredito"],
        row=lambda r: [
            str(r["id"]),
            r["case"],
            cell(attempt_text(r["attempt"]), 120),
            max(r["comparisons"], key=lambda c: c["probability"])["attempt"],
            f"{r['maxProbability']:.0%}",
            r["suggestion"],
            "sim" if r["exactRepeat"] else "não",
        ],
        example="--value distinct",
    ),
    "context": dict(
        title="Seleção de contexto",
        questions={"relevant": RELEVANT_DOC},
        rule={
            "sugeridos": f"fora da seleção, com probabilidade de {SUGGEST_THRESHOLD} ou mais",
            "duvidosos": f"escolhidos só por palavra em comum, com probabilidade abaixo de {DOUBT_THRESHOLD}",
            "model": "seu veredito quando a seleção ajustada pelo modelo é pelo menos tão boa quanto a atual",
            "keyword": "seu veredito quando a seleção atual, por palavras, é melhor",
        },
        columns=[
            "#",
            "Tarefa",
            "Selecionados por palavra",
            "Sugeridos pelo modelo",
            "Duvidosos",
            "Seu veredito",
        ],
        row=lambda r: [
            str(r["id"]),
            cell(r["task"]),
            short(r["keywordSelection"]),
            short(r["suggested"]),
            short(r["doubtful"]),
        ],
        example="--value keyword",
    ),
    "intake": dict(
        title="Intake: respostas do Charter",
        questions={"specific": SPECIFIC_ANSWER},
        rule={
            "fraca": "resposta avaliada como vaga ou parcial; vira pergunta da entrevista, sem bloquear a aprovação",
            "right": "seu veredito quando as respostas marcadas como fracas (e só elas) estão certas",
            "wrong": "seu veredito quando o modelo marcou uma resposta boa como fraca, ou deixou passar uma fraca",
        },
        columns=["#", "Charter", "Avaliação por campo", "Respostas fracas", "Seu veredito"],
        row=lambda r: [
            str(r["id"]),
            r["charter"][:12],
            ", ".join(f"{f}: {v}" for f, v in r["levels"].items()) or "—",
            ", ".join(w["field"] for w in r["weakAnswers"]) or "nenhuma",
        ],
        example="--value wrong",
    ),
    "traceability": dict(
        title="Rastreabilidade da spec",
        questions={"covers": COVERS},
        rule={
            "fraco": f"par requisito e cenário com probabilidade abaixo de {WEAK_TRACE_THRESHOLD}; aviso, nunca bloqueio",
            "right": "seu veredito quando os pares marcados como fracos, e só eles, estão certos",
            "wrong": "seu veredito quando o modelo marcou um par bom como fraco, ou deixou passar um fraco",
        },
        columns=["#", "Mudança", "Pares avaliados", "Pares fracos", "Seu veredito"],
        row=lambda r: [
            str(r["id"]),
            r["change"],
            str(len(r["pairs"])),
            ", ".join(
                f"{w['requirement']} → {w['scenario']} ({w['probability']:.0%})" for w in r["weakTraces"]
            )
            or "nenhum",
        ],
        example="--value wrong",
    ),
    "decisions": dict(
        title="Catálogos de decisão: sinais sugeridos",
        questions={
            "driver": dict(
                instructions="A pergunta de cada direcionador do catálogo, respondida a partir do Charter e do pedido",
                criteria={
                    "sinais": "as alternativas do direcionador",
                    UNKNOWN_SIGNAL: "o texto não dá base para responder",
                },
            )
        },
        rule={
            "sugerido": f"resposta diferente de {UNKNOWN_SIGNAL} com confiança de {SIGNAL_CONFIDENCE} ou mais",
            "uso": "os sinais só entram no ranking oficial quando você os passa em --signals",
            "right": "seu veredito quando os sinais sugeridos estão certos",
            "wrong": "seu veredito quando algum sinal sugerido está errado ou faltou",
        },
        columns=["#", "Categoria", "Sinais sugeridos", "Ranking com eles", "Seu veredito"],
        row=lambda r: [
            str(r["id"]),
            r["category"],
            ", ".join(r["suggestedSignals"]) or "nenhum",
            ", ".join(f"{o['optionId']} ({o['score']:+d})" for o in r["ranking"]),
        ],
        example="--value wrong",
    ),
}


def pending_notices(root):
    """Session-start reminders for features that reached the shadow goal with verdicts still missing."""
    try:
        config = settings(root)
    except (OSError, KeyError, TypeError):
        return []
    if config["mode"] != "shadow":
        return []
    notices = []
    # The tasks assessor is always active (ADR-0037); verdicts on it are optional quality tracking.
    for feature in (f for f in FEATURES if f in config["features"] and f != "tasks"):
        summary = report(root, feature)["summary"]
        if summary["assessments"] >= ACTIVATION["requests"] and summary["judged"] < summary["assessments"]:
            notices.append(
                f"{feature} assessor: {summary['assessments']} shadow assessments recorded. Run "
                f"`aifw assess report --feature {feature}` and show it to the person so they can record verdicts."
            )
    return notices
