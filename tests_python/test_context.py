"""Context contracts using synthetic projects only; never contact external services."""

import json

from aifw.cli import create_parser, execute
from aifw.discovery import discover_project
from aifw.gates import evaluate_quality_gates
from aifw.common import AifwError
import pytest


def put(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def run(root, *args):
    return execute(create_parser().parse_args(args), root)


def test_conventional_adrs_and_templates(tmp_path):
    for name in [
        "docs/decisions/001-auth.md",
        "docs/decisions/README.md",
        "docs/decisions/_template.md",
        "docs/adr/002-api.md",
        "docs/adr-003-cache.md",
    ]:
        put(tmp_path, name, "# Decision")
    assert discover_project(tmp_path)["adrFiles"] == [
        "docs/adr-003-cache.md",
        "docs/adr/002-api.md",
        "docs/decisions/001-auth.md",
    ]


def test_context_selection_keeps_dependency_closure_over_budget(tmp_path):
    put(
        tmp_path,
        "docs/features/login.md",
        "---\nscope: login authentication\ndepends-on: schemas/auth.md\nintents: [bugfix]\nsources: [src/auth.ts]\ntokens: 1\n---\n"
        + "details " * 100,
    )
    put(tmp_path, "docs/schemas/auth.md", "---\ndepends-on: ../decisions/001-auth.md\n---\n# Schema")
    put(tmp_path, "docs/decisions/001-auth.md", "# ADR")
    put(tmp_path, "docs/features/billing.md", "# Billing")
    put(tmp_path, "src/auth.ts", "export const auth = true")
    before = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file())
    value, code = run(
        tmp_path,
        "context",
        "select",
        "--task",
        "login",
        "--intent",
        "bugfix",
        "--files",
        "src/auth.ts",
        "--budget",
        "10",
    )
    assert code == 2 and value["overBudget"]
    assert {d["path"] for d in value["selected"]} == {
        "docs/features/login.md",
        "docs/schemas/auth.md",
        "docs/decisions/001-auth.md",
    }
    assert value["estimatedTokens"] > 100
    assert value["tokenEstimateMethod"] == "characters/4-ceiling"
    assert sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*") if p.is_file()) == before


def test_context_freshness_and_broken_references(tmp_path):
    put(
        tmp_path,
        "docs/login.md",
        "---\nsources: [src/auth.ts]\n---\n[Guide](guide.md)\n`src/missing.ts`\n[Website](https://example.com)\n```ts\nconst demo = 'fake/missing.ts'\n```\n",
    )
    put(tmp_path, "src/auth.ts", "v1")
    value, code = run(tmp_path, "context", "check")
    assert code == 2
    assert {f["code"] for f in value["findings"]} == {"BROKEN_REFERENCE"}
    assert len(value["findings"]) == 2
    put(tmp_path, "docs/guide.md", "# Guide")
    put(tmp_path, "src/missing.ts", "ok")
    run(tmp_path, "context", "index", "--write")
    assert run(tmp_path, "context", "check")[1] == 0
    put(tmp_path, "src/auth.ts", "v2")
    value, code = run(tmp_path, "context", "check")
    assert code == 2
    assert "SOURCE_CHANGED" in {f["code"] for f in value["findings"]}
    assert value["semanticValidation"] == "not-performed"


def test_private_files_traversal_and_malformed_metadata_do_not_leak(tmp_path):
    secret = "private-fixture-value-do-not-output"
    put(tmp_path, ".env", secret)
    put(tmp_path, "docs/private.md", "---\nsources: [../.env, ../../outside.txt]\n---\n[secret](../.env)\n")
    put(tmp_path, "docs/bad.md", f"---\nscope: [unterminated {secret}\n---\n")
    value, code = run(tmp_path, "context", "index")
    assert code == 2
    assert secret not in json.dumps(value)
    assert {f["code"] for f in value["findings"]} >= {"RESTRICTED_REFERENCE", "INVALID_METADATA"}
    with pytest.raises(AifwError):
        run(tmp_path, "context", "select", "--task", "login", "--budget", "0")


