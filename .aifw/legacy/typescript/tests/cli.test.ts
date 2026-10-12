import { spawnSync } from "node:child_process";
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";

const projectRoot = fileURLToPath(new URL("..", import.meta.url));

function runCli(...args: string[]) {
  return spawnSync(
    process.execPath,
    ["src/cli.ts", ...args],
    {
      cwd: projectRoot,
      encoding: "utf8",
      env: { ...process.env, NO_COLOR: "1" },
    },
  );
}

describe("aifw CLI", () => {
  it("reports its public version", () => {
    const result = runCli("--version");

    assert.equal(result.status, 0);
    assert.equal(result.stdout.trim(), "0.2.0");
    assert.equal(result.stderr, "");
  });
});
