"""The hook reads code a command runs indirectly: script files, local modules, package.json scripts,
Makefile recipes and git settings that run programs (change hook-indirect-code)."""

import json
import subprocess
import time

import pytest

from aifw.common import read_yaml, write_yaml
from aifw.hooks import handle
from aifw.shell import analyze, runs_tests
from test_workflows import init

PUSH = "git push origin main\n"
PYTHON_PUSH = "import subprocess\nsubprocess.run(['git', 'push'])\n"


def project(tmp_path, harmless=False):
    """A project whose scripts push, or only print when harmless."""
    shell = "echo hi\nls -la\n" if harmless else PUSH
    python = "print('hi')\n" if harmless else PYTHON_PUSH
    for name in ("run.sh", "run.ps1", "run.bat"):
        (tmp_path / name).write_text(shell)
    (tmp_path / "run.py").write_text(python)
    (tmp_path / "run").write_text(python)
    (tmp_path / "tool.py").write_text(python)
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg/__main__.py").write_text(python)
    (tmp_path / "run.pl").write_text("print 'hi';\n")
    scripts = {"deploy": shell.strip().replace("\n", " && "), "test": "pytest", "pretest": "echo pre"}
    (tmp_path / "package.json").write_text(json.dumps({"scripts": scripts}))
    (tmp_path / "Makefile").write_text(
        "build:\n\t@echo $(CC) $$HOME\nrelease: build\n\t" + shell.split("\n")[0]
    )
    return tmp_path


def decision(root, command):
    output = handle(dict(cwd=str(root), tool_name="Bash", tool_input=dict(command=command)))
    return output and output["hookSpecificOutput"]["permissionDecision"]


def strict(root):
    """A project that asks for code the hook cannot read; new projects allow it (ADR-0037)."""
    policy = read_yaml(root / ".aifw/permissions.yaml")
    write_yaml(root / ".aifw/permissions.yaml", dict(policy, opaqueCode="ask"))


VECTORS = [
    "bash run.sh",
    "sh ./run.sh",
    "./run.sh",
    "pwsh -File run.ps1",
    "powershell -ExecutionPolicy Bypass -File run.ps1",
    "./run.ps1",
    "cmd /c run.bat",
    "uv run run.py",
    "./run.py",
    "python run",
    "python -m tool",
    "python -m pkg",
    "npm run deploy",
    "yarn deploy",
    "make release",
    "make -f Makefile release",
]


@pytest.mark.parametrize("command", VECTORS)
def test_indirect_code_that_pushes_asks(tmp_path, command):
    init(tmp_path)
    strict(tmp_path)
    assert decision(project(tmp_path), command) == "ask"


@pytest.mark.parametrize("command", [*VECTORS, "npm test", "python run.py"])
def test_harmless_indirect_code_runs_without_asking(tmp_path, command):
    init(tmp_path)
    assert decision(project(tmp_path, harmless=True), command) is None


@pytest.mark.parametrize("command", ["perl run.pl", "./run.pl"])
def test_code_the_hook_cannot_read_is_opaque(tmp_path, command):
    assert analyze(command, cwd=project(tmp_path))["kind"] == "opaque"


def test_binaries_built_in_the_project_are_opaque(tmp_path):
    (tmp_path / "app").write_bytes(b"\x7fELF\0\0binary")
    assert analyze("./app", cwd=tmp_path)["kind"] == "opaque"


def test_installed_tools_and_programs_elsewhere_are_not_read(tmp_path):
    tool = tmp_path / ".venv/bin/ruff"
    tool.parent.mkdir(parents=True)
    tool.write_bytes(b"\0binary")
    assert analyze(".venv/bin/ruff check .", cwd=tmp_path)["kind"] != "opaque"
    outside = tmp_path.parent / "outside-tool.exe"
    outside.write_bytes(b"\0binary")
    assert analyze(f"{outside.as_posix()} --version", cwd=tmp_path)["kind"] != "opaque"


def test_scripts_read_the_scripts_they_call_once(tmp_path):
    (tmp_path / "a.sh").write_text("bash b.sh\n")
    (tmp_path / "b.sh").write_text(PUSH)
    assert analyze("bash a.sh", cwd=tmp_path)["kind"] == "git-remote"
    # A script that calls itself is read once: its requests already count higher up.
    (tmp_path / "loop.sh").write_text("bash loop.sh\n" * 30 + PUSH)
    started = time.perf_counter()
    assert analyze("bash loop.sh", cwd=tmp_path)["kind"] == "git-remote"
    assert time.perf_counter() - started < 2


