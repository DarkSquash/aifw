import assert from "node:assert/strict";
import fs from "node:fs/promises";
import { syncBuiltinESMExports } from "node:module";
import { tmpdir } from "node:os";
import path from "node:path";
import { describe, it } from "node:test";

import { Ajv2020 } from "ajv/dist/2020.js";
import type { AnySchema } from "ajv";
import { parse } from "yaml";

import {
  analyzeSpecChange, approveSpecChange, archiveSpecChange, createSpecChange,
  updateSpecChangeStatus, validateSpecChange,
  type CapabilityDelta, type CapabilitySpec, type ChangeTraceability, type SpecChangeRecord,
} from "../src/core/spec-lifecycle.ts";

const at = "2026-09-06T02:00:00.000Z";
const id = "integrity";
const archiveRelative = `.aifw/changes/archive/2026-09-06-${id}`;

async function fixture() {
  const root = await fs.realpath(await fs.mkdtemp(path.join(tmpdir(), "aifw-integrity-")));
  await createSpecChange(root, { id, title: "Integrity", summary: "Archive regression", level: "L2", createdAt: at });
  const base = path.join(root, ".aifw/changes/active", id);
  const delta: CapabilityDelta = {
    apiVersion: "aifw.dev/v1alpha1", kind: "CapabilityDelta", changeId: id,
    capability: "search", title: "Search", purpose: "Find records",
    operations: { added: [{ id: "REQ-ONE", strength: "MUST", statement: "Find records",
      scenarios: [{ id: "SCN-ONE", given: ["input"], when: ["search"], then: ["records"] }],
    }], modified: [], removed: [] },
  };
  const trace: ChangeTraceability = {
    apiVersion: "aifw.dev/v1alpha1", kind: "ChangeTraceability", changeId: id,
    artifacts: [{ id: "TEST-ONE", type: "test", status: "passed", path: "tests/search.test.ts" }],
    links: [{ from: "SCN-ONE", relation: "verifiedBy", to: "TEST-ONE" }],
  };
  await fs.mkdir(path.join(root, "tests"));
  await fs.writeFile(path.join(root, "tests/search.test.ts"), "// isolated test artifact\n");
  await fs.writeFile(path.join(base, "specs/search.delta.yaml"), JSON.stringify(delta));
  await fs.writeFile(path.join(base, "traceability.yaml"), JSON.stringify(trace));
  await fs.writeFile(path.join(base, "tasks.yaml"), JSON.stringify({
    apiVersion: "aifw.dev/v1alpha1", kind: "ChangeTasks", changeId: id,
    tasks: [{ id: "TASK-ONE", title: "Implement", status: "done", dependsOn: [], requirementIds: ["REQ-ONE"], paths: [] }],
  }));
  await fs.mkdir(path.join(root, ".aifw/specs/current"), { recursive: true });
  await fs.writeFile(path.join(root, ".aifw/specs/current/sentinel.txt"), "original accepted state");
  return { root, base, delta, trace };
}

async function recordAt(base: string): Promise<SpecChangeRecord> {
  return parse(await fs.readFile(path.join(base, "change.yaml"), "utf8")) as SpecChangeRecord;
}

async function assertUnchanged(root: string, base: string) {
  assert.equal(await fs.readFile(path.join(root, ".aifw/specs/current/sentinel.txt"), "utf8"), "original accepted state");
  await fs.access(path.join(base, "change.yaml"));
  await assert.rejects(fs.access(path.join(root, archiveRelative)), /ENOENT/u);
  await assert.rejects(fs.access(path.join(root, ".aifw/specs/current/search.yaml")), /ENOENT/u);
}

