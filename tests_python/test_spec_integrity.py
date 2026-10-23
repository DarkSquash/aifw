from copy import deepcopy
from pathlib import Path

import pytest

from aifw import specs
from aifw.common import API, AifwError, read_yaml, validate, write_json, write_yaml

AT = "2026-09-06T02:00:00.000Z"
ID = "integrity"
ARCHIVE = ".aifw/changes/archive/2026-09-06-integrity"


@pytest.fixture
def fixture(tmp_path):
    specs.create_change(
        tmp_path, dict(id=ID, title="Integrity", summary="Archive regression", level="L2", createdAt=AT)
    )
    base = specs.change_dir(tmp_path, ID)
    delta = dict(
        apiVersion=API,
        kind="CapabilityDelta",
        changeId=ID,
        capability="search",
        title="Search",
        purpose="Find records",
        operations=dict(
            added=[
                dict(
                    id="REQ-ONE",
                    strength="MUST",
                    statement="Find records",
                    scenarios=[dict(id="SCN-ONE", given=["input"], when=["search"], then=["records"])],
                )
            ],
            modified=[],
            removed=[],
        ),
    )
    trace = dict(
        apiVersion=API,
        kind="ChangeTraceability",
        changeId=ID,
        artifacts=[dict(id="TEST-ONE", type="test", status="passed", path="tests/search.py")],
        links=[{"from": "SCN-ONE", "relation": "verifiedBy", "to": "TEST-ONE"}],
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/search.py").write_text("# isolated test evidence\n")
    write_yaml(base / "specs/search.delta.yaml", delta)
    write_yaml(base / "traceability.yaml", trace)
    write_yaml(
        base / "tasks.yaml",
        dict(
            apiVersion=API,
            kind="ChangeTasks",
            changeId=ID,
            tasks=[
                dict(
                    id="TASK-ONE",
                    title="Implement",
                    status="done",
                    dependsOn=[],
                    requirementIds=["REQ-ONE"],
                    paths=[],
                )
            ],
        ),
    )
    current = tmp_path / ".aifw/specs/current"
    current.mkdir(parents=True)
    (current / "sentinel.txt").write_text("original accepted state")
    return tmp_path, base, delta, trace


def validated(root):
    """Record a passing validation for the current state, as `validate --change --write` would."""
    report = dict(status="pass", inputs=specs.validation_inputs(root, ID))
    write_json(specs.change_dir(root, ID) / specs.VALIDATION_REPORT, report)


def unchanged(root, base):
    assert (root / ".aifw/specs/current/sentinel.txt").read_text() == "original accepted state"
    assert (base / "change.yaml").is_file()
    assert not (root / ARCHIVE).exists()
    assert not (root / ".aifw/specs/current/search.yaml").exists()


def test_partial_cleanup_preserves_committed_state(fixture, monkeypatch):
    root, base, _, _ = fixture
    specs.update_status(root, ID, "ready")
    original = specs.remove_tree

    def fail_cleanup(path):
        if path.parent.name == "transactions":
            original(path / "previous-current")
            original(path / "previous-active")
            raise OSError("Injected EACCES during cleanup")
        original(path)

    monkeypatch.setattr(specs, "remove_tree", fail_cleanup)
    validated(root)
    result = specs.archive_change(root, ID, AT)
    assert "cleanupPending" in result
    assert (root / ARCHIVE / "change.yaml").is_file()
    assert not base.exists()
    assert read_yaml(root / ".aifw/specs/current/search.yaml")["requirements"][0]["id"] == "REQ-ONE"


@pytest.mark.parametrize(
    "destination", ["previous-current", "current", "previous-active", "2026-09-06-integrity"]
)
def test_rename_failure_restores_both_states(fixture, monkeypatch, destination):
    root, base, _, _ = fixture
    specs.update_status(root, ID, "ready")
    original, injected = Path.rename, False

    def fail_once(source, target):
        nonlocal injected
        if not injected and target.name == destination:
            injected = True
            raise OSError("Injected rename failure")
        return original(source, target)

    monkeypatch.setattr(Path, "rename", fail_once)
    validated(root)
    with pytest.raises(AifwError, match="rolled back"):
        specs.archive_change(root, ID, AT)
    unchanged(root, base)


@pytest.mark.parametrize(
    "invalidation",
    ["reclassified", "removed-approval", "removed-record", "agent-identity", "directory-record"],
)
def test_archive_rechecks_l3_approval(fixture, invalidation):
    root, base, _, _ = fixture
    record = read_yaml(base / "change.yaml")
    if invalidation != "reclassified":
        record["metadata"]["level"] = "L3"
        write_yaml(base / "change.yaml", record)
        (root / "approval.md").write_text("Isolated fixture authorization")
        specs.approve_change(root, ID, dict(approvedBy="human:test", approvedAt=AT, record="approval.md"))
    specs.update_status(root, ID, "ready")
    record = read_yaml(base / "change.yaml")
    if invalidation == "reclassified":
        record["metadata"]["level"] = "L3"
    if invalidation == "removed-approval":
        del record["approval"]
    if invalidation == "removed-record":
        (root / "approval.md").unlink()
    if invalidation == "agent-identity":
        record["approval"]["approvedBy"] = "agent:test"
    if invalidation == "directory-record":
        record["approval"]["record"] = "tests"
    write_yaml(base / "change.yaml", record)
    with pytest.raises(AifwError) as error:
        specs.archive_change(root, ID, AT)
    assert error.value.code == "APPROVAL_REQUIRED"
    unchanged(root, base)


def test_duplicate_capability_is_blocked(fixture):
    root, base, delta, _ = fixture
    second = deepcopy(delta)
    second["operations"]["added"][0]["id"] = "REQ-TWO"
    second["operations"]["added"][0]["scenarios"][0]["id"] = "SCN-TWO"
    write_yaml(base / "specs/second.delta.yaml", second)
    result = specs.validate_change(root, ID)
    assert not result["pass"]
    assert "DUPLICATE_CAPABILITY_DELTA" in [f["code"] for f in result["findings"]]
    unchanged(root, base)


@pytest.mark.parametrize("path", [None, "tests", "missing.txt", "../outside.txt"])
def test_evidence_requires_existing_project_file(fixture, path):
    root, base, _, trace = fixture
    if path is None:
        del trace["artifacts"][0]["path"]
    else:
        trace["artifacts"][0]["path"] = path
    write_yaml(base / "traceability.yaml", trace)
    analysis = specs.analyze_change(root, ID)
    assert not analysis["pass"] and analysis["coverage"]["scenarios"]["verified"] == 0
    with pytest.raises(AifwError):
        specs.update_status(root, ID, "ready")


@pytest.mark.parametrize("status", ["failed", "planned", "waived"])
def test_checked_gate_blocks_even_after_ready(fixture, status):
    root, base, _, trace = fixture
    specs.update_status(root, ID, "ready")
    trace["artifacts"].append(dict(id="GATE-ONE", type="gate", status=status))
    trace["links"].append({"from": "REQ-ONE", "relation": "checkedBy", "to": "GATE-ONE"})
    write_yaml(base / "traceability.yaml", trace)
    assert not specs.analyze_change(root, ID)["pass"]
    with pytest.raises(AifwError):
        specs.archive_change(root, ID, AT)
    unchanged(root, base)


def test_unlinked_audit_remains_nonblocking(fixture):
    root, base, _, trace = fixture
    trace["artifacts"].append(dict(id="AUDIT", type="gate", status="failed"))
    write_yaml(base / "traceability.yaml", trace)
    assert specs.analyze_change(root, ID)["pass"]
    specs.update_status(root, ID, "ready")
    validated(root)
    assert "cleanupPending" not in specs.archive_change(root, ID, AT)


@pytest.mark.parametrize("title", ["", "   "])
def test_blank_title_rejected(fixture, title):
    root, base, delta, _ = fixture
    delta["title"] = title
    write_yaml(base / "specs/search.delta.yaml", delta)
    with pytest.raises(AifwError):
        specs.validate_change(root, ID)
    unchanged(root, base)


def test_approved_l3_archives(fixture):
    root, base, delta, trace = fixture
    validate(delta, "capability-delta.schema.json")
    validate(trace, "traceability.schema.json")
    record = read_yaml(base / "change.yaml")
    record["metadata"]["level"] = "L3"
    write_yaml(base / "change.yaml", record)
    (root / "approval.md").write_text("Fixture approval")
    specs.approve_change(root, ID, dict(approvedBy="human:test", approvedAt=AT, record="approval.md"))
    specs.update_status(root, ID, "ready")
    validated(root)
    result = specs.archive_change(root, ID, AT)
    assert read_yaml(root / result["archivePath"] / "change.yaml")["status"] == "archived"


def test_directory_link_cannot_supply_outside_evidence(fixture):
    import os
    import subprocess

    root, base, _, trace = fixture
    outside = root.parent / (root.name + "-outside")
    outside.mkdir()
    (outside / "proof.md").write_text("outside")
    link = root / "linked"
    if os.name == "nt":
        completed = subprocess.run(
            ["cmd.exe", "/c", "mklink", "/J", str(link), str(outside)], capture_output=True
        )
        assert completed.returncode == 0
    else:
        link.symlink_to(outside, target_is_directory=True)
    trace["artifacts"][0]["path"] = "linked/proof.md"
    write_yaml(base / "traceability.yaml", trace)
    assert "TRACE_ARTIFACT_OUTSIDE_PROJECT" in [f["code"] for f in specs.analyze_change(root, ID)["findings"]]
    with pytest.raises(AifwError):
        specs.approve_change(root, ID, dict(approvedBy="human:test", approvedAt=AT, record="linked/proof.md"))


def test_merge_updates_removes_and_preserves_unaffected_requirements(fixture):
    root, base, delta, _ = fixture
    template = delta["operations"]["added"][0]
    old = []
    for suffix in ("UPDATE", "REMOVE", "KEEP"):
        requirement = deepcopy(template)
        requirement["id"] = "REQ-" + suffix
        requirement["scenarios"][0]["id"] = "SCN-" + suffix
        old.append(requirement)
    current_path = root / ".aifw/specs/current/search.yaml"
    write_yaml(
        current_path,
        dict(
            apiVersion=API,
            kind="CapabilitySpec",
            capability="search",
            title="Search",
            purpose="Existing purpose",
            requirements=old,
        ),
    )
    before = current_path.read_bytes()
    updated = deepcopy(old[0])
    updated["statement"] = "Updated behavior"
    delta["operations"]["modified"] = [updated]
    delta["operations"]["removed"] = [dict(id="REQ-REMOVE", reason="Replaced")]
    write_yaml(base / "specs/search.delta.yaml", delta)
    plan = specs.preview_sync(root, ID)
    assert plan["pass"]
    output = plan["outputs"][0]["spec"]
    assert output["purpose"] == "Existing purpose"
    assert [r["id"] for r in output["requirements"]] == ["REQ-KEEP", "REQ-ONE", "REQ-UPDATE"]
    assert output["requirements"][-1]["statement"] == "Updated behavior"
    assert current_path.read_bytes() == before


def test_removing_every_requirement_retires_the_capability(fixture):
    root, base, delta, _ = fixture
    old = deepcopy(delta["operations"]["added"][0])
    old["id"], old["scenarios"][0]["id"] = "REQ-OLD", "SCN-OLD"
    spec = dict(
        apiVersion=API, kind="CapabilitySpec", capability="old", title="Old", purpose="P", requirements=[old]
    )
    write_yaml(root / ".aifw/specs/current/old.yaml", spec)
    retire = dict(delta, capability="old", title="Old")
    retire["operations"] = dict(added=[], modified=[], removed=[dict(id="REQ-OLD", reason="Gone")])
    write_yaml(base / "specs/old.delta.yaml", retire)
    tasks = read_yaml(base / "tasks.yaml")
    tasks["tasks"][0]["requirementIds"].append("REQ-OLD")
    write_yaml(base / "tasks.yaml", tasks)
    assert [c["action"] for c in specs.preview_sync(root, ID)["changes"]] == ["remove", "create"]
    specs.update_status(root, ID, "ready")
    validated(root)
    result = specs.archive_change(root, ID, AT)
    assert not (root / ".aifw/specs/current/old.yaml").exists()
    assert result["currentSpecs"] == [".aifw/specs/current/search.yaml"]


def test_missing_precondition_and_dangling_link_block_readiness(fixture):
    root, base, delta, trace = fixture
    delta["operations"]["modified"] = delta["operations"].pop("added")
    delta["operations"]["added"] = []
    write_yaml(base / "specs/search.delta.yaml", delta)
    assert not specs.validate_change(root, ID)["pass"]
    trace["links"][0]["to"] = "UNKNOWN"
    write_yaml(base / "traceability.yaml", trace)
    assert not specs.analyze_change(root, ID)["pass"]
    with pytest.raises(AifwError):
        specs.update_status(root, ID, "ready")


def test_archive_requires_a_current_validation(fixture):
    root, base, _, _ = fixture
    specs.update_status(root, ID, "ready")
    with pytest.raises(AifwError, match="validate --change"):
        specs.archive_change(root, ID, AT)
    validated(root)
    (root / "tests/search.py").write_text("# changed after validation\n")
    with pytest.raises(AifwError, match="validate again"):
        specs.archive_change(root, ID, AT)
    unchanged(root, base)


def test_validate_change_checks_level_artifacts_and_records_evidence(fixture):
    from aifw import gates
    from test_workflows import init

    root, base, _, _ = fixture
    init(root, "python")
    gate_set = read_yaml(root / ".aifw/gates.yaml")
    for gate in gate_set["gates"]:
        if gate["id"] == "tests":
            gate["command"] = ["python", "-m", "pytest"]
    write_yaml(root / ".aifw/gates.yaml", gate_set)
    ok = lambda *_: dict(ok=True, stdout="", stderr="")  # noqa: E731
    report = gates.validate_change_workspace(root, ID, run=ok)
    assert report["status"] == "blocked"
    assert {m["artifact"] for m in report["missingArtifacts"]} == {
        "technical-plan",
        "rollback",
        "independent-review",
    }
    design = (base / "design.md").read_text(encoding="utf-8")
    design = design.replace("## Approach\n", "## Approach\n\nIndex records.\n")
    (base / "design.md").write_text(design + "\nRevert the index.\n", encoding="utf-8")
    review = base / "independent-review.md"
    for text, status in (("No findings.\n", "fail"), ("**Resultado:** reprovado\n", "fail")):
        review.write_text(text, encoding="utf-8")
        report = gates.validate_change_workspace(root, ID, run=ok)
        gate = [r for r in report["warnings"] + report["blockers"] if r["gateId"] == "independent-review"]
        assert gate and gate[0]["status"] == status
    review.write_text("No findings.\n\nResultado: aprovado com ressalvas\n", encoding="utf-8")
    report = gates.validate_change_workspace(root, ID, write=True, run=ok)
    assert report["status"] in {"pass", "warning"} and not report["missingArtifacts"]
    assert "independent-review" in [r["gateId"] for r in report["passed"]]
    specs.update_status(root, ID, "ready")
    assert specs.archive_change(root, ID, AT)["archivePath"].startswith(".aifw/changes/archive/")