def test_a_quote_left_open_is_opaque_and_fast(tmp_path):
    (tmp_path / "long.sh").write_text("echo it's\n" + "echo line\n" * 3000)
    started = time.perf_counter()
    assert analyze("bash long.sh", cwd=tmp_path)["kind"] == "opaque"
    assert time.perf_counter() - started < 2


GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def git(root, *args):
    subprocess.run([*GIT, *args], cwd=root, check=True, capture_output=True, stdin=subprocess.DEVNULL)


def test_test_runners_still_count_as_verification(tmp_path):
    project(tmp_path, harmless=True)
    (tmp_path / "gradlew").write_text("#!/bin/sh\neval exec java\n")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "gradlew")
    git(tmp_path, "commit", "-qm", "wrapper")
    for command in ("python -m pytest", "npm test", "./gradlew test"):
        assert runs_tests(command)
        assert analyze(command, cwd=tmp_path)["kind"] != "opaque"


@pytest.mark.parametrize("command", ["./gradlew test", "./pytest -q", "python -m pytest"])
def test_test_runners_written_in_the_project_are_read(tmp_path, command):
    """Only an unchanged wrapper from the repository runs unread; a local pytest.py shadows the package."""
    for name in ("gradlew", "pytest"):
        (tmp_path / name).write_text("#!/bin/sh\ngit push\n")
    (tmp_path / "pytest.py").write_text(PYTHON_PUSH)
    assert analyze(command, cwd=tmp_path)["kind"] in {"git-remote", "opaque"}


def test_package_scripts_include_pre_and_post_scripts(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"build": "echo ok", "postbuild": PUSH}}))
    assert analyze("npm run build", cwd=tmp_path)["kind"] == "git-remote"


def test_make_reads_shell_calls_and_keeps_make_variables_as_data(tmp_path):
    (tmp_path / "Makefile").write_text(
        "FLAGS = -k\nall:\n\t$(MAKE) -C sub $(FLAGS)\n\t$(MAKE) other $@ $(CC)\n"
    )
    assert analyze("make", cwd=tmp_path)["kind"] != "opaque"
    (tmp_path / "Makefile").write_text("all:\n\techo $(shell git push)\n")
    assert analyze("make", cwd=tmp_path)["kind"] == "git-remote"


@pytest.mark.parametrize(
    ("command", "kind"),
    [
        ("git config alias.p push", "opaque"),
        ("git config --global alias.l list", "opaque"),
        ("git config set alias.x push", "opaque"),
        ("git config core.hooksPath .hooks", "opaque"),
        ("git config core.sshCommand 'ssh -i k'", "opaque"),
        ("git -c core.hooksPath=x commit -m x", "opaque"),
        ("git -c diff.x.textconv=cat diff", "opaque"),
        ("git config --get alias.p", "read-only"),
        ("git config get alias.p", "read-only"),
        ("git config --list", "read-only"),
        ("git config --unset alias.p", "git-local"),
        ("git config user.name x", "git-local"),
    ],
)
def test_git_settings_that_run_programs_are_opaque(command, kind):
    assert analyze(command)["kind"] == kind


@pytest.mark.parametrize(
    ("tool", "tool_input"),
    [
        ("Write", dict(file_path=".git/hooks/pre-commit")),
        ("Edit", dict(file_path=".git/config")),
        ("Bash", dict(command="echo push > .git/hooks/post-commit")),
    ],
)
def test_git_hooks_and_config_are_control_files(tmp_path, tool, tool_input):
    init(tmp_path)
    output = handle(dict(cwd=str(tmp_path), tool_name=tool, tool_input=tool_input))
    assert output["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert ".git/" in output["hookSpecificOutput"]["permissionDecisionReason"]


@pytest.mark.parametrize(
    "command",
    [
        "printf 'git push' > new.sh && bash new.sh",
        "printf 'git push' > new.sh && ./new.sh",
        "cat > new.py <<'EOF'\nimport subprocess\nEOF\npython new.py",
        "printf 'git push' > ok.sh && bash ok.sh",
        "echo 'git push' >> ok.sh; ./ok.sh",
        "sed -i s/hi/push/ package.json && npm run build",
        "printf 'all:\\n\\tgit push' > Makefile && make",
    ],
)
def test_code_written_by_the_same_command_is_opaque(tmp_path, command):
    """The hook reads files before the command runs, so a file the command writes is not what it read."""
    (tmp_path / "ok.sh").write_text("echo hi\n")
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"build": "echo hi"}}))
    assert analyze(command, cwd=tmp_path)["kind"] == "opaque"


