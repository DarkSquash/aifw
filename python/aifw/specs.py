"""Executable capability deltas, traceability and recoverable archive commits."""

from collections import Counter
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import shutil
import subprocess
from uuid import uuid4

from . import signing
from .common import (
    API,
    AifwError,
    assets,
    digest,
    file_state,
    human,
    project_path,
    read_json,
    read_yaml,
    require,
    slug,
    timestamp,
    validate,
    write_yaml,
)


def change_dir(root, change_id):
    return Path(root) / ".aifw/changes/active" / slug(change_id)


def load_change(root, change_id):
    file = change_dir(root, change_id) / "change.yaml"
    require(file.is_file(), f"Active spec change not found: {change_id}", "NOT_READY")
    value = read_yaml(file)
    if isinstance(value, dict) and isinstance(value.get("approval"), dict):
        human(value["approval"].get("approvedBy"))
    return validate(value, "spec-change.schema.json")


def create_change(root, data):
    change_id = slug(data["id"])
    require(
        data["title"].strip() and data["summary"].strip(),
        "A spec change requires a non-empty title and summary.",
    )
    timestamp(data["createdAt"])
    change = dict(
        apiVersion=API,
        kind="SpecChange",
        metadata=dict(
            id=change_id, title=data["title"].strip(), level=data["level"], createdAt=data["createdAt"]
        ),
        summary=data["summary"].strip(),
        status="draft",
    )
    validate(change, "spec-change.schema.json")
    base = change_dir(root, change_id)
    require(not base.exists(), f"Spec change already exists: {change_id}", "POLICY_CONFLICT")
    files = {
        "change.yaml": change,
        "design.md": f"# Design — {change['metadata']['title']}\n\n## Context\n\n## Approach\n\n## Decisions\n\n## Risks and rollback\n",
        "proposal.md": f"# Proposal — {change['metadata']['title']}\n\n## Intent\n\n{change['summary']}\n\n## Scope\n\n## Non-goals\n\n## Acceptance\n",
        "evidence/README.md": "# Evidence\n\nStore reproducible gate and verification evidence for this change here.\n",
        "specs/README.md": "# Capability deltas\n\nAdd one `<capability>.delta.yaml` file per affected capability.\n",
        "tasks.yaml": dict(apiVersion=API, kind="ChangeTasks", changeId=change_id, tasks=[]),
        "traceability.yaml": dict(
            apiVersion=API, kind="ChangeTraceability", changeId=change_id, artifacts=[], links=[]
        ),
    }
    for name, content in files.items():
        target = base / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, dict):
            write_yaml(target, content, exclusive=True)
        else:
            with target.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
    return dict(
        change=change, createdFiles=sorted((base / name).relative_to(root).as_posix() for name in files)
    )


def list_changes(root):
    entries = []
    for location in ("active", "archive"):
        for file in (Path(root) / ".aifw/changes" / location).glob("*/change.yaml"):
            change = validate(read_yaml(file), "spec-change.schema.json")
            entries.append(
                dict(
                    id=change["metadata"]["id"],
                    title=change["metadata"]["title"],
                    level=change["metadata"]["level"],
                    status=change["status"],
                    location=location,
                    relativePath=file.relative_to(root).as_posix(),
                )
            )
    return sorted(entries, key=lambda e: (e["location"], e["id"]))


