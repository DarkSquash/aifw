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
    from . import judge

    config = a.settings(root)
    # A suite can be run before its feature is switched on; the other guards still apply.
    if feature == "judge":
        call, reason, model = call or judge.ask_claude, judge.blocker(config, False), "+".join(judge.MODELS)
    else:
        call, reason, model = (
            call or a.decide,
            a.blocker(dict(config, features=a.FEATURES), feature),
            config["model"],
        )
    if reason:
        return dict(status="unavailable", feature=feature, reason=reason)
    file = suite_file(root, feature, cases)
    require(file.is_file(), f"No suite for {feature}: {file}")
    suite = read_yaml(file)
    require(suite.get("feature") == feature, f"{file} is not a {feature} suite.")
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


def percentile(values, share):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(share * len(ordered)))] if ordered else 0


def strategy(rows, pick):
    """Accuracy, releases of a command that should ask, latency and cost of one way to choose the judge."""
    picked = [(r, *pick(r)) for r in rows]
    latencies = [ms for *_, ms, _ in picked]
    released = [r["id"] for r, got, *_ in picked if got == "harmless" and r["expected"] == "ask"]
    return dict(
        right=sum(got == r["expected"] for r, got, *_ in picked),
        released=released,
        injectionReleased=[
            i for i in released if "injection" in next(r["tags"] for r in rows if r["id"] == i)
        ],
        latencyMs=dict(
            p50=percentile(latencies, 0.5), p95=percentile(latencies, 0.95), max=max(latencies, default=0)
        ),
        overHookTimeout=sum(ms > 10_000 for ms in latencies),
        cost=round(sum(cost for *_, cost in picked), 6),
    )


def run_judge(root, model, suite, call):
    """Each case runs on Haiku and on Sonnet, so every way to choose the judge is measured on the same answers."""
    import tempfile

    from . import judge

    def verdict(answer):
        return "harmless" if answer["verdict"] == "harmless" else "ask"  # unknown asks, like the hook

    def one(case):
        with tempfile.TemporaryDirectory() as folder:
            for name, text in (case.get("files") or {}).items():
                path = Path(folder) / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8", newline="\n")
            files = judge.sources(folder, case["command"])
        answers = {
            m: judge.judge_text(case["command"], files, case.get("claim"), call, (m,))[0]
            for m in judge.MODELS
        }
        first, second = (answers[m] for m in judge.MODELS)
        escalate = first["verdict"] == "unknown" or first["confidence"] < judge.ESCALATE_BELOW
        final = second if escalate else first
        mention = [w.lower() for w in case.get("mustMention", [])]
        return dict(
            id=case["id"],
            tags=case.get("tags", []),
            expected=case["expected"],
            got=verdict(final),
            answers={
                m: {k: a[k] for k in ("verdict", "confidence", "intent", "mismatch", "latencyMs", "cost")}
                for m, a in answers.items()
            },
            escalated=escalate,
            intentFaithful=None if not mention else any(w in final["intent"].lower() for w in mention),
            mismatchRight=None
            if "expectedMismatch" not in case
            else final["mismatch"] == case["expectedMismatch"],
            ok=verdict(final) == case["expected"],
            cost=sum(a.get("cost") or 0 for a in answers.values()) if escalate else first.get("cost") or 0,
        )

    rows = pool_map(one, suite["cases"], workers=3)  # parallel CLI starts slow each other down; keep it low

    def alone(m):
        return lambda r: (
            verdict(r["answers"][m]),
            r["answers"][m]["latencyMs"],
            r["answers"][m].get("cost") or 0,
        )

    def escalated(r):
        ms = (
            sum(a["latencyMs"] for a in r["answers"].values())
            if r["escalated"]
            else r["answers"]["haiku"]["latencyMs"]
        )
        return r["got"], ms, r["cost"]

    faithful = [r["intentFaithful"] for r in rows if r["intentFaithful"] is not None]
    mismatch = [r["mismatchRight"] for r in rows if r["mismatchRight"] is not None]
    return rows, dict(
        strategies={
            # The tier rule (one level below the session) is Sonnet for Opus sessions and Haiku otherwise.
            "haiku-only (tier: sessões Sonnet e Haiku)": strategy(rows, alone("haiku")),
            "sonnet-only (tier: sessões Opus)": strategy(rows, alone("sonnet")),
            "haiku-escala-sonnet": strategy(rows, escalated),
        },
        escalated=sum(r["escalated"] for r in rows),
        intentFaithful=f"{sum(faithful)}/{len(faithful)}",
        mismatchRight=f"{sum(mismatch)}/{len(mismatch)}",
    )


RUNNERS = dict(
    tasks=run_tasks,
    impasse=run_impasse,
    context=run_context,
    intake=run_intake,
    traceability=run_traceability,
    decisions=run_decisions,
    judge=run_judge,
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
                "invented", "keywordCoverage", "coverage", "escalated", "intentFaithful",
                "mismatchRight"):  # fmt: skip
        if key in result:
            lines.append(f"{key}: {result[key]}")
    for name, s in result.get("strategies", {}).items():
        ms = s["latencyMs"]
        lines.append(
            f"{name}: acertos {s['right']}/{result['cases']}, liberaria {len(s['released'])} que deviam pedir "
            f"(injeção: {len(s['injectionReleased'])}), latência p50 {ms['p50'] / 1000:.1f} s, "
            f"p95 {ms['p95'] / 1000:.1f} s, máx {ms['max'] / 1000:.1f} s, acima de 10 s: {s['overHookTimeout']}"
        )
    if result["failures"]:
        lines.append("divergências:")
        lines += [
            f"  {r['id']}: esperado {r['expected']}, modelo {r.get('got', r.get('probability', r.get('missed')))}"
            for r in result["failures"]
        ]
    return "\n".join(lines)
