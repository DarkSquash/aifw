import { spawnSync } from "node:child_process";
import { mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
const root = await mkdtemp(path.join(tmpdir(), "aifw-parity-"));
const cli = path.resolve("src/cli.ts");
function run(args) {
  const result = spawnSync(process.execPath, [cli, ...args, "--json"], {cwd:root,encoding:"utf8"});
  if (![0,2].includes(result.status)) throw new Error(result.stderr);
  return { code: result.status, output: JSON.parse(result.stdout) };
}
run(["init", "--id", "sample", "--name", "Sample", "--primary", "windows", "--targets", "windows"]);
const commands = [["intake","status"],["decision","list"],["decision","recommend","--category","application-architecture","--signals","domain:complex,integrations:many"],["principle","list"],["principle","review","--signals","domain:complex,implementation"],["route","status"],["route","eval"],["eval"],["spec","list"],["resolve","build"],["resolve","check"],["map","check"],["validate","--level","L0"]];
await writeFile("tests_python/fixtures/cli-parity.json", JSON.stringify(commands.map(args=>({args,...run(args)})),null,2)+"\n");
