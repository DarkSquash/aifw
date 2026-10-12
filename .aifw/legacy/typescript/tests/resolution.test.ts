import assert from "node:assert/strict";
import { describe, it } from "node:test";

type ResolutionModule = typeof import("../src/core/resolution.ts");

async function loadResolution(): Promise<ResolutionModule> {
  try {
    return await import("../src/core/resolution.ts");
  } catch (error) {
    assert.fail(`resolution module must be implemented: ${String(error)}`);
  }
}

function rule(
  id: string,
  statement: string,
  options: { overridable?: boolean } = {},
) {
  return {
    id,
    version: "1.0.0",
    keyword: "MUST" as const,
    statement,
    scope: ["project"],
    rationale: "test fixture",
    owner: "human:owner",
    enforcement: { mode: "hard" as const, evidence: ["test"] },
    source: "test",
    overridable: options.overridable ?? true,
  };
}

function profile(
  id: string,
  kind: "capability" | "stack",
  options: {
    provides?: string[];
    requires?: string[];
    conflicts?: string[];
    rules?: ReturnType<typeof rule>[];
  } = {},
) {
  return {
    id,
    version: "1.0.0",
    kind,
    provides: options.provides ?? [],
    requires: options.requires ?? [],
    conflicts: options.conflicts ?? [],
    rules: options.rules ?? [],
  };
}

describe("framework resolution", () => {
  it("applies project rules over replaceable personal defaults", async () => {
    const { resolveFramework } = await loadResolution();

    const result = resolveFramework({
      coreRules: [],
      personalRules: [rule("design.button-radius", "Use rounded buttons")],
      profiles: [],
      projectRules: [
        rule("design.button-radius", "Use compact radius in dense tables"),
      ],
    });

    assert.equal(
      result.rules.find((item) => item.id === "design.button-radius")
        ?.statement,
      "Use compact radius in dense tables",
    );
    assert.equal(
      result.rules.find((item) => item.id === "design.button-radius")?.origin,
      "project",
    );
  });

  it("never lets a lower layer replace a core invariant", async () => {
    const { resolveFramework } = await loadResolution();

    assert.throws(
      () =>
        resolveFramework({
          coreRules: [
            rule("security.no-secret-output", "Never output secrets", {
              overridable: false,
            }),
          ],
          personalRules: [],
          profiles: [],
          projectRules: [
            rule("security.no-secret-output", "Secrets may be printed"),
          ],
        }),
      (error: unknown) => {
        assert.equal((error as { code?: string }).code, "POLICY_CONFLICT");
        assert.match(String(error), /security\.no-secret-output/);
        return true;
      },
    );
  });

  it("rejects explicitly conflicting profiles", async () => {
    const { resolveFramework } = await loadResolution();

    assert.throws(
      () =>
        resolveFramework({
          coreRules: [],
          personalRules: [],
          profiles: [
            profile("web-ts", "stack", { conflicts: ["web-python"] }),
            profile("web-python", "stack"),
          ],
          projectRules: [],
        }),
      (error: unknown) => {
        assert.equal((error as { code?: string }).code, "PROFILE_CONFLICT");
        assert.match(String(error), /web-ts.*web-python|web-python.*web-ts/);
        return true;
      },
    );
  });

  it("rejects profiles whose capabilities are not provided", async () => {
    const { resolveFramework } = await loadResolution();

    assert.throws(
      () =>
        resolveFramework({
          coreRules: [],
          personalRules: [],
          profiles: [
            profile("nextjs", "stack", { requires: ["capability:web-ui"] }),
          ],
          projectRules: [],
        }),
      (error: unknown) => {
        assert.equal((error as { code?: string }).code, "PROFILE_CONFLICT");
        assert.match(String(error), /capability:web-ui/);
        return true;
      },
    );
  });

  it("produces a deterministic lock regardless of profile input order", async () => {
    const { resolveFramework } = await loadResolution();
    const web = profile("web-ui", "capability", {
      provides: ["capability:web-ui"],
    });
    const next = profile("nextjs", "stack", {
      requires: ["capability:web-ui"],
    });

    const first = resolveFramework({
      coreRules: [],
      personalRules: [],
      profiles: [web, next],
      projectRules: [],
    });
    const second = resolveFramework({
      coreRules: [],
      personalRules: [],
      profiles: [next, web],
      projectRules: [],
    });

    assert.deepEqual(first.profileLock, second.profileLock);
    assert.match(first.profileLock.digest, /^[a-f0-9]{64}$/);
    assert.deepEqual(
      first.profileLock.profiles.map((item) => item.id),
      ["nextjs", "web-ui"],
    );
  });
});
