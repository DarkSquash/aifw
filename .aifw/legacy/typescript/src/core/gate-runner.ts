import { execFile } from "node:child_process";
import { access, readFile } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";

import { parseDocument } from "yaml";

import type { ChangeLevel } from "./change.ts";
import { AifwError } from "./errors.ts";
import {
  evaluateQualityGates,
  type GateEvaluation,
  type GateResult,
} from "./gates.ts";
import { buildWorkspaceMap, loadWorkspaceManifest } from "./workspace.ts";

const execFileAsync = promisify(execFile);

export interface GateDefinition {
  id: string;
  enforcement: "hard" | "audit" | "human";
  levels: ChangeLevel[];
  command?: string[];
  workingDirectory?: string;
}

export interface QualityGateSet {
  apiVersion: "aifw.dev/v1alpha1";
  kind: "QualityGateSet";
  philosophy: "progressive-by-risk";
  gates: GateDefinition[];
}

export interface GateCommandResult {
  ok: boolean;
  stdout: string;
  stderr: string;
}

export type GateCommandRunner = (
  executable: string,
  args: readonly string[],
  cwd: string,
) => Promise<GateCommandResult>;

export interface RunGateSetOptions {
  root: string;
  run: GateCommandRunner;
  builtIns: Map<string, GateResult>;
}

