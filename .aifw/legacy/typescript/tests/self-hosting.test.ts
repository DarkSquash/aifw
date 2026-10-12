import { readFile } from "node:fs/promises";
import path from "node:path";
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";

import type { AnySchema } from "ajv";
import { Ajv2020 } from "ajv/dist/2020.js";
import { parse } from "yaml";

import { assessWorkspaceCharter } from "../src/core/charter-file.ts";
import { resolveWorkspace } from "../src/core/policy-loader.ts";
import { buildWorkspaceMap } from "../src/core/workspace.ts";

const root = fileURLToPath(new URL("..", import.meta.url));

describe("AIFW dogfoods its own control plane", () => {
  it("validates every committed control document against its published schema", async () => {
    const documents = [
      ["aifw.yaml", "project-manifest.schema.json", "yaml"],
      [".aifw/charter.yaml", "charter.schema.json", "yaml"],
      [".aifw/catalog.yaml", "catalog.schema.json", "yaml"],
      [".aifw/gates.yaml", "quality-gates.schema.json", "yaml"],
      [".aifw/routing.yaml", "routing.schema.json", "yaml"],
      [".aifw/permissions.yaml", "permissions.schema.json", "yaml"],
      [".aifw/framework.lock.yaml", "framework-lock.schema.json", "yaml"],
      [".aifw/effective-policy.json", "effective-policy.schema.json", "json"],
      [".aifw/adoption/discovery.json", "brownfield-discovery.schema.json", "json"],
      [".aifw/adoption/status.yaml", "brownfield-adoption.schema.json", "yaml"],
      [".aifw/specs/current/aifw-control-plane.yaml", "capability-spec.schema.json", "yaml"],
    ] as const;
    const ajv = new Ajv2020({ strict: true, allErrors: true });

    for (const [documentPath, schemaPath, encoding] of documents) {
      const schema = JSON.parse(
        await readFile(path.join(root, "schemas", schemaPath), "utf8"),
      ) as AnySchema;
      const source = await readFile(path.join(root, documentPath), "utf8");
      const value: unknown = encoding === "json" ? JSON.parse(source) : parse(source);
      const validate = ajv.compile(schema);
      assert.equal(validate(value), true, `${documentPath}: ${JSON.stringify(validate.errors)}`);
    }
  });

  it("keeps generated artifacts current and persists routing approval separately from charter approval", async () => {
    const [map, resolution, intake] = await Promise.all([
      buildWorkspaceMap(root, { write: false }),
      resolveWorkspace(root, { write: false }),
      assessWorkspaceCharter(root),
    ]);

    assert.equal(map.current, true);
    assert.equal(resolution.current, true);
    assert.equal(intake.ready, true);
    assert.match(await readFile(path.join(root, ".aifw", "charter.yaml"), "utf8"), /state: draft/);
    const routing = await readFile(path.join(root, ".aifw", "routing.yaml"), "utf8");
    assert.match(routing, /enabled: true/);
    assert.match(routing, /approvedBy: human:DarkSquash/);
    assert.match(routing, /cases: 32/);
  });
});
