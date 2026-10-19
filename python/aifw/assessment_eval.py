"""`aifw assess eval`: run a reviewable suite in evals/assessment against the decision model.

Each suite holds cases with the answer a person agreed on. The run asks the model the same questions the
shadow features ask, so a model change or a new cut-off can be checked before it reaches the project.
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import assessment as a
from .common import assets, read_yaml, require

SWEEP = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)


def suite_file(root, feature, cases=None):
    if cases:
        return Path(cases)
    local = Path(root) / f"evals/assessment/{feature}-cases.yaml"
    return local if local.is_file() else assets() / f"evals/assessment/{feature}-cases.yaml"


def evaluate(root, feature, cases=None, call=None):
    """Accuracy of the model on one suite; nothing is recorded in the project's shadow logs."""
    require(feature in a.FEATURES, f"Unknown feature {feature}.")
    call = call or a.decide
    config = a.settings(root)
    # A suite can be run before its feature is switched on; the other guards still apply.
    reason = a.blocker(dict(config, features=a.FEATURES), feature)
    if reason:
        return dict(status="unavailable", feature=feature, reason=reason)
    file = suite_file(root, feature, cases)
    require(file.is_file(), f"No suite for {feature}: {file}")
    suite = read_yaml(file)
    require(suite.get("feature") == feature, f"{file} is not a {feature} suite.")
    model = config["model"]
    rows, extra = RUNNERS[feature](root, model, suite, call)
    right = sum(r["ok"] for r in rows)
    return dict(
        status="evaluated",
        feature=feature,
        model=model,
        suite=str(file),
        cases=len(rows),
        right=right,
        accuracy=round(right / len(rows), 3) if rows else 0.0,
        cost=round(sum(r.pop("cost") for r in rows), 6),
        **extra,
        failures=[r for r in rows if not r["ok"]],
    )


def pool_map(function, items, workers=8):
    with ThreadPoolExecutor(workers) as pool:
        return list(pool.map(function, items))


def sweep(rows, positive, current):
    """Accuracy at each cut-off for a yes/no probability; `positive` is the expected label at or above it."""
    return dict(
        threshold=current,
        sweep={
            str(t): sum((r["probability"] >= t) == (r["expected"] == positive) for r in rows) for t in SWEEP
        },
    )


def run_tasks(root, model, suite, call):
    def one(case):
        answers = {key: call(model, case["task"], {key: a.QUESTIONS[key]}) for key in a.QUESTIONS}
        risk = answers["risk"][0]["risk"]["choice"]
        importance = a.most_likely(answers["importance"][0]["importance"], a.IMPORTANCE)
        complexity = a.most_likely(answers["complexity"][0]["complexity"], a.COMPLEXITY)
        path = a.path_for(risk, importance, complexity)
        got = dict(risk=risk, importance=importance, complexity=complexity, path=path)
        return dict(
            id=case["id"],
            expected={k: case[k] for k in got},
            got=got,
            ok=path == case["path"],
            below=a.PATHS.index(path) < a.PATHS.index(case["path"]),
            cost=sum(cost for _, cost in answers.values()),
        )

    rows = pool_map(one, suite["cases"])
    stages = {
        k: sum(r["got"][k] == r["expected"][k] for r in rows) for k in ("risk", "importance", "complexity")
    }
    return rows, dict(exactByStage=stages, pathBelowExpected=sum(r["below"] for r in rows))


def run_impasse(root, model, suite, call):
    def one(case):
        answers, cost = call(model, a.pair_state(case["previous"], case["new"]), {"same": a.SAME_ATTEMPT})
        p = round(answers["same"]["noul"], 3)
        ok = (p >= a.REPEAT_THRESHOLD) == (case["expected"] == "repeat")
        return dict(id=case["id"], expected=case["expected"], probability=p, ok=ok, cost=cost)

    rows = pool_map(one, suite["cases"])
    return rows, sweep(rows, "repeat", a.REPEAT_THRESHOLD)


def run_traceability(root, model, suite, call):
    def one(case):
        state = a.trace_text(case["requirement"], case["scenario"])
        answers, cost = call(model, state, {"covers": a.COVERS})
        p = round(answers["covers"]["noul"], 3)
        ok = (p >= a.WEAK_TRACE_THRESHOLD) == (case["expected"] == "covers")
        return dict(id=case["id"], expected=case["expected"], probability=p, ok=ok, cost=cost)

    rows = pool_map(one, suite["cases"])
    return rows, sweep(rows, "covers", a.WEAK_TRACE_THRESHOLD)


