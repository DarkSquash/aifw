import assert from "node:assert/strict";
import { access, mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { describe, it } from "node:test";

import { initializeProject } from "../src/core/workspace.ts";

type SpecLifecycleModule = typeof import("../src/core/spec-lifecycle.ts");

async function loadSpecLifecycle(): Promise<SpecLifecycleModule> {
  try {
    return await import("../src/core/spec-lifecycle.ts");
  } catch (error) {
    assert.fail(`spec lifecycle module must be implemented: ${String(error)}`);
  }
}

async function project(): Promise<string> {
  const root = await mkdtemp(path.join(tmpdir(), "aifw-spec-lifecycle-"));
  await initializeProject(root, {
    id: "northstar",
    name: "Northstar",
    projectType: "new",
    locale: "pt-BR",
    primaryEnvironment: "windows",
    validationTargets: ["windows"],
  });
  return root;
}

describe("executable spec lifecycle", () => {
  it("creates a self-contained active change and lists it deterministically", async () => {
    const spec = await loadSpecLifecycle();
    const root = await project();

    const created = await spec.createSpecChange(root, {
      id: "add-customer-search",
      title: "Add customer search",
      summary: "Allow operators to find customers safely.",
      level: "L2",
      createdAt: "2026-08-29T12:00:00.000Z",
    });

    assert.equal(created.change.metadata.id, "add-customer-search");
    assert.equal(created.change.status, "draft");
    assert.deepEqual(created.createdFiles, [
      ".aifw/changes/active/add-customer-search/change.yaml",
      ".aifw/changes/active/add-customer-search/design.md",
      ".aifw/changes/active/add-customer-search/evidence/README.md",
      ".aifw/changes/active/add-customer-search/proposal.md",
      ".aifw/changes/active/add-customer-search/specs/README.md",
      ".aifw/changes/active/add-customer-search/tasks.yaml",
      ".aifw/changes/active/add-customer-search/traceability.yaml",
    ]);
    await assert.doesNotReject(() =>
      access(path.join(root, ".aifw", "changes", "active", "add-customer-search", "change.yaml")),
    );
    assert.match(
      await readFile(
        path.join(root, ".aifw", "changes", "active", "add-customer-search", "proposal.md"),
        "utf8",
      ),
      /Add customer search/u,
    );

    const listed = await spec.listSpecChanges(root);
    assert.deepEqual(
      listed.map((entry) => ({ id: entry.id, status: entry.status, location: entry.location })),
      [{ id: "add-customer-search", status: "draft", location: "active" }],
    );
  });

  it("reports orphan requirements and scenarios without verification", async () => {
    const spec = await loadSpecLifecycle();
    const root = await project();
    await spec.createSpecChange(root, {
      id: "add-customer-search",
      title: "Add customer search",
      summary: "Allow operators to find customers safely.",
      level: "L2",
      createdAt: "2026-08-29T12:00:00.000Z",
    });
    await writeFile(
      path.join(
        root,
        ".aifw",
        "changes",
        "active",
        "add-customer-search",
        "specs",
        "customer-search.delta.yaml",
      ),
      `apiVersion: aifw.dev/v1alpha1
kind: CapabilityDelta
changeId: add-customer-search
capability: customer-search
title: Customer search
purpose: Find customer records without exposing restricted data.
operations:
  added:
    - id: REQ-CUSTOMER-SEARCH
      strength: MUST
      statement: The system must find customers by an approved identifier.
      scenarios:
        - id: SCN-CUSTOMER-SEARCH-VALID
          given: [an authorized operator]
          when: [the operator searches by an approved identifier]
          then: [matching customer records are returned]
  modified: []
  removed: []
`,
      "utf8",
    );

    const analysis = await spec.analyzeSpecChange(root, "add-customer-search");

    assert.equal(analysis.pass, false);
    assert.deepEqual(
      analysis.findings.map((finding) => finding.code).sort(),
      ["ORPHAN_REQUIREMENT", "SCENARIO_WITHOUT_VERIFICATION"],
    );
    assert.deepEqual(analysis.coverage, {
      requirements: { total: 1, linkedToTask: 0 },
      scenarios: { total: 1, verified: 0 },
      tasks: { total: 0, completed: 0 },
    });
  });

  it("rejects a trace link whose target artifact does not exist", async () => {
    const spec = await loadSpecLifecycle();
    const root = await project();
    const base = path.join(root, ".aifw", "changes", "active", "add-search");
    await spec.createSpecChange(root, {
      id: "add-search",
      title: "Add search",
      summary: "Add a verifiable search capability.",
      level: "L2",
      createdAt: "2026-08-29T12:00:00.000Z",
    });
    await writeFile(
      path.join(base, "specs", "search.delta.yaml"),
      `apiVersion: aifw.dev/v1alpha1
kind: CapabilityDelta
changeId: add-search
capability: search
title: Search
purpose: Search records.
operations:
  added:
    - id: REQ-SEARCH
      strength: MUST
      statement: The system must search records.
      scenarios:
        - id: SCN-SEARCH
          given: [an authorized user]
          when: [a query is submitted]
          then: [matching records are returned]
  modified: []
  removed: []
`,
      "utf8",
    );
    await writeFile(
      path.join(base, "tasks.yaml"),
      `apiVersion: aifw.dev/v1alpha1
kind: ChangeTasks
changeId: add-search
tasks:
  - id: TASK-SEARCH
    title: Implement search
    status: done
    dependsOn: []
    requirementIds: [REQ-SEARCH]
    paths: [src/search.ts]
`,
      "utf8",
    );
    await writeFile(
      path.join(base, "traceability.yaml"),
      `apiVersion: aifw.dev/v1alpha1
kind: ChangeTraceability
changeId: add-search
artifacts: []
links:
  - from: SCN-SEARCH
    relation: verifiedBy
    to: TEST-MISSING
`,
      "utf8",
    );

    const analysis = await spec.analyzeSpecChange(root, "add-search");

    assert.equal(analysis.pass, false);
    assert.deepEqual(
      analysis.findings.map((finding) => finding.code).sort(),
      ["DANGLING_TRACE_LINK", "SCENARIO_WITHOUT_VERIFICATION"],
    );
  });

  it("reports a task that references an unknown requirement", async () => {
    const spec = await loadSpecLifecycle();
    const root = await project();
    const base = path.join(root, ".aifw", "changes", "active", "unknown-requirement");
    await spec.createSpecChange(root, {
      id: "unknown-requirement",
      title: "Unknown requirement",
      summary: "Exercise trace integrity.",
      level: "L2",
      createdAt: "2026-08-29T12:00:00.000Z",
    });
    await writeFile(
      path.join(base, "specs", "search.delta.yaml"),
      `apiVersion: aifw.dev/v1alpha1
kind: CapabilityDelta
changeId: unknown-requirement
capability: search
title: Search
purpose: Search records.
operations:
  added:
    - id: REQ-SEARCH
      strength: MUST
      statement: The system must search records.
      scenarios:
        - id: SCN-SEARCH
          given: [an authorized user]
          when: [a query is submitted]
          then: [matching records are returned]
  modified: []
  removed: []
`,
      "utf8",
    );
    await writeFile(
      path.join(base, "tasks.yaml"),
      `apiVersion: aifw.dev/v1alpha1
kind: ChangeTasks
changeId: unknown-requirement
tasks:
  - id: TASK-SEARCH
    title: Implement search
    status: pending
    dependsOn: []
    requirementIds: [REQ-NOT-DECLARED]
    paths: [src/search.ts]
`,
      "utf8",
    );

    const analysis = await spec.analyzeSpecChange(root, "unknown-requirement");

    assert.deepEqual(
      analysis.findings.map((finding) => finding.code).sort(),
      ["ORPHAN_REQUIREMENT", "SCENARIO_WITHOUT_VERIFICATION", "TASK_UNKNOWN_REQUIREMENT"],
    );
  });

  it("rejects a delta that modifies a requirement absent from current truth", async () => {
    const spec = await loadSpecLifecycle();
    const root = await project();
    const base = path.join(root, ".aifw", "changes", "active", "modify-search");
    await spec.createSpecChange(root, {
      id: "modify-search",
      title: "Modify search",
      summary: "Change search behavior.",
      level: "L2",
      createdAt: "2026-08-29T12:00:00.000Z",
    });
    const currentDirectory = path.join(root, ".aifw", "specs", "current");
    await mkdir(currentDirectory, { recursive: true });
    await writeFile(
      path.join(currentDirectory, "search.yaml"),
      `apiVersion: aifw.dev/v1alpha1
kind: CapabilitySpec
capability: search
title: Search
purpose: Search current records.
requirements:
  - id: REQ-SEARCH-EXISTING
    strength: MUST
    statement: The system must search by identifier.
    scenarios:
      - id: SCN-SEARCH-EXISTING
        given: [an authorized user]
        when: [an identifier is submitted]
        then: [the matching record is returned]
`,
      "utf8",
    );
    await writeFile(
      path.join(base, "specs", "search.delta.yaml"),
      `apiVersion: aifw.dev/v1alpha1
kind: CapabilityDelta
changeId: modify-search
capability: search
title: Search
operations:
  added: []
  modified:
    - id: REQ-SEARCH-MISSING
      strength: MUST
      statement: The system must search by approved fields.
      scenarios:
        - id: SCN-SEARCH-MISSING
          given: [an authorized user]
          when: [an approved field is submitted]
          then: [the matching record is returned]
  removed: []
`,
      "utf8",
    );

    const validation = await spec.validateSpecChange(root, "modify-search");

    assert.equal(validation.pass, false);
    assert.deepEqual(
      validation.findings.map((finding) => finding.code),
      ["DELTA_MODIFIES_UNKNOWN_REQUIREMENT"],
    );
  });

  it("rejects adding an existing requirement and removing an unknown one", async () => {
    const spec = await loadSpecLifecycle();
    const root = await project();
    const base = path.join(root, ".aifw", "changes", "active", "invalid-delta");
    await spec.createSpecChange(root, {
      id: "invalid-delta",
      title: "Invalid delta",
      summary: "Exercise delta preconditions.",
      level: "L2",
      createdAt: "2026-08-29T12:00:00.000Z",
    });
    const currentDirectory = path.join(root, ".aifw", "specs", "current");
    await mkdir(currentDirectory, { recursive: true });
    await writeFile(
      path.join(currentDirectory, "search.yaml"),
      `apiVersion: aifw.dev/v1alpha1
kind: CapabilitySpec
capability: search
title: Search
purpose: Search current records.
requirements:
  - id: REQ-SEARCH
    strength: MUST
    statement: The system must search by identifier.
    scenarios:
      - id: SCN-SEARCH
        given: [an authorized user]
        when: [an identifier is submitted]
        then: [the matching record is returned]
`,
      "utf8",
    );
    await writeFile(
      path.join(base, "specs", "search.delta.yaml"),
      `apiVersion: aifw.dev/v1alpha1
kind: CapabilityDelta
changeId: invalid-delta
capability: search
title: Search
operations:
  added:
    - id: REQ-SEARCH
      strength: MUST
      statement: The system must search by identifier.
      scenarios:
        - id: SCN-SEARCH-NEW
          given: [an authorized user]
          when: [an identifier is submitted]
          then: [the matching record is returned]
  modified: []
  removed:
    - id: REQ-NOT-CURRENT
      reason: It is obsolete.
`,
      "utf8",
    );

    const validation = await spec.validateSpecChange(root, "invalid-delta");

    assert.deepEqual(
      validation.findings.map((finding) => finding.code).sort(),
      ["DELTA_ADDS_EXISTING_REQUIREMENT", "DELTA_REMOVES_UNKNOWN_REQUIREMENT"],
    );
  });

  it("requires a purpose when a delta creates a new capability", async () => {
    const spec = await loadSpecLifecycle();
    const root = await project();
    const base = path.join(root, ".aifw", "changes", "active", "new-capability");
    await spec.createSpecChange(root, {
      id: "new-capability",
      title: "New capability",
      summary: "Create a capability with explicit intent.",
      level: "L2",
      createdAt: "2026-08-29T12:00:00.000Z",
    });
    await writeFile(
      path.join(base, "specs", "search.delta.yaml"),
      `apiVersion: aifw.dev/v1alpha1
kind: CapabilityDelta
changeId: new-capability
capability: search
title: Search
operations:
  added:
    - id: REQ-SEARCH
      strength: MUST
      statement: The system must search records.
      scenarios:
        - id: SCN-SEARCH
          given: [an authorized user]
          when: [a query is submitted]
          then: [matching records are returned]
  modified: []
  removed: []
`,
      "utf8",
    );

    const validation = await spec.validateSpecChange(root, "new-capability");

    assert.deepEqual(
      validation.findings.map((finding) => finding.code),
      ["NEW_CAPABILITY_REQUIRES_PURPOSE"],
    );
  });

  it("requires at least one capability delta for an L2 change", async () => {
    const spec = await loadSpecLifecycle();
    const root = await project();
    await spec.createSpecChange(root, {
      id: "empty-feature",
      title: "Empty feature",
      summary: "An L2 feature cannot be ready without a behavior delta.",
      level: "L2",
      createdAt: "2026-08-29T12:00:00.000Z",
    });

    const validation = await spec.validateSpecChange(root, "empty-feature");

    assert.deepEqual(
      validation.findings.map((finding) => finding.code),
      ["CHANGE_REQUIRES_DELTA"],
    );
  });

  it("previews a deterministic spec merge without mutating current truth", async () => {
    const spec = await loadSpecLifecycle();
    const root = await project();
    const base = path.join(root, ".aifw", "changes", "active", "add-search");
    await spec.createSpecChange(root, {
      id: "add-search",
      title: "Add search",
      summary: "Add a search capability.",
      level: "L2",
      createdAt: "2026-08-29T12:00:00.000Z",
    });
    await writeFile(
      path.join(base, "specs", "search.delta.yaml"),
      `apiVersion: aifw.dev/v1alpha1
kind: CapabilityDelta
changeId: add-search
capability: search
title: Search
purpose: Find records by approved identifiers.
operations:
  added:
    - id: REQ-SEARCH
      strength: MUST
      statement: The system must search records.
      scenarios:
        - id: SCN-SEARCH
          given: [an authorized user]
          when: [a query is submitted]
          then: [matching records are returned]
  modified: []
  removed: []
`,
      "utf8",
    );

    const preview = await spec.previewSpecSync(root, "add-search");

    assert.equal(preview.pass, true);
    assert.deepEqual(preview.changes, [
      {
        capability: "search",
        action: "create",
        added: ["REQ-SEARCH"],
        modified: [],
        removed: [],
        outputPath: ".aifw/specs/current/search.yaml",
      },
    ]);
    assert.equal(preview.outputs[0]?.spec.kind, "CapabilitySpec");
    await assert.rejects(
      () => readFile(path.join(root, ".aifw", "specs", "current", "search.yaml"), "utf8"),
      /ENOENT/u,
    );
  });

  it("refuses to archive a change that was not marked ready", async () => {
    const spec = await loadSpecLifecycle();
    const root = await project();
    await spec.createSpecChange(root, {
      id: "draft-change",
      title: "Draft change",
      summary: "Remain active until readiness is proven.",
      level: "L1",
      createdAt: "2026-08-29T12:00:00.000Z",
    });

    await assert.rejects(
      () =>
        spec.archiveSpecChange(root, "draft-change", {
          archivedAt: "2026-08-29T13:00:00.000Z",
        }),
      (error: unknown) => {
        assert.equal((error as { code?: string }).code, "NOT_READY");
        assert.match(String(error), /ready/iu);
        return true;
      },
    );
  });

  it("does not mark an L2 change ready while traceability is incomplete", async () => {
    const spec = await loadSpecLifecycle();
    const root = await project();
    const base = path.join(root, ".aifw", "changes", "active", "not-ready");
    await spec.createSpecChange(root, {
      id: "not-ready",
      title: "Not ready",
      summary: "Traceability must be complete before readiness.",
      level: "L2",
      createdAt: "2026-08-29T12:00:00.000Z",
    });
    await writeFile(
      path.join(base, "specs", "search.delta.yaml"),
      `apiVersion: aifw.dev/v1alpha1
kind: CapabilityDelta
changeId: not-ready
capability: search
title: Search
purpose: Search records.
operations:
  added:
    - id: REQ-SEARCH
      strength: MUST
      statement: The system must search records.
      scenarios:
        - id: SCN-SEARCH
          given: [an authorized user]
          when: [a query is submitted]
          then: [matching records are returned]
  modified: []
  removed: []
`,
      "utf8",
    );

    await assert.rejects(
      () => spec.updateSpecChangeStatus(root, "not-ready", "ready"),
      (error: unknown) => {
        assert.equal((error as { code?: string }).code, "NOT_READY");
        assert.match(String(error), /ORPHAN_REQUIREMENT|traceability/iu);
        return true;
      },
    );
    assert.match(await readFile(path.join(base, "change.yaml"), "utf8"), /status: draft/u);
  });

  it("atomically merges a ready change into current truth and archives its full context", async () => {
    const spec = await loadSpecLifecycle();
    const root = await project();
    const base = path.join(root, ".aifw", "changes", "active", "add-search");
    await spec.createSpecChange(root, {
      id: "add-search",
      title: "Add search",
      summary: "Add a tested search capability.",
      level: "L2",
      createdAt: "2026-08-29T12:00:00.000Z",
    });
    await writeFile(
      path.join(base, "specs", "search.delta.yaml"),
      `apiVersion: aifw.dev/v1alpha1
kind: CapabilityDelta
changeId: add-search
capability: search
title: Search
purpose: Find records by approved identifiers.
operations:
  added:
    - id: REQ-SEARCH
      strength: MUST
      statement: The system must search records.
      scenarios:
        - id: SCN-SEARCH
          given: [an authorized user]
          when: [a query is submitted]
          then: [matching records are returned]
  modified: []
  removed: []
`,
      "utf8",
    );
    await writeFile(
      path.join(base, "tasks.yaml"),
      `apiVersion: aifw.dev/v1alpha1
kind: ChangeTasks
changeId: add-search
tasks:
  - id: TASK-SEARCH
    title: Implement search
    status: done
    dependsOn: []
    requirementIds: [REQ-SEARCH]
    paths: [src/search.ts]
`,
      "utf8",
    );
    await mkdir(path.join(root, "src"), { recursive: true });
    await mkdir(path.join(root, "tests"), { recursive: true });
    await writeFile(path.join(root, "src", "search.ts"), "export const search = true;\n", "utf8");
    await writeFile(path.join(root, "tests", "search.test.ts"), "// passing evidence\n", "utf8");
    await writeFile(path.join(base, "evidence", "gates.json"), '{"status":"pass"}\n', "utf8");
    await writeFile(
      path.join(base, "traceability.yaml"),
      `apiVersion: aifw.dev/v1alpha1
kind: ChangeTraceability
changeId: add-search
artifacts:
  - id: TEST-SEARCH
    type: test
    path: tests/search.test.ts
    status: passed
  - id: GATE-QUALITY
    type: gate
    path: .aifw/changes/active/add-search/evidence/gates.json
    status: passed
  - id: EVID-QUALITY
    type: evidence
    path: .aifw/changes/active/add-search/evidence/gates.json
    status: passed
links:
  - from: SCN-SEARCH
    relation: verifiedBy
    to: TEST-SEARCH
  - from: REQ-SEARCH
    relation: checkedBy
    to: GATE-QUALITY
  - from: REQ-SEARCH
    relation: provedBy
    to: EVID-QUALITY
`,
      "utf8",
    );

    const ready = await spec.updateSpecChangeStatus(root, "add-search", "ready");
    assert.equal(ready.status, "ready");
    const archived = await spec.archiveSpecChange(root, "add-search", {
      archivedAt: "2026-08-29T13:00:00.000Z",
    });

    assert.deepEqual(archived, {
      changeId: "add-search",
      archivePath: ".aifw/changes/archive/2026-08-29-add-search",
      currentSpecs: [".aifw/specs/current/search.yaml"],
    });
    assert.match(
      await readFile(path.join(root, ".aifw", "specs", "current", "search.yaml"), "utf8"),
      /REQ-SEARCH/u,
    );
    await assert.rejects(() => readFile(path.join(base, "change.yaml"), "utf8"), /ENOENT/u);
    assert.match(
      await readFile(
        path.join(root, ".aifw", "changes", "archive", "2026-08-29-add-search", "change.yaml"),
        "utf8",
      ),
      /status: archived[\s\S]*archivedAt: 2026-08-29T13:00:00.000Z/u,
    );
    assert.deepEqual(
      (await spec.listSpecChanges(root)).map((entry) => ({
        id: entry.id,
        status: entry.status,
        location: entry.location,
      })),
      [{ id: "add-search", status: "archived", location: "archive" }],
    );
  });

  it("does not accept passed trace evidence whose referenced file is missing", async () => {
    const spec = await loadSpecLifecycle();
    const root = await project();
    const base = path.join(root, ".aifw", "changes", "active", "missing-evidence");
    await spec.createSpecChange(root, {
      id: "missing-evidence",
      title: "Missing evidence",
      summary: "Passed evidence must exist on disk.",
      level: "L2",
      createdAt: "2026-08-29T12:00:00.000Z",
    });
    await writeFile(
      path.join(base, "specs", "search.delta.yaml"),
      `apiVersion: aifw.dev/v1alpha1
kind: CapabilityDelta
changeId: missing-evidence
capability: search
title: Search
purpose: Search records.
operations:
  added:
    - id: REQ-SEARCH
      strength: MUST
      statement: The system must search records.
      scenarios:
        - id: SCN-SEARCH
          given: [an authorized user]
          when: [a query is submitted]
          then: [matching records are returned]
  modified: []
  removed: []
`,
      "utf8",
    );
    await writeFile(
      path.join(base, "tasks.yaml"),
      `apiVersion: aifw.dev/v1alpha1
kind: ChangeTasks
changeId: missing-evidence
tasks:
  - id: TASK-SEARCH
    title: Implement search
    status: done
    dependsOn: []
    requirementIds: [REQ-SEARCH]
    paths: [src/search.ts]
`,
      "utf8",
    );
    await writeFile(
      path.join(base, "traceability.yaml"),
      `apiVersion: aifw.dev/v1alpha1
kind: ChangeTraceability
changeId: missing-evidence
artifacts:
  - id: TEST-SEARCH
    type: test
    path: tests/does-not-exist.test.ts
    status: passed
links:
  - from: SCN-SEARCH
    relation: verifiedBy
    to: TEST-SEARCH
`,
      "utf8",
    );

    const analysis = await spec.analyzeSpecChange(root, "missing-evidence");

    assert.deepEqual(
      analysis.findings.map((finding) => finding.code),
      ["SCENARIO_WITHOUT_VERIFICATION", "TRACE_ARTIFACT_MISSING"],
    );
    assert.equal(analysis.pass, false);
  });

  it("requires persisted human approval before an L3 change can become ready", async () => {
    const spec = await loadSpecLifecycle();
    const root = await project();
    const base = path.join(root, ".aifw", "changes", "active", "change-core");
    await spec.createSpecChange(root, {
      id: "change-core",
      title: "Change core",
      summary: "Change a framework-level capability.",
      level: "L3",
      createdAt: "2026-08-29T12:00:00.000Z",
    });
    await writeFile(
      path.join(base, "specs", "core.delta.yaml"),
      `apiVersion: aifw.dev/v1alpha1
kind: CapabilityDelta
changeId: change-core
capability: core
title: Core
purpose: Govern framework behavior.
operations:
  added:
    - id: REQ-CORE
      strength: MUST
      statement: The core must enforce approved changes.
      scenarios:
        - id: SCN-CORE
          given: [an approved change]
          when: [the change is archived]
          then: [current truth is updated]
  modified: []
  removed: []
`,
      "utf8",
    );
    await writeFile(
      path.join(base, "tasks.yaml"),
      `apiVersion: aifw.dev/v1alpha1
kind: ChangeTasks
changeId: change-core
tasks:
  - id: TASK-CORE
    title: Implement core change
    status: done
    dependsOn: []
    requirementIds: [REQ-CORE]
    paths: [src/core/change.ts]
`,
      "utf8",
    );
    await mkdir(path.join(root, "src", "core"), { recursive: true });
    await mkdir(path.join(root, "tests"), { recursive: true });
    await writeFile(path.join(root, "src", "core", "change.ts"), "export {};\n", "utf8");
    await writeFile(path.join(root, "tests", "core.test.ts"), "// passing evidence\n", "utf8");
    await writeFile(path.join(base, "evidence", "gates.json"), '{"status":"pass"}\n', "utf8");
    await writeFile(
      path.join(base, "traceability.yaml"),
      `apiVersion: aifw.dev/v1alpha1
kind: ChangeTraceability
changeId: change-core
artifacts:
  - id: TEST-CORE
    type: test
    path: tests/core.test.ts
    status: passed
  - id: GATE-CORE
    type: gate
    path: .aifw/changes/active/change-core/evidence/gates.json
    status: passed
  - id: EVID-CORE
    type: evidence
    path: .aifw/changes/active/change-core/evidence/gates.json
    status: passed
links:
  - from: SCN-CORE
    relation: verifiedBy
    to: TEST-CORE
  - from: REQ-CORE
    relation: checkedBy
    to: GATE-CORE
  - from: REQ-CORE
    relation: provedBy
    to: EVID-CORE
`,
      "utf8",
    );

    await assert.rejects(
      () => spec.updateSpecChangeStatus(root, "change-core", "ready"),
      (error: unknown) => {
        assert.equal((error as { code?: string }).code, "APPROVAL_REQUIRED");
        return true;
      },
    );
  });

  it("persists an L3 approval only from a human and an in-project ADR", async () => {
    const spec = await loadSpecLifecycle();
    const root = await project();
    await spec.createSpecChange(root, {
      id: "approved-core",
      title: "Approved core",
      summary: "Exercise explicit L3 approval.",
      level: "L3",
      createdAt: "2026-08-29T12:00:00.000Z",
    });
    await mkdir(path.join(root, "docs", "adr"), { recursive: true });
    await writeFile(
      path.join(root, "docs", "adr", "ADR-0009-approved-core.md"),
      "# ADR-0009\n\nStatus: accepted\n",
      "utf8",
    );

    await assert.rejects(
      () =>
        spec.approveSpecChange(root, "approved-core", {
          approvedBy: "agent:orchestrator",
          approvedAt: "2026-08-29T12:30:00.000Z",
          record: "docs/adr/ADR-0009-approved-core.md",
        }),
      (error: unknown) => {
        assert.equal((error as { code?: string }).code, "APPROVAL_REQUIRED");
        return true;
      },
    );

    const approved = await spec.approveSpecChange(root, "approved-core", {
      approvedBy: "human:owner",
      approvedAt: "2026-08-29T12:30:00.000Z",
      record: "docs/adr/ADR-0009-approved-core.md",
    });

    assert.deepEqual(approved.approval, {
      approvedBy: "human:owner",
      approvedAt: "2026-08-29T12:30:00.000Z",
      record: "docs/adr/ADR-0009-approved-core.md",
    });
    assert.match(
      await readFile(
        path.join(root, ".aifw", "changes", "active", "approved-core", "change.yaml"),
        "utf8",
      ),
      /approvedBy: human:owner/u,
    );
  });

  it("rejects duplicate requirement and scenario ids across capability deltas", async () => {
    const spec = await loadSpecLifecycle();
    const root = await project();
    const base = path.join(root, ".aifw", "changes", "active", "duplicate-ids");
    await spec.createSpecChange(root, {
      id: "duplicate-ids",
      title: "Duplicate ids",
      summary: "Stable trace ids must be unique across the change.",
      level: "L2",
      createdAt: "2026-08-29T12:00:00.000Z",
    });
    const delta = (capability: string, title: string) => `apiVersion: aifw.dev/v1alpha1
kind: CapabilityDelta
changeId: duplicate-ids
capability: ${capability}
title: ${title}
purpose: ${title} capability.
operations:
  added:
    - id: REQ-DUPLICATE
      strength: MUST
      statement: The system must provide ${title}.
      scenarios:
        - id: SCN-DUPLICATE
          given: [an authorized user]
          when: [the capability is used]
          then: [the result is returned]
  modified: []
  removed: []
`;
    await writeFile(path.join(base, "specs", "one.delta.yaml"), delta("one", "One"), "utf8");
    await writeFile(path.join(base, "specs", "two.delta.yaml"), delta("two", "Two"), "utf8");

    const validation = await spec.validateSpecChange(root, "duplicate-ids");

    assert.deepEqual(
      validation.findings.map((finding) => finding.code).sort(),
      ["DUPLICATE_REQUIREMENT_ID", "DUPLICATE_SCENARIO_ID"],
    );
  });
});
