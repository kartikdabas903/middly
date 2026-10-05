#!/usr/bin/env node
// Runs scripts/<name>.ps1 on Windows and scripts/<name>.sh elsewhere (used by npm scripts).
import { spawnSync } from "node:child_process"
import { existsSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const root = join(dirname(fileURLToPath(import.meta.url)), "..")
const name = process.argv[2]
const ps1 = join(root, "scripts", `${name}.ps1`)
const [cmd, args] =
  process.platform === "win32" && existsSync(ps1)
    ? ["powershell", ["-ExecutionPolicy", "Bypass", "-File", ps1]]
    : ["bash", [join(root, "scripts", `${name}.sh`)]]
const res = spawnSync(cmd, args, { cwd: root, stdio: "inherit" })
process.exit(res.status ?? 1)
