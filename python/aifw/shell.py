"""Read shell command text for the Claude Code hook: words, segments and the action each one takes.

The text is tokenized like a shell would (quotes, separators, redirections) instead of searched
for patterns, so `git -C . push` is a push and `grep "git push" notes.txt` is a read. Code that
the hook cannot read (eval, encoded commands, text piped into a shell) is reported as opaque.
"""

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
OPAQUE = {"eval", "iex", "invoke-expression", "start-process", "saps", "start", "xargs"}
INTERPRETERS = {"python", "python3", "py", "node", "perl", "ruby", "deno", "bun"}
PUBLISH = {
    "npm": "publish", "pnpm": "publish", "yarn": "publish", "twine": "upload", "docker": "push",
    "podman": "push", "cargo": "publish", "gem": "push", "dart": "publish", "flutter": "publish",
}  # fmt: skip
REMOTE_SHELL = {"ssh", "scp", "sftp", "rsync"}
INSTALL = {
    "npm": {"install", "i", "ci", "add"}, "pnpm": {"install", "i", "add"}, "yarn": {"install", "add"},
    "pip": {"install"}, "pip3": {"install"}, "uv": {"add", "sync", "pip"}, "poetry": {"add", "install"},
    "cargo": {"add", "install"}, "go": {"get", "install"}, "gem": {"install"},
}  # fmt: skip
GIT_LOCAL = {
    "add", "commit", "merge", "rebase", "tag", "stash", "checkout", "switch", "cherry-pick", "revert", "am",
    "fetch", "pull", "clone", "init", "mv", "rm", "restore", "reset", "clean", "branch", "remote", "config",
    "worktree", "submodule", "apply", "notes", "bisect", "gc", "maintenance", "sparse-checkout", "lfs",
}  # fmt: skip
WRAPPERS = {"sudo", "env", "time", "nohup", "command", "exec", "nice", "npx", "pnpx", "bunx"}
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
    "opaque", "destructive", "deploy", "git-remote", "external-write", "secret-read",
    "git-local", "filesystem-write", "external-read", "read-only",
]  # fmt: skip


def request(kind, **extra):
    return dict(kind=kind, mutation=kind not in {"read-only", "external-read", "secret-read"}, **extra)


def service_of(text, allowlist):
    match = URL.search(text or "")
    host = match.group(1).lower() if match else ""
    # shortcut: an allowlisted name matches a host label (github -> api.github.com); map
    # explicit hosts per service if names collide.
    return next((name for name in allowlist if name in host.split(".")), host or "unknown")


def lex(line):
    lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.escape = ""  # keep Windows paths such as C:\Users intact
    return list(lexer)


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
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in GIT_VALUE_OPTIONS else 1
    sub, rest = (args[i], args[i + 1 :]) if i < len(args) else ("", [])
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
    if destructive:
        return [request("filesystem-write", destructive=True)]
    if sub in GIT_READ or (sub in GIT_LISTING and (not rest or rest[0] in LIST_ARGS)):
        return [request("read-only")]
    # Unknown subcommands include aliases, which can expand to anything (git p -> git push).
    return [request("git-local" if sub in GIT_LOCAL else "opaque")]


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


def segment_requests(words, piped, allowlist, depth):
    name, args = program(words)
    lowered = [a.lower() for a in args]
    text = " ".join(words)
    found = []
    inline = inline_code(name, args, lowered) if name in SHELLS else None
    interpreted = name in INTERPRETERS and bool({"-c", "-e", "--eval"} & set(lowered))
    if (
        depth > 3
        or name in OPAQUE
        or interpreted
        or (name in SHELLS and (set(lowered) & ENCODED or (piped and not args)))
    ):
        found.append(request("opaque"))
    elif name in SHELLS and inline is not None:
        found += analyze(inline, allowlist, depth + 1)["requests"]
    elif name == "git":
        found += git_requests(args)
    elif name == "gh":
        if lowered[:1] == ["api"]:
            found.append(http_request(name, args, ["github"] + list(allowlist)))
        elif lowered[:1] in (["pr"], ["release"], ["repo"], ["workflow"], ["issue"]) and len(lowered) > 1:
            read = lowered[1] in {"list", "view", "status", "checks", "diff"}
            found.append(request("external-read" if read else "git-remote", service="github"))
        else:
            found.append(request("read-only"))
    elif name in {"curl", "wget", "invoke-webrequest", "invoke-restmethod", "iwr", "irm"}:
        found.append(http_request(name, args, allowlist))
    elif name in PUBLISH and PUBLISH[name] in lowered[:2]:
        found.append(request("external-write", service="package-registry"))
    elif name in REMOTE_SHELL:
        found.append(request("external-write", service="remote-host"))
    elif name in INSTALL and lowered[:1] and lowered[0] in INSTALL[name]:
        # Dependencies run third-party code; allowlist "package-registry" in aifw.yaml to stop asking.
        found.append(request("external-read", service="package-registry"))
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
        set(lowered) & {"approve", "activate", "decide", "grant"} or lowered[:2] == ["waiver", "add"]
    ):
        found = [dict(r, approval=True) for r in found]
    return found


def rank(item):
    return SEVERITY.index("destructive" if item.get("destructive") else item["kind"])


def analyze(command, allowlist=(), depth=0):
    """The most severe request in the command, with every request under "requests"."""
    parts = segments(command)
    if parts is None:
        found = [request("opaque")]
    else:
        found, previous = [], ""
        for words, operator in parts:
            found += segment_requests(words, previous in {"|", "|&"}, allowlist, depth)
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
