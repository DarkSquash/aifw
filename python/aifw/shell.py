"""Read shell command text for the Claude Code hook: words, segments and the action each one takes.

The text is tokenized like a shell would (quotes, separators, redirections) instead of searched
for patterns, so `git -C . push` is a push and `grep "git push" notes.txt` is a read. Code that
the hook cannot read (eval, encoded commands, text piped into a shell) is reported as opaque.
"""

from pathlib import Path
import re
import shlex

SEPARATORS = {"&&", "||", ";", "|", "&", "|&", ";;"}
HARMLESS_REDIRECT = re.compile(r"\d?>&\d|\d?>\s*(/dev/null|\$null|NUL)\b", re.IGNORECASE)
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
URL = re.compile(r"https?://([^/\s'\"]+)")
# Test runners by program name; the first argument that makes the call a test run, if one is needed.
TEST_RUNNERS = {
    "pytest": None, "npm": "test", "pnpm": "test", "yarn": "test", "flutter": "test", "dart": "test",
    "go": "test", "cargo": "test", "dotnet": "test", "mvn": "test", "gradle": "test", "gradlew": "test",
}  # fmt: skip
SECRET_FILE = re.compile(
    r"(^|[\\/])(\.env(\.[\w.-]+)?|id_(rsa|dsa|ecdsa|ed25519)|[^\\/]+\.(pem|key|p12|pfx|keystore|jks))$", re.I
)
DESTRUCTIVE_SQL = re.compile(r"\b(drop\s+(table|database|schema)|truncate\s+table)\b", re.IGNORECASE)

