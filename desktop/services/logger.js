"use strict";

const fs = require("fs");
const path = require("path");
const { app } = require("electron");

const REDACT_KEYS = [
  "API_KEY",
  "ACCESS_KEY",
  "SECRET",
  "PASSWORD",
  "TOKEN",
  "AUTH",
];

function redactSensitive(value) {
  if (typeof value !== "string") return value;
  let result = value;
  for (const key of REDACT_KEYS) {
    const regex = new RegExp(`(${key}=?["']?)[^\\s"']+`, "gi");
    result = result.replace(regex, `$1***`);
  }
  return result;
}

class Logger {
  constructor(subdir, maxBytes = 5 * 1024 * 1024) {
    this.maxBytes = maxBytes;
    this.logDir = path.join(app.getPath("userData"), "logs", subdir);
    this.currentPath = null;
    this.stream = null;
    this._ensureDir();
    this._rotate();
  }

  _ensureDir() {
    fs.mkdirSync(this.logDir, { recursive: true });
  }

  _timestamp() {
    return new Date().toISOString();
  }

  _rotate() {
    if (this.stream) {
      try { this.stream.end(); } catch { /* ignore */ }
    }

    const now = new Date();
    const dateStr = now.toISOString().slice(0, 10);
    const logPath = path.join(this.logDir, `${dateStr}.log`);

    try {
      const stat = fs.statSync(logPath);
      if (stat.size >= this.maxBytes) {
        const idx = 1;
        const rotatedPath = path.join(this.logDir, `${dateStr}.${idx}.log`);
        fs.renameSync(logPath, rotatedPath);
      }
    } catch {
      // File doesn't exist yet, that's fine
    }

    this.currentPath = logPath;
    this.stream = fs.createWriteStream(logPath, { flags: "a", encoding: "utf8" });
  }

  _write(level, message) {
    const line = `[${this._timestamp()}] [${level.toUpperCase()}] ${redactSensitive(message)}\n`;
    if (this.stream) {
      this.stream.write(line);
    }
    // Also mirror to console
    if (level === "error" || level === "warn") {
      console[level](`[logger:${level}] ${message}`);
    } else {
      console.log(`[logger:${level}] ${message}`);
    }

    if (this.stream && this.stream.bytesWritten >= this.maxBytes) {
      this._rotate();
    }
  }

  debug(message) { this._write("debug", message); }
  info(message) { this._write("info", message); }
  warn(message) { this._write("warn", message); }
  error(message) { this._write("error", message); }

  close() {
    if (this.stream) {
      try { this.stream.end(); } catch { /* ignore */ }
      this.stream = null;
    }
  }
}

module.exports = { Logger, redactSensitive };