function strings(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isLevel(value: string): value is ChangeLevel {
  return value === "L0" || value === "L1" || value === "L2" || value === "L3";
}

export function parseGateSet(source: string, label: string): QualityGateSet {
  const document = parseDocument(source, {
    schema: "core",
    strict: true,
    uniqueKeys: true,
  });
  if (document.errors.length > 0) {
    throw new AifwError(
      "YAML_INVALID",
      `${label} is invalid: ${document.errors.map((error) => error.message).join("; ")}`,
    );
  }
  const value = document.toJS() as Partial<QualityGateSet> | null;
  if (
    value === null ||
    value.apiVersion !== "aifw.dev/v1alpha1" ||
    value.kind !== "QualityGateSet" ||
    value.philosophy !== "progressive-by-risk" ||
    !Array.isArray(value.gates)
  ) {
    throw new AifwError("MANIFEST_INVALID", `${label} is not a QualityGateSet.`);
  }

  const ids = new Set<string>();
  for (const gate of value.gates) {
    const valid =
      typeof gate?.id === "string" &&
      ["hard", "audit", "human"].includes(gate.enforcement) &&
      strings(gate.levels) &&
      gate.levels.every(isLevel) &&
      (gate.command === undefined || (strings(gate.command) && gate.command.length > 0)) &&
      (gate.workingDirectory === undefined || typeof gate.workingDirectory === "string");
    if (!valid) {
      throw new AifwError(
        "MANIFEST_INVALID",
        `${label} contains an invalid gate definition.`,
      );
    }
    if (ids.has(gate.id)) {
      throw new AifwError("POLICY_CONFLICT", `${label} repeats gate ${gate.id}.`);
    }
    ids.add(gate.id);
  }

  return structuredClone(value) as QualityGateSet;
}

function resolveWorkingDirectory(root: string, relative = "."): string {
  const resolvedRoot = path.resolve(root);
  const resolved = path.resolve(resolvedRoot, relative);
  const relativeToRoot = path.relative(resolvedRoot, resolved);
  if (relativeToRoot.startsWith("..") || path.isAbsolute(relativeToRoot)) {
    throw new AifwError(
      "POLICY_CONFLICT",
      `Gate working directory escapes the project root: ${relative}`,
    );
  }
  return resolved;
}

function commandEvidence(result: GateCommandResult): string[] {
  const evidence: string[] = [];
  if (result.stdout.trim().length > 0) {
    evidence.push(`stdout:${result.stdout.trim().slice(0, 2_000)}`);
  }
  if (result.stderr.trim().length > 0) {
    evidence.push(`stderr:${result.stderr.trim().slice(0, 2_000)}`);
  }
  return evidence;
}

async function resolveWindowsExecutable(executable: string): Promise<string> {
  if (path.extname(executable).length > 0 || executable.includes("/") || executable.includes("\\")) {
    return executable;
  }
  const extensions = (process.env["PATHEXT"] ?? ".COM;.EXE;.BAT;.CMD")
    .split(";")
    .map((extension) => extension.trim().toLowerCase())
    .filter((extension) => extension.length > 0);
  for (const directory of (process.env["PATH"] ?? "").split(path.delimiter)) {
    const normalizedDirectory = directory.trim().replace(/^"|"$/gu, "");
    if (normalizedDirectory.length === 0) continue;
    for (const extension of extensions) {
      const candidate = path.join(normalizedDirectory, `${executable}${extension}`);
      try {
        await access(candidate);
        return candidate;
      } catch (error) {
        if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
      }
    }
  }
  return executable;
}

export async function runGateSet(
  gateSet: QualityGateSet,
  level: ChangeLevel,
  options: RunGateSetOptions,
): Promise<GateResult[]> {
  const selected = gateSet.gates
    .filter((gate) => gate.levels.includes(level))
    .sort((left, right) => left.id.localeCompare(right.id));
  const results: GateResult[] = [];

  for (const gate of selected) {
    const builtIn = options.builtIns.get(gate.id);
    if (builtIn !== undefined) {
      results.push({ ...structuredClone(builtIn), enforcement: gate.enforcement });
      continue;
    }
    if (gate.command === undefined) {
      results.push({
        gateId: gate.id,
        enforcement: gate.enforcement,
        status: "not-run",
        summary: "No command or built-in evidence source is configured.",
        evidence: [],
      });
      continue;
    }

    const [executable, ...args] = gate.command;
    if (executable === undefined) {
      throw new AifwError("MANIFEST_INVALID", `Gate ${gate.id} has an empty command.`);
    }
    const commandResult = await options.run(
      executable,
      args,
      resolveWorkingDirectory(options.root, gate.workingDirectory),
    );
    results.push({
      gateId: gate.id,
      enforcement: gate.enforcement,
      status: commandResult.ok
        ? "pass"
        : gate.enforcement === "audit"
          ? "warning"
          : "fail",
      summary: commandResult.ok ? "Command passed." : "Command failed.",
      evidence: commandEvidence(commandResult),
    });
  }

  return results;
}

export async function systemGateRunner(
  executable: string,
  args: readonly string[],
  cwd: string,
): Promise<GateCommandResult> {
  let resolvedExecutable = executable;
  let resolvedArgs = [...args];
  let windowsVerbatimArguments = false;

  if (process.platform === "win32" && (executable === "npm" || executable === "npx")) {
    const cliName = executable === "npm" ? "npm-cli.js" : "npx-cli.js";
    const candidates = [
      ...(executable === "npm" && process.env["npm_execpath"]
        ? [process.env["npm_execpath"]]
        : []),
      path.join(path.dirname(process.execPath), "node_modules", "npm", "bin", cliName),
    ];
    for (const candidate of candidates) {
      try {
        await access(candidate);
        resolvedExecutable = process.execPath;
        resolvedArgs = [candidate, ...args];
        break;
      } catch (error) {
        if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
      }
    }
  }

  if (process.platform === "win32") {
    resolvedExecutable = await resolveWindowsExecutable(resolvedExecutable);
  }

  if (
    process.platform === "win32" &&
    (resolvedExecutable.toLowerCase().endsWith(".cmd") ||
      resolvedExecutable.toLowerCase().endsWith(".bat"))
  ) {
    const invalidToken = [resolvedExecutable, ...resolvedArgs].find((token) =>
      /["\r\n\0]/u.test(token),
    );
    if (invalidToken !== undefined) {
      return {
        ok: false,
        stdout: "",
        stderr: "Windows batch gate commands cannot contain quotes, newlines or NUL bytes.",
      };
    }
    const commandLine = [resolvedExecutable, ...resolvedArgs]
      .map((token) => `"${token}"`)
      .join(" ");
    resolvedExecutable = process.env["ComSpec"] ?? "cmd.exe";
    resolvedArgs = ["/d", "/s", "/v:off", "/c", `call ${commandLine}`];
    windowsVerbatimArguments = true;
  }

  try {
    const result = await execFileAsync(resolvedExecutable, resolvedArgs, {
      cwd,
      windowsHide: true,
      windowsVerbatimArguments,
      timeout: 10 * 60_000,
      maxBuffer: 10 * 1024 * 1024,
    });
    return { ok: true, stdout: result.stdout, stderr: result.stderr };
  } catch (error) {
    const failure = error as { stdout?: string; stderr?: string; message?: string };
    const stderr =
      failure.stderr?.trim() || failure.message?.trim() || String(error);
    return {
      ok: false,
      stdout: failure.stdout ?? "",
      stderr,
    };
  }
}

export async function validateWorkspace(
  root: string,
  level: ChangeLevel,
  options: {
    run?: GateCommandRunner;
    approval?: { approvedBy: string; approvalDigest: string };
  } = {},
): Promise<GateEvaluation> {
  const [manifest, projectMap, gateSource] = await Promise.all([
    loadWorkspaceManifest(root),
    buildWorkspaceMap(root, { write: false }),
    readFile(path.join(root, ".aifw", "gates.yaml"), "utf8"),
  ]);
  const gateSet = parseGateSet(gateSource, ".aifw/gates.yaml");
  const builtIns = new Map<string, GateResult>([
    [
      "manifest",
      {
        gateId: "manifest",
        enforcement: "hard",
        status: "pass",
        summary: `Manifest ${manifest.metadata.id} is valid and pinned.`,
        evidence: ["aifw.yaml"],
      },
    ],
    [
      "project-map",
      {
        gateId: "project-map",
        enforcement: "hard",
        status: projectMap.current ? "pass" : "fail",
        summary: projectMap.current ? "PROJECT_MAP is current." : "PROJECT_MAP is stale.",
        evidence: ["PROJECT_MAP.md", `sha256:${projectMap.digest}`],
      },
    ],
  ]);
  if (options.approval !== undefined) {
    builtIns.set("human-approval", {
      gateId: "human-approval",
      enforcement: "human",
      status: "pass",
      summary: `Approved by ${options.approval.approvedBy}.`,
      evidence: [options.approval.approvalDigest],
    });
  }
  const results = await runGateSet(gateSet, level, {
    root,
    run: options.run ?? systemGateRunner,
    builtIns,
  });
  const requiredGateIds = gateSet.gates
    .filter((gate) => gate.levels.includes(level))
    .map((gate) => gate.id);

  return evaluateQualityGates({
    change: {
      level,
      humanApproval: level === "L3" ? "required" : level === "L2" ? "conditional" : "none",
    },
    requiredGateIds,
    results,
    ...(options.approval === undefined ? {} : { approval: options.approval }),
  });
}
