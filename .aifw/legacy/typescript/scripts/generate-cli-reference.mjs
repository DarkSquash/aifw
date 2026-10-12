import { spawnSync } from "node:child_process";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = fileURLToPath(new URL("..", import.meta.url));
const cliPath = path.join(root, "src", "cli.ts");
const outputPath = path.join(root, "docs", "cli-reference.generated.md");

function help(args) {
  const result = spawnSync(process.execPath, [cliPath, ...args, "--help"], {
    cwd: root,
    encoding: "utf8",
    env: { ...process.env, NO_COLOR: "1" },
  });
  if (result.status !== 0) {
    throw new Error(result.stderr || result.stdout || `Help failed for: ${args.join(" ")}`);
  }
  return result.stdout.replaceAll("\r\n", "\n").trimEnd();
}

function childCommands(helpOutput) {
  const lines = helpOutput.split("\n");
  const commandsAt = lines.findIndex((line) => line.trim() === "Commands:");
  if (commandsAt < 0) return [];
  return lines
    .slice(commandsAt + 1)
    .map((line) => /^  ([a-z][a-z0-9-]*)(?:\s|$)/u.exec(line)?.[1])
    .filter((command) => command !== undefined && command !== "help");
}

function leafCommands(parents = []) {
  const output = help(parents);
  const children = childCommands(output);
  if (children.length === 0) return parents.length === 0 ? [] : [{ args: parents, output }];
  return children.flatMap((child) => leafCommands([...parents, child]));
}

function renderReference() {
  const rootHelp = help([]);
  const commands = leafCommands();
  const sections = commands.map(
    ({ args, output }) =>
      `## \`aifw ${args.join(" ")}\`\n\n\`\`\`text\n${output}\n\`\`\``,
  );
  return `# Referência gerada da CLI do AIFW

> Arquivo gerado por \`npm run docs:generate\`. Não edite manualmente. O guia com explicações e fluxos está em [HOW_TO_USE.md](../HOW_TO_USE.md).

Esta referência contém ${commands.length} comandos finais e suas opções, extraídos da implementação atual.

## \`aifw --help\`

\`\`\`text
${rootHelp}
\`\`\`

${sections.join("\n\n")}
`;
}

const expected = renderReference();
if (process.argv.includes("--check")) {
  let current = "";
  try {
    current = await readFile(outputPath, "utf8");
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
  if (current.replaceAll("\r\n", "\n") !== expected) {
    process.stderr.write(
      "CLI reference is stale. Run `npm run docs:generate` and commit the result.\n",
    );
    process.exitCode = 2;
  }
} else {
  await mkdir(path.dirname(outputPath), { recursive: true });
  await writeFile(outputPath, expected, "utf8");
  process.stdout.write("Updated docs/cli-reference.generated.md\n");
}