SHELLS = {"bash", "sh", "zsh", "dash", "pwsh", "powershell", "cmd"}
# cmd /c and powershell -Command run the rest of the line; sh -c runs only the next argument.
INLINE = {"-c", "-command", "/c", "/k"}
REST_OF_LINE = {"cmd", "pwsh", "powershell"}
ENCODED = {"-encodedcommand", "-enc", "-ec", "-e"}
# Programs that run code or other programs the hook cannot see.
OPAQUE = {
    "eval",
    "iex",
    "invoke-expression",
    "start-process",
    "saps",
    "start",
    "xargs",
    ".",
    # Pseudo-terminal drivers can type into prompts meant for a person.
    "expect",
    "unbuffer",
    "socat",
    "winpty",
    "faketty",
}
REMOTE_SESSION = {"-computername", "-cn", "-session", "-hostname", "-vmname", "-containerid"}
# Inline Python/JavaScript is read for what it can do; Perl and Ruby stay opaque.
READABLE_INLINE = {"python", "python3", "py", "node", "deno", "bun"}
INLINE_CODE_FLAGS = {"-c", "-e", "--eval", "-p", "--print"}
RUNS_PROGRAMS = re.compile(
    r"subprocess|os\.(system|popen|exec|spawn)|\bpty\b|child_process|exec(Sync|File)?\s*\(|spawn(Sync)?\s*\("
    r"|\beval\s*\(|\bexec\s*\(|__import__|importlib|ctypes|\bFunction\s*\("
)
NETWORK = re.compile(
    r"\b(socket|urllib|http\.client|requests|httpx|aiohttp|smtplib|ftplib|axios|websocket)\b"
    r"|\bfetch\s*\(|https?\.request|\bnet\.connect"
)
WRITES = re.compile(
    r"write_text|write_bytes|open\s*\([^)]*['\"][wax]|shutil|os\.(remove|unlink|rename|replace|mkdir|makedirs)"
    r"|\.unlink\(|rmtree|mkdir\(|fs\.(write|append|rm|unlink|rename|mkdir)|writeFile|appendFile"
)
DELETES = re.compile(r"rmtree|os\.(remove|unlink)|\.unlink\(|fs\.(rm|unlink)")
INTERPRETERS = {"python", "python3", "py", "node", "perl", "ruby", "deno", "bun"}
SCRIPT_SUFFIXES = (".py", ".js", ".mjs", ".cjs", ".ts")
PUBLISH = {
    "npm": "publish", "pnpm": "publish", "yarn": "publish", "twine": "upload", "docker": "push",
    "podman": "push", "cargo": "publish", "gem": "push", "dart": "publish", "flutter": "publish",
}  # fmt: skip
REMOTE_SHELL = {"ssh", "scp", "sftp", "rsync"}
# Installs of packages, programs or new projects always need the person (ADR-0025); `uv sync` only
# restores what uv.lock already pins.
INSTALL = {
    "npm": {"install", "i", "ci", "add", "create", "exec"}, "pnpm": {"install", "i", "add", "create", "dlx"},
    "yarn": {"install", "add", "create", "dlx"}, "bun": {"install", "i", "add", "create", "x"},
    "pip": {"install"}, "pip3": {"install"}, "uv": {"add", "pip", "tool"}, "pipx": {"install", "run"},
    "poetry": {"add", "install"}, "conda": {"install", "create"}, "cargo": {"add", "install"},
    "go": {"get", "install"}, "gem": {"install"}, "composer": {"require", "install", "create-project"},
    "flutter": {"pub"}, "dart": {"pub"}, "winget": {"install", "upgrade"}, "choco": {"install", "upgrade"},
    "scoop": {"install", "update"}, "apt": {"install"}, "apt-get": {"install"}, "brew": {"install", "upgrade"},
    "snap": {"install"}, "dnf": {"install"}, "yum": {"install"}, "pacman": {"-s", "-sy", "-syu"},
}  # fmt: skip
FETCH_AND_RUN = {"npx", "pnpx", "bunx", "uvx"}  # download a package and run it
# Commands that create or rewrite commits; the person reviews every commit (ADR-0025).
COMMITS = {"commit", "merge", "rebase", "cherry-pick", "revert", "am"}
GIT_LOCAL = {
    "add", "commit", "merge", "rebase", "tag", "stash", "checkout", "switch", "cherry-pick", "revert", "am",
    "fetch", "pull", "clone", "init", "mv", "rm", "restore", "reset", "clean", "branch", "remote", "config",
    "worktree", "submodule", "apply", "notes", "bisect", "gc", "maintenance", "sparse-checkout", "lfs",
}  # fmt: skip
WRAPPERS = {"sudo", "env", "time", "nohup", "command", "exec", "nice"}
PYTHONS = {"python", "python3", "py"}
READ_ONLY = {
    "cd", "set-location", "pushd", "popd", "ls", "dir", "cat", "type", "head", "tail", "grep", "rg",
    "find", "pwd", "echo", "printf", "wc", "which", "where", "get-childitem", "get-content",
    "select-string", "get-command", "get-location", "less", "more", "stat", "file", "sort", "uniq",
    "diff", "tree", "test", "true", "false", "du", "df", "date", "whoami", "aifw", "write-output",
}  # fmt: skip
GIT_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"}
GIT_READ = {
    "status", "diff", "log", "show", "rev-parse", "ls-files", "ls-tree", "blame", "grep", "describe",
    "shortlog", "cat-file", "show-ref", "for-each-ref", "reflog", "help", "version",
}  # fmt: skip
GIT_LISTING = {"branch", "tag", "remote", "stash", "config", "worktree", "submodule"}
LIST_ARGS = {"-a", "-r", "-v", "-vv", "-l", "--list", "list", "show", "--show-current", "--get", "--get-all"}
SEVERITY = [
    "opaque", "destructive", "deploy", "git-remote", "external-write", "install", "secret-read", "signing",
    "commit", "git-local", "filesystem-write", "external-read", "read-only",
]  # fmt: skip


def request(kind, **extra):
    return dict(kind=kind, mutation=kind not in {"read-only", "external-read", "secret-read"}, **extra)


