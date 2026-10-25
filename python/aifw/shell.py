"""Read shell command text for the Claude Code hook: words, segments and the action each one takes.

The text is tokenized like a shell would (quotes, separators, redirections) instead of searched
for patterns, so `git -C . push` is a push and `grep "git push" notes.txt` is a read. Code a
command runs indirectly (a script file, a local module, a package.json script, a Makefile recipe)
is read too. Code that the hook cannot read (eval, encoded commands, text piped into a shell, a
binary or a language it does not read) is reported as opaque.
"""

import re
import shlex

from . import indirect

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
    r"(^|[\\/:])(\.env(?!\.(example|sample|template|dist)$)(\.[\w.-]+)?|id_(rsa|dsa|ecdsa|ed25519)|[^\\/]+\.(pem|key|p12|pfx|keystore|jks))$",
    re.I,
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
# Git settings that make git run another program: setting one is running code the hook cannot see.
EXEC_CONFIG = re.compile(
    r"(alias\.|include\.path|includeif\.|credential\.|filter\.|pager\.|hook\.|protocol\.|sequence\.editor"
    r"|diff\.external|web\.browser|uploadpack\.packobjectshook"
    r"|core\.(hookspath|fsmonitor|sshcommand|pager|editor|askpass|gitproxy)|gpg\.(\w+\.)?program"
    r"|diff\.[^.=]+\.(command|textconv)|merge\.[^.=]+\.driver|remote\.[^=]+\.(receivepack|uploadpack)"
    r"|(difftool|mergetool|browser|man|trailer)\.[^=]+\.(cmd|command|path)|submodule\.[^=]+\.update)",
    re.IGNORECASE,
)
# git config options that take a value, so the value is not the key being set.
CONFIG_VALUE_OPTIONS = {"--file", "-f", "--blob", "--type", "--default", "--comment", "--value"}
PUBLISH = {
    "npm": "publish", "pnpm": "publish", "yarn": "publish", "twine": "upload", "docker": "push",
    "podman": "push", "cargo": "publish", "gem": "push", "dart": "publish", "flutter": "publish", "bun": "publish",
    "uv": "publish", "poetry": "publish", "hatch": "publish", "flit": "publish", "pdm": "publish",
    "deno": "publish", "jsr": "publish", "vsce": "publish", "ovsx": "publish", "dotnet": "push", "nuget": "push",}  # fmt: skip
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
    "reflog",  # only `expire` and `delete` get here; plain `git reflog` reads
}  # fmt: skip
WRAPPERS = {"sudo", "env", "time", "nohup", "command", "exec", "nice", "timeout"}
# Wrapper options that take a value, and positional arguments a wrapper reads before the program.
WRAPPER_VALUES = {
    "sudo": {"-u", "-g", "-h", "-p", "-r", "-t", "-U", "-C", "-D"},
    "env": {"-u", "--unset", "-C", "--chdir"},
    "nice": {"-n", "--adjustment"},
    "time": {"-f", "-o", "--format", "--output"},
    "timeout": {"-s", "--signal", "-k", "--kill-after"},
    "uv": {
        "--with", "--with-requirements", "--with-editable", "--python", "-p", "--project", "--directory",
        "--env-file", "--extra", "--group", "--only-group", "--no-group", "--index", "--default-index",
        "--package", "--from",
    },
}  # fmt: skip
WRAPPER_POSITIONALS = {"timeout": 1}
PYTHONS = {"python", "python3", "py"}
READ_ONLY = {
    "cd", "set-location", "pushd", "popd", "ls", "dir", "cat", "type", "head", "tail", "grep", "rg",
    "find", "pwd", "echo", "printf", "wc", "which", "where", "get-childitem", "get-content",
    "select-string", "get-command", "get-location", "less", "more", "stat", "file", "sort", "uniq",
    "diff", "tree", "test", "true", "false", "du", "df", "date", "whoami", "aifw", "write-output",
    "cut", "tr", "nl", "basename", "dirname", "realpath", "sed", "awk", "gawk",  # see edits_files
    "",  # only variable assignments (L=x); $(...) inside them is analyzed on its own
}  # fmt: skip
AWK_INPLACE = re.compile(r"(-i|--include)[ =]?inplace\b")
# An unparenthesized > or | after print/printf is a redirect or a pipe (NR>=310 is a comparison, not one);
# `|&` and system() run commands.
AWK_WRITES = re.compile(r"\bprintf?\b(?:\"[^\"]*\"|[^;}\"])*[>|]|\|&|\bsystem\s*\(")
# Programs that put a file's content in front of the agent: on a secret file they are denied (ADR-0037).
SHOWS_CONTENT = {
    "cat", "type", "get-content", "gc", "less", "more", "head", "tail", "grep", "egrep", "fgrep", "rg",
    "ag", "findstr", "select-string", "sls", "xxd", "od", "hexdump", "strings", "bat", "nl", "awk",
    "gawk", "sed", "cut", "sort", "uniq", "tac", "rev", "base64", "certutil", "diff", "cmp", "comm",
    "jq", "yq", "fold", "column", "iconv", "format-hex",
}  # fmt: skip
GIT_SHOWS = {"show", "diff", "log", "blame", "cat-file", "grep", "annotate"}
SEARCHES = {"grep", "egrep", "fgrep", "rg", "ag", "findstr", "select-string", "sls"}
PATTERN_OPTIONS = {"-e", "--regexp", "-f", "--file", "-pattern"}
REDIRECTS = {">", ">>", ">|", "&>", "&>>", "1>", "2>", "1>>", "2>>"}


