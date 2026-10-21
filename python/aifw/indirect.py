"""Code a shell command runs indirectly, read for the Claude Code hook (ADR-0034).

A command can run code that is not in its own text: a script file, a local module, a package.json
script, a Makefile recipe. The hook reads that code with the same rules as the command itself and
reports as opaque whatever it cannot read with confidence: a binary, a language it does not read, a
file that does not exist yet or that the same command changes (the hook reads before the command
runs), and Makefile constructs it does not follow. Reading fails closed: an error is opaque.
"""

from functools import lru_cache
import json
import os
from pathlib import Path
import re
import subprocess

from . import shell

SCRIPT_SUFFIXES = (".py", ".js", ".mjs", ".cjs", ".ts")
SHELL_SUFFIXES = (".sh", ".bash", ".zsh", ".ps1", ".psm1", ".bat", ".cmd")
# Installs put tools here, and an install needs the person; the hook runs them without reading.
INSTALLED_TOOLS = {".venv", "venv", "node_modules", ".tox"}
ACTIVATE_SCRIPTS = {
    "activate",
    "activate.sh",
    "activate.ps1",
    "activate.bat",
    "activate.fish",
    "activate.csh",
}
BUILD_WRAPPERS = {"gradlew", "mvnw"}  # generated wrappers that download and run the build tool
MAKE_PROGRAMS = {"CC", "CXX", "CPP", "FC", "AR", "AS", "LD", "LEX", "YACC", "RM"}  # run by built-in rules
# make's own variables: they name programs, flags and files, never the targets of a rule.
MAKE_KNOWN = MAKE_PROGRAMS | {
    "CURDIR", "MAKEFILE_LIST", "MAKE", "MAKEFLAGS", "MAKECMDGOALS", "MAKELEVEL", "CFLAGS", "CXXFLAGS",
    "CPPFLAGS", "LDFLAGS", "LDLIBS",
}  # fmt: skip
PACKAGE_RUNNERS = {"npm", "pnpm", "yarn", "bun"}
MAKES = {"make", "gmake", "mingw32-make"}
SOURCES = {".": "bash", "source": "bash", "call": "cmd"}  # run a script in the current shell
MAX_BYTES = 1_000_000
MAX_SHELL_CHARS = 100_000  # a longer shell script is opaque: reading it could outlast the hook timeout
# Options that take a value, so the value is not the script, by family of runner.
VALUE_OPTIONS = {
    "shell": {"-o", "+o", "-O", "+O", "--rcfile", "--init-file"},
    "python": {"-W", "-X", "-Q"},
    "node": {"-r", "--require", "--import", "--loader", "--experimental-loader", "--input-type", "-C"},
    "pwsh": {
        "-executionpolicy", "-ep", "-workingdirectory", "-wd", "-windowstyle", "-w", "-configurationname",
        "-outputformat", "-of", "-inputformat", "-if", "-settingsfile", "-version", "-custompipename",
    },
}  # fmt: skip
BUN_COMMANDS = {
    "run", "test", "build", "install", "i", "add", "remove", "rm", "x", "create", "init", "upgrade", "pm",
    "link", "unlink", "publish", "outdated", "update", "patch", "repl", "exec",
}  # fmt: skip
NPM_LIFECYCLE = {
    "version": ["preversion", "version", "postversion"],
    "pack": ["prepack", "prepare", "postpack"],
    "restart": ["prerestart", "restart", "postrestart", "prestop", "stop", "poststop", "prestart", "start"],
}
# Makefile constructs the reader does not follow: their effect on the recipes is unknown.
MAKE_UNREADABLE = re.compile(
    r"^\s*(-?include|sinclude|define|\.RECIPEPREFIX|\.SHELLFLAGS|(export\s+)?SHELL\s*[:+?!]*=)"
    r"|\$[({](eval|call|foreach|value|file|guile|subst|patsubst)\b",
    re.MULTILINE,
)
MAKE_ASSIGNMENT = re.compile(
    r"^(?:(?:export|override|private)\s+)*([A-Za-z_.][\w.-]*)\s*(:::=|::=|:=|\?=|\+=|!=|=)\s*(.*)$"
)
MAKE_PATH_FUNCTIONS = {"wildcard", "realpath", "abspath", "dir", "notdir", "suffix", "basename", "words"}
MAKE_TEXT_FUNCTIONS = {
    "strip", "findstring", "filter", "filter-out", "sort", "word", "wordlist", "firstword", "lastword",
    "addsuffix", "addprefix", "join", "if", "or", "and", "error", "warning", "info",
}  # fmt: skip
_READING = set()  # files being read higher up in this command: a script that calls itself
_READ = {}  # what each file does, by content stamp; a hook process reads one command
NODE_PRELOADS = {"-r", "--require", "--import", "--loader", "--experimental-loader"}
YARN_COMMANDS = {
    "publish", "pack", "version", "login", "logout", "npm", "dlx", "exec", "why", "info", "config", "link",
    "unlink", "import", "patch", "up", "upgrade", "remove", "rebuild", "audit", "outdated", "list", "ls",
    "store", "init", "create", "env", "bin", "cache", "owner", "team", "tag", "unpublish", "workspace",
    "workspaces",
}  # fmt: skip