def load_artifacts(root, change_id):
    base = change_dir(root, change_id)
    change = load_change(root, change_id)
    deltas = [
        validate(read_yaml(file), "capability-delta.schema.json")
        for file in sorted((base / "specs").glob("*.delta.yaml"))
        if not file.is_symlink()
    ]
    tasks = validate(read_yaml(base / "tasks.yaml"), "change-tasks.schema.json")
    trace = read_yaml(base / "traceability.yaml")
    # Keep missing proof paths as analyzer findings, matching the public CLI's exit 2.
    require(
        isinstance(trace, dict)
        and trace.get("apiVersion") == API
        and trace.get("kind") == "ChangeTraceability"
        and isinstance(trace.get("artifacts"), list)
        and isinstance(trace.get("links"), list),
        "Invalid ChangeTraceability contract.",
    )
    for artifact in trace["artifacts"]:
        require(
            isinstance(artifact, dict)
            and isinstance(artifact.get("id"), str)
            and artifact.get("type") in {"test", "gate", "evidence", "adr", "design"}
            and artifact.get("status") in {"planned", "passed", "failed", "waived"}
            and ("path" not in artifact or isinstance(artifact["path"], str)),
            "Invalid trace artifact.",
        )
    for link in trace["links"]:
        require(
            isinstance(link, dict)
            and isinstance(link.get("from"), str)
            and isinstance(link.get("to"), str)
            and link.get("relation") in {"verifiedBy", "provedBy", "designedBy", "governedBy", "checkedBy"},
            "Invalid trace link.",
        )
    require(
        all(d.get("changeId") == change_id for d in [*deltas, tasks, trace]),
        "Change artifact ids must match the active change.",
    )
    return change, deltas, tasks, trace


def current_spec(root, capability):
    file = Path(root) / ".aifw/specs/current" / f"{slug(capability)}.yaml"
    if not file.exists():
        return None
    value = validate(read_yaml(file), "capability-spec.schema.json")
    require(
        value["title"].strip() and value["purpose"].strip(),
        "Current capability title and purpose must be non-empty.",
    )
    return value


def finding(code, ids, location, message, severity="error"):
    return dict(code=code, severity=severity, message=message, relatedIds=ids, locations=[location])


def ordered_findings(findings):
    return sorted(findings, key=lambda f: (f["code"], ",".join(f["relatedIds"])))


def validate_change(root, change_id):
    change, deltas, _, _ = load_artifacts(root, change_id)
    findings, location = [], f".aifw/changes/active/{change_id}/specs"
    if not deltas and change["metadata"]["level"] in {"L2", "L3"}:
        findings.append(
            finding(
                "CHANGE_REQUIRES_DELTA", [change_id], location, "L2/L3 changes require a capability delta."
            )
        )
    requirements, scenarios, capabilities = [], [], []
    for delta in deltas:
        capabilities.append(delta["capability"])
        for requirement in (
            delta["operations"]["added"] + delta["operations"]["modified"] + delta["operations"]["removed"]
        ):
            requirements.append(requirement["id"])
            scenarios.extend(s["id"] for s in requirement.get("scenarios", []))
        current = current_spec(root, delta["capability"])
        if current is None and not delta.get("purpose", "").strip():
            findings.append(
                finding(
                    "NEW_CAPABILITY_REQUIRES_PURPOSE",
                    [delta["capability"]],
                    location,
                    "New capability requires an explicit purpose.",
                )
            )
        existing = {r["id"] for r in (current or {}).get("requirements", [])}
        for operation, code in (
            ("added", "DELTA_ADDS_EXISTING_REQUIREMENT"),
            ("modified", "DELTA_MODIFIES_UNKNOWN_REQUIREMENT"),
            ("removed", "DELTA_REMOVES_UNKNOWN_REQUIREMENT"),
        ):
            for requirement in delta["operations"][operation]:
                if (requirement["id"] in existing) == (operation == "added"):
                    findings.append(
                        finding(
                            code,
                            [delta["capability"], requirement["id"]],
                            location,
                            f"Invalid {operation} precondition for {requirement['id']}.",
                        )
                    )
    for values, code in (
        (capabilities, "DUPLICATE_CAPABILITY_DELTA"),
        (requirements, "DUPLICATE_REQUIREMENT_ID"),
        (scenarios, "DUPLICATE_SCENARIO_ID"),
    ):
        for value, count in Counter(values).items():
            if count > 1:
                findings.append(finding(code, [value], location, f"Duplicate identifier: {value}"))
    return dict(
        change=change,
        **{"pass": not any(f["severity"] == "error" for f in findings)},
        findings=ordered_findings(findings),
        capabilities=sorted(capabilities),
    )


