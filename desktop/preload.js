"use strict";

const { contextBridge } = require("electron");
const { ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("keobotDesktop", {
  platform: process.platform,
  isDesktop: true,
  getSettings: () => ipcRenderer.invoke("keobot:getSettings"),
  saveSettings: (settings) => ipcRenderer.invoke("keobot:saveSettings", settings),
  getStartWithWindows: () => ipcRenderer.invoke("keobot:getStartWithWindows"),
  setStartWithWindows: (enabled) => ipcRenderer.invoke("keobot:setStartWithWindows", enabled),
  requestStartListening: () => ipcRenderer.invoke("keobot:requestStartListening"),
  requestStopListening: () => ipcRenderer.invoke("keobot:requestStopListening"),
  openSettings: () => ipcRenderer.invoke("keobot:openSettings"),
  notifyWakeWordDetected: (phrase) => ipcRenderer.invoke("keobot:wakewordDetected", phrase),
  notifyWakeWordStatus: (status) => ipcRenderer.invoke("keobot:wakewordStatus", status),
  onStartListening: (callback) => {
    const handler = () => callback();
    ipcRenderer.on("handsfree:start-listening", handler);
    return () => {
      ipcRenderer.removeListener("handsfree:start-listening", handler);
    };
  },
  onStopListening: (callback) => {
    const handler = () => callback();
    ipcRenderer.on("handsfree:stop-listening", handler);
    return () => {
      ipcRenderer.removeListener("handsfree:stop-listening", handler);
    };
  },
  onOpenSettings: (callback) => {
    const handler = () => callback();
    ipcRenderer.on("handsfree:open-settings", handler);
    return () => {
      ipcRenderer.removeListener("handsfree:open-settings", handler);
    };
  },
  onSettingsChanged: (callback) => {
    const handler = (_event, settings) => callback(settings);
    ipcRenderer.on("keobot:settingsChanged", handler);
    return () => {
      ipcRenderer.removeListener("keobot:settingsChanged", handler);
    };
  },
  onWakeWordDetected: (callback) => {
    const handler = (_event, phrase) => callback(phrase);
    ipcRenderer.on("wakeword:detected", handler);
    return () => {
      ipcRenderer.removeListener("wakeword:detected", handler);
    };
  },
  onWakeWordStatus: (callback) => {
    const handler = (_event, payload) => callback(payload);
    ipcRenderer.on("wakeword:status", handler);
    return () => {
      ipcRenderer.removeListener("wakeword:status", handler);
    };
  },
  onReminderDue: (callback) => {
    const handler = (_event, reminder) => callback(reminder);
    ipcRenderer.on("keobot:reminderDue", handler);
    return () => {
      ipcRenderer.removeListener("keobot:reminderDue", handler);
    };
  },
  startLocalWakeWord: () => ipcRenderer.invoke("localWakeWord:start"),
  stopLocalWakeWord: () => ipcRenderer.invoke("localWakeWord:stop"),
  getLocalWakeWordStatus: () => ipcRenderer.invoke("localWakeWord:getStatus"),
  onLocalWakeWordStatusChanged: (callback) => {
    const handler = (_event, payload) => callback(payload);
    ipcRenderer.on("localWakeWord:statusChanged", handler);
    return () => {
      ipcRenderer.removeListener("localWakeWord:statusChanged", handler);
    };
  },

  // Diagnostics & metadata
  exportMemory: () => ipcRenderer.invoke("keobot:exportMemory"),
  importMemory: () => ipcRenderer.invoke("keobot:importMemory"),
  resetPersonalData: () => ipcRenderer.invoke("keobot:resetPersonalData"),
  getAppInfo: () => ipcRenderer.invoke("keobot:getAppInfo"),
  getBackendHealth: () => ipcRenderer.invoke("keobot:getBackendHealth"),
  logDiagnostic: (payload) => ipcRenderer.invoke("keobot:logDiagnostic", payload),
  openLogsFolder: () => ipcRenderer.invoke("keobot:openLogsFolder"),

  // Update events
  onUpdateStatus: (callback) => {
    const handler = (_event, payload) => callback(payload);
    ipcRenderer.on("update:status", handler);
    return () => {
      ipcRenderer.removeListener("update:status", handler);
    };
  },
  checkForUpdates: () => ipcRenderer.invoke("update:check"),
  downloadUpdate: () => ipcRenderer.invoke("update:download"),
  quitAndInstall: () => ipcRenderer.invoke("update:quitAndInstall"),
});
