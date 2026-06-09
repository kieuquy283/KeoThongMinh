import type { KeoBotReminder, KeoBotSettings, WakeWordState, WakeWordStatus } from "./types";

declare global {
  interface Window {
    keobotDesktop?: {
      platform: string;
      isDesktop: boolean;
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
        callback: (settings: Pick<KeoBotSettings, "WAKE_WORD_ENABLED" | "WAKE_WORD_PHRASES" | "START_WITH_WINDOWS" | "BACKGROUND_ASSISTANT_ENABLED">) => void,
      ) => () => void;
      onWakeWordDetected: (callback: (phrase: string) => void) => () => void;
      onWakeWordStatus: (callback: (status: WakeWordState) => void) => () => void;
      onReminderDue: (callback: (reminder: KeoBotReminder) => void) => () => void;
    };
  }
}

export {};