def analyze_change(root, change_id):
    change, deltas, task_doc, trace = load_artifacts(root, change_id)
    tasks = task_doc["tasks"]
    requirements = [r for d in deltas for r in d["operations"]["added"] + d["operations"]["modified"]]
    requirements += [dict(id=r["id"], scenarios=[]) for d in deltas for r in d["operations"]["removed"]]
    scenarios = [s for r in requirements for s in r["scenarios"]]
    req_ids, scn_ids = {r["id"] for r in requirements}, {s["id"] for s in scenarios}
    linked = {r for t in tasks for r in t["requirementIds"] if r in req_ids}
    known = req_ids | scn_ids | {t["id"] for t in tasks} | {a["id"] for a in trace["artifacts"]}
    findings, valid_artifacts = [], set()
    location = f".aifw/changes/active/{change_id}/traceability.yaml"
    for link in trace["links"]:
        missing = [node for node in (link["from"], link["to"]) if node not in known]
        if missing:
            findings.append(
                finding("DANGLING_TRACE_LINK", missing, location, "Trace link references an unknown node.")
            )
        target = next((a for a in trace["artifacts"] if a["id"] == link["to"]), None)
        if (
            link["relation"] == "checkedBy"
            and target
            and target["type"] == "gate"
            and target["status"] != "passed"
        ):
            findings.append(
                finding(
                    "TRACE_GATE_NOT_PASSED",
                    [link["from"], target["id"]],
                    location,
                    "Required checkedBy gate is not passed.",
                )
            )
    for task in tasks:
        unknown = [r for r in task["requirementIds"] if r not in req_ids]
        if unknown:
            findings.append(
                finding(
                    "TASK_UNKNOWN_REQUIREMENT",
                    [task["id"], *unknown],
                    f".aifw/changes/active/{change_id}/tasks.yaml",
                    "Task references unknown requirements.",
                )
            )
    for artifact in trace["artifacts"]:
        if artifact["status"] != "passed":
            continue
        state = file_state(root, artifact.get("path"))
        if state == "valid":
            valid_artifacts.add(artifact["id"])
        else:
            code = "TRACE_ARTIFACT_OUTSIDE_PROJECT" if state == "outside" else "TRACE_ARTIFACT_MISSING"
            findings.append(
                finding(
                    code,
                    [artifact["id"]],
                    artifact.get("path") or location,
                    "Passed artifact requires a file inside the project.",
                )
            )
    tests = {a["id"] for a in trace["artifacts"] if a["type"] == "test"}
    verified = {
        link["from"]
        for link in trace["links"]
        if link["relation"] == "verifiedBy"
        and link["from"] in scn_ids
        and link["to"] in valid_artifacts & tests
    }
    severity = "warning" if change["metadata"]["level"] in {"L0", "L1"} else "error"
    for requirement in requirements:
        if requirement["id"] not in linked:
            findings.append(
                finding(
                    "ORPHAN_REQUIREMENT",
                    [requirement["id"]],
                    location,
                    "Requirement is not linked to a task.",
                    severity,
                )
            )
    for scenario in scenarios:
        if scenario["id"] not in verified:
            findings.append(
                finding(
                    "SCENARIO_WITHOUT_VERIFICATION",
                    [scenario["id"]],
                    location,
                    "Scenario has no passed test verification.",
                    severity,
                )
            )
    nodes = [dict(id=r["id"], type="requirement") for r in requirements] + [
        dict(id=s["id"], type="scenario") for s in scenarios
    ]
    nodes += [dict(id=t["id"], type="task") for t in tasks]
    nodes += [dict(id=f"FILE:{p}", type="code", path=p) for t in tasks for p in t["paths"]]
    nodes += [{k: a[k] for k in ("id", "type", "path") if k in a} for a in trace["artifacts"]]
    links = [
        dict(from_=r["id"], relation="hasScenario", to=s["id"]) for r in requirements for s in r["scenarios"]
    ]
    links += [dict(from_=r, relation="implementedBy", to=t["id"]) for t in tasks for r in t["requirementIds"]]
    links += [dict(from_=t["id"], relation="changes", to=f"FILE:{p}") for t in tasks for p in t["paths"]]
    links = [
        {"from": link["from_"], "relation": link["relation"], "to": link["to"]} for link in links
    ] + trace["links"]
    return dict(
        change=change,
        **{"pass": not any(f["severity"] == "error" for f in findings)},
        findings=ordered_findings(findings),
        coverage=dict(
            requirements=dict(total=len(requirements), linkedToTask=len(linked)),
            scenarios=dict(total=len(scenarios), verified=len(verified)),
            tasks=dict(total=len(tasks), completed=sum(t["status"] == "done" for t in tasks)),
        ),
        graph=dict(
            nodes=sorted(nodes, key=lambda n: n["id"]),
            links=sorted(links, key=lambda link: (link["from"], link["relation"], link["to"])),
        ),
    )


