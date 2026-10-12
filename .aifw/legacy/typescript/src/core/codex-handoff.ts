import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

import type { ChangeLevel, CognitiveRoute } from "./change.ts";
import { AifwError } from "./errors.ts";

export interface CodexHandoffAttempt {
  hypothesis: string;
  intervention: string;
  result: string;
  evidence?: string[];
}

export interface CodexHandoffInput {
  project: { id: string; name: string };
  objective: string;
  reason: string;
  impact: ChangeLevel;
  suggestedRoute: CognitiveRoute;
  blocker: {
    summary: string;
    exactError?: string;
    suspectedCause?: string;
  };
  attempts: CodexHandoffAttempt[];
  relevantFiles: string[];
  authoritativeArtifacts: string[];
  constraints: string[];
  verification: string[];
  requestedOutcome: string;
  generatedAt?: string;
}

export interface WrittenCodexHandoff {
  absolutePath: string;
  relativePath: string;
  document: string;
}

const SECRET_PATTERNS: ReadonlyArray<RegExp> = [
  /\bsk-[A-Za-z0-9_-]{8,}\b/gu,
  /\bBearer\s+[A-Za-z0-9._~+/-]+=*\b/giu,
  /\b(api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*[^\s,;]+/giu,
];

function redact(value: string): string {
  return SECRET_PATTERNS.reduce(
    (current, pattern) => current.replace(pattern, "[REDACTED]"),
    value,
  );
}

function bulletList(values: readonly string[], empty: string): string {
  return values.length === 0
    ? `- ${empty}`
    : values.map((value) => `- ${redact(value)}`).join("\n");
}

function attemptsSection(attempts: readonly CodexHandoffAttempt[]): string {
  if (attempts.length === 0) return "No distinct attempt was recorded.";
  return attempts
    .map((attempt, index) => {
      const evidence = bulletList(attempt.evidence ?? [], "No evidence reference recorded.");
      return [
        `### Attempt ${String(index + 1)}`,
        "",
        `- Hypothesis: ${redact(attempt.hypothesis)}`,
        `- Intervention: ${redact(attempt.intervention)}`,
        `- Result: ${redact(attempt.result)}`,
        "- Evidence:",
        evidence
          .split("\n")
          .map((line) => `  ${line}`)
          .join("\n"),
      ].join("\n");
    })
    .join("\n\n");
}

export function buildCodexHandoff(input: CodexHandoffInput): string {
  const generatedAt = input.generatedAt ?? new Date().toISOString();
  const exactError = input.blocker.exactError?.trim();
  const suspectedCause = input.blocker.suspectedCause?.trim();
  return [
    "# AIFW Codex Handoff",
    "",
    `Generated: ${generatedAt}`,
    `Project: ${redact(input.project.name)} (${redact(input.project.id)})`,
    `Impact: ${input.impact}`,
    `Required cognitive route: ${input.suggestedRoute}`,
    "Transfer mode: manual; this document does not authorize external actions.",
    "",
    "## Objective",
    "",
    redact(input.objective),
    "",
    "## Why Pi escalated",
    "",
    redact(input.reason),
    "",
    "## Exact blocker",
    "",
    redact(input.blocker.summary),
    "",
    `Suspected cause: ${suspectedCause ? redact(suspectedCause) : "Not established."}`,
    "",
    "### Verbatim error",
    "",
    "```text",
    exactError ? redact(exactError) : "No exact error was captured.",
    "```",
    "",
    "## Distinct attempts",
    "",
    attemptsSection(input.attempts),
    "",
    "## Relevant files",
    "",
    bulletList(input.relevantFiles, "No file reference recorded."),
    "",
    "## Sources of truth",
    "",
    bulletList(input.authoritativeArtifacts, "No authoritative artifact recorded."),
    "",
    "## Constraints and non-goals",
    "",
    bulletList(input.constraints, "No additional constraint recorded."),
    "",
    "## Requested Codex outcome",
    "",
    redact(input.requestedOutcome),
    "",
    "## Definition of done",
    "",
    bulletList(input.verification, "Define and run risk-proportional verification."),
    "",
    "## Required return handoff",
    "",
    "Return diagnosis, files changed, decisions/ADRs affected, exact verification commands and results, remaining risks, and anything Pi must continue. Never claim completion without fresh evidence.",
    "",
  ].join("\n");
}

function defaultRelativePath(generatedAt: string): string {
  const timestamp = generatedAt.replaceAll(":", "-").replaceAll(".", "-");
  return `.aifw/handoffs/codex-${timestamp}.md`;
}

export async function writeCodexHandoff(
  root: string,
  input: CodexHandoffInput,
  outputPath?: string,
): Promise<WrittenCodexHandoff> {
  const resolvedRoot = path.resolve(root);
  const relativePath = (outputPath ?? defaultRelativePath(input.generatedAt ?? new Date().toISOString()))
    .replaceAll("\\", "/");
  const absolutePath = path.resolve(resolvedRoot, relativePath);
  const insideRoot =
    absolutePath === resolvedRoot || absolutePath.startsWith(`${resolvedRoot}${path.sep}`);
  if (!insideRoot) {
    throw new AifwError(
      "PERMISSION_DENIED",
      "Codex handoff output must stay inside the project root.",
      [relativePath],
    );
  }

  const document = buildCodexHandoff(input);
  await mkdir(path.dirname(absolutePath), { recursive: true });
  await writeFile(absolutePath, document, { encoding: "utf8", flag: "wx" });
  return {
    absolutePath,
    relativePath: path.relative(resolvedRoot, absolutePath).replaceAll("\\", "/"),
    document,
  };
}
