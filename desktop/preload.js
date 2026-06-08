"use strict";

const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("keobotDesktop", {
  platform: process.platform,
  isDesktop: true,
});

