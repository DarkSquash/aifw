"""Strict document boundaries, deterministic encoding and project paths."""

from copy import deepcopy
from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import re
import unicodedata

import yaml

API = "aifw.dev/v1alpha1"
SLUG = re.compile(r"^[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class AifwError(Exception):
    def __init__(self, code, message, details=()):
        super().__init__(message)
        self.code, self.details = code, list(details)


def require(condition, message, code="MANIFEST_INVALID", details=()):
    if not condition:
        raise AifwError(code, message, details)


class CoreLoader(yaml.SafeLoader):
    """YAML core booleans; dates remain strings; duplicate keys are errors."""


CoreLoader.yaml_implicit_resolvers = deepcopy(yaml.SafeLoader.yaml_implicit_resolvers)
for key, resolvers in CoreLoader.yaml_implicit_resolvers.items():
    CoreLoader.yaml_implicit_resolvers[key] = [
        (tag, regex)
        for tag, regex in resolvers
        if tag
        not in {
            "tag:yaml.org,2002:bool",
            "tag:yaml.org,2002:timestamp",
            "tag:yaml.org,2002:int",
            "tag:yaml.org,2002:float",
        }
    ]
CoreLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|false|True|False|TRUE|FALSE)$"), list("tTfF")
)
CoreLoader.add_implicit_resolver(
    "tag:yaml.org,2002:int", re.compile(r"^(?:[-+]?[0-9]+|0o[0-7]+|0x[0-9a-fA-F]+)$"), list("-+0123456789")
)
CoreLoader.add_implicit_resolver(
    "tag:yaml.org,2002:float",
    re.compile(
        r"^(?:[-+]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][-+]?[0-9]+)?|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$"
    ),
    list("-+0123456789."),
)
CoreLoader.add_constructor(
    "tag:yaml.org,2002:int",
    lambda loader, node: int(
        node.value, 8 if node.value.startswith("0o") else 16 if node.value.startswith("0x") else 10
    ),
)


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, (str, int, float, bool, type(None))):
            raise yaml.YAMLError("Unsupported mapping key")
        if key in result:
            raise yaml.YAMLError(f"Duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


CoreLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def parse_yaml(source, label="document"):
    try:
        return yaml.load(source, Loader=CoreLoader)
    except yaml.YAMLError as error:
        raise AifwError("YAML_INVALID", f"{label}: {error}") from error


def read_yaml(file):
    return parse_yaml(Path(file).read_text(encoding="utf-8-sig"), str(file))


def write_yaml(file, value, exclusive=False):
    file = Path(file)
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("x" if exclusive else "w", encoding="utf-8", newline="\n") as stream:
        yaml.safe_dump(value, stream, allow_unicode=True, sort_keys=False, width=100000)


def read_json(file):
    try:
        return json.loads(
            Path(file).read_text(encoding="utf-8-sig"),
            parse_constant=lambda value: require(False, f"Invalid JSON number: {value}"),
        )
    except (ValueError, TypeError) as error:
        raise AifwError("MANIFEST_INVALID", f"Invalid JSON in {file}: {error}") from error


def json_text(value, pretty=True):
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
    )


def write_json(file, value):
    file = Path(file)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json_text(value) + "\n", encoding="utf-8", newline="\n")


def sort_key(value):
    normalized = unicodedata.normalize("NFD", str(value))
    return ("".join(c for c in normalized if not unicodedata.combining(c)).casefold(), str(value))


def stable(value):
    if isinstance(value, dict):
        return {key: stable(value[key]) for key in sorted(value, key=sort_key)}
    if isinstance(value, list):
        return [stable(item) for item in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def digest(value):
    return sha256(json_text(stable(value), False).encode()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def timestamp(value):
    require(isinstance(value, str), "A timestamp must be a string.")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise AifwError("MANIFEST_INVALID", f"Invalid timestamp: {value}") from error


def slug(value):
    require(isinstance(value, str) and SLUG.fullmatch(value), f"Invalid project-safe id: {value}")
    return value


def human(identity):
    require(
        isinstance(identity, str) and re.fullmatch(r"human:\S+", identity),
        "Approval requires an identified human.",
        "APPROVAL_REQUIRED",
    )


def assets():
    bundled = Path(__file__).parent / "data"
    return bundled if bundled.is_dir() else Path(__file__).resolve().parents[2]


@lru_cache(maxsize=None)
def schema_validator(schema_name):
    import jsonschema
    from referencing import Registry, Resource

    resources = []
    for file in (assets() / "schemas").glob("*.json"):
        content = read_json(file)
        if "$id" in content:
            resources.append((content["$id"], Resource.from_contents(content)))
    schema = read_json(assets() / "schemas" / schema_name)
    return jsonschema.Draft202012Validator(schema, registry=Registry().with_resources(resources))


def validate(value, schema_name):
    validator = schema_validator(schema_name)
    errors = sorted(validator.iter_errors(value), key=lambda error: str(list(error.path)))
    require(
        not errors,
        f"Document does not match {schema_name}.",
        details=[f"{list(e.path)}: {e.message}" for e in errors[:20]],
    )
    return deepcopy(value)


def read_valid_yaml(file, schema_name):
    """read_yaml + validate, remembering validated content so short-lived hooks skip loading jsonschema.

    The cache only records that some content passed a schema; values always come from the file itself.
    """
    import tempfile

    data = Path(file).read_bytes()
    key = f"{schema_name}:{sha256(data).hexdigest()}"
    cache = Path(tempfile.gettempdir()) / "aifw-validated.txt"
    try:
        known = key in cache.read_text(encoding="utf-8").split()
    except OSError:
        known = False
    value = read_yaml(file)
    if not known:
        validate(value, schema_name)
        try:
            with cache.open("a", encoding="utf-8") as stream:
                stream.write(key + "\n")
        except OSError:
            pass
    return value


def project_path(root, relative, *, file=False):
    root = Path(root).resolve()
    candidate = (root / relative).resolve()
    require(
        candidate != root and candidate.is_relative_to(root),
        f"Path must remain inside project: {relative}",
        "PERMISSION_DENIED",
    )
    if file:
        require(candidate.is_file(), f"Project file does not exist: {relative}", "NOT_READY")
    return candidate


def file_state(root, relative):
    if not isinstance(relative, str) or not relative.strip():
        return "missing"
    try:
        candidate = project_path(root, relative)
    except AifwError:
        return "outside"
    return "valid" if candidate.is_file() else "missing"


def normalize(source):
    return source.replace("\r\n", "\n").rstrip()
