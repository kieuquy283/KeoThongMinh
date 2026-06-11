const MAX_EVENTS = 200;

export type DiagnosticEvent = {
  ts: string;
  category: "voice_session" | "audio_playback" | "wake_word" | "reminder" | "tool_provider" | "app" | "error";
  message: string;
  meta?: Record<string, unknown>;
};

const events: DiagnosticEvent[] = [];

export function logDiagnostic(
  category: DiagnosticEvent["category"],
  message: string,
  meta?: Record<string, unknown>,
): void {
  const event: DiagnosticEvent = {
    ts: new Date().toISOString(),
    category,
    message,
    meta,
  };
  events.push(event);
  if (events.length > MAX_EVENTS) {
    events.splice(0, events.length - MAX_EVENTS);
  }
  if (import.meta.env.DEV) {
    console.log(`[diag:${category}] ${message}`, meta ?? "");
  }
  const desktop = window.keobotDesktop;
  if (desktop?.logDiagnostic) {
    desktop.logDiagnostic({ category, message, meta });
  }
}

export function getDiagnosticEvents(): DiagnosticEvent[] {
  return [...events];
}

export function getDiagnosticSummary(): Record<string, number> {
  const summary: Record<string, number> = {};
  for (const ev of events) {
    summary[ev.category] = (summary[ev.category] ?? 0) + 1;
  }
  return summary;
}

export function clearDiagnosticEvents(): void {
  events.length = 0;
}

export function getAppDiagnostics(): Record<string, unknown> {
  return {
    userAgent: navigator.userAgent,
    platform: navigator.platform,
    language: navigator.language,
    isDesktop: Boolean(window.keobotDesktop?.isDesktop),
    desktopPlatform: window.keobotDesktop?.platform ?? null,
    diagnosticEvents: getDiagnosticSummary(),
  };
}
