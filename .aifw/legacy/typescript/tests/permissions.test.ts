import assert from "node:assert/strict";
import { describe, it } from "node:test";

type PermissionsModule = typeof import("../src/core/permissions.ts");

async function loadPermissions(): Promise<PermissionsModule> {
  try {
    return await import("../src/core/permissions.ts");
  } catch (error) {
    assert.fail(`permissions module must be implemented: ${String(error)}`);
  }
}

describe("capability and side-effect policy", () => {
  it("allows local git work but requires approval for remote mutation", async () => {
    const { authorizeAction, defaultPermissionPolicy } = await loadPermissions();

    assert.equal(
      authorizeAction(
        { kind: "git-local", operation: "commit" },
        defaultPermissionPolicy,
      ).decision,
      "allow",
    );
    assert.equal(
      authorizeAction(
        { kind: "git-remote", operation: "push" },
        defaultPermissionPolicy,
      ).decision,
      "require-approval",
    );
  });

  it("allows previews but requires approval for production deployment", async () => {
    const { authorizeAction, defaultPermissionPolicy } = await loadPermissions();

    assert.equal(
      authorizeAction(
        { kind: "deploy", environment: "preview" },
        defaultPermissionPolicy,
      ).decision,
      "allow",
    );
    assert.equal(
      authorizeAction(
        { kind: "deploy", environment: "production" },
        defaultPermissionPolicy,
      ).decision,
      "require-approval",
    );
  });

  it("denies an external service outside the project's allowlist", async () => {
    const { authorizeAction, defaultPermissionPolicy } = await loadPermissions();

    const result = authorizeAction(
      { kind: "external-read", service: "unknown-scraper" },
      { ...defaultPermissionPolicy, externalAllowlist: ["context7"] },
    );

    assert.equal(result.decision, "deny");
    assert.equal(result.reason, "service-not-allowlisted");
  });

  it("prevents a child agent from exceeding its parent's capability ceiling", async () => {
    const { validateDelegation } = await loadPermissions();

    const result = validateDelegation(
      ["filesystem:read", "test:run"],
      ["filesystem:read", "git:push"],
    );

    assert.equal(result.valid, false);
    assert.deepEqual(result.excessCapabilities, ["git:push"]);
  });

  it("accepts break-glass only when it is scoped, approved and unexpired", async () => {
    const { validateBreakGlass } = await loadPermissions();

    const result = validateBreakGlass(
      {
        incidentId: "INC-42",
        scope: ["production:rollback"],
        approvedBy: "human:owner",
        approvedAt: "2026-08-22T10:00:00.000Z",
        expiresAt: "2026-08-22T10:15:00.000Z",
        reason: "Stop an active data-corruption incident",
      },
      "production:rollback",
      new Date("2026-08-22T10:05:00.000Z"),
    );

    assert.equal(result.valid, true);
    assert.equal(
      validateBreakGlass(
        {
          incidentId: "INC-42",
          scope: ["production:rollback"],
          approvedBy: "human:owner",
          approvedAt: "2026-08-22T10:00:00.000Z",
          expiresAt: "2026-08-22T10:15:00.000Z",
          reason: "Stop an active data-corruption incident",
        },
        "production:delete-database",
        new Date("2026-08-22T10:05:00.000Z"),
      ).valid,
      false,
    );
    assert.equal(
      validateBreakGlass(
        {
          incidentId: "INC-42",
          scope: ["production:rollback"],
          approvedBy: "agent:orchestrator",
          approvedAt: "2026-08-22T10:00:00.000Z",
          expiresAt: "2026-08-22T10:15:00.000Z",
          reason: "Stop an active data-corruption incident",
        },
        "production:rollback",
        new Date("2026-08-22T10:05:00.000Z"),
      ).valid,
      false,
    );
  });
});
