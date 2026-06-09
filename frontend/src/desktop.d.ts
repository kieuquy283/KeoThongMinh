import type { KeoBotReminder, KeoBotSettings } from "./types";

declare global {
  interface Window {
    keobotDesktop?: {
      platform: string;
      isDesktop: boolean;
      getSettings: () => Promise<KeoBotSettings>;
      saveSettings: (settings: KeoBotSettings) => Promise<{ ok: boolean }>;
      requestStartListening: () => Promise<void>;
      requestStopListening: () => Promise<void>;
      openSettings: () => Promise<void>;
      onStartListening: (callback: () => void) => () => void;
      onStopListening: (callback: () => void) => () => void;
      onOpenSettings: (callback: () => void) => () => void;
      onReminderDue: (callback: (reminder: KeoBotReminder) => void) => () => void;
    };
  }
}

export {};
