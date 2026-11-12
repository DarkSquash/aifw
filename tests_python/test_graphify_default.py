"""aifw claude enable sets up graphify when it is on PATH (change graphify-default); doubles only."""

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from aifw import cli
from aifw.claude import check_project, enable_project
from aifw.common import read_yaml, write_yaml
from aifw.hooks import handle
from test_workflows import init

NAME = "graphify-fake-for-tests"
FAKE = os.path.abspath("/fake/bin/graphify-fake")  # absolute on Windows too
REAL_RUN = subprocess.run
REAL_WHICH = shutil.which


class Graphify:
    """Stands in for the graphify executable: records calls and can fail on a subcommand."""

    def __init__(self):
        self.calls, self.codes, self.raises = [], {}, {}

    def subcommands(self):
        return [call[0][1:] for call in self.calls]

    def run(self, argv, *args, **kwargs):
        if argv[0] != FAKE:
            return REAL_RUN(argv, *args, **kwargs)
        self.calls.append((list(argv), kwargs.get("cwd"), kwargs))
        sub = argv[1]
        if sub in self.raises:
            raise self.raises[sub]
        code = self.codes.get(sub, 0)
        if sub == "update" and code == 0:
            out = Path(kwargs["cwd"]) / "graphify-out"
            out.mkdir(exist_ok=True)
            (out / "graph.json").write_text("{}")
        return subprocess.CompletedProcess(argv, code, b"", b"")


def on_path(monkeypatch):
    monkeypatch.setattr("aifw.claude.GRAPHIFY", NAME, raising=False)
    monkeypatch.setattr(
        shutil, "which", lambda cmd, *a, **k: FAKE if cmd == NAME else REAL_WHICH(cmd, *a, **k)
    )


@pytest.fixture
def graphify(monkeypatch):
    on_path(monkeypatch)
    double = Graphify()
    monkeypatch.setattr(subprocess, "run", double.run)
    return double


def git_project(root):
    init(root)
    REAL_RUN(["git", "init", "-q"], cwd=root, check=True)
    return root


def ignored(root):
    file = root / ".gitignore"
    return file.read_text().splitlines() if file.is_file() else []


def test_absent_from_path_skips_everything(tmp_path, monkeypatch):
    monkeypatch.setattr("aifw.claude.GRAPHIFY", NAME, raising=False)  # not on PATH
    calls = []
    monkeypatch.setattr(
        subprocess, "run", lambda argv, *a, **k: calls.append(argv) or REAL_RUN(argv, *a, **k)
    )
    init(tmp_path)
    result = enable_project(tmp_path)
    assert "not found on PATH" in result["graphify"]
    assert not [c for c in calls if NAME in str(c)]
    assert not any("graphify-out" in line for line in ignored(tmp_path))
    for key in ("status", "hooksChanged", "gitignored", "settings", "skill", "agents", "nextAction"):
        assert key in result


def test_happy_path_in_git_project(tmp_path, graphify):
    root = git_project(tmp_path)
    result = enable_project(root)
    assert "graphify-out/" in ignored(root)
    assert graphify.subcommands() == [["update", "."], ["hook", "install"]]
    assert Path(graphify.calls[0][1]) == root
    assert "graph built" in result["graphify"] and "hook" in result["graphify"]


def test_second_run_skips_update_and_reinstalls_hook(tmp_path, graphify):
    root = git_project(tmp_path)
    enable_project(root)
    graphify.calls.clear()
    result = enable_project(root)
    assert graphify.subcommands() == [["hook", "install"]]
    assert ignored(root).count("graphify-out/") == 1
    assert result["graphify"]


def test_core_hooks_path_skips_hook_install(tmp_path, graphify):
    root = git_project(tmp_path)
    REAL_RUN(["git", "config", "core.hooksPath", ".husky"], cwd=root, check=True)
    result = enable_project(root)
    assert graphify.subcommands() == [["update", "."]]
    assert "hooksPath" in result["graphify"]


def test_no_git_dir_skips_hook_install(tmp_path, graphify):
    init(tmp_path)
    result = enable_project(tmp_path)
    assert result["status"] == "enabled"
    assert graphify.subcommands() == [["update", "."]]


def test_existing_graphify_out_keeps_gitignore_but_still_updates(tmp_path, graphify):
    root = git_project(tmp_path)
    (root / "graphify-out").mkdir()
    enable_project(root)
    assert "graphify-out/" not in ignored(root)
    assert ["update", "."] in graphify.subcommands()


