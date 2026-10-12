import assert from "node:assert/strict";
import { describe, it } from "node:test";

type ChangeModule = typeof import("../src/core/change.ts");

async function loadChange(): Promise<ChangeModule> {
  try {
    return await import("../src/core/change.ts");
  } catch (error) {
    assert.fail(`change module must be implemented: ${String(error)}`);
  }
}

describe("change impact classification", () => {
  it("classifies read-only discovery as L0", async () => {
    const { classifyChange } = await loadChange();

    const result = classifyChange({ readOnly: true });

    assert.equal(result.level, "L0");
    assert.equal(result.humanApproval, "none");
  });

  it("classifies a local reversible behavior change as L1", async () => {
    const { classifyChange } = await loadChange();

    const result = classifyChange({
      behaviorChange: true,
      localOnly: true,
      reversible: true,
    });

    assert.equal(result.level, "L1");
    assert.deepEqual(result.requiredArtifacts, ["change-case", "tests", "rollback"]);
  });

  it("classifies a shared contract change as L2 with conditional approval", async () => {
    const { classifyChange } = await loadChange();

    const result = classifyChange({
      behaviorChange: true,
      sharedContract: true,
      reversible: true,
    });

    assert.equal(result.level, "L2");
    assert.equal(result.humanApproval, "required");
    assert.ok(result.reasons.includes("shared-contract"));
    assert.ok(result.requiredArtifacts.includes("spec"));
    assert.ok(result.requiredArtifacts.includes("independent-review"));
  });

  it("classifies a framework policy change as L3", async () => {
    const { classifyChange } = await loadChange();

    const result = classifyChange({ frameworkCore: true });

    assert.equal(result.level, "L3");
    assert.equal(result.humanApproval, "required");
    assert.ok(result.requiredArtifacts.includes("rfc"));
    assert.ok(result.requiredArtifacts.includes("threat-model"));
  });

  it("keeps cognitive complexity separate from impact", async () => {
    const { classifyChange } = await loadChange();

    const result = classifyChange({ readOnly: true, semanticComplexity: "brain" });

    assert.equal(result.level, "L0");
    assert.equal(result.suggestedRoute, "BRAIN");
  });
});
