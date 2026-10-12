import { readFile } from "node:fs/promises";
import path from "node:path";
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { fileURLToPath } from "node:url";

import type { AnySchema } from "ajv";
import { Ajv2020 } from "ajv/dist/2020.js";
import fg from "fast-glob";
import { parse } from "yaml";

const root = fileURLToPath(new URL("..", import.meta.url));

describe("published JSON Schema contracts", () => {
  it("ships and compiles every framework document contract", async () => {
    const expected = [
      "agent-trace.schema.json",
      "brownfield-adoption.schema.json",
      "brownfield-discovery.schema.json",
      "capability-delta.schema.json",
      "capability-spec.schema.json",
      "catalog.schema.json",
      "change-case.schema.json",
      "change-tasks.schema.json",
      "charter.schema.json",
      "codex-handoff.schema.json",
      "conformance-case.schema.json",
      "decision-case.schema.json",
      "decision-catalog.schema.json",
      "decision-record.schema.json",
      "effective-policy.schema.json",
      "framework-lock.schema.json",
      "impasse.schema.json",
      "permissions.schema.json",
      "policy-set.schema.json",
      "principle-catalog.schema.json",
      "principle-review.schema.json",
      "profile.schema.json",
      "project-manifest.schema.json",
      "quality-gates.schema.json",
      "routing.schema.json",
      "spec-change.schema.json",
      "traceability.schema.json",
      "waiver.schema.json",
    ];
    const files = await fg("*.schema.json", { cwd: path.join(root, "schemas"), onlyFiles: true });
    assert.deepEqual(files.sort(), expected);

    const ajv = new Ajv2020({ strict: true, allErrors: true });
    for (const file of files) {
      const schema = JSON.parse(
        await readFile(path.join(root, "schemas", file), "utf8"),
      ) as AnySchema;
      assert.doesNotThrow(() => ajv.compile(schema), file);
    }
  });

  it("validates the bundled core policy, profiles and decision catalogs", async () => {
    const ajv = new Ajv2020({ strict: true, allErrors: true });
    const policySchema = JSON.parse(
      await readFile(path.join(root, "schemas", "policy-set.schema.json"), "utf8"),
    ) as AnySchema;
    const profileSchema = JSON.parse(
      await readFile(path.join(root, "schemas", "profile.schema.json"), "utf8"),
    ) as AnySchema;
    const decisionCatalogSchema = JSON.parse(
      await readFile(path.join(root, "schemas", "decision-catalog.schema.json"), "utf8"),
    ) as AnySchema;
    const principleCatalogSchema = JSON.parse(
      await readFile(path.join(root, "schemas", "principle-catalog.schema.json"), "utf8"),
    ) as AnySchema;
    const validatePolicy = ajv.compile(policySchema);
    const validateProfile = ajv.compile(profileSchema);
    const validateDecisionCatalog = ajv.compile(decisionCatalogSchema);
    const validatePrincipleCatalog = ajv.compile(principleCatalogSchema);
    const policy = parse(await readFile(path.join(root, "policies", "core.yaml"), "utf8"));
    assert.equal(validatePolicy(policy), true, JSON.stringify(validatePolicy.errors));
    for (const profileId of ["flutter-mobile", "python", "web-ts"]) {
      const profile = parse(
        await readFile(path.join(root, "profiles", profileId, "profile.yaml"), "utf8"),
      );
      assert.equal(
        validateProfile(profile),
        true,
        `${profileId}: ${JSON.stringify(validateProfile.errors)}`,
      );
    }
    const decisionCatalogs = await fg(
      ["decision-catalogs/*.yaml", "profiles/*/decisions/*.yaml"],
      { cwd: root, onlyFiles: true },
    );
    assert.ok(decisionCatalogs.length >= 4);
    for (const relativePath of decisionCatalogs) {
      const catalog = parse(await readFile(path.join(root, relativePath), "utf8"));
      assert.equal(
        validateDecisionCatalog(catalog),
        true,
        `${relativePath}: ${JSON.stringify(validateDecisionCatalog.errors)}`,
      );
    }
    const principleCatalogs = await fg("principle-catalogs/*.yaml", {
      cwd: root,
      onlyFiles: true,
    });
    assert.ok(principleCatalogs.length >= 1);
    for (const relativePath of principleCatalogs) {
      const catalog = parse(await readFile(path.join(root, relativePath), "utf8"));
      assert.equal(
        validatePrincipleCatalog(catalog),
        true,
        `${relativePath}: ${JSON.stringify(validatePrincipleCatalog.errors)}`,
      );
    }
  });

  it("validates every executable-spec template against its public contract", async () => {
    const pairs = [
      ["capability-spec.yaml", "capability-spec.schema.json"],
      ["capability-delta.yaml", "capability-delta.schema.json"],
      ["change-tasks.yaml", "change-tasks.schema.json"],
      ["traceability.yaml", "traceability.schema.json"],
    ] as const;
    const ajv = new Ajv2020({ strict: true, allErrors: true });

    for (const [templateName, schemaName] of pairs) {
      const schema = JSON.parse(
        await readFile(path.join(root, "schemas", schemaName), "utf8"),
      ) as AnySchema;
      const value: unknown = parse(
        await readFile(path.join(root, "templates", templateName), "utf8"),
      );
      const validate = ajv.compile(schema);
      assert.equal(
        validate(value),
        true,
        `${templateName}: ${JSON.stringify(validate.errors)}`,
      );
    }
  });
});
