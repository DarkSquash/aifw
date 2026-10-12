import { tmpdir } from "node:os";
import path from "node:path";
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { mkdtemp, readFile, rm, writeFile } from "node:fs/promises";

type GateRunnerModule = typeof import("../src/core/gate-runner.ts");
type WorkspaceModule = typeof import("../src/core/workspace.ts");

async function modules(): Promise<{ gates: GateRunnerModule; workspace: WorkspaceModule }> {
  try {
    return {
      gates: await import("../src/core/gate-runner.ts"),
      workspace: await import("../src/core/workspace.ts"),
    };
  } catch (error) {
    assert.fail(`gate runner must be implemented: ${String(error)}`);
  }
}

describe("executable progressive gate runner", () => {
  it("executes the npm shim portably and preserves spawn errors as evidence", async () => {
    const { gates } = await modules();

    const npm = await gates.systemGateRunner("npm", ["--version"], process.cwd());
    assert.equal(npm.ok, true, npm.stderr);
    assert.match(npm.stdout.trim(), /^\d+\.\d+\.\d+/u);

    const missing = await gates.systemGateRunner(
      "aifw-command-that-does-not-exist",
      [],
      process.cwd(),
    );
    assert.equal(missing.ok, false);
    assert.match(missing.stderr, /ENOENT|not found/iu);
  });

  it("executes Flutter and Dart batch shims on Windows without enabling an implicit shell", async (context) => {
    if (process.platform !== "win32") {
      context.skip("Windows-specific command shim behavior");
      return;
    }
    const { gates } = await modules();
    const root = await mkdtemp(path.join(tmpdir(), "aifw-flutter-shim-"));
    const previousPath = process.env["PATH"];
    try {
      const shim = path.join(root, "flutter.cmd");
      await writeFile(
        shim,
        "@echo off\r\nif \"%~1\"==\"analyze\" (echo flutter-analyze-ok& exit /b 0)\r\nexit /b 9\r\n",
      );
      await writeFile(
        path.join(root, "fvm.cmd"),
        "@echo off\r\nif \"%~1\"==\"flutter\" if \"%~2\"==\"analyze\" (echo fvm-flutter-analyze-ok& exit /b 0)\r\nexit /b 9\r\n",
      );
      process.env["PATH"] = `${root}${path.delimiter}${previousPath ?? ""}`;

      const result = await gates.systemGateRunner("flutter", ["analyze"], root);
      const fvmResult = await gates.systemGateRunner(
        "fvm",
        ["flutter", "analyze"],
        root,
      );

      assert.equal(result.ok, true, result.stderr);
      assert.equal(result.stdout.trim(), "flutter-analyze-ok");
      assert.equal(fvmResult.ok, true, fvmResult.stderr);
      assert.equal(fvmResult.stdout.trim(), "fvm-flutter-analyze-ok");
    } finally {
      if (previousPath === undefined) delete process.env["PATH"];
      else process.env["PATH"] = previousPath;
      await rm(root, { recursive: true, force: true });
    }
  });

  it("loads the Flutter Windows gate recipe as executable analyze, format and test behavior", async () => {
    const { gates } = await modules();
    const profileRoot = path.join(process.cwd(), "profiles", "flutter-mobile");
    const gateSet = gates.parseGateSet(
      await readFile(path.join(profileRoot, "gates.windows.yaml"), "utf8"),
      "profiles/flutter-mobile/gates.windows.yaml",
    );
    const calls: Array<{ executable: string; args: readonly string[] }> = [];

    const results = await gates.runGateSet(gateSet, "L1", {
      root: process.cwd(),
      run: async (executable, args) => {
        calls.push({ executable, args });
        return { ok: true, stdout: "ok", stderr: "" };
      },
      builtIns: new Map([
        [
          "manifest",
          {
            gateId: "manifest",
            enforcement: "hard",
            status: "pass",
            summary: "fixture",
            evidence: ["aifw.yaml"],
          },
        ],
        [
          "project-map",
          {
            gateId: "project-map",
            enforcement: "hard",
            status: "pass",
            summary: "fixture",
            evidence: ["PROJECT_MAP.md"],
          },
        ],
      ]),
    });

    assert.deepEqual(calls, [
      {
        executable: "dart",
        args: ["format", "--output=none", "--set-exit-if-changed", "lib", "test"],
      },
      { executable: "flutter", args: ["analyze"] },
      { executable: "flutter", args: ["test"] },
    ]);
    assert.equal(results.every((result) => result.status === "pass"), true);
  });

  it("loads the FVM recipe using the project-pinned Flutter SDK", async () => {
    const { gates } = await modules();
    const source = await readFile(
      path.join(process.cwd(), "profiles", "flutter-mobile", "gates.windows-fvm.yaml"),
      "utf8",
    );
    const gateSet = gates.parseGateSet(source, "gates.windows-fvm.yaml");
    const calls: Array<{ executable: string; args: readonly string[] }> = [];

    await gates.runGateSet(gateSet, "L1", {
      root: process.cwd(),
      run: async (executable, args) => {
        calls.push({ executable, args });
        return { ok: true, stdout: "ok", stderr: "" };
      },
      builtIns: new Map([
        ["manifest", { gateId: "manifest", enforcement: "hard", status: "pass", summary: "fixture", evidence: [] }],
        ["project-map", { gateId: "project-map", enforcement: "hard", status: "pass", summary: "fixture", evidence: [] }],
      ]),
    });

    assert.deepEqual(calls, [
      {
        executable: "fvm",
        args: ["dart", "format", "--output=none", "--set-exit-if-changed", "lib", "test"],
      },
      { executable: "fvm", args: ["flutter", "analyze"] },
      { executable: "fvm", args: ["flutter", "test"] },
    ]);
  });

  it("selects gates by impact and executes commands without a shell", async () => {
    const { gates } = await modules();
    const gateSet = gates.parseGateSet(`
apiVersion: aifw.dev/v1alpha1
kind: QualityGateSet
philosophy: progressive-by-risk
gates:
  - id: test
    enforcement: hard
    levels: [L1, L2, L3]
    command: [npm, test]
  - id: security-review
    enforcement: audit
    levels: [L2, L3]
    command: [npm, run, security]
`, "gates.yaml");
    const calls: Array<{ executable: string; args: readonly string[] }> = [];

    const results = await gates.runGateSet(gateSet, "L2", {
      root: "C:\\project",
      run: async (executable, args) => {
        calls.push({ executable, args });
        return executable === "npm" && args[0] === "test"
          ? { ok: true, stdout: "42 tests passed", stderr: "" }
          : { ok: false, stdout: "", stderr: "2 high findings" };
      },
      builtIns: new Map(),
    });

    assert.ok(
      calls.some(
        (call) => call.executable === "npm" && call.args.length === 1 && call.args[0] === "test",
      ),
    );
    assert.equal(results.find((result) => result.gateId === "test")?.status, "pass");
    assert.equal(
      results.find((result) => result.gateId === "security-review")?.status,
      "warning",
    );
  });

  it("marks a selected gate without a command or built-in as not-run", async () => {
    const { gates } = await modules();
    const gateSet = gates.parseGateSet(`
apiVersion: aifw.dev/v1alpha1
kind: QualityGateSet
philosophy: progressive-by-risk
gates:
  - id: independent-review
    enforcement: hard
    levels: [L2]
`, "gates.yaml");

    const results = await gates.runGateSet(gateSet, "L2", {
      root: ".",
      run: async () => ({ ok: true, stdout: "", stderr: "" }),
      builtIns: new Map(),
    });

    assert.equal(results[0]?.status, "not-run");
  });

  it("validates a newly initialized project at L0 and blocks missing L1 tests", async () => {
    const { gates, workspace } = await modules();
    const { mkdtemp } = await import("node:fs/promises");
    const root = await mkdtemp(path.join(tmpdir(), "aifw-gates-"));
    await workspace.initializeProject(root, {
      id: "northstar",
      name: "Northstar",
      projectType: "new",
      locale: "pt-BR",
      primaryEnvironment: "windows",
      validationTargets: ["windows"],
    });
    const runner = async () => ({ ok: true, stdout: "", stderr: "" });

    const l0 = await gates.validateWorkspace(root, "L0", { run: runner });
    assert.equal(l0.status, "pass");

    const l1 = await gates.validateWorkspace(root, "L1", { run: runner });
    assert.equal(l1.status, "blocked");
    assert.ok(l1.blockers.some((blocker) => blocker.gateId === "tests"));
  });
});
