"use strict";

const fs = require("fs");
const path = require("path");

const pkgPath = path.resolve(__dirname, "..", "package.json");
const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));

const checked = [];

function info(label, value) {
  checked.push({ label, value });
  console.log(`  ${label}: ${value}`);
}

function warn(label, msg) {
  checked.push({ label, value: `WARN: ${msg}` });
  console.warn(`  WARN: ${label} — ${msg}`);
}

console.log("=== Signing Config Check ===\n");

const cscLink = process.env.CSC_LINK || process.env.WIN_CSC_LINK || "";
const cscPassword = process.env.CSC_KEY_PASSWORD || process.env.WIN_CSC_KEY_PASSWORD || "";
const azureTenant = process.env.AZURE_TENANT_ID || "";
const azureClient = process.env.AZURE_CLIENT_ID || "";
const azureSecret = process.env.AZURE_CLIENT_SECRET || "";
const azureAccount = process.env.AZURE_TRUSTED_SIGNING_ACCOUNT_NAME || "";
const azureCertProfile = process.env.AZURE_TRUSTED_SIGNING_CERT_PROFILE_NAME || "";
const azureEndpoint = process.env.AZURE_TRUSTED_SIGNING_ENDPOINT || "";
const forceCodeSigning = process.env.FORCE_CODE_SIGNING === "true" || process.env.FORCE_CODE_SIGNING === "1";
const releaseMode = process.env.RELEASE_MODE || "dev";
const effectiveMode = forceCodeSigning ? "signed-release" : releaseMode;

info("Release mode", effectiveMode);
info("forceCodeSigning", forceCodeSigning ? "yes" : "no");

const hasPfx = !!(cscLink || (pkg.build?.win?.certificateFile));
const hasPfxPassword = !!cscPassword;
const hasAzure = !!(azureTenant && azureClient && azureSecret && azureAccount && azureCertProfile);
const hasAzurePartial = !!(azureTenant || azureClient || azureSecret || azureAccount || azureCertProfile);
const azureComplete = hasAzure;

let mode = "unsigned";
if (hasPfx && hasPfxPassword) {
  mode = "pfx";
} else if (hasPfx && !hasPfxPassword) {
  mode = "pfx-missing-password";
} else if (azureComplete) {
  mode = "azure-trusted-signing";
} else if (hasAzurePartial) {
  mode = "azure-incomplete";
}

info("Signing mode", mode);

if (hasPfx) {
  info("PFX source", cscLink ? "env var (CSC_LINK / WIN_CSC_LINK)" : "config file (build.win.certificateFile)");
  info("PFX password", hasPfxPassword ? "configured (env var)" : "MISSING");
}
if (hasAzure || hasAzurePartial) {
  info("Azure tenant", azureTenant ? "set" : "MISSING");
  info("Azure client ID", azureClient ? "set" : "MISSING");
  info("Azure client secret", azureSecret ? "set (hidden)" : "MISSING");
  info("Azure account name", azureAccount ? "set" : "MISSING");
  info("Azure cert profile", azureCertProfile ? "set" : "MISSING");
  info("Azure endpoint", azureEndpoint ? "set" : "MISSING");
  info("Azure config complete", azureComplete ? "yes" : "no (partial)");
}

if (forceCodeSigning && mode === "unsigned") {
  console.error("\n  ERROR: forceCodeSigning is enabled but no signing config is present.");
  console.error("  Set CSC_LINK + CSC_KEY_PASSWORD, or configure Azure Trusted Signing.");
  process.exit(1);
}

if (forceCodeSigning && mode === "pfx-missing-password") {
  console.error("\n  ERROR: forceCodeSigning is enabled but CSC_KEY_PASSWORD is not set.");
  process.exit(1);
}

if (forceCodeSigning && mode === "azure-incomplete") {
  console.error("\n  ERROR: forceCodeSigning is enabled but Azure config is incomplete.");
  process.exit(1);
}

console.log(`\n=== Signing config check: ${mode === "unsigned" ? "unsigned mode (dev)" : mode} ===`);
console.log("Certificate files and passwords are never logged.\n");