def prints_environment(words, name, args):
    """Commands that print environment variables, where tokens and passwords often live."""
    lowered = [a.lower() for a in args]
    return (
        name == "printenv"
        or (name in {"set", "export"} and lowered in ([], ["-p"]))
        or (not name and words and name_of(words[0]) == "env")
        or (
            name in {"get-childitem", "gci", "dir", "ls", "get-item", "gi"}
            and any(a.startswith("env:") for a in lowered)
        )
    )


# Domains each allowlisted service name stands for; a name with a dot is a domain itself.
SERVICE_DOMAINS = {
    "github": ["github.com", "githubusercontent.com", "githubassets.com"],
    "gitlab": ["gitlab.com"],
    "context7": ["context7.com"],
    "npm": ["npmjs.org", "npmjs.com"],
    "pypi": ["pypi.org", "pythonhosted.org"],
    "openrouter": ["openrouter.ai"],
}


def domains_for(allowlist):
    if isinstance(allowlist, dict):
        return allowlist
    return {name: SERVICE_DOMAINS.get(name, [name] if "." in name else []) for name in allowlist}


def service_of(text, allowlist):
    match = URL.search(text or "")
    host = match.group(1).lower().split(":")[0] if match else ""
    known = domains_for(allowlist)
    return next(
        (
            name
            for name, domains in known.items()
            if any(host == d or host.endswith("." + d) for d in domains)
        ),
        host or "unknown",
    )


def lex(line):
    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.escape = ""  # keep Windows paths such as C:\Users intact
    return list(lexer)


HEREDOC = re.compile(r"(?<!<)<<(-?)\s*(['\"]?)([A-Za-z_][\w-]*)\2")


def split_heredocs(command):
    """The command without heredoc bodies, and each body in order as (text, quoted).

    A body is input for its command, not shell code: `cat > notes.md <<'EOF'` writes text that
    may mention `git push` without pushing anything.
    """
    lines, kept, bodies, i = command.splitlines(), [], [], 0
    while i < len(lines):
        line = lines[i]
        kept.append(line)
        i += 1
        for strip_tabs, quote, delimiter in HEREDOC.findall(line):
            body = []
            while i < len(lines) and (lines[i].lstrip("\t") if strip_tabs else lines[i]) != delimiter:
                body.append(lines[i])
                i += 1
            i += 1  # the delimiter line
            bodies.append(("\n".join(body), bool(quote)))
    return "\n".join(kept), bodies


def heredoc_requests(words, body, quoted, allowlist, depth, cwd):
    """A heredoc runs as code only when it feeds an interpreter or a shell; otherwise it is data."""
    name, _ = program([w for w in words if not w.startswith("<<")])
    if name in READABLE_INLINE:
        return inline_script(name, body)
    if name in SHELLS or name in INTERPRETERS:
        return analyze(body, allowlist, depth + 1, cwd)["requests"]
    if quoted:
        return []
    # Unquoted bodies still expand $(...) and backticks before the command reads them.
    _, embedded = split_embedded(body)
    return [r for code in embedded for r in analyze(code, allowlist, depth + 1, cwd)["requests"]]


def logical_lines(command):
    """Physical lines joined across continuations and open quotes."""
    command = re.sub(r"(\\|`)\r?\n", " ", HARMLESS_REDIRECT.sub(" ", command))
    buffer = ""
    for line in command.splitlines():
        buffer = f"{buffer}\n{line}" if buffer else line
        try:
            lex(buffer)
        except ValueError:
            continue
        yield buffer
        buffer = ""
    if buffer:
        raise ValueError("unterminated quote")


def segments(command):
    """[(words, operator after)] for each simple command; the last operator is "". None if unreadable."""
    out = []
    try:
        for line in logical_lines(command):
            words = []
            for token in lex(line):
                if token in SEPARATORS:
                    out.append((words, token))
                    words = []
                else:
                    words.append(token)
            out.append((words, ";"))
    except ValueError:
        return None
    out = [(w, op) for w, op in out if w]
    if out:
        out[-1] = (out[-1][0], "")
    return out


