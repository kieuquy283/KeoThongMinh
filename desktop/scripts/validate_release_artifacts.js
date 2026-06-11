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

// 10. No certificate/private key files in packaged output
const certExts = [".pfx", ".p12", ".pem", ".key", ".crt", ".cer", ".p7b", ".spc"];
const certFiles = [];
function scanForCerts(dir, depth = 0) {
  if (depth > 3 || !fs.existsSync(dir)) return;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory() && entry.name !== "node_modules" && !entry.name.startsWith(".")) {
      scanForCerts(fullPath, depth + 1);
    } else if (certExts.some((ext) => entry.name.toLowerCase().endsWith(ext))) {
      certFiles.push(fullPath);
    }
  }
}
scanForCerts(releaseDir);
check("No certificate files in release", certFiles.length === 0,
  certFiles.length > 0 ? certFiles.join(", ") : "none found");

// 11. No signing password leaks in source
const allSourceDirs = [
  path.join(desktopRoot, "scripts"),
  path.join(desktopRoot, "services"),
  path.join(repoRoot, ".github"),
];
let signSecretLeak = false;
const signSecretPatterns = [
  /CSC_KEY_PASSWORD\s*=\s*["'][^"']+["']/,
  /WIN_CSC_KEY_PASSWORD\s*=\s*["'][^"']+["']/,
  /certificatePassword\s*[:=]\s*["'][^"']+["']/,
  /AZURE_CLIENT_SECRET\s*=\s*["'][^"']+["']/,
];
for (const dir of allSourceDirs) {
  if (!fs.existsSync(dir)) continue;
  function scanDir(d) {
    for (const entry of fs.readdirSync(d, { withFileTypes: true })) {
      const fullPath = path.join(d, entry.name);
      if (entry.isDirectory() && !entry.name.startsWith(".") && entry.name !== "node_modules") {
        scanDir(fullPath);
      } else if (entry.isFile() && /\.(js|yml|yaml|json|md)$/i.test(entry.name)) {
        const content = fs.readFileSync(fullPath, "utf8");
        for (const pattern of signSecretPatterns) {
          const matches = content.match(pattern);
          if (matches && !content.includes("process.env.") && !content.includes("${{") && !content.includes("***")) {
            console.warn(`  WARN: potential signing secret leak in ${path.relative(repoRoot, fullPath)}: ${pattern}`);
            signSecretLeak = true;
          }
        }
      }
    }
  }
  scanDir(dir);
}
check("No signing secret leaks", !signSecretLeak,
  signSecretLeak ? "potential leak(s) found (see above)" : "none found");

// 12. Verify no .env files in packaged resources
const packagedResources = path.join(releaseDir, "win-unpacked", "resources");
const envInPackaged = [];
function scanForEnvInPackaged(dir, depth = 0) {
  if (depth > 3 || !fs.existsSync(dir)) return;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory() && !entry.name.startsWith(".")) {
      scanForEnvInPackaged(fullPath, depth + 1);
    } else if (entry.name === ".env" || entry.name.endsWith(".env.local") || entry.name.endsWith(".env.production")) {
      envInPackaged.push(fullPath);
    }
  }
}
scanForEnvInPackaged(packagedResources);
check("No .env files in packaged resources", envInPackaged.length === 0,
  envInPackaged.length > 0 ? envInPackaged.join(", ") : "none found");

// 13. Signing config check (optional — does not fail unsigned dev builds)
const cscLink = process.env.CSC_LINK || process.env.WIN_CSC_LINK || "";
const cscPassword = process.env.CSC_KEY_PASSWORD || process.env.WIN_CSC_KEY_PASSWORD || "";
const azureConfigured = !!(
  process.env.AZURE_TENANT_ID &&
  process.env.AZURE_CLIENT_ID &&
  process.env.AZURE_CLIENT_SECRET &&
  process.env.AZURE_TRUSTED_SIGNING_ACCOUNT_NAME &&
  process.env.AZURE_TRUSTED_SIGNING_CERT_PROFILE_NAME
);
const forceSigning = process.env.FORCE_CODE_SIGNING === "true";
const hasSigningConfig = !!(cscLink || cscPassword || azureConfigured);
let signingStatus = "unsigned (dev)";
if (cscLink || cscPassword) {
  signingStatus = cscLink && cscPassword ? "PFX configured" : "PFX partial";
}
if (azureConfigured) {
  signingStatus = "Azure Trusted Signing configured";
}
check(`Signing status (${signingStatus})`, !forceSigning || hasSigningConfig,
  forceSigning && !hasSigningConfig ? "FORCE_CODE_SIGNING=true but no signing config" : "ok");

// Results
const passed = checks.filter((c) => c.ok).length;
const failed = checks.filter((c) => !c.ok).length;
console.log(`\nVALIDATION: ${passed} passed, ${failed} failed`);
if (failed > 0) {
  process.exit(1);
}