def opaque():
    return [shell.request("opaque")]


def local_file(cwd, word, suffixes=()):
    """The existing file a command word names, relative to the session folder; node also tries suffixes."""
    if cwd is None or not word:
        return None
    for candidate in (word, *(word + s for s in suffixes)):
        try:
            file = Path(cwd) / candidate
            if file.is_file():
                return file
        except (OSError, ValueError):
            return None
    return None


@lru_cache(maxsize=4096)
def resolved(path):
    """Path.resolve is slow on Windows; a hook process resolves each path once."""
    return Path(path).resolve()


def inside(cwd, file):
    """Path parts of the file under the session folder, or None when it lies elsewhere."""
    try:
        return resolved(str(file)).relative_to(resolved(str(cwd))).parts
    except (OSError, ValueError):
        return None


def installed(cwd, file):
    return bool(INSTALLED_TOOLS.intersection(inside(cwd, file) or ()))


def committed(cwd, file):
    """The file is tracked by git and unchanged, so its content is in history the person reviews."""
    relative = inside(cwd, file)
    if relative is None:
        return False
    path = "/".join(relative)

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, timeout=3
        )

    try:
        tracked = git("ls-files", "--error-unmatch", "--", path)
        status = git("status", "--porcelain", "--", path)
    except (OSError, subprocess.TimeoutExpired):
        return False  # unknown is read, never trusted
    return tracked.returncode == 0 and status.returncode == 0 and not status.stdout.strip()


def language(file, text, runner=None):
    """How a code file runs: by the program that runs it, else its suffix, else its #! line."""
    if runner:
        return runner
    suffix = file.suffix.lower()
    if suffix == ".py":
        return "python"
    if suffix in SCRIPT_SUFFIXES:
        return "node"
    if suffix in SHELL_SUFFIXES:
        return "bash"
    first = text.splitlines()[0] if text else ""
    words = first[2:].split() if first.startswith("#!") else []
    if words and shell.name_of(words[0]) == "env":
        words = [w for w in words[1:] if not w.startswith("-")]
    return shell.name_of(words[0]) if words else ""


def file_requests(file, allowlist, depth, cwd, runner=None):
    """What running a code file does, read by its language; opaque when the hook cannot read it."""
    try:
        key = resolved(str(file))
        stat = file.stat()
    except OSError:
        return opaque()
    if key in _READING:
        return [shell.request("read-only")]  # already being read higher up: its requests count there
    # One reading per file and process, so scripts that call the same scripts many times stay fast.
    memo = (key, stat.st_mtime_ns, stat.st_size, runner, str(cwd), repr(allowlist))
    if memo not in _READ:
        _READ[memo] = read_file(file, key, allowlist, depth, cwd, runner)
    return _READ[memo]


def read_file(file, key, allowlist, depth, cwd, runner):
    try:
        data = file.read_bytes()[:MAX_BYTES]
    except OSError:
        return opaque()
    text = None if b"\0" in data else data.decode("utf-8", "replace")
    lang = language(file, text, runner)
    if text is None or depth > 3:
        return opaque()
    if lang.startswith("python") or lang == "py":
        return shell.inline_script("python", text)
    if lang in {"node", "deno", "bun"}:
        return shell.inline_script("node", text)
    if lang in shell.SHELLS and len(text) <= MAX_SHELL_CHARS:
        _READING.add(key)
        try:
            return shell.analyze(text, allowlist, depth + 1, cwd)["requests"]
        finally:
            _READING.discard(key)
    return opaque()  # perl, ruby, a long shell script: code the hook does not read


