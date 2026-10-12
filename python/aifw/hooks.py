"""Claude Code hooks for AIFW projects.

PreToolUse enforces the permission policy, open impasses and control files; it never
auto-approves, so Claude Code's own permission rules still apply. PostToolUse records the
session log, Stop blocks unverified code changes and SessionStart injects project state.
Outside an AIFW project every event is a no-op.
"""

import json
from pathlib import Path
import re
import sys

from .common import now, read_yaml
from .impasse import load_cases, mutation_allowed
from .permissions import decide_action, load_permission_policy, validate_break_glass
from .shell import VERIFY, analyze, service_of, verification_visible

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
SHELL_TOOLS = {"Bash", "PowerShell"}

# Files that govern AIFW itself: editing them could loosen the checks applied to the agent.
CONTROL = (
    "aifw.yaml",
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
)


def find_root(cwd):
    for folder in [Path(cwd), *Path(cwd).parents]:
        if (folder / "aifw.yaml").is_file():
            return folder
    return None


def control_target(root, tool_name, tool_input, mutation):
    """The AIFW control file this call would change, if any."""
    if tool_name in EDIT_TOOLS:
        target = Path(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
        target = (target if target.is_absolute() else Path(root) / target).resolve()
        if not target.is_relative_to(Path(root).resolve()):
            return None
        text = target.relative_to(Path(root).resolve()).as_posix()
        matches = [c for c in CONTROL if text == c or text.startswith(c) or text.endswith("/" + c)]
    elif tool_name in SHELL_TOOLS and mutation:
        text = tool_input.get("command", "").replace("\\", "/")
        matches = [c for c in CONTROL if c in text]
    else:
        return None
    return matches[0] if matches else None


def classify(tool_name, tool_input, allowlist):
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
        return dict(kind="delegation", model=tool_input.get("model"), mutation=False)
    if tool_name == "WebSearch":
        return dict(kind="external-read", service="web-search", mutation=False)
    if tool_name not in SHELL_TOOLS:
        return dict(kind="read-only", mutation=False)
    return analyze(tool_input.get("command", ""), allowlist)


def project_settings(root):
    """Manifest fields the hook enforces: the single external allowlist and the data classification."""
    spec = read_yaml(Path(root) / "aifw.yaml")["spec"]
    return spec.get("externalAllowlist", []), spec.get("dataClassification", "internal")


def active_levels(root):
    return {
        read_yaml(f).get("metadata", {}).get("level")
        for f in (Path(root) / ".aifw/changes/active").glob("*/change.yaml")
    }


def active_grants(root, policy):
    """Action kinds covered by a valid, unexpired break-glass grant."""
    if not policy.get("breakGlass", {}).get("enabled"):
        return set()
    kinds = set()
    for file in (Path(root) / ".aifw/break-glass").glob("*.yaml"):
        grant = read_yaml(file)
        kinds |= {s for s in grant.get("scope", []) if validate_break_glass(grant, s)["valid"]}
    return kinds


def item_findings(root, policy, item, allowlist, classification):
    """Policy findings for one action of a tool call."""
    kind, findings = item["kind"], []
    if kind == "opaque":
        findings.append(("ask", "runs code the hook cannot read (eval, encoded or piped into a shell)"))
    elif kind == "mcp":
        servers = policy.get("mcpServers", {})
        if item["server"] in servers.get("deny", []):
            findings.append(("deny", f"MCP server {item['server']} is denied by the policy"))
        elif item["server"] in servers.get("ask", []):
            findings.append(("ask", f"MCP server {item['server']} requires confirmation"))
    elif kind == "delegation":
        risky = active_levels(root) & {"L2", "L3"}
        if item.get("model") == "haiku" and risky:
            # The model table never runs L2/L3 work on haiku.
            findings.append(("ask", f"delegates to haiku while an active {max(risky)} change exists"))
    else:
        decision = decide_action(item, policy, allowlist)
        if decision["decision"] != "allow" and kind in active_grants(root, policy):
            decision = dict(decision="allow", reason="break-glass")
        outside = kind == "external-read" and decision["decision"] == "deny"
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


def evaluate(root, tool_name, tool_input):
    """Return ("deny"|"ask", reasons) or None when AIFW has no objection."""
    policy = load_permission_policy(root)
    allowlist, classification = project_settings(root)
    request = classify(tool_name, tool_input, allowlist)
    findings = []
    for case in load_cases(root):
        if request["mutation"] and not mutation_allowed(case, request.get("destructive", False)):
            # Shell text is classified heuristically, so a frozen case asks instead of denying it.
            soft = case["state"] in {"OPEN", "HUMAN_REVIEW"} and tool_name in SHELL_TOOLS
            findings.append(
                (
                    "ask" if soft and not request.get("destructive") else "deny",
                    f"impasse {case['id']} is {case['state']}; see `aifw impasse status`",
                )
            )
    for item in request.get("requests", [request]):
        findings += item_findings(root, policy, item, allowlist, classification)
    control = control_target(root, tool_name, tool_input, request["mutation"])
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
        result = evaluate(root, payload.get("tool_name", ""), payload.get("tool_input") or {})
    except Exception as error:  # noqa: BLE001 - a broken policy must reach the human, not pass silently
        result = "ask", [f"AIFW hook could not evaluate the policy: {error}"]
    if result is None:
        return None
    level, reasons = result
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
        entry.update(command=command, verification=bool(VERIFY.search(raw)))
        if entry["verification"] and entry["ok"] and not verification_visible(raw):
            entry.update(ok=None, masked=True)
    elif tool in EDIT_TOOLS:
        path = Path(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
        path = (path if path.is_absolute() else Path(root) / path).resolve()
        inside = path.is_relative_to(Path(root).resolve())
        entry["file"] = path.relative_to(Path(root).resolve()).as_posix() if inside else "<outside project>"
    log = run_log(root, payload)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read_log(file):
    if not file.is_file():
        return []
    return [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines() if line.strip()]


def code_edit(entry):
    file = entry.get("file", "")
    return (
        bool(file)
        and not file.startswith(("docs/", ".aifw/", "<"))
        and not file.endswith((".md", ".txt", ".rst"))
    )


def unverified_edits(entries):
    """Code files edited after the last successful verification command."""
    last_ok = max((i for i, e in enumerate(entries) if e.get("verification") and e.get("ok")), default=-1)
    return sorted({e["file"] for e in entries[last_ok + 1 :] if code_edit(e)})


def post_tool_use(root, payload):
    entry = record(root, payload)
    if entry["ok"] is not False or not entry.get("verification"):
        return None
    log = read_log(run_log(root, payload))
    failures = [e for e in log if e.get("command") == entry["command"] and e["ok"] is False]
    if len(failures) < 2 or any(c["state"] != "RESOLVED" for c in load_cases(root)):
        return None
    return dict(
        hookSpecificOutput=dict(
            hookEventName=payload.get("hook_event_name", "PostToolUse"),
            additionalContext=(
                f"AIFW: `{entry['command']}` failed {len(failures)} times in this session. "
                "Before another fix, open an impasse case with `aifw impasse open --id <slug> --impact <level>` "
                "and record each distinct attempt with `aifw impasse attempt`."
            ),
        )
    )


def stop(root, payload):
    if payload.get("stop_hook_active"):
        return None
    entries = read_log(run_log(root, payload))
    pending = unverified_edits(entries)
    if not pending:
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

    lines = ["AIFW is enabled in this project; follow the aifw-workflow skill."]
    if not assess_intake(root)["complete"]:
        lines.append("Intake is incomplete: run `aifw intake status`.")
    lines += [f"Impasse {c['id']} is {c['state']}." for c in load_cases(root) if c["state"] != "RESOLVED"]
    for file in sorted((Path(root) / ".aifw/changes/active").glob("*/change.yaml")):
        change = read_yaml(file)
        meta = change.get("metadata", {})
        lines.append(f"Active change {meta.get('id')} ({meta.get('level')}, {change.get('status')}).")
    return dict(hookSpecificOutput=dict(hookEventName="SessionStart", additionalContext="\n".join(lines)))


HANDLERS = {
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
        findings = []
        pending = unverified_edits(entries)
        if pending:
            findings.append("code changed after the last successful verification: " + ", ".join(pending[:5]))
        repeated = sorted(c for c, n in failures.items() if n >= 2)
        if repeated and not has_cases:
            findings.append("repeated failures without an impasse case: " + "; ".join(repeated[:3]))
        control = sorted(
            {e["file"] for e in entries if e.get("file") and any(c in e["file"] for c in CONTROL)}
        )
        if control:
            findings.append("AIFW control files edited: " + ", ".join(control))
        summaries.append(
            dict(
                session=file.stem,
                calls=len(entries),
                edits=sum(1 for e in entries if code_edit(e)),
                verifications=sum(1 for e in entries if e.get("verification")),
                failedVerifications=sum(failures.values()),
                findings=findings,
                status="warning" if findings else "pass",
            )
        )
    return summaries
