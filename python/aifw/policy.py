"""Authority resolution with protected invariants and pinned profiles."""

from copy import deepcopy
from pathlib import Path

from .common import (
    API,
    assets,
    digest,
    json_text,
    normalize,
    read_yaml,
    require,
    slug,
    sort_key,
    validate,
    write_json,
    write_yaml,
)
from .workspace import load_manifest


def parse_policy(value):
    validate(value, "policy-set.schema.json")
    ids = [rule["id"] for rule in value["rules"]]
    require(len(ids) == len(set(ids)), "Policy repeats a rule id.", "POLICY_CONFLICT")
    return value


def parse_profile(value):
    validate(value, "profile.schema.json")
    return dict(id=value["metadata"]["id"], version=value["metadata"]["version"], **value["spec"])


def resolve_framework(data):
    profiles = data["profiles"]
    selected = {p["id"] for p in profiles}
    provided = {capability for p in profiles for capability in p["provides"]}
    for profile in profiles:
        for conflict in profile["conflicts"]:
            require(
                conflict not in selected,
                f"Profile {profile['id']} conflicts with {conflict}",
                "PROFILE_CONFLICT",
            )
        for requirement in profile["requires"]:
            require(
                requirement in provided,
                f"Profile {profile['id']} requires missing capability {requirement}",
                "PROFILE_CONFLICT",
            )

    def priority(origin):
        if origin == "core":
            return 0
        if origin == "personal":
            return 1
        if origin.startswith("capability:"):
            return 2
        if origin.startswith("stack:"):
            return 3
        return 4

    effective = {}

    def add(rule, origin):
        current = effective.get(rule["id"])
        if current is None:
            effective[rule["id"]] = dict(deepcopy(rule), origin=origin)
            return
        same = digest({k: v for k, v in current.items() if k != "origin"}) == digest(rule)
        if current["origin"] == "core" and not current["overridable"]:
            require(same, f"Core invariant {rule['id']} cannot be overridden by {origin}", "POLICY_CONFLICT")
            return
        require(
            priority(current["origin"]) != priority(origin) or same,
            f"Rule {rule['id']} has conflicting definitions at the same authority level",
            "POLICY_CONFLICT",
        )
        if priority(origin) > priority(current["origin"]):
            effective[rule["id"]] = dict(deepcopy(rule), origin=origin)

    for rule in data["coreRules"]:
        add(rule, "core")
    for rule in data["personalRules"]:
        add(rule, "personal")
    for profile in sorted(profiles, key=lambda p: (p["kind"] != "capability", sort_key(p["id"]))):
        for rule in profile["rules"]:
            add(rule, f"{profile['kind']}:{profile['id']}")
    for rule in data["projectRules"]:
        add(rule, "project")
    entries = sorted(
        [dict(id=p["id"], version=p["version"], kind=p["kind"], digest=digest(p)) for p in profiles],
        key=lambda p: sort_key(p["id"]),
    )
    return {
        "rules": sorted(effective.values(), key=lambda r: sort_key(r["id"])),
        "profileLock": {"profiles": entries, "digest": digest(entries)},
    }


def resolve_workspace(root, write=False, personal=None):
    root = Path(root)
    manifest = load_manifest(root)

    def optional(file):
        return parse_policy(read_yaml(file))["rules"] if file and Path(file).exists() else []

    profiles = [
        parse_profile(read_yaml(assets() / "profiles" / slug(p) / "profile.yaml"))
        for p in manifest["spec"]["profiles"]
    ]
    resolution = resolve_framework(
        dict(
            coreRules=parse_policy(read_yaml(assets() / "policies/core.yaml"))["rules"],
            personalRules=optional(personal),
            profiles=profiles,
            projectRules=optional(root / ".aifw/project-rules.yaml"),
        )
    )
    version = manifest["spec"]["frameworkVersion"]
    effective = dict(
        apiVersion=API,
        kind="EffectivePolicy",
        projectId=manifest["metadata"]["id"],
        frameworkVersion=version,
        **resolution,
    )
    lock = dict(
        apiVersion=API,
        kind="FrameworkLock",
        frameworkVersion=version,
        profiles=resolution["profileLock"]["profiles"],
        resolutionDigest=resolution["profileLock"]["digest"],
        generatedBy=f"aifw/{version}",
    )
    effective_path, lock_path = root / ".aifw/effective-policy.json", root / ".aifw/framework.lock.yaml"
    current = (
        effective_path.is_file()
        and normalize(effective_path.read_text(encoding="utf-8")) == normalize(json_text(effective))
        and lock_path.is_file()
        and read_yaml(lock_path) == lock
    )
    if write and not current:
        write_json(effective_path, effective)
        write_yaml(lock_path, lock)
        current = True
    return dict(
        current=current,
        resolution=resolution,
        effectivePolicyPath=str(effective_path),
        lockPath=str(lock_path),
    )
