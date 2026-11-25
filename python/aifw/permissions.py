"""Explicit permissions and bounded delegation."""

from pathlib import Path

from .common import read_valid_yaml, require

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
            # "allowlist": writes to allowlisted services run on their own; others ask (ADR-0037).
            approveExternalWrites=external["writes"] != "allowlist",
            approveDestructiveWrites=True,
        ),
    )
    kind = request["kind"]
    production = request.get("environment") == "production"
    setting = {
        "git-local": data["localGit"],
        "git-remote": data["remoteMutation"],
        "deploy": data["productionDeployment" if production else "previewDeployment"],
        "external-write": None if external["writes"] == "allowlist" else external["writes"],
        "filesystem-write": data["destructiveChanges"] if request.get("destructive") else None,
    }.get(kind)
    if setting == "denied" and decision["decision"] != "deny":
        return dict(decision="deny", reason=f"policy-denies-{kind}")
    # Any value but the known ones (say, a file that skipped validation) asks the person.
    if setting not in {None, "autonomous", "denied"} and decision["decision"] == "allow":
        return dict(decision="require-approval", reason=f"policy-requires-approval-{kind}")
    return decision