def test_dependency_cycle_terminates_and_missing_dependency_blocks(tmp_path):
    put(tmp_path, "docs/a.md", "---\nscope: login\ndepends-on: b.md\n---\nA")
    put(tmp_path, "docs/b.md", "---\ndepends-on: [a.md, missing.md]\n---\nB")
    value, code = run(tmp_path, "context", "select", "--task", "login")
    assert code == 2 and value["status"] == "blocked"
    assert len(value["selected"]) == 2


def test_instruction_blocks_preserve_user_text_and_detect_drift(tmp_path):
    put(tmp_path, ".aifw/project-instructions.md", "# Project rules\nUse existing conventions.\n")
    original = b"# Universal\r\nShort answers.\r\n"
    (tmp_path / "AGENTS.md").write_bytes(original)
    value, code = run(tmp_path, "instructions", "build", "--agent", "all")
    assert code == 0
    assert (tmp_path / "AGENTS.md").read_bytes().startswith(original)
    assert (tmp_path / "CLAUDE.md").is_file()
    before = (tmp_path / "AGENTS.md").read_bytes()
    run(tmp_path, "instructions", "build", "--agent", "all")
    assert (tmp_path / "AGENTS.md").read_bytes() == before
    put(tmp_path, ".aifw/project-instructions.md", "# New rules\n")
    assert run(tmp_path, "instructions", "check", "--agent", "all")[1] == 2
    put(tmp_path, "CLAUDE.md", "<!-- aifw:instructions:start -->\ncorrupt")
    with pytest.raises(AifwError):
        run(tmp_path, "instructions", "build", "--agent", "all")
    assert (tmp_path / "AGENTS.md").read_bytes() == before


def test_instruction_source_cannot_be_secret_or_generated_target(tmp_path):
    for source in [".env", "../outside.md", "AGENTS.md"]:
        with pytest.raises(AifwError):
            run(tmp_path, "instructions", "build", "--source", source)


def test_ci_inspection_does_not_claim_execution(tmp_path):
    put(
        tmp_path,
        ".aifw/gates.yaml",
        "apiVersion: aifw.dev/v1alpha1\nkind: QualityGateSet\nphilosophy: progressive-by-risk\ngates:\n- id: tests\n  enforcement: hard\n  levels: [L1]\n  command: [python, -m, pytest, -q]\n- id: review\n  enforcement: audit\n  levels: [L1]\n",
    )
    put(
        tmp_path,
        ".github/workflows/tests.yml",
        "on: workflow_dispatch\njobs:\n  tests:\n    runs-on: ubuntu-latest\n    steps:\n    - run: python -m pytest -q\n",
    )
    value, code = run(tmp_path, "gates", "check", "--level", "L1")
    assert code == 2
    row = next(g for g in value["gates"] if g["id"] == "tests")
    assert row["execution"] == "not-run" and row["ciStatus"] == "manual-only"
    assert next(g for g in value["gates"] if g["id"] == "review")["configured"] is False


def test_missing_hard_gate_never_passes():
    value = evaluate_quality_gates(
        dict(change={"level": "L1", "humanApproval": "none"}, requiredGateIds=["tests"], results=[])
    )
    assert value["status"] == "blocked"
    assert value["blockers"][0]["status"] == "not-run"


def test_directory_links_external_metadata_and_invalid_selection(tmp_path):
    put(tmp_path, "docs/login.md", "[Directory](../src/)\n")
    put(tmp_path, "src/auth.ts", "ok")
    assert run(tmp_path, "context", "check")[1] == 0
    put(tmp_path, "docs/login.md", "---\nsources: [https://example.com/private]\n---\n")
    assert run(tmp_path, "context", "check")[1] == 2
    put(tmp_path, "docs/login.md", "---\nrequired: yes-not-a-boolean\n---\n")
    value, code = run(tmp_path, "context", "select", "--task", "login")
    assert code == 2 and value["status"] == "blocked"


def test_instruction_failed_write_restores_both_files(tmp_path, monkeypatch):
    from pathlib import Path

    put(tmp_path, ".aifw/project-instructions.md", "# Project rules")
    put(tmp_path, "AGENTS.md", "# Universal")
    put(tmp_path, "CLAUDE.md", "# Existing")
    original = Path.write_bytes
    calls = []

    def fail_once(path, data):
        if path.name == "CLAUDE.md" and not calls:
            calls.append(path)
            original(path, b"partial")
            raise OSError("Simulated disk failure")
        return original(path, data)

    monkeypatch.setattr(Path, "write_bytes", fail_once)
    with pytest.raises(OSError):
        run(tmp_path, "instructions", "build")
    assert (tmp_path / "AGENTS.md").read_text() == "# Universal"
    assert (tmp_path / "CLAUDE.md").read_text() == "# Existing"