def family(name):
    if name in shell.PYTHONS:
        return "python"
    if name in {"node", "deno", "bun"}:
        return "node"
    return "pwsh" if name in {"pwsh", "powershell"} else "shell"


def script_argument(name, args):
    """The script an interpreter or shell runs: its first argument that is not an option or its value."""
    kind = family(name)
    lowered = [a.lower() for a in args]
    if kind == "pwsh":
        flag = next((f for f in ("-file", "-f") if f in lowered), None)
        if flag:
            i = lowered.index(flag)
            return args[i + 1] if i + 1 < len(args) else None
    i = 0
    while i < len(args):
        a = args[i]
        if set(a) <= set("<>&|0123456789"):
            # Input redirected from a file is the script; any other redirection ends the arguments.
            return args[i + 1] if a == "<" and i + 1 < len(args) else None
        if (lowered[i] if kind == "pwsh" else a) in VALUE_OPTIONS[kind]:
            i += 2
        elif a.startswith(("-", "+")) or (name == "cmd" and a.startswith("/")):
            i += 1
        else:
            return a
    return None


def runner_requests(name, args, piped, allowlist, depth, cwd):
    """A script run by an interpreter, a shell or `source`; None when no script is run."""
    runner = SOURCES.get(name) or (name if name in shell.INTERPRETERS or name in shell.SHELLS else None)
    if runner is None:
        return None
    if name in {"deno", "bun"} and args[:1] == ["run"]:
        args = args[1:]
    elif name == "deno":
        return opaque() if args[:1] in (["task"], ["eval"], ["repl"]) else None
    found = preload_requests(name, args, allowlist, depth, cwd)
    script = script_requests(name, args, runner, piped, allowlist, depth, cwd)
    return None if script is None and not found else found + (script or [])


def preload_requests(name, args, allowlist, depth, cwd):
    """Modules node loads before the script (-r ./x.js, --import ./x.mjs): code that runs too."""
    if family(name) != "node":
        return []
    values = [value for flag, value in zip(args, args[1:]) if flag in NODE_PRELOADS]
    values += [a.split("=", 1)[1] for a in args if a.split("=", 1)[0] in NODE_PRELOADS and "=" in a]
    found = []
    for value in values:
        if value.startswith((".", "/", "\\")) or re.match(r"[A-Za-z]:[\\/]", value):
            file = local_file(cwd, value, SCRIPT_SUFFIXES)
            found += file_requests(file, allowlist, depth, cwd, "node") if file else opaque()
    return found  # shortcut: preloaded packages by name are installed code, not read


def script_requests(name, args, runner, piped, allowlist, depth, cwd):
    """The script file itself; None when the command runs none."""
    word = script_argument(name, args)
    if word is None:
        return opaque() if piped else None  # code arriving on standard input
    if name == "powershell" and not {"-file", "-f"} & {a.lower() for a in args}:
        # Windows PowerShell runs the rest of the line as a command, not as a script file.
        return shell.analyze(" ".join(args[args.index(word) :]), allowlist, depth + 1, cwd)["requests"]
    if name == "bun" and not word.lower().endswith(SCRIPT_SUFFIXES) and local_file(cwd, word) is None:
        return None  # a bun subcommand; installs and package scripts are read elsewhere
    if name in SOURCES:
        word = os.path.expanduser(re.sub(r"^\$(HOME|\{HOME\})", lambda _: str(Path.home()), word))
    file = local_file(cwd, word, SCRIPT_SUFFIXES if family(name) == "node" else ())
    if file is None:
        return opaque()  # it may be written by this same command, after the hook read it
    # The activation script of a virtual environment, whatever the folder is called.
    activate = (
        name in SOURCES
        and file.name.lower() in ACTIVATE_SCRIPTS
        and file.parent.name.lower() in {"bin", "scripts"}
    )
    if installed(cwd, file) or activate or (name in SOURCES and inside(cwd, file) is None):
        # Installed tools, and shell setup sourced from outside the project (~/.bashrc), run unread.
        return [shell.request("read-only")]
    return file_requests(file, allowlist, depth, cwd, runner)


