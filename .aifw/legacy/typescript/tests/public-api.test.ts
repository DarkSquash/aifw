import assert from "node:assert/strict";
import { describe, it } from "node:test";

import type { AgentAdapter } from "../src/adapters/sdk.ts";

describe("public framework API", () => {
  it("exports the vendor-neutral core and adapter SDK", async () => {
    let core: typeof import("../src/index.ts");
    try {
      core = await import("../src/index.ts");
    } catch (error) {
      assert.fail(`public entrypoints must be implemented: ${String(error)}`);
    }

    assert.equal(typeof core.classifyChange, "function");
    assert.equal(typeof core.resolveFramework, "function");
    assert.equal(typeof core.buildProjectMap, "function");
    assert.equal(typeof core.evaluateTrace, "function");
    assert.equal(typeof core.createSpecChange, "function");
    assert.equal(typeof core.analyzeSpecChange, "function");
    assert.equal(typeof core.analyzeBrownfieldProject, "function");
    assert.equal(typeof core.applyBrownfieldMapping, "function");
    const adapterContract: keyof AgentAdapter = "plan";
    assert.equal(adapterContract, "plan");
  });
});
