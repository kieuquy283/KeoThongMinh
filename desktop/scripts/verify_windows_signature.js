"use strict";

const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const repoRoot = path.resolve(__dirname, "..", "..");
const releaseDir = path.join(repoRoot, "release");
const pkgPath = path.join(repoRoot, "desktop", "package.json");
const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
const version = pkg.version;

const requireSigned = process.env.REQUIRE_SIGNED_ARTIFACTS === "true" || process.env.FORCE_CODE_SIGNING === "true";

const artifacts = [
  path.join(releaseDir, `KeoThongMinh-Portable-v${version}.exe`),
  path.join(releaseDir, `KeoThongMinh-Setup-v${version}.exe`),
];

function checkAuthenticode(filePath) {
  if (!fs.existsSync(filePath)) {
    return { exists: false, status: "not_found", detail: "File not found" };
  }
  try {
    const rawResult = execSync(
      `powershell -NoProfile -Command "$sig = Get-AuthenticodeSignature -FilePath '${filePath.replace(/'/g, "''")}' -ErrorAction SilentlyContinue; if ($sig) { Write-Output ('STATUS=' + $sig.Status.ToString()) } else { Write-Output 'STATUS=NotFound' }"`,
      { encoding: "utf8", timeout: 15000 },
    ).trim();
    if (!rawResult) {
      return { exists: true, status: "error", detail: "Empty result from signature check" };
    }
    const lines = rawResult.split("\n").map((l) => l.trim()).filter(Boolean);
    let statusVal = "Unknown";
    for (const line of lines) {
      if (line.startsWith("STATUS=")) {
        statusVal = line.slice(7);
        break;
      }
    }
    if (statusVal === "NotFound" || statusVal === "NotSigned") {
      return { exists: true, status: "notsigned", detail: `Status: ${statusVal}` };
    }
    if (statusVal === "Valid") {
      return { exists: true, status: "valid", detail: "Signed" };
    }
    return { exists: true, status: "notsigned", detail: `Status: ${statusVal}` };
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (/(not recognized|not found|is not recognized|command was not found)/i.test(msg)) {
      return { exists: true, status: "verifier_not_available", detail: "Get-AuthenticodeSignature not available on this system" };
    }
    return { exists: true, status: "error", detail: msg };
  }
}

console.log("=== Windows Signature Verification ===\n");

const results = [];
let anyFailed = false;

for (const artifact of artifacts) {
  const name = path.basename(artifact);
  const result = checkAuthenticode(artifact);
  results.push({ name, ...result });

  if (result.status === "not_found") {
    console.log(`  ${name}: NOT FOUND (skip signing check)`);
    anyFailed = true;
  } else if (result.status === "valid") {
    console.log(`  ${name}: SIGNED — ${result.detail}`);
  } else if (result.status === "verifier_not_available") {
    console.log(`  ${name}: VERIFIER NOT AVAILABLE (cannot check signature on this system)`);
  } else {
    const label = result.status === "notsigned" ? "NOT SIGNED" : result.detail;
    console.log(`  ${name}: ${label}`);
    if (requireSigned) {
      anyFailed = true;
    }
  }
}

const verifierAvailable = results.some((r) => r.status !== "verifier_not_available" && r.status !== "not_found");
const signed = results.filter((r) => r.status === "valid").length;
const total = artifacts.length;

console.log(`\n=== Results: ${signed}/${total} artifacts signed ===`);

if (!verifierAvailable) {
  console.log("Signature verification: skipped (verifier not available)");
}

if (requireSigned && anyFailed) {
  console.error("ERROR: REQUIRE_SIGNED_ARTIFACTS is set but not all artifacts are signed.");
  process.exit(1);
}

if (requireSigned && signed === total) {
  console.log("All artifacts signed. REQUIRE_SIGNED_ARTIFACTS satisfied.");
}

console.log("");
