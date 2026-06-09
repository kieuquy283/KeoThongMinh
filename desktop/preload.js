"use strict";

const { contextBridge } = require("electron");
const { ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("keobotDesktop", {
  platform: process.platform,
  isDesktop: true,
  getSettings: () => ipcRenderer.invoke("keobot:getSettings"),
  saveSettings: (settings) => ipcRenderer.invoke("keobot:saveSettings", settings),
  requestStartListening: () => ipcRenderer.invoke("keobot:requestStartListening"),
  requestStopListening: () => ipcRenderer.invoke("keobot:requestStopListening"),
  openSettings: () => ipcRenderer.invoke("keobot:openSettings"),
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
  onReminderDue: (callback) => {
    const handler = (_event, reminder) => callback(reminder);
    ipcRenderer.on("keobot:reminderDue", handler);
    return () => {
      ipcRenderer.removeListener("keobot:reminderDue", handler);
    };
  },
});
