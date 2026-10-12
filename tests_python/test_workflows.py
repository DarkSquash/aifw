import os
from pathlib import Path
import sys

import pytest

from aifw import brownfield, catalogs, conformance, gates, intake, policy, routing, workspace
from aifw.common import AifwError, API, assets, digest, parse_yaml, read_yaml, write_yaml

AT = "2026-09-06T03:00:00.000Z"


def init(root, profile=None, existing=False):
    workspace.initialize_project(
        root,
        dict(
            id="sample",
            name="Sample",
            projectType="existing" if existing else "new",
            locale="pt-BR",
            primaryEnvironment="windows",
            validationTargets=["windows"],
            profiles=[profile] if profile else [],
        ),
    )


@pytest.mark.parametrize("profile", [None, "python", "web-ts", "flutter-mobile"])
def test_scaffold_policy_and_intake(tmp_path, profile):
    init(tmp_path, profile)
    assert workspace.build_workspace_map(tmp_path)["current"]
    assert not intake.assess_intake(tmp_path)["ready"]
    policy.resolve_workspace(tmp_path, write=True)
    assert policy.resolve_workspace(tmp_path)["current"]
    with pytest.raises(AifwError):
        init(tmp_path, profile)


def test_existing_project_adoption_and_drift(tmp_path):
    (tmp_path / "pyproject.toml").write_text('[project]\nname="example"\nversion="1.0.0"\n')
    init(tmp_path, "python", True)
    before = (tmp_path / "pyproject.toml").read_bytes()
    report = brownfield.write_analysis(tmp_path, AT)["report"]
    assert report["digest"] == brownfield.analyze_brownfield(tmp_path, AT)["digest"]
    assert brownfield.apply_mapping(tmp_path, AT)["state"]["status"] == "review-required"
    with pytest.raises(AifwError):
        brownfield.approve_mapping(tmp_path, "agent:test", AT)
    brownfield.approve_mapping(tmp_path, "human:test", AT)
    assert brownfield.assess_adoption(tmp_path)["status"] == "current"
    assert (tmp_path / "pyproject.toml").read_bytes() == before
    catalog = read_yaml(tmp_path / ".aifw/catalog.yaml")
    catalog["entities"][0]["owner"] = "human:another"
    write_yaml(tmp_path / ".aifw/catalog.yaml", catalog)
    assert brownfield.assess_adoption(tmp_path)["status"] != "current"


def test_decision_approval(tmp_path):
    init(tmp_path)
    decision = catalogs.recommend_workspace(
        tmp_path, "application-architecture", ["domain:complex", "integrations:many"], write=True
    )
    option = next(r["optionId"] for r in decision["rankings"] if r["eligible"])
    (tmp_path / "adr.md").write_text("# Fixture architecture approval")
    with pytest.raises(AifwError):
        catalogs.approve_decision(tmp_path, "application-architecture", option, "agent:test", AT, "adr.md")
    accepted = catalogs.approve_decision(
        tmp_path, "application-architecture", option, "human:test", AT, "adr.md"
    )
    assert accepted["status"] == "accepted"


def test_complete_charter_approval(tmp_path):
    init(tmp_path)
    with pytest.raises(AifwError):
        intake.approve_workspace(tmp_path, "human:test", AT)
    charter = read_yaml(tmp_path / ".aifw/charter.yaml")
    charter.update(
        problem="Solve a real problem",
        audiences=["Users"],
        outcomes=["Working product"],
        scope={"in": ["Core"], "out": ["Extra"]},
        dataClassification="public",
        autonomy=dict(
            localGit=True,
            remoteGit="approval-required",
            previewDeploy=True,
            productionDeploy="approval-required",
        ),
        unknowns=[],
    )
    write_yaml(tmp_path / ".aifw/charter.yaml", charter)
    approved = intake.approve_workspace(tmp_path, "human:test", AT)["charter"]
    assert approved["approval"]["contentDigest"] == digest(
        {k: v for k, v in approved.items() if k != "approval"}
    )
    assert intake.assess_intake(tmp_path)["complete"]


