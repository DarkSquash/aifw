"""Risk-selected gates and process execution with explicit platform boundaries."""

import os
from functools import lru_cache
from pathlib import Path
import re
import shutil
import subprocess
import sys

from .common import AifwError, digest, file_state, human, now, read_yaml, require, validate, write_json
from .waiver import apply_waivers
from .workspace import build_workspace_map, load_manifest


@lru_cache(maxsize=None)
def real_interpreter(launcher):
    """The interpreter a `python` on PATH actually runs.

    Launchers such as the Python install manager's `bin\\python.exe` start the real interpreter
    themselves; under CREATE_NO_WINDOW they can hand it invalid standard handles (WinError 6),
    which broke gates at random. Asking the launcher once and calling the interpreter directly avoids it.
    """
    try:
        found = subprocess.run(
            [launcher, "-c", "import sys; print(sys.executable)"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return launcher
    return found if found and Path(found).is_file() else launcher


def run_command(executable, args, cwd=None, timeout=600):
    resolved = shutil.which(executable)
    # The Windows Store alias in WindowsApps is a launcher stub, not an interpreter.
    stub = resolved is not None and "windowsapps" in resolved.lower()
    if resolved is None or (stub and executable in {"python", "python3"}):
        resolved = sys.executable if executable in {"python", "python3"} else executable
    elif executable in {"python", "python3"}:
        resolved = real_interpreter(resolved)
    command = [resolved, *args]
    if os.name == "nt" and Path(resolved).suffix.lower() in {".cmd", ".bat"}:
        # cmd expands percent variables even inside quotes; reject shell-sensitive tokens.
        if any(re.search(r'["\r\n\x00%]', token) for token in [resolved, *args]):
            return dict(
                ok=False,
                stdout="",
                stderr="Windows batch gate arguments cannot contain quotes, newlines, NUL or percent expansion.",
            )
        command_line = " ".join(f'"{token}"' for token in [resolved, *args])
        command = f'"{os.environ.get("COMSPEC", "cmd.exe")}" /d /s /v:off /c "{command_line}"'
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return dict(ok=completed.returncode == 0, stdout=completed.stdout, stderr=completed.stderr)
    except (OSError, subprocess.TimeoutExpired) as error:
        return dict(ok=False, stdout="", stderr=str(error))


def evaluate_quality_gates(data):
    results = list(data["results"])
    present = {r["gateId"] for r in results}
    for gate_id in sorted(data["requiredGateIds"]):
        if gate_id not in present:
            results.append(
                dict(
                    gateId=gate_id,
                    enforcement="hard",
                    status="not-run",
                    summary="Required gate did not run",
                    evidence=[],
                )
            )
    approval = data.get("approval", {})
    valid_approval = str(approval.get("approvedBy", "")).startswith("human:") and re.fullmatch(
        r"[a-f0-9]{64}", approval.get("approvalDigest", "")
    )
    if data["change"]["humanApproval"] == "required" and not valid_approval:
        results.append(
            dict(
                gateId="human-approval",
                enforcement="human",
                status="not-run",
                summary=f"Valid human approval is required for {data['change']['level']}",
                evidence=[],
            )
        )
    blockers = sorted(
        [r for r in results if r["enforcement"] in {"hard", "human"} and r["status"] != "pass"],
        key=lambda r: r["gateId"],
    )
    warnings = sorted(
        [r for r in results if r["enforcement"] == "audit" and r["status"] != "pass"],
        key=lambda r: r["gateId"],
    )
    return dict(
        status="blocked" if blockers else "warning" if warnings else "pass",
        blockers=blockers,
        warnings=warnings,
        passed=sorted([r for r in results if r["status"] == "pass"], key=lambda r: r["gateId"]),
    )


def run_gate_set(gates, level, root, run=run_command, builtins=None):
    validate(gates, "quality-gates.schema.json")
    ids = [g["id"] for g in gates["gates"]]
    require(len(ids) == len(set(ids)), "Gate definition ids must be unique.", "POLICY_CONFLICT")
    results, builtins = [], builtins or {}
    root = Path(root).resolve()
    for gate in sorted([g for g in gates["gates"] if level in g["levels"]], key=lambda g: g["id"]):
        if gate["id"] in builtins:
            results.append(dict(builtins[gate["id"]], enforcement=gate["enforcement"]))
        elif "command" not in gate:
            results.append(
                dict(
                    gateId=gate["id"],
                    enforcement=gate["enforcement"],
                    status="not-run",
                    summary="No command is configured; set one for this gate in .aifw/gates.yaml.",
                    evidence=[],
                )
            )
        else:
            cwd = (root / gate.get("workingDirectory", ".")).resolve()
            require(
                cwd.is_relative_to(root),
                "Gate working directory escapes the project root.",
                "POLICY_CONFLICT",
            )
            output = run(gate["command"][0], gate["command"][1:], str(cwd))
            evidence = [
                f"{key}:{output[key].strip()[:2000]}" for key in ("stdout", "stderr") if output[key].strip()
            ]
            results.append(
                dict(
                    gateId=gate["id"],
                    enforcement=gate["enforcement"],
                    status="pass"
                    if output["ok"]
                    else "warning"
                    if gate["enforcement"] == "audit"
                    else "fail",
                    summary="Command passed." if output["ok"] else "Command failed.",
                    evidence=evidence,
                )
            )
    return results


def validate_workspace(root, level, run=run_command, approval=None, evidence=None):
    manifest = load_manifest(root)
    project_map = build_workspace_map(root)
    gates = read_yaml(Path(root) / ".aifw/gates.yaml")
    builtins = {
        "manifest": dict(
            gateId="manifest",
            enforcement="hard",
            status="pass",
            summary=f"Manifest {manifest['metadata']['id']} is valid and pinned.",
            evidence=["aifw.yaml"],
        ),
        "project-map": dict(
            gateId="project-map",
            enforcement="hard",
            status="pass" if project_map["current"] else "fail",
            summary="PROJECT_MAP is current." if project_map["current"] else "PROJECT_MAP is stale.",
            evidence=["PROJECT_MAP.md", "sha256:" + project_map["digest"]],
        ),
    }
    configured = {g["id"] for g in gates["gates"] if level in g["levels"]}
    for gate_id in configured & {"context-integrity", "instructions-integrity"}:
        from .context import check_context
        from .instructions import sync_instructions

        result = check_context(root) if gate_id == "context-integrity" else sync_instructions(root)
        builtins[gate_id] = dict(
            gateId=gate_id,
            enforcement="hard",
            status="pass" if result["status"] == "pass" else "fail",
            summary="Local documentation/instructions checked; semantic correctness is not certified.",
            evidence=[
                ".aifw/context-index.json"
                if gate_id == "context-integrity"
                else ".aifw/project-instructions.md"
            ],
        )
    builtins.update(evidence or {})
    if "independent-review" in configured and "independent-review" not in builtins:
        builtins["independent-review"] = pending_reviews(root)
    if approval:
        builtins["human-approval"] = dict(
            gateId="human-approval",
            enforcement="human",
            status="pass",
            summary=f"Approved by {approval['approvedBy']}.",
            evidence=[approval["approvalDigest"]],
        )
    data = dict(
        change=dict(
            level=level,
            humanApproval="required" if level == "L3" else "conditional" if level == "L2" else "none",
        ),
        requiredGateIds=[g["id"] for g in gates["gates"] if level in g["levels"]],
        results=apply_waivers(root, run_gate_set(gates, level, root, run, builtins)),
    )
    if approval:
        data["approval"] = approval
    return evaluate_quality_gates(data)


def inspect_gate_wiring(root, level):
    """Static references only: never infer successful execution or branch protection."""
    from .common import AifwError
    from .context import safe_path

    root = Path(root).resolve()

    def normalize(command):
        command = " ".join(command.split())
        command = re.sub(r"^uv run (?:(?:--no-sync|--locked|--frozen) )*", "", command)
        return re.sub(r"^python -m (ruff|pytest|aifw)\b", r"\1", command)

    config = validate(read_yaml(safe_path(root, ".aifw/gates.yaml")), "quality-gates.schema.json")
    workflows = []
    for name in sorted((root / ".github/workflows").glob("*")):
        if name.suffix not in {".yml", ".yaml"}:
            continue
        path = name.relative_to(root).as_posix()
        try:
            data = read_yaml(safe_path(root, path))
            require(isinstance(data, dict), "Workflow must be a mapping.")
            triggers = data.get("on", {})
            if isinstance(triggers, str):
                triggers = [triggers]
            automatic = (
                any(t in triggers for t in ("push", "pull_request", "pull_request_target", "merge_group"))
                if isinstance(triggers, (dict, list))
                else False
            )
            for job in data.get("jobs", {}).values():
                for step in job.get("steps", []):
                    if isinstance(step.get("run"), str):
                        workflows.append(
                            dict(
                                path=path,
                                automatic=automatic,
                                conditional="if" in job
                                or "if" in step
                                or bool(job.get("continue-on-error") or step.get("continue-on-error")),
                                lines=[normalize(line) for line in step["run"].splitlines()],
                            )
                        )
        except (AifwError, OSError, TypeError, AttributeError):
            workflows.append(dict(path=path, automatic=False, conditional=True, lines=[]))
    rows = []
    for gate in config["gates"]:
        if level not in gate["levels"]:
            continue
        builtin = gate["id"] in {"manifest", "project-map", "context-integrity", "instructions-integrity"}
        command = normalize(" ".join(gate.get("command", [])))
        validators = {
            f"{prefix} validate --level {level}{suffix}"
            for prefix in ("aifw", "python -m aifw")
            for suffix in ("", " --json")
        }
        matches = [
            w for w in workflows if (command and command in w["lines"]) or validators.intersection(w["lines"])
        ]
        state = (
            "automatic-reference"
            if any(w["automatic"] and not w["conditional"] for w in matches)
            else "conditional-reference"
            if any(w["automatic"] for w in matches)
            else "manual-only"
            if matches
            else "not-found"
        )
        rows.append(
            dict(
                id=gate["id"],
                configured=bool(command) or builtin,
                enforcement=gate["enforcement"],
                execution="not-run",
                ciStatus=state,
                ciFiles=sorted({w["path"] for w in matches}),
            )
        )
    return dict(
        status="pass"
        if rows and all(r["configured"] and r["ciStatus"] == "automatic-reference" for r in rows)
        else "warning",
        gates=rows,
        execution="not-run",
        branchProtection="not-verified",
        deploymentBlocking="not-verified",
        analysis="literal GitHub Actions command references only",
    )


def run_doctor(platform=None, run=run_command):
    platform = platform or sys.platform

    def check(result):
        return (
            dict(status="pass", version=result["stdout"].strip())
            if result["ok"]
            else dict(status="fail", detail=(result["stderr"] or result["stdout"]).strip())
        )

    checks = dict(
        python=check(run(sys.executable, ["--version"], timeout=15)),
        git=check(run("git", ["--version"], timeout=15)),
    )
    wsl = dict(applicable=platform == "win32", available=False, pythonAvailable=False)
    guidance = []
    if wsl["applicable"]:
        status = run("wsl.exe", ["--status"], timeout=15)
        if status["ok"]:
            wsl["available"] = True
            wsl["pythonAvailable"] = run("wsl.exe", ["--exec", "python3", "--version"], timeout=15)["ok"]
            if not wsl["pythonAvailable"]:
                wsl["reason"] = "python-missing"
            guidance.append(
                "Keep Windows and WSL virtual environments and caches separate; install dependencies inside each environment."
            )
        else:
            wsl["reason"] = (
                "access-denied"
                if re.search(r"E_ACCESSDENIED|access.+denied", status["stderr"], re.I)
                else "not-installed"
            )
    return dict(
        healthy=all(c["status"] == "pass" for c in checks.values()),
        primaryEnvironment={"win32": "windows", "linux": "linux", "darwin": "macos"}.get(platform, "other"),
        checks=checks,
        wsl=wsl,
        guidance=guidance,
    )


REVIEW_VERDICT = re.compile(
    r"^[\s>*_-]*resultado[*_]*\s*:[\s*_]*(aprovado com ressalvas|aprovado|reprovado)",
    re.IGNORECASE | re.MULTILINE,
)


def review_result(root, path):
    """The independent-review gate reads the reviewer's verdict, not only that the file exists."""
    match = REVIEW_VERDICT.search((Path(root) / path).read_text(encoding="utf-8"))
    verdict = match and match.group(1).lower()
    return dict(
        gateId="independent-review",
        status="pass" if verdict in {"aprovado", "aprovado com ressalvas"} else "fail",
        summary=f"Independent review: {verdict}."
        if verdict
        else "independent-review.md needs a line `Resultado: aprovado | aprovado com ressalvas | reprovado`.",
        evidence=[path],
    )


def pending_reviews(root):
    """Without a change id there is nothing to review; say which active changes still need `--change`."""
    active = sorted(
        read_yaml(file)["metadata"]["id"]
        for file in (Path(root) / ".aifw/changes/active").glob("*/change.yaml")
        if read_yaml(file).get("metadata", {}).get("level") in {"L2", "L3"}
    )
    return dict(
        gateId="independent-review",
        status="not-run" if active else "pass",
        summary="Review is checked per change: run `aifw validate --change <id>` for " + ", ".join(active)
        if active
        else "No active L2/L3 change needs an independent review.",
        evidence=[],
    )


def validate_change_workspace(root, change_id, write=False, run=run_command):
    """Validate a spec change: its level's gates, approval and required artifacts, optionally recorded."""
    from . import specs

    change = specs.load_change(root, change_id)
    level, approval = change["metadata"]["level"], None
    if change.get("approval"):
        try:
            human(change["approval"].get("approvedBy"))
            require(file_state(root, change["approval"].get("record")) == "valid", "Missing approval record.")
            approval = dict(
                approvedBy=change["approval"]["approvedBy"], approvalDigest=digest(change["approval"])
            )
        except AifwError:
            approval = None
    missing = specs.missing_artifacts(root, change_id)
    review = {}
    if level in specs.LEVEL_ARTIFACTS and "independent-review" not in [m["artifact"] for m in missing]:
        path = (specs.change_dir(root, change_id) / "independent-review.md").relative_to(root).as_posix()
        review["independent-review"] = review_result(root, path)
    report = validate_workspace(root, level, run, approval, review)
    report["blockers"] = report["blockers"] + [
        dict(
            gateId=f"artifact:{m['artifact']}",
            enforcement="hard",
            status="fail",
            summary=f"Required {level} artifact is missing or empty.",
            evidence=[m["path"]],
        )
        for m in missing
    ]
    if missing:
        report["status"] = "blocked"
    report.update(
        changeId=change_id,
        missingArtifacts=missing,
        validatedAt=now(),
        inputs=specs.validation_inputs(root, change_id),
    )
    if write:
        write_json(specs.change_dir(root, change_id) / specs.VALIDATION_REPORT, report)
    return report