EMBEDDED = "__aifw_embedded__"
BLOCK = "__aifw_block__"


def split_embedded(command):
    """Command text with embedded code replaced by a placeholder, plus each embedded body."""
    out, bodies, quote, i = [], [], None, 0
    while i < len(command):
        c = command[i]
        if quote == "'":
            quote = None if c == "'" else quote
            out.append(c)
            i += 1
            continue
        if c in "'\"" and quote in (None, c):
            quote = None if quote == c else c
            out.append(c)
            i += 1
            continue
        if c == "`":
            end = command.find("`", i + 1)
            if end < 0:
                raise ValueError("unterminated backtick")
            bodies.append(command[i + 1 : end])
            out.append(f" {EMBEDDED} ")
            i = end + 1
            continue
        process = command.startswith(("$(", "<(", ">("), i) and not command.startswith("$((", i)
        block = c == "{" and quote is None and (i == 0 or command[i - 1] not in "$@")
        if process or block:
            opener, close = ("(", ")") if process else ("{", "}")
            start = i + (2 if process else 1)
            depth, j = 1, start
            while j < len(command) and depth:
                depth += {opener: 1, close: -1}.get(command[j], 0)
                j += 1
            if depth:
                raise ValueError("unbalanced embedded code")
            body = command[start : j - 1]
            if process or any(ch.isspace() for ch in body.strip()) or ";" in body:
                bodies.append(body)  # brace expansion such as {a,b} is not code
                out.append(f" {EMBEDDED if process else BLOCK} ")
            else:
                out.append(command[i:j])
            i = j
            continue
        out.append(c)
        i += 1
    return "".join(out), bodies


def name_of(word):
    name = re.split(r"[\\/]", word)[-1].lower()
    return re.sub(r"\.(exe|cmd|bat|ps1|com)$", "", name)


def program(words):
    """(name, args) after variable assignments and wrappers such as sudo, uv run, python -m and npx."""
    i = 0
    while i < len(words):
        name = name_of(words[i])
        if ASSIGNMENT.match(words[i]):
            i += 1
        elif name in WRAPPERS or (name == "uv" and words[i + 1 : i + 2] == ["run"]):
            i += 2 if name == "uv" else 1
            while i < len(words) and words[i].startswith("-"):
                i += 1
        elif name in PYTHONS and words[i + 1 : i + 2] == ["-m"] and i + 2 < len(words):
            return name_of(words[i + 2]), words[i + 3 :]
        else:
            return name, words[i + 1 :]
    return "", []


def git_requests(args):
    i, configs = 0, []
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "-c" and i + 1 < len(args):
            configs.append(args[i + 1].lower())
        i += 2 if args[i] in GIT_VALUE_OPTIONS else 1
    sub, rest = (args[i], args[i + 1 :]) if i < len(args) else ("", [])
    signs = any(c.startswith(("commit.gpgsign=true", "tag.gpgsign=true")) for c in configs) or (
        sub in {"commit", "tag", "merge", "rebase", "revert", "cherry-pick", "am"}
        and any(
            a.startswith(("-S", "--gpg-sign"))
            or (sub == "tag" and a in {"-s", "--sign", "-u", "--local-user"})
            for a in rest
        )
    )
    signing = [request("signing")] if signs else []
    destructive = (
        (sub == "reset" and "--hard" in rest)
        or (
            sub == "clean"
            and any(
                a == "--force" or (a.startswith("-") and not a.startswith("--") and "f" in a) for a in rest
            )
        )
        or (sub == "branch" and any(a in {"-D", "--force"} for a in rest))
        or (sub in {"checkout", "restore"} and ("--" in rest or sub == "restore") and "--staged" not in rest)
        or (sub == "stash" and rest[:1] in (["drop"], ["clear"]))
    )
    if sub == "push":
        force = any(
            a.startswith(("--force", "+", ":")) or a in {"-f", "--mirror", "--delete", "-d", "--prune"}
            for a in rest
        )
        return [request("git-remote")] + ([request("filesystem-write", destructive=True)] if force else [])
    if sub == "clone":
        return [request("install")] + signing
    if sub in COMMITS:
        return [request("commit")] + signing
    if destructive:
        return [request("filesystem-write", destructive=True)] + signing
    if sub in GIT_READ or (sub in GIT_LISTING and (not rest or rest[0] in LIST_ARGS)):
        return [request("read-only")]
    # Unknown subcommands include aliases, which can expand to anything (git p -> git push).
    return [request("git-local" if sub in GIT_LOCAL else "opaque")] + signing


