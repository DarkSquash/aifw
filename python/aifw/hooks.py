"""Claude Code hooks for AIFW projects.

PreToolUse enforces the permission policy, open impasses and control files; it never
auto-approves, so Claude Code's own permission rules still apply. PostToolUse records the
session log, Stop blocks unverified code changes and SessionStart injects project state.
Outside an AIFW project every event is a no-op.
"""

from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess
import sys
import time

from . import signing
from .common import now, read_yaml
from .impasse import case_file, load_cases, mutation_allowed
from .permissions import decide_action, load_permission_policy, validate_break_glass
from .shell import SECRET_FILE, analyze, domains_for, runs_tests, service_of, verification_visible

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
RUN_RETENTION_DAYS = 30
SHELL_TOOLS = {"Bash", "PowerShell"}

# Files that govern AIFW itself: editing them could loosen the checks applied to the agent.
CONTROL = (
    "aifw.yaml",
    ".aifw/charter.yaml",
    ".aifw/waivers/",
    ".aifw/break-glass/",
    ".aifw/runs/",
    ".aifw/permissions.yaml",
    ".aifw/routing.yaml",
    ".aifw/gates.yaml",
    ".aifw/project-rules.yaml",
    ".aifw/framework.lock.yaml",
    ".aifw/effective-policy.json",
    ".aifw/adoption/status.yaml",
    ".aifw/impasses/",
    ".aifw/decisions/",
    ".aifw/specs/current/",
    "evidence/validation.json",
    "policies/",
    ".claude/settings.json",
    ".claude/settings.local.json",
    ".claude/skills/aifw-workflow/",
    ".aifw/assessments/",
    # git runs code from here by itself (hooks, aliases and helpers from config), unread by the hook.
    ".git/",
    ".husky/",  # husky points core.hooksPath here: git runs these hooks on commit
    ".aifw/assessor.yaml",  # the person's activation of the task assessor (ADR-0036)
)
# Installed tools the hook runs without reading (ADR-0034): editing them with the edit tools asks.
# Shell commands are not checked: `.venv/bin/ruff format .` names the folder without changing it.
INSTALLED = re.compile(r"(^|[\s'\"=:/])(\.venv|node_modules|\.tox)/")


def find_root(cwd):
    for folder in [Path(cwd), *Path(cwd).parents]:
        if (folder / "aifw.yaml").is_file():
            return folder
    return None


