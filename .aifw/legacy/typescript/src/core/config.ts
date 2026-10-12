import { Ajv, type ErrorObject, type JSONSchemaType } from "ajv";
import { parseDocument } from "yaml";

import { AifwError } from "./errors.ts";

export type PrimaryEnvironment = "windows" | "wsl" | "linux";
export type ValidationTarget = PrimaryEnvironment | "linux-ci";
export type ProjectType = "new" | "existing";
export type DataClassification =
  | "public"
  | "internal"
  | "confidential"
  | "restricted";

export interface ProjectManifest {
  apiVersion: "aifw.dev/v1alpha1";
  kind: "Project";
  metadata: {
    id: string;
    name: string;
  };
  spec: {
    frameworkVersion: string;
    projectType: ProjectType;
    locale: string;
    primaryEnvironment: PrimaryEnvironment;
    validationTargets: ValidationTarget[];
    profiles: string[];
    dataClassification: DataClassification;
    externalAllowlist: string[];
  };
}

const projectManifestSchema: JSONSchemaType<ProjectManifest> = {
  type: "object",
  additionalProperties: false,
  required: ["apiVersion", "kind", "metadata", "spec"],
  properties: {
    apiVersion: { type: "string", const: "aifw.dev/v1alpha1" },
    kind: { type: "string", const: "Project" },
    metadata: {
      type: "object",
      additionalProperties: false,
      required: ["id", "name"],
      properties: {
        id: { type: "string", pattern: "^[a-z][a-z0-9-]{1,62}$" },
        name: { type: "string", minLength: 1, maxLength: 120 },
      },
    },
    spec: {
      type: "object",
      additionalProperties: false,
      required: [
        "frameworkVersion",
        "projectType",
        "locale",
        "primaryEnvironment",
        "validationTargets",
        "profiles",
        "dataClassification",
        "externalAllowlist",
      ],
      properties: {
        frameworkVersion: {
          type: "string",
          pattern: "^(0|[1-9]\\d*)\\.(0|[1-9]\\d*)\\.(0|[1-9]\\d*)(?:-[0-9A-Za-z.-]+)?$",
        },
        projectType: { type: "string", enum: ["new", "existing"] },
        locale: { type: "string", minLength: 2, maxLength: 35 },
        primaryEnvironment: {
          type: "string",
          enum: ["windows", "wsl", "linux"],
        },
        validationTargets: {
          type: "array",
          minItems: 1,
          uniqueItems: true,
          items: {
            type: "string",
            enum: ["windows", "wsl", "linux", "linux-ci"],
          },
        },
        profiles: {
          type: "array",
          uniqueItems: true,
          items: { type: "string", minLength: 1 },
        },
        dataClassification: {
          type: "string",
          enum: ["public", "internal", "confidential", "restricted"],
        },
        externalAllowlist: {
          type: "array",
          uniqueItems: true,
          items: { type: "string", minLength: 1 },
        },
      },
    },
  },
};

const ajv = new Ajv({ allErrors: true, strict: true });
const validateManifest = ajv.compile(projectManifestSchema);

function formatValidationError(error: ErrorObject): string {
  const path = error.instancePath || "/";
  const missing =
    error.keyword === "required" &&
    typeof error.params["missingProperty"] === "string"
      ? `/${error.params["missingProperty"]}`
      : "";
  return `${path}${missing} ${error.message ?? "is invalid"}`;
}

export function parseProjectManifest(input: string): ProjectManifest {
  let value: unknown;

  try {
    const document = parseDocument(input, {
      schema: "core",
      strict: true,
      uniqueKeys: true,
    });
    if (document.errors.length > 0) {
      throw new Error(document.errors.map((error) => error.message).join("; "));
    }
    value = document.toJS();
  } catch (error) {
    throw new AifwError(
      "YAML_INVALID",
      `Invalid YAML: ${error instanceof Error ? error.message : String(error)}`,
    );
  }

  if (!validateManifest(value)) {
    const details = (validateManifest.errors ?? []).map(formatValidationError);
    throw new AifwError(
      "MANIFEST_INVALID",
      `Project manifest is invalid: ${details.join("; ")}`,
      details,
    );
  }

  return structuredClone(value);
}

export { projectManifestSchema };
