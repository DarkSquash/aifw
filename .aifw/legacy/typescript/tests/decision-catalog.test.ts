import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { describe, it } from "node:test";

type DecisionModule = typeof import("../src/core/decision-catalog.ts");
type WorkspaceModule = typeof import("../src/core/workspace.ts");

async function modules(): Promise<{
  decisions: DecisionModule;
  workspace: WorkspaceModule;
}> {
  try {
    return {
      decisions: await import("../src/core/decision-catalog.ts"),
      workspace: await import("../src/core/workspace.ts"),
    };
  } catch (error) {
    assert.fail(`global decision catalog must be implemented: ${String(error)}`);
  }
}

const architectureCatalog = `
apiVersion: aifw.dev/v1alpha1
kind: DecisionCatalog
metadata:
  id: core-application-architecture
  version: 1.0.0
  category: application-architecture
  scope: core
  impact: L2
spec:
  title: Application architecture
  drivers:
    - id: domain-complexity
      prompt: How complex is the business domain?
      signals: [domain:simple, domain:complex]
    - id: integration-count
      prompt: How many external integrations exist?
      signals: [integrations:few, integrations:many]
  options:
    - id: pragmatic-layered
      name: Pragmatic layered
      summary: Minimal UI, application and data boundaries.
      status: recommended
      maturity: stable
      criteria:
        - signal: domain:simple
          effect: prefer
          weight: 3
          reason: Simple domains benefit from fewer abstractions.
        - signal: domain:complex
          effect: avoid
          weight: 2
          reason: Complex rules need stronger isolation.
      tradeoffs: [Lower ceremony, Fewer isolation boundaries]
      requires: []
      conflicts: []
      sources: [https://example.test/layered]
    - id: ports-and-adapters
      name: Ports and adapters
      summary: Domain behavior behind explicit ports.
      status: supported
      maturity: stable
      criteria:
        - signal: domain:complex
          effect: prefer
          weight: 4
          reason: Isolates complex business rules.
        - signal: integrations:many
          effect: prefer
          weight: 3
          reason: Adapters contain integration churn.
      tradeoffs: [More interfaces, Higher initial cost]
      requires: []
      conflicts: [active-record-only]
      sources: [https://example.test/ports]
`;

describe("framework-wide architecture decision catalogs", () => {
  it("ranks eligible options from explicit project signals and explains every score", async () => {
    const { decisions } = await modules();
    const catalog = decisions.parseDecisionCatalog(
      architectureCatalog,
      "architecture.fixture.yaml",
    );

    const result = decisions.recommendDecision([catalog], {
      category: "application-architecture",
      signals: ["domain:complex", "integrations:many"],
      selectedOptionIds: [],
    });

    const top = result.rankings[0];
    assert.ok(top);
    assert.equal(top.optionId, "ports-and-adapters");
    assert.equal(top.score, 7);
    assert.deepEqual(
      top.reasons,
      [
        "+4 domain:complex: Isolates complex business rules.",
        "+3 integrations:many: Adapters contain integration churn.",
      ],
    );
    assert.deepEqual(result.unansweredDrivers, []);
    assert.match(result.digest, /^[a-f0-9]{64}$/u);
    assert.equal(result.requiresHumanApproval, true);
    assert.equal(result.recordRequired, "ADR");
  });

  it("excludes conflicts and returns the missing decision questions instead of inventing certainty", async () => {
    const { decisions } = await modules();
    const catalog = decisions.parseDecisionCatalog(
      architectureCatalog,
      "architecture.fixture.yaml",
    );

    const result = decisions.recommendDecision([catalog], {
      category: "application-architecture",
      signals: [],
      selectedOptionIds: ["active-record-only"],
    });

    assert.equal(
      result.rankings.find((ranking) => ranking.optionId === "ports-and-adapters")?.eligible,
      false,
    );
    assert.deepEqual(
      result.unansweredDrivers.map((driver) => driver.id),
      ["domain-complexity", "integration-count"],
    );
    assert.equal(result.confidence, "low");
  });

  it("loads core and selected-profile catalogs for every project, then persists a reviewable case", async () => {
    const { decisions, workspace } = await modules();
    const root = await mkdtemp(path.join(tmpdir(), "aifw-decision-profile-"));
    await workspace.initializeProject(root, {
      id: "mobile-app",
      name: "Mobile App",
      projectType: "existing",
      locale: "pt-BR",
      primaryEnvironment: "windows",
      validationTargets: ["windows"],
    });
    const manifestPath = path.join(root, "aifw.yaml");
    await writeFile(
      manifestPath,
      (await readFile(manifestPath, "utf8")).replace(
        "profiles: []",
        "profiles:\n  - flutter-mobile",
      ),
      "utf8",
    );

    const result = await decisions.recommendWorkspaceDecision(root, {
      category: "state-management",
      signals: ["stack:flutter", "project:existing", "existing:provider"],
      selectedOptionIds: [],
      write: true,
    });

    assert.equal(result.rankings[0]?.optionId, "flutter-provider");
    assert.match(
      await readFile(
        path.join(root, ".aifw", "decision-cases", "state-management.json"),
        "utf8",
      ),
      /"digest": "[a-f0-9]{64}"/u,
    );
  });

  it("requires a human and an existing in-repository ADR before approving a decision", async () => {
    const { decisions, workspace } = await modules();
    const root = await mkdtemp(path.join(tmpdir(), "aifw-decision-approval-"));
    await workspace.initializeProject(root, {
      id: "northstar",
      name: "Northstar",
      projectType: "new",
      locale: "pt-BR",
      primaryEnvironment: "windows",
      validationTargets: ["windows"],
    });
    await decisions.recommendWorkspaceDecision(root, {
      category: "application-architecture",
      signals: ["domain:complex", "integrations:many", "testability:high"],
      selectedOptionIds: [],
      write: true,
    });
    await mkdir(path.join(root, "docs", "adr"), { recursive: true });
    await writeFile(
      path.join(root, "docs", "adr", "ADR-0001-architecture.md"),
      "# ADR-0001\n\nDecision: ports-and-adapters\n",
    );

    await assert.rejects(
      () =>
        decisions.approveWorkspaceDecision(root, {
          category: "application-architecture",
          optionId: "ports-and-adapters",
          approvedBy: "agent:sol",
          approvedAt: "2026-08-22T18:00:00.000Z",
          adrPath: "docs/adr/ADR-0001-architecture.md",
        }),
      /human approval/iu,
    );

    const record = await decisions.approveWorkspaceDecision(root, {
      category: "application-architecture",
      optionId: "ports-and-adapters",
      approvedBy: "human:owner",
      approvedAt: "2026-08-22T18:00:00.000Z",
      adrPath: "docs/adr/ADR-0001-architecture.md",
    });

    assert.equal(record.optionId, "ports-and-adapters");
    assert.match(record.adr.digest, /^[a-f0-9]{64}$/u);
    assert.match(
      await readFile(
        path.join(root, ".aifw", "decisions", "application-architecture.yaml"),
        "utf8",
      ),
      /approvedBy: human:owner/u,
    );
  });
});