def direct_requests(words, allowlist, depth, cwd):
    """A local file run by its path (./x.sh, uv run x.py) or a local module (python -m x)."""
    i = shell.program_at(words)
    if i >= len(words):
        return None
    word = words[i]
    if i >= 2 and words[i - 1] == "-m" and shell.name_of(words[i - 2]) in shell.PYTHONS:
        base = word.replace(".", "/")
        file = local_file(cwd, base + ".py") or local_file(cwd, base + "/__main__.py")
        return file_requests(file, allowlist, depth, cwd, "python") if file else None
    script = word.lower().endswith(SCRIPT_SUFFIXES + SHELL_SUFFIXES)
    if not (script or re.search(r"[\\/]", word)):
        return None
    file = local_file(cwd, word)
    if file is None:
        # A script that does not exist yet may be written by this same command; a missing program fails.
        return opaque() if script or word.startswith(("./", ".\\")) else None
    if installed(cwd, file) or (not script and inside(cwd, file) is None):
        return None  # an installed tool or a program elsewhere on disk, such as git.exe
    wrapper = shell.name_of(word) in BUILD_WRAPPERS
    if (wrapper or shell.is_test(words)) and committed(cwd, file):
        return None  # an unchanged build or test wrapper from the repository, such as ./gradlew build
    return file_requests(file, allowlist, depth, cwd)


def package_requests(name, args, allowlist, depth, cwd):
    """The package.json scripts npm, pnpm, yarn or bun runs, with their pre and post scripts."""
    if name not in PACKAGE_RUNNERS:
        return None
    folder, words, workspace, i = ".", [], False, 0
    while i < len(args):
        a = args[i]
        key, _, value = a.partition("=")
        if a == "--":
            break  # the rest goes to the script
        if key in {"--prefix", "-C", "--dir", "--cwd", "--filter", "-F", "--workspace", "-w"}:
            value = value or (args[i + 1] if i + 1 < len(args) else "")
            if key in {"--prefix", "-C", "--dir", "--cwd"}:
                folder = value
            else:
                workspace = True
            i += 1 if "=" in a else 2
            continue
        workspace = workspace or key in {"--workspaces", "-ws", "-r", "--recursive"}
        if key == "--script-shell":
            return opaque()  # the scripts would run in a program the hook does not read
        if not a.startswith("-"):
            words.append(a)
        i += 1
    first = words[0].lower() if words else ""
    bare = False
    if name == "yarn" and first in {"workspace", "workspaces"}:
        return opaque()  # scripts of workspace packages are not read
    if first in {"run", "run-script", "rum", "urn"}:
        if len(words) < 2:
            return [shell.request("read-only")]  # lists the scripts
        keys = [f"pre{words[1]}", words[1], f"post{words[1]}"]
    elif name != "bun" and first in {"test", "t", "tst", "start", "stop"}:
        target = {"t": "test", "tst": "test"}.get(first, first)
        keys = [f"pre{target}", target, f"post{target}"]
    elif name == "npm" and first in NPM_LIFECYCLE:
        keys = NPM_LIFECYCLE[first]
    elif name == "bun" and first == "exec":
        return opaque()
    elif name in {"yarn", "pnpm", "bun"} and first and first not in shell.INSTALL.get(name, set()):
        if first in (BUN_COMMANDS if name == "bun" else YARN_COMMANDS):
            return None  # a builtin such as `yarn publish`, judged by its own rule
        keys, bare = [f"pre{words[0]}", words[0], f"post{words[0]}"], True
    else:
        return None
    file = local_file(cwd, str(Path(folder) / "package.json"))
    if file is None:
        return None
    try:
        data = json.loads(file.read_text(encoding="utf-8-sig"))
        scripts = data.get("scripts", {})
    except (OSError, ValueError, AttributeError):
        return opaque()  # npm may still read it, so a file the hook cannot parse is not harmless
    if not isinstance(scripts, dict) or any(not isinstance(scripts.get(k, ""), str) for k in keys):
        return opaque()
    if bare and keys[1] not in scripts:
        return None  # a builtin such as `yarn why`, or bun running a file
    if workspace or script_shell(Path(cwd) / folder):
        return opaque()  # workspace scripts are not read; a configured script shell is not read
    bodies = [scripts[k] for k in keys if k in scripts]
    if keys[1] == "start" and "start" not in scripts:
        bodies.append("node server.js")  # npm's default start
    base = Path(cwd) / folder
    memo = ("package", resolved(str(file)), tuple(bodies), str(base), repr(allowlist))
    if memo not in _READ:  # scripts that call npm run many times are read once
        found = [r for body in bodies for r in shell.analyze(body, allowlist, depth + 1, base)["requests"]]
        _READ[memo] = found or [shell.request("read-only")]
    return _READ[memo]


