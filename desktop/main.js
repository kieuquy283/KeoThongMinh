"use strict";

const http = require("http");
const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");
const { ipcMain } = require("electron");
const { createLocalWakeWordService } = require("./localWakeWord");
const { Logger } = require("./services/logger");

const { app, BrowserWindow, Menu, Notification, Tray, dialog, globalShortcut, nativeImage, shell } = require("electron");
const packageJson = require("./package.json");

const DEV_FRONTEND_URL = "http://localhost:5173";
const BACKEND_URL = "http://127.0.0.1:8000";
const BACKEND_HEALTH_URL = `${BACKEND_URL}/health`;
const BACKEND_START_TIMEOUT_MS = Number(process.env.KEOBOT_BACKEND_START_TIMEOUT_MS || "30000");
const REMINDER_POLL_INTERVAL_MS = Number(process.env.KEOBOT_REMINDER_POLL_INTERVAL_MS || "20000");
const DEFAULT_SETTINGS = {
  STT_PROVIDER: "mock",
  LLM_PROVIDER: "local",
  TTS_PROVIDER: "edge_tts",
  WAKE_WORD_ENABLED: false,
  WAKE_WORD_PHRASES: ["keobot oi", "nay keobot", "hey keobot"],
  WAKE_WORD_MODE: "local_stt",
  WAKE_WORD_ENGINE: "web_speech",
  LOCAL_WAKE_WORD_ENABLED: false,
  PICOVOICE_ACCESS_KEY: "",
  PORCUPINE_KEYWORD_PATH: "",
  LOCAL_WAKE_SENSITIVITY: 0.5,
  HOTKEY_ENABLED: true,
  HOTKEY_VALUE: "Ctrl+Shift+K",
  HANDSFREE_AUTO_RETURN_TO_WAKE_MODE: true,
  START_WITH_WINDOWS: false,
  BACKGROUND_ASSISTANT_ENABLED: true,
  OPENAI_API_KEY: "",
  GEMINI_API_KEY: "",
  GOOGLE_API_KEY: "",
  WEATHER_PROVIDER: "none",
  OPENWEATHER_API_KEY: "",
  SEARCH_PROVIDER: "none",
  TAVILY_API_KEY: "",
  SERPAPI_API_KEY: "",
  EDGE_TTS_VOICE: "vi-VN-HoaiMyNeural",
};
const singleInstanceLock = app.requestSingleInstanceLock();

if (!singleInstanceLock) {
  app.quit();
  process.exit(0);
}

let backendProcess = null;
let mainWindow = null;
let windowCreationPromise = null;
let tray = null;
let isQuitting = false;
let settingsCache = null;
let localWakeWordService = null;
let reminderPollTimer = null;
let reminderPollInFlight = false;
let electronPathsInitialized = false;

// Loggers (initialised after app ready)
let mainLogger = null;
let backendLogger = null;
let wakeWordLogger = null;
let updateLogger = null;

// Auto-updater
let autoUpdater = null;

const COMMIT_HASH = process.env.KEOBOT_COMMIT_HASH || "";
const BUILD_MODE = app.isPackaged ? "production" : "development";
const UPDATE_CHANNEL = "stable";

function hasPublishConfig() {
  try {
    const buildPublish = packageJson.build?.publish;
    if (!buildPublish) return false;
    const list = Array.isArray(buildPublish) ? buildPublish : [buildPublish];
    return list.some((p) => p && p.provider === "github");
  } catch {
    return false;
  }
}

function hasSigningConfig() {
  const cscLink = process.env.CSC_LINK || process.env.WIN_CSC_LINK || "";
  if (cscLink) return true;
  if (process.env.AZURE_TENANT_ID && process.env.AZURE_CLIENT_ID && process.env.AZURE_CLIENT_SECRET) return true;
  return false;
}

function getSettingsPath() {
  return path.join(app.getPath("userData"), "config.json");
}

function ensureElectronDataPaths() {
  if (electronPathsInitialized) {
    return;
  }

  const roamingAppData = process.env.APPDATA || path.join(process.env.USERPROFILE || "", "AppData", "Roaming");
  const userDataPath = path.join(roamingAppData, "KeoBot");
  const sessionDataPath = path.join(userDataPath, "Session Data");
  const cachePath = path.join(userDataPath, "Cache");

  app.setPath("userData", userDataPath);
  fs.mkdirSync(sessionDataPath, { recursive: true });
  fs.mkdirSync(cachePath, { recursive: true });
  app.setPath("sessionData", sessionDataPath);
  app.commandLine.appendSwitch("disk-cache-dir", cachePath);
  electronPathsInitialized = true;
}

