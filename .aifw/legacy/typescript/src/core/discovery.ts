import { readFile, stat } from "node:fs/promises";
import path from "node:path";

import fg from "fast-glob";
import { parse } from "yaml";

export type ProjectStack = "node" | "dart" | "flutter" | "python";
export type PlatformTarget =
  | "android"
  | "ios"
  | "web"
  | "windows"
  | "macos"
  | "linux";

export interface ProjectDiscovery {
  packageManager: "npm" | "pnpm" | "yarn" | "bun" | "unknown";
  stacks: ProjectStack[];
  platformTargets: PlatformTarget[];
  scripts: Record<string, string>;
  dependencies: string[];
  contracts: string[];
  ciFiles: string[];
  adrFiles: string[];
  moduleManifests: string[];
  entrypoints: string[];
  configurationFiles: string[];
  documentationFiles: string[];
  sourceRoots: string[];
}

interface PackageJson {
  scripts?: Record<string, string>;
  dependencies?: Record<string, string>;
  devDependencies?: Record<string, string>;
  peerDependencies?: Record<string, string>;
}

interface Pubspec {
  dependencies?: Record<string, unknown>;
  dev_dependencies?: Record<string, unknown>;
}

const ignore = ["**/node_modules/**", "**/.git/**", "**/.aifw/**"];

async function files(root: string, patterns: string[]): Promise<string[]> {
  return fg(patterns, {
    cwd: root,
    onlyFiles: true,
    dot: true,
    ignore,
    followSymbolicLinks: false,
  }).then((matches) => matches.map((match) => match.replaceAll("\\", "/")).sort());
}

async function detectPackageManager(root: string): Promise<ProjectDiscovery["packageManager"]> {
  const locks = await files(root, [
    "pnpm-lock.yaml",
    "yarn.lock",
    "package-lock.json",
    "bun.lock",
    "bun.lockb",
  ]);
  if (locks.includes("pnpm-lock.yaml")) return "pnpm";
  if (locks.includes("yarn.lock")) return "yarn";
  if (locks.includes("package-lock.json")) return "npm";
  if (locks.some((lock) => lock.startsWith("bun.lock"))) return "bun";
  return "unknown";
}

async function optionalFile(filePath: string): Promise<string | undefined> {
  try {
    return await readFile(filePath, "utf8");
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return undefined;
    throw error;
  }
}

async function isDirectory(directoryPath: string): Promise<boolean> {
  try {
    return (await stat(directoryPath)).isDirectory();
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return false;
    throw error;
  }
}

function isFlutterSdkDependency(value: unknown): boolean {
  return (
    value !== null &&
    typeof value === "object" &&
    !Array.isArray(value) &&
    (value as { sdk?: unknown }).sdk === "flutter"
  );
}

