"""Public command contracts independent of the implementation language."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

REPO = Path(__file__).resolve().parents[1]
COMMANDS = json.loads((REPO / "tests_python/fixtures/commands.json").read_text())


def cli(root, *args):
    env = dict(os.environ, PYTHONPATH=str(REPO / "python"), PYTHONIOENCODING="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "aifw", *args],
        cwd=root,
        env=env,
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=30,
    )


def result(root, *args):
    process = cli(root, *args, "--json")
    assert process.returncode == 0, process.stderr or process.stdout
    return json.loads(process.stdout)


def test_python_entrypoint_without_node(tmp_path):
    process = cli(tmp_path, "--version")
    assert process.returncode == 0, process.stderr
    assert process.stdout.strip() == "0.4.1"


@pytest.mark.parametrize("command", COMMANDS)
def test_all_existing_commands_have_help(tmp_path, command):
    process = cli(tmp_path, *command, "--help")
    assert process.returncode == 0, process.stderr
    assert "usage:" in process.stdout.lower()


def test_init_map_resolution_and_pending_intake(tmp_path):
    initialized = result(tmp_path, "init", "--id", "northstar", "--name", "Northstar", "--python")
    assert initialized["manifest"]["spec"]["profiles"] == ["python"]
    assert initialized["manifest"]["spec"]["frameworkVersion"] == "0.4.1"
    assert (tmp_path / "PROJECT_MAP.md").is_file()
    assert result(tmp_path, "map", "check")["current"] is True
    assert result(tmp_path, "resolve", "build")["current"] is True
    assert result(tmp_path, "resolve", "check")["current"] is True
    pending = cli(tmp_path, "intake", "status", "--json")
    assert pending.returncode == 2
    assert json.loads(pending.stdout)["complete"] is False
    before = (tmp_path / "aifw.yaml").read_bytes()
    assert cli(tmp_path, "init", "--id", "other", "--name", "Other").returncode == 1
    assert (tmp_path / "aifw.yaml").read_bytes() == before


def test_framework_changes_remain_l3_and_brain(tmp_path):
    change = result(tmp_path, "change", "classify", "--framework-core")
    assert change["level"] == "L3"
    assert change["humanApproval"] == "required"
    route = result(
        tmp_path,
        "route",
        "explain",
        "--impact",
        "L3",
        "--operation",
        "implementation",
        "--uncertainty",
        "low",
    )
    assert route["route"] == "BRAIN"
    assert route["executionMode"] == "recommendation-only"


def test_invalid_inputs_never_downgrade_risk(tmp_path):
    assert cli(tmp_path, "change", "classify", "--complexity", "invalid").returncode != 0
    assert cli(tmp_path, "init", "--id", "sample", "--name", "Sample", "--web", "--python").returncode != 0
    assert not (tmp_path / "aifw.yaml").exists()
