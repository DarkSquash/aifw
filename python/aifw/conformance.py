"""Evaluate observable agent events and cognitive routing fixtures."""

from pathlib import Path

from .common import read_yaml, require, validate
from .routing import route_task


def evaluate_trace(case, trace):
    violations = []

    def indices(event):
        return [i for i, value in enumerate(trace["events"]) if value["type"] == event]

    def violation(code, severity, event, message):
        violations.append(dict(code=code, severity=severity, event=event, message=message))

    if trace["caseId"] != case["id"]:
        violation(
            "CASE_MISMATCH",
            "high",
            trace["caseId"],
            f"Trace {trace['caseId']} does not belong to case {case['id']}.",
        )
    rules = case["requirements"]
    for event in rules["requiredEvents"]:
        if not indices(event):
            violation("REQUIRED_EVENT_MISSING", "high", event, f"Required event {event} is missing.")
    for event in rules["forbiddenEvents"]:
        if indices(event):
            violation("FORBIDDEN_EVENT", "critical", event, f"Forbidden event {event} occurred.")
    for order in rules["ordering"]:
        before, after = indices(order["before"]), indices(order["after"])
        if before and after and before[0] >= after[0]:
            violation(
                "ORDER_VIOLATION",
                "high",
                order["after"],
                f"{order['before']} must occur before {order['after']}.",
            )
    for protected in rules["approvalBefore"]:
        for index in indices(protected):
            event = trace["events"][index]
            approvals = [a for a in trace["events"][:index] if a["type"] == "human-approval"]
            if not any(
                "approvalId" not in event or a.get("approvalId") == event["approvalId"] for a in approvals
            ):
                violation(
                    "APPROVAL_MISSING",
                    "critical",
                    protected,
                    f"{protected} occurred without a matching prior human approval.",
                )
    for event in rules["evidenceRequiredFor"]:
        for index in indices(event):
            if not trace["events"][index].get("evidence"):
                violation("EVIDENCE_MISSING", "medium", event, f"{event} has no persisted evidence.")
    return {"caseId": case["id"], "pass": not violations, "violations": violations}


def run_conformance(cases_dir, traces_dir):
    results = []
    files = sorted([*Path(cases_dir).glob("*.yaml"), *Path(cases_dir).glob("*.yml")])
    for file in files:
        case = validate(read_yaml(file), "conformance-case.schema.json")
        trace = validate(read_yaml(Path(traces_dir) / f"{file.stem}.yaml"), "agent-trace.schema.json")
        results.append(evaluate_trace(case, trace))
    passed = sum(r["pass"] for r in results)
    return {
        "pass": bool(results) and passed == len(results),
        "passRate": passed / len(results) if results else 0,
        "criticalFailures": sum(v["severity"] == "critical" for r in results for v in r["violations"]),
        "cases": results,
    }


def evaluate_routing_cases(file):
    value = read_yaml(file)
    require(
        isinstance(value, dict) and isinstance(value.get("cases"), list),
        "Routing evaluation requires a cases array.",
    )
    cases = value["cases"]
    for case in cases:
        require(
            isinstance(case.get("id"), str)
            and isinstance(case.get("critical"), bool)
            and case.get("expectedRoute") in {"FAST", "WORK", "BRAIN"}
            and isinstance(case.get("input"), dict),
            "Malformed routing case.",
        )
    require(len({c["id"] for c in cases}) == len(cases), "Routing case IDs must be unique.")
    failures = []
    for case in cases:
        actual = route_task(case["input"])["route"]
        if actual != case["expectedRoute"]:
            failures.append(
                dict(
                    id=case["id"],
                    expectedRoute=case["expectedRoute"],
                    actualRoute=actual,
                    critical=case["critical"],
                )
            )
    passed = len(cases) - len(failures)
    return dict(
        cases=len(cases),
        passed=passed,
        passRate=passed / len(cases) if cases else 0,
        criticalFailures=sum(f["critical"] for f in failures),
        failures=failures,
    )
