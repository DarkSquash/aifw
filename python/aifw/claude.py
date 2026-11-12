"""Claude Code setup: a global /aifw command and per-project activation."""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import shutil
import subprocess

from . import __version__
from .common import assets, ignore_local_logs, project_path, read_json, require, write_json

TOOLS = "Bash|PowerShell|Edit|Write|MultiEdit|NotebookEdit"
MISSING = (
    "AIFW is enabled in this project, but aifw-hook failed or is not installed on this machine. "
    "Install it with: uv tool install <aifw folder>, then: aifw claude install (see HOW_TO_USE). "
    "Until then, commands and edits in this project are blocked."
)
# Single quotes: bash must print the message, never expand or run anything inside it.
assert not set(MISSING) & set("'`$\\"), "MISSING is embedded in single-quoted shell text"
# Git Bash is required on Windows (Git is an AIFW dependency), so the fallbacks use bash syntax.
COMMAND = dict(type="command", command="aifw-hook || true", shell="bash", timeout=10)
HOOKS = {
    # A project that opted into AIFW must not fail open: a missing hook blocks with instructions.
    "PreToolUse": dict(
        matcher=TOOLS + "|Read|Grep|Glob|WebFetch|WebSearch|Agent|Task|mcp__.*",
        hooks=[dict(COMMAND, command=f"aifw-hook || {{ echo '{MISSING}' >&2; exit 2; }}", onFailure="block")],
    ),
    # Logging runs in the background so successful calls pay no hook latency.
    "PostToolUse": dict(matcher=TOOLS, hooks=[{**COMMAND, "async": True}]),
    "PostToolUseFailure": dict(matcher=TOOLS, hooks=[COMMAND]),
    "Stop": dict(hooks=[COMMAND]),
    # Before the agent reads a message, the hook records a plan approval and hands over the task path
    # (ADR-0037); 60 s covers the three retries of the decision model, so its failure still arrives.
    "UserPromptSubmit": dict(hooks=[{**COMMAND, "timeout": 60}]),
    # Plain text on stdout becomes session context, so Claude can tell the person what is missing.
    "SessionStart": dict(hooks=[dict(COMMAND, command=f"aifw-hook || echo '{MISSING}'")]),
}


def entries_for(event):
    return [HOOKS[event]]


REQUIRED_SKILLS = ("grilling", "grill-me", "code-review", "setup-matt-pocock-skills", "handoff")
STAMP = "<!-- aifw-version: {} -->"
SPAWN_DEPTH = "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH"
HASH = "<!-- aifw-sha256: {} -->"
INSTALLED = re.compile(
    r"(?P<body>.*)\n\n<!-- aifw-version: [^\n]* -->\n<!-- aifw-sha256: (?P<hash>[0-9a-f]{64}) -->\n", re.S
)
AGENTS = (
    "aifw-explorer",
    "aifw-quick",
    "aifw-executor",
    "aifw-adversary",
    "aifw-qa",
    "aifw-planner",
    "aifw-lead",
    "aifw-worker",
    "aifw-senior",
)


def install_command(home=None):
    """Install the user-invoked /aifw command; it never activates AIFW by itself."""
    target = Path(home or Path.home()) / ".claude/skills/aifw/SKILL.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(assets() / "templates/claude/skills/aifw/SKILL.md", target)
    return dict(status="installed", skill=str(target))


def ours(entry):
    # The removed shadow judge (ADR-0035, ADR-0037) still counts as ours, so `enable` cleans it up.
    return any(
        "aifw-hook" in h.get("command", "") or "aifw assess judge" in h.get("command", "")
        for h in entry.get("hooks", [])
    )


def install_template(root, template, target):
    """Copy a stamped template into the project; returns the backup path if an edited copy was kept."""
    path = project_path(root, target)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = (assets() / template).read_text(encoding="utf-8")
    body = text.rstrip("\n")
    digest = sha256(body.encode("utf-8")).hexdigest()
    content = body + "\n\n" + STAMP.format(__version__) + "\n" + HASH.format(digest) + "\n"
    backup = None
    if path.is_file():
        existing = path.read_text(encoding="utf-8")
        # The hash lets an untouched copy from another version be replaced silently.
        found = INSTALLED.fullmatch(existing)
        untouched = found and sha256(found["body"].encode("utf-8")).hexdigest() == found["hash"]
        if existing != content and not untouched:
            # Someone edited the project copy, or it has no hash: keep it before replacing.
            path.with_name(path.name + ".bak").write_text(existing, encoding="utf-8", newline="\n")
            backup = f"{target}.bak"
    path.write_text(content, encoding="utf-8", newline="\n")
    return backup


GRAPHIFY = "graphify"


