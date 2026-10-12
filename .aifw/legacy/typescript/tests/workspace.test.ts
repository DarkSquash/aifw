import { readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

type WorkspaceModule = typeof import("../src/core/workspace.ts");

async function loadWorkspace(): Promise<WorkspaceModule> {
  try {
    return await import("../src/core/workspace.ts");
  } catch (error) {
    assert.fail(`workspace module must be implemented: ${String(error)}`);
  }
}

async function temporaryProject(testName: string): Promise<string> {
  const { mkdtemp } = await import("node:fs/promises");
  return mkdtemp(path.join(tmpdir(), `aifw-${testName}-`));
}

describe("project workspace scaffolding", () => {
  it("creates a pinned, auditable project control plane without choosing the stack", async () => {
    const { initializeProject } = await loadWorkspace();
    const root = await temporaryProject("init");

    const result = await initializeProject(root, {
      id: "northstar",
      name: "Northstar",
      projectType: "new",
      locale: "pt-BR",
      primaryEnvironment: "windows",
      validationTargets: ["windows", "wsl", "linux-ci"],
    });

    assert.ok(result.createdFiles.includes("aifw.yaml"));
    assert.ok(result.createdFiles.includes(".aifw/charter.yaml"));
    assert.ok(result.createdFiles.includes(".aifw/catalog.yaml"));
    assert.ok(result.createdFiles.includes("PROJECT_MAP.md"));
    const manifest = await readFile(path.join(root, "aifw.yaml"), "utf8");
    assert.match(manifest, /frameworkVersion: 0\.2\.0/);
    assert.match(manifest, /profiles: \[\]/);
    assert.doesNotMatch(manifest, /react|typescript|python/iu);
    const routing = await readFile(path.join(root, ".aifw", "routing.yaml"), "utf8");
    assert.match(routing, /enabled: false/);
    assert.match(routing, /mode: recommendation-only/);
    assert.ok(result.createdFiles.includes(".aifw/specs/current/README.md"));
    assert.ok(result.createdFiles.includes(".aifw/changes/active/README.md"));
    assert.ok(result.createdFiles.includes(".aifw/changes/archive/README.md"));
    assert.ok(result.createdFiles.includes(".aifw/adoption/README.md"));
    const catalog = await readFile(path.join(root, ".aifw", "catalog.yaml"), "utf8");
    assert.match(catalog, /Approved capability specs/);
    assert.match(catalog, /\.aifw\/specs\/current\//);
  });

  it("refuses to overwrite an initialized project", async () => {
    const { initializeProject } = await loadWorkspace();
    const root = await temporaryProject("no-overwrite");
    const options = {
      id: "northstar",
      name: "Northstar",
      projectType: "existing" as const,
      locale: "pt-BR",
      primaryEnvironment: "windows" as const,
      validationTargets: ["windows" as const],
    };
    await initializeProject(root, options);

    assert.rejects(
      () => initializeProject(root, options),
      (error: unknown) => {
        assert.equal((error as { code?: string }).code, "POLICY_CONFLICT");
        return true;
      },
    );
  });

  it("rebuilds PROJECT_MAP from authoritative YAML and detects drift", async () => {
    const { buildWorkspaceMap, initializeProject } = await loadWorkspace();
    const root = await temporaryProject("map");
    await initializeProject(root, {
      id: "northstar",
      name: "Northstar",
      projectType: "new",
      locale: "pt-BR",
      primaryEnvironment: "windows",
      validationTargets: ["windows"],
    });

    const first = await buildWorkspaceMap(root, { write: false });
    assert.equal(first.current, true);
    await writeFile(
      path.join(root, "PROJECT_MAP.md"),
      first.markdown.replace("Northstar", "Stale title"),
      "utf8",
    );
    const stale = await buildWorkspaceMap(root, { write: false });
    assert.equal(stale.current, false);

    const rebuilt = await buildWorkspaceMap(root, { write: true });
    assert.equal(rebuilt.current, true);
    assert.equal(
      await readFile(path.join(root, "PROJECT_MAP.md"), "utf8"),
      rebuilt.markdown,
    );
  });
});