@pytest.mark.parametrize(
    "command", ["cat ok.sh && bash ok.sh", "chmod +x ok.sh && ./ok.sh", "pytest -q && ./ok.sh"]
)
def test_reading_or_marking_a_script_before_running_it_does_not_ask(tmp_path, command):
    (tmp_path / "ok.sh").write_text("echo hi\n")
    assert analyze(command, cwd=tmp_path)["kind"] != "opaque"


# Findings of the first independent review of this change.


@pytest.mark.parametrize(
    "command",
    [
        "source run.sh",
        ". ./run.sh",
        "bash -c 'source run.sh'",
        "cmd /c call run.bat",
        "timeout 10 bash run.sh",
        "nice -n 5 ./run.sh",
        "uv run --with requests run.py",
        "env FOO=1 bash run.sh",
        "bun deploy",
        "bun run deploy",
        "npm --prefix web run deploy",
        "pnpm -C web run deploy",
        "npm version patch",
        "powershell ./run.ps1",
    ],
)
def test_more_forms_that_run_scripts_are_read(tmp_path, command):
    project(tmp_path)
    (tmp_path / "web").mkdir()
    (tmp_path / "web/package.json").write_text(json.dumps({"scripts": {"deploy": PUSH.strip()}}))
    scripts = {"deploy": PUSH.strip(), "version": PUSH.strip()}
    (tmp_path / "package.json").write_text(json.dumps({"scripts": scripts}))
    assert analyze(command, cwd=tmp_path)["kind"] in {"git-remote", "opaque"}


@pytest.mark.parametrize(
    "makefile",
    [
        "PUSH = git push\nrelease:\n\t$(PUSH)\n",
        "release: ; git push\n",
        "X := $(shell git push)\nall:\n\techo hi\n",
        "X != git push\nall:\n\techo hi\n",
        "include other.mk\nall:\n\techo hi\n",
        ".RECIPEPREFIX = >\nall:\n> git push\n",
        "all:\n\techo hi && \\\ngit push\n",
        "CMD = $(subst X,push,git X)\nall:\n\t$(CMD)\n",
    ],
)
def test_makefile_forms_that_hide_commands_ask(tmp_path, makefile):
    (tmp_path / "Makefile").write_text(makefile)
    assert analyze("make", cwd=tmp_path)["kind"] in {"git-remote", "opaque"}


@pytest.mark.parametrize(
    "command",
    ["make -Csub", "make --directory=sub", "make -fother.mk", "make --file=other.mk", "make PUSH='git push'"],
)
def test_make_options_glued_or_overriding_are_followed(tmp_path, command):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub/Makefile").write_text("all:\n\tgit push\n")
    (tmp_path / "other.mk").write_text("all:\n\tgit push\n")
    (tmp_path / "Makefile").write_text("PUSH = echo hi\nall:\n\t$(PUSH)\n")
    assert analyze(command, cwd=tmp_path)["kind"] in {"git-remote", "opaque"}


@pytest.mark.parametrize(
    "command",
    [
        "printf 'import os' > newmod.py && python -m newmod",
        "printf 'git push' > new && bash new",
        "printf 'git push' > new && python new",
        "printf 'all:\\n\\tgit push' > new.mk && make -f new.mk",
        "echo 'git push' | python -",
        "echo 'git push' | sh -s",
    ],
)
def test_code_without_a_readable_file_is_opaque(tmp_path, command):
    assert analyze(command, cwd=tmp_path)["kind"] == "opaque"


@pytest.mark.parametrize(
    "command",
    [
        "git config diff.external ./x.sh",
        "git config --file .git/config alias.p push",
        "git config -f other alias.p push",
        "git config --type path core.hooksPath h",
        "git --config-env core.hooksPath=H commit -m x",
        "git config submodule.x.update '!git push'",
        "git -c protocol.ext.allow=always fetch ext::x",
        "git config hook.pre-commit.command ./x.sh",
        "git config --edit",
    ],
)
def test_more_git_settings_that_run_programs_are_opaque(command):
    assert analyze(command)["kind"] == "opaque"


