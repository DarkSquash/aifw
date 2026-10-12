"""Local documentation inventory and dependency selection, without executing project code.

Documents are untrusted context, never authority. Outputs contain references and
redacted metadata, not document bodies. Snapshots detect drift, not correctness.
"""

from hashlib import sha256
from math import ceil
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from .common import API, AifwError, parse_yaml, read_json, require, validate, write_json
from .discovery import inventory

INDEX = ".aifw/context-index.json"


def redact(value):
    for pattern in (
        r"\bsk-[A-Za-z0-9_-]{8,}\b",
        r"\bBearer\s+[A-Za-z0-9._~+/-]+=*\b",
        r"\b(api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*[^\s,;]+",
    ):
        value = re.sub(pattern, "[REDACTED]", value, flags=re.IGNORECASE)
    return value


MAX_BYTES = 1_000_000
EXCLUDED = {
    ".git",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "test-results",
    "playwright-report",
    "_archive",
    "archive",
    ".venv",
    "venv",
    "__pycache__",
}


def safe_path(root, name):
    """Reject secrets, external paths and symlink/junction escapes before any read."""
    root = Path(root).resolve()
    require(isinstance(name, str) and name.strip(), "A local file reference is required.")
    name = name.replace("\\", "/")
    parts = Path(name).parts
    require(not Path(name).is_absolute() and not re.match(r"^[A-Za-z]:", name), "External path rejected.")
    require(
        not any(c in name for c in ("\x00", "\n", "\r", "`", "*", "?", "<", ">")), "Invalid local reference."
    )
    require(
        not any(p.lower().startswith(".env") or p.lower() in EXCLUDED for p in parts),
        "Restricted file reference.",
    )
    require(Path(name).suffix.lower() not in {".pem", ".key", ".p12", ".pfx"}, "Restricted file reference.")
    target = root / name
    require(target.resolve().is_relative_to(root), "External path rejected.")
    for parent in [target, *target.parents]:
        if parent == root:
            break
        require(not parent.is_symlink(), "Symbolic link rejected.")
    return target


def fingerprint(path):
    require(
        path.is_file() and path.stat().st_size <= MAX_BYTES, "File missing or exceeds context size limit."
    )
    return sha256(path.read_bytes()).hexdigest()


def clean_metadata(text):
    text = redact(text)
    text = re.sub(r"\b(?:gh[pousr]_|github_pat_|sbp_)[A-Za-z0-9_-]{8,}", "[REDACTED]", text)
    text = re.sub(r"eyJ[\w-]+\.[\w-]+\.[\w-]+", "[REDACTED]", text)
    return text[:1000]


def values(meta, key):
    value = meta.get(key, [])
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    require(isinstance(value, list) and all(isinstance(v, str) for v in value), "Invalid metadata field.")
    return value


def resolve_reference(root, document, reference):
    reference = unquote(reference.strip().strip("<>"))
    parsed = urlsplit(reference)
    if parsed.scheme or parsed.netloc or reference.startswith("#"):
        return None
    name = parsed.path
    if not name:
        return None
    parent = Path(document).parent
    candidates = (
        [Path(name), parent / name, Path("docs") / name]
        if name.startswith(("src/", "docs/", ".aifw/"))
        else [parent / name, Path("docs") / name, Path(name)]
    )
    # Explicit traversal is interpreted relative to the document, never silently rebased.
    if name.startswith("."):
        candidates = [parent / name]
    paths = [safe_path(root, p.as_posix()) for p in candidates]
    chosen = next((p for p in paths if p.exists()), paths[0])
    return chosen.resolve().relative_to(Path(root).resolve()).as_posix()


def references(body):
    body = re.sub(r"(?ms)^\s*(`{3,}|~{3,})[^\n]*\n.*?^\s*\1\s*$", "", body)
    links = re.findall(r"\[[^\]\n]*\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)", body)
    links += re.findall(r"(?m)^\s*\[[^\]]+\]:\s*(\S+)", body)
    # Literal code paths only: patterns and placeholders are examples, not contracts.
    links += [
        p
        for p in re.findall(r"`([^`\n]+)`", body)
        if re.fullmatch(r"(?:\.?\.?/|src/|docs/|python/|tests/|scripts/)[\w./-]+\.[\w]+", p)
    ]
    return links