def git_subcommand(args):
    """The git subcommand after the global options: `git --no-pager -C . diff` is a diff."""
    i = 0
    while i < len(args) and args[i].startswith("-"):
        i += 2 if args[i] in GIT_VALUE_OPTIONS else 1
    return (args[i].lower(), i) if i < len(args) else ("", i)


def secret_use(name, args):
    """How the command uses a file that usually holds secrets: "read" when it shows the content,
    "mention" when it only names or writes it, None when it names none. A search pattern and a
    redirect target are not reads: `grep .env .gitignore`, `cat .env.example > .env`."""
    lowered = [a.lower() for a in args]
    sub, at = git_subcommand(args) if name == "git" else ("", -1)
    operands = list(range(at + 1, len(args))) if name == "git" else list(range(len(args)))
    if name in SEARCHES or sub == "grep":
        given = [i + 1 for i in operands if lowered[i] in PATTERN_OPTIONS]
        positional = [i for i in operands if not args[i].startswith("-") and args[i] not in REDIRECTS]
        operands = [i for i in operands if i not in (given or positional[:1])]  # the pattern is no file
    written = {i + 1 for i in operands if args[i] in REDIRECTS} | {
        i for i in operands if args[i].startswith(">") and args[i] not in REDIRECTS
    }
    named = [i for i in operands if SECRET_FILE.search(args[i].lstrip(">&|"))]
    if not named:
        return None
    shows = name in SHOWS_CONTENT or sub in GIT_SHOWS
    return "read" if shows and any(i not in written for i in named) else "mention"


GIT_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"}
GIT_READ = {
    "status", "diff", "log", "show", "rev-parse", "ls-files", "ls-tree", "blame", "grep", "describe",
    "shortlog", "cat-file", "show-ref", "for-each-ref", "reflog", "help", "version",
}  # fmt: skip
# The first argument that only lists, per subcommand: `git tag -a` and `git stash -a` create, not list.
GIT_LISTING = {
    "branch": {"-a", "-r", "-v", "-vv", "-l", "--list", "--show-current"},
    "tag": {"-l", "--list", "-n", "-v", "--verify"},
    "remote": {"-v", "show", "get-url"},
    "stash": {"list", "show"},
    "config": {"-l", "--list", "--get", "--get-all", "list", "get"},  # git 2.46+: git config list|get
    "worktree": {"list"},
    "submodule": {"status"},
}
# Options that change something wherever they appear: `git branch -r -d x` deletes, not lists.
GIT_CHANGES = {
    "branch": {
        "-d", "-D", "--delete", "-m", "-M", "--move", "-c", "-C", "--copy", "-u", "--set-upstream-to",
        "--unset-upstream", "--edit-description", "-f", "--force",
    },
    "tag": {"-a", "--annotate", "-s", "--sign", "-u", "--local-user", "-d", "--delete", "-f", "--force", "-m", "-F"},
}  # fmt: skip
# Programs whose job is writing files; any other unknown program is marked as such (ADR-0038).
FILE_WRITERS = {
    "cp", "mv", "touch", "mkdir", "tee", "ln", "install", "rsync", "truncate", "chmod", "chown", "patch",
    "tar", "unzip", "copy", "move", "ren", "rename", "mklink", "copy-item", "cpi", "move-item", "mi",
    "new-item", "ni", "set-content", "sc", "add-content", "ac", "out-file", "rename-item", "rni",
}  # fmt: skip
SEVERITY = [
    "opaque", "destructive", "deploy", "publish", "git-remote", "external-write", "install", "secret-read",
    "signing",
    "commit", "git-local", "filesystem-write", "external-read", "read-only",
]  # fmt: skip