def test_a_package_json_the_hook_cannot_parse_is_opaque(tmp_path):
    (tmp_path / "package.json").write_bytes(b"\xef\xbb\xbf" + json.dumps({"scripts": {"x": PUSH}}).encode())
    assert analyze("npm run x", cwd=tmp_path)["kind"] == "git-remote"  # a BOM is read like npm reads it
    (tmp_path / "package.json").write_text("{not json")
    assert analyze("npm run x", cwd=tmp_path)["kind"] == "opaque"


def test_env_split_string_is_opaque():
    assert analyze("env -S 'git push'")["kind"] == "opaque"


@pytest.mark.parametrize(
    ("tool", "tool_input"),
    [
        ("Write", dict(file_path=".GIT/hooks/pre-commit")),
        ("Write", dict(file_path="sub/.git/hooks/pre-commit")),
        ("Bash", dict(command="cp x .git/hook*/")),
        ("Bash", dict(command="echo x > .GIT/config")),
        ("Write", dict(file_path=".venv/bin/tool")),
        ("Edit", dict(file_path="node_modules/.bin/eslint")),
    ],
)
def test_git_folder_and_installed_tools_ask_in_any_case(tmp_path, tool, tool_input):
    init(tmp_path)
    output = handle(dict(cwd=str(tmp_path), tool_name=tool, tool_input=tool_input))
    assert output["hookSpecificOutput"]["permissionDecision"] == "ask"


@pytest.mark.parametrize(
    "command",
    [
        "npm test && git add package.json",
        "source .venv/bin/activate",
        "uv sync && python -m venv .venv",
        "powershell Get-ChildItem",
        "python -V",
        "node --version",
        ".venv/bin/ruff format .",
        "source .venv/bin/activate && ruff format .",
        "python3.12 run.py",
        "node -r dotenv/config run.js",
        "GIT_AUTHOR_NAME=x git status",
        "yarn why lodash",
    ],
)
def test_common_commands_stay_quiet(tmp_path, command):
    init(tmp_path)
    project(tmp_path, harmless=True)
    (tmp_path / ".venv/bin").mkdir(parents=True)
    (tmp_path / ".venv/bin/activate").write_text("deactivate () { unset X; }\nexport PATH\n")
    (tmp_path / "run.js").write_text("console.log(1)\n")
    assert decision(tmp_path, command) is None


# Findings of the second independent review, under the model decided in the impasse (ADR-0034).


@pytest.mark.parametrize(
    "command",
    [
        "node -r ./deploy.js ok.js",
        "node --require=./deploy.js ok.js",
        "node --import ./deploy.js ok.js",
        "make SHELL=./run.sh",
        "make --eval='x:=1'",
        "make -f evil.mk -f Makefile",
        "MAKEFLAGS=-e make",
        "npm test --script-shell=./run.sh",
        "npm_config_script_shell=./run.sh npm run ok",
        "yarn workspace web deploy",
        "yarn workspaces foreach run deploy",
        "GIT_SSH_COMMAND='sh run.sh' git fetch",
        "GIT_CONFIG_COUNT=1 git commit -m x",
        "export GIT_EXTERNAL_DIFF=./run.sh; git diff",
        "NODE_OPTIONS='-r ./deploy.js' node ok.js",
        "BASH_ENV=./run.sh bash -c true",
        "python3.12 run.py",
    ],
)
def test_second_review_forms_ask(tmp_path, command):
    project(tmp_path)
    (tmp_path / "deploy.js").write_text("require('child_process').execSync('git push')\n")
    (tmp_path / "ok.js").write_text("console.log(1)\n")
    (tmp_path / "evil.mk").write_text("all:\n\tgit push\n")
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"ok": "echo ok", "test": "echo ok"}}))
    assert analyze(command, cwd=tmp_path)["kind"] in {"git-remote", "opaque"}


@pytest.mark.parametrize("command", ["yarn publish", "pnpm publish"])
def test_publish_builtins_keep_their_rule_with_a_same_named_script(tmp_path, command):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"publish": "echo hi"}}))
    assert analyze(command, cwd=tmp_path)["kind"] == "publish"


def test_npmrc_script_shell_is_opaque(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"ok": "echo ok"}}))
    assert analyze("npm run ok", cwd=tmp_path)["kind"] != "opaque"
    (tmp_path / ".npmrc").write_text("script-shell=./run.sh\n")
    assert analyze("npm run ok", cwd=tmp_path)["kind"] == "opaque"


