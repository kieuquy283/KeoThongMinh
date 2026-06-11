"use strict";

const fs = require("fs");
const path = require("path");

const repoRoot = path.resolve(__dirname, "..", "..");
const releaseDir = path.join(repoRoot, "release");
const pkg = JSON.parse(fs.readFileSync(path.join(repoRoot, "desktop", "package.json"), "utf8"));
const version = pkg.version;

const errors = [];

function error(msg) {
  errors.push(msg);
  console.error(`  ERROR: ${msg}`);
}

function check(label, ok, detail) {
  if (ok) {
    console.log(`  PASS: ${label}`);
  } else {
    error(`${label}: ${detail || "fail"}`);
  }
}

console.log("=== Update Metadata Validation ===\n");

// 1. Check latest.yml exists
const latestYml = path.join(releaseDir, "latest.yml");
check("latest.yml exists", fs.existsSync(latestYml), latestYml);

if (fs.existsSync(latestYml)) {
  try {
    const content = fs.readFileSync(latestYml, "utf8");
    const meta = {};
    for (const line of content.split("\n")) {
      const m = line.match(/^(\w+):\s*(.+)/);
      if (m) meta[m[1]] = m[2].trim();
    }

    check("latest.yml has version", meta?.version === version,
      `expected=${version}, got=${meta?.version}`);
    check("latest.yml has path", !!meta?.path, meta?.path);
    check("latest.yml has sha512", !!meta?.sha512, "sha512 present");

    if (meta?.sha512) {
      check("sha512 looks valid", meta.sha512.length >= 64, `length=${meta.sha512.length}`);
    }
  } catch (parseError) {
    error(`latest.yml parse error: ${parseError instanceof Error ? parseError.message : String(parseError)}`);
  }
}

// 2. Check latest.yml blockmap exists if configured
const latestBlockmap = path.join(releaseDir, "latest.yml.blockmap");
if (fs.existsSync(latestBlockmap)) {
  check("latest.yml.blockmap exists", true, latestBlockmap);
} else {
  check("latest.yml.blockmap (optional)", true, "not generated (expected for portable-only publish)");
}

// 3. Verify installer exe exists with matching version
const setupExe = path.join(releaseDir, `KeoThongMinh-Setup-v${version}.exe`);
check("Setup exe with matching version", fs.existsSync(setupExe), setupExe);

// 4. Verify portable exe
const portableExe = path.join(releaseDir, `KeoThongMinh-Portable-v${version}.exe`);
check("Portable exe with matching version", fs.existsSync(portableExe), portableExe);

// 5. No token leaks
const latestContent = fs.readFileSync(latestYml, "utf8");
const tokenPatterns = [/ghp_[A-Za-z0-9]{36}/, /gho_[A-Za-z0-9]{36}/, /github_pat_/];
let tokenLeak = false;
for (const p of tokenPatterns) {
  if (p.test(latestContent)) {
    console.warn("  WARN: potential token in latest.yml");
    tokenLeak = true;
  }
}
check("No tokens in update metadata", !tokenLeak, tokenLeak ? "potential token found" : "ok");

console.log(`\n=== Results: ${errors.length} error(s) ===`);
if (errors.length > 0) {
  process.exit(1);
}
