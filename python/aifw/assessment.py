"""Task assessment by a decision model, in shadow mode: it records a suggested path and never decides.

Three independent questions (risk, importance, complexity) go to the Decider through OpenRouter.
A fixed rule turns the answers into an execution path; facts from the git diff set a floor for risk
that the model cannot lower. A person later records whether they agree, which feeds activation.
"""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

from .common import AifwError, now, read_yaml, require

URL = "https://openrouter.ai/api/alpha/decisions"
DEFAULT_MODEL = "perplexity/pplx-decider-v1.2"
SHADOW_LOG = ".aifw/assessments/shadow.jsonl"
VERDICTS = ".aifw/assessments/verdicts.jsonl"
ACTIVATION = dict(requests=50, agreement=0.9)
LEVELS = ["L0", "L1", "L2", "L3"]
IMPORTANCE = ["baixa", "média", "alta", "crítica"]
COMPLEXITY = ["trivial", "simples", "moderada", "alta"]
PATHS = ["FAST", "WORK", "PLANNED", "CRITICAL"]
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
        allowlist=spec.get("externalAllowlist", []),
        classification=spec.get("dataClassification", "internal"),
    )


def blocker(config):
    """Why the assessor must not call the API, or None."""
    if config["mode"] != "shadow":
        return "assessment is off: set spec.assessment.mode to shadow in aifw.yaml"
    if "openrouter" not in config["allowlist"]:
        return "openrouter is not in spec.externalAllowlist; the task text would leave the machine"
    if config["classification"] in {"confidential", "restricted"}:
        return f"{config['classification']} projects never send task text to an external model"
    if not os.environ.get("OPENROUTER_API_KEY"):
        return "OPENROUTER_API_KEY is not set"
    return None


def ask(model, state, key):
    """One question to the decision model; raises AifwError when the service fails."""
    body = json.dumps(dict(model=model, state=state, questions={key: QUESTIONS[key]})).encode()
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
            return data["answers"][key], data.get("usage", {}).get("cost", 0)
        except (urllib.error.URLError, OSError, ValueError, KeyError) as error:
            if attempt == 2:
                raise AifwError("NOT_READY", f"Decision model unavailable: {error}") from error
            time.sleep(1 + attempt)


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
    entries = read_lines(Path(root) / SHADOW_LOG)
    record["id"] = len(entries) + 1
    append(Path(root) / SHADOW_LOG, record)
    return dict(status="recorded", mode="shadow", recorded=True, **record)


def read_lines(file):
    if not file.is_file():
        return []
    return [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines() if line.strip()]


def append(file, entry):
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + "\n")


def record_verdicts(root, ids, by, path=None, note=""):
    """The person's view on recorded assessments: agree with the suggested path, or name the right one."""
    entries = {e["id"]: e for e in read_lines(Path(root) / SHADOW_LOG)}
    missing = sorted(set(ids) - set(entries))
    require(not missing, f"No recorded assessment with id {missing}.", "NOT_READY")
    require(path is None or path in PATHS, f"--path must be one of {', '.join(PATHS)}.")
    written = []
    for assessment_id in ids:
        verdict = dict(
            id=assessment_id,
            path=path or entries[assessment_id]["path"],
            by=by,
            at=now(),
            note=note,
        )
        append(Path(root) / VERDICTS, verdict)
        written.append(verdict)
    return dict(status="recorded", verdicts=written)


def report(root):
    """Every assessment with the person's latest verdict, and whether the activation criteria hold."""
    entries = read_lines(Path(root) / SHADOW_LOG)
    verdicts = {v["id"]: v for v in read_lines(Path(root) / VERDICTS)}
    rows = [dict(e, verdict=verdicts.get(e["id"])) for e in entries]
    judged = [r for r in rows if r["verdict"]]
    agreed = [r for r in judged if r["verdict"]["path"] == r["path"]]
    demoted = [r for r in judged if r["verdict"]["path"] == "CRITICAL" and r["path"] != "CRITICAL"]
    agreement = len(agreed) / len(judged) if judged else 0
    ready = len(judged) >= ACTIVATION["requests"] and agreement >= ACTIVATION["agreement"] and not demoted
    return dict(
        questions=QUESTIONS,
        pathRule=PATH_RULE,
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


def render_report(value):
    """The report as Markdown, in the same shape as the manual review."""
    s = value["summary"]
    lines = [
        "# Avaliador de tarefas: relatório da sombra",
        "",
        f"- Pedidos avaliados: {s['assessments']} (meta: {s['criteria']['requests']})",
        f"- Com seu veredito: {s['judged']}",
        f"- Concordância: {s['agreement']:.0%} (meta: {s['criteria']['agreement']:.0%})",
        f"- CRITICAL rebaixados: {len(s['criticalDemoted'])} {s['criticalDemoted'] or ''}".rstrip(),
        f"- Critério de ativação atingido: {'sim' if s['criteriaMet'] else 'não'}",
        f"- Custo total: US$ {s['cost']:.6f}",
        "",
        "## Perguntas",
        "",
    ]
    for key, question in value["questions"].items():
        options = question["criteria"]
        items = options.items() if isinstance(options, dict) else (o.split(": ", 1) for o in options)
        lines.append(f"**{question['instructions']}**")
        lines += [f"- {name}: {text}" for name, text in items]
        lines.append("")
    lines += ["## Regra do caminho", ""]
    lines += [f"- {name}: {text}" for name, text in value["pathRule"].items()]
    lines += [
        "",
        "## Avaliações",
        "",
        "| # | Pedido | Risco (confiança) | Piso do diff | Importância | Complexidade | Caminho | Seu veredito |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in value["rows"]:
        verdict = r["verdict"]
        mark = "" if not verdict else ("concorda" if verdict["path"] == r["path"] else verdict["path"])
        task = r["task"].replace("|", "/").replace("\n", " ")
        lines.append(
            f"| {r['id']} | {task[:90]} | {r['risk']['value']} ({r['risk']['confidence']:.0%}) | "
            f"{r['floor']['level'] or '—'} | {r['importance']['value']} | {r['complexity']['value']} | "
            f"{r['path']} | {mark or 'pendente'} |"
        )
    lines += [
        "",
        "Para registrar: `aifw assess verdict --id 1,2,3 --agree --by human:<nome>` "
        "ou `aifw assess verdict --id 4 --path WORK --by human:<nome>`, no seu terminal.",
    ]
    return "\n".join(lines) + "\n"


def shadow_count(root):
    file = Path(root) / SHADOW_LOG
    if not file.is_file():
        return 0
    return sum(1 for line in file.read_text(encoding="utf-8").splitlines() if line.strip())
