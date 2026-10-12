"""Evidence-driven impasse state machine; transitions never mutate inputs."""

from copy import deepcopy
from hashlib import sha256

from pathlib import Path

from .common import (
    AifwError,
    human,
    project_path,
    read_valid_yaml,
    read_yaml,
    require,
    timestamp,
    validate,
    write_yaml,
)


def create_impasse_case(case_id, impact):
    require(case_id.strip(), "An impasse case needs a stable id.", "NOT_READY")
    require(impact in {"L0", "L1", "L2", "L3"}, "Invalid impact.")
    return dict(
        id=case_id,
        impact=impact,
        state="NORMAL",
        attempts=[],
        attemptFingerprints=[],
        stopDestructiveChanges=False,
    )


def record_attempt(case, attempt):
    require(
        case["state"] in {"NORMAL", "SUSPECTED"},
        f"Attempts are frozen while the impasse is {case['state']}.",
        "IMPASSE_OPEN",
    )
    require(
        all(attempt.get(k, "").strip() for k in ("id", "hypothesis", "intervention", "occurredAt"))
        and attempt.get("evidence"),
        "A correction attempt needs a hypothesis, intervention and evidence.",
        "NOT_READY",
    )
    require(attempt["outcome"] in {"success", "failure", "inconclusive"}, "Invalid attempt outcome.")
    fingerprint = sha256(
        "\n".join(" ".join(attempt[k].lower().split()) for k in ("hypothesis", "intervention")).encode()
    ).hexdigest()
    result = deepcopy(case)
    if fingerprint in case["attemptFingerprints"]:
        return dict(result, state="OPEN", openReason="repeated-strategy", stopDestructiveChanges=True)
    result["attempts"].append(deepcopy(attempt))
    result["attemptFingerprints"].append(fingerprint)
    if attempt["outcome"] == "success":
        return dict(result, state="RESOLVED", stopDestructiveChanges=False)
    exhausted = sum(a["outcome"] == "failure" for a in result["attempts"]) >= (
        5 if case["impact"] in {"L0", "L1"} else 2
    )
    if exhausted:
        result["openReason"] = "distinct-attempt-limit"
    return dict(result, state="OPEN" if exhausted else "SUSPECTED", stopDestructiveChanges=True)


def request_human_review(case, proposal):
    require(
        case["state"] == "OPEN"
        and all(proposal.get(k, "").strip() for k in ("suspectedRuleId", "explanation", "proposedChange"))
        and any(a["evidence"] for a in case["attempts"]),
        "Human review requires an open impasse, evidence and a concrete framework proposal.",
        "NOT_READY",
    )
    return dict(
        deepcopy(case), state="HUMAN_REVIEW", proposal=deepcopy(proposal), stopDestructiveChanges=True
    )


def apply_human_decision(case, decision):
    require(
        case["state"] == "HUMAN_REVIEW",
        "A human decision can only be applied during HUMAN_REVIEW.",
        "NOT_READY",
    )
    require(
        decision.get("approved") and decision.get("decisionRecord", "").strip(),
        "Approval requires a persisted decision record.",
        "APPROVAL_REQUIRED",
    )
    human(decision.get("decidedBy"))
    try:
        timestamp(decision.get("decidedAt"))
    except AifwError as error:
        raise AifwError("APPROVAL_REQUIRED", "Approval requires a valid timestamp.") from error
    return dict(
        deepcopy(case), state="HALF_OPEN", humanDecision=deepcopy(decision), stopDestructiveChanges=True
    )


def record_revalidation(case, result):
    require(
        case["state"] == "HALF_OPEN",
        "Revalidation is only valid after an approved framework change.",
        "NOT_READY",
    )
    require(
        result["evidence"] and result["updatedArtifacts"],
        "Revalidation requires test evidence and updated persisted artifacts.",
        "NOT_READY",
    )
    updated = deepcopy(case)
    if result["passed"]:
        updated.pop("openReason", None)
    return dict(
        updated,
        state="RESOLVED" if result["passed"] else "OPEN",
        revalidation=deepcopy(result),
        stopDestructiveChanges=not result["passed"],
    )


def mutation_allowed(case, destructive):
    return case["state"] not in {"OPEN", "HUMAN_REVIEW"} and not (
        destructive and case["stopDestructiveChanges"]
    )


def impasse_id(value):
    return value if value.startswith("impasse:") else "impasse:" + value


def case_file(root, case_id):
    return project_path(root, f".aifw/impasses/{impasse_id(case_id).removeprefix('impasse:')}.yaml")


def load_case(root, case_id):
    file = case_file(root, case_id)
    require(file.is_file(), f"Impasse case does not exist: {impasse_id(case_id)}", "NOT_READY")
    return validate(read_yaml(file), "impasse.schema.json")


def save_case(root, case, exclusive=False):
    validate(case, "impasse.schema.json")
    write_yaml(case_file(root, case["id"]), case, exclusive=exclusive)
    return case


def load_cases(root):
    folder = Path(root) / ".aifw/impasses"
    return [read_valid_yaml(f, "impasse.schema.json") for f in sorted(folder.glob("*.yaml"))]