function initLoggers() {
  mainLogger = new Logger("main");
  backendLogger = new Logger("backend");
  wakeWordLogger = new Logger("wake-word");
  updateLogger = new Logger("update");
}

process.on("uncaughtException", (error) => {
  const msg = error instanceof Error ? error.stack || error.message : String(error);
  if (mainLogger) mainLogger.error(`Uncaught exception: ${msg}`);
  console.error("UNCAUGHT EXCEPTION:", msg);
});

process.on("unhandledRejection", (reason) => {
  const msg = reason instanceof Error ? reason.stack || reason.message : String(reason);
  if (mainLogger) mainLogger.error(`Unhandled rejection: ${msg}`);
  console.error("UNHANDLED REJECTION:", msg);
});

function getLogsDir() {
  return path.join(app.getPath("userData"), "logs");
}

function openLogsFolder() {
  const logsDir = getLogsDir();
  fs.mkdirSync(logsDir, { recursive: true });
  shell.openPath(logsDir);
}

function normalizeSettings(rawSettings) {
  const wakeWordPhrases = Array.isArray(rawSettings?.WAKE_WORD_PHRASES)
    ? rawSettings.WAKE_WORD_PHRASES.filter((phrase) => typeof phrase === "string" && phrase.trim()).map((phrase) => phrase.trim())
    : DEFAULT_SETTINGS.WAKE_WORD_PHRASES;

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
  settings.WEATHER_PROVIDER = settings.WEATHER_PROVIDER === "openweathermap" ? "openweathermap" : "none";
  settings.OPENWEATHER_API_KEY = typeof settings.OPENWEATHER_API_KEY === "string" ? settings.OPENWEATHER_API_KEY : "";
  settings.SEARCH_PROVIDER = ["tavily", "serpapi"].includes(settings.SEARCH_PROVIDER) ? settings.SEARCH_PROVIDER : "none";
  settings.TAVILY_API_KEY = typeof settings.TAVILY_API_KEY === "string" ? settings.TAVILY_API_KEY : "";
  settings.SERPAPI_API_KEY = typeof settings.SERPAPI_API_KEY === "string" ? settings.SERPAPI_API_KEY : "";
  settings.EDGE_TTS_VOICE = typeof settings.EDGE_TTS_VOICE === "string" && settings.EDGE_TTS_VOICE.trim()
    ? settings.EDGE_TTS_VOICE.trim()
    : DEFAULT_SETTINGS.EDGE_TTS_VOICE;
  settings.WAKE_WORD_ENABLED = Boolean(settings.WAKE_WORD_ENABLED);
  settings.WAKE_WORD_PHRASES = wakeWordPhrases.length > 0 ? wakeWordPhrases : DEFAULT_SETTINGS.WAKE_WORD_PHRASES;
  settings.WAKE_WORD_MODE = settings.WAKE_WORD_MODE === "local_stt" ? "local_stt" : "local_stt";
  settings.START_WITH_WINDOWS = Boolean(settings.START_WITH_WINDOWS);
  settings.BACKGROUND_ASSISTANT_ENABLED = settings.BACKGROUND_ASSISTANT_ENABLED !== false;
  settings.HOTKEY_ENABLED = settings.HOTKEY_ENABLED !== false;
  settings.HOTKEY_VALUE = typeof settings.HOTKEY_VALUE === "string" && settings.HOTKEY_VALUE.trim()
    ? settings.HOTKEY_VALUE.trim()
    : DEFAULT_SETTINGS.HOTKEY_VALUE;
  settings.HANDSFREE_AUTO_RETURN_TO_WAKE_MODE = settings.HANDSFREE_AUTO_RETURN_TO_WAKE_MODE !== false;
  settings.WAKE_WORD_ENGINE = ["local", "web_speech", "hotkey_only"].includes(settings.WAKE_WORD_ENGINE)
    ? settings.WAKE_WORD_ENGINE
    : DEFAULT_SETTINGS.WAKE_WORD_ENGINE;
  settings.LOCAL_WAKE_WORD_ENABLED = settings.LOCAL_WAKE_WORD_ENABLED === true;
  settings.PICOVOICE_ACCESS_KEY = typeof settings.PICOVOICE_ACCESS_KEY === "string" ? settings.PICOVOICE_ACCESS_KEY : "";
  settings.PORCUPINE_KEYWORD_PATH = typeof settings.PORCUPINE_KEYWORD_PATH === "string" ? settings.PORCUPINE_KEYWORD_PATH : "";
  settings.LOCAL_WAKE_SENSITIVITY = typeof settings.LOCAL_WAKE_SENSITIVITY === "number" && settings.LOCAL_WAKE_SENSITIVITY >= 0 && settings.LOCAL_WAKE_SENSITIVITY <= 1
    ? settings.LOCAL_WAKE_SENSITIVITY
    : DEFAULT_SETTINGS.LOCAL_WAKE_SENSITIVITY;

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
  applyStartupSetting(normalized);
  broadcastSettingsChange(normalized);
  refreshTrayMenu();
  unregisterGlobalHotkeys();
  registerGlobalHotkeys();
  return normalized;
}

