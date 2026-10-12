import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { describe, it } from "node:test";

import { initializeProject } from "../src/core/workspace.ts";

type BrownfieldModule = typeof import("../src/core/brownfield.ts");

async function loadBrownfield(): Promise<BrownfieldModule> {
  try {
    return await import("../src/core/brownfield.ts");
  } catch (error) {
    assert.fail(`brownfield adoption module must be implemented: ${String(error)}`);
  }
}

async function existingProject(): Promise<string> {
  const root = await mkdtemp(path.join(tmpdir(), "aifw-brownfield-"));
  await mkdir(path.join(root, "src"), { recursive: true });
  await mkdir(path.join(root, "contracts"), { recursive: true });
  await mkdir(path.join(root, "docs", "adr"), { recursive: true });
  await mkdir(path.join(root, ".github", "workflows"), { recursive: true });
  await writeFile(
    path.join(root, "package.json"),
    JSON.stringify({
      name: "northstar-app",
      scripts: { test: "node --test", build: "tsc" },
      dependencies: { react: "19.0.0" },
    }),
  );
  await writeFile(path.join(root, "package-lock.json"), "{}");
  await writeFile(path.join(root, "src", "index.ts"), "export {};\n");
  await writeFile(path.join(root, "contracts", "openapi.yaml"), "openapi: 3.1.0\n");
  await writeFile(path.join(root, "docs", "adr", "0001-architecture.md"), "# ADR 0001\n");
  await writeFile(path.join(root, ".github", "workflows", "ci.yml"), "name: CI\n");
  await initializeProject(root, {
    id: "northstar",
    name: "Northstar",
    projectType: "existing",
    locale: "pt-BR",
    primaryEnvironment: "windows",
    validationTargets: ["windows"],
    profiles: ["web-ts"],
  });
  return root;
}

