import { logDiagnostic } from "./diagnostics";

type PlaybackState = "idle" | "playing" | "stopped" | "error";

type PlaybackListener = (state: PlaybackState) => void;

let currentAudio: HTMLAudioElement | null = null;
let currentState: PlaybackState = "idle";
let objectUrls: string[] = [];
let listeners: Set<PlaybackListener> = new Set();

function notifyListeners(): void {
  for (const listener of listeners) {
    listener(currentState);
  }
}

function cleanupObjectUrl(url: string): void {
  const index = objectUrls.indexOf(url);
  if (index >= 0) {
    objectUrls.splice(index, 1);
  }
  try {
    URL.revokeObjectURL(url);
  } catch {
    // Ignore cleanup errors.
  }
}

function stopCurrent(): void {
  if (!currentAudio) {
    return;
  }

  try {
    currentAudio.pause();
    currentAudio.currentTime = 0;
  } catch {
    // Ignore stop errors.
  }

  currentAudio.onended = null;
  currentAudio.onerror = null;
  currentAudio = null;
}

function play(url: string): Promise<void> {
  return new Promise((resolve, reject) => {
    stopCurrent();
    cleanupObjectUrl(url);

    currentState = "playing";
    notifyListeners();

    const audio = new Audio(url);
    currentAudio = audio;

    audio.onended = () => {
      currentState = "idle";
      currentAudio = null;
      notifyListeners();
      resolve();
    };

    audio.onerror = () => {
      currentState = "error";
      currentAudio = null;
      notifyListeners();
      reject(new Error("Audio playback failed."));
    };

    try {
      void audio.play();
    } catch (playError) {
      currentState = "error";
      currentAudio = null;
      notifyListeners();
      reject(playError);
    }
  });
}

function stop(): void {
  if (currentState === "idle" || currentState === "error") {
    return;
  }

  stopCurrent();
  currentState = "stopped";
  notifyListeners();
}

function getState(): PlaybackState {
  return currentState;
}

function isPlaying(): boolean {
  return currentState === "playing";
}

function isStopped(): boolean {
  return currentState === "stopped" || currentState === "idle";
}

function subscribe(listener: PlaybackListener): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function reset(): void {
  stopCurrent();
  currentState = "idle";
  for (const url of objectUrls) {
    cleanupObjectUrl(url);
  }
  objectUrls = [];
  listeners.clear();
  notifyListeners();
}

export { play, stop, getState, isPlaying, isStopped, subscribe, reset };
export type { PlaybackState };