def preview_sync(root, change_id):
    validation = validate_change(root, change_id)
    plan = dict(
        changeId=change_id,
        **{"pass": validation["pass"]},
        findings=validation["findings"],
        changes=[],
        outputs=[],
    )
    if not plan["pass"]:
        return plan
    _, deltas, _, _ = load_artifacts(root, change_id)
    for delta in deltas:
        current = current_spec(root, delta["capability"])
        requirements = {r["id"]: deepcopy(r) for r in (current or {}).get("requirements", [])}
        for r in delta["operations"]["added"] + delta["operations"]["modified"]:
            requirements[r["id"]] = deepcopy(r)
        for r in delta["operations"]["removed"]:
            requirements.pop(r["id"])
        for r in requirements.values():
            r["scenarios"].sort(key=lambda s: s["id"])
        spec = dict(
            apiVersion=API,
            kind="CapabilitySpec",
            capability=delta["capability"],
            title=delta["title"].strip(),
            purpose=(current["purpose"] if current else delta.get("purpose", "")).strip(),
            requirements=sorted(requirements.values(), key=lambda r: r["id"]),
        )
        validate(spec, "capability-spec.schema.json")
        require(spec["title"] and spec["purpose"], "Output capability title and purpose must be non-empty.")
        output = f".aifw/specs/current/{delta['capability']}.yaml"
        plan["outputs"].append(dict(relativePath=output, spec=spec))
        plan["changes"].append(
            dict(
                capability=delta["capability"],
                action="update" if current else "create",
                outputPath=output,
                **{
                    op: sorted(r["id"] for r in delta["operations"][op])
                    for op in ("added", "modified", "removed")
                },
            )
        )
    plan["outputs"].sort(key=lambda o: o["relativePath"])
    plan["changes"].sort(key=lambda c: c["capability"])
    return plan


def assert_approval(root, change):
    if change["metadata"]["level"] != "L3":
        return
    approval = change.get("approval", {})
    try:
        human(approval.get("approvedBy"))
        timestamp(approval.get("approvedAt"))
        require(file_state(root, approval.get("record")) == "valid", "Missing approval record.")
        change_file = change_dir(root, change["metadata"]["id"]) / "change.yaml"
        require(signing.approved(root, change_file), "The approval is not in a signed commit.")
    except AifwError as error:
        raise AifwError(
            "APPROVAL_REQUIRED",
            "L3 requires persisted human approval and an existing in-project approval record.",
        ) from error


def approve_change(root, change_id, approval):
    change = load_change(root, change_id)
    human(approval["approvedBy"])
    timestamp(approval["approvedAt"])
    require(
        file_state(root, approval["record"]) == "valid",
        "Approval record must be an existing file inside the project.",
        "APPROVAL_REQUIRED",
    )
    record = (Path(root) / approval["record"]).resolve().relative_to(Path(root).resolve()).as_posix()
    change["approval"] = dict(approval, record=record)
    write_yaml(change_dir(root, change_id) / "change.yaml", change)
    return change


def update_status(root, change_id, status):
    require(status in {"active", "ready"}, "Invalid change status.")
    change = load_change(root, change_id)
    if status == "ready":
        validation, analysis = validate_change(root, change_id), analyze_change(root, change_id)
        blockers = [
            f["code"] for f in validation["findings"] + analysis["findings"] if f["severity"] == "error"
        ]
        require(
            not blockers,
            "Change cannot become ready while validation or traceability has blockers.",
            "NOT_READY",
            blockers,
        )
        assert_approval(root, change)
    change["status"] = status
    write_yaml(change_dir(root, change_id) / "change.yaml", change)
    return change