describe("brownfield adoption", () => {
  it("builds a deterministic factual mapping proposal without writing it", async () => {
    const brownfield = await loadBrownfield();
    const root = await existingProject();
    const packageBefore = await readFile(path.join(root, "package.json"), "utf8");

    const first = await brownfield.analyzeBrownfieldProject(root, {
      generatedAt: "2026-08-29T14:00:00.000Z",
    });
    const second = await brownfield.analyzeBrownfieldProject(root, {
      generatedAt: "2026-08-29T14:00:00.000Z",
    });

    assert.equal(first.kind, "BrownfieldDiscovery");
    assert.equal(first.projectId, "northstar");
    assert.equal(first.digest, second.digest);
    assert.match(first.digest, /^[a-f0-9]{64}$/u);
    assert.deepEqual(first.discovery.entrypoints, ["src/index.ts"]);
    assert.deepEqual(
      first.candidates.entities.map((entity) => entity.id),
      [
        "component:northstar-root",
        "contract:contracts-openapi-yaml",
        "decision:docs-adr-0001-architecture-md",
        "resource:github-workflows-ci-yml",
      ],
    );
    assert.ok(
      first.unknowns.some((unknown) => /responsibilit|responsabil/iu.test(unknown)),
    );
    assert.equal(await readFile(path.join(root, "package.json"), "utf8"), packageBefore);
    await assert.rejects(
      () => readFile(path.join(root, ".aifw", "adoption", "discovery.json"), "utf8"),
      /ENOENT/u,
    );
  });

  it("persists a reviewable discovery report without changing the catalog", async () => {
    const brownfield = await loadBrownfield();
    const root = await existingProject();
    const catalogBefore = await readFile(path.join(root, ".aifw", "catalog.yaml"), "utf8");

    const written = await brownfield.writeBrownfieldAnalysis(root, {
      generatedAt: "2026-08-29T14:00:00.000Z",
    });

    assert.equal(written.reportPath, ".aifw/adoption/discovery.json");
    assert.equal(written.state.status, "analyzed");
    assert.equal(written.state.reportDigest, written.report.digest);
    assert.deepEqual(
      JSON.parse(
        await readFile(path.join(root, ".aifw", "adoption", "discovery.json"), "utf8"),
      ),
      written.report,
    );
    assert.match(
      await readFile(path.join(root, ".aifw", "adoption", "status.yaml"), "utf8"),
      /status: analyzed[\s\S]*reportDigest: [a-f0-9]{64}/u,
    );
    assert.equal(
      await readFile(path.join(root, ".aifw", "catalog.yaml"), "utf8"),
      catalogBefore,
    );
  });

  it("applies only factual candidates to the catalog and writes a reviewable architecture inventory", async () => {
    const brownfield = await loadBrownfield();
    const root = await existingProject();
    await brownfield.writeBrownfieldAnalysis(root, {
      generatedAt: "2026-08-29T14:00:00.000Z",
    });

    const first = await brownfield.applyBrownfieldMapping(root, {
      appliedAt: "2026-08-29T14:05:00.000Z",
    });
    const second = await brownfield.applyBrownfieldMapping(root, {
      appliedAt: "2026-08-29T14:05:00.000Z",
    });

    assert.equal(first.state.status, "review-required");
    assert.equal(first.projectMap.current, true);
    assert.deepEqual(first.appliedEntityIds, second.appliedEntityIds);
    assert.deepEqual(first.appliedEntityIds, [
      "component:northstar-root",
      "contract:contracts-openapi-yaml",
      "decision:docs-adr-0001-architecture-md",
      "resource:github-workflows-ci-yml",
    ]);
    const catalog = await readFile(path.join(root, ".aifw", "catalog.yaml"), "utf8");
    assert.equal((catalog.match(/id: component:northstar-root/gu) ?? []).length, 1);
    assert.match(catalog, /id: system:northstar/u);
    assert.match(catalog, /Brownfield discovery/u);
    const architecture = await readFile(
      path.join(root, "docs", "architecture", "discovered.md"),
      "utf8",
    );
    assert.match(architecture, /src\/index\.ts/u);
    assert.match(architecture, /contracts\/openapi\.yaml/u);
    assert.match(architecture, /requires human review/iu);
    assert.match(await readFile(path.join(root, "PROJECT_MAP.md"), "utf8"), /component:northstar-root/u);
  });

  it("requires human review before confirming discovered entities", async () => {
    const brownfield = await loadBrownfield();
    const root = await existingProject();
    await brownfield.writeBrownfieldAnalysis(root, {
      generatedAt: "2026-08-29T14:00:00.000Z",
    });
    await brownfield.applyBrownfieldMapping(root, {
      appliedAt: "2026-08-29T14:05:00.000Z",
    });

    await assert.rejects(
      () =>
        brownfield.approveBrownfieldMapping(root, {
          approvedBy: "agent:orchestrator",
          approvedAt: "2026-08-29T14:10:00.000Z",
        }),
      (error: unknown) => {
        assert.equal((error as { code?: string }).code, "APPROVAL_REQUIRED");
        return true;
      },
    );
    const approved = await brownfield.approveBrownfieldMapping(root, {
      approvedBy: "human:owner",
      approvedAt: "2026-08-29T14:10:00.000Z",
    });

    assert.equal(approved.state.status, "approved");
    assert.equal(approved.state.approval?.approvedBy, "human:owner");
    const catalog = await readFile(path.join(root, ".aifw", "catalog.yaml"), "utf8");
    assert.doesNotMatch(catalog, /human:unassigned/u);
    assert.doesNotMatch(catalog, /confidence: candidate/u);
    assert.equal((catalog.match(/confidence: confirmed/gu) ?? []).length, 4);
    const assessment = await brownfield.assessBrownfieldAdoption(root);
    assert.equal(assessment.status, "current");
    assert.equal(assessment.blockingHumanApproval, false);
    assert.equal(assessment.nextAction, undefined);
  });

  it("detects catalog drift after human approval", async () => {
    const brownfield = await loadBrownfield();
    const root = await existingProject();
    await brownfield.writeBrownfieldAnalysis(root, {
      generatedAt: "2026-08-29T14:00:00.000Z",
    });
    await brownfield.applyBrownfieldMapping(root, {
      appliedAt: "2026-08-29T14:05:00.000Z",
    });
    await brownfield.approveBrownfieldMapping(root, {
      approvedBy: "human:owner",
      approvedAt: "2026-08-29T14:10:00.000Z",
    });
    const catalogPath = path.join(root, ".aifw", "catalog.yaml");
    const catalog = await readFile(catalogPath, "utf8");
    await writeFile(
      catalogPath,
      catalog.replace(
        "Discovered module manifest at package.json; responsibility requires review.",
        "Responsibility changed after approval.",
      ),
      "utf8",
    );

    const assessment = await brownfield.assessBrownfieldAdoption(root);

    assert.equal(assessment.status, "invalid");
    assert.equal(assessment.blockingHumanApproval, true);
    assert.match(assessment.reason, /digest|changed|drift/iu);
    assert.match(assessment.nextAction ?? "", /adopt apply/iu);
  });
});