def run(args, root, timeout=60):
    """Run a third-party command without a shell; the CompletedProcess, or None when it cannot run."""
    try:
        return subprocess.run(args, cwd=root, stdin=subprocess.DEVNULL, capture_output=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None


def enable_graphify(root):
    """Set up graphify when it is on PATH (graph, .gitignore, git hooks); one line of notes, never raises."""
    exe = shutil.which(GRAPHIFY)
    if not exe:
        return "graphify not found on PATH: skipped"
    out, notes = root / "graphify-out", []
    if not out.is_dir():
        ignore_local_logs(root, ("graphify-out/",))
    if (out / "graph.json").is_file():
        notes.append("graph already exists")
    else:
        built = run([exe, "update", "."], root, 300)
        notes.append(
            "graph built"
            if built and built.returncode == 0
            else "graph build failed: run `graphify update .`"
        )
    if not (root / ".git").exists():
        notes.append("no .git: git hooks skipped")
    else:
        hooks_path = run(["git", "config", "--get", "core.hooksPath"], root)
        if hooks_path and hooks_path.stdout.strip():
            notes.append(
                "core.hooksPath set: git hooks skipped (run `graphify hook install` if you want them)"
            )
        else:
            hook = run([exe, "hook", "install"], root)
            notes.append(
                "git hooks installed"
                if hook and hook.returncode == 0
                else "git hooks failed: run `graphify hook install`"
            )
    return "; ".join(notes)


def enable_project(root, graphify=True):
    """Add the AIFW hooks, workflow skill and role subagents to this project's .claude folder, idempotently."""
    root = Path(root)
    require((root / "aifw.yaml").is_file(), "Run aifw init before enabling Claude Code.", "NOT_READY")
    settings_file = project_path(root, ".claude/settings.json")
    # A malformed settings file raises here, so it is never overwritten.
    settings = read_json(settings_file) if settings_file.is_file() else {}
    require(isinstance(settings, dict), "Invalid .claude/settings.json.", "POLICY_CONFLICT")
    hooks, changed = settings.setdefault("hooks", {}), []
    for event in HOOKS:
        entries, wanted = hooks.setdefault(event, []), entries_for(event)
        current = [e for e in entries if ours(e)]
        if current != wanted:
            hooks[event] = [e for e in entries if not ours(e)] + deepcopy(wanted)
            changed.append(event)
    if changed:
        write_json(settings_file, settings)
    skill_backup = install_template(
        root, "templates/claude/skills/aifw-workflow/SKILL.md", ".claude/skills/aifw-workflow/SKILL.md"
    )
    agent_backups = [
        backup
        for name in AGENTS
        if (
            backup := install_template(
                root, f"templates/claude/agents/{name}.md", f".claude/agents/{name}.md"
            )
        )
    ]
    result = dict(
        status="enabled",
        hooksChanged=changed,
        gitignored=ignore_local_logs(root),  # also for projects initialized before the logs were ignored
        settings=".claude/settings.json",
        skill=".claude/skills/aifw-workflow/SKILL.md",
        skillBackup=skill_backup,
        agents=[f".claude/agents/{n}.md" for n in AGENTS],
        agentBackups=agent_backups,
        nextAction="Open a new Claude Code session in this project so the hooks and skill load.",
    )
    result["graphify"] = enable_graphify(root) if graphify else "skipped (--no-graphify)"
    return result


def env_value(file, name):
    try:
        data = json.loads(file.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None
    env = data.get("env") if isinstance(data, dict) else None
    return env.get(name) if isinstance(env, dict) else None


def nesting_findings(root, home):
    """Warn when the spawn depth is 1: the planner and lead then cannot launch workers."""
    sources = {"environment": os.environ.get(SPAWN_DEPTH)}
    files = [
        root / ".claude/settings.local.json",
        root / ".claude/settings.json",
        home / ".claude/settings.json",
    ]
    for file in files:
        sources[str(file)] = env_value(file, SPAWN_DEPTH)
    return [
        f"{SPAWN_DEPTH}=1 in {source}: aifw-planner and aifw-lead cannot launch aifw-worker "
        "(they need 2 or more; Claude Code default is 3)"
        for source, value in sources.items()
        if re.fullmatch(r"0*1", str(value))
    ]


def check_project(root, home=None):
    """Report what is missing for Claude Code to run AIFW in this project; never changes files."""
    root, home = Path(root), Path(home or Path.home())
    findings = []
    settings_file = root / ".claude/settings.json"
    settings = read_json(settings_file) if settings_file.is_file() else {}
    for event in HOOKS:
        if [e for e in settings.get("hooks", {}).get(event, []) if ours(e)] != entries_for(event):
            findings.append(f"hook {event} missing or outdated: run `aifw claude enable`")
    skill = root / ".claude/skills/aifw-workflow/SKILL.md"
    if not skill.is_file():
        findings.append("project skill aifw-workflow missing: run `aifw claude enable`")
    elif STAMP.format(__version__) not in skill.read_text(encoding="utf-8"):
        findings.append(
            f"project skill aifw-workflow is not from aifw {__version__}: run `aifw claude enable`"
        )
    for name in AGENTS:
        agent = root / f".claude/agents/{name}.md"
        if not agent.is_file():
            findings.append(f"subagent {name} missing: run `aifw claude enable`")
        elif STAMP.format(__version__) not in agent.read_text(encoding="utf-8"):
            findings.append(f"subagent {name} is not from aifw {__version__}: run `aifw claude enable`")
    if not shutil.which("aifw-hook"):
        findings.append("aifw-hook is not on PATH: reinstall with `uv tool install <aifw folder>`")
    command = home / ".claude/skills/aifw/SKILL.md"
    if not command.is_file():
        findings.append("global /aifw command missing: run `aifw claude install`")
    elif command.read_bytes() != (assets() / "templates/claude/skills/aifw/SKILL.md").read_bytes():
        findings.append("global /aifw command is outdated: run `aifw claude install`")
    findings += [
        f"required skill {name} is not installed (see HOW_TO_USE, Skills, plugins e MCPs)"
        for name in REQUIRED_SKILLS
        if not (home / ".claude/skills" / name / "SKILL.md").is_file()
    ]
    findings += nesting_findings(root, home)
    return dict(status="pass" if not findings else "warning", findings=findings)
