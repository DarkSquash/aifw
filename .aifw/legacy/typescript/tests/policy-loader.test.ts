import { readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

type LoaderModule = typeof import("../src/core/policy-loader.ts");
type WorkspaceModule = typeof import("../src/core/workspace.ts");

async function modules(): Promise<{ loader: LoaderModule; workspace: WorkspaceModule }> {
  try {
    return {
      loader: await import("../src/core/policy-loader.ts"),
      workspace: await import("../src/core/workspace.ts"),
    };
  } catch (error) {
    assert.fail(`policy resolution modules must be implemented: ${String(error)}`);
  }
}

async function temporaryProject(): Promise<string> {
  const { mkdtemp } = await import("node:fs/promises");
  return mkdtemp(path.join(tmpdir(), "aifw-policy-"));
}

describe("versioned policy loading and resolution", () => {
  it("parses policy sets with stable rule ids and rejects duplicate YAML keys", async () => {
    const { loader } = await modules();
    const source = `
apiVersion: aifw.dev/v1alpha1
kind: PolicySet
metadata:
  id: test
  version: 1.0.0
rules:
  - id: security.no-secret-output
    version: 1.0.0
    keyword: MUST_NOT
    statement: Output credentials or secrets.
    scope: [project]
    rationale: Secrets must not leave trusted boundaries.
    owner: framework:security
    enforcement:
      mode: hard
      evidence: [secret-scan]
    source: test
    overridable: false
`;

    const parsed = loader.parsePolicySet(source, "test.yaml");
    assert.equal(parsed.rules[0]?.id, "security.no-secret-output");
    assert.throws(() =>
      loader.parsePolicySet(source.replace("kind: PolicySet", "kind: PolicySet\nkind: PolicySet"), "duplicate.yaml"),
    );
  });

  it("resolves core, personal, profile and project layers into a deterministic lock", async () => {
    const { loader, workspace } = await modules();
    const root = await temporaryProject();
    await workspace.initializeProject(root, {
      id: "northstar",
      name: "Northstar",
      projectType: "new",
      locale: "pt-BR",
      primaryEnvironment: "windows",
      validationTargets: ["windows", "linux-ci"],
    });
    const manifestPath = path.join(root, "aifw.yaml");
    await writeFile(
      manifestPath,
      (await readFile(manifestPath, "utf8")).replace("profiles: []", "profiles:\n  - web-ts"),
      "utf8",
    );
    const personalPath = path.join(root, "personal.yaml");
    await writeFile(
      personalPath,
      `apiVersion: aifw.dev/v1alpha1
kind: PolicySet
metadata: { id: personal, version: 1.0.0 }
rules:
  - id: design.button-radius
    version: 1.0.0
    keyword: SHOULD
    statement: Prefer generously rounded buttons.
    scope: [frontend]
    rationale: Personal visual preference.
    owner: human:owner
    enforcement: { mode: audit, evidence: [visual-review] }
    source: personal.yaml
    overridable: true
`,
      "utf8",
    );
    await writeFile(
      path.join(root, ".aifw", "project-rules.yaml"),
      `apiVersion: aifw.dev/v1alpha1
kind: PolicySet
metadata: { id: project, version: 1.0.0 }
rules:
  - id: design.button-radius
    version: 1.0.0
    keyword: SHOULD
    statement: Use compact radii in dense controls.
    scope: [frontend]
    rationale: Dense tables need more space.
    owner: human:owner
    enforcement: { mode: audit, evidence: [visual-review] }
    source: .aifw/project-rules.yaml
    overridable: true
`,
      "utf8",
    );

    const resolved = await loader.resolveWorkspace(root, {
      personalPolicyPath: personalPath,
      write: true,
    });

    assert.equal(resolved.current, true);
    assert.ok(resolved.resolution.rules.some((rule) => rule.origin === "core"));
    assert.ok(resolved.resolution.rules.some((rule) => rule.origin === "stack:web-ts"));
    assert.equal(
      resolved.resolution.rules.find((rule) => rule.id === "design.button-radius")?.origin,
      "project",
    );
    assert.match(resolved.resolution.profileLock.digest, /^[a-f0-9]{64}$/);
    assert.match(
      await readFile(path.join(root, ".aifw", "effective-policy.json"), "utf8"),
      /security\.no-secret-output/,
    );
  });

  it("detects a stale effective-policy artifact without rewriting it", async () => {
    const { loader, workspace } = await modules();
    const root = await temporaryProject();
    await workspace.initializeProject(root, {
      id: "northstar",
      name: "Northstar",
      projectType: "new",
      locale: "pt-BR",
      primaryEnvironment: "windows",
      validationTargets: ["windows"],
    });
    await loader.resolveWorkspace(root, { write: true });
    await writeFile(path.join(root, ".aifw", "effective-policy.json"), "{}\n", "utf8");

    const result = await loader.resolveWorkspace(root, { write: false });

    assert.equal(result.current, false);
    assert.equal(await readFile(path.join(root, ".aifw", "effective-policy.json"), "utf8"), "{}\n");
  });
});