def test_routing_activation_requires_evidence_thresholds(tmp_path):
    init(tmp_path)
    assert not routing.load_routing(tmp_path)["enabled"]
    for report in [
        dict(cases=29, passRate=1, criticalFailures=0),
        dict(cases=30, passRate=0.94, criticalFailures=0),
        dict(cases=30, passRate=1, criticalFailures=1),
        dict(cases=30, passRate=float("nan"), criticalFailures=0),
    ]:
        with pytest.raises(AifwError):
            routing.activate_routing(tmp_path, report, "human:test", "adr.md")
    report = conformance.evaluate_routing_cases(assets() / "evals/routing/cases.yaml")
    metrics = {k: report[k] for k in ("cases", "passRate", "criticalFailures")}
    routing.activate_routing(tmp_path, metrics, "human:test", "adr.md")
    assert routing.load_routing(tmp_path)["mode"] == "automatic"


def test_context_redacts_secrets():
    from aifw.context import redact

    text = redact("api_key=secret123 Bearer secret456 sk-abcdefghijk")
    assert all(s not in text for s in ("secret123", "secret456", "sk-abcdefghijk"))


def test_gates_execute_and_reject_workdir_escape(tmp_path):
    config = dict(
        apiVersion=API,
        kind="QualityGateSet",
        philosophy="progressive-by-risk",
        gates=[
            dict(
                id="test",
                enforcement="hard",
                levels=["L1"],
                command=[sys.executable, "-c", "print('verified')"],
            )
        ],
    )
    results = gates.run_gate_set(config, "L1", tmp_path)
    assert results[0]["status"] == "pass" and "verified" in results[0]["evidence"][0]
    config["gates"][0]["workingDirectory"] = ".."
    with pytest.raises(AifwError):
        gates.run_gate_set(config, "L1", tmp_path)


@pytest.mark.skipif(os.name != "nt", reason="Windows batch shim behavior")
def test_windows_batch_gate_with_space(tmp_path):
    shim = tmp_path / "gate command.cmd"
    shim.write_text("@echo off\necho %~1\nexit /b 0\n")
    result = gates.run_command(str(shim), ["hello world"], tmp_path)
    assert result["ok"] and "hello world" in result["stdout"]


def test_yaml_core_compatibility():
    assert parse_yaml("on: yes\ndate: 2026-09-06\nenabled: true\n") == {
        "on": "yes",
        "date": "2026-09-06",
        "enabled": True,
    }
    with pytest.raises(AifwError):
        parse_yaml("key: 1\nkey: 2\n")
    assert parse_yaml("decimal: 0123\noctal: 0o17\nsexagesimal: 12:30\nexponent: 1e3\n") == dict(
        decimal=123, octal=15, sexagesimal="12:30", exponent=1000.0
    )


def test_python_gate_uses_interpreter_selected_on_path(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(Path(sys.executable).parent))
    result = gates.run_command("python", ["-c", "import sys; print(sys.prefix)"], tmp_path)
    assert result["ok"], result["stderr"]
    assert Path(result["stdout"].strip()) == Path(sys.prefix)


def test_python_gate_falls_back_to_own_environment_without_python_on_path(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "")
    result = gates.run_command("python", ["-c", "import sys; print(sys.prefix)"], tmp_path)
    assert result["ok"], result["stderr"]
    assert Path(result["stdout"].strip()) == Path(sys.prefix)


def test_editing_an_approved_charter_reopens_intake(tmp_path):
    init(tmp_path)
    charter = read_yaml(tmp_path / ".aifw/charter.yaml")
    charter.update(
        problem="Solve a real problem",
        audiences=["Users"],
        outcomes=["Working product"],
        scope={"in": ["Core"], "out": ["Extra"]},
        dataClassification="public",
        autonomy=dict(
            localGit=True,
            remoteGit="approval-required",
            previewDeploy=True,
            productionDeploy="approval-required",
        ),
        unknowns=[],
    )
    write_yaml(tmp_path / ".aifw/charter.yaml", charter)
    status = intake.assess_intake(tmp_path)
    assert status["ready"] and not status["complete"] and not status["charterApproved"]
    intake.approve_workspace(tmp_path, "human:test", AT)
    assert intake.assess_intake(tmp_path)["complete"]
    charter = read_yaml(tmp_path / ".aifw/charter.yaml")
    charter["outcomes"].append("Unapproved addition")
    write_yaml(tmp_path / ".aifw/charter.yaml", charter)
    assert not intake.assess_intake(tmp_path)["complete"]
