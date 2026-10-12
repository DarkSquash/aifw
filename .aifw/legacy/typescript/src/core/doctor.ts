import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

export interface CommandResult {
  ok: boolean;
  stdout: string;
  stderr: string;
}

export type CommandRunner = (
  command: string,
  args: readonly string[],
) => Promise<CommandResult>;

export interface DoctorOptions {
  platform: NodeJS.Platform;
  run: CommandRunner;
}

export interface RuntimeCheck {
  status: "pass" | "fail";
  version?: string;
  detail?: string;
}

export interface DoctorReport {
  healthy: boolean;
  primaryEnvironment: "windows" | "linux" | "macos" | "other";
  checks: {
    node: RuntimeCheck;
    git: RuntimeCheck;
  };
  wsl: {
    applicable: boolean;
    available: boolean;
    nodeAvailable: boolean;
    reason?: "access-denied" | "not-installed" | "node-missing";
  };
  guidance: string[];
}

function environmentName(
  platform: NodeJS.Platform,
): DoctorReport["primaryEnvironment"] {
  if (platform === "win32") return "windows";
  if (platform === "linux") return "linux";
  if (platform === "darwin") return "macos";
  return "other";
}

function runtimeCheck(result: CommandResult): RuntimeCheck {
  if (result.ok) return { status: "pass", version: result.stdout.trim() };
  return { status: "fail", detail: (result.stderr || result.stdout).trim() };
}

export async function systemCommandRunner(
  command: string,
  args: readonly string[],
): Promise<CommandResult> {
  try {
    const result = await execFileAsync(command, [...args], {
      windowsHide: true,
      timeout: 15_000,
    });
    return {
      ok: true,
      stdout: result.stdout,
      stderr: result.stderr,
    };
  } catch (error) {
    const failure = error as {
      stdout?: string;
      stderr?: string;
      message?: string;
    };
    const stderr =
      failure.stderr?.trim() || failure.message?.trim() || String(error);
    return {
      ok: false,
      stdout: failure.stdout ?? "",
      stderr,
    };
  }
}

export async function runDoctor(options: DoctorOptions): Promise<DoctorReport> {
  const [nodeResult, gitResult] = await Promise.all([
    options.run("node", ["--version"]),
    options.run("git", ["--version"]),
  ]);
  const checks = {
    node: runtimeCheck(nodeResult),
    git: runtimeCheck(gitResult),
  };

  const wsl: DoctorReport["wsl"] = {
    applicable: options.platform === "win32",
    available: false,
    nodeAvailable: false,
  };
  const guidance: string[] = [];

  if (options.platform === "win32") {
    const status = await options.run("wsl.exe", ["--status"]);
    if (status.ok) {
      wsl.available = true;
      const wslNode = await options.run("wsl.exe", ["--exec", "node", "--version"]);
      wsl.nodeAvailable = wslNode.ok;
      if (!wslNode.ok) wsl.reason = "node-missing";
      guidance.push(
        "Keep Windows and WSL node_modules and package-manager caches separate; reinstall dependencies inside each environment.",
      );
    } else if (/E_ACCESSDENIED|access.+denied/iu.test(status.stderr)) {
      wsl.reason = "access-denied";
    } else {
      wsl.reason = "not-installed";
    }
  }

  return {
    healthy: checks.node.status === "pass" && checks.git.status === "pass",
    primaryEnvironment: environmentName(options.platform),
    checks,
    wsl,
    guidance,
  };
}

export function runSystemDoctor(): Promise<DoctorReport> {
  return runDoctor({ platform: process.platform, run: systemCommandRunner });
}
