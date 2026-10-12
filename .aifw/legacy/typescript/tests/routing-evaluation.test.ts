import { readFile } from "node:fs/promises";
import path from "node:path";
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";

type EvaluationModule = typeof import("../src/core/routing-evaluation.ts");

async function loadEvaluation(): Promise<EvaluationModule> {
  try {
    return await import("../src/core/routing-evaluation.ts");
  } catch (error) {
    assert.fail(`routing evaluation module must be implemented: ${String(error)}`);
  }
}

const projectRoot = fileURLToPath(new URL("..", import.meta.url));

describe("routing conformance evaluation", () => {
  it("evaluates at least thirty representative routing cases with no critical failure", async () => {
    const { evaluateRoutingCases } = await loadEvaluation();
    const fixturePath = path.join(projectRoot, "evals", "routing", "cases.yaml");

    const result = await evaluateRoutingCases(fixturePath);

    assert.ok(result.cases >= 30);
    assert.equal(result.passRate, 1);
    assert.equal(result.criticalFailures, 0);
    assert.equal(result.failures.length, 0);
  });

  it("keeps the fixture reviewable and free of hidden generated expectations", async () => {
    const source = await readFile(
      path.join(projectRoot, "evals", "routing", "cases.yaml"),
      "utf8",
    );
    assert.match(source, /expectedRoute:/u);
    assert.match(source, /critical:/u);
  });
});
