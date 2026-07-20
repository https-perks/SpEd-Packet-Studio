import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { join } from "node:path";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const isWindows = process.platform === "win32";
const projectRoot = dirname(dirname(fileURLToPath(import.meta.url)));
const venvPython = join(projectRoot, ".venv", isWindows ? "Scripts/python.exe" : "bin/python");
const python = process.env.PYTHON ?? (existsSync(venvPython) ? venvPython : "python");
const pnpmEntry = process.env.npm_execpath;
const children = new Set();
let shuttingDown = false;

function start(command, args, options = {}) {
  const child = spawn(command, args, {
    cwd: projectRoot,
    env: process.env,
    stdio: "inherit",
    ...options,
  });
  children.add(child);
  child.once("exit", () => children.delete(child));
  return child;
}
function shutdown(code = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const child of children) {
    if (child.killed || child.exitCode !== null) continue;
    if (isWindows) {
      spawnSync("taskkill", ["/pid", String(child.pid), "/t", "/f"], { stdio: "ignore" });
    } else {
      child.kill();
    }
  }
  process.exit(code);
}
const backend = start(python, ["-m", "backend"], {
  env: {
    ...process.env,
    PACKET_STUDIO_ENV: "desktop-development",
    SPED_PACKET_APP_DATA_DIR: process.env.SPED_PACKET_APP_DATA_DIR ?? join(projectRoot, ".dev-data"),
    SPED_PACKET_RESOURCE_DIR: process.env.SPED_PACKET_RESOURCE_DIR ?? projectRoot,
    SPED_PACKET_CACHE_DIR: process.env.SPED_PACKET_CACHE_DIR ?? join(projectRoot, ".dev-data", "cache"),
  },
});
backend.once("exit", (code) => { if (code) shutdown(code); });
const desktop = pnpmEntry
  ? start(process.execPath, [pnpmEntry, "tauri", "dev"])
  : start(isWindows ? "pnpm.cmd" : "pnpm", ["tauri", "dev"], { shell: isWindows });
desktop.once("exit", (code) => shutdown(code ?? 0));
process.once("SIGINT", () => shutdown(0));
process.once("SIGTERM", () => shutdown(0));