def control_target(root, tool_name, tool_input, mutation, protected=()):
    """The AIFW control file this call would change, if any."""
    if tool_name in EDIT_TOOLS:
        target = Path(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
        target = (target if target.is_absolute() else Path(root) / target).resolve()
        if not target.is_relative_to(Path(root).resolve()):
            # Claude Code settings anywhere (the global one too) can disable every hook.
            settings = target.parent.name == ".claude" and target.name.startswith("settings")
            return f"{target.parent.name}/{target.name}" if settings else None
        # Lowercase: Windows and macOS file systems ignore case, so .GIT/hooks is .git/hooks.
        text = target.relative_to(Path(root).resolve()).as_posix().lower()
        matches = [
            c
            for c in (*CONTROL, *protected)
            if text == c.lower() or text.startswith(c.lower()) or text.endswith("/" + c.lower())
        ]
        if "/.git/" in "/" + text:
            matches.append(".git/")  # a nested repository or a submodule
        if text.startswith(".aifw/changes/") and text.endswith("/change.yaml"):
            matches.append("change.yaml")  # holds the spec approval
        if INSTALLED.search(text):
            matches.append(INSTALLED.search(text).group(2) + "/")
    elif tool_name in SHELL_TOOLS and mutation:
        text = tool_input.get("command", "").replace("\\", "/").lower()
        controls = (*CONTROL, *protected, "change.yaml", ".claude/settings")
        matches = [c for c in controls if c.lower() in text]
    else:
        return None
    return matches[0] if matches else None


def classify(tool_name, tool_input, allowlist, cwd=None):
    """Translate a Claude Code tool call into an AIFW action request."""
    if tool_name in EDIT_TOOLS:
        return dict(kind="filesystem-write", destructive=False, mutation=True)
    if tool_name == "WebFetch":
        return dict(
            kind="external-read", service=service_of(tool_input.get("url"), allowlist), mutation=False
        )
    if tool_name.startswith("mcp__"):
        return dict(kind="mcp", server=tool_name.split("__")[1], mutation=False)
    if tool_name in {"Agent", "Task"}:
        return dict(
            kind="delegation",
            model=tool_input.get("model"),
            agent=tool_input.get("subagent_type"),
            remote=tool_input.get("isolation") == "remote",
            mutation=False,
        )
    if tool_name == "WebSearch":
        return dict(kind="external-read", service="web-search", mutation=False)
    if tool_name in {"Read", "Grep", "Glob"}:
        targets = [tool_input.get(k) or "" for k in ("file_path", "path", "glob", "pattern")]
        secret = tool_name != "Grep" or tool_input.get("path") or tool_input.get("glob")
        if secret and any(
            SECRET_FILE.search(t.replace("*", "x")) for t in targets[: 4 if tool_name == "Glob" else 3]
        ):
            return dict(kind="secret-read", mutation=False)
        return dict(kind="read-only", mutation=False)
    if tool_name not in SHELL_TOOLS:
        return dict(kind="read-only", mutation=False)
    return analyze(tool_input.get("command", ""), allowlist, cwd=cwd)


def project_settings(root):
    """Manifest fields the hook enforces: the single external allowlist and the data classification."""
    spec = read_yaml(Path(root) / "aifw.yaml")["spec"]
    return spec.get("externalAllowlist", []), spec.get("dataClassification", "internal")


def service_domains(policy, allowlist):
    custom = policy.get("serviceDomains", {})
    return {name: custom.get(name) or domains_for([name])[name] for name in allowlist}


def active_levels(root):
    return {
        read_yaml(f).get("metadata", {}).get("level")
        for f in (Path(root) / ".aifw/changes/active").glob("*/change.yaml")
    }


def active_grants(root, policy):
    """Action kinds covered by a valid, unexpired break-glass grant."""
    if not policy.get("breakGlass", {}).get("enabled"):
        return set()
    kinds = {}
    for file in (Path(root) / ".aifw/break-glass").glob("*.yaml"):
        grant = read_yaml(file)
        if signing.approved(root, file):
            kinds.update({s: file for s in grant.get("scope", []) if validate_break_glass(grant, s)["valid"]})
    return kinds


def log_break_glass(file, kind, tool_name, tool_input):
    """Audit trail for every action a break-glass grant lets through."""
    from .context import redact

    detail = redact(str(tool_input.get("command") or tool_input.get("file_path") or ""))[:300]
    entry = dict(at=now(), kind=kind, tool=tool_name, detail=detail)
    with file.with_suffix(".log").open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + "\n")


def agent_model(root, name):
    """The model a custom subagent definition names, from the project's or the user's .claude/agents."""
    if not name or not re.fullmatch(r"[\w.-]+", name):
        return None
    for folder in (Path(root) / ".claude/agents", Path.home() / ".claude/agents"):
        file = folder / f"{name}.md"
        if file.is_file():
            match = re.search(r"^model:\s*['\"]?([\w.-]+)", file.read_text(encoding="utf-8")[:4000], re.M)
            return match and match.group(1)
    return None