function applyStartupSetting(settings = readSettingsFromDisk()) {
  if (!app.isPackaged) {
    if (settings.START_WITH_WINDOWS) {
      console.warn("START_WITH_WINDOWS is enabled in dev mode, but login item changes are skipped.");
    }
    return;
  }

  try {
    app.setLoginItemSettings({
      openAtLogin: Boolean(settings.START_WITH_WINDOWS),
      path: process.execPath,
    });
  } catch (error) {
    console.warn("Failed to apply start-with-Windows setting:", error);
  }
}

function getStartupSetting() {
  return {
    enabled: Boolean(readSettingsFromDisk().START_WITH_WINDOWS),
  };
}

function shouldKeepRunningInBackground() {
  return Boolean(readSettingsFromDisk().BACKGROUND_ASSISTANT_ENABLED);
}

function broadcastSettingsChange(settings) {
  if (!mainWindow || mainWindow.isDestroyed()) {
    return;
  }

  mainWindow.webContents.send("keobot:settingsChanged", {
    WAKE_WORD_ENABLED: settings.WAKE_WORD_ENABLED,
    WAKE_WORD_PHRASES: settings.WAKE_WORD_PHRASES,
    WAKE_WORD_ENGINE: settings.WAKE_WORD_ENGINE,
    LOCAL_WAKE_WORD_ENABLED: settings.LOCAL_WAKE_WORD_ENABLED,
    PICOVOICE_ACCESS_KEY: settings.PICOVOICE_ACCESS_KEY,
    PORCUPINE_KEYWORD_PATH: settings.PORCUPINE_KEYWORD_PATH,
    LOCAL_WAKE_SENSITIVITY: settings.LOCAL_WAKE_SENSITIVITY,
    HOTKEY_ENABLED: settings.HOTKEY_ENABLED,
    HOTKEY_VALUE: settings.HOTKEY_VALUE,
    HANDSFREE_AUTO_RETURN_TO_WAKE_MODE: settings.HANDSFREE_AUTO_RETURN_TO_WAKE_MODE,
    START_WITH_WINDOWS: settings.START_WITH_WINDOWS,
    BACKGROUND_ASSISTANT_ENABLED: settings.BACKGROUND_ASSISTANT_ENABLED,
  });
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
  ensureElectronDataPaths();
  const userDataPath = app.getPath("userData");
  return {
    ...process.env,
    KEOBOT_DATA_DIR: userDataPath,
    KEOBOT_LOG_DIR: path.join(userDataPath, "logs"),
    PYTHONUNBUFFERED: "1",
    STT_PROVIDER: settings.STT_PROVIDER,
    LLM_PROVIDER: settings.LLM_PROVIDER,
    TTS_PROVIDER: settings.TTS_PROVIDER,
    OPENAI_API_KEY: settings.OPENAI_API_KEY,
    GEMINI_API_KEY: settings.GEMINI_API_KEY,
    GOOGLE_API_KEY: settings.GOOGLE_API_KEY,
    WEATHER_PROVIDER: settings.WEATHER_PROVIDER,
    OPENWEATHER_API_KEY: settings.OPENWEATHER_API_KEY,
    SEARCH_PROVIDER: settings.SEARCH_PROVIDER,
    TAVILY_API_KEY: settings.TAVILY_API_KEY,
    SERPAPI_API_KEY: settings.SERPAPI_API_KEY,
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

function getTrayIconPath() {
  const candidates = [
    path.join(app.getAppPath(), "frontend", "dist", "keobot", "keobot_mascot.png"),
    path.join(__dirname, "..", "frontend", "dist", "keobot", "keobot_mascot.png"),
    path.join(__dirname, "..", "frontend", "public", "keobot", "keobot_mascot.png"),
    path.join(app.getAppPath(), "frontend", "public", "keobot", "keobot_mascot.png"),
  ];

  return candidates.find((candidate) => fs.existsSync(candidate)) || null;
}

function getTrayIcon() {
  const iconPath = getTrayIconPath();
  if (iconPath) {
    return nativeImage.createFromPath(iconPath);
  }

  return nativeImage.createEmpty();
}

async function showMainWindow() {
  if (!mainWindow || mainWindow.isDestroyed()) {
    await createWindow();
    return;
  }

  if (mainWindow.isMinimized()) {
    mainWindow.restore();
  }

  mainWindow.show();
  mainWindow.focus();
}

async function startHandsfreeListening() {
  await showMainWindow();
  mainWindow?.webContents.send("handsfree:start-listening");
}

async function stopHandsfreeListening() {
  await showMainWindow();
  mainWindow?.webContents.send("handsfree:stop-listening");
}

async function openSettingsFromTray() {
  await showMainWindow();
  mainWindow?.webContents.send("handsfree:open-settings");
}

async function notifyWakeWordDetected(phrase) {
  await showMainWindow();
  mainWindow?.webContents.send("wakeword:detected", phrase);
  mainWindow?.webContents.send("wakeword:status", {
    status: "wake_word_detected",
    phrase,
  });
  mainWindow?.webContents.send("handsfree:start-listening");
}

async function notifyWakeWordStatus(status) {
  mainWindow?.webContents.send("wakeword:status", status);
}

function tryInitAutoUpdater() {
  try {
    autoUpdater = require("electron-updater").autoUpdater;
    autoUpdater.logger = updateLogger || console;
    autoUpdater.autoDownload = false;
    autoUpdater.autoInstallOnAppQuit = true;

    autoUpdater.on("checking-for-update", () => {
      if (updateLogger) updateLogger.info("Checking for update...");
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send("update:status", { status: "checking" });
      }
    });
    autoUpdater.on("update-available", (info) => {
      if (updateLogger) updateLogger.info(`Update available: ${JSON.stringify(info)}`);
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send("update:status", { status: "update_available", info });
      }
    });
    autoUpdater.on("update-not-available", (info) => {
      if (updateLogger) updateLogger.info("No update available");
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send("update:status", { status: "update_not_available", info });
      }
    });
    autoUpdater.on("error", (error) => {
      const msg = error instanceof Error ? error.message : String(error);
      if (updateLogger) updateLogger.error(`Update error: ${msg}`);
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send("update:status", { status: "error", message: msg });
      }
    });
    autoUpdater.on("download-progress", (progress) => {
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send("update:status", { status: "downloading", progress });
      }
    });
    autoUpdater.on("update-downloaded", (info) => {
      if (updateLogger) updateLogger.info(`Update downloaded: ${JSON.stringify(info)}`);
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send("update:status", { status: "downloaded", info });
      }
    });
  } catch {
    if (updateLogger) updateLogger.info("electron-updater not available — update support disabled");
  }
}

