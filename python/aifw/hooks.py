"""Claude Code hooks for AIFW projects.

PreToolUse enforces the permission policy, open impasses and control files; it never
auto-approves, so Claude Code's own permission rules still apply. PostToolUse records the
session log, Stop blocks unverified code changes and SessionStart injects project state.
Outside an AIFW project every event is a no-op.
"""

from fnmatch import fnmatch
from hashlib import sha256
from itertools import islice
import json
from pathlib import Path
import re
import subprocess
import sys
import time

from . import signing
from .common import AifwError, now, read_yaml
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
    ".claude/agents/aifw-",  # the role subagents: their model, tools and instructions (ADR-0038)
    ".aifw/assessments/",
    # git runs code from here by itself (hooks, aliases and helpers from config), unread by the hook.
    ".git/",
    ".husky/",  # husky points core.hooksPath here: git runs these hooks on commit
)
# What a commit must not carry without asking: files a signature turns into an approval (Charter,
# adoption, impasse, waiver, break-glass) and the policy itself. Generated files, evidence and change
# approvals are left out (ADR-0037).
SIGNED_OR_POLICY = (
    "aifw.yaml", ".aifw/charter.yaml", ".aifw/adoption/status.yaml", ".aifw/impasses/", ".aifw/waivers/",
    ".aifw/break-glass/", ".aifw/permissions.yaml", ".aifw/routing.yaml", ".aifw/gates.yaml",
    ".aifw/project-rules.yaml", ".claude/settings.json", ".claude/settings.local.json",
)  # fmt: skip
# Installed tools the hook runs without reading (ADR-0034): editing them with the edit tools asks.
# Shell commands are not checked: `.venv/bin/ruff format .` names the folder without changing it.
INSTALLED = re.compile(r"(^|[\s'\"=:/])(\.venv|node_modules|\.tox)/")


def find_root(cwd):
    for folder in [Path(cwd), *Path(cwd).parents]:
        if (folder / "aifw.yaml").is_file():
            return folder
    return None


PATTERN_WORD = re.compile(r"[^\s'\"<>|;&()=]*[*?\[{][^\s'\"<>|;&()=]*")
BRACES = re.compile(r"\{([^{}]*,[^{}]*)\}")


def pattern_files(root, cwd, word):
    """The project files a shell pattern names: `chang?.yaml`, `approval.m[d]`, `approval.{md,x}`."""
    words, found = [word], []
    while len(words) < 64 and any(BRACES.search(w) for w in words):  # innermost braces first
        expanded = []
        for w in words:
            m = BRACES.search(w)
            expanded += [w[: m.start()] + p + w[m.end() :] for p in m.group(1).split(",")] if m else [w]
        words = expanded
    base, top = Path(cwd or root), Path(root).resolve()
    for pattern in words:
        if pattern.lstrip("./").startswith("**"):
            continue  # shortcut: a pattern recursive from the top is not expanded, it would walk node_modules
        path = Path(pattern)
        if path.is_absolute() and not path.is_relative_to(top):
            continue
        parent, name = (top, path.relative_to(top).as_posix()) if path.is_absolute() else (base, pattern)
        try:  # bounded: a pattern like **/* must not stall every command
            matches = list(islice(parent.glob(name), 200))
        except (OSError, ValueError, NotImplementedError):
            matches = []
        for match in matches:
            match = match.resolve()
            if match.is_relative_to(top):
                found.append(match.relative_to(top).as_posix().lower())
    return found


def approved_plans(root):
    """The paths each active, approved change planned to touch, by change id (ADR-0039)."""
    plans = {}
    for folder in sorted((Path(root) / ".aifw/changes/active").glob("*/")):
        try:
            if not (read_yaml(folder / "change.yaml") or {}).get("approval"):
                continue
            tasks = (read_yaml(folder / "tasks.yaml") or {}).get("tasks") or []
            plans[folder.name.lower()] = [str(p) for t in tasks for p in t.get("paths") or []]
        except Exception:  # noqa: BLE001 - a broken change leaves the rule, never takes the hook down
            continue
    return plans


