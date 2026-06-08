"use strict";

const http = require("http");
const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

const { app, BrowserWindow, dialog } = require("electron");

const DEV_FRONTEND_URL = "http://localhost:5173";
const BACKEND_URL = "http://127.0.0.1:8000";
const BACKEND_HEALTH_URL = `${BACKEND_URL}/health`;
const BACKEND_START_TIMEOUT_MS = Number(process.env.KEOBOT_BACKEND_START_TIMEOUT_MS || "30000");

let backendProcess = null;
let mainWindow = null;

function getBackendDevCommand() {
  return {
    command: "python",
    args: ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
    cwd: path.join(__dirname, "..", "backend"),
  };
}

function getBackendProductionPath() {
  const candidates = [
    path.join(process.resourcesPath, "backend", "keobot_backend.exe"),
    path.join(app.getAppPath(), "backend", "dist", "keobot_backend.exe"),
  ];

  return candidates.find((candidate) => fs.existsSync(candidate)) || null;
}

function getFrontendProductionPath() {
  return path.join(app.getAppPath(), "frontend", "dist", "index.html");
}

function logBackendOutput(streamName, data) {
  const message = data.toString().trim();
  if (message) {
    console.log(`[backend:${streamName}] ${message}`);
  }
}

function stopBackend() {
  if (!backendProcess || backendProcess.killed) {
    backendProcess = null;
    return;
  }

  try {
    backendProcess.kill();
  } catch (error) {
    console.error("Failed to stop backend:", error);
  } finally {
    backendProcess = null;
  }
}

function spawnBackend() {
  const isProduction = app.isPackaged;
  const spawnOptions = {
    env: {
      ...process.env,
      PYTHONUNBUFFERED: "1",
    },
    windowsHide: true,
  };

  if (isProduction) {
    const backendPath = getBackendProductionPath();
    if (!backendPath) {
      throw new Error(
        "Không tìm thấy backend executable. Hãy build backend trước: backend/dist/keobot_backend.exe hoặc bundle vào resources/backend/keobot_backend.exe.",
      );
    }

    backendProcess = spawn(backendPath, [], spawnOptions);
    return;
  }

  const { command, args, cwd } = getBackendDevCommand();
  backendProcess = spawn(command, args, {
    ...spawnOptions,
    cwd,
  });
}

function waitForBackendReady(timeoutMs) {
  return new Promise((resolve, reject) => {
    const startedAt = Date.now();

    const check = () => {
      if (backendProcess && backendProcess.exitCode !== null) {
        reject(new Error(`Backend exited early with code ${backendProcess.exitCode}.`));
        return;
      }

      const request = http.get(BACKEND_HEALTH_URL, (response) => {
        response.resume();
        if (response.statusCode === 200) {
          resolve();
          return;
        }

        if (Date.now() - startedAt >= timeoutMs) {
          reject(new Error(`Backend không sẵn sàng sau ${timeoutMs}ms.`));
          return;
        }

        setTimeout(check, 500);
      });

      request.on("error", () => {
        if (Date.now() - startedAt >= timeoutMs) {
          reject(new Error(`Backend không sẵn sàng sau ${timeoutMs}ms.`));
          return;
        }

        setTimeout(check, 500);
      });

      request.setTimeout(1000, () => {
        request.destroy();
      });
    };

    check();
  });
}

async function showFatalError(message) {
  await dialog.showErrorBox("KeoBot", message);
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1100,
    height: 760,
    minWidth: 900,
    minHeight: 640,
    title: "KeoBot",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  if (app.isPackaged) {
    await mainWindow.loadFile(getFrontendProductionPath());
    return;
  }

  await mainWindow.loadURL(DEV_FRONTEND_URL);
}

async function bootstrap() {
  try {
    spawnBackend();

    if (backendProcess) {
      backendProcess.stdout?.on("data", (data) => logBackendOutput("stdout", data));
      backendProcess.stderr?.on("data", (data) => logBackendOutput("stderr", data));
      backendProcess.on("error", (error) => {
        console.error("Backend process error:", error);
      });
    }

    await waitForBackendReady(BACKEND_START_TIMEOUT_MS);
    await createWindow();
  } catch (error) {
    const message = error instanceof Error ? error.message : "Không thể khởi động KeoBot desktop app.";
    console.error(message);
    await showFatalError(message);
    app.quit();
  }
}

app.commandLine.appendSwitch("disable-features", "OutOfBlinkCors");

app.whenReady().then(() => {
  void bootstrap();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      void createWindow();
    }
  });
});

app.on("before-quit", () => {
  stopBackend();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