def script_shell(folder):
    """A .npmrc or .yarnrc in the package folder or above sets the program that runs every script.

    shortcut: the user-level ~/.npmrc is not read; upgrade if a global script shell matters.
    """
    for parent in (folder, *folder.resolve().parents):
        for name in (".npmrc", ".yarnrc", ".yarnrc.yml"):
            try:
                if "script-shell" in (parent / name).read_text(encoding="utf-8", errors="replace").lower():
                    return True
            except OSError:
                continue
    return False


def make_options(words, args):
    """(folder, chosen makefiles, variable overrides, goals, unreadable) from a make command line.

    Unreadable: options and variables that change what runs in a way the reader does not follow.
    """
    folder, chosen, goals, unreadable = ".", [], [], False
    overrides = dict(w.split("=", 1) for w in words[: shell.program_at(words)] if shell.ASSIGNMENT.match(w))
    i = 0
    while i < len(args):
        a = args[i]
        glued = re.match(r"(-C|--directory=|-f|--file=|--makefile=)(.+)$", a)
        if a in {"-C", "--directory", "-f", "--file", "--makefile", "-I", "--include-dir", "-o", "-W"}:
            value = args[i + 1] if i + 1 < len(args) else ""
            if a in {"-C", "--directory"}:
                folder = str(Path(folder) / value)
            elif a in {"-f", "--file", "--makefile"}:
                chosen.append(value)
            i += 2
            continue
        if glued and glued.group(1) in {"-C", "--directory="}:
            folder = str(Path(folder) / glued.group(2))
        elif glued:
            chosen.append(glued.group(2))
        elif "=" in a and not a.startswith("-"):
            key, value = a.split("=", 1)
            overrides[key] = value
        elif a in {"-e", "--environment-overrides", "-E"} or a.startswith("--eval"):
            unreadable = True
        elif not a.startswith("-") and not a.isdigit():  # a number is the value of -j or -l
            goals.append(a)
        i += 1
    # Built-in rules run these variables, so overriding them changes code the reader does not see.
    changed = {"SHELL", ".SHELLFLAGS", "MAKEFILES", "MAKEFLAGS"} | MAKE_PROGRAMS
    unreadable = unreadable or bool(changed & set(overrides))
    return folder, chosen, overrides, goals, unreadable


CYCLE = object()  # a variable being expanded: meeting it again is a cycle


def substitute(value, before, after):
    """$(VAR:a=b): each word ending in a, or matching the % pattern, rewritten as make does."""
    if "%" not in before:
        before, after = "%" + before, "%" + after
    head, _, tail = before.partition("%")
    words = []
    for word in value.split():
        if word.startswith(head) and word.endswith(tail) and len(word) >= len(head) + len(tail):
            stem = word[len(head) : len(word) - len(tail)]
            words.append(after.replace("%", stem, 1) if "%" in after else after)
        else:
            words.append(word)
    return " ".join(words)