def item_findings(root, policy, item, allowlist, classification, tool_name="", tool_input=None):
    """Policy findings for one action of a tool call."""
    kind, findings = item["kind"], []
    if kind == "opaque":
        if policy.get("opaqueCode", "ask") == "allow":
            return findings  # the project accepts code the hook cannot read (ADR-0025)
        findings.append(
            (
                "ask",
                "runs code the hook cannot read (eval, inline code, aliases or piped into a shell);"
                " write it to a .py or .js file and run that file so the hook can read it",
            )
        )
    elif kind == "secret-read":
        findings.append(("ask", "reads files or variables that usually hold secrets"))
    elif kind == "signing":
        findings.append(("ask", "signs a commit; signed commits are the proof of human approval"))
    elif kind == "install" and item.get("package") in policy.get("trustedPackages", []):
        pass  # a package the project chose to run without asking, such as ctx7
    elif kind == "install":
        findings.append(
            ("ask", "installs a package, program or new project; installs need the person's approval")
        )
    elif kind == "commit":
        allowed = policy.get("commits", "ask") == "allow" and not item.get("mixed")
        control = dirty_control(root) if allowed else None
        if control is None:
            findings.append(("ask", "creates or rewrites a commit; the person reviews every commit"))
        elif control:
            # A commit carrying a control file can turn into an approval once signed.
            findings.append(("ask", f"commits with the AIFW control file {control} changed"))
    elif kind == "mcp":
        servers = policy.get("mcpServers", {})
        if item["server"] in servers.get("deny", []):
            findings.append(("deny", f"MCP server {item['server']} is denied by the policy"))
        elif item["server"] in servers.get("ask", []):
            findings.append(("ask", f"MCP server {item['server']} requires confirmation"))
    elif kind == "delegation":
        risky = active_levels(root) & {"L3"}
        model = item.get("model") or agent_model(root, item.get("agent")) or ""
        if "haiku" in model and risky:
            # The model table never runs L3 work on haiku; on L2 it is the agent's call (ADR-0030).
            findings.append(("ask", f"delegates to haiku while an active {max(risky)} change exists"))
        elif "haiku" in model:
            from .assessment import PLANNED_PATHS, active, last_path

            path = last_path(root, item.get("session")) if active(root) else None
            if path in PLANNED_PATHS:
                # In active mode the assessor's path sets the model table (ADR-0036).
                findings.append(("ask", f"delegates to haiku on a request the task assessor routed {path}"))
        if item.get("remote"):
            # Subagents on this machine inherit these hooks; a cloud session runs outside them.
            findings.append(("ask", "delegates to a cloud session, outside this machine's AIFW hooks"))
    else:
        decision = decide_action(item, policy, allowlist)
        grants = active_grants(root, policy) if decision["decision"] != "allow" else {}
        if kind in grants:
            log_break_glass(grants[kind], kind, tool_name, tool_input or {})
            decision = dict(decision="allow", reason="break-glass")
        # Outside the allowlist, a person confirms external reads and writes; sensitive data is denied.
        outside = kind in {"external-read", "external-write"} and decision["decision"] == "deny"
        if outside and classification in {"confidential", "restricted"}:
            findings.append(("deny", f"{decision['reason']} ({classification} data)"))
        elif kind == "external-write" and classification == "restricted":
            findings.append(("deny", "external writes are denied for restricted data"))
        elif decision["decision"] == "deny":
            # External reads outside the allowlist are confirmed by the human instead of silently blocked.
            findings.append(("ask" if outside else "deny", decision["reason"]))
        elif decision["decision"] == "require-approval":
            findings.append(("ask", decision["reason"]))
    return findings


def evaluate(root, tool_name, tool_input, cwd=None, session=None):
    """Return ("deny"|"ask", reasons) or None when AIFW has no objection."""
    policy = load_permission_policy(root)
    allowlist, classification = project_settings(root)
    request = classify(tool_name, tool_input, service_domains(policy, allowlist), cwd or root)
    findings = []
    for case in load_cases(root):
        if case.get("humanDecision") and not signing.approved(root, case_file(root, case["id"])):
            case = dict(case, state="HUMAN_REVIEW")  # an unsigned decision does not release the freeze
        if request["mutation"] and not mutation_allowed(case, request.get("destructive", False)):
            # Shell text is classified heuristically, so a frozen case asks instead of denying it.
            soft = case["state"] in {"OPEN", "HUMAN_REVIEW"} and tool_name in SHELL_TOOLS
            findings.append(
                (
                    "ask" if soft and not request.get("destructive") else "deny",
                    f"impasse {case['id']} is {case['state']}; see `aifw impasse status`",
                )
            )
    items = request.get("requests", [request])
    # The control-file check reads git status before the command runs, so a commit beside other writes asks.
    mixed = any(i["kind"] not in {"commit", "git-local", "read-only", "signing"} for i in items)
    for item in items:
        item = dict(item, mixed=True) if mixed and item["kind"] == "commit" else item
        item = dict(item, session=session) if item["kind"] == "delegation" else item
        findings += item_findings(root, policy, item, allowlist, classification, tool_name, tool_input)
    control = control_target(
        root, tool_name, tool_input, request["mutation"], policy.get("protectedPaths", [])
    )
    if control:
        findings.append(("ask", f"changes the AIFW control file {control}"))
    if request.get("approval"):
        findings.append(
            (
                "deny",
                "approvals must be run by the person approving, in their own terminal (the CLI refuses the agent shell)",
            )
        )
    if not findings:
        return None
    level = "deny" if any(level == "deny" for level, _ in findings) else "ask"
    return level, [reason for _, reason in findings]


