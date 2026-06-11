"use strict";

const path = require("path");

let Porcupine = null;
let PvRecorder = null;

try {
  Porcupine = require("@picovoice/porcupine-node");
  PvRecorder = require("@picovoice/pvrecorder-node");
} catch {
  // Local wake word engine not available — all operations will return unavailable.
}

const DEFAULT_SENSITIVITY = 0.5;
const FRAME_LENGTH = 512;
const SAMPLE_RATE = 16000;

function createLocalWakeWordService(broadcastStatus, broadcastDetected) {
  let porcupine = null;
  let recorder = null;
  let active = false;
  let stopRequested = false;

  function broadcast(state, phrase) {
    const payload = { status: state, phrase: phrase || null };
    if (typeof broadcastStatus === "function") {
      broadcastStatus(payload);
    }
  }

  function isAvailable() {
    return Porcupine !== null && PvRecorder !== null;
  }

  async function start(options) {
    if (active) {
      return { ok: true };
    }

    if (!isAvailable()) {
      broadcast("unavailable");
      return { ok: false, error: "Local wake word engine modules not available." };
    }

    const sensitivity = typeof options?.sensitivity === "number"
      ? Math.max(0, Math.min(1, options.sensitivity))
      : DEFAULT_SENSITIVITY;
    const accessKey = typeof options?.accessKey === "string" && options.accessKey.trim()
      ? options.accessKey.trim()
      : "";
    const keywordPath = typeof options?.keywordPath === "string" && options.keywordPath.trim()
      ? options.keywordPath.trim()
      : "";
    const audioDeviceIndex = typeof options?.audioDeviceIndex === "number"
      ? options.audioDeviceIndex
      : -1;

    if (!accessKey) {
      broadcast("error", null);
      return { ok: false, error: "Picovoice access key is required." };
    }

    stopRequested = false;
    active = true;
    broadcast("starting");

    try {
      let keywordPathResolved;

      if (keywordPath) {
        keywordPathResolved = path.resolve(keywordPath);
      } else {
        keywordPathResolved = Porcupine.getBuiltinKeywordPath(Porcupine.BuiltinKeyword.PORCUPINE);
      }

      porcupine = new Porcupine(accessKey, [keywordPathResolved], [sensitivity]);

      const audioDevices = PvRecorder.getAvailableDevices();
      const deviceIndex = audioDeviceIndex >= 0 && audioDeviceIndex < audioDevices.length
        ? audioDeviceIndex
        : -1;

      recorder = new PvRecorder(deviceIndex, FRAME_LENGTH);
      recorder.start();
      broadcast("listening_for_wake_word");

      const frameBuffer = new Int16Array(FRAME_LENGTH);

      (function pollLoop() {
        if (!active || stopRequested) {
          return;
        }

        try {
          recorder.read(frameBuffer);
          const keywordIndex = porcupine.process(frameBuffer);

          if (keywordIndex >= 0) {
            const detectedPhrase = keywordPath
              ? path.basename(keywordPath, path.extname(keywordPath))
              : "porcupine (built-in)";
            broadcast("wake_word_detected", detectedPhrase);
            if (typeof broadcastDetected === "function") {
              broadcastDetected(detectedPhrase);
            }
            active = false;

            setImmediate(() => {
              cleanup();
            });
            return;
          }
        } catch (readError) {
          if (!stopRequested) {
            broadcast("error");
          }
          active = false;
          cleanup();
          return;
        }

        setImmediate(pollLoop);
      })();

      return { ok: true };
    } catch (initError) {
      active = false;
      const message = initError instanceof Error ? initError.message : "Failed to initialize local wake word engine.";
      broadcast("error");
      cleanup();
      return { ok: false, error: message };
    }
  }

  function stop() {
    stopRequested = true;
    active = false;
    cleanup();
    broadcast("off");
    return { ok: true };
  }

  function cleanup() {
    try {
      if (recorder) {
        recorder.stop();
      }
    } catch {
      // Ignore cleanup errors.
    }

    try {
      if (porcupine) {
        porcupine.release();
      }
    } catch {
      // Ignore cleanup errors.
    }

    recorder = null;
    porcupine = null;
  }

  function getStatus() {
    if (!isAvailable()) {
      return { status: "unavailable", phrase: null };
    }

    if (!active) {
      return { status: "off", phrase: null };
    }

    return { status: "listening_for_wake_word", phrase: null };
  }

  return {
    start,
    stop,
    getStatus,
    isAvailable,
  };
}

module.exports = { createLocalWakeWordService };