def outside_plan(root, policy, tool_name, tool_input):
    """Why an edit asks: it lands outside every approved plan's paths (ADR-0039)."""
    if tool_name not in EDIT_TOOLS or policy.get("changeScope", "ask") != "ask":
        return None
    plans = approved_plans(root)
    base = Path(root).resolve()
    target = Path(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
    target = (target if target.is_absolute() else base / target).resolve()
    if not plans or not target.is_relative_to(base):
        return None
    text = target.relative_to(base).as_posix().lower()
    if text.startswith(".aifw/changes/active/"):
        return None  # the changes' own artifacts; change.yaml, approval.md and tasks.yaml are control files
    for path in (p.replace("\\", "/").lower().strip("/") for paths in plans.values() for p in paths):
        if text == path or text.startswith(path + "/") or fnmatch(text, path):
            return None
    return (
        f"changes {text}, outside the approved plan of {', '.join(plans)}; add it to that change's tasks.yaml"
    )


def control_target(root, tool_name, tool_input, mutation, protected=(), cwd=None):
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
        # Also inside a worktree or a copy of the tree, from where a merge or a copy brings it in.
        if "/.aifw/changes/" in "/" + text and text.endswith(("/change.yaml", "/approval.md")):
            matches.append(text.rsplit("/", 1)[1])  # the approval and its record, kept by the prompt hook
        if INSTALLED.search(text):
            matches.append(INSTALLED.search(text).group(2) + "/")
        plan = re.fullmatch(r"\.aifw/changes/active/([^/]+)/tasks\.yaml", text)
        if plan and plan.group(1) in approved_plans(root):
            matches.append("tasks.yaml")  # the approved plan does not widen itself (ADR-0039)
    elif tool_name in SHELL_TOOLS and mutation:
        text = tool_input.get("command", "").replace("\\", "/").lower()
        controls = (*CONTROL, *protected, "change.yaml", "approval.md", ".claude/settings")
        matches = [c for c in controls if c.lower() in text]
        if "tasks.yaml" in text:
            matches += [
                "tasks.yaml" for c in approved_plans(root) if f".aifw/changes/active/{c}/tasks.yaml" in text
            ]
        # A pattern can name a control file without spelling it (chang?.yaml, approval.m[d]).
        for word in PATTERN_WORD.findall(tool_input.get("command", "").replace("\\", "/")):
            matches += [c for f in pattern_files(root, cwd, word) for c in controls if c.lower() in "/" + f]
    else:
        return None
    return matches[0] if matches else None


# Role subagents that review a change: they read and test, and write only the review (ADR-0038).
REVIEWERS = {"aifw-adversary", "aifw-qa"}
REVIEW_FILE = re.compile(r"\.aifw/changes/active/[^/]+/independent-review\.md")
# Opaque code still runs, so the adversary can prove a finding with a probe; what it does is not read.
REVIEWER_KINDS = {"read-only", "external-read", "secret-read", "opaque"}


def reviewer_change(root, payload):
    """Why a reviewer subagent may not make this call: it would change the project."""
    if payload.get("agent_type") not in REVIEWERS:
        return None
    tool_name, tool_input = payload.get("tool_name", ""), payload.get("tool_input") or {}
    if tool_name in EDIT_TOOLS:
        base = Path(root).resolve()
        target = Path(tool_input.get("file_path") or tool_input.get("notebook_path") or "")
        target = (target if target.is_absolute() else base / target).resolve()
        if not target.is_relative_to(base):
            return None  # probes in a temporary folder
        if REVIEW_FILE.fullmatch(target.relative_to(base).as_posix().lower()):
            return None
        return "a reviewer subagent writes only the change's independent-review.md; put probes in a temporary folder"
    if tool_name in SHELL_TOOLS:
        requests = analyze(tool_input.get("command", ""), cwd=payload.get("cwd"))["requests"]
        # An unknown program (python --version, ruff check) runs like opaque code; known writers do not.
        writes = [r for r in requests if not (r["kind"] == "filesystem-write" and r.get("unknown"))]
        if {r["kind"] for r in writes} - REVIEWER_KINDS:
            return "a reviewer subagent does not write files, commit or change the repository; read, test or probe instead"
    return None


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


def git_output(root, *args):
    try:
        done = subprocess.run(
            ["git", *args], cwd=root, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


PROTECTED_PUSH = "changes the default branch or the remote history; work goes through a branch"


def protected_push(root, item):
    """Why a push asks: it reaches the default branch, all branches or tags, or the hook cannot place it.

    "" for a push to a work branch, which runs on its own (ADR-0037); forced pushes and deletions are
    destructive and ask through destructiveChanges. A gh write that is not a pull request arrives as
    protected.
    """
    if item.get("protected"):
        return PROTECTED_PUSH
    if "push" not in item:
        return ""
    targets, flags = item["push"]["targets"], {f.split("=", 1)[0] for f in item["push"]["flags"]}
    if flags & {"--all", "--branches", "--mirror", "--tags", "--follow-tags", "--prune"}:
        return PROTECTED_PUSH
    remote, specs = (targets[0], targets[1:]) if targets else ("origin", [])
    current = git_output(root, "rev-parse", "--abbrev-ref", "HEAD")
    # Without the remote's HEAD (a URL, or a remote added by hand) the default branch is unknown: ask.
    head = git_output(root, "symbolic-ref", "--short", f"refs/remotes/{remote}/HEAD").split("/", 1)[-1]
    if not head and re.search(r"[:/@\\]", remote):
        return "pushes to a URL, whose default branch the hook cannot tell; push through a named remote"
    if not head:
        return (
            f"the default branch of {remote} is unknown (no refs/remotes/{remote}/HEAD); run "
            f"`git remote set-head {remote} --auto` once and pushes to work branches run on their own"
        )
    if current in {"", "HEAD"} or "tag" in specs:
        return PROTECTED_PUSH
    if not specs:
        # Configuration decides where a bare push lands: a push refspec, or the branch's upstream.
        configured = git_output(root, "config", "--get-regexp", r"^remote\..*\.push$")
        upstream = git_output(root, "rev-parse", "--abbrev-ref", "@{upstream}").split("/", 1)[-1]
        if configured or git_output(root, "config", "push.default") == "matching" or upstream == head:
            return PROTECTED_PUSH
        specs = [current]
    for spec in specs:
        source, _, destination = spec.lstrip("+").rpartition(":")
        source = source or destination
        destination = current if destination in {"HEAD", "@"} else destination
        if "*" in spec or not destination or source.startswith(("refs/tags/", "tags/")):
            return PROTECTED_PUSH
        if git_output(root, "show-ref", "--verify", f"refs/tags/{source}"):
            return PROTECTED_PUSH  # a tag pushed by its short name
        branch = destination.removeprefix("refs/").removeprefix("heads/")
        if (destination.startswith("refs/") and not destination.startswith("refs/heads/")) or branch == head:
            return PROTECTED_PUSH
    return ""


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
    elif kind == "secret-read" and item.get("mention"):
        findings.append(("ask", "names a file that usually holds secrets"))
    elif kind == "secret-read":
        # The person reads secrets; the agent never does (ADR-0037).
        findings.append(("deny", "reads files or variables that usually hold secrets"))
    elif kind == "publish" and classification in {"confidential", "restricted"}:
        findings.append(("deny", f"publishes the project's code outside the machine ({classification} data)"))
    elif kind == "publish":
        findings.append(
            ("ask", "publishes a package to a registry; a published version cannot be taken back")
        )
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
            # A commit carrying a control file can turn into an approval once signed (Charter, adoption,
            # impasse, waiver, break-glass); change approvals no longer depend on signing (ADR-0037).
            findings.append(("ask", f"commits with the AIFW control file {control} changed"))
    elif kind == "mcp":
        servers = policy.get("mcpServers", {})
        if item["server"] in servers.get("deny", []):
            findings.append(("deny", f"MCP server {item['server']} is denied by the policy"))
        elif item["server"] in servers.get("ask", []):
            findings.append(("ask", f"MCP server {item['server']} requires confirmation"))
    elif kind == "delegation":
        # Which model takes the work is the agent's call, by the model table (ADR-0037).
        if item.get("remote"):
            # Subagents on this machine inherit these hooks; a cloud session runs outside them.
            findings.append(("ask", "delegates to a cloud session, outside this machine's AIFW hooks"))
    elif kind == "git-remote" and policy.get("remoteMutation") == "branches":
        reason = protected_push(root, item)
        grants = active_grants(root, policy) if reason else {}
        if reason and kind in grants:
            log_break_glass(grants[kind], kind, tool_name, tool_input or {})
        elif reason:
            findings.append(("ask", reason))
    elif (
        kind in {"external-write", "external-read"}
        and item.get("discussion")
        and policy.get("remoteMutation") == "branches"
        and classification not in {"confidential", "restricted"}
    ):
        pass  # opening and discussing pull requests is how branch work reaches the person (ADR-0037)
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


def evaluate(root, tool_name, tool_input, cwd=None):
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
    # A push is judged on its own, so `git commit -am x && git push` is not a commit beside other writes.
    mixed = any(i["kind"] not in {"commit", "git-local", "read-only", "signing", "git-remote"} for i in items)
    for item in items:
        item = dict(item, mixed=True) if mixed and item["kind"] == "commit" else item
        findings += item_findings(root, policy, item, allowlist, classification, tool_name, tool_input)
    control = control_target(
        root, tool_name, tool_input, request["mutation"], policy.get("protectedPaths", []), cwd
    )
    if control:
        findings.append(("ask", f"changes the AIFW control file {control}"))
    elif scope := outside_plan(root, policy, tool_name, tool_input):
        findings.append(("ask", scope))
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


# The command itself, at the start of a command line, not a grep or a commit message that names it.
REQUEST_APPROVAL = re.compile(
    r"(?:^|[;&|(\n])\s*(?:\w+=\S*\s+)*(?:\S*[\\/])?"
    r"(?:aifw(?:\.exe)?|(?:\S*[\\/])?(?:python3?|py)(?:\.exe)?\s+-m\s+aifw|uv\s+run\s+(?:python\s+-m\s+)?aifw|uvx\s+aifw)"
    r"\s+spec\s+request-approval\s+(?:-\S+\s+)*([a-z][a-z0-9-]*)",
    re.IGNORECASE,
)


def approval_owner(root, change_id):
    """Where the hook keeps which chat session asked for the change's approval (ADR-0037)."""
    return Path(root) / ".aifw/runs/approvals" / f"{change_id}.session"


def session_name(payload):
    return re.sub(r"[^A-Za-z0-9_-]", "", str(payload.get("session_id") or ""))[:80] or "unknown"


def awaiting_reply(root, payload):
    """The change whose plan this session put to the person and that still waits for the reply."""
    from .specs import APPROVAL_REQUEST

    pending = sorted((Path(root) / ".aifw/changes/active").glob(f"*/{APPROVAL_REQUEST}"))
    asked = requested_here(root, payload) if pending else None  # nothing to read without a request
    return next((p.parent.name for p in pending if asked(p.parent.name)), None)


def pre_tool_use(root, payload):
    # The agent stays frozen until the person answers the plan, so the next message is that answer.
    waiting = awaiting_reply(root, payload)
    if waiting:
        return dict(
            hookSpecificOutput=dict(
                hookEventName="PreToolUse",
                permissionDecision="deny",
                permissionDecisionReason=(
                    f"AIFW: o plano da mudança {waiting} aguarda a resposta da pessoa; pare aqui e "
                    "espere, nenhuma ferramenta roda até ela responder (ADR-0037)"
                ),
            )
        )
    try:
        # A reviewer's write is denied before the policy is read, so a broken policy cannot soften it.
        reason = reviewer_change(root, payload)
        result = (
            ("deny", [reason])
            if reason
            else evaluate(
                root, payload.get("tool_name", ""), payload.get("tool_input") or {}, payload.get("cwd")
            )
        )
    except Exception as error:  # noqa: BLE001 - a broken policy must reach the human, not pass silently
        result = "ask", [f"AIFW hook could not evaluate the policy: {error}"]
    command = str((payload.get("tool_input") or {}).get("command") or "")
    asking = REQUEST_APPROVAL.search(command) if payload.get("tool_name") in SHELL_TOOLS else None
    if asking and (result is None or result[0] != "deny"):
        # Kept now, not by the async PostToolUse, so the freeze holds from the very next call.
        owner = approval_owner(root, asking.group(1))
        owner.parent.mkdir(parents=True, exist_ok=True)
        owner.write_text(session_name(payload), encoding="utf-8")
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
    return Path(root) / ".aifw/runs" / f"{session_name(payload)}.jsonl"


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
    for line in listed.splitlines():
        path = line[3:].split(" -> ")[-1].strip().strip('"').lower()
        for control in SIGNED_OR_POLICY:
            if path == control or (control.endswith("/") and path.startswith(control)):
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


def requested_here(root, payload):
    """Whether this chat session is the last one that asked for the change's approval."""
    session = session_name(payload)

    def asked(change_id):
        try:
            return approval_owner(root, change_id).read_text(encoding="utf-8").strip() == session
        except (OSError, ValueError):  # a missing or garbled owner file is no request of this session
            return False

    return asked


def user_prompt(root, payload):
    """The person's message, before the agent sees it.

    It records the approval of a plan awaiting it (ADR-0037): only this hook writes it, from the
    person's own words. With the task assessment on, it hands the agent the execution path; a
    failure only says so, and the request goes on as usual.
    """
    from .assessment import AUTOMATIC_PROMPT, assess, enabled, is_request, path_context
    from .context import redact
    from .specs import record_chat_approval

    prompt = (payload.get("prompt") or "").strip()
    context = []
    if not AUTOMATIC_PROMPT.match(prompt):  # only the person's own messages approve
        try:
            reply = record_chat_approval(root, prompt, now(), requested_here(root, payload))
        except AifwError as error:
            context.append(f"AIFW: a aprovação não foi registrada: {error}")
        else:
            if reply and reply.get("approved"):
                context.append(
                    f"AIFW: aprovação da mudança {reply['approved']} registrada a partir da mensagem da pessoa."
                )
            elif reply:
                context.append(
                    f"AIFW: a resposta não aprovou o plano de {', '.join(reply['dropped'])}; o pedido foi "
                    "cancelado. Ajuste o plano se for o caso e peça de novo com `aifw spec request-approval`."
                )
    # Slash commands, short replies and automatic messages (subagent reports, other sessions) are not
    # tasks, and their text must not leave the machine.
    if is_request(prompt) and enabled(root, "tasks"):
        try:
            result = assess(root, redact(prompt)[:4000], use_diff=True, source="prompt")
        except Exception as error:  # noqa: BLE001 - the request goes on, with the reason, whatever failed
            result = dict(status="unavailable", reason=str(error) or type(error).__name__)
        context.append(path_context(result))
    if not context:
        return None
    return dict(
        hookSpecificOutput=dict(hookEventName="UserPromptSubmit", additionalContext="\n".join(context))
    )


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
