"""Assessments by a decision model, in shadow mode: they record what the model suggests and never decide.

Each feature asks the Decider through OpenRouter and writes its suggestion to a local log:

- tasks: risk, importance and complexity of a request, turned into an execution path by a fixed rule;
  facts from the git diff set a floor for risk that the model cannot lower.
- impasse: whether a new correction attempt repeats an earlier one in other words.

A person later records whether they agree, which feeds a future activation decision.
"""

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

from .common import AifwError, now, read_yaml, require

URL = "https://openrouter.ai/api/alpha/decisions"
DEFAULT_MODEL = "perplexity/pplx-decider-v1.2"
FEATURES = ("tasks", "impasse")
LOGS = {
    "tasks": (".aifw/assessments/shadow.jsonl", ".aifw/assessments/verdicts.jsonl"),
    "impasse": (".aifw/assessments/impasse.jsonl", ".aifw/assessments/impasse-verdicts.jsonl"),
}
SHADOW_LOG, VERDICTS = LOGS["tasks"]
ACTIVATION = dict(requests=50, agreement=0.9)
REPEAT_THRESHOLD = 0.7
LEVELS = ["L0", "L1", "L2", "L3"]
IMPORTANCE = ["baixa", "média", "alta", "crítica"]
COMPLEXITY = ["trivial", "simples", "moderada", "alta"]
PATHS = ["FAST", "WORK", "PLANNED", "CRITICAL"]
VALUES = {"tasks": PATHS, "impasse": ["repeat", "distinct"]}
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
PATH_RULE = {
    "FAST": "risco L0, complexidade trivial ou simples, importância baixa ou média: Haiku executa",
    "WORK": "risco L1, ou L0 com complexidade moderada ou alta, ou com importância alta ou crítica: Sonnet executa",
    "PLANNED": "risco L2, ou L1 com complexidade alta: Opus planeja, Sonnet executa, Opus revisa",
    "CRITICAL": "risco L3: Opus planeja e executa, revisor independente e aprovação humana",
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


def assess(root, task, use_diff=False, base=None, call=ask):
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
        risk=dict(value=model_risk, confidence=round(risk.get("confidence", 0), 3)),
        importance=dict(value=most_likely(importance, IMPORTANCE), level=round(importance["score"], 2)),
        complexity=dict(value=most_likely(complexity, COMPLEXITY), level=round(complexity["score"], 2)),
        floor=dict(level=floor, reasons=floor_reasons),
        finalRisk=final_risk,
        cost=round(sum(cost for _, cost in results.values()), 8),
    )
    record["path"] = path_for(final_risk, record["importance"]["value"], record["complexity"]["value"])
    return dict(status="recorded", mode="shadow", recorded=True, **store(root, "tasks", record))


def fingerprint(attempt):
    """Same normalization as impasse.record_attempt, kept here so this module never changes the hook's imports."""
    text = "\n".join(" ".join(attempt[k].lower().split()) for k in ("hypothesis", "intervention"))
    return sha256(text.encode()).hexdigest()


def attempt_text(attempt):
    return f"Hipótese: {attempt['hypothesis']}\nIntervenção: {attempt['intervention']}"