def request(kind, **extra):
    return dict(kind=kind, mutation=kind not in {"read-only", "external-read", "secret-read"}, **extra)


MAVEN_PUBLISH = {"deploy", "deploy:deploy", "deploy:deploy-file", "release:prepare", "release:perform"}
# Options whose next word is a value, not a task or goal, per tool and case-sensitive: gradle -x
# publish skips publishing, while mvn -B and gradle -s are flags.
BUILD_VALUE_OPTIONS = {
    "gradle": {
        "-x", "--exclude-task", "-p", "--project-dir", "-b", "--build-file", "-c", "--settings-file",
        "--group", "--task", "-I", "--init-script", "-g", "--gradle-user-home", "-D", "-P",
    },
    "mvn": {
        "-pl", "--projects", "-f", "--file", "-s", "--settings", "-gs", "--global-settings", "-rf",
        "--resume-from", "-t", "--toolchains", "-P", "--activate-profiles", "-l", "--log-file", "-T",
        "--threads", "-D",
    },
}  # fmt: skip


def build_publishes(name, args):
    """Gradle tasks that publish (publish, :lib:publish, publishToMavenCentral) and Maven deploy goals.

    Publishing to the local repository (publishToMavenLocal) stays local; option values are not tasks.
    """
    tool = {"gradle": "gradle", "gradlew": "gradle", "mvn": "mvn", "mvnw": "mvn"}.get(name)
    if tool is None:
        return False
    tasks, i = [], 0
    while i < len(args):
        a = args[i]
        i += 2 if a in BUILD_VALUE_OPTIONS[tool] else 1
        if not a.startswith("-"):
            tasks.append(a.lower())
    if tool == "mvn":
        return bool(MAVEN_PUBLISH & set(tasks))
    names = [t.rsplit(":", 1)[-1] for t in tasks]
    return any("publish" in t and not t.endswith("tomavenlocal") for t in names)


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
    buffer, joined = "", 0
    for line in command.splitlines():
        buffer, joined = (f"{buffer}\n{line}", joined + 1) if buffer else (line, 0)
        try:
            lex(buffer)
        except ValueError:
            if joined > 200:
                # Re-reading an ever longer open quote would outlast the hook timeout; treat it as unreadable.
                raise ValueError("quote left open for too long") from None
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
    name = re.sub(r"\.(exe|cmd|bat|ps1|com)$", "", name)
    return re.sub(r"^(python3?)\.\d+$", r"\1", name)  # python3.12 is python3


def program_at(words):
    """Index of the word naming the program, after assignments and wrappers such as sudo, uv run and python -m."""
    i = 0
    while i < len(words):
        name = name_of(words[i])
        if ASSIGNMENT.match(words[i]):
            i += 1
        elif name in WRAPPERS or (name == "uv" and words[i + 1 : i + 2] == ["run"]):
            i += 2 if name == "uv" else 1
            values, positionals = WRAPPER_VALUES.get(name, set()), WRAPPER_POSITIONALS.get(name, 0)
            while i < len(words) and (words[i].startswith("-") or positionals):
                if not words[i].startswith("-"):
                    positionals -= 1
                i += 2 if words[i] in values else 1
        elif name in PYTHONS and words[i + 1 : i + 2] == ["-m"] and i + 2 < len(words):
            return i + 2
        else:
            return i
    return i


def env_splits(words):
    """`env -S "cmd args"` splits one word into a command the reader sees as a single program name."""
    head = words[: program_at(words)]
    return any(name_of(w) == "env" for w in head) and any(
        w == "-S" or w.startswith("--split-string") for w in head
    )


# Variables that make a program run another program or load code (ADR-0034).
EXEC_ENVIRONMENT = re.compile(
    r"^(GIT_(SSH|SSH_COMMAND|EXTERNAL_DIFF|PAGER|EDITOR|SEQUENCE_EDITOR|ASKPASS|PROXY_COMMAND|EXEC_PATH"
    r"|TEMPLATE_DIR|CONFIG\w*)|NODE_OPTIONS|BASH_ENV|ENV|PROMPT_COMMAND|LD_PRELOAD|LD_LIBRARY_PATH|DYLD_\w+"
    r"|PYTHONSTARTUP|PERL5OPT|RUBYOPT|EDITOR|VISUAL|PAGER|SHELL|MAKEFLAGS|MAKEFILES|NPM_CONFIG_\w+)=",
    re.IGNORECASE,
)


