"use strict";

const http = require("http");
const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");
const { ipcMain } = require("electron");

const { app, BrowserWindow, dialog } = require("electron");

const DEV_FRONTEND_URL = "http://localhost:5173";
const BACKEND_URL = "http://127.0.0.1:8000";
const BACKEND_HEALTH_URL = `${BACKEND_URL}/health`;
const BACKEND_START_TIMEOUT_MS = Number(process.env.KEOBOT_BACKEND_START_TIMEOUT_MS || "30000");
const DEFAULT_SETTINGS = {
  STT_PROVIDER: "mock",
  LLM_PROVIDER: "local",
  TTS_PROVIDER: "edge_tts",
  OPENAI_API_KEY: "",
  GEMINI_API_KEY: "",
  GOOGLE_API_KEY: "",
  EDGE_TTS_VOICE: "vi-VN-HoaiMyNeural",
};

let backendProcess = null;
let mainWindow = null;
let settingsCache = null;

function getSettingsPath() {
  return path.join(app.getPath("userData"), "config.json");
}

function normalizeSettings(rawSettings) {
  const settings = {
    ...DEFAULT_SETTINGS,
    ...(rawSettings && typeof rawSettings === "object" ? rawSettings : {}),
  };

  settings.STT_PROVIDER = settings.STT_PROVIDER === "openai" ? "openai" : "mock";
  settings.LLM_PROVIDER = ["openai", "gemini"].includes(settings.LLM_PROVIDER) ? settings.LLM_PROVIDER : "local";
  settings.TTS_PROVIDER = "edge_tts";
  settings.OPENAI_API_KEY = typeof settings.OPENAI_API_KEY === "string" ? settings.OPENAI_API_KEY : "";
  settings.GEMINI_API_KEY = typeof settings.GEMINI_API_KEY === "string" ? settings.GEMINI_API_KEY : "";
  settings.GOOGLE_API_KEY = typeof settings.GOOGLE_API_KEY === "string" ? settings.GOOGLE_API_KEY : "";
  settings.EDGE_TTS_VOICE = typeof settings.EDGE_TTS_VOICE === "string" && settings.EDGE_TTS_VOICE.trim()
    ? settings.EDGE_TTS_VOICE.trim()
    : DEFAULT_SETTINGS.EDGE_TTS_VOICE;

  return settings;
}

function readSettingsFromDisk() {
  if (settingsCache) {
    return settingsCache;
  }

  const settingsPath = getSettingsPath();
  if (!fs.existsSync(settingsPath)) {
    settingsCache = { ...DEFAULT_SETTINGS };
    return settingsCache;
  }

  try {
    const raw = JSON.parse(fs.readFileSync(settingsPath, "utf8"));
    settingsCache = normalizeSettings(raw);
  } catch (error) {
    console.error("Failed to read settings file:", error);
    settingsCache = { ...DEFAULT_SETTINGS };
  }

  return settingsCache;
}

function saveSettingsToDisk(nextSettings) {
  const settingsPath = getSettingsPath();
  fs.mkdirSync(path.dirname(settingsPath), { recursive: true });
  const normalized = normalizeSettings(nextSettings);
  fs.writeFileSync(settingsPath, `${JSON.stringify(normalized, null, 2)}\n`, "utf8");
  settingsCache = normalized;
  return normalized;
}

function getBackendDevCommand() {
  return {
    command: "python",
    args: ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
    cwd: path.join(__dirname, "..", "backend"),
  };
}

function buildBackendEnvironment() {
  const settings = readSettingsFromDisk();
  return {
    ...process.env,
    PYTHONUNBUFFERED: "1",
    STT_PROVIDER: settings.STT_PROVIDER,
    LLM_PROVIDER: settings.LLM_PROVIDER,
    TTS_PROVIDER: settings.TTS_PROVIDER,
    OPENAI_API_KEY: settings.OPENAI_API_KEY,
    GEMINI_API_KEY: settings.GEMINI_API_KEY,
    GOOGLE_API_KEY: settings.GOOGLE_API_KEY,
    EDGE_TTS_VOICE: settings.EDGE_TTS_VOICE,
  };
}

function getBackendProductionPath() {
  const candidates = [
    path.join(process.resourcesPath, "backend", "keobot_backend", "keobot_backend.exe"),
    path.join(app.getAppPath(), "backend", "keobot_backend", "keobot_backend.exe"),
    path.join(__dirname, "..", "backend", "dist", "keobot_backend", "keobot_backend.exe"),
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

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isBackendHealthy(timeoutMs = 1000) {
  return new Promise((resolve) => {
    const request = http.get(BACKEND_HEALTH_URL, (response) => {
      response.resume();
      resolve(response.statusCode === 200);
    });

    request.on("error", () => resolve(false));
    request.setTimeout(timeoutMs, () => {
      request.destroy();
      resolve(false);
    });
  });
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
    env: buildBackendEnvironment(),
    windowsHide: true,
  };

  if (isProduction) {
    const backendPath = getBackendProductionPath();
    if (!backendPath) {
      throw new Error(
        "Backend executable not found. Build backend/dist/keobot_backend/keobot_backend.exe or bundle it into resources/backend/keobot_backend/keobot_backend.exe.",
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

async function waitForBackendReady(timeoutMs) {
  const startedAt = Date.now();

  while (Date.now() - startedAt < timeoutMs) {
    if (await isBackendHealthy()) {
      return;
    }

    if (backendProcess && backendProcess.exitCode !== null) {
      if (await isBackendHealthy()) {
        return;
      }

      throw new Error(`Backend exited early with code ${backendProcess.exitCode}.`);
    }

    await sleep(500);
  }

  throw new Error(`Backend not ready after ${timeoutMs}ms.`);
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
    if (!(await isBackendHealthy())) {
      spawnBackend();
    }

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
    const message = error instanceof Error ? error.message : "Failed to start KeoBot desktop app.";
    console.error(message);
    await showFatalError(message);
    app.quit();
  }
}

app.commandLine.appendSwitch("disable-features", "OutOfBlinkCors");

app.whenReady().then(() => {
  ipcMain.handle("keobot:getSettings", async () => readSettingsFromDisk());
  ipcMain.handle("keobot:saveSettings", async (_event, nextSettings) => {
    saveSettingsToDisk(nextSettings);
    return { ok: true };
  });

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
