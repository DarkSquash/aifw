import assert from "node:assert/strict";
import { mkdtemp, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";

import type { AnySchema } from "ajv";
import { Ajv2020 } from "ajv/dist/2020.js";

const frameworkRoot = fileURLToPath(new URL("..", import.meta.url));

type PrincipleModule = typeof import("../src/core/principle-catalog.ts");
type WorkspaceModule = typeof import("../src/core/workspace.ts");

async function modules(): Promise<{
  principles: PrincipleModule;
  workspace: WorkspaceModule;
}> {
  try {
    return {
      principles: await import("../src/core/principle-catalog.ts"),
      workspace: await import("../src/core/workspace.ts"),
    };
  } catch (error) {
    assert.fail(`global engineering principle catalog must be implemented: ${String(error)}`);
  }
}

const fixture = `
apiVersion: aifw.dev/v1alpha1
kind: PrincipleCatalog
metadata:
  id: core-engineering-principles
  version: 1.0.0
  scope: core
spec:
  title: Engineering principles
  principles:
    - id: clean-code-naming
      name: Meaningful names
      family: clean-code
      statement: Names communicate intent in the vocabulary of the problem.
      appliesWhen: []
      reviewQuestions: [Can a maintainer understand the role without tracing implementation?]
      evidence: [changed-code, public-interfaces]
      misuseRisks: [Renaming without improving shared understanding creates churn.]
      exceptions: [Protocol and framework names may be externally fixed.]
      sources: [https://example.test/clean-code]
    - id: solid-srp
      name: Single Responsibility Principle
      family: solid
      statement: A module should have one coherent reason to change.
      appliesWhen: [design:object-oriented, design:modular]
      reviewQuestions: [Are unrelated actors forcing changes in this module?]
      evidence: [change-history, dependency-map]
      misuseRisks: [Splitting by method count creates fragmentation.]
      exceptions: [A small cohesive module may serve several operations for one actor.]
      sources: [https://example.test/srp]
    - id: dry-stable-knowledge
      name: Avoid duplicated knowledge
      family: foundational
      statement: Consolidate duplicated knowledge after its common meaning is stable.
      appliesWhen: [duplication:stable]
      reviewQuestions: [Does the duplication represent the same knowledge?]
      evidence: [duplicate-behavior, change-history]
      misuseRisks: [Premature abstraction couples unrelated behavior.]
      exceptions: [Coincidental duplication may remain separate.]
      sources: [https://example.test/dry]
`;

describe("contextual engineering principle catalog", () => {
  it("keeps universal Clean Code guidance active without forcing context-specific principles", async () => {
    const { principles } = await modules();
    const catalog = principles.parsePrincipleCatalog(fixture, "principles.fixture.yaml");

    const review = principles.reviewPrinciples([catalog], { signals: [] });

    assert.equal(
      review.checks.find((check) => check.principleId === "clean-code-naming")?.applicability,
      "applicable",
    );
    assert.equal(
      review.checks.find((check) => check.principleId === "solid-srp")?.applicability,
      "deferred",
    );
    assert.equal(
      review.checks.find((check) => check.principleId === "dry-stable-knowledge")?.applicability,
      "deferred",
    );
  });

  it("activates matching SOLID guidance and preserves its anti-dogma safeguards", async () => {
    const { principles } = await modules();
    const catalog = principles.parsePrincipleCatalog(fixture, "principles.fixture.yaml");

    const review = principles.reviewPrinciples([catalog], {
      signals: ["design:object-oriented"],
    });
    const srp = review.checks.find((check) => check.principleId === "solid-srp");

    assert.ok(srp);
    assert.equal(srp.applicability, "applicable");
    assert.deepEqual(srp.matchedSignals, ["design:object-oriented"]);
    assert.deepEqual(srp.misuseRisks, ["Splitting by method count creates fragmentation."]);
    assert.match(review.digest, /^[a-f0-9]{64}$/u);
  });

  it("loads the bundled global catalog and writes a reproducible project review", async () => {
    const { principles, workspace } = await modules();
    const root = await mkdtemp(path.join(tmpdir(), "aifw-principles-"));
    await workspace.initializeProject(root, {
      id: "existing-app",
      name: "Existing App",
      projectType: "existing",
      locale: "pt-BR",
      primaryEnvironment: "windows",
      validationTargets: ["windows"],
    });

    const review = await principles.reviewWorkspacePrinciples(root, {
      signals: ["design:object-oriented", "duplication:stable"],
      write: true,
    });

    assert.equal(
      review.checks.find((check) => check.principleId === "solid-srp")?.applicability,
      "applicable",
    );
    assert.equal(
      review.checks.find((check) => check.principleId === "clean-code-naming")?.applicability,
      "applicable",
    );
    assert.match(
      await readFile(
        path.join(root, ".aifw", "reviews", "engineering-principles.json"),
        "utf8",
      ),
      /"kind": "PrincipleReview"/u,
    );
  });

  it("produces a PrincipleReview that satisfies its published JSON Schema", async () => {
    const { principles } = await modules();
    const catalog = principles.parsePrincipleCatalog(fixture, "principles.fixture.yaml");
    const review = principles.reviewPrinciples([catalog], {
      signals: ["design:object-oriented"],
    });
    const ajv = new Ajv2020({ strict: true, allErrors: true });
    const catalogSchema = JSON.parse(
      await readFile(
        path.join(frameworkRoot, "schemas", "principle-catalog.schema.json"),
        "utf8",
      ),
    ) as AnySchema;
    const reviewSchema = JSON.parse(
      await readFile(
        path.join(frameworkRoot, "schemas", "principle-review.schema.json"),
        "utf8",
      ),
    ) as AnySchema;
    ajv.addSchema(catalogSchema);
    const validate = ajv.compile(reviewSchema);

    assert.equal(validate(review), true, JSON.stringify(validate.errors));
  });
});
