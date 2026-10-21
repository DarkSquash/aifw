"""Claude Code setup: a global /aifw command and per-project activation."""

from copy import deepcopy
from pathlib import Path
import shutil

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
    # The shadow task assessor calls the decision model; in the background the prompt never waits.
    "UserPromptSubmit": dict(hooks=[{**COMMAND, "async": True, "timeout": 60}]),
    # Plain text on stdout becomes session context, so Claude can tell the person what is missing.
    "SessionStart": dict(hooks=[dict(COMMAND, command=f"aifw-hook || echo '{MISSING}'")]),
}
# The shadow judge of opaque commands runs beside the PreToolUse check, never in it: an async hook adds
# no latency and its output cannot change the decision (ADR-0035). Off unless aifw.yaml lists it.
JUDGE = dict(
    matcher="Bash|PowerShell",
    hooks=[dict(COMMAND, command="aifw assess judge --hook || true", timeout=120, **{"async": True})],
)


def entries_for(event):
    return [HOOKS[event], JUDGE] if event == "PreToolUse" else [HOOKS[event]]


REQUIRED_SKILLS = ("grilling", "grill-me", "code-review", "setup-matt-pocock-skills", "handoff")
STAMP = "<!-- aifw-version: {} -->"


def install_command(home=None):
    """Install the user-invoked /aifw command; it never activates AIFW by itself."""
    target = Path(home or Path.home()) / ".claude/skills/aifw/SKILL.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(assets() / "templates/claude/skills/aifw/SKILL.md", target)
    return dict(status="installed", skill=str(target))


def ours(entry):
    return any(
        "aifw-hook" in h.get("command", "") or "aifw assess judge" in h.get("command", "")
        for h in entry.get("hooks", [])
    )


def enable_project(root):
    """Add the AIFW hooks and workflow skill to this project's .claude folder, idempotently."""
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
    skill = project_path(root, ".claude/skills/aifw-workflow/SKILL.md")
    skill.parent.mkdir(parents=True, exist_ok=True)
    text = (assets() / "templates/claude/skills/aifw-workflow/SKILL.md").read_text(encoding="utf-8")
    content = text.rstrip("\n") + "\n\n" + STAMP.format(__version__) + "\n"
    backup = None
    if skill.is_file():
        existing = skill.read_text(encoding="utf-8")
        if existing != content:
            # Someone edited the project copy, or it came from another version: keep it before replacing.
            backup = skill.with_name("SKILL.md.bak")
            backup.write_text(existing, encoding="utf-8", newline="\n")
    skill.write_text(content, encoding="utf-8", newline="\n")
    return dict(
        status="enabled",
        hooksChanged=changed,
        gitignored=ignore_local_logs(root),  # also for projects initialized before the logs were ignored
        settings=".claude/settings.json",
        skill=".claude/skills/aifw-workflow/SKILL.md",
        skillBackup=backup and ".claude/skills/aifw-workflow/SKILL.md.bak",
        nextAction="Open a new Claude Code session in this project so the hooks and skill load.",
    )


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
    return dict(status="pass" if not findings else "warning", findings=findings)