def remove_tree(directory):
    shutil.rmtree(directory)


def archive_change(root, change_id, archived_at):
    root = Path(root)
    change = load_change(root, change_id)
    require(change["status"] == "ready", "Spec change must be ready before archive.", "NOT_READY")
    timestamp(archived_at)
    assert_approval(root, change)
    validation, analysis, plan = (
        validate_change(root, change_id),
        analyze_change(root, change_id),
        preview_sync(root, change_id),
    )
    require(
        validation["pass"] and analysis["pass"] and plan["pass"],
        "Archive has validation or traceability blockers.",
        "NOT_READY",
    )
    _, _, tasks, _ = load_artifacts(root, change_id)
    require(
        all(t["status"] == "done" for t in tasks["tasks"]), "Change still has incomplete tasks.", "NOT_READY"
    )
    assert_current_validation(root, change_id)
    archived_relative = f".aifw/changes/archive/{archived_at[:10]}-{change_id}"
    active, archived, current = (
        change_dir(root, change_id),
        root / archived_relative,
        root / ".aifw/specs/current",
    )
    require(not archived.exists(), "Archive target already exists.", "POLICY_CONFLICT")
    transaction = root / ".aifw/transactions" / f"{change_id}-{uuid4()}"
    next_current, previous_current = transaction / "next-current", transaction / "previous-current"
    next_archive, previous_active = transaction / "next-archive", transaction / "previous-active"
    transaction.mkdir(parents=True)
    existed, swapped, moved = current.exists(), False, False
    if existed:
        shutil.copytree(current, next_current, symlinks=True)
    else:
        next_current.mkdir()
    for output in plan["outputs"]:
        write_yaml(next_current / f"{output['spec']['capability']}.yaml", output["spec"])
    shutil.copytree(active, next_archive, symlinks=True)
    write_yaml(next_archive / "change.yaml", dict(change, status="archived", archivedAt=archived_at))
    trace_file = next_archive / "traceability.yaml"
    trace_file.write_text(
        trace_file.read_text(encoding="utf-8").replace(
            f".aifw/changes/active/{change_id}/", archived_relative + "/"
        ),
        encoding="utf-8",
    )
    try:
        current.parent.mkdir(parents=True, exist_ok=True)
        archived.parent.mkdir(parents=True, exist_ok=True)
        if existed:
            current.rename(previous_current)
        next_current.rename(current)
        swapped = True
        active.rename(previous_active)
        moved = True
        next_archive.rename(archived)
    except OSError as error:
        try:
            if moved and previous_active.exists() and not active.exists():
                previous_active.rename(active)
            if swapped and current.exists():
                remove_tree(current)
            if existed and previous_current.exists():
                previous_current.rename(current)
            remove_tree(transaction)
        except OSError as rollback_error:
            raise AifwError(
                "COMMAND_FAILED",
                "Archive failed and rollback also failed.",
                [str(error), str(rollback_error), str(transaction)],
            ) from error
        raise AifwError(
            "COMMAND_FAILED", "Archive transaction failed and was rolled back.", [str(error)]
        ) from error
    result = dict(
        changeId=change_id,
        archivePath=archived_relative,
        currentSpecs=sorted(o["relativePath"] for o in plan["outputs"]),
    )
    try:
        remove_tree(transaction)
    except OSError as error:
        result["cleanupPending"] = dict(path=transaction.relative_to(root).as_posix(), reason=str(error))
    return result


VALIDATION_REPORT = "evidence/validation.json"
# artifact -> (file in the change folder, heading whose section must have content)
LEVEL_ARTIFACTS = {
    "L2": {
        "technical-plan": ("design.md", "approach"),
        "rollback": ("design.md", "rollback"),
        "independent-review": ("independent-review.md", None),
    }
}
LEVEL_ARTIFACTS["L3"] = {
    **LEVEL_ARTIFACTS["L2"],
    "rfc": ("proposal.md", "acceptance"),
    "threat-model": ("threat-model.md", None),
    "migration": ("migration.md", None),
}