function logBackendOutput(streamName, data) {
  const message = data.toString().trim();
  if (message) {
    const line = `[${streamName}] ${message}`;
    console.log(`[backend:${streamName}] ${message}`);
    if (backendLogger) backendLogger.info(line);
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

function requestJson(url, { method = "GET", timeoutMs = 2000 } = {}) {
  return new Promise((resolve, reject) => {
    const request = http.request(url, { method }, (response) => {
      let body = "";
      response.setEncoding("utf8");
      response.on("data", (chunk) => {
        body += chunk;
      });
      response.on("end", () => {
        if ((response.statusCode || 500) < 200 || (response.statusCode || 500) >= 300) {
          reject(new Error(`HTTP ${response.statusCode || 500}`));
          return;
        }

        if (!body) {
          resolve(null);
          return;
        }

        try {
          resolve(JSON.parse(body));
        } catch (error) {
          reject(error);
        }
      });
    });

    request.on("error", reject);
    request.setTimeout(timeoutMs, () => {
      request.destroy(new Error(`Timeout after ${timeoutMs}ms`));
    });
    request.end();
  });
}

function showReminderNotification(reminder) {
  const body = `Kẹo Thông Minh nhắc bạn: ${reminder.title}`;
  if (!Notification.isSupported()) {
    console.log(`[reminder] ${body}`);
    return;
  }

  const notification = new Notification({
    title: "Kẹo Thông Minh",
    body,
  });
  notification.on("click", () => {
    void showMainWindow();
  });
  notification.show();
}

function emitReminderDue(reminder) {
  if (!mainWindow || mainWindow.isDestroyed()) {
    return;
  }

  mainWindow.webContents.send("keobot:reminderDue", reminder);
}

async function markReminderTriggered(reminderId) {
  await requestJson(`${BACKEND_URL}/reminders/${reminderId}/triggered`, {
    method: "POST",
    timeoutMs: 3000,
  });
}

async function pollDueReminders() {
  if (reminderPollInFlight) {
    return;
  }

  reminderPollInFlight = true;
  try {
    if (!(await isBackendHealthy())) {
      return;
    }

    const reminders = await requestJson(`${BACKEND_URL}/reminders/due`, {
      method: "GET",
      timeoutMs: 3000,
    });

    if (!Array.isArray(reminders) || reminders.length === 0) {
      return;
    }

    for (const reminder of reminders) {
      if (mainLogger) mainLogger.info(`Reminder due: ${reminder.id} "${reminder.title}"`);
      showReminderNotification(reminder);
      emitReminderDue(reminder);
      await markReminderTriggered(reminder.id);
    }
  } catch (error) {
    console.error("Reminder polling failed:", error);
  } finally {
    reminderPollInFlight = false;
  }
}

function startReminderPolling() {
  stopReminderPolling();
  if (mainLogger) mainLogger.info("Reminder polling started");
  reminderPollTimer = setInterval(() => {
    void pollDueReminders();
  }, REMINDER_POLL_INTERVAL_MS);

  void pollDueReminders();
}

function stopReminderPolling() {
  if (reminderPollTimer) {
    clearInterval(reminderPollTimer);
    reminderPollTimer = null;
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

function createTray() {
  if (tray) {
    return tray;
  }

  tray = new Tray(getTrayIcon());
  tray.setToolTip("Kẹo Thông Minh");
  tray.on("double-click", () => {
    if (mainLogger) mainLogger.info("Tray double-click");
    void showMainWindow();
  });

  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: "Show Kẹo Thông Minh", click: () => void showMainWindow() },
      { label: "Start listening", click: () => void startHandsfreeListening() },
      { label: "Stop listening", click: () => void stopHandsfreeListening() },
      { type: "separator" },
      {
        label: readSettingsFromDisk().WAKE_WORD_ENABLED ? "Disable wake word" : "Enable wake word",
        click: () => {
          const settings = readSettingsFromDisk();
          saveSettingsToDisk({
            ...settings,
            WAKE_WORD_ENABLED: !settings.WAKE_WORD_ENABLED,
          });
          refreshTrayMenu();
        },
      },
      { type: "separator" },
      { label: "Open Settings", click: () => void openSettingsFromTray() },
      { type: "separator" },
      {
        label: "Quit",
        click: () => {
          isQuitting = true;
          app.quit();
        },
      },
    ]),
  );

  return tray;
}

