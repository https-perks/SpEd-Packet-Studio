import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";

const isWindows = process.platform === "win32";
const venvPython = join(process.cwd(), ".venv", isWindows ? "Scripts/python.exe" : "bin/python");
const python = process.env.PYTHON ?? (existsSync(venvPython) ? venvPython : "python");
const pnpmEntry = process.env.npm_execpath;
const children = new Set();

function start(command, args, options = {}) {
  const child = spawn(command, args, {
    cwd: process.cwd(),
    env: process.env,
    stdio: "inherit",
    ...options,
  });
  children.add(child);
  child.once("exit", () => children.delete(child));
  return child;
}
function shutdown(code = 0) {
  for (const child of children) if (!child.killed) child.kill();
  process.exit(code);
}
const backend = start(python, ["-m", "backend"], {
  env: { ...process.env, PACKET_STUDIO_ENV: "desktop-development" },
});
backend.once("exit", (code) => { if (code) shutdown(code); });
const desktop = pnpmEntry
  ? start(process.execPath, [pnpmEntry, "tauri", "dev"])
  : start(isWindows ? "pnpm.cmd" : "pnpm", ["tauri", "dev"], { shell: isWindows });
desktop.once("exit", (code) => shutdown(code ?? 0));
process.once("SIGINT", () => shutdown(0));
process.once("SIGTERM", () => shutdown(0));
