import { readFile } from "node:fs/promises";
import path from "node:path";
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));

describe("Pi integration package", () => {
  it("publishes the routing and Codex handoff extension through the package manifest", async () => {
    const manifest = JSON.parse(await readFile(path.join(root, "package.json"), "utf8")) as {
      keywords?: string[];
      pi?: { extensions?: string[] };
      files?: string[];
    };

    assert.ok(manifest.keywords?.includes("pi-package"));
    assert.deepEqual(manifest.pi?.extensions, ["extensions/aifw.ts"]);
    assert.ok(manifest.files?.includes("extensions"));
    assert.match(
      await readFile(path.join(root, "extensions", "aifw.ts"), "utf8"),
      /aifw_route_task/u,
    );
    assert.match(
      await readFile(path.join(root, "extensions", "aifw.ts"), "utf8"),
      /aifw_codex_handoff/u,
    );
    assert.match(
      await readFile(path.join(root, "extensions", "aifw.ts"), "utf8"),
      /aifw-route/u,
    );
  });
});