def exec_environment(words):
    """Sets, on this line or with export, a variable that makes a program run code the hook does not read.

    shortcut: only variables named in EXEC_ENVIRONMENT; a tool's own variables beyond those stay unread.
    """
    i = program_at(words)
    assigned = [w for w in words[:i] if ASSIGNMENT.match(w)]
    if i < len(words) and name_of(words[i]) in {"export", "set", "setx", "declare", "typeset", "readonly"}:
        assigned += words[i + 1 :]  # later commands inherit it
    return any(EXEC_ENVIRONMENT.match(w) and not harmless_setting(w) for w in assigned)


def harmless_setting(word):
    """Common values that run nothing new: GIT_EDITOR=true, GIT_PAGER=cat, NODE_OPTIONS without preloads."""
    key, value = word.split("=", 1)
    key, value = key.upper(), value.strip().strip("'\"")
    if key in {"GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_NOGLOBAL"}:
        return True  # these only switch configuration files off
    if key == "GIT_CONFIG_GLOBAL" or key == "GIT_CONFIG_SYSTEM":
        return value.lower() in {"/dev/null", "nul", ""}
    if key == "NODE_OPTIONS":
        return not re.search(r"(^|\s)(-r|--require|--import|--loader|--experimental-loader)\b", value)
    if key in {"GIT_EDITOR", "GIT_SEQUENCE_EDITOR", "GIT_PAGER", "EDITOR", "VISUAL", "PAGER"}:
        return value in {"", "true", "false", ":", "cat", "less", "less -R", "more"}
    return False


def program(words):
    """(name, args) of the program the words run; python -m X runs X."""
    i = program_at(words)
    return (name_of(words[i]), words[i + 1 :]) if i < len(words) else ("", [])


def git_requests(args):
    i, configs = 0, []
    while i < len(args) and args[i].startswith("-"):
        if args[i] in {"-c", "--config-env"} and i + 1 < len(args):
            configs.append(args[i + 1].lower())
        elif args[i].startswith("--config-env="):
            configs.append(args[i].split("=", 1)[1].lower())
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
    keys, j = [], 0
    while sub == "config" and j < len(rest):
        if not rest[j].startswith("-"):
            keys.append(rest[j])
        j += 2 if rest[j] in CONFIG_VALUE_OPTIONS else 1
    keys = keys[1:] if keys[:1] == ["set"] else keys  # git 2.46+: git config set <key> <value>
    reads = {"--get", "--get-all", "--get-regexp", "--get-urlmatch", "--list", "-l", "--unset", "--unset-all"}
    sets = len(keys) >= 2 and keys[0] not in {"get", "list", "unset"} and not reads.intersection(rest)
    edits = sub == "config" and bool({"-e", "--edit"} & set(rest))  # an editor can write any setting
    if edits or any(EXEC_CONFIG.match(c) for c in configs) or (sets and EXEC_CONFIG.match(keys[0])):
        return [request("opaque")] + signing
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
            a.startswith(("--force", "+", ":"))
            or a in {"--mirror", "--delete", "--prune"}
            or (a.startswith("-") and not a.startswith("--") and set(a[1:]) & {"f", "d"})  # -fu, -df
            for a in rest
        )
        targets, flags, j = [], [], 0
        while j < len(rest):
            if rest[j] in {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}:
                j += 2
                continue
            (flags if rest[j].startswith("-") else targets).append(rest[j])
            j += 1
        # The hook checks where it lands: a work branch runs on its own, the default branch asks (ADR-0037).
        push = request("git-remote", push=dict(targets=targets, flags=flags))
        if configs:  # -c remote.origin.push=HEAD:main and friends redirect the push
            push["protected"] = True
        return [push] + ([request("filesystem-write", destructive=True)] if force else [])
    if sub == "send-pack":  # a push by its plumbing name
        return [request("git-remote", protected=True)]
    if sub == "clone":
        return [request("install")] + signing
    if sub in COMMITS:
        return [request("commit")] + signing
    if destructive:
        return [request("filesystem-write", destructive=True)] + signing
    # A bare `git stash` saves and reverts the working tree; the other bare listings only list.
    changes = GIT_CHANGES.get(sub, set()) & {a.split("=", 1)[0] for a in rest}
    listing = sub in GIT_LISTING and not changes and (rest[0] in GIT_LISTING[sub] if rest else sub != "stash")
    # `git reflog expire` and `delete` drop history; plain `git reflog` reads it.
    reads = sub in GIT_READ and not (sub == "reflog" and rest[:1] in (["expire"], ["delete"]))
    if reads or listing:
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
    url = next(
        (
            a
            for a in args
            if re.match(r"https?://([^/@\s]+@)?(api|uploads)\.github\.com(:\d+)?/", a, re.IGNORECASE)
        ),
        None,
    )
    if write and url:
        return github_write(re.sub(r"^https?://[^/]+", "", url))
    return [request(kind, service=service_of(" ".join(args), allowlist))]


