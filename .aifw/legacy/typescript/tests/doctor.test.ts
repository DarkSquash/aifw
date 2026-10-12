import assert from "node:assert/strict";
import { describe, it } from "node:test";

type DoctorModule = typeof import("../src/core/doctor.ts");

async function loadDoctor(): Promise<DoctorModule> {
  try {
    return await import("../src/core/doctor.ts");
  } catch (error) {
    assert.fail(`doctor module must be implemented: ${String(error)}`);
  }
}

describe("Windows and WSL environment doctor", () => {
  it("preserves a spawn failure message for diagnosis", async () => {
    const { systemCommandRunner } = await loadDoctor();

    const result = await systemCommandRunner("aifw-command-that-does-not-exist", []);

    assert.equal(result.ok, false);
    assert.match(result.stderr, /ENOENT|not found/iu);
  });

  it("reports Windows as primary and WSL as a separate validation target", async () => {
    const { runDoctor } = await loadDoctor();
    const calls: string[] = [];
    const report = await runDoctor({
      platform: "win32",
      run: async (command, args) => {
        calls.push([command, ...args].join(" "));
        if (command === "node") return { ok: true, stdout: "v24.15.0", stderr: "" };
        if (command === "git") return { ok: true, stdout: "git version 2.55.0", stderr: "" };
        if (args[0] === "--status") return { ok: true, stdout: "Default Distribution: Ubuntu", stderr: "" };
        return { ok: true, stdout: "v22.14.0", stderr: "" };
      },
    });

    assert.equal(report.primaryEnvironment, "windows");
    assert.equal(report.wsl.available, true);
    assert.equal(report.wsl.nodeAvailable, true);
    assert.ok(calls.includes("wsl.exe --status"));
    assert.ok(report.guidance.some((item) => item.includes("node_modules")));
  });

  it("treats WSL access denial as unavailable without failing Windows checks", async () => {
    const { runDoctor } = await loadDoctor();
    const report = await runDoctor({
      platform: "win32",
      run: async (command) => {
        if (command === "node") return { ok: true, stdout: "v24.15.0", stderr: "" };
        if (command === "git") return { ok: true, stdout: "git version 2.55.0", stderr: "" };
        return {
          ok: false,
          stdout: "",
          stderr: "Wsl/EnumerateDistros/Service/E_ACCESSDENIED",
        };
      },
    });

    assert.equal(report.healthy, true);
    assert.equal(report.wsl.available, false);
    assert.equal(report.wsl.reason, "access-denied");
  });

  it("marks the environment unhealthy when the primary Node runtime is absent", async () => {
    const { runDoctor } = await loadDoctor();
    const report = await runDoctor({
      platform: "linux",
      run: async (command) => ({
        ok: command === "git",
        stdout: command === "git" ? "git version 2.55.0" : "",
        stderr: command === "git" ? "" : "command not found",
      }),
    });

    assert.equal(report.healthy, false);
    assert.equal(report.checks.node.status, "fail");
    assert.equal(report.wsl.applicable, false);
  });
});