def expand(text, variables, level=0, memo=None):
    """Makefile text with variables expanded and $(shell X) as $(X); None when it cannot be followed.

    A variable the Makefile does not define expands to a placeholder, as make expands it to empty;
    one set by an earlier `export` is a declared residual (ADR-0034). Each variable is expanded once
    per memo, and an expansion longer than a script the hook would read is unreadable, so layers of
    variables cannot make the hook outlast its timeout.
    """
    memo = {} if memo is None else memo

    def variable(name):
        if memo.get(name) is CYCLE:
            return None
        if name not in memo:
            memo[name] = CYCLE
            memo[name] = expand(variables[name], variables, level + 1, memo)
        return memo[name]

    if level > 10:
        return None
    out, size, i = [], 0, 0
    while i < len(text):
        c, following = text[i], text[i + 1 : i + 2]
        if c != "$":
            out.append(c)
            i += 1
        elif following == "$":
            out.append("$")
            i += 2
        elif following in {"(", "{"}:
            close = ")" if following == "(" else "}"
            depth, j = 1, i + 2
            while j < len(text) and depth:
                depth += {following: 1, close: -1}.get(text[j], 0)
                j += 1
            if depth:
                return None
            inner = text[i + 2 : j - 1]
            function, _, rest = inner.partition(" ")
            reference = re.fullmatch(r"([\w.-]+):([^=]*)=(.*)", inner)
            if function == "shell":
                value = expand(rest, variables, level + 1, memo)
                value = value and f"$({value})"
            elif inner in variables:
                value = variable(inner)
            elif reference and reference.group(1) in variables:
                value = variable(reference.group(1))
                before = expand(reference.group(2), variables, level + 1, memo)
                after = expand(reference.group(3), variables, level + 1, memo)
                ready = None not in (value, before, after)
                value = substitute(value, before, after) if ready else None
            elif inner == "MAKE":
                value = "make"  # a recursive make is read like any make command
            elif function in MAKE_TEXT_FUNCTIONS:
                value = expand(rest, variables, level + 1, memo)  # every argument: a superset of the result
            elif " " in inner and function not in MAKE_PATH_FUNCTIONS:
                return None  # a function the reader does not follow
            else:
                value = "makevar"  # built-in, automatic, path function or undefined: no command text
            size += len(value or "")
            if value is None or size > MAX_SHELL_CHARS:
                return None
            out.append(value)
            i = j
        elif following and following in "@<^?*+|%":
            out.append("makevar")
            i += 2
        elif following and (following.isalnum() or following == "_"):
            value = variable(following) if following in variables else "makevar"
            size += len(value or "")
            if value is None or size > MAX_SHELL_CHARS:
                return None
            out.append(value)
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


CONDITIONALS = {"ifeq", "ifneq", "ifdef", "ifndef", "else", "endif"}


def make_rules(text):
    """(variables, commands run while reading, rules) of a Makefile; None when it cannot be followed."""
    if MAKE_UNREADABLE.search(text):
        return None
    text = re.sub(r"\\\r?\n[ \t]*", " ", text)
    variables, reading, rules, current = {}, [], [], None
    for line in text.splitlines():
        if line.startswith("\t"):
            (current["commands"] if current else reading).append(line[1:].lstrip("@-+ \t"))
            continue
        line = line.split("#", 1)[0]
        reading += [f"$(shell {m})" for m in re.findall(r"\$[({]shell\s+([^)}]*)[)}]", line)]
        stripped = line.strip()
        if not stripped or stripped.split()[0] in CONDITIONALS:
            continue  # both sides of a conditional are read; a recipe goes on across them
        assignment = MAKE_ASSIGNMENT.match(stripped)
        rule = re.match(r"^([^:=]+?)\s*::?(?!=)\s*(.*)$", stripped)
        current = None
        if assignment:
            key, operator, value = assignment.groups()
            if operator == "!=":
                reading.append(value)
            elif operator == "+=":
                variables[key] = f"{variables.get(key, '')} {value}".strip()
            elif operator != "?=" or key not in variables:
                variables[key] = value
        elif rule:
            prerequisites, _, command = rule.group(2).partition(";")
            # target-specific variables are not rules; `=` inside $(X:a=b) is a substitution
            if "=" not in re.sub(r"\$[({][^)}]*[)}]", "", prerequisites):
                current = dict(targets=rule.group(1).split(), prerequisites=prerequisites, commands=[])
                current["commands"] += [command] if command.strip() else []
                rules.append(current)
    return variables, reading, rules


