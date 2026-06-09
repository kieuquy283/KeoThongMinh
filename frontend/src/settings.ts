import type { KeoBotSettings } from "./types";

export const DEFAULT_SETTINGS: KeoBotSettings = {
  STT_PROVIDER: "mock",
  LLM_PROVIDER: "local",
  TTS_PROVIDER: "edge_tts",
  WAKE_WORD_ENABLED: false,
  WAKE_WORD_PHRASES: ["keobot oi", "nay keobot", "hey keobot"],
  WAKE_WORD_MODE: "local_stt",
  START_WITH_WINDOWS: false,
  BACKGROUND_ASSISTANT_ENABLED: true,
  OPENAI_API_KEY: "",
  GEMINI_API_KEY: "",
  GOOGLE_API_KEY: "",
  WEATHER_PROVIDER: "none",
  OPENWEATHER_API_KEY: "",
  SEARCH_PROVIDER: "none",
  TAVILY_API_KEY: "",
  SERPAPI_API_KEY: "",
  EDGE_TTS_VOICE: "vi-VN-HoaiMyNeural",
};

export function normalizeSettings(settings: Partial<KeoBotSettings> | null | undefined): KeoBotSettings {
  const rawWakeWordPhrases = settings?.WAKE_WORD_PHRASES;
  const wakeWordPhrases = Array.isArray(rawWakeWordPhrases)
    ? rawWakeWordPhrases
        .filter((phrase): phrase is string => typeof phrase === "string" && phrase.trim().length > 0)
        .map((phrase) => phrase.trim())
    : DEFAULT_SETTINGS.WAKE_WORD_PHRASES;

  return {
    ...DEFAULT_SETTINGS,
    ...(settings ?? {}),
    TTS_PROVIDER: "edge_tts",
    WAKE_WORD_ENABLED: settings?.WAKE_WORD_ENABLED === true,
    WAKE_WORD_PHRASES: wakeWordPhrases.length > 0 ? wakeWordPhrases : DEFAULT_SETTINGS.WAKE_WORD_PHRASES,
    WAKE_WORD_MODE: "local_stt",
    START_WITH_WINDOWS: settings?.START_WITH_WINDOWS === true,
    BACKGROUND_ASSISTANT_ENABLED: settings?.BACKGROUND_ASSISTANT_ENABLED !== false,
  };
}