def compare_attempt(root, case, attempt, call=decide):
    """Shadow check: how likely the new attempt repeats each earlier one. Never changes the case."""
    config = settings(root)
    reason = blocker(config, "impasse")
    previous = case["attempts"]
    if reason or not previous:
        return dict(status="unavailable" if reason else "nothing-to-compare", reason=reason, recorded=False)

    def same(earlier):
        state = f"Tentativa anterior:\n{attempt_text(earlier)}\n\nNova tentativa:\n{attempt_text(attempt)}"
        answers, cost = call(config["model"], state, {"same": SAME_ATTEMPT})
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
    entries = read_lines(Path(root) / log)
    verdicts = {v["id"]: v for v in read_lines(Path(root) / verdict_log)}
    rows = [dict(e, suggestion=suggestion(feature, e), verdict=verdicts.get(e["id"])) for e in entries]
    judged = [r for r in rows if r["verdict"]]
    agreed = [r for r in judged if r["verdict"]["value"] == r["suggestion"]]
    demoted = [r for r in judged if r["verdict"]["value"] == "CRITICAL" and r["suggestion"] != "CRITICAL"]
    agreement = len(agreed) / len(judged) if judged else 0
    ready = len(judged) >= ACTIVATION["requests"] and agreement >= ACTIVATION["agreement"] and not demoted
    questions = QUESTIONS if feature == "tasks" else {"same": SAME_ATTEMPT}
    return dict(
        feature=feature,
        questions=questions,
        rule=PATH_RULE if feature == "tasks" else {"repeat": f"probabilidade de {REPEAT_THRESHOLD} ou mais"},
        rows=rows,
        summary=dict(
            assessments=len(rows),
            judged=len(judged),
            agreement=round(agreement, 3),
            criticalDemoted=[r["id"] for r in demoted],
            cost=round(sum(r.get("cost", 0) for r in rows), 6),
            criteria=dict(ACTIVATION, criticalDemoted=0),
            criteriaMet=ready,
        ),
    )


def cell(text, size=90):
    return text.replace("|", "/").replace("\n", " ")[:size]


def render_report(value):
    """The report as Markdown, in the same shape as the manual review."""
    s, feature = value["summary"], value["feature"]
    title = "Avaliador de tarefas" if feature == "tasks" else "Impasse: tentativa repetida"
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
    if feature == "tasks":
        lines += [
            "| # | Pedido | Risco (confiança) | Piso do diff | Importância | Complexidade | Caminho | Seu veredito |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    else:
        lines += [
            "| # | Caso | Nova tentativa | Mais parecida | Probabilidade | Sugestão | Texto idêntico | Seu veredito |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    for r in value["rows"]:
        verdict = r["verdict"]
        mark = (
            "" if not verdict else ("concorda" if verdict["value"] == r["suggestion"] else verdict["value"])
        )
        if feature == "tasks":
            lines.append(
                f"| {r['id']} | {cell(r['task'])} | {r['risk']['value']} ({r['risk']['confidence']:.0%}) | "
                f"{r['floor']['level'] or '—'} | {r['importance']['value']} | {r['complexity']['value']} | "
                f"{r['path']} | {mark or 'pendente'} |"
            )
        else:
            closest = max(r["comparisons"], key=lambda c: c["probability"])
            lines.append(
                f"| {r['id']} | {r['case']} | {cell(attempt_text(r['attempt']), 120)} | {closest['attempt']} | "
                f"{r['maxProbability']:.0%} | {r['suggestion']} | {'sim' if r['exactRepeat'] else 'não'} | "
                f"{mark or 'pendente'} |"
            )
    example = "--value WORK" if feature == "tasks" else "--value distinct"
    lines += [
        "",
        f"Para registrar: `aifw assess verdict --feature {feature} --id 1,2,3 --agree --by human:<nome>` "
        f"ou `aifw assess verdict --feature {feature} --id 4 {example} --by human:<nome>`, no seu terminal.",
    ]
    return "\n".join(lines) + "\n"


def pending_notices(root):
    """Session-start reminders for features that reached the shadow goal with verdicts still missing."""
    try:
        config = settings(root)
    except (OSError, KeyError, TypeError):
        return []
    if config["mode"] != "shadow":
        return []
    notices = []
    for feature in (f for f in FEATURES if f in config["features"]):
        summary = report(root, feature)["summary"]
        if summary["assessments"] >= ACTIVATION["requests"] and summary["judged"] < summary["assessments"]:
            notices.append(
                f"{feature} assessor: {summary['assessments']} shadow assessments recorded. Run "
                f"`aifw assess report --feature {feature}` and show it to the person so they can record verdicts."
            )
    return notices