def built_by_function(text, variables, seen=None):
    """The text builds names the reader cannot follow, directly or in a variable it references.

    That is a make function (addprefix, patsubst) or an undefined variable; path functions such as
    wildcard only list files, and substitution references ($(X:%=p-%)) are expanded by `expand`.
    Each variable is followed once, so a cycle stops; the cost grows with references times text, which
    the 100 000-character limit on the Makefile keeps within the hook timeout.
    """
    seen = set() if seen is None else seen
    calls = re.findall(r"\$[({]([\w-]+)\s", text)
    if any(call not in MAKE_PATH_FUNCTIONS for call in calls):
        return True
    names = re.findall(r"\$[({]([\w.-]+)(?::[^)}]*)?[)}]|\$([A-Za-z_])", text)
    for name in {a or b for a, b in names} - seen:
        seen.add(name)
        if name in MAKE_KNOWN:
            continue  # make's own variables name programs and files, not targets
        if name not in variables or built_by_function(variables[name], variables, seen):
            return True
    return False


def make_commands(text, overrides, goals=()):
    """The shell commands `make goals` can run, expanded; None when the reader cannot follow them.

    The goals and their prerequisites, through explicit rules; a goal without one brings every
    pattern rule. Rules with variables in their targets always count. shortcut: both sides of
    conditionals and every pattern rule, so it may ask more than needed.
    """
    parsed = make_rules(text)
    if parsed is None:
        return None
    variables, reading, rules = parsed
    variables.update(overrides)
    explicit, patterns, dynamic = {}, [], []
    for rule in rules:
        if any("$" in t for t in rule["targets"]):
            dynamic.append(rule)
        elif any("%" in t for t in rule["targets"]):
            patterns.append(rule)
        else:
            for target in rule["targets"]:
                explicit.setdefault(target, []).append(rule)
    first = next((r["targets"][0] for r in rules if not r["targets"][0].startswith(".")), None)
    memo = {}  # each variable expands once for the whole Makefile
    default = (
        expand(variables[".DEFAULT_GOAL"], variables, memo=memo) if ".DEFAULT_GOAL" in variables else first
    )
    pending, seen, chosen = list(goals) or (default or "").split(), set(), list(dynamic)
    unresolved = ".DEFAULT_GOAL" in variables and (
        not pending or built_by_function(variables[".DEFAULT_GOAL"], variables)
    )
    if unresolved and not goals:
        chosen, pending = rules, []  # a default goal the reader cannot resolve: read every rule
    while pending:
        goal = pending.pop()
        if goal in seen:
            continue
        seen.add(goal)
        for rule in explicit.get(goal) or patterns:
            if rule not in chosen:
                chosen.append(rule)
            if built_by_function(rule["prerequisites"], variables):
                chosen = rules  # prerequisites built by a function: read every rule
                pending = []
                break
            prerequisites = expand(rule["prerequisites"], variables, memo=memo)
            if prerequisites is None:
                return None
            pending += [p for p in prerequisites.replace("|", " ").split() if "%" not in p]
    commands = reading + [c for rule in chosen for c in rule["commands"]]
    expanded = [expand(command, variables, memo=memo) for command in commands]
    if any(e is None for e in expanded) or sum(map(len, expanded)) > MAX_SHELL_CHARS:
        return None  # unreadable, or more shell text than the hook can read within its timeout
    return expanded


def make_requests(words, name, args, allowlist, depth, cwd):
    """The commands of the Makefile `make` reads for the goals asked."""
    if name not in MAKES:
        return None
    folder, chosen, overrides, goals, unreadable = make_options(words, args)
    if chosen:
        files = [local_file(cwd, str(Path(folder) / n)) for n in chosen]
        if None in files:
            return opaque()  # a chosen makefile may be written by this same command
    else:
        default = ("GNUmakefile", "makefile", "Makefile")
        found = next((f for n in default if (f := local_file(cwd, str(Path(folder) / n)))), None)
        if found is None:
            return None
        files = [found]
    try:
        stamps = tuple((resolved(str(f)), f.stat().st_mtime_ns, f.stat().st_size) for f in files)
        # Several -f files are read in order as one Makefile, sharing variables.
        text = "\n".join(f.read_text(encoding="utf-8-sig", errors="replace") for f in files)
    except OSError:
        return opaque()
    if len(text) > MAX_SHELL_CHARS:
        return opaque()  # too long to read within the hook timeout
    reading = (stamps, tuple(goals))
    if reading in _READING:
        return [shell.request("read-only")]  # a recursive make into the same goals
    memo = ("make", reading, tuple(sorted(overrides.items())), unreadable, str(cwd), folder, repr(allowlist))
    if memo not in _READ:
        commands = None if unreadable else make_commands(text, overrides, goals)
        if commands is None:
            _READ[memo] = opaque()
        else:
            _READING.add(reading)
            try:
                found = shell.analyze("\n".join(commands), allowlist, depth + 1, Path(cwd) / folder)
                _READ[memo] = found["requests"]
            finally:
                _READING.discard(reading)
    return _READ[memo]