describe("spec archive integrity", { concurrency: false }, () => {
  it("preserves committed specs and archive when backup cleanup fails partway", async () => {
    const { root, base } = await fixture();
    await updateSpecChangeStatus(root, id, "ready");
    const originalRm = fs.rm;
    let injected = false;
    fs.rm = async (target, options) => {
      const resolved = path.resolve(String(target));
      assert.ok(resolved.startsWith(root + path.sep), "fault injection stays in fixture");
      if (!injected && path.basename(path.dirname(resolved)) === "transactions") {
        injected = true;
        await originalRm(path.join(resolved, "previous-current"), { recursive: true, force: true });
        await originalRm(path.join(resolved, "previous-active"), { recursive: true, force: true });
        throw new Error("Injected EACCES during cleanup");
      }
      return originalRm(target, options);
    };
    syncBuiltinESMExports();
    try {
      const result = await archiveSpecChange(root, id, { archivedAt: at });
      assert.ok("cleanupPending" in result, "caller must receive a recoverable cleanup warning");
      const current = parse(await fs.readFile(path.join(root, ".aifw/specs/current/search.yaml"), "utf8")) as CapabilitySpec;
      assert.deepEqual(current.requirements.map((requirement) => requirement.id), ["REQ-ONE"]);
      await fs.access(path.join(root, archiveRelative, "change.yaml"));
      await assert.rejects(fs.access(path.join(base, "change.yaml")), /ENOENT/u);
    } finally {
      fs.rm = originalRm;
      syncBuiltinESMExports();
    }
  });

  for (const destination of ["previous-current", "current", "previous-active", "2026-09-06-integrity"]) {
    it(`restores accepted specs and active context when rename to ${destination} fails`, async () => {
      const { root, base } = await fixture();
      await updateSpecChangeStatus(root, id, "ready");
      const originalRename = fs.rename;
      let injected = false;
      fs.rename = async (from, to) => {
        if (!injected && path.basename(String(to)) === destination) {
          injected = true;
          throw new Error("Injected rename failure");
        }
        return originalRename(from, to);
      };
      syncBuiltinESMExports();
      try {
        await assert.rejects(archiveSpecChange(root, id, { archivedAt: at }), /rolled back/u);
        await assertUnchanged(root, base);
      } finally {
        fs.rename = originalRename;
        syncBuiltinESMExports();
      }
    });
  }

  it("rejects an L3 reclassification after readiness without approval", async () => {
    const { root, base } = await fixture();
    await updateSpecChangeStatus(root, id, "ready");
    const record = await recordAt(base);
    record.metadata.level = "L3";
    await fs.writeFile(path.join(base, "change.yaml"), JSON.stringify(record));
    await assert.rejects(archiveSpecChange(root, id, { archivedAt: at }), { code: "APPROVAL_REQUIRED" });
    await assertUnchanged(root, base);
  });

  for (const invalidation of ["removed-approval", "removed-record", "agent-identity", "directory-record"] as const) {
    it(`revalidates L3 approval at archive after ${invalidation}`, async () => {
      const { root, base } = await fixture();
      const record = await recordAt(base);
      record.metadata.level = "L3";
      await fs.writeFile(path.join(base, "change.yaml"), JSON.stringify(record));
      await fs.writeFile(path.join(root, "approval.md"), "Isolated fixture authorization");
      await approveSpecChange(root, id, { approvedBy: "human:test-fixture", approvedAt: at, record: "approval.md" });
      await updateSpecChangeStatus(root, id, "ready");
      const ready = await recordAt(base);
      if (invalidation === "removed-record") await fs.unlink(path.join(root, "approval.md"));
      if (invalidation === "removed-approval") delete ready.approval;
      if (invalidation === "agent-identity") ready.approval!.approvedBy = "agent:test";
      if (invalidation === "directory-record") ready.approval!.record = "tests";
      await fs.writeFile(path.join(base, "change.yaml"), JSON.stringify(ready));
      await assert.rejects(archiveSpecChange(root, id, { archivedAt: at }), { code: "APPROVAL_REQUIRED" });
      await assertUnchanged(root, base);
    });
  }

  it("blocks two deltas targeting one capability before overwriting requirements", async () => {
    const { root, base, delta } = await fixture();
    const second = structuredClone(delta);
    second.operations.added[0]!.id = "REQ-TWO";
    second.operations.added[0]!.scenarios[0]!.id = "SCN-TWO";
    await fs.writeFile(path.join(base, "specs/second.delta.yaml"), JSON.stringify(second));
    const validation = await validateSpecChange(root, id);
    assert.equal(validation.pass, false);
    assert.ok(validation.findings.some((finding) => finding.code === "DUPLICATE_CAPABILITY_DELTA"));
    await assertUnchanged(root, base);
  });

  it("archives an L3 change with a valid persisted approval", async () => {
    const { root, base } = await fixture();
    const record = await recordAt(base);
    record.metadata.level = "L3";
    await fs.writeFile(path.join(base, "change.yaml"), JSON.stringify(record));
    await fs.writeFile(path.join(root, "approval.md"), "Isolated fixture authorization");
    await approveSpecChange(root, id, { approvedBy: "human:test-fixture", approvedAt: at, record: "approval.md" });
    await updateSpecChangeStatus(root, id, "ready");
    const archived = await archiveSpecChange(root, id, { archivedAt: at });
    await fs.access(path.join(root, archived.archivePath, "change.yaml"));
    assert.equal("cleanupPending" in archived, false);
  });

  it("rejects approval and evidence escaping through a directory link", async () => {
    const { root, base, trace } = await fixture();
    const outside = await fs.mkdtemp(path.join(tmpdir(), "aifw-outside-evidence-"));
    await fs.writeFile(path.join(outside, "proof.md"), "Outside fixture root");
    await fs.symlink(outside, path.join(root, "linked"), process.platform === "win32" ? "junction" : "dir");
    trace.artifacts[0]!.path = "linked/proof.md";
    await fs.writeFile(path.join(base, "traceability.yaml"), JSON.stringify(trace));
    const analysis = await analyzeSpecChange(root, id);
    assert.equal(analysis.pass, false);
    assert.ok(analysis.findings.some((finding) => finding.code === "TRACE_ARTIFACT_OUTSIDE_PROJECT"));
    await assert.rejects(
      approveSpecChange(root, id, { approvedBy: "human:test-fixture", approvedAt: at, record: "linked/proof.md" }),
      { code: "APPROVAL_REQUIRED" },
    );
  });

  it("does not count a passed test without an evidence path as verified", async () => {
    const { root, base, trace } = await fixture();
    delete trace.artifacts[0]!.path;
    await fs.writeFile(path.join(base, "traceability.yaml"), JSON.stringify(trace));
    const analysis = await analyzeSpecChange(root, id);
    assert.equal(analysis.pass, false);
    assert.equal(analysis.coverage.scenarios.verified, 0);
    await assert.rejects(updateSpecChangeStatus(root, id, "ready"), { code: "NOT_READY" });
  });

  it("rejects a directory used as passed test evidence", async () => {
    const { root, base, trace } = await fixture();
    trace.artifacts[0]!.path = "tests";
    await fs.writeFile(path.join(base, "traceability.yaml"), JSON.stringify(trace));
    assert.equal((await analyzeSpecChange(root, id)).pass, false);
  });

  for (const status of ["failed", "planned", "waived"] as const) {
    it(`blocks a checkedBy gate that is ${status} even after readiness`, async () => {
      const { root, base, trace } = await fixture();
      await updateSpecChangeStatus(root, id, "ready");
      trace.artifacts.push({ id: "GATE-ONE", type: "gate", status });
      trace.links.push({ from: "REQ-ONE", relation: "checkedBy", to: "GATE-ONE" });
      await fs.writeFile(path.join(base, "traceability.yaml"), JSON.stringify(trace));
      assert.equal((await analyzeSpecChange(root, id)).pass, false);
      await assert.rejects(archiveSpecChange(root, id, { archivedAt: at }), { code: "NOT_READY" });
      await assertUnchanged(root, base);
    });
  }

  it("keeps an unlinked audit observation non-blocking", async () => {
    const { root, base, trace } = await fixture();
    trace.artifacts.push({ id: "AUDIT-OBSERVATION", type: "gate", status: "failed" });
    await fs.writeFile(path.join(base, "traceability.yaml"), JSON.stringify(trace));
    assert.equal((await analyzeSpecChange(root, id)).pass, true);
    await updateSpecChangeStatus(root, id, "ready");
    await archiveSpecChange(root, id, { archivedAt: at });
  });

  for (const title of ["", "   "]) {
    it(`rejects delta title ${JSON.stringify(title)} before contaminating current specs`, async () => {
      const { root, base, delta } = await fixture();
      delta.title = title;
      await fs.writeFile(path.join(base, "specs/search.delta.yaml"), JSON.stringify(delta));
      await assert.rejects(validateSpecChange(root, id), { code: "MANIFEST_INVALID" });
      await assertUnchanged(root, base);
    });
  }

  it("aligns published delta and trace schemas with integrity requirements", async () => {
    const { delta, trace } = await fixture();
    const ajv = new Ajv2020({ strict: true });
    const deltaSchema = JSON.parse(await fs.readFile(new URL("../schemas/capability-delta.schema.json", import.meta.url), "utf8")) as AnySchema;
    const traceSchema = JSON.parse(await fs.readFile(new URL("../schemas/traceability.schema.json", import.meta.url), "utf8")) as AnySchema;
    const validateDelta = ajv.compile(deltaSchema);
    const validateTrace = ajv.compile(traceSchema);
    assert.equal(validateDelta(delta), true);
    assert.equal(validateTrace(trace), true);
    delta.title = "   ";
    assert.equal(validateDelta(delta), false);
    delete trace.artifacts[0]!.path;
    assert.equal(validateTrace(trace), false);
  });
});