function refreshTrayMenu() {
  if (!tray) {
    return;
  }

  tray.destroy();
  tray = null;
  createTray();
}

function registerGlobalHotkeys() {
  const settings = readSettingsFromDisk();
  if (!settings.HOTKEY_ENABLED) {
    return;
  }

  const hotkey = settings.HOTKEY_VALUE || "CommandOrControl+Shift+K";
  const startRegistered = globalShortcut.register(hotkey, () => {
    if (mainLogger) mainLogger.info(`Hotkey triggered: ${hotkey}`);
    void startHandsfreeListening();
  });
  if (startRegistered) {
    if (mainLogger) mainLogger.info(`Global hotkey registered: ${hotkey}`);
  } else {
    console.warn(
      `Failed to register global hotkey ${hotkey}. Another app or another Kẹo Thông Minh instance may already be using it. Close duplicate windows or change the shortcut if the conflict persists.`,
    );
  }
}

function unregisterGlobalHotkeys() {
  globalShortcut.unregisterAll();
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
  await dialog.showErrorBox("Kẹo Thông Minh", message);
}

async function createWindow() {
  if (mainWindow && !mainWindow.isDestroyed()) {
    return mainWindow;
  }

  if (windowCreationPromise) {
    return windowCreationPromise;
  }

  windowCreationPromise = (async () => {
  mainWindow = new BrowserWindow({
    width: 1100,
    height: 760,
    minWidth: 900,
    minHeight: 640,
    title: "Kẹo Thông Minh",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.on("close", (event) => {
    if (isQuitting || !shouldKeepRunningInBackground()) {
      return;
    }

    event.preventDefault();
    mainWindow?.hide();
  });

  mainWindow.on("minimize", (event) => {
    if (isQuitting || !shouldKeepRunningInBackground()) {
      return;
    }

    event.preventDefault();
    mainWindow?.hide();
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  if (app.isPackaged) {
    await mainWindow.loadFile(getFrontendProductionPath());
    startReminderPolling();
    return mainWindow;
  }

  await mainWindow.loadURL(DEV_FRONTEND_URL);
  startReminderPolling();
  return mainWindow;
  })();

  try {
    return await windowCreationPromise;
  } finally {
    windowCreationPromise = null;
  }
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
        const msg = error instanceof Error ? error.message : String(error);
        if (mainLogger) mainLogger.error(`Backend process error: ${msg}`);
        console.error("Backend process error:", error);
      });
      backendProcess.on("exit", (code, signal) => {
        if (mainLogger) mainLogger.info(`Backend process exited (code=${code}, signal=${signal})`);
        console.log(`[main] Backend process exited (code=${code}, signal=${signal})`);
      });
    }

    await waitForBackendReady(BACKEND_START_TIMEOUT_MS);
    await createWindow();
  } catch (error) {
    const message = error instanceof Error ? error.message : "Failed to start Kẹo Thông Minh desktop app.";
    console.error(message);
    await showFatalError(message);
    app.quit();
  }
}