def build_index(root, write=False):
    root = Path(root).resolve()
    names = [
        n
        for n in inventory(root)
        if n.endswith(".md")
        and (n.startswith("docs/") or n in {"AGENTS.md", "CLAUDE.md", "README.md"})
        and not any(p in EXCLUDED for p in Path(n).parts)
    ]
    documents, findings = [], []
    for name in names:

        def issue(code, severity="error", target=None):
            finding = dict(code=code, path=name, severity=severity)
            if target is not None:
                finding["target"] = target
            findings.append(finding)

        try:
            file = safe_path(root, name)
            file_hash = fingerprint(file)
            text = file.read_text(encoding="utf-8-sig")
        except (AifwError, OSError, UnicodeError):
            issue("UNREADABLE_DOCUMENT")
            continue
        meta, body = {}, text
        if text.startswith("---\n") or text.startswith("---\r\n"):
            header = re.match(r"\A---\s*\n(.*?)\n---(?:\s*\n|$)", text, re.S)
            try:
                require(header is not None, "Unclosed frontmatter.")
                meta = parse_yaml(header[1]) or {}
                require(isinstance(meta, dict), "Metadata must be a mapping.")
                require(isinstance(meta.get("scope", ""), str), "Scope must be text.")
                for key in ("depends-on", "sources", "intents"):
                    values(meta, key)
                require(isinstance(meta.get("required", False), bool), "Required must be boolean.")
                body = text[header.end() :]
            except (AifwError, TypeError, ValueError):
                issue("INVALID_METADATA")
                continue
        dependencies, sources, hashes = [], [], {}
        refs = [(r, "dependency") for r in values(meta, "depends-on")]
        refs += [(r, "source") for r in values(meta, "sources")]
        refs += [(r, "link") for r in references(body)]
        for ref, kind in refs:
            try:
                resolved = resolve_reference(root, name, ref)
                if resolved is None:
                    if kind != "link":
                        issue("RESTRICTED_REFERENCE")
                    continue
                target = safe_path(root, resolved)
                if not target.is_file() and not (kind == "link" and target.is_dir()):
                    issue("BROKEN_REFERENCE", target=resolved)
                elif kind != "link":
                    hashes[resolved] = fingerprint(target)
                if kind == "dependency":
                    dependencies.append(resolved)
                elif kind == "source":
                    sources.append(resolved)
            except (AifwError, OSError, ValueError):
                issue("RESTRICTED_REFERENCE")
        heading = re.search(r"(?m)^#\s+(.+)$", body)
        scope = meta.get("scope", "") or (heading[1] if heading else "")
        documents.append(
            dict(
                path=name,
                scope=clean_metadata(scope),
                intents=[clean_metadata(v) for v in values(meta, "intents")],
                required=meta.get("required", False),
                dependencies=sorted(set(dependencies)),
                sources=sorted(set(sources)),
                sourceHashes=hashes,
                sha256=file_hash,
                estimatedTokens=ceil(len(text) / 4),
            )
        )
    value = dict(
        apiVersion=API,
        kind="ContextIndex",
        documents=documents,
        findings=findings,
        semanticValidation="not-performed",
        tokenEstimateMethod="characters/4-ceiling",
        status="blocked" if findings else "pass",
    )
    validate(value, "context-index.schema.json")
    if write:
        require(not findings, "Resolve context findings before saving a baseline.", "NOT_READY")
        write_json(safe_path(root, INDEX), value)
    return value


def check_context(root):
    value = build_index(root)
    baseline = safe_path(root, INDEX)
    value["baselinePresent"] = baseline.is_file()
    if not baseline.is_file():
        return value
    previous = validate(read_json(baseline), "context-index.schema.json")
    old = {d["path"]: d for d in previous["documents"]}
    current = {d["path"]: d for d in value["documents"]}
    for path in sorted(set(old) | set(current)):
        codes = []
        if path not in old:
            codes.append("DOCUMENT_ADDED")
        elif path not in current:
            codes.append("DOCUMENT_REMOVED")
        else:
            if old[path]["sha256"] != current[path]["sha256"]:
                codes.append("DOCUMENT_CHANGED")
            if old[path]["sourceHashes"] != current[path]["sourceHashes"]:
                codes.append("SOURCE_CHANGED")
        value["findings"].extend(dict(code=code, path=path, severity="warning") for code in codes)
    if value["findings"] and value["status"] == "pass":
        value["status"] = "warning"
    return value


def select_context(root, task, intent="", files=(), budget=2500):
    require(budget > 0, "Context budget must be positive.")
    for file in files:
        safe_path(root, file)
    index = check_context(root)
    docs = {d["path"]: d for d in index["documents"]}
    terms = set(re.findall(r"[\w-]{3,}", task.casefold()))
    chosen, reasons = set(), {}
    for path, doc in docs.items():
        why = []
        if doc["required"]:
            why.append("required")
        if intent and intent in doc["intents"]:
            why.append("intent")
        if terms & set(re.findall(r"[\w-]{3,}", (path + " " + doc["scope"]).casefold())):
            why.append("task")
        if set(files) & (set(doc["sources"]) | {path}):
            why.append("changed-file")
        if why:
            chosen.add(path)
            reasons[path] = why
    pending = sorted(chosen)
    while pending:
        for dependency in docs[pending.pop()]["dependencies"]:
            if dependency in docs and dependency not in chosen:
                chosen.add(dependency)
                reasons[dependency] = ["dependency"]
                pending.append(dependency)
    findings = [f for f in index["findings"] if f["path"] in chosen or f["path"] not in docs]
    if not chosen:
        findings.append(dict(code="NO_CONTEXT_MATCH", path="", severity="warning"))
    selected = [dict(docs[p], reasons=reasons[p]) for p in sorted(chosen)]
    total = sum(d["estimatedTokens"] for d in selected)
    # Non-document dependencies remain explicit required references, never silently lost.
    required_refs = sorted({d for p in chosen for d in docs[p]["dependencies"] if d not in docs})
    if required_refs:
        findings.append(dict(code="UNINDEXED_DEPENDENCY", path="", severity="error"))
    return dict(
        status="blocked"
        if any(f["severity"] == "error" for f in findings)
        else "warning"
        if findings or total > budget
        else "pass",
        selected=selected,
        findings=findings,
        requiredReferences=required_refs,
        estimatedTokens=total,
        budget=budget,
        overBudget=total > budget,
        tokenEstimateMethod="characters/4-ceiling",
        semanticValidation="not-performed",
    )