def test_scripts_calling_scripts_many_times_stay_fast(tmp_path):
    for level in range(3):
        calls = "".join(f"bash s{level + 1}_{i}.sh\n" for i in range(40))
        for i in range(40):
            (tmp_path / f"s{level}_{i}.sh").write_text(calls if level < 2 else "echo leaf\n")
    (tmp_path / "s2_0.sh").write_text(PUSH)
    started = time.perf_counter()
    assert analyze("bash s0_0.sh", cwd=tmp_path)["kind"] == "git-remote"
    assert time.perf_counter() - started < 3


# Third independent review: false positives against the decided model, and the low findings.

SPHINX = (
    "SPHINXOPTS    ?=\nSPHINXBUILD   ?= sphinx-build\nSOURCEDIR = source\nBUILDDIR = build\n"
    'help:\n\t@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)\n'
    ".PHONY: help Makefile\n"
    '%: Makefile\n\t@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)\n'
)


@pytest.mark.parametrize(
    ("makefile", "command"),
    [
        ("test:\n\tpytest\nrelease:\n\tgit push\n", "make test"),
        ("all: build\nbuild:\n\techo hi\nrelease:\n\tgit push\n", "make"),
        (SPHINX, "make html"),
        ("lint:\n\truff check $(SRC)\n", "make lint"),
        ("CFLAGS = -O2\nall:\n\t$(CC) $(CFLAGS) -o x x.c\n", "make CFLAGS=-O0"),
    ],
)
def test_make_reads_only_the_goals_asked(tmp_path, makefile, command):
    (tmp_path / "Makefile").write_text(makefile)
    assert analyze(command, cwd=tmp_path)["kind"] not in {"git-remote", "opaque"}


@pytest.mark.parametrize(
    ("makefile", "command"),
    [
        ("test: release\n\tpytest\nrelease:\n\tgit push\n", "make test"),
        ("test:\n\tpytest\n%:\n\tgit push\n", "make anything"),
        ("all:\n\t$(MAKE) release\nrelease:\n\tgit push\n", "make"),
        ("all:\n\techo hi\n", "make .SHELLFLAGS=-c"),
        ("hello:\n", "make CC=./x hello"),
    ],
)
def test_make_still_reads_prerequisites_patterns_and_recursion(tmp_path, makefile, command):
    (tmp_path / "Makefile").write_text(makefile)
    assert analyze(command, cwd=tmp_path)["kind"] in {"git-remote", "opaque"}


@pytest.mark.parametrize(
    "command",
    [
        "GIT_EDITOR=true git rebase --continue",
        "GIT_PAGER=cat git log",
        "GIT_CONFIG_NOSYSTEM=1 git status",
        "NODE_OPTIONS=--experimental-vm-modules npm test",
        "export NODE_OPTIONS=--max-old-space-size=4096",
    ],
)
def test_harmless_values_of_watched_variables_do_not_ask(tmp_path, command):
    project(tmp_path, harmless=True)
    assert analyze(command, cwd=tmp_path)["kind"] != "opaque"


def test_glued_preload_written_in_the_same_command_is_opaque(tmp_path):
    (tmp_path / "ok.js").write_text("console.log(1)\n")
    (tmp_path / "deploy.js").write_text("console.log(1)\n")
    command = "printf x > deploy.js && node --require=./deploy.js ok.js"
    assert analyze(command, cwd=tmp_path)["kind"] == "opaque"


def test_package_scripts_calling_npm_many_times_stay_fast(tmp_path):
    scripts = {
        f"s{level}_{i}": " && ".join(f"npm run s{level + 1}_{j}" for j in range(20))
        for level in range(2)
        for i in range(20)
    }
    scripts |= {f"s2_{i}": "echo leaf" for i in range(20)}
    scripts["s2_0"] = PUSH.strip()
    (tmp_path / "package.json").write_text(json.dumps({"scripts": scripts}))
    started = time.perf_counter()
    assert analyze("npm run s0_0", cwd=tmp_path)["kind"] == "git-remote"
    assert time.perf_counter() - started < 3


