"use strict";

const fs = require("fs");
const path = require("path");

const repoRoot = path.resolve(__dirname, "..", "..");
const desktopPkg = JSON.parse(fs.readFileSync(path.join(repoRoot, "desktop", "package.json"), "utf8"));
const frontendPkg = JSON.parse(fs.readFileSync(path.join(repoRoot, "frontend", "package.json"), "utf8"));

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

console.log("=== KeoBot Release Preparation ===\n");

// 1. Version
const version = desktopPkg.version;
console.log(`Version: ${version}\n`);

// 2. Version consistency
check("desktop and frontend version match", desktopPkg.version === frontendPkg.version,
  `desktop=${desktopPkg.version}, frontend=${frontendPkg.version}`);

// 3. Build config
const buildConfig = desktopPkg.build || {};
check("publish config exists", !!buildConfig.publish,
  JSON.stringify(buildConfig.publish));

if (buildConfig.publish) {
  const publish = Array.isArray(buildConfig.publish) ? buildConfig.publish[0] : buildConfig.publish;
  check("publish provider is github", publish?.provider === "github",
    `provider=${publish?.provider}`);
  check("publish owner set", !!publish?.owner, publish?.owner);
  check("publish repo set", !!publish?.repo, publish?.repo);
  check("publish releaseType is draft", publish?.releaseType === "draft",
    `releaseType=${publish?.releaseType}`);
}

// 4. Output filenames
const portableName = buildConfig.portable?.artifactName || "KeoThongMinh-Portable-v${version}.${ext}";
const nsisName = buildConfig.nsis?.artifactName || "KeoThongMinh-Setup-v${version}.${ext}";
check("portable artifact pattern set", portableName.includes("${version}"), portableName);
check("setup artifact pattern set", nsisName.includes("${version}"), nsisName);

// 5. Output directory exists
const releaseDir = path.join(repoRoot, "release");
const releaseDirOk = fs.existsSync(releaseDir) && fs.statSync(releaseDir).isDirectory();
check("release directory exists", releaseDirOk, releaseDir);

// 6. No tokens in config
const mainJsPath = path.join(repoRoot, "desktop", "main.js");
const mainJs = fs.readFileSync(mainJsPath, "utf8");
const tokenPatterns = [
  /GH_TOKEN\s*=\s*["'][^"']+["']/,
  /GITHUB_TOKEN\s*=\s*["'][^"']+["']/,
  /ghp_[A-Za-z0-9]{36}/,
  /gho_[A-Za-z0-9]{36}/,
  /github_pat_[A-Za-z0-9_]{80,}/,
];
let tokenFound = false;
for (const pattern of tokenPatterns) {
  if (pattern.test(mainJs) && !mainJs.includes("process.env.") && !mainJs.includes("secrets.")) {
    console.warn(`  WARN: potential token pattern found in main.js: ${pattern}`);
    tokenFound = true;
  }
}
check("No hardcoded tokens in source", !tokenFound, tokenFound ? "see above" : "ok");

// 7. electron-updater installed
const desktopNodeModules = path.join(repoRoot, "desktop", "node_modules", "electron-updater");
check("electron-updater installed", fs.existsSync(desktopNodeModules), "found");

// 8. Backend dist exists
const backendDist = path.join(repoRoot, "backend", "dist", "keobot_backend", "keobot_backend.exe");
check("Backend exe exists", fs.existsSync(backendDist), backendDist);

// 9. Frontend dist exists
const frontendDist = path.join(repoRoot, "frontend", "dist", "index.html");
check("Frontend dist exists", fs.existsSync(frontendDist), frontendDist);

// 10. Git tag
let currentTag = null;
try {
  currentTag = require("child_process").execSync("git describe --tags --abbrev=0 2>nul", { encoding: "utf8" }).trim();
} catch {
  // No tags yet
}
check("Git tag matches version (optional)", !currentTag || currentTag === `v${version}`,
  currentTag ? `tag=${currentTag}, version=${version}` : "no tag found (first release?)");

console.log(`\n=== Results: ${errors.length} error(s) ===`);
if (errors.length > 0) {
  console.error("\nFix the following before releasing:");
  for (const err of errors) {
    console.error(`  - ${err}`);
  }
  process.exit(1);
}

console.log("All checks passed. Ready to release.\n");
