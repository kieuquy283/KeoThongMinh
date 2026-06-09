import type { KeoBotReminder, KeoBotSettings } from "./types";

declare global {
  interface Window {
    keobotDesktop?: {
      platform: string;
      isDesktop: boolean;
      getSettings: () => Promise<KeoBotSettings>;
      saveSettings: (settings: KeoBotSettings) => Promise<{ ok: boolean }>;
      onReminderDue: (callback: (reminder: KeoBotReminder) => void) => () => void;
    };
  }
}

export {};
