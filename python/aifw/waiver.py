"""Time-bounded human exceptions that cannot waive core invariants."""

from copy import deepcopy
from pathlib import Path
import subprocess

from .common import assets, human, now, read_yaml, require, slug, timestamp, validate, write_yaml


def create_waiver(data, *, non_waivable_rule_ids=()):
    human(data["approvedBy"])
    require(
        data["ruleId"] not in non_waivable_rule_ids, "Core invariant cannot be waived.", "POLICY_CONFLICT"
    )
    require(
        timestamp(data["expiresAt"]) > timestamp(data["approvedAt"]), "Waiver requires a valid time window."
    )
    require(data["scope"] and data["reason"].strip(), "Waiver requires scope and reason.")
    return dict(deepcopy(data), status="active")


def is_waiver_active(waiver, at=None):
    return timestamp(at or now()) < timestamp(waiver["expiresAt"])


# Gates that a waiver can never replace: the manifest check and human approval.
NON_WAIVABLE_GATES = {"manifest", "human-approval"}


def non_waivable(root):

    core = read_yaml(assets() / "policies/core.yaml")
    return NON_WAIVABLE_GATES | {r["id"] for r in core["rules"] if not r.get("overridable", True)}


def git_checkpoint(root):

    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True
        ).stdout.strip()
        return f"git:{sha}"
    except (OSError, subprocess.CalledProcessError):
        return "git:none"


def add_waiver(root, data):
    """Persist a time-bounded human exception for a gate or overridable rule."""

    waiver = create_waiver(
        dict(data, checkpoint=data.get("checkpoint") or git_checkpoint(root)),
        non_waivable_rule_ids=non_waivable(root),
    )
    waiver["id"] = f"waiver:{slug(waiver['ruleId'].replace('.', '-'))}-{waiver['approvedAt'][:10]}"
    validate(waiver, "waiver.schema.json")
    write_yaml(
        Path(root) / ".aifw/waivers" / f"{waiver['id'].removeprefix('waiver:')}.yaml", waiver, exclusive=True
    )
    return waiver


def load_waivers(root, at=None):

    from . import signing

    files = sorted((Path(root) / ".aifw/waivers").glob("*.yaml"))
    waivers = [(f, validate(read_yaml(f), "waiver.schema.json")) for f in files]
    return [dict(w, active=is_waiver_active(w, at) and signing.approved(root, f)) for f, w in waivers]


def apply_waivers(root, results, at=None):
    """Turn failed gate results into waived passes when an active waiver names the gate."""
    active = {w["ruleId"]: w for w in load_waivers(root, at) if w["active"]}
    blocked = non_waivable(root)
    applied = []
    for result in results:
        waiver = active.get(result["gateId"])
        if waiver and result["status"] != "pass" and result["gateId"] not in blocked:
            result = dict(
                result,
                status="pass",
                summary=f"Waived by {waiver['approvedBy']} until {waiver['expiresAt']}: {waiver['reason']}",
                evidence=[waiver["id"]],
                waived=True,
            )
        applied.append(result)
    return applied