def pre_tool_use(root, payload):
    try:
        result = evaluate(
            root,
            payload.get("tool_name", ""),
            payload.get("tool_input") or {},
            payload.get("cwd"),
            payload.get("session_id"),
        )
    except Exception as error:  # noqa: BLE001 - a broken policy must reach the human, not pass silently
        result = "ask", [f"AIFW hook could not evaluate the policy: {error}"]
    if result is None:
        return None
    level, reasons = result
    try:  # which actions still reach the person, to find prompts worth removing
        detail = payload.get("tool_input") or {}
        target = str(detail.get("command") or detail.get("file_path") or "")
        append(
            root, payload, dict(at=now(), tool="Ask", decision=level, reasons=reasons, target=target[:2000])
        )
    except Exception:  # noqa: BLE001 - logging never changes the decision
        pass
    return dict(
        hookSpecificOutput=dict(
            hookEventName="PreToolUse",
            permissionDecision=level,
            permissionDecisionReason="AIFW: " + "; ".join(reasons),
        )
    )


def run_log(root, payload):
    session = re.sub(r"[^A-Za-z0-9_-]", "", str(payload.get("session_id") or ""))[:80] or "unknown"
    return Path(root) / ".aifw/runs" / f"{session}.jsonl"


def failed(payload):
    if payload.get("hook_event_name") == "PostToolUseFailure":
        return True
    response = payload.get("tool_response")
    if isinstance(response, dict):
        code = next((response[k] for k in ("exit_code", "exitCode", "returnCode") if k in response), 0)
        return bool(code) or bool(response.get("interrupted"))
    return False