def run_intake(root, model, suite, call):
    def one(case):
        state = a.answer_state(case["field"], case["answer"])
        answers, cost = call(model, state, {"specific": a.SPECIFIC_ANSWER})
        level = a.most_likely(answers["specific"], a.SPECIFICITY)
        weak = level != "específica"
        ok = weak == (case["expected"] != "específica")
        return dict(id=case["id"], expected=case["expected"], got=level, ok=ok, cost=cost)

    rows = pool_map(one, suite["cases"])
    return rows, dict(exactLevel=sum(r["got"] == r["expected"] for r in rows))


def run_decisions(root, model, suite, call):
    from .catalogs import load_decision_catalogs

    drivers = [d for c in load_decision_catalogs(root) for d in c["spec"]["drivers"]]

    def one(job):
        case, driver = job
        answers, cost = call(model, f"Projeto: {case['project']}", {"driver": a.driver_question(driver)})
        answer = answers["driver"]
        confident = (
            answer["choice"] != a.UNKNOWN_SIGNAL and answer.get("confidence", 0) >= a.SIGNAL_CONFIDENCE
        )
        suggested = answer["choice"] if confident else a.UNKNOWN_SIGNAL
        expected = case["expected"].get(driver["id"], a.UNKNOWN_SIGNAL)
        return dict(
            id=f"{case['id']}/{driver['id']}",
            expected=expected,
            got=suggested,
            confidence=round(answer.get("confidence", 0), 3),
            # Silence is never wrong: the person types the signals the model leaves out.
            ok=suggested in {expected, a.UNKNOWN_SIGNAL},
            cost=cost,
        )

    rows = pool_map(one, [(case, driver) for case in suite["cases"] for driver in drivers], workers=12)
    labeled = [r for r in rows if r["expected"] != a.UNKNOWN_SIGNAL]
    return rows, dict(
        supportedSignals=len(labeled),
        suggestedRight=sum(r["got"] == r["expected"] for r in labeled),
        invented=sum(r["expected"] == a.UNKNOWN_SIGNAL and r["got"] != a.UNKNOWN_SIGNAL for r in rows),
    )


def run_context(root, model, suite, call):
    from .context import check_context, select_context

    docs = check_context(root)["documents"]
    known = {d["path"] for d in docs}
    for case in suite["cases"]:
        missing = set(case["expected"]) - known
        require(
            not missing,
            f"Case {case['id']} expects documents this project does not index.",
            details=sorted(missing),
        )

    def one(case):
        def relevant(doc):
            answers, cost = call(model, a.doc_state(case["task"], doc), {"relevant": a.RELEVANT_DOC})
            return doc["path"], answers["relevant"]["noul"], cost

        found = pool_map(relevant, docs, workers=16)
        probability = {path: p for path, p, _ in found}
        chosen = {s["path"]: s["reasons"] for s in select_context(root, case["task"])["selected"]}
        suggested = {p for p, v in probability.items() if v >= a.SUGGEST_THRESHOLD}
        doubtful = {p for p, why in chosen.items() if why == ["task"] and probability[p] < a.DOUBT_THRESHOLD}
        adjusted = (set(chosen) | suggested) - doubtful
        expected = set(case["expected"])
        return dict(
            id=case["id"],
            expected=sorted(expected),
            keywordCoverage=round(len(expected & set(chosen)) / len(expected), 3),
            coverage=round(len(expected & adjusted) / len(expected), 3),
            missed=sorted(expected - adjusted),
            ok=expected <= adjusted,
            cost=sum(c for *_, c in found),
        )

    rows = [one(case) for case in suite["cases"]]  # each case already runs its documents in parallel
    n = len(rows) or 1
    return rows, dict(
        keywordCoverage=round(sum(r["keywordCoverage"] for r in rows) / n, 3),
        coverage=round(sum(r["coverage"] for r in rows) / n, 3),
    )


RUNNERS = dict(
    tasks=run_tasks,
    impasse=run_impasse,
    context=run_context,
    intake=run_intake,
    traceability=run_traceability,
    decisions=run_decisions,
)


def render(result):
    if result["status"] != "evaluated":
        return f"{result['feature']}: não avaliado ({result['reason']})"
    lines = [
        f"{result['feature']} — {result['model']}",
        f"acertos {result['right']}/{result['cases']} ({result['accuracy']:.0%}) | custo US$ {result['cost']:.6f}",
    ]
    if "sweep" in result:
        lines.append(f"corte atual {result['threshold']}; acertos por corte:")
        lines += [f"  {t}: {n}/{result['cases']}" for t, n in result["sweep"].items()]
    for key in ("exactByStage", "pathBelowExpected", "exactLevel", "supportedSignals", "suggestedRight",
                "invented", "keywordCoverage", "coverage"):  # fmt: skip
        if key in result:
            lines.append(f"{key}: {result[key]}")
    if result["failures"]:
        lines.append("divergências:")
        lines += [
            f"  {r['id']}: esperado {r['expected']}, modelo {r.get('got', r.get('probability', r.get('missed')))}"
            for r in result["failures"]
        ]
    return "\n".join(lines)