def http_request(name, args, allowlist):
    lowered = [a.lower() for a in args]
    method = next(
        (args[i + 1].upper() for i, a in enumerate(lowered[:-1]) if a in {"-x", "--request", "-method"}), ""
    )
    method = method or next((a[2:].upper() for a in args if a.startswith("-X") and len(a) > 2), "")
    write = method in {"POST", "PUT", "PATCH", "DELETE"} or any(
        a.startswith(("--data", "--form", "--upload-file", "--json", "--post-")) or a in {"-d", "-F", "-T"}
        for a in args
    )
    kind = "external-write" if write else "external-read"
    return request(kind, service=service_of(" ".join(args), allowlist))


def deletion(name, args):
    lowered = [a.lower() for a in args]
    if name == "rm":
        short = [a[1:] for a in args if a.startswith("-") and not a.startswith("--")]
        return any(set(f) & {"r", "R", "f"} for f in short) or bool({"--recursive", "--force"} & set(lowered))
    if name in {"remove-item", "ri"}:
        return any(a.startswith(("-r", "-fo")) for a in lowered)
    if name in {"del", "erase"}:
        return bool({"/s", "/q"} & set(lowered))
    if name in {"rmdir", "rd"}:
        return "/s" in lowered or any(a.startswith("-") and "r" in a for a in lowered)
    return name in {"shred", "mkfs", "format", "dd"}


def deploy(name, args):
    lowered = [a.lower() for a in args]
    if name in {"vercel", "netlify"}:
        if name == "vercel" or "deploy" in lowered:
            return "production" if "--prod" in lowered else "preview"
    if name in {"firebase", "fly", "flyctl"} and "deploy" in lowered:
        return "production"
    if name in {"terraform", "tofu"} and lowered[:1] in (["apply"], ["destroy"]):
        return "production"
    if name == "kubectl" and lowered[:1] in (["apply"], ["delete"], ["replace"], ["rollout"]):
        return "production"
    if name == "helm" and lowered[:1] in (["install"], ["upgrade"], ["uninstall"], ["rollback"]):
        return "production"
    if name == "gcloud" and "deploy" in lowered:
        return "production"
    return None


def is_test(words):
    """The command itself runs a test runner or `aifw validate`; an argument that merely names one does not."""
    name, args = program(words)
    lowered = [a.lower() for a in args]
    if name == "aifw":
        return lowered[:1] == ["validate"]
    if name not in TEST_RUNNERS:
        return False
    first = TEST_RUNNERS[name]
    return first is None or lowered[:1] == [first] or lowered[:2] in (["run", "test"], ["run", first])


def inline_code(name, args, lowered):
    index = next((i for i, a in enumerate(lowered[:-1]) if a in INLINE), None)
    if index is None:
        return None
    return " ".join(args[index + 1 :]) if name in REST_OF_LINE else args[index + 1]