# The GitHub API writes that stay discussion: pull requests, issues, reviews and comments.
GITHUB_DISCUSSION = re.compile(
    r"^/?repos/[^/]+/[^/]+/(pulls|issues)(/\d+(/(comments|reviews(/\d+/events)?|requested_reviewers|labels))?)?/?"
    r"([?#].*)?$|^/?repos/[^/]+/[^/]+/(pulls|issues)/comments/\d+/?$",
    re.IGNORECASE,
)


def github_write(path):
    """A GitHub API write: discussion is an external write; anything else can also reach the default branch."""
    if GITHUB_DISCUSSION.match(path):
        return [request("external-write", service="github", discussion=True)]
    return [
        request("external-write", service="github"),
        request("git-remote", service="github", protected=True),
    ]


def gh_api(args):
    lowered = [a.lower() for a in args]
    method = next((args[i + 1].upper() for i, a in enumerate(lowered[:-1]) if a in {"-x", "--method"}), "")
    method = method or next((a.split("=", 1)[1].upper() for a in lowered if a.startswith("--method=")), "")
    method = method or next((a[2:].upper() for a in args if a.startswith("-X") and len(a) > 2), "")
    fields = any(a in {"-f", "-F", "--field", "--raw-field", "--input"} for a in args) or any(
        a.startswith(("--field=", "--raw-field=", "--input=")) for a in lowered
    )
    valued = {"-q", "--jq", "-t", "--template", "-H", "--header", "-p", "--preview", "--hostname", "--cache"}
    valued |= {"-x", "-X", "--method", "-f", "-F", "--field", "--raw-field", "--input"}
    path, i = "", 1
    while i < len(args):
        if args[i] in valued:
            i += 2
            continue
        if not args[i].startswith("-"):
            path = re.sub(r"^https?://[^/]+", "", args[i])
            break
        i += 1
    # A GraphQL query reads; only a mutation writes, and it can reach anything (merge, refs).
    query = path.strip("/").lower() == "graphql" and not any("mutation" in a for a in lowered)
    if method in {"GET", "HEAD"} or not (method or fields) or query:  # gh api posts when given fields
        return [request("external-read", service="github")]
    return github_write(path)


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


def edits_files(name, args):
    """sed and awk only read, unless sed edits in place (-i, -Ei, --in-place) or an awk program
    edits in place, writes to a file or runs a command.

    shortcut: sed's w and e commands and `cmd | getline` stay reads; upgrade if a script file needs reading.
    """
    if name == "sed":
        return any(a.startswith("--in-place") or (re.match(r"-[^-]", a) and "i" in a) for a in args)
    if name in {"awk", "gawk"}:
        text = " ".join(args)
        return bool(AWK_INPLACE.search(text) or AWK_WRITES.search(text))
    return False


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
    if re.search(r"\baifw\b", code) and (
        re.search(r"approve|activate|decide|grant|add_waiver|verdict|record_chat", code)
        or FORGES.search(code)
    ):
        found = [dict(r, approval=True) for r in found]
    return found


# Feeding the hooks a made-up message would record it as the person's reply (ADR-0037).
FORGES = re.compile(r"UserPromptSubmit|aifw[.-]hooks?\b|from\s+aifw\s+import[^\n;]*\bhooks\b")


def forges_prompt(name, args, text):
    """Running the hook, or a new Claude session, with a message of the agent's choosing."""
    lowered = [a.lower() for a in args]
    # xargs, find -exec and friends run their arguments; other programs only mention the name.
    runs_hook = name in RUNNERS and any(re.search(r"(^|[\s\\/])aifw-hook(\.exe)?(\s|$)", a) for a in lowered)
    module = name.startswith("aifw.hooks") or (  # python -m aifw.hooks arrives as the module
        name in INTERPRETERS and any(a.startswith("aifw.hooks") for a in lowered)
    )
    claude = name == "claude" and bool({"-p", "--print"} & set(lowered))  # a session with a prompt
    return name == "aifw-hook" or runs_hook or module or claude


