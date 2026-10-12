import pytest

from aifw.common import AifwError
from aifw import permissions, impasse, waiver

AT = "2026-09-06T03:00:00.000Z"


@pytest.mark.parametrize(
    "action,expected",
    [
        ({"kind": "read-only"}, "allow"),
        ({"kind": "git-local"}, "allow"),
        ({"kind": "git-remote"}, "require-approval"),
        ({"kind": "deploy", "environment": "production"}, "require-approval"),
        ({"kind": "deploy", "environment": "preview"}, "allow"),
        ({"kind": "external-read", "service": "unknown"}, "deny"),
        ({"kind": "external-write", "service": "known"}, "require-approval"),
        ({"kind": "filesystem-write", "destructive": True}, "require-approval"),
    ],
)
def test_permissions(action, expected):
    policy = dict(permissions.DEFAULT_PERMISSION_POLICY, externalAllowlist=["known"])
    assert permissions.authorize_action(action, policy)["decision"] == expected


def test_no_delegation_escalation():
    assert permissions.validate_delegation(["read"], ["write", "read", "write"]) == {
        "valid": False,
        "excessCapabilities": ["write"],
    }


def test_break_glass_window():
    grant = dict(
        incidentId="INC-1",
        scope=["repair"],
        approvedBy="human:test",
        approvedAt=AT,
        expiresAt="2026-09-06T04:00:00Z",
        reason="Repair incident",
    )
    assert permissions.validate_break_glass(grant, "repair", AT)["valid"]
    assert not permissions.validate_break_glass(grant, "deploy", AT)["valid"]
    assert not permissions.validate_break_glass(grant, "repair", "2026-09-06T04:00:00Z")["valid"]


def attempt(index):
    return dict(
        id=f"a{index}",
        hypothesis=f"Cause {index}",
        intervention=f"Fix {index}",
        evidence=["test.txt"],
        outcome="failure",
        occurredAt=AT,
    )


def test_impasse_requires_approval_and_revalidation():
    initial = impasse.create_impasse_case("case", "L3")
    case = impasse.record_attempt(initial, attempt(1))
    assert initial["attempts"] == []
    assert not impasse.mutation_allowed(case, True)
    case = impasse.record_attempt(case, attempt(2))
    assert case["state"] == "OPEN"
    assert not impasse.mutation_allowed(case, False)
    with pytest.raises(AifwError):
        impasse.record_attempt(case, attempt(3))
    case = impasse.request_human_review(
        case, dict(suspectedRuleId="rule", explanation="Conflict", proposedChange="Revise")
    )
    with pytest.raises(AifwError):
        impasse.apply_human_decision(
            case, dict(approved=True, decidedBy="agent:test", decidedAt=AT, decisionRecord="adr.md")
        )
    case = impasse.apply_human_decision(
        case, dict(approved=True, decidedBy="human:test", decidedAt=AT, decisionRecord="adr.md")
    )
    assert case["state"] == "HALF_OPEN"
    with pytest.raises(AifwError):
        impasse.record_revalidation(case, dict(passed=True, evidence=[], updatedArtifacts=[]))
    case = impasse.record_revalidation(
        case, dict(passed=True, evidence=["test.txt"], updatedArtifacts=["adr.md"], occurredAt=AT)
    )
    assert case["state"] == "RESOLVED" and "openReason" not in case
    assert impasse.mutation_allowed(case, True)


def test_repeated_strategy_opens_immediately():
    case = impasse.record_attempt(impasse.create_impasse_case("case", "L0"), attempt(1))
    repeated = dict(attempt(1), hypothesis=" CAUSE   1 ", intervention=" FIX  1 ")
    assert impasse.record_attempt(case, repeated)["openReason"] == "repeated-strategy"


def test_waiver_cannot_override_invariant():
    data = dict(
        id="w",
        ruleId="core",
        scope=["task"],
        reason="Justified",
        requestedBy="agent:test",
        approvedBy="human:test",
        approvedAt=AT,
        expiresAt="2026-09-07T03:00:00Z",
        checkpoint="before",
    )
    with pytest.raises(AifwError):
        waiver.create_waiver(data, non_waivable_rule_ids=["core"])
    value = waiver.create_waiver(data)
    assert waiver.is_waiver_active(value, AT)
    assert not waiver.is_waiver_active(value, "2026-09-07T03:00:00Z")
