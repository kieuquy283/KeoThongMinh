import type { KeoBotSettings } from "./types";

export const DEFAULT_SETTINGS: KeoBotSettings = {
  STT_PROVIDER: "mock",
  LLM_PROVIDER: "local",
  TTS_PROVIDER: "edge_tts",
  WAKE_WORD_ENABLED: false,
  WAKE_WORD_PHRASES: ["kẹo thông minh ơi", "này kẹo thông minh", "hey kẹo thông minh"],
  WAKE_WORD_MODE: "local_stt",
  WAKE_WORD_ENGINE: "web_speech",
  LOCAL_WAKE_WORD_ENABLED: false,
  PICOVOICE_ACCESS_KEY: "",
  PORCUPINE_KEYWORD_PATH: "",
  LOCAL_WAKE_SENSITIVITY: 0.5,
  HOTKEY_ENABLED: true,
  HOTKEY_VALUE: "Ctrl+Shift+K",
  HANDSFREE_AUTO_RETURN_TO_WAKE_MODE: true,
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
  PRIVACY_NOTICE_SEEN: false,
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
    WAKE_WORD_ENGINE: (settings && ["local", "web_speech", "hotkey_only"].includes(settings.WAKE_WORD_ENGINE as string))
      ? (settings.WAKE_WORD_ENGINE as "local" | "web_speech" | "hotkey_only")
      : DEFAULT_SETTINGS.WAKE_WORD_ENGINE,
    LOCAL_WAKE_WORD_ENABLED: settings?.LOCAL_WAKE_WORD_ENABLED === true,
    PICOVOICE_ACCESS_KEY: typeof settings?.PICOVOICE_ACCESS_KEY === "string" ? settings.PICOVOICE_ACCESS_KEY : "",
    PORCUPINE_KEYWORD_PATH: typeof settings?.PORCUPINE_KEYWORD_PATH === "string" ? settings.PORCUPINE_KEYWORD_PATH : "",
    LOCAL_WAKE_SENSITIVITY: typeof settings?.LOCAL_WAKE_SENSITIVITY === "number" && settings.LOCAL_WAKE_SENSITIVITY >= 0 && settings.LOCAL_WAKE_SENSITIVITY <= 1
      ? settings.LOCAL_WAKE_SENSITIVITY
      : DEFAULT_SETTINGS.LOCAL_WAKE_SENSITIVITY,
    HOTKEY_ENABLED: settings?.HOTKEY_ENABLED !== false,
    HOTKEY_VALUE: typeof settings?.HOTKEY_VALUE === "string" && settings.HOTKEY_VALUE.trim()
      ? settings.HOTKEY_VALUE.trim()
      : DEFAULT_SETTINGS.HOTKEY_VALUE,
    HANDSFREE_AUTO_RETURN_TO_WAKE_MODE: settings?.HANDSFREE_AUTO_RETURN_TO_WAKE_MODE !== false,
    START_WITH_WINDOWS: settings?.START_WITH_WINDOWS === true,
    BACKGROUND_ASSISTANT_ENABLED: settings?.BACKGROUND_ASSISTANT_ENABLED !== false,
  };
}