app.commandLine.appendSwitch("disable-features", "OutOfBlinkCors");
ensureElectronDataPaths();

app.on("second-instance", () => {
  void showMainWindow();
});

app.whenReady().then(() => {
  initLoggers();
  mainLogger.info(`App starting (version=${app.isPackaged ? app.getVersion() : "dev"}, buildMode=${BUILD_MODE})`);
  mainLogger.info(`Electron ${process.versions.electron}, Node ${process.versions.node}, Chrome ${process.versions.chrome}`);

  tryInitAutoUpdater();
  const publishConfigured = hasPublishConfig();
  mainLogger.info(`Auto-updater: ${autoUpdater ? "initialized" : "disabled"} (publishProvider=${publishConfigured ? "github" : "none"})`);

  ipcMain.handle("keobot:getSettings", async () => readSettingsFromDisk());
  ipcMain.handle("keobot:saveSettings", async (_event, nextSettings) => {
    saveSettingsToDisk(nextSettings);
    return { ok: true };
  });
  ipcMain.handle("keobot:getStartWithWindows", async () => getStartupSetting());
  ipcMain.handle("keobot:setStartWithWindows", async (_event, enabled) => {
    const nextSettings = saveSettingsToDisk({
      ...readSettingsFromDisk(),
      START_WITH_WINDOWS: Boolean(enabled),
    });
    return { ok: Boolean(nextSettings.START_WITH_WINDOWS) };
  });
  ipcMain.handle("keobot:requestStartListening", async () => {
    await startHandsfreeListening();
    return { ok: true };
  });
  ipcMain.handle("keobot:requestStopListening", async () => {
    await stopHandsfreeListening();
    return { ok: true };
  });
  ipcMain.handle("keobot:openSettings", async () => {
    await openSettingsFromTray();
    return { ok: true };
  });
  ipcMain.handle("keobot:wakewordDetected", async (_event, phrase) => {
    await notifyWakeWordDetected(typeof phrase === "string" ? phrase : "");
    return { ok: true };
  });
  ipcMain.handle("keobot:wakewordStatus", async (_event, payload) => {
    await notifyWakeWordStatus(payload);
    return { ok: true };
  });

  localWakeWordService = createLocalWakeWordService(
    (payload) => {
      if (wakeWordLogger) wakeWordLogger.info(`Status: ${JSON.stringify(payload)}`);
      mainWindow?.webContents.send("localWakeWord:statusChanged", payload);
    },
    (phrase) => {
      if (wakeWordLogger) wakeWordLogger.info(`Detected: ${phrase}`);
      notifyWakeWordDetected(phrase);
    },
  );

  ipcMain.handle("localWakeWord:start", async () => {
    const settings = readSettingsFromDisk();
    const result = await localWakeWordService.start({
      accessKey: settings.PICOVOICE_ACCESS_KEY,
      keywordPath: settings.PORCUPINE_KEYWORD_PATH,
      sensitivity: settings.LOCAL_WAKE_SENSITIVITY,
    });
    return result;
  });

  ipcMain.handle("localWakeWord:stop", async () => {
    return localWakeWordService.stop();
  });

  ipcMain.handle("localWakeWord:getStatus", async () => {
    return localWakeWordService.getStatus();
  });

  // Diagnostics & metadata
  ipcMain.handle("keobot:getAppInfo", async () => ({
    appVersion: app.isPackaged ? app.getVersion() : packageJson.version,
    buildMode: BUILD_MODE,
    releaseMode: process.env.RELEASE_MODE || (app.isPackaged ? "unsigned-release" : "dev"),
    signedBuild: app.isPackaged ? hasSigningConfig() : false,
    commitHash: COMMIT_HASH,
    updateChannel: UPDATE_CHANNEL,
    publishProvider: hasPublishConfig() ? "github" : null,
    electronVersion: process.versions.electron,
    nodeVersion: process.versions.node,
    chromeVersion: process.versions.chrome,
  }));

  ipcMain.handle("keobot:getBackendHealth", async () => {
    try {
      const healthy = await isBackendHealthy(2000);
      let backendVersion = null;
      try {
        const resp = await fetch("http://127.0.0.1:8765/health", { signal: AbortSignal.timeout(2000) });
        if (resp.ok) {
          const data = await resp.json();
          backendVersion = data.version || null;
        }
      } catch {
        // backend not reachable yet
      }
      return { healthy, version: backendVersion };
    } catch {
      return { healthy: false, version: null };
    }
  });

  ipcMain.handle("keobot:logDiagnostic", async (_event, payload) => {
    if (!payload || typeof payload !== "object") return;
    const { category, message, meta } = payload;
    const targetLogger =
      category === "wake_word" ? wakeWordLogger :
      category === "voice_session" ? mainLogger :
      category === "reminder" ? mainLogger :
      category === "error" ? mainLogger :
      null;
    if (targetLogger) {
      targetLogger.info(`[renderer:${category}] ${message}${meta ? " " + JSON.stringify(meta) : ""}`);
    }
  });

  ipcMain.handle("keobot:openLogsFolder", async () => {
    openLogsFolder();
    return { ok: true };
  });

  // Memory export / import / personal data reset
  ipcMain.handle("keobot:exportMemory", async () => {
    try {
      const data = await requestJson(`${BACKEND_URL}/memory/export`);
      const result = await dialog.showSaveDialog(mainWindow, {
        title: "Export Memory",
        defaultPath: `keobot-memory-${new Date().toISOString().slice(0, 10)}.json`,
        filters: [{ name: "JSON files", extensions: ["json"] }],
      });
      if (result.canceled || !result.filePath) return { ok: false, canceled: true };
      await fs.promises.writeFile(result.filePath, JSON.stringify(data, null, 2), "utf-8");
      return { ok: true, filePath: result.filePath };
    } catch (err) {
      mainLogger.error(`Export memory failed: ${err.message}`);
      return { ok: false, error: err.message };
    }
  });

  ipcMain.handle("keobot:importMemory", async () => {
    try {
      const result = await dialog.showOpenDialog(mainWindow, {
        title: "Import Memory",
        filters: [{ name: "JSON files", extensions: ["json"] }],
        properties: ["openFile"],
      });
      if (result.canceled || result.filePaths.length === 0) return { ok: false, canceled: true };
      const content = await fs.promises.readFile(result.filePaths[0], "utf-8");
      const payload = JSON.parse(content);
      const mode = "merge";
      const resp = await requestJson(`${BACKEND_URL}/memory/import`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ records: payload.records || payload, mode }),
      });
      return { ok: true, ...resp };
    } catch (err) {
      mainLogger.error(`Import memory failed: ${err.message}`);
      return { ok: false, error: err.message };
    }
  });

  ipcMain.handle("keobot:resetPersonalData", async () => {
    const buttonIndex = dialog.showMessageBoxSync(mainWindow, {
      type: "warning",
      title: "Reset Personal Data",
      message: "Are you sure you want to reset all personal data?\n\nThis will delete all memories, reminders, documents, indexes, and temporary files. This action cannot be undone.",
      buttons: ["Cancel", "Reset Everything"],
      defaultId: 0,
      cancelId: 0,
    });
    if (buttonIndex !== 1) return { ok: false, canceled: true };
    try {
      const resp = await fetch(`${BACKEND_URL}/personal-data/reset`, { method: "POST" });
      const data = await resp.json();
      mainLogger.info(`Personal data reset: ${JSON.stringify(data)}`);
      return { ok: true, ...data };
    } catch (err) {
      mainLogger.error(`Reset personal data failed: ${err.message}`);
      return { ok: false, error: err.message };
    }
  });

  // System commands (shutdown, restart, sleep, open/close app)
  let systemCommandTimer = null;
  ipcMain.handle("keobot:executeSystemCommand", async (_event, command, options = {}) => {
    const { delaySeconds = 0, appName = "" } = options;
    if (mainLogger) mainLogger.info(`System command requested: ${command}, delay=${delaySeconds}s, app=${appName}`);

    // Show confirmation for destructive commands
    const destructiveCommands = new Set(["shutdown", "restart"]);
    if (destructiveCommands.has(command)) {
      const buttonIndex = dialog.showMessageBoxSync(mainWindow, {
        type: "warning",
        title: "Xác nhận lệnh hệ thống",
        message: `Bạn có chắc muốn ${command === "shutdown" ? "tắt máy" : "khởi động lại máy"}${delaySeconds > 0 ? ` sau ${delaySeconds} giây` : ""}?`,
        buttons: ["Hủy", "Xác nhận"],
        defaultId: 0,
        cancelId: 0,
      });
      if (buttonIndex !== 1) {
        return { ok: false, canceled: true };
      }
    }

    // Cancel any existing timer
    if (systemCommandTimer) {
      clearTimeout(systemCommandTimer);
      systemCommandTimer = null;
    }

    const execute = () => {
      try {
        if (command === "shutdown") {
          spawn("shutdown", ["/s", "/t", "0"], { windowsHide: true, detached: true });
        } else if (command === "restart") {
          spawn("shutdown", ["/r", "/t", "0"], { windowsHide: true, detached: true });
        } else if (command === "sleep") {
          spawn("rundll32", ["powrprof.dll,SetSuspendState", "0,1,0"], { windowsHide: true, detached: true });
        } else if (command === "open_app") {
          if (appName) {
            spawn("cmd", ["/c", "start", "", appName], { windowsHide: true, detached: true });
          } else {
            return { ok: false, error: "Thiếu tên ứng dụng." };
          }
        } else if (command === "close_app") {
          if (appName) {
            spawn("taskkill", ["/IM", appName, "/F"], { windowsHide: true, detached: true });
          } else {
            return { ok: false, error: "Thiếu tên ứng dụng." };
          }
        } else {
          return { ok: false, error: `Lệnh không hỗ trợ: ${command}` };
        }
        if (mainLogger) mainLogger.info(`System command executed: ${command}`);
        return { ok: true };
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        if (mainLogger) mainLogger.error(`System command failed: ${msg}`);
        return { ok: false, error: msg };
      }
    };

    if (delaySeconds > 0) {
      systemCommandTimer = setTimeout(() => {
        execute();
      }, delaySeconds * 1000);
      return { ok: true, scheduled: true, delaySeconds };
    }

    return execute();
  });

  ipcMain.handle("keobot:cancelSystemCommand", async () => {
    if (systemCommandTimer) {
      clearTimeout(systemCommandTimer);
      systemCommandTimer = null;
      if (mainLogger) mainLogger.info("System command canceled");
      return { ok: true, canceled: true };
    }
    return { ok: false, error: "Không có lệnh nào đang chờ." };
  });

  // Knowledge file picker
  ipcMain.handle("keobot:chooseKnowledgeFiles", async () => {
    try {
      const result = await dialog.showOpenDialog(mainWindow, {
        title: "Choose Knowledge Documents",
        filters: [
          { name: "Documents", extensions: ["txt", "md", "pdf", "docx"] },
        ],
        properties: ["openFile", "multiSelections"],
      });
      if (result.canceled || result.filePaths.length === 0) {
        return { canceled: true, files: [] };
      }
      const files = result.filePaths.map((fp) => {
        let size;
        try {
          size = fs.statSync(fp).size;
        } catch {
          size = 0;
        }
        return { path: fp, name: path.basename(fp), size };
      });
      return { canceled: false, files };
    } catch (err) {
      mainLogger.error("chooseKnowledgeFiles failed: " + (err instanceof Error ? err.message : String(err)));
      return { canceled: true, files: [], error: err instanceof Error ? err.message : String(err) };
    }
  });

  // Update-related IPC
  ipcMain.handle("update:check", async () => {
    if (!autoUpdater) {
      return { ok: false, error: "Auto update is not available." };
    }
    if (!hasPublishConfig()) {
      return { ok: false, error: "Auto update is not configured for this build." };
    }
    try {
      const result = await autoUpdater.checkForUpdates();
      return { ok: true, result };
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (updateLogger) updateLogger.error(`Check for updates failed: ${msg}`);
      return { ok: false, error: msg };
    }
  });

  ipcMain.handle("update:download", async () => {
    if (!autoUpdater) {
      return { ok: false, error: "Auto update is not configured for this build." };
    }
    autoUpdater.downloadUpdate().catch((err) => {
      if (updateLogger) updateLogger.error(`Download update failed: ${err instanceof Error ? err.message : String(err)}`);
    });
    return { ok: true };
  });

  ipcMain.handle("update:quitAndInstall", async () => {
    if (!autoUpdater) {
      return { ok: false, error: "Auto update is not configured for this build." };
    }
    setImmediate(() => autoUpdater.quitAndInstall());
    return { ok: true };
  });

  applyStartupSetting();
  createTray();
  registerGlobalHotkeys();
  void bootstrap();

  app.on("activate", () => {
    void showMainWindow();
  });
});

app.on("before-quit", () => {
  isQuitting = true;
  if (mainLogger) mainLogger.info("App quitting");
  unregisterGlobalHotkeys();
  if (tray) {
    tray.destroy();
    tray = null;
  }
  stopReminderPolling();
  stopBackend();
  if (localWakeWordService) {
    localWakeWordService.stop();
  }
  if (mainLogger) mainLogger.info("Cleanup complete, closing loggers");
  // Close loggers after a short delay to flush pending writes
  setTimeout(() => {
    if (mainLogger) mainLogger.close();
    if (backendLogger) backendLogger.close();
    if (wakeWordLogger) wakeWordLogger.close();
    if (updateLogger) updateLogger.close();
  }, 500);
});

app.on("window-all-closed", () => {
  if (!shouldKeepRunningInBackground()) {
    app.quit();
  }
});