def has_content(text, section=None):
    lines = text.splitlines()
    if section:
        start = next(
            (i for i, line in enumerate(lines) if line.startswith("#") and section in line.lower()), None
        )
        if start is None:
            return False
        end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("#")), len(lines))
        lines = lines[start + 1 : end]
    return any(line.strip() and not line.startswith("#") for line in lines)


def missing_artifacts(root, change_id):
    """Artifacts required by the change level that are absent or still an empty scaffold."""
    change, _, _, trace = load_artifacts(root, change_id)
    base, missing = change_dir(root, change_id), []
    for artifact, (name, section) in LEVEL_ARTIFACTS.get(change["metadata"]["level"], {}).items():
        file = base / name
        if not (file.is_file() and has_content(file.read_text(encoding="utf-8"), section)):
            where = f"{name} ({section})" if section else name
            missing.append(dict(artifact=artifact, path=f"{base.relative_to(root).as_posix()}/{where}"))
    if change["metadata"]["level"] == "L3" and not any(
        a["type"] == "adr" and a.get("path") and file_state(root, a["path"]) == "valid"
        for a in trace["artifacts"]
    ):
        missing.append(dict(artifact="adr", path="traceability.yaml (artifact of type adr with a path)"))
    return missing


def project_files(root):
    """Files that define the project state: git's view when available, else the inventory."""
    root = Path(root)
    try:
        listed = subprocess.run(
            ["git", "ls-files", "-co", "--exclude-standard"],
            cwd=root,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        from .discovery import inventory

        # shortcut: without git, ignored build output outside these folders still counts; use git.
        listed = [
            p for p in inventory(root) if not p.startswith(("dist/", "coverage/")) and ".egg-info/" not in p
        ]
    return sorted(p for p in listed if not p.startswith(".aifw/") and (root / p).is_file())


def validation_inputs(root, change_id):
    """Digests that make a validation report stale when the change or the code changes."""
    root, base = Path(root), change_dir(root, change_id)
    change_files = []
    for file in sorted(f for f in base.rglob("*") if f.is_file()):
        relative = file.relative_to(base).as_posix()
        if relative == VALIDATION_REPORT:
            continue
        content = file.read_bytes()
        if relative == "change.yaml":
            # Moving to "ready" after validating must not invalidate the report.
            content = digest({k: v for k, v in read_yaml(file).items() if k != "status"}).encode()
        change_files.append([relative, sha256(content).hexdigest()])
    workspace = [[p, sha256((root / p).read_bytes()).hexdigest()] for p in project_files(root)]
    return dict(change=digest(change_files), workspace=digest(workspace))


def assert_current_validation(root, change_id):
    file = change_dir(root, change_id) / VALIDATION_REPORT
    require(
        file.is_file(),
        f"Run `aifw validate --change {change_id} --write` before archive.",
        "NOT_READY",
    )
    report = read_json(file)
    # Audit warnings are non-blocking by definition; hard and human blockers are not.
    require(report.get("status") in {"pass", "warning"}, "The recorded validation has blockers.", "NOT_READY")
    require(
        report.get("inputs") == validation_inputs(root, change_id),
        "The change or the project changed after validation; validate again.",
        "NOT_READY",
    )


def list_templates():
    return sorted(
        f.name
        for f in (assets() / "templates").iterdir()
        if f.is_file() and f.name != "project-scaffold.json"
    )


def copy_template(root, name, change_id=None, output=None):
    """Copy a template into a change folder or a project path, never overwriting."""
    require(name in list_templates(), f"Unknown template: {name}. See `aifw template list`.")
    require(bool(change_id) != bool(output), "Use either --change or --output.")
    target = change_dir(root, change_id) / name if change_id else project_path(root, output)
    if change_id:
        load_change(root, change_id)
    require(not target.exists(), f"Target already exists: {target.name}", "POLICY_CONFLICT")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(assets() / "templates" / name, target)
    return dict(status="created", path=target.resolve().relative_to(Path(root).resolve()).as_posix())