def test_ci_conditional_false_is_not_automatic_evidence(tmp_path):
    put(
        tmp_path,
        ".aifw/gates.yaml",
        "apiVersion: aifw.dev/v1alpha1\nkind: QualityGateSet\nphilosophy: progressive-by-risk\ngates:\n- id: tests\n  enforcement: hard\n  levels: [L1]\n  command: [python, -m, pytest]\n",
    )
    put(
        tmp_path,
        ".github/workflows/test.yml",
        "on: push\njobs:\n  test:\n    if: false\n    steps:\n    - run: python -m pytest\n",
    )
    value, code = run(tmp_path, "gates", "check", "--level", "L1")
    assert code == 2
    assert value["gates"][0]["ciStatus"] == "conditional-reference"


@pytest.mark.parametrize("status", ["skipped", "warning", "unknown"])
def test_unproven_hard_gate_blocks(status):
    value = evaluate_quality_gates(
        dict(
            change={"level": "L1", "humanApproval": "none"},
            requiredGateIds=["tests"],
            results=[
                dict(gateId="tests", enforcement="hard", status=status, summary="Not verified", evidence=[])
            ],
        )
    )
    assert value["status"] == "blocked"


def test_symlinked_source_is_rejected_without_reading(tmp_path):
    outside = put(tmp_path, "private.txt", "PRIVATE")
    link = tmp_path / "docs/link.md"
    link.parent.mkdir()
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("Host does not allow symlink creation")
    put(tmp_path, "docs/auth.md", "---\nsources: [link.md]\n---\n# Auth")
    value, code = run(tmp_path, "context", "index")
    assert code == 2 and "PRIVATE" not in json.dumps(value)


def test_builtin_context_gate_reports_real_broken_links(tmp_path):
    from aifw import workspace, gates
    from aifw.common import write_yaml, API

    workspace.initialize_project(
        tmp_path,
        dict(
            id="sample",
            name="Sample",
            projectType="new",
            locale="pt-BR",
            primaryEnvironment="windows",
            validationTargets=["windows"],
            profiles=[],
        ),
    )
    write_yaml(
        tmp_path / ".aifw/gates.yaml",
        dict(
            apiVersion=API,
            kind="QualityGateSet",
            philosophy="progressive-by-risk",
            gates=[dict(id="context-integrity", enforcement="hard", levels=["L1"])],
        ),
    )
    put(tmp_path, "docs/test.md", "[Missing](missing.md)")
    value = gates.validate_workspace(tmp_path, "L1")
    assert value["status"] == "blocked"
    assert value["blockers"][0]["gateId"] == "context-integrity"


def test_ci_recognizes_literal_uv_runner_but_not_echo(tmp_path):
    put(
        tmp_path,
        ".aifw/gates.yaml",
        "apiVersion: aifw.dev/v1alpha1\nkind: QualityGateSet\nphilosophy: progressive-by-risk\ngates:\n- id: tests\n  enforcement: hard\n  levels: [L1]\n  command: [python, -m, pytest, -q]\n",
    )
    workflow = ".github/workflows/test.yml"
    put(
        tmp_path,
        workflow,
        "on: pull_request\njobs:\n  test:\n    steps:\n    - run: uv run --no-sync python -m pytest -q\n",
    )
    value, code = run(tmp_path, "gates", "check", "--level", "L1")
    assert code == 0 and value["gates"][0]["execution"] == "not-run"
    put(
        tmp_path,
        workflow,
        "on: pull_request\njobs:\n  test:\n    steps:\n    - run: echo python -m pytest -q\n",
    )
    assert run(tmp_path, "gates", "check", "--level", "L1")[1] == 2


def test_existing_document_title_is_searchable_without_metadata(tmp_path):
    put(tmp_path, "docs/authentication.md", "# Autenticação e sessão\n\nExisting documentation.")
    value, code = run(tmp_path, "context", "select", "--task", "corrigir sessão")
    assert code == 0
    assert value["selected"][0]["path"] == "docs/authentication.md"