def requests(words, name, args, piped, allowlist, depth, cwd):
    """What the code this command runs indirectly does, or None when it runs no such code."""
    if cwd is None:
        return opaque() if name in SOURCES else None  # without a folder, a sourced script cannot be read
    for found in (
        package_requests(name, args, allowlist, depth, cwd),
        make_requests(words, name, args, allowlist, depth, cwd),
    ):
        if found is not None:
            return found
    found = runner_requests(name, args, piped, allowlist, depth, cwd)
    return found if found is not None else direct_requests(words, allowlist, depth, cwd)


def basename(word):
    return re.split(r"[\\/]", word)[-1].lower()


def files_run(words, cwd):
    """Lowercase names of the files whose code this command would run, existing or not."""
    name, args = shell.program(words)
    names = set()
    if name in PACKAGE_RUNNERS:
        names.add("package.json")
    if name in MAKES:
        chosen = make_options(words, args)[1]
        names |= {basename(c) for c in chosen} if chosen else {"makefile", "gnumakefile"}
    if name in SOURCES or name in shell.INTERPRETERS or name in shell.SHELLS:
        suffixes = ("", *SCRIPT_SUFFIXES) if family(name) == "node" else ("",)
        loaded = [script_argument(name, args)]
        if family(name) == "node":
            loaded += [v for f, v in zip(args, args[1:]) if f in NODE_PRELOADS]
            loaded += [a.split("=", 1)[1] for a in args if a.split("=", 1)[0] in NODE_PRELOADS and "=" in a]
        names |= {basename(w) + s for w in loaded if w for s in suffixes}
    i = shell.program_at(words)
    if 2 <= i < len(words) and words[i - 1] == "-m":
        parts = words[i].lower().split(".")
        names |= {parts[0], parts[-1] + ".py", "__main__.py"}
    elif i < len(words) and re.search(r"[\\/]|\.\w+$", words[i]):
        names.add(basename(words[i]))
    return names - {""}


def harmless_writer(words):
    """Changes a file without changing what it runs: chmod, git add."""
    name, args = shell.program(words)
    sub = next((a for a in args if not a.startswith("-")), "")
    return name in {"chmod", "attrib"} or (name == "git" and sub in {"add", "stage", "commit"})


def rewritten(per_segment, operators, bodies, cwd):
    """Opaque when another part of the command changes a file whose code this part runs.

    The hook read that file before the command ran, so what runs may not be what it read. Later
    parts count only in loops, pipelines and background jobs, which can run before or alongside.
    """
    writers = {
        j: {basename(w) for w in words}
        for j, (words, found) in enumerate(per_segment)
        if any(r["mutation"] for r in found) and not harmless_writer(words)
    }
    embedded = "\n".join(bodies).lower()
    if cwd is None or not (writers or embedded):
        return []  # nothing in the command changes files: what the hook read is what runs
    loop = bool({"&", "|", "|&"} & set(operators)) or any(
        w and shell.name_of(w[0]) in {"for", "while", "until", "do", "done"} for w, _ in per_segment
    )
    for i, (words, _) in enumerate(per_segment):
        for name in files_run(words, cwd):
            mention = re.compile(r"(^|[\s'\"=:/\\<>|;&(])" + re.escape(name) + r"($|[\s'\";|&)<>])")
            if mention.search(embedded):
                return opaque()
            if any(name in names for j, names in writers.items() if j != i and (j < i or loop)):
                return opaque()
    return []
