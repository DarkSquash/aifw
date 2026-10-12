import { createHash } from "node:crypto";

import { AifwError } from "./errors.ts";

export type CatalogKind =
  | "System"
  | "Component"
  | "API"
  | "Resource"
  | "DataStore"
  | "Runtime"
  | "ExternalDependency"
  | "Contract"
  | "Decision"
  | "Runbook";

export interface CatalogRelation {
  type:
    | "partOf"
    | "dependsOn"
    | "consumes"
    | "provides"
    | "providedBy"
    | "storesIn"
    | "runsOn"
    | "documentedBy";
  target: string;
}

export interface CatalogEntity {
  id: string;
  kind: CatalogKind;
  name: string;
  description: string;
  owner: string;
  source: string;
  visibility: "public" | "restricted" | "internal" | "private";
  origin?: "manual" | "discovered";
  confidence?: "candidate" | "confirmed";
  lastVerifiedAt?: string;
  relations: CatalogRelation[];
}

export interface ProjectMapInput {
  project: { id: string; name: string };
  purpose: string;
  frameworkVersion: string;
  verifiedRevision: string;
  entities: CatalogEntity[];
  sourcesOfTruth: Array<{ topic: string; source: string }>;
}

export interface GeneratedProjectMap {
  markdown: string;
  digest: string;
  entities: CatalogEntity[];
}

function hash(value: string): string {
  return createHash("sha256").update(value).digest("hex");
}

function cell(value: string): string {
  return value.replaceAll("|", "\\|").replaceAll("\n", " ").trim();
}

function validateUniqueEntities(entities: readonly CatalogEntity[]): void {
  const ids = new Set<string>();
  for (const entity of entities) {
    if (ids.has(entity.id)) {
      throw new AifwError(
        "MANIFEST_INVALID",
        `Duplicate catalog entity id: ${entity.id}`,
        [entity.id],
      );
    }
    ids.add(entity.id);
  }
}

export function buildProjectMap(input: ProjectMapInput): GeneratedProjectMap {
  validateUniqueEntities(input.entities);
  const entities = structuredClone(input.entities).sort(
    (left, right) =>
      left.kind.localeCompare(right.kind) || left.id.localeCompare(right.id),
  );
  const sources = [...input.sourcesOfTruth].sort((left, right) =>
    left.topic.localeCompare(right.topic),
  );

  const lines = [
    `# PROJECT_MAP — ${input.project.name}`,
    "",
    "> Compiled entrypoint. Edit authoritative sources, then regenerate this file.",
    "",
    "## Project",
    "",
    "| Field | Value |",
    "| --- | --- |",
    `| Project ID | ${cell(input.project.id)} |`,
    `| Framework | ${cell(input.frameworkVersion)} |`,
    `| Verified revision | ${cell(input.verifiedRevision)} |`,
    "",
    "## Purpose",
    "",
    input.purpose.trim(),
    "",
    "## Sources of truth",
    "",
    "| Topic | Source |",
    "| --- | --- |",
    ...sources.map(
      (source) => `| ${cell(source.topic)} | ${cell(source.source)} |`,
    ),
    "",
    "## Catalog",
    "",
    "| ID | Kind | Name | Owner | Visibility | Origin | Confidence | Verified | Source | Description |",
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ...entities.map(
      (entity) =>
        `| ${cell(entity.id)} | ${entity.kind} | ${cell(entity.name)} | ${cell(entity.owner)} | ${entity.visibility} | ${entity.origin ?? "manual"} | ${entity.confidence ?? "confirmed"} | ${cell(entity.lastVerifiedAt ?? "not-recorded")} | ${cell(entity.source)} | ${cell(entity.description)} |`,
    ),
    "",
    "## Relationships",
    "",
    "| Source | Relation | Target |",
    "| --- | --- | --- |",
    ...entities.flatMap((entity) =>
      [...entity.relations]
        .sort(
          (left, right) =>
            left.type.localeCompare(right.type) ||
            left.target.localeCompare(right.target),
        )
        .map(
          (relation) =>
            `| ${cell(entity.id)} | ${relation.type} | ${cell(relation.target)} |`,
        ),
    ),
    "",
  ];

  const body = lines.join("\n");
  const digest = hash(body);
  const markdown = `<!-- aifw:project-map digest=${digest} -->\n${body}`;
  return { markdown, digest, entities };
}

export function checkProjectMap(
  currentMarkdown: string,
  expected: GeneratedProjectMap,
): { current: boolean; expectedDigest: string } {
  const normalize = (value: string) => value.replaceAll("\r\n", "\n").trimEnd();
  return {
    current: normalize(currentMarkdown) === normalize(expected.markdown),
    expectedDigest: expected.digest,
  };
}