def script_command(args):
    """The command `script` runs: -c CMD, --command CMD or a short cluster ending in c (-qc, -qec)."""
    for i, a in enumerate(args):
        if a.startswith("--command="):
            return a.split("=", 1)[1]
        if (
            a == "--command" or (a.startswith("-") and not a.startswith("--") and a.endswith("c"))
        ) and i + 1 < len(args):
            return args[i + 1]
    return None


def inline_script(name, code):
    """What inline Python or JavaScript can do, read from its text."""
    found = []
    if RUNS_PROGRAMS.search(code):
        found.append(request("opaque"))
    if NETWORK.search(code):
        found.append(request("external-write", service="unknown"))  # can send data anywhere
    if WRITES.search(code):
        found.append(request("filesystem-write", destructive=bool(DELETES.search(code))))
    found = found or [request("read-only")]
    # Approvals belong to the person, so they are flagged even inside code that also runs programs.
    if re.search(r"\baifw\b", code) and re.search(r"approve|activate|decide|grant|add_waiver|verdict", code):
        found = [dict(r, approval=True) for r in found]
    return found


def script_source(cwd, args):
    """Text of the script file an interpreter runs, read like inline code.

    shortcut: only the file named on the command line, relative to the session folder; modules it
    imports and scripts run after a `cd` stay unread, upgrade by following imports if that matters.
    """
    target = next((a for a in args if not a.startswith("-")), None)
    if cwd is None or not target or not target.lower().endswith(SCRIPT_SUFFIXES):
        return None
    try:
        file = Path(cwd) / target
        return file.read_text(encoding="utf-8", errors="replace")[:1_000_000] if file.is_file() else None
    except OSError:
        return None


def package_name(args):
    """The package npx and friends would run: `ctx7@latest` is ctx7, `@scope/tool@1` is @scope/tool."""
    if any(
        a in {"-p", "--package", "--from", "--with"} or a.startswith(("--package=", "--from=")) for a in args
    ):
        return None  # the command name no longer says which package gets installed
    target = next((a for a in args if not a.startswith("-")), "")
    return target.rsplit("@", 1)[0] if target.rfind("@") > 0 else target