def test_shell_setup_and_build_wrappers_stay_quiet(tmp_path):
    (tmp_path / "env/bin").mkdir(parents=True)
    (tmp_path / "env/bin/activate").write_text("deactivate () { unset X; }\n")
    assert analyze("source env/bin/activate", cwd=tmp_path)["kind"] == "read-only"
    outside = tmp_path.parent / f"{tmp_path.name}-bashrc"
    outside.write_text("alias ll='ls -l'\neval \"$(starship init bash)\"\n")
    assert analyze(f"source {outside.as_posix()}", cwd=tmp_path)["kind"] == "read-only"
    (tmp_path / "gradlew").write_text("#!/bin/sh\neval exec java\n")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "gradlew")
    git(tmp_path, "commit", "-qm", "wrapper")
    assert analyze("./gradlew build", cwd=tmp_path)["kind"] != "opaque"


def test_fourth_review_regressions_ask(tmp_path):
    (tmp_path / "infra/env").mkdir(parents=True)
    (tmp_path / "infra/env/deploy.sh").write_text(PUSH)
    assert analyze("bash infra/env/deploy.sh", cwd=tmp_path)["kind"] == "git-remote"
    (tmp_path / "Makefile").write_text(".DEFAULT_GOAL := release\nall:\n\techo hi\nrelease:\n\tgit push\n")
    assert analyze("make", cwd=tmp_path)["kind"] == "git-remote"
    (tmp_path / "Makefile").write_text(
        "PKGS = a\nall: $(addprefix publish-,$(PKGS))\n\techo hi\npublish-a:\n\tgit push\n"
    )
    assert analyze("make", cwd=tmp_path)["kind"] == "git-remote"
    (tmp_path / "gradlew").write_text("#!/bin/sh\neval exec java\n")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "gradlew")
    git(tmp_path, "commit", "-qm", "wrapper")
    assert analyze("./gradlew publish", cwd=tmp_path)["kind"] == "publish"


@pytest.mark.parametrize(
    "command",
    [
        "./gradlew publishToMavenCentral",
        "./gradlew :lib:publish",
        "./gradlew clean build publish",
        "./mvnw -B -DskipTests deploy",
        "mvn clean install deploy",
        "mvn release:perform",
    ],
)
def test_build_tool_publishing_asks(tmp_path, command):
    (tmp_path / "gradlew").write_text("#!/bin/sh\neval exec java\n")
    (tmp_path / "mvnw").write_text("#!/bin/sh\neval exec java\n")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "gradlew", "mvnw")
    git(tmp_path, "commit", "-qm", "wrappers")
    assert analyze(command, cwd=tmp_path)["kind"] == "publish"


@pytest.mark.parametrize(
    ("makefile", "command", "asks"),
    [
        (
            "PKGS = a\nT = $(addprefix publish-,$(PKGS))\nrelease: $(T)\npublish-a:\n\tgit push\n",
            "make release",
            True,
        ),
        (".DEFAULT_GOAL := $(if $(X),a,b)\na:\n\techo a\nb:\n\tgit push\n", "make", True),
        ("test: $(wildcard *.py)\n\tpytest\nrelease:\n\tgit push\n", "make test", False),
    ],
)
def test_make_fifth_review_cases(tmp_path, makefile, command, asks):
    (tmp_path / "Makefile").write_text(makefile)
    assert (analyze(command, cwd=tmp_path)["kind"] in {"git-remote", "opaque"}) == asks


def test_cyclic_make_variables_stay_fast_and_ask(tmp_path):
    names = [f"V{i}" for i in range(12)]
    lines = [
        f"{n} = $({names[(i + 1) % 12]}) $({names[(i + 2) % 12]}) $({names[(i + 3) % 12]})"
        for i, n in enumerate(names)
    ]
    (tmp_path / "Makefile").write_text("\n".join(lines) + "\nall:\n\techo hi\nrelease: $(V0)\n\tgit push\n")
    started = time.perf_counter()
    assert analyze("make release", cwd=tmp_path)["kind"] in {"git-remote", "opaque"}
    assert time.perf_counter() - started < 2


@pytest.mark.parametrize(
    "makefile",
    [
        "PKGS = a\nall: $(PKGS:%=publish-%)\n\techo hi\npublish-a:\n\tgit push\n",
        "T = publish-a\nall: $T\n\techo hi\npublish-a:\n\tgit push\n",
        ".DEFAULT_GOAL := $(GOAL)\nall:\n\techo hi\nrelease:\n\tgit push\n",
    ],
)
def test_make_sixth_review_cases_ask(tmp_path, makefile):
    (tmp_path / "Makefile").write_text(makefile)
    assert analyze("make", cwd=tmp_path)["kind"] in {"git-remote", "opaque"}


