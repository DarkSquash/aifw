"""Explicit permissions, bounded delegation and temporary incident grants."""

from pathlib import Path

from .common import AifwError, now, read_valid_yaml, read_yaml, require, timestamp

DEFAULT_PERMISSION_POLICY = dict(
    externalAllowlist=[],
    approveRemoteMutations=True,
    approveProduction=True,
    approveExternalWrites=True,
    approveDestructiveWrites=True,
)


def authorize_action(request, policy):
    kind = request["kind"]
    decision, reason = "allow", "read-only"
    if kind == "read-only":
        pass
    elif kind == "git-local":
        reason = "local-version-control"
    elif kind == "git-remote":
        decision, reason = (
            ("require-approval", "remote-mutation")
            if policy["approveRemoteMutations"]
            else ("allow", "policy-allows-remote-mutation")
        )
    elif kind == "deploy":
        decision, reason = (
            ("require-approval", "production-effect")
            if request["environment"] == "production" and policy["approveProduction"]
            else ("allow", f"{request['environment']}-deployment")
        )
    elif kind in {"external-read", "external-write"}:
        if request["service"] not in policy["externalAllowlist"]:
            decision, reason = "deny", "service-not-allowlisted"
        elif kind == "external-read":
            reason = "allowlisted-external-read"
        else:
            decision, reason = (
                ("require-approval", "external-side-effect")
                if policy["approveExternalWrites"]
                else ("allow", "policy-allows-external-write")
            )
    elif kind == "filesystem-write":
        decision, reason = (
            ("require-approval", "destructive-write")
            if request.get("destructive") and policy["approveDestructiveWrites"]
            else ("allow", "local-reversible-write")
        )
    else:
        require(False, f"Unknown action kind: {kind}")
    return dict(decision=decision, reason=reason)


def validate_break_glass(grant, requested_scope, at=None):
    reasons = []
    if not grant["incidentId"].strip():
        reasons.append("incident-id")
    if not grant["approvedBy"].startswith("human:"):
        reasons.append("human-approval")
    if not grant["reason"].strip():
        reasons.append("reason")
    if requested_scope not in grant["scope"]:
        reasons.append("scope")
    try:
        start, end, current = (timestamp(v) for v in (grant["approvedAt"], grant["expiresAt"], at or now()))
        if end <= start:
            reasons.append("invalid-time-window")
        if current < start or current >= end:
            reasons.append("expired-or-not-active")
    except (AifwError, TypeError):
        reasons.append("invalid-time-window")
    return dict(valid=not reasons, reasons=reasons)


def load_permission_policy(root):
    return read_valid_yaml(Path(root) / ".aifw/permissions.yaml", "permissions.schema.json")


def decide_action(request, data, allowlist=None):
    """Apply a persisted PermissionPolicy file on top of authorize_action.

    The allowlist comes from aifw.yaml (externalAllowlist); the policy file keeps the write rule.
    """
    external = dict(dict(allowlist=[], writes="human-approval"), **data.get("externalServices", {}))
    decision = authorize_action(
        request,
        dict(
            externalAllowlist=external["allowlist"] if allowlist is None else allowlist,
            approveRemoteMutations=data["remoteMutation"] != "autonomous",
            approveProduction=True,
            approveExternalWrites=True,
            approveDestructiveWrites=True,
        ),
    )
    kind = request["kind"]
    production = request.get("environment") == "production"
    setting = {
        "git-local": data["localGit"],
        "git-remote": data["remoteMutation"],
        "deploy": data["productionDeployment" if production else "previewDeployment"],
        "external-write": external["writes"],
        "filesystem-write": data["destructiveChanges"] if request.get("destructive") else None,
    }.get(kind)
    if setting == "denied" and decision["decision"] != "deny":
        return dict(decision="deny", reason=f"policy-denies-{kind}")
    # Any value but the known ones (say, a file that skipped validation) asks the person.
    if setting not in {None, "autonomous", "denied"} and decision["decision"] == "allow":
        return dict(decision="require-approval", reason=f"policy-requires-approval-{kind}")
    return decision


BREAK_GLASS_SCOPES = {"git-local", "git-remote", "deploy", "external-write", "filesystem-write"}


def grant_break_glass(root, data):
    """Persist a temporary incident grant; the hook honors it only while it is valid."""
    from .common import slug, write_yaml

    require(
        data["scope"] and set(data["scope"]) <= BREAK_GLASS_SCOPES,
        f"Break-glass scope must be among: {', '.join(sorted(BREAK_GLASS_SCOPES))}.",
    )
    for scope in data["scope"]:
        check = validate_break_glass(data, scope, data["approvedAt"])
        require(check["valid"], "Invalid break-glass grant.", "APPROVAL_REQUIRED", check["reasons"])
    write_yaml(Path(root) / ".aifw/break-glass" / f"{slug(data['incidentId'])}.yaml", data, exclusive=True)
    return dict(data, status="granted")


def list_break_glass(root, at=None):
    grants = [read_yaml(f) for f in sorted((Path(root) / ".aifw/break-glass").glob("*.yaml"))]
    return [
        dict(g, active=any(validate_break_glass(g, s, at)["valid"] for s in g.get("scope", [])))
        for g in grants
    ]
