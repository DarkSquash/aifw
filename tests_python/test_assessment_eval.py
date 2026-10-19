import pytest

from aifw.assessment import COMPLEXITY, IMPORTANCE
from aifw.assessment_eval import evaluate, render
from aifw.common import AifwError, write_yaml
from test_assessment import project, set_spec  # noqa: F401 - fixture


def suite(root, feature, cases):
    file = root / f"evals/assessment/{feature}-cases.yaml"
    file.parent.mkdir(parents=True, exist_ok=True)
    write_yaml(
        file,
        dict(apiVersion="aifw.dev/v1alpha1", kind="AssessmentEvaluationSuite", feature=feature, cases=cases),
    )
    return file


def scored(names, value):
    return dict(
        score=float(names.index(value)), probabilities={n: 0.97 if n == value else 0.01 for n in names}
    )


def test_impasse_suite_reports_accuracy_and_cutoffs(project):  # noqa: F811
    attempt = dict(hypothesis="h", intervention="i")
    suite(
        project,
        "impasse",
        [
            dict(id="same", previous=attempt, new=dict(hypothesis="h2", intervention="i"), expected="repeat"),
            dict(
                id="other", previous=attempt, new=dict(hypothesis="x", intervention="y"), expected="distinct"
            ),
        ],
    )

    def call(model, state, questions):
        return dict(same=dict(noul=0.65 if "h2" in state else 0.05)), 0.00001

    result = evaluate(project, "impasse", call=call)
    assert (result["right"], result["cases"], result["threshold"]) == (1, 2, 0.7)
    assert result["sweep"]["0.6"] == 2 and result["failures"][0]["id"] == "same"
    assert "same: esperado repeat" in render(result)


def test_tasks_suite_flags_paths_below_the_answer(project):  # noqa: F811
    suite(
        project,
        "tasks",
        [
            dict(
                id="t1",
                task="Apagar backups",
                risk="L3",
                importance="alta",
                complexity="simples",
                path="CRITICAL",
            )
        ],
    )

    def call(model, state, questions):
        key = next(iter(questions))
        if key == "risk":
            return dict(risk=dict(choice="L2", confidence=0.8)), 0.0
        names = IMPORTANCE if key == "importance" else COMPLEXITY
        return {key: scored(names, "alta" if key == "importance" else "simples")}, 0.0

    result = evaluate(project, "tasks", call=call)
    assert result["right"] == 0 and result["pathBelowExpected"] == 1
    assert result["exactByStage"] == dict(risk=0, importance=1, complexity=1)


def test_suite_needs_guards_and_the_right_feature(project, monkeypatch):  # noqa: F811
    file = suite(project, "intake", [dict(id="x", field="problem", answer="a definir", expected="vaga")])
    with pytest.raises(AifwError):
        evaluate(project, "impasse", cases=str(file), call=lambda *_: None)
    monkeypatch.delenv("OPENROUTER_API_KEY")
    result = evaluate(project, "intake", call=lambda *_: None)
    assert result["status"] == "unavailable" and "não avaliado" in render(result)
