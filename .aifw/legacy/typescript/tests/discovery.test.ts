import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { after, before, describe, it } from "node:test";

type DiscoveryModule = typeof import("../src/core/discovery.ts");

async function loadDiscovery(): Promise<DiscoveryModule> {
  try {
    return await import("../src/core/discovery.ts");
  } catch (error) {
    assert.fail(`discovery module must be implemented: ${String(error)}`);
  }
}

describe("read-only existing-project discovery", () => {
  let root = "";

  before(async () => {
    root = await mkdtemp(path.join(tmpdir(), "aifw-discovery-"));
    await mkdir(path.join(root, ".github", "workflows"), { recursive: true });
    await mkdir(path.join(root, "contracts"), { recursive: true });
    await mkdir(path.join(root, "docs", "adr"), { recursive: true });
    await mkdir(path.join(root, "docs", "decisions"), { recursive: true });
    await mkdir(path.join(root, "src"), { recursive: true });
    await writeFile(
      path.join(root, "package.json"),
      JSON.stringify({
        name: "fixture-app",
        scripts: { test: "node --test", build: "tsc" },
        dependencies: { next: "15.0.0", react: "19.0.0" },
        devDependencies: { typescript: "5.9.2" },
      }),
    );
    await writeFile(path.join(root, "package-lock.json"), "{}");
    await writeFile(path.join(root, "src", "index.ts"), "export {};\n");
    await writeFile(path.join(root, "tsconfig.json"), "{}");
    await writeFile(path.join(root, "README.md"), "# Fixture\n");
    await writeFile(
      path.join(root, ".github", "workflows", "ci.yml"),
      "name: CI",
    );
    await writeFile(
      path.join(root, "contracts", "openapi.yaml"),
      "openapi: 3.2.0",
    );
    await writeFile(
      path.join(root, "docs", "adr", "0001-stack.md"),
      "# ADR 0001",
    );
    await writeFile(
      path.join(root, "docs", "decisions", "ADR-0002-boundaries.md"),
      "# ADR 0002",
    );
  });

  after(async () => {
    await rm(root, { recursive: true, force: true });
  });

  it("discovers commands, dependencies, CI, contracts and ADRs without writing", async () => {
    const { discoverProject } = await loadDiscovery();
    const beforePackage = await readFile(path.join(root, "package.json"), "utf8");

    const result = await discoverProject(root);

    assert.equal(result.packageManager, "npm");
    assert.deepEqual(result.stacks, ["node"]);
    assert.deepEqual(result.platformTargets, []);
    assert.deepEqual(result.scripts, { build: "tsc", test: "node --test" });
    assert.deepEqual(result.dependencies, ["next", "react", "typescript"]);
    assert.deepEqual(result.contracts, ["contracts/openapi.yaml"]);
    assert.deepEqual(result.ciFiles, [".github/workflows/ci.yml"]);
    assert.deepEqual(result.adrFiles, [
      "docs/adr/0001-stack.md",
      "docs/decisions/ADR-0002-boundaries.md",
    ]);
    assert.deepEqual(result.moduleManifests, ["package.json"]);
    assert.deepEqual(result.entrypoints, ["src/index.ts"]);
    assert.deepEqual(result.configurationFiles, ["package.json", "tsconfig.json"]);
    assert.deepEqual(result.documentationFiles, [
      "README.md",
      "docs/adr/0001-stack.md",
      "docs/decisions/ADR-0002-boundaries.md",
    ]);
    assert.deepEqual(result.sourceRoots, ["src"]);
    assert.equal(
      await readFile(path.join(root, "package.json"), "utf8"),
      beforePackage,
    );
  });

  it("detects a Flutter mobile project and its checked-in platform targets", async () => {
    const { discoverProject } = await loadDiscovery();
    const flutterRoot = await mkdtemp(path.join(tmpdir(), "aifw-flutter-discovery-"));
    try {
      await Promise.all([
        mkdir(path.join(flutterRoot, "android")),
        mkdir(path.join(flutterRoot, "ios")),
        mkdir(path.join(flutterRoot, "lib")),
        mkdir(path.join(flutterRoot, "test")),
      ]);
      await writeFile(
        path.join(flutterRoot, "pubspec.yaml"),
        [
          "name: mobile_fixture",
          "environment:",
          "  sdk: '>=3.7.0 <4.0.0'",
          "dependencies:",
          "  flutter:",
          "    sdk: flutter",
          "dev_dependencies:",
          "  flutter_test:",
          "    sdk: flutter",
          "",
        ].join("\n"),
      );

      const result = await discoverProject(flutterRoot);

      assert.equal(result.packageManager, "unknown");
      assert.deepEqual(result.stacks, ["dart", "flutter"]);
      assert.deepEqual(result.platformTargets, ["android", "ios"]);
    } finally {
      await rm(flutterRoot, { recursive: true, force: true });
    }
  });

  it("detects a Python project and its factual entrypoint", async () => {
    const { discoverProject } = await loadDiscovery();
    const pythonRoot = await mkdtemp(path.join(tmpdir(), "aifw-python-discovery-"));
    try {
      await writeFile(
        path.join(pythonRoot, "pyproject.toml"),
        "[project]\nname = \"python-fixture\"\nversion = \"0.1.0\"\n",
      );
      await writeFile(path.join(pythonRoot, "main.py"), "print('fixture')\n");

      const result = await discoverProject(pythonRoot);

      assert.deepEqual(result.stacks, ["python"]);
      assert.deepEqual(result.moduleManifests, ["pyproject.toml"]);
      assert.deepEqual(result.entrypoints, ["main.py"]);
    } finally {
      await rm(pythonRoot, { recursive: true, force: true });
    }
  });
});
