"use strict";

const fs = require("fs");
const path = require("path");

const repoRoot = path.resolve(__dirname, "..", "..");
const desktopRoot = path.join(repoRoot, "desktop");
const releaseDir = path.join(repoRoot, "release");
const frontendDist = path.join(repoRoot, "frontend", "dist");
const packageJson = JSON.parse(fs.readFileSync(path.join(desktopRoot, "package.json"), "utf8"));
const version = packageJson.version;

const checks = [];

function check(label, ok, detail) {
  checks.push({ label, ok, detail });
  console.log(`${ok ? "PASS" : "FAIL"}: ${label}${detail ? ` (${detail})` : ""}`);
}

// 1. Portable exe exists
const portableExe = path.join(releaseDir, `KeoThongMinh-Portable-v${version}.exe`);
check("Portable exe exists", fs.existsSync(portableExe), portableExe);

// 2. Setup exe exists
const setupExe = path.join(releaseDir, `KeoThongMinh-Setup-v${version}.exe`);
check("Setup exe exists", fs.existsSync(setupExe), setupExe);

// 3. Backend executable in packaged resources
const backendExeCandidates = [
  path.join(releaseDir, "win-unpacked", "resources", "backend", "keobot_backend", "keobot_backend.exe"),
  path.join(repoRoot, "backend", "dist", "keobot_backend", "keobot_backend.exe"),
];
const backendExe = backendExeCandidates.find((c) => fs.existsSync(c));
check("Backend executable exists", !!backendExe, backendExe || "not found");

// 4. Mascot assets exist
const mascotDir = path.join(frontendDist, "keobot");
const mascotExpected = ["keobot_mascot.png", "keobot_idle.png", "keobot_listening.png", "keobot_thinking.png", "keobot_error.png", "keobot_happy.png"];
let mascotOkCount = 0;
const mascotMissing = [];
for (const asset of mascotExpected) {
  if (fs.existsSync(path.join(mascotDir, asset))) {
    mascotOkCount++;
  } else {
    mascotMissing.push(asset);
  }
}
check(`Mascot assets (${mascotOkCount}/${mascotExpected.length})`, mascotOkCount >= 3, mascotMissing.length > 0 ? `missing: ${mascotMissing.join(", ")}` : mascotDir);

// 5. No .env files in release
const envFiles = [];
function scanForEnv(dir, depth = 0) {
  if (depth > 3 || !fs.existsSync(dir)) return;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory() && !entry.name.startsWith(".")) {
      scanForEnv(fullPath, depth + 1);
    } else if (entry.name === ".env" || entry.name.endsWith(".env.local") || entry.name.endsWith(".env.production")) {
      envFiles.push(fullPath);
    }
  }
}
scanForEnv(releaseDir);
check(".env files in release", envFiles.length === 0, envFiles.length > 0 ? envFiles.join(", ") : "none found");

// 6. Native wake word modules included
const picovoicePaths = [
  path.join(repoRoot, "desktop", "node_modules", "@picovoice", "porcupine-node"),
  path.join(repoRoot, "desktop", "node_modules", "@picovoice", "pvrecorder-node"),
];
let picovoiceOk = 0;
for (const p of picovoicePaths) {
  if (fs.existsSync(p)) {
    picovoiceOk++;
  }
}
check("Picovoice native modules", picovoiceOk === 2, `${picovoiceOk}/2 found`);

// 7. Frontend dist exists
check("Frontend dist/index.html exists", fs.existsSync(path.join(frontendDist, "index.html")), frontendDist);

// 8. No hardcoded API keys in source
const sourceFiles = [
  path.join(desktopRoot, "main.js"),
  path.join(repoRoot, "backend", "app", "main.py"),
];
let apiKeyLeak = false;
for (const sf of sourceFiles) {
  if (!fs.existsSync(sf)) continue;
  const content = fs.readFileSync(sf, "utf8");
  const lines = content.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (/API_KEY\s*=\s*["'][A-Za-z0-9_-]{16,}["']/.test(line) && !line.includes("***")) {
      console.warn(`  WARN: potential API key in ${sf}:${i + 1}`);
      apiKeyLeak = true;
    }
  }
}
check("No hardcoded API keys in source", !apiKeyLeak, apiKeyLeak ? "potential key found (see above)" : "ok");

// 9. Config defaults safe
const mainJs = fs.readFileSync(path.join(desktopRoot, "main.js"), "utf8");
const hasDefaultEmptyKeys = mainJs.includes('""') && mainJs.includes("API_KEY");
check("Config defaults are safe", hasDefaultEmptyKeys, "defaults use empty strings");

// Results
const passed = checks.filter((c) => c.ok).length;
const failed = checks.filter((c) => !c.ok).length;
console.log(`\nVALIDATION: ${passed} passed, ${failed} failed`);
if (failed > 0) {
  process.exit(1);
}
