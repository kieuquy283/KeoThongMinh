import type { KeoBotSettings } from "./types";

export const DEFAULT_SETTINGS: KeoBotSettings = {
  STT_PROVIDER: "mock",
  LLM_PROVIDER: "local",
  TTS_PROVIDER: "edge_tts",
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
  return {
    ...DEFAULT_SETTINGS,
    ...(settings ?? {}),
    TTS_PROVIDER: "edge_tts",
  };
}