export async function discoverProject(root: string): Promise<ProjectDiscovery> {
  const packageJsonPath = path.join(root, "package.json");
  const packageJsonSource = await optionalFile(packageJsonPath);
  let packageJson: PackageJson = {};
  if (packageJsonSource !== undefined) {
    packageJson = JSON.parse(packageJsonSource) as PackageJson;
  }

  const pubspecSource = await optionalFile(path.join(root, "pubspec.yaml"));
  const pyprojectSource = await optionalFile(path.join(root, "pyproject.toml"));
  const pubspec = pubspecSource === undefined
    ? undefined
    : (parse(pubspecSource) as Pubspec | null);
  const flutter =
    pubspec !== null &&
    pubspec !== undefined &&
    (isFlutterSdkDependency(pubspec.dependencies?.["flutter"]) ||
      isFlutterSdkDependency(pubspec.dev_dependencies?.["flutter_test"]));
  const stacks: ProjectStack[] = [
    ...(packageJsonSource === undefined ? [] : ["node" as const]),
    ...(pubspecSource === undefined ? [] : ["dart" as const]),
    ...(flutter ? ["flutter" as const] : []),
    ...(pyprojectSource === undefined ? [] : ["python" as const]),
  ];
  const supportedTargets: PlatformTarget[] = [
    "android",
    "ios",
    "web",
    "windows",
    "macos",
    "linux",
  ];
  const targetChecks = await Promise.all(
    supportedTargets.map(async (target) => ({
      target,
      present: flutter && (await isDirectory(path.join(root, target))),
    })),
  );
  const platformTargets = targetChecks
    .filter((check) => check.present)
    .map((check) => check.target);

  const scripts = Object.fromEntries(
    Object.entries(packageJson.scripts ?? {}).sort(([left], [right]) =>
      left.localeCompare(right),
    ),
  );
  const dependencies = [
    ...Object.keys(packageJson.dependencies ?? {}),
    ...Object.keys(packageJson.devDependencies ?? {}),
    ...Object.keys(packageJson.peerDependencies ?? {}),
  ].filter((value, index, all) => all.indexOf(value) === index).sort();

  const [
    packageManager,
    contracts,
    ciFiles,
    adrFiles,
    moduleManifests,
    entrypoints,
    configurationFiles,
    documentationFiles,
  ] = await Promise.all([
    detectPackageManager(root),
    files(root, [
      "**/openapi*.{yaml,yml,json}",
      "**/asyncapi*.{yaml,yml,json}",
      "**/*.graphql",
      "**/*.proto",
    ]),
    files(root, [
      ".github/workflows/*.{yaml,yml}",
      ".gitlab-ci.yml",
      "azure-pipelines.yml",
    ]),
    files(root, [
      "**/adr/**/*.md",
      "**/adrs/**/*.md",
      "**/decisions/ADR-*.md",
      "**/ADR-*.md",
    ]),
    files(root, [
      "package.json",
      "**/package.json",
      "pubspec.yaml",
      "**/pubspec.yaml",
      "pyproject.toml",
      "**/pyproject.toml",
      "go.mod",
      "**/go.mod",
      "Cargo.toml",
      "**/Cargo.toml",
    ]),
    files(root, [
      "src/{index,main,app}.{js,jsx,mjs,cjs,ts,tsx,py}",
      "**/src/{index,main,app}.{js,jsx,mjs,cjs,ts,tsx,py}",
      "{index,main,app,manage}.{js,jsx,mjs,cjs,ts,tsx,py}",
      "lib/main.dart",
      "**/lib/main.dart",
      "cmd/*/main.go",
      "**/cmd/*/main.go",
      "src/main.rs",
      "**/src/main.rs",
      "**/__main__.py",
    ]),
    files(root, [
      "package.json",
      "**/package.json",
      "pubspec.yaml",
      "**/pubspec.yaml",
      "pyproject.toml",
      "**/pyproject.toml",
      "tsconfig*.json",
      "**/tsconfig*.json",
      "analysis_options.yaml",
      "**/analysis_options.yaml",
      "requirements*.txt",
      "**/requirements*.txt",
      "Dockerfile*",
      "**/Dockerfile*",
      "docker-compose*.{yaml,yml}",
      "**/docker-compose*.{yaml,yml}",
      "next.config.*",
      "**/next.config.*",
      "vite.config.*",
      "**/vite.config.*",
    ]),
    files(root, ["README*.md", "**/README*.md", "docs/**/*.md"]),
  ]);

  const sourceRoots = [...new Set(entrypoints.flatMap((entrypoint) => {
    const parts = entrypoint.split("/");
    let rootIndex = -1;
    for (let index = 0; index < parts.length - 1; index += 1) {
      if (["src", "lib", "app"].includes(parts[index] ?? "")) rootIndex = index;
    }
    if (rootIndex < 0) return [];
    return [parts.slice(0, rootIndex + 1).join("/")];
  }))].sort();
  const decisionFiles = adrFiles.filter(
    (file) => path.posix.basename(file).toLocaleLowerCase("en-US") !== "readme.md",
  );

  return {
    packageManager,
    stacks,
    platformTargets,
    scripts,
    dependencies,
    contracts,
    ciFiles,
    adrFiles: decisionFiles,
    moduleManifests,
    entrypoints,
    configurationFiles,
    documentationFiles,
    sourceRoots,
  };
}
