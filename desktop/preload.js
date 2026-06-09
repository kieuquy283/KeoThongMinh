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
});
