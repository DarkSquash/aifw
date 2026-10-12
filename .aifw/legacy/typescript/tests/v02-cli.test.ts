import { spawnSync } from "node:child_process";
import { mkdir, mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";

const frameworkRoot = fileURLToPath(new URL("..", import.meta.url));
const cliPath = path.join(frameworkRoot, "src", "cli.ts");

function runCli(root: string, ...args: string[]) {
  return spawnSync(process.execPath, [cliPath, ...args], {
    cwd: root,
    encoding: "utf8",
    env: { ...process.env, NO_COLOR: "1" },
  });
}

describe("AIFW v0.2 CLI", () => {
  it("exposes the executable spec lifecycle and read-only analyzer", async () => {
    const root = await mkdtemp(path.join(tmpdir(), "aifw-v02-spec-cli-"));
    const init = runCli(
      root,
      "init",
      "--id",
      "northstar",
      "--name",
      "Northstar",
      "--json",
    );
    assert.equal(init.status, 0, init.stderr);

    const created = runCli(
      root,
      "spec",
      "new",
      "add-search",
      "--title",
      "Add search",
      "--summary",
      "Add a verified search capability.",
      "--level",
      "L2",
      "--at",
      "2026-08-29T12:00:00.000Z",
      "--json",
    );
    assert.equal(created.status, 0, created.stderr);
    assert.equal((JSON.parse(created.stdout) as { status: string }).status, "created");

    const list = runCli(root, "spec", "list", "--json");
    assert.equal(list.status, 0, list.stderr);
    assert.deepEqual(
      (JSON.parse(list.stdout) as Array<{ id: string; status: string }>).map((entry) => ({
        id: entry.id,
        status: entry.status,
      })),
      [{ id: "add-search", status: "draft" }],
    );

    const activated = runCli(
      root,
      "spec",
      "status",
      "add-search",
      "--set",
      "active",
      "--json",
    );
    assert.equal(activated.status, 0, activated.stderr);
    assert.equal((JSON.parse(activated.stdout) as { status: string }).status, "active");

    const shown = runCli(root, "spec", "show", "add-search", "--json");
    assert.equal(shown.status, 0, shown.stderr);
    assert.equal((JSON.parse(shown.stdout) as { id: string }).id, "add-search");

    const validation = runCli(root, "spec", "validate", "add-search", "--json");
    assert.equal(validation.status, 2, validation.stderr);
    assert.deepEqual(
      (JSON.parse(validation.stdout) as { findings: Array<{ code: string }> }).findings.map(
        (finding) => finding.code,
      ),
      ["CHANGE_REQUIRES_DELTA"],
    );

    const sync = runCli(root, "spec", "sync", "add-search", "--dry-run", "--json");
    assert.equal(sync.status, 2, sync.stderr);
    assert.equal((JSON.parse(sync.stdout) as { pass: boolean }).pass, false);

    const archive = runCli(root, "spec", "archive", "add-search", "--json");
    assert.equal(archive.status, 1);
    assert.match(archive.stderr, /NOT_READY.*ready/isu);

    const analysis = runCli(root, "spec", "analyze", "add-search", "--json");
    assert.equal(analysis.status, 0, analysis.stderr);
    assert.deepEqual(
      (JSON.parse(analysis.stdout) as { coverage: unknown }).coverage,
      {
        requirements: { total: 0, linkedToTask: 0 },
        scenarios: { total: 0, verified: 0 },
        tasks: { total: 0, completed: 0 },
      },
    );
  });

  it("runs the two-phase brownfield mapping and approval workflow", async () => {
    const root = await mkdtemp(path.join(tmpdir(), "aifw-v02-adopt-cli-"));
    await mkdir(path.join(root, "src"), { recursive: true });
    await writeFile(path.join(root, "package.json"), '{"name":"existing-app"}\n', "utf8");
    await writeFile(path.join(root, "package-lock.json"), "{}\n", "utf8");
    await writeFile(path.join(root, "src", "index.ts"), "export {};\n", "utf8");
    const init = runCli(
      root,
      "init",
      "--id",
      "existing-app",
      "--name",
      "Existing App",
      "--existing",
      "--web",
      "--json",
    );
    assert.equal(init.status, 0, init.stderr);

    const analyze = runCli(
      root,
      "adopt",
      "analyze",
      "--write",
      "--at",
      "2026-08-29T14:00:00.000Z",
      "--json",
    );
    assert.equal(analyze.status, 0, analyze.stderr);
    assert.equal((JSON.parse(analyze.stdout) as { persisted: boolean }).persisted, true);

    const apply = runCli(
      root,
      "adopt",
      "apply",
      "--at",
      "2026-08-29T14:05:00.000Z",
      "--json",
    );
    assert.equal(apply.status, 0, apply.stderr);
    assert.equal((JSON.parse(apply.stdout) as { status: string }).status, "review-required");

    const beforeApproval = runCli(root, "adopt", "status", "--json");
    assert.equal(beforeApproval.status, 2, beforeApproval.stderr);
    assert.equal(
      (JSON.parse(beforeApproval.stdout) as { status: string }).status,
      "review-required",
    );

    const approve = runCli(
      root,
      "adopt",
      "approve",
      "--by",
      "human:owner",
      "--at",
      "2026-08-29T14:10:00.000Z",
      "--json",
    );
    assert.equal(approve.status, 0, approve.stderr);
    assert.equal((JSON.parse(approve.stdout) as { status: string }).status, "approved");

    const afterApproval = runCli(root, "adopt", "status", "--json");
    assert.equal(afterApproval.status, 0, afterApproval.stderr);
    assert.equal((JSON.parse(afterApproval.stdout) as { status: string }).status, "current");
  });
});