def record(root, payload):
    """Append the tool call to the session log; it feeds the Stop check, impasse hints and `aifw runs`."""
    from .context import redact

    tool, tool_input = payload.get("tool_name", ""), payload.get("tool_input") or {}
    entry = dict(at=now(), tool=tool, ok=not failed(payload))
    if tool in SHELL_TOOLS:
        raw = tool_input.get("command", "")
        command = redact(raw)[:300]
        entry.update(command=command, verification=runs_tests(raw))
        if entry["verification"] and entry["ok"] and not verification_visible(raw):
            entry.update(ok=None, masked=True)
        if entry["verification"] and entry["ok"]:
            entry["tree"] = tree_state(root)
    elif tool in EDIT_TOOLS:
        path = Path(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
        path = (path if path.is_absolute() else Path(root) / path).resolve()
        inside = path.is_relative_to(Path(root).resolve())
        entry["file"] = path.relative_to(Path(root).resolve()).as_posix() if inside else "<outside project>"
    return append(root, payload, entry)


def append(root, payload, entry):
    log = run_log(root, payload)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def dirty_control(root):
    """The first changed, staged or untracked control file, "" when there is none, None without git."""
    try:
        listed = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=root,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    for control in (*CONTROL, "/change.yaml"):
        # Session and assessment logs are written by the hook itself and never hold an approval.
        if control in listed and control not in {".aifw/runs/", ".aifw/assessments/"}:
            return control
    return ""


def tree_state(root):
    """Content hash of every changed or untracked file, from git; None without git."""
    try:
        listed = subprocess.run(
            ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
            cwd=root,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=True,
        ).stdout.decode("utf-8", "replace")
    except (OSError, subprocess.CalledProcessError):
        return None
    paths = {item[3:] for item in listed.split("\0") if len(item) > 3 and item[2] == " "}
    state = {}
    for path in sorted(p for p in paths if not p.startswith(".aifw/")):
        state[path] = file_hash(root, path)
    return state


def file_hash(root, path):
    file = Path(root) / path
    return sha256(file.read_bytes()).hexdigest() if file.is_file() else "absent"


def read_log(file):
    if not file.is_file():
        return []
    return [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines() if line.strip()]


def code_path(file):
    return (
        bool(file)
        and not file.startswith(("docs/", ".aifw/", "<"))
        and not file.endswith((".md", ".txt", ".rst"))
    )


def code_edit(entry):
    return code_path(entry.get("file", ""))


def unverified_edits(entries):
    """Code files edited after the last successful verification command."""
    last_ok = max((i for i, e in enumerate(entries) if e.get("verification") and e.get("ok")), default=-1)
    return sorted({e["file"] for e in entries[last_ok + 1 :] if code_edit(e)})


def streak(entries, command):
    """Failures of this command since it last passed: a fix that works resets the count."""
    count = 0
    for e in entries:
        if e.get("command") == command and e.get("ok") is not None:
            count = 0 if e["ok"] else count + 1
    return count


def post_tool_use(root, payload):
    entry = record(root, payload)
    if entry["ok"] is not False or not entry.get("verification"):
        return None
    failures = streak(read_log(run_log(root, payload)), entry["command"])
    if failures < 2 or any(c["state"] != "RESOLVED" for c in load_cases(root)):
        return None
    return dict(
        hookSpecificOutput=dict(
            hookEventName=payload.get("hook_event_name", "PostToolUse"),
            additionalContext=(
                f"AIFW: `{entry['command']}` failed {failures} times in a row. "
                "Before another fix, open an impasse case with `aifw impasse open --id <slug> --impact <level>` "
                "and record each distinct attempt with `aifw impasse attempt`."
            ),
        )
    )


def stop(root, payload):
    entries = read_log(run_log(root, payload))
    baseline = next((e["tree"] for e in reversed(entries) if e.get("tree") is not None), None)
    current = tree_state(root) if baseline is not None else None
    if current is not None:
        # git sees edits made by any route: Edit, scripts, sed -i, generators.
        # Compare content, not membership: a commit cleans files without changing them.
        pending = sorted(
            p
            for p in set(baseline) | set(current)
            if code_path(p) and (p not in baseline or baseline[p] != file_hash(root, p))
        )

    else:
        pending = unverified_edits(entries)
    if not pending:
        return None
    if payload.get("stop_hook_active"):
        # Claude Code lets a second stop through; the record makes `aifw runs show` report it.
        append(root, payload, dict(at=now(), tool="Stop", unverified=pending[:20]))
        return None
    masked = any(e.get("masked") for e in entries)
    return dict(
        decision="block",
        reason=(
            "AIFW: code changed after the last successful verification ("
            + ", ".join(pending[:5])
            + "). Run the tests or `aifw validate` before concluding, or state explicitly why they do not apply."
            + (
                " A test command ending in | ; || or & hides its exit status; run it on its own or with && only."
                if masked
                else ""
            )
        ),
    )


def session_start(root, payload):
    from .intake import assess_intake

    runs = Path(root) / ".aifw/runs"
    for old in runs.glob("*.jsonl"):
        if time.time() - old.stat().st_mtime > RUN_RETENTION_DAYS * 86400:
            old.unlink()
    append(root, payload, dict(at=now(), tool="SessionStart", tree=tree_state(root)))
    lines = ["AIFW is enabled in this project; follow the aifw-workflow skill."]
    if not assess_intake(root)["complete"]:
        lines.append("Intake is incomplete: run `aifw intake status`.")
    lines += [f"Impasse {c['id']} is {c['state']}." for c in load_cases(root) if c["state"] != "RESOLVED"]
    from .assessment import pending_notices

    lines += pending_notices(root)
    for file in sorted((Path(root) / ".aifw/changes/active").glob("*/change.yaml")):
        change = read_yaml(file)
        meta = change.get("metadata", {})
        lines.append(f"Active change {meta.get('id')} ({meta.get('level')}, {change.get('status')}).")
    return dict(hookSpecificOutput=dict(hookEventName="SessionStart", additionalContext="\n".join(lines)))


def user_prompt(root, payload):
    """Assess each request as the person sends it.

    In shadow mode the hook runs in the background and only records. Once the person activated the
    assessor (ADR-0036), it runs before the request and hands the agent the execution path; a
    failure only says so, and the request goes on as usual.
    """
    from .assessment import active, assess, enabled, is_request, path_context
    from .context import redact

    prompt = (payload.get("prompt") or "").strip()
    # Slash commands, short replies and automatic messages (subagent reports, other sessions) are not
    # tasks, and their text must not leave the machine.
    if not is_request(prompt) or not enabled(root, "tasks"):
        return None
    task, session = redact(prompt)[:4000], payload.get("session_id")
    if not active(root):
        assess(root, task, source="prompt", session=session)
        return None
    try:
        result = assess(root, task, use_diff=True, source="prompt", session=session)
    except Exception as error:  # noqa: BLE001 - the request goes on, with the reason, whatever failed
        result = dict(status="unavailable", reason=str(error) or type(error).__name__)
    context = path_context(result)
    return dict(hookSpecificOutput=dict(hookEventName="UserPromptSubmit", additionalContext=context))


HANDLERS = {
    "UserPromptSubmit": user_prompt,
    "PreToolUse": pre_tool_use,
    "PostToolUse": post_tool_use,
    "PostToolUseFailure": post_tool_use,
    "Stop": stop,
    "SessionStart": session_start,
}


def handle(payload):
    root = find_root(payload.get("cwd") or Path.cwd())
    handler = HANDLERS.get(payload.get("hook_event_name") or "PreToolUse")
    if root is None or handler is None:
        return None
    if handler is pre_tool_use:
        return handler(root, payload)
    try:
        return handler(root, payload)
    except Exception:  # noqa: BLE001 - logging and hints must never break the session
        return None


def main():
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    output = handle(payload)
    if output:
        print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def summarize_runs(root, session=None):
    """Behavior actually recorded in session logs, checked against the AIFW workflow rules."""
    logs = sorted((Path(root) / ".aifw/runs").glob("*.jsonl"), key=lambda f: f.stat().st_mtime)
    if session == "latest":
        logs = logs[-1:]
    elif session:
        logs = [f for f in logs if f.stem == session]
    has_cases = bool(load_cases(root))
    summaries = []
    for file in logs:
        entries = read_log(file)
        failures = {}
        for e in entries:
            if e.get("verification") and e["ok"] is False:
                failures[e["command"]] = failures.get(e["command"], 0) + 1
        streaks = {command: streak(entries, command) for command in failures}
        # Findings break the workflow rules; notes are for review (control edits were confirmed by a person).
        findings, notes = [], []
        last_ok = max((i for i, e in enumerate(entries) if e.get("verification") and e.get("ok")), default=-1)
        ignored = sorted(
            {f for e in entries[last_ok + 1 :] if e.get("tool") == "Stop" for f in e["unverified"]}
        )
        if ignored:
            findings.append(
                "a turn ended with unverified code despite the Stop warning: " + ", ".join(ignored[:5])
            )
        repeated = sorted(c for c, n in streaks.items() if n >= 2)
        if repeated and not has_cases:
            findings.append("repeated failures without an impasse case: " + "; ".join(repeated[:3]))
        pending = unverified_edits(entries)
        if pending:
            notes.append("code changed after the last successful verification: " + ", ".join(pending[:5]))
        control = sorted(
            {e["file"] for e in entries if e.get("file") and any(c in e["file"] for c in CONTROL)}
        )
        if control:
            notes.append("AIFW control files edited: " + ", ".join(control))
        summaries.append(
            dict(
                session=file.stem,
                calls=len(entries),
                edits=sum(1 for e in entries if code_edit(e)),
                verifications=sum(1 for e in entries if e.get("verification")),
                failedVerifications=sum(failures.values()),
                findings=findings,
                notes=notes,
                status="warning" if findings else "pass",
            )
        )
    return summaries