def test_gitignore_not_writable_is_a_note_not_a_crash(tmp_path, graphify, monkeypatch):
    import aifw.claude as claude

    original = claude.ignore_local_logs

    def guarded(root, *args, **kwargs):
        if args == (("graphify-out/",),):
            raise PermissionError("read-only .gitignore")
        return original(root, *args, **kwargs)

    monkeypatch.setattr(claude, "ignore_local_logs", guarded)
    root = git_project(tmp_path)
    result = enable_project(root)
    assert result["status"] == "enabled"
    assert "could not update .gitignore: add `graphify-out/` yourself" in result["graphify"]
    assert graphify.subcommands() == [["update", "."], ["hook", "install"]]


@pytest.mark.parametrize("planted", ["inside", "relative"])
def test_executable_found_inside_the_project_is_not_run(tmp_path, graphify, monkeypatch, planted):
    planted = str(tmp_path / "graphify.cmd") if planted == "inside" else r".\graphify.CMD"
    monkeypatch.setattr(shutil, "which", lambda cmd, *a, **k: planted if cmd == NAME else REAL_WHICH(cmd))
    spy = []
    monkeypatch.setattr(
        subprocess, "run", lambda argv, *a, **k: spy.append(argv) or graphify.run(argv, *a, **k)
    )
    root = git_project(tmp_path)
    result = enable_project(root)
    assert "inside the project" in result["graphify"]
    assert graphify.calls == [] and not [c for c in spy if planted in c]
    assert not any("graphify-out" in line for line in ignored(root))


@pytest.mark.parametrize(
    "codes, raises, hint",
    [
        ({"update": 1}, {}, "graphify update ."),
        ({}, {"update": subprocess.TimeoutExpired("graphify", 300)}, "graphify update ."),
        ({}, {"hook": OSError("boom")}, "graphify hook install"),
    ],
    ids=["update-exit-1", "update-timeout", "hook-oserror"],
)
def test_failures_never_break_enable(tmp_path, graphify, codes, raises, hint):
    root = git_project(tmp_path)
    graphify.codes, graphify.raises = codes, raises
    result = enable_project(root)
    assert result["status"] == "enabled"
    assert hint in result["graphify"]
    assert (root / ".claude/settings.json").is_file()
    assert (root / ".claude/skills/aifw-workflow/SKILL.md").is_file()
    assert all((root / path).is_file() for path in result["agents"])


@pytest.mark.parametrize("scenario", ["happy", "failing", "no-git", "second-run"])
def test_never_runs_graphify_claude_install(tmp_path, graphify, scenario):
    root = tmp_path
    if scenario == "no-git":
        init(root)
    else:
        git_project(root)
    if scenario == "failing":
        graphify.codes = {"update": 1, "hook": 1}
    enable_project(root)
    if scenario == "second-run":
        enable_project(root)
    assert graphify.calls
    assert not [c for c in graphify.calls if "claude" in c[0]]


def test_no_graphify_option_in_process_cli(tmp_path, graphify, monkeypatch, capsys):
    root = git_project(tmp_path)
    monkeypatch.chdir(root)
    assert cli.main(["claude", "enable", "--no-graphify", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["graphify"] == "skipped (--no-graphify)"
    assert graphify.calls == []


def test_no_graphify_parameter(tmp_path, graphify):
    root = git_project(tmp_path)
    result = enable_project(root, graphify=False)
    assert result["graphify"] == "skipped (--no-graphify)"
    assert graphify.calls == []


def test_check_is_the_same_with_and_without_graphify(tmp_path, monkeypatch):
    init(tmp_path)
    enable_project(tmp_path)
    home = tmp_path / "home"
    without = check_project(tmp_path, home)
    on_path(monkeypatch)
    assert check_project(tmp_path, home) == without


def decision(root, command):
    output = handle(dict(cwd=str(root), tool_name="Bash", tool_input=dict(command=command)))
    return output and output["hookSpecificOutput"]["permissionDecision"]


@pytest.mark.parametrize("command", ['graphify query "x"', "graphify update ."])
def test_hook_lets_graphify_through_with_opaque_code_allow(tmp_path, command):
    init(tmp_path)
    policy = read_yaml(tmp_path / ".aifw/permissions.yaml")
    write_yaml(tmp_path / ".aifw/permissions.yaml", dict(policy, opaqueCode="allow"))
    assert decision(tmp_path, command) not in ("deny", "ask")


@pytest.mark.parametrize("command", ['graphify query "x"', "graphify update ."])
def test_hook_without_opaque_code_key_documents_current_behavior(tmp_path, command):
    init(tmp_path)
    policy = read_yaml(tmp_path / ".aifw/permissions.yaml")
    write_yaml(tmp_path / ".aifw/permissions.yaml", {k: v for k, v in policy.items() if k != "opaqueCode"})
    # Today a plain `graphify ...` is not flagged at all (no decision), not even "ask": the design.md
    # claim that it asks without the key does not hold for these commands.
    assert decision(tmp_path, command) is None