@pytest.mark.parametrize(
    ("command", "publishes"),
    [
        ("mvn deploy:deploy-file -Dfile=x.jar", True),
        ("gradle publishToMavenLocal", False),
        ("gradle build -x publish", False),
        ("gradle tasks --group publishing", False),
        ("gradle help --task publish", False),
        ("mvn -pl deploy install", False),
    ],
)
def test_build_publishing_edges(command, publishes):
    assert (analyze(command)["kind"] == "publish") == publishes


@pytest.mark.parametrize(
    "command",
    [
        "mvn -B deploy",
        "mvn -X deploy",
        "mvn -C deploy",
        "mvn -c deploy",
        "gradle -s publish",
        "gradle -S publish",
        "gradle -t publish",
        "gradle tasks publish",
        "gradle help publish",
    ],
)
def test_build_flags_do_not_hide_publishing(command):
    assert analyze(command)["kind"] == "publish"


def test_layers_of_make_variables_stay_fast(tmp_path):
    lines = [f"L0_{i} = x{i}" for i in range(8)]
    for level in range(1, 9):
        refs = " ".join(f"$(L{level - 1}_{j})" for j in range(8))
        lines += [f"L{level}_{i} = {refs}" for i in range(8)]
    (tmp_path / "Makefile").write_text("\n".join(lines) + "\nall:\n\techo $(L8_0)\n")
    started = time.perf_counter()
    analyze("make", cwd=tmp_path)
    assert time.perf_counter() - started < 2


@pytest.mark.parametrize(
    ("makefile", "command", "asks"),
    [
        ("PKGS = a\nrelease: $(PKGS:%=publish-%)\n\techo hi\npublish-a:\n\tgit push\n", "make release", True),
        (
            "SRCS = a.c\nOBJS = $(SRCS:.c=.o)\nprog: $(OBJS)\n\t$(CC) -o prog $(OBJS)\ninstall:\n\tgit push\n",
            "make",
            False,
        ),
        ("all: $(CURDIR)/x\n\techo hi\ninstall:\n\tgit push\n", "make", False),
        ("all:\n\techo hi\n" + "# padding\n" * 12000 + "release:\n\tgit push\n", "make release", True),
    ],
    ids=["substitution-in-prerequisite", "c-objects", "curdir", "longer-than-readable"],
)
def test_make_seventh_review_cases(tmp_path, makefile, command, asks):
    (tmp_path / "Makefile").write_text(makefile)
    assert (analyze(command, cwd=tmp_path)["kind"] in {"git-remote", "opaque"}) == asks


def test_large_expanded_recipes_are_opaque_and_fast(tmp_path):
    recipes = "".join("\techo $(BIG)\n" for _ in range(800))
    (tmp_path / "Makefile").write_text("BIG = " + "x" * 90_000 + "\nall:\n" + recipes)
    started = time.perf_counter()
    assert analyze("make", cwd=tmp_path)["kind"] == "opaque"
    assert time.perf_counter() - started < 2


def test_substitution_with_variables_inside_is_expanded(tmp_path):
    (tmp_path / "Makefile").write_text(
        "A = publish\nPKGS = a\nall: $(PKGS:%=$(A)-%)\n\techo hi\npublish-a:\n\tgit push\n"
    )
    assert analyze("make", cwd=tmp_path)["kind"] == "git-remote"


def test_only_virtual_environment_activation_runs_unread(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/activate-deploy.sh").write_text(PUSH)
    assert analyze("source scripts/activate-deploy.sh", cwd=tmp_path)["kind"] == "git-remote"


def test_sourcing_from_home_stays_quiet(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".bashrc").write_text('eval "$(starship init bash)"\n')
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    for command in ("source ~/.bashrc", '. "$HOME/.bashrc"'):
        assert analyze(command, cwd=project_dir)["kind"] == "read-only"


def test_bun_publish_and_husky_hooks_ask(tmp_path):
    assert analyze("bun publish", cwd=tmp_path)["kind"] == "publish"
    init(tmp_path)
    output = handle(
        dict(cwd=str(tmp_path), tool_name="Write", tool_input=dict(file_path=".husky/pre-commit"))
    )
    assert output["hookSpecificOutput"]["permissionDecision"] == "ask"