RUNNERS = {
    "xargs", "find", "busybox", "parallel", "env", "nohup", "timeout", "watch", "nice", "sudo", "doas",
    "time", "start", "stdbuf", "setsid", "exec", "command", "builtin", "strace", "chroot",
}  # fmt: skip


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
        or env_splits(words)
        or exec_environment(words)
    ):
        found.append(request("opaque"))
    elif name in SHELLS and inline is not None:
        found += analyze(inline, allowlist, depth + 1, cwd)["requests"]
    elif (code := indirect.requests(words, name, args, piped, allowlist, depth, cwd)) is not None:
        found += code
    elif name == "git":
        found += git_requests(args)
    elif name in FETCH_AND_RUN:
        found.append(request("install", package=package_name(args)))
    elif name == "gh" and lowered[:2] == ["repo", "clone"]:
        found.append(request("install"))
    elif name == "gh":
        if lowered[:1] == ["api"]:
            found += gh_api(args)
        elif lowered[:1] in (["pr"], ["release"], ["repo"], ["workflow"], ["issue"]) and len(lowered) > 1:
            read = lowered[1] in {"list", "view", "status", "checks", "diff", "download", "checkout"}
            # Opening and discussing pull requests and issues is how branch work reaches the person.
            discuss = lowered[0] in {"pr", "issue"} and lowered[1] in {
                "create", "edit", "comment", "review", "ready", "close", "reopen",
            }  # fmt: skip
            if read:
                found.append(
                    request("external-read", service="github", discussion=lowered[0] in {"pr", "issue"})
                )
            elif discuss:
                found.append(request("external-write", service="github", discussion=True))
            elif lowered[0] == "release":  # create, upload, edit and delete change what users download
                found.append(request("publish", service="github"))
            else:  # merging, repository and workflow changes reach the default branch or settings
                found.append(request("git-remote", service="github", protected=True))
        else:
            found.append(request("read-only"))
    elif name in {"curl", "wget", "invoke-webrequest", "invoke-restmethod", "iwr", "irm"}:
        found += http_request(name, args, allowlist)
    elif prints_environment(words, name, args):
        found.append(request("secret-read"))
    elif (
        (name in PUBLISH and PUBLISH[name] in lowered[:2])
        or build_publishes(name, args)
        or (name in {"docker", "podman"} and "--push" in lowered)  # docker buildx build --push
    ):
        found.append(request("publish", service="package-registry"))  # always asks, allowlist or not
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
        name in READ_ONLY
        and not (name == "find" and {"-exec", "-execdir"} & set(lowered))
        and not edits_files(name, args)
    ):
        found.append(request("read-only"))
    else:
        unknown = name not in FILE_WRITERS and not edits_files(name, args)
        found.append(request("filesystem-write", destructive=False, unknown=unknown))
    if DESTRUCTIVE_SQL.search(text):
        found.append(request("filesystem-write", destructive=True))
    if any(">" in w and set(w) <= set(">&|") for w in words):
        found.append(request("filesystem-write", destructive=False))
    if secret := secret_use(name, args):
        # Showing the content is denied; naming the file (.gitignore, cp .env.example .env) only asks.
        found.append(request("secret-read", mention=secret == "mention"))
    if name == "gh" and lowered[:2] == ["auth", "token"]:  # prints the GitHub token
        found.append(request("secret-read"))
    if (
        name == "aifw"
        and (
            set(lowered) & {"approve", "activate", "decide", "grant", "verdict"}
            or lowered[:2] == ["waiver", "add"]
        )
        or forges_prompt(name, args, text)
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
        found, previous, per_segment, operators = [], "", [], [op for _, op in parts]
        for body in bodies:
            found += analyze(body, allowlist, depth + 1, cwd)["requests"]
        for words, operator in parts:
            here = []
            for _ in [w for w in words if w.startswith("<<") and not w.startswith("<<<")]:
                text, quoted = heredocs.pop(0) if heredocs else ("", True)
                here += heredoc_requests(words, text, quoted, allowlist, depth, cwd)
            here += segment_requests(words, previous in {"|", "|&"}, allowlist, depth, cwd)
            per_segment.append((words, here))
            found += here
            previous = operator
        found += indirect.rewritten(per_segment, operators, bodies, cwd)
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
