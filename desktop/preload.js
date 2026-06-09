"use strict";

const { contextBridge } = require("electron");
const { ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("keobotDesktop", {
  platform: process.platform,
  isDesktop: true,
  getSettings: () => ipcRenderer.invoke("keobot:getSettings"),
  saveSettings: (settings) => ipcRenderer.invoke("keobot:saveSettings", settings),
  onReminderDue: (callback) => {
    const handler = (_event, reminder) => callback(reminder);
    ipcRenderer.on("keobot:reminderDue", handler);
    return () => {
      ipcRenderer.removeListener("keobot:reminderDue", handler);
    };
  },
});
