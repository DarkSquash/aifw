import pytest

from aifw import assessment
from aifw.cli import create_parser, execute
from aifw.common import read_yaml, write_yaml
from aifw.context import select_context
from test_workflows import init


def fake(scores):
    """Probability per document path; documents not listed are irrelevant."""

    def call(model, state, questions):
        path = state.split("Documento: ")[1].split("\n")[0]
        return {"relevant": dict(type="noul", noul=scores.get(path, 0.0))}, 0.00001

    return call


@pytest.fixture
def project(tmp_path, monkeypatch):
    init(tmp_path)
    manifest = read_yaml(tmp_path / "aifw.yaml")
    manifest["spec"].update(
        assessment=dict(mode="shadow", features=["context"]), externalAllowlist=["openrouter"]
    )
    write_yaml(tmp_path / "aifw.yaml", manifest)
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "login.md").write_text("# Autenticação de usuários\n\nTokens e sessões.\n", encoding="utf-8")
    (docs / "billing.md").write_text("# Cobrança mensal\n\nFaturas.\n", encoding="utf-8")
    (docs / "cache.md").write_text("# Cache de respostas\n\nTempo de vida.\n", encoding="utf-8")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    return tmp_path


def test_suggests_missed_documents_and_doubts_word_matches(project):
    task = "corrigir a expiração do login dos usuários e o cache"
    selection = select_context(project, task)
    keyword = {s["path"] for s in selection["selected"]}
    assert "docs/cache.md" in keyword
    scores = {"docs/login.md": 0.92, "docs/cache.md": 0.05, "docs/billing.md": 0.3}
    result = assessment.review_context(project, task, selection, call=fake(scores))
    assert result["recorded"] and result["id"] == 1
    assert "docs/login.md" in result["suggested"] or "docs/login.md" in keyword
    assert "docs/billing.md" not in result["suggested"]
    assert result["doubtful"] == ["docs/cache.md"]
    assert result["keywordSelection"] == sorted(keyword)  # shadow: the selection itself is untouched


def test_required_or_changed_file_documents_are_never_doubted(project):
    selection = dict(selected=[dict(path="docs/cache.md", reasons=["task", "changed-file"])])
    result = assessment.review_context(project, "cache", selection, call=fake({}))
    assert result["doubtful"] == []


def test_off_without_the_feature(project):
    manifest = read_yaml(project / "aifw.yaml")
    manifest["spec"]["assessment"]["features"] = ["tasks"]
    write_yaml(project / "aifw.yaml", manifest)
    result = assessment.review_context(project, "x", dict(selected=[]), call=fake({}))
    assert result["status"] == "unavailable" and "context" in result["reason"]


def test_context_select_reports_the_shadow_review(project, monkeypatch):
    monkeypatch.setattr(assessment, "decide", fake({"docs/billing.md": 0.8}))
    args = create_parser().parse_args(["context", "select", "--task", "faturas atrasadas", "--json"])
    value, _ = execute(args, project)
    assert value["assessment"]["recorded"] and value["assessment"]["suggested"] == ["docs/billing.md"]


def test_context_report_and_verdicts(project):
    selection = dict(selected=[])
    assessment.review_context(project, "faturas", selection, call=fake({"docs/billing.md": 0.9}))
    assessment.record_verdicts(project, [1], "human:me", value="keyword", feature="context")
    value = assessment.report(project, "context")
    assert value["summary"]["judged"] == 1 and value["summary"]["agreement"] == 0
    text = assessment.render_report(value)
    assert "Seleção de contexto" in text and "billing.md" in text and "keyword" in text
