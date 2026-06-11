import type { DiagnosticEvent } from "./utils/diagnostics";
import type { KeoBotReminder, KeoBotSettings, WakeWordState, WakeWordStatus } from "./types";

declare global {
  interface Window {
    keobotDesktop?: {
      platform: string;
      isDesktop: boolean;
      appVersion?: string;
      buildMode?: string;
      commitHash?: string;
      getSettings: () => Promise<KeoBotSettings>;
      saveSettings: (settings: KeoBotSettings) => Promise<{ ok: boolean }>;
      getStartWithWindows: () => Promise<{ enabled: boolean }>;
      setStartWithWindows: (enabled: boolean) => Promise<{ ok: boolean }>;
      requestStartListening: () => Promise<void>;
      requestStopListening: () => Promise<void>;
      openSettings: () => Promise<void>;
      notifyWakeWordDetected: (phrase: string) => Promise<{ ok: boolean }>;
      notifyWakeWordStatus: (status: WakeWordState) => Promise<{ ok: boolean }>;
      onStartListening: (callback: () => void) => () => void;
      onStopListening: (callback: () => void) => () => void;
      onOpenSettings: (callback: () => void) => () => void;
      onSettingsChanged: (
        callback: (settings: Pick<KeoBotSettings, "WAKE_WORD_ENABLED" | "WAKE_WORD_PHRASES" | "WAKE_WORD_ENGINE" | "LOCAL_WAKE_WORD_ENABLED" | "PICOVOICE_ACCESS_KEY" | "PORCUPINE_KEYWORD_PATH" | "LOCAL_WAKE_SENSITIVITY" | "HOTKEY_ENABLED" | "HOTKEY_VALUE" | "HANDSFREE_AUTO_RETURN_TO_WAKE_MODE" | "START_WITH_WINDOWS" | "BACKGROUND_ASSISTANT_ENABLED">) => void,
      ) => () => void;
      onWakeWordDetected: (callback: (phrase: string) => void) => () => void;
      onWakeWordStatus: (callback: (status: WakeWordState) => void) => () => void;
      onReminderDue: (callback: (reminder: KeoBotReminder) => void) => () => void;
      startLocalWakeWord: () => Promise<{ ok: boolean; error?: string }>;
      stopLocalWakeWord: () => Promise<{ ok: boolean }>;
      getLocalWakeWordStatus: () => Promise<WakeWordState>;
      onLocalWakeWordStatusChanged: (callback: (status: WakeWordState) => void) => () => void;
      // Diagnostics & metadata
      getAppInfo: () => Promise<{
        appVersion: string;
        buildMode: string;
        releaseMode: string;
        signedBuild: boolean;
        commitHash: string;
        updateChannel: string;
        publishProvider: string | null;
        electronVersion: string;
        nodeVersion: string;
        chromeVersion: string;
      }>;
      getBackendHealth: () => Promise<{ healthy: boolean; version: string | null }>;
      logDiagnostic: (payload: { category: string; message: string; meta?: Record<string, unknown> }) => Promise<void>;
      openLogsFolder: () => Promise<{ ok: boolean }>;
      // Update events
      onUpdateStatus: (callback: (status: {
        status: "idle" | "checking" | "update_available" | "update_not_available" | "downloading" | "downloaded" | "error";
        info?: unknown;
        progress?: unknown;
        message?: string;
      }) => void) => () => void;
      checkForUpdates: () => Promise<{ ok: boolean; error?: string }>;
      downloadUpdate: () => Promise<{ ok: boolean; error?: string }>;
      quitAndInstall: () => Promise<{ ok: boolean; error?: string }>;
    };
  }
}

export {};
