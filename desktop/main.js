"use strict";

const http = require("http");
const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");
const { ipcMain } = require("electron");

const { app, BrowserWindow, Menu, Notification, Tray, dialog, globalShortcut, nativeImage } = require("electron");

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

let backendProcess = null;
let mainWindow = null;
let windowCreationPromise = null;
let tray = null;
let isQuitting = false;
let settingsCache = null;
let reminderPollTimer = null;
let reminderPollInFlight = false;

function getSettingsPath() {
  return path.join(app.getPath("userData"), "config.json");
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
  return {
    ...process.env,
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
  const body = `KeoBot nhắc bạn: ${reminder.title}`;
  if (!Notification.isSupported()) {
    console.log(`[reminder] ${body}`);
    return;
  }

  const notification = new Notification({
    title: "KeoBot",
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
  tray.setToolTip("KeoBot");
  tray.on("double-click", () => {
    void showMainWindow();
  });

  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: "Show KeoBot", click: () => void showMainWindow() },
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
  const startRegistered = globalShortcut.register("CommandOrControl+Shift+K", () => {
    void startHandsfreeListening();
  });
  if (!startRegistered) {
    console.warn("Failed to register global hotkey Ctrl+Shift+K.");
  }

  const stopRegistered = globalShortcut.register("CommandOrControl+Shift+L", () => {
    void stopHandsfreeListening();
  });
  if (!stopRegistered) {
    console.warn("Failed to register global hotkey Ctrl+Shift+L.");
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
    title: "KeoBot",
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
  globalShortcut.unregisterAll();
  if (tray) {
    tray.destroy();
    tray = null;
  }
  stopReminderPolling();
  stopBackend();
});

app.on("window-all-closed", () => {
  if (!shouldKeepRunningInBackground()) {
    app.quit();
  }
});
