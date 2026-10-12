import assert from "node:assert/strict";
import { describe, it } from "node:test";

type ConfigModule = typeof import("../src/core/config.ts");

async function loadConfig(): Promise<ConfigModule> {
  try {
    return await import("../src/core/config.ts");
  } catch (error) {
    assert.fail(`config module must be implemented: ${String(error)}`);
  }
}

const validManifest = `
apiVersion: aifw.dev/v1alpha1
kind: Project
metadata:
  id: northstar
  name: Northstar
spec:
  frameworkVersion: 0.1.0
  projectType: new
  locale: pt-BR
  primaryEnvironment: windows
  validationTargets:
    - windows
    - wsl
    - linux-ci
  profiles:
    - web-ts
  dataClassification: internal
  externalAllowlist:
    - context7
`;

describe("project manifest", () => {
  it("parses a valid pinned project configuration", async () => {
    const { parseProjectManifest } = await loadConfig();

    const manifest = parseProjectManifest(validManifest);

    assert.equal(manifest.metadata.id, "northstar");
    assert.equal(manifest.spec.frameworkVersion, "0.1.0");
    assert.equal(manifest.spec.primaryEnvironment, "windows");
    assert.deepEqual(manifest.spec.validationTargets, [
      "windows",
      "wsl",
      "linux-ci",
    ]);
    assert.deepEqual(manifest.spec.externalAllowlist, ["context7"]);
  });

  it("rejects an unpinned framework version", async () => {
    const { parseProjectManifest } = await loadConfig();
    const input = validManifest.replace(
      "frameworkVersion: 0.1.0",
      'frameworkVersion: "latest"',
    );

    assert.throws(
      () => parseProjectManifest(input),
      (error: unknown) => {
        assert.equal(
          (error as { code?: string }).code,
          "MANIFEST_INVALID",
        );
        assert.match(String(error), /frameworkVersion/);
        return true;
      },
    );
  });

  it("rejects duplicate YAML keys instead of silently choosing one", async () => {
    const { parseProjectManifest } = await loadConfig();
    const input = validManifest.replace(
      "  locale: pt-BR",
      "  locale: pt-BR\n  locale: en-US",
    );

    assert.throws(
      () => parseProjectManifest(input),
      (error: unknown) => {
        assert.equal((error as { code?: string }).code, "YAML_INVALID");
        assert.match(String(error), /unique|duplicate/i);
        return true;
      },
    );
  });

  it("rejects unsupported primary environments", async () => {
    const { parseProjectManifest } = await loadConfig();
    const input = validManifest.replace(
      "primaryEnvironment: windows",
      "primaryEnvironment: solaris",
    );

    assert.throws(
      () => parseProjectManifest(input),
      (error: unknown) => {
        assert.equal(
          (error as { code?: string }).code,
          "MANIFEST_INVALID",
        );
        assert.match(String(error), /primaryEnvironment/);
        return true;
      },
    );
  });
});
