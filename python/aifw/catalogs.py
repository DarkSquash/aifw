"""Contextual architecture alternatives and engineering principles."""

from hashlib import sha256
from pathlib import Path

from .common import (
    API,
    assets,
    digest,
    human,
    project_path,
    read_json,
    read_yaml,
    require,
    slug,
    sort_key,
    timestamp,
    validate,
    write_json,
    write_yaml,
)
from .workspace import load_manifest


def unique(values, message):
    require(len(values) == len(set(values)), message, "POLICY_CONFLICT")


def load_decision_catalogs(root):
    files = list((assets() / "decision-catalogs").glob("*.yaml"))
    for profile in load_manifest(root)["spec"]["profiles"]:
        files.extend((assets() / "profiles" / slug(profile) / "decisions").glob("*.yaml"))
    catalogs = []
    for file in sorted(files):
        catalog = validate(read_yaml(file), "decision-catalog.schema.json")
        for collection in ("drivers", "options"):
            unique(
                [entry["id"] for entry in catalog["spec"][collection]],
                "Decision catalog repeats a driver or option id.",
            )
        catalogs.append(catalog)
    return catalogs


def recommend_decision(catalogs, category, signals, selected=()):
    selected_catalogs = sorted(
        [c for c in catalogs if c["metadata"]["category"] == category],
        key=lambda c: sort_key(c["metadata"]["id"]),
    )
    require(selected_catalogs, f"No decision catalog exists for category {category}.")
    options = [o for c in selected_catalogs for o in c["spec"]["options"]]
    unique([o["id"] for o in options], "Decision category repeats an option id.")
    signals, selected = sorted(set(signals)), sorted(set(selected))
    rankings = []
    for option in options:
        conflicts = sorted(set(option["conflicts"]) & set(selected))
        missing = [r for r in option["requires"] if r not in selected and r not in signals]
        score, reasons = 0, []
        for criterion in option["criteria"]:
            if criterion["signal"] not in signals:
                continue
            delta = criterion["weight"] * (1 if criterion["effect"] == "prefer" else -1)
            score += delta
            reasons.append(f"{delta:+d} {criterion['signal']}: {criterion['reason']}")
        if missing:
            reasons.append("missing requirements: " + ", ".join(missing))
        if conflicts:
            reasons.append("conflicts: " + ", ".join(conflicts))
        rankings.append(
            dict(
                optionId=option["id"],
                name=option["name"],
                score=score,
                eligible=not conflicts and not missing,
                reasons=reasons,
                conflicts=conflicts,
                tradeoffs=option["tradeoffs"],
                sources=option["sources"],
            )
        )
    rankings.sort(key=lambda r: (not r["eligible"], -r["score"], sort_key(r["optionId"])))
    drivers = {}
    for catalog in selected_catalogs:
        for driver in catalog["spec"]["drivers"]:
            require(
                driver["id"] not in drivers or digest(drivers[driver["id"]]) == digest(driver),
                "Conflicting decision drivers.",
                "POLICY_CONFLICT",
            )
            drivers[driver["id"]] = driver
    unanswered = sorted(
        [d for d in drivers.values() if not set(d["signals"]) & set(signals)], key=lambda d: sort_key(d["id"])
    )
    top = next((r for r in rankings if r["eligible"]), None)
    confidence = (
        "low"
        if not signals or top is None or top["score"] <= 0
        else "high"
        if not unanswered and top["score"] >= 4
        else "medium"
    )
    payload = dict(
        apiVersion=API,
        kind="DecisionCase",
        category=category,
        impact=max(c["metadata"]["impact"] for c in selected_catalogs),
        signals=signals,
        selectedOptionIds=selected,
        catalogs=[{k: c["metadata"][k] for k in ("id", "version", "scope")} for c in selected_catalogs],
        rankings=rankings,
        unansweredDrivers=unanswered,
        confidence=confidence,
        requiresHumanApproval=True,
        recordRequired="ADR",
    )
    return dict(payload, digest=digest(payload))


def recommend_workspace(root, category, signals, selected=(), write=False):
    result = recommend_decision(load_decision_catalogs(root), category, signals, selected)
    if write:
        write_json(Path(root) / ".aifw/decision-cases" / f"{slug(category)}.json", result)
    return result


def approve_decision(root, category, option, by, at, adr):
    human(by)
    approved_at = timestamp(at)
    decision = read_json(Path(root) / ".aifw/decision-cases" / f"{slug(category)}.json")
    validate(decision, "decision-case.schema.json")
    require(
        decision["digest"] == digest({k: v for k, v in decision.items() if k != "digest"}),
        "The persisted decision case digest is invalid.",
        "POLICY_CONFLICT",
    )
    require(
        any(r["optionId"] == option and r["eligible"] for r in decision["rankings"]),
        "Decision option is not eligible.",
        "POLICY_CONFLICT",
    )
    file = project_path(root, adr, file=True)
    record = dict(
        apiVersion=API,
        kind="DecisionRecord",
        category=category,
        optionId=option,
        status="accepted",
        recommendationDigest=decision["digest"],
        approvedBy=by,
        approvedAt=approved_at.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        adr=dict(
            path=file.relative_to(Path(root).resolve()).as_posix(),
            digest=sha256(file.read_bytes()).hexdigest(),
        ),
    )
    write_yaml(Path(root) / ".aifw/decisions" / f"{slug(category)}.yaml", record)
    return record


def load_principles():
    catalogs = [
        validate(read_yaml(file), "principle-catalog.schema.json")
        for file in sorted((assets() / "principle-catalogs").glob("*.yaml"))
    ]
    require(catalogs, "No engineering principle catalog is available.")
    unique(
        [p["id"] for c in catalogs for p in c["spec"]["principles"]],
        "Engineering principle ids must be globally unique.",
    )
    return catalogs