def segment_requests(words, piped, allowlist, depth, cwd=None):
    name, args = program(words)
    lowered = [a.lower() for a in args]
    text = " ".join(words)
    found = []
    inline = inline_code(name, args, lowered) if name in SHELLS else None
    interpreted = name in INTERPRETERS and bool(INLINE_CODE_FLAGS & set(lowered))
    code = next((args[i + 1] for i, a in enumerate(lowered[:-1]) if a in INLINE_CODE_FLAGS), None)
    if name == BLOCK:
        found.append(request("read-only"))
    elif name in READABLE_INLINE and code is not None and depth <= 3:
        found += inline_script(name, code)
    elif name in READABLE_INLINE and not interpreted and (source := script_source(cwd, args)) is not None:
        found += inline_script(name, source)
    elif name == "script" and script_command(args) is not None and depth <= 3:
        found += analyze(script_command(args), allowlist, depth + 1, cwd)["requests"]
    elif name in {"invoke-command", "icm", "enter-pssession", "new-pssession"}:
        remote = name != "invoke-command" and name != "icm" or bool(REMOTE_SESSION & set(lowered))
        found.append(request("external-write", service="remote-host") if remote else request("read-only"))
    elif (
        depth > 3
        or name in OPAQUE
        or name.startswith(("$", "%"))
        or name == EMBEDDED
        or interpreted
        or name == "script"
        or (name in SHELLS and (set(lowered) & ENCODED or (piped and not args)))
    ):
        found.append(request("opaque"))
    elif name in SHELLS and inline is not None:
        found += analyze(inline, allowlist, depth + 1, cwd)["requests"]
    elif name == "git":
        found += git_requests(args)
    elif name in FETCH_AND_RUN:
        found.append(request("install", package=package_name(args)))
    elif name == "gh" and lowered[:2] == ["repo", "clone"]:
        found.append(request("install"))
    elif name == "gh":
        if lowered[:1] == ["api"]:
            found.append(dict(http_request(name, args, allowlist), service="github"))
        elif lowered[:1] in (["pr"], ["release"], ["repo"], ["workflow"], ["issue"]) and len(lowered) > 1:
            read = lowered[1] in {"list", "view", "status", "checks", "diff"}
            found.append(request("external-read" if read else "git-remote", service="github"))
        else:
            found.append(request("read-only"))
    elif name in {"curl", "wget", "invoke-webrequest", "invoke-restmethod", "iwr", "irm"}:
        found.append(http_request(name, args, allowlist))
    elif prints_environment(words, name, args):
        found.append(request("secret-read"))
    elif name in PUBLISH and PUBLISH[name] in lowered[:2]:
        found.append(request("external-write", service="package-registry"))
    elif name in REMOTE_SHELL:
        found.append(request("external-write", service="remote-host"))
    elif name in INSTALL and lowered[:1] and lowered[0] in INSTALL[name]:
        found.append(request("install"))
    elif deletion(name, args):
        found.append(request("filesystem-write", destructive=True))
    elif environment := deploy(name, args):
        found.append(request("deploy", environment=environment))
    elif name == "find" and "-delete" in lowered:
        found.append(request("filesystem-write", destructive=True))
    elif is_test(words) or (
        name in READ_ONLY and not (name == "find" and {"-exec", "-execdir"} & set(lowered))
    ):
        found.append(request("read-only"))
    else:
        found.append(request("filesystem-write", destructive=False))
    if DESTRUCTIVE_SQL.search(text):
        found.append(request("filesystem-write", destructive=True))
    if any(">" in w and set(w) <= set(">&|") for w in words):
        found.append(request("filesystem-write", destructive=False))
    if any(SECRET_FILE.search(w) for w in args):
        found.append(request("secret-read"))
    if name == "aifw" and (
        set(lowered) & {"approve", "activate", "decide", "grant", "verdict"}
        or lowered[:2] == ["waiver", "add"]
    ):
        found = [dict(r, approval=True) for r in found]
    return found


def rank(item):
    return SEVERITY.index("destructive" if item.get("destructive") else item["kind"])


def analyze(command, allowlist=(), depth=0, cwd=None):
    """The most severe request in the command, with every request under "requests"."""
    command, heredocs = split_heredocs(command)
    try:
        command, bodies = split_embedded(command)
    except ValueError:
        bodies, command = [], None
    parts = segments(command) if command is not None and depth <= 3 else None
    if parts is None:
        found = [request("opaque")]
    else:
        found, previous = [], ""
        for body in bodies:
            found += analyze(body, allowlist, depth + 1, cwd)["requests"]
        for words, operator in parts:
            for _ in [w for w in words if w.startswith("<<") and not w.startswith("<<<")]:
                text, quoted = heredocs.pop(0) if heredocs else ("", True)
                found += heredoc_requests(words, text, quoted, allowlist, depth, cwd)
            found += segment_requests(words, previous in {"|", "|&"}, allowlist, depth, cwd)
            previous = operator
    found = found or [request("read-only")]
    dominant = min(found, key=rank)
    return dict(
        dominant,
        mutation=any(r["mutation"] for r in found),
        approval=any(r.get("approval") for r in found),
        requests=found,
    )


def runs_tests(command):
    parts = segments(command) or []
    return any(is_test(words) for words, _ in parts)


def verification_visible(command):
    """False when the exit status of the last test command is hidden by a later | ; || or &."""
    parts = segments(command)
    if not parts:
        return False
    tests = [i for i, (words, _) in enumerate(parts) if is_test(words)]
    if not tests:
        return True
    pipefail = "pipefail" in command
    after = [operator for _, operator in parts[tests[-1] : -1]]
    return all(op == "&&" or (op in {"|", "|&"} and pipefail) for op in after)
