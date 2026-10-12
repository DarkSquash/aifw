export type AifwErrorCode =
  | "YAML_INVALID"
  | "MANIFEST_INVALID"
  | "PROFILE_CONFLICT"
  | "POLICY_CONFLICT"
  | "NOT_READY"
  | "APPROVAL_REQUIRED"
  | "PERMISSION_DENIED"
  | "IMPASSE_OPEN"
  | "COMMAND_FAILED";

export class AifwError extends Error {
  readonly code: AifwErrorCode;
  readonly details: readonly string[];

  constructor(
    code: AifwErrorCode,
    message: string,
    details: readonly string[] = [],
  ) {
    super(message);
    this.name = "AifwError";
    this.code = code;
    this.details = details;
  }
}
