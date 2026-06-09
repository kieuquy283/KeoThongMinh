"use strict";

const fs = require("fs");
const path = require("path");
const http = require("http");
const { spawn } = require("child_process");

const repoRoot = path.resolve(__dirname, "..", "..");
const desktopRoot = path.join(repoRoot, "desktop");
const frontendIndex = path.join(repoRoot, "frontend", "dist", "index.html");
const releaseDir = path.join(repoRoot, "release");
const packageJson = JSON.parse(fs.readFileSync(path.join(desktopRoot, "package.json"), "utf8"));
const expectedArtifacts = [
  path.join(releaseDir, `KeoBot-Portable-v${packageJson.version}.exe`),
  path.join(releaseDir, `KeoBot-Setup-v${packageJson.version}.exe`),
];
const backendCandidates = [
  path.join(releaseDir, "win-unpacked", "resources", "backend", "keobot_backend", "keobot_backend.exe"),
  path.join(repoRoot, "backend", "dist", "keobot_backend", "keobot_backend.exe"),
];
const HEALTH_URL = "http://127.0.0.1:8000/health";

function report(ok, message) {
  console.log(`${ok ? "PASS" : "FAIL"}: ${message}`);
}

function assertFileExists(filePath, label, failures) {
  if (fs.existsSync(filePath)) {
    report(true, `${label} exists: ${filePath}`);
    return;
  }

  report(false, `${label} missing: ${filePath}`);
  failures.push(`${label} missing: ${filePath}`);
}

function httpGet(url, timeoutMs = 1000) {
  return new Promise((resolve, reject) => {
    const request = http.get(url, (response) => {
      response.resume();
      resolve(response);
    });

    request.setTimeout(timeoutMs, () => {
      request.destroy(new Error(`Timeout after ${timeoutMs}ms`));
    });
    request.on("error", reject);
  });
}

async function waitForHealth(timeoutMs = 30000) {
  const startedAt = Date.now();

  while (Date.now() - startedAt < timeoutMs) {
    try {
      const response = await httpGet(HEALTH_URL, 1000);
      if (response.statusCode === 200) {
        return;
      }
    } catch {
      // Keep polling until timeout.
    }

    await new Promise((resolve) => setTimeout(resolve, 500));
  }

  throw new Error(`Backend health check did not return 200 within ${timeoutMs}ms.`);
}

function terminateProcess(child) {
  if (!child || child.exitCode !== null) {
    return;
  }

  try {
    child.kill();
  } catch {
    // ignore
  }

  if (process.platform === "win32") {
    setTimeout(() => {
      if (child.exitCode === null) {
        spawn("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
          windowsHide: true,
          stdio: "ignore",
        });
      }
    }, 3000);
  }
}

async function main() {
  const failures = [];

  assertFileExists(frontendIndex, "frontend index", failures);
  assertFileExists(path.join(releaseDir, "win-unpacked"), "win-unpacked directory", failures);
  assertFileExists(path.join(releaseDir, "win-unpacked", "resources", "backend", "keobot_backend"), "packaged backend folder", failures);
  for (const artifact of expectedArtifacts) {
    assertFileExists(artifact, "release artifact", failures);
  }

  const backendExe = backendCandidates.find((candidate) => fs.existsSync(candidate));
  if (!backendExe) {
    const expectedList = backendCandidates.join(", ");
    report(false, `backend exe not found in any expected location: ${expectedList}`);
    failures.push("backend exe missing");
  } else {
    report(true, `backend exe found: ${backendExe}`);
  }

  if (failures.length > 0) {
    console.log("SMOKE RESULT: FAIL");
    return 1;
  }

  const backendProcess = spawn(backendExe, [], {
    cwd: path.dirname(backendExe),
    env: {
      ...process.env,
      BACKEND_PORT: "8000",
    },
    windowsHide: true,
    stdio: ["ignore", "pipe", "pipe"],
  });

  backendProcess.stdout.on("data", (data) => {
    process.stdout.write(`[backend:stdout] ${data}`);
  });
  backendProcess.stderr.on("data", (data) => {
    process.stderr.write(`[backend:stderr] ${data}`);
  });

  try {
    await waitForHealth();
    report(true, "backend health endpoint returned 200");
    console.log("SMOKE RESULT: PASS");
    return 0;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    report(false, message);
    console.log("SMOKE RESULT: FAIL");
    return 1;
  } finally {
    terminateProcess(backendProcess);
  }
}

main()
  .then((code) => process.exit(code))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
