import assert from "node:assert/strict";
import { describe, it } from "node:test";

type ProjectMapModule = typeof import("../src/core/project-map.ts");

async function loadProjectMap(): Promise<ProjectMapModule> {
  try {
    return await import("../src/core/project-map.ts");
  } catch (error) {
    assert.fail(`project map module must be implemented: ${String(error)}`);
  }
}

const entities = [
  {
    id: "component:web",
    kind: "Component" as const,
    name: "Web application",
    description: "Customer-facing web interface",
    owner: "human:owner",
    source: "package.json",
    visibility: "internal" as const,
    relations: [
      { type: "consumes" as const, target: "api:customers-v1" },
    ],
  },
  {
    id: "api:customers-v1",
    kind: "API" as const,
    name: "Customers API",
    description: "HTTP customer operations",
    owner: "human:owner",
    source: "contracts/openapi.yaml",
    visibility: "restricted" as const,
    relations: [
      { type: "providedBy" as const, target: "component:api" },
    ],
  },
  {
    id: "component:api",
    kind: "Component" as const,
    name: "API service",
    description: "Customer API implementation",
    owner: "human:owner",
    source: "apps/api/package.json",
    visibility: "internal" as const,
    relations: [],
  },
];

describe("PROJECT_MAP generation", () => {
  it("generates a deterministic human entrypoint with source links", async () => {
    const { buildProjectMap } = await loadProjectMap();
    const input = {
      project: { id: "northstar", name: "Northstar" },
      purpose: "Centralize customer operations",
      frameworkVersion: "0.1.0",
      verifiedRevision: "git:abc123",
      entities,
      sourcesOfTruth: [
        { topic: "Product intent", source: ".aifw/charter.yaml" },
        { topic: "HTTP API", source: "contracts/openapi.yaml" },
      ],
    };

    const first = buildProjectMap(input);
    const second = buildProjectMap(input);

    assert.equal(first.markdown, second.markdown);
    assert.equal(first.digest, second.digest);
    assert.match(first.markdown, /# PROJECT_MAP — Northstar/);
    assert.match(first.markdown, /component:web/);
    assert.match(first.markdown, /api:customers-v1/);
    assert.match(first.markdown, /contracts\/openapi\.yaml/);
    assert.match(first.markdown, /git:abc123/);
    assert.match(first.digest, /^[a-f0-9]{64}$/);
  });

  it("rejects duplicate entity ids", async () => {
    const { buildProjectMap } = await loadProjectMap();

    assert.throws(() =>
      buildProjectMap({
        project: { id: "northstar", name: "Northstar" },
        purpose: "Centralize customer operations",
        frameworkVersion: "0.1.0",
        verifiedRevision: "git:abc123",
        entities: [entities[0]!, entities[0]!],
        sourcesOfTruth: [],
      }),
    );
  });

  it("detects a stale committed map", async () => {
    const { buildProjectMap, checkProjectMap } = await loadProjectMap();
    const generated = buildProjectMap({
      project: { id: "northstar", name: "Northstar" },
      purpose: "Centralize customer operations",
      frameworkVersion: "0.1.0",
      verifiedRevision: "git:abc123",
      entities,
      sourcesOfTruth: [],
    });

    assert.deepEqual(checkProjectMap(generated.markdown, generated), {
      current: true,
      expectedDigest: generated.digest,
    });
    const stale = generated.markdown.replace("API service", "Old API service");
    const result = checkProjectMap(stale, generated);
    assert.equal(result.current, false);
    assert.equal(result.expectedDigest, generated.digest);
  });
});
