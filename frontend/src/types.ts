export type Emotion =
  | "neutral"
  | "happy"
  | "thinking"
  | "sad"
  | "surprised"
  | "angry"
  | "wink"
  | "celebrate"
  | "sleepy"
  | "calm"
  | "confused";

export type ChatAction = "reminder_created" | "tool_response" | "memory_updated" | "memory_deleted";
export type ToolUsed = "weather" | "time" | "currency" | "news_search" | "general_search" | "none";
export type ConversationMode = "manual" | "auto";

export type AutoConversationStatus =
  | "off"
  | "listening"
  | "speech_detected"
  | "silence_wait"
  | "sending"
  | "thinking"
  | "speaking"
  | "error";

export interface KeoBotReminder {
  id: number;
  title: string;
  remind_at: string;
  status: "pending" | "triggered";
  created_at: string;
  triggered_at: string | null;
}

export interface ToolSource {
  title: string;
  url: string;
  published_at: string | null;
}

export interface MemoryItem {
  key:
    | "user_name"
    | "preferred_form_of_address"
    | "default_city"
    | "default_timezone"
    | "default_currency"
    | "preferred_tts_voice"
    | "answer_style";
  value: string;
  category: string;
  source: string;
  confidence: number;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
  last_used_at: string | null;
}

export interface ToolProviderStatus {
  provider: string;
  configured: boolean;
  live?: boolean | null;
  status?: "ok" | "not_configured" | "invalid_key" | "network_error" | "rate_limited" | "unknown_error";
  message?: string;
  last_checked_at?: string | null;
}

export interface ToolsStatusResponse {
  weather: ToolProviderStatus;
  search: ToolProviderStatus;
  currency: ToolProviderStatus;
}

export interface ToolTestRequest {
  tool: "weather" | "search" | "currency" | "time";
  sample_query: string;
}

export interface ToolTestResponse {
  tool: "weather" | "search" | "currency" | "time";
  status: "ok" | "not_configured" | "invalid_key" | "network_error" | "rate_limited" | "unknown_error";
  message: string;
  sample_result: Record<string, unknown> | null;
  checked_at: string;
}

export interface MemoryUpsertRequest {
  key: MemoryItem["key"];
  value: string;
  category?: string;
}

export interface MemoryUpdateRequest {
  value?: string;
  category?: string;
  is_enabled?: boolean;
}

export interface MemoryContextResponse {
  context: Record<string, string>;
}

export interface VoiceChatResponse {
  user_text: string;
  bot_text: string;
  audio_url: string;
  emotion: Emotion;
  action?: ChatAction | null;
  reminder?: KeoBotReminder | null;
  tool_used?: ToolUsed;
  tool_result?: Record<string, unknown> | null;
  sources?: ToolSource[];
  updated_at?: string | null;
}

export type VoiceStatus = "idle" | "recording" | "uploading" | "thinking" | "speaking" | "error";

export type VoiceSessionState =
  | "idle"
  | "wake_listening"
  | "command_listening"
  | "uploading"
  | "thinking"
  | "speaking"
  | "interrupted"
  | "error";

export interface ConversationState {
  userText: string;
  botText: string;
  emotion: Emotion;
  action: ChatAction | null;
  audioUrl: string;
  toolUsed: ToolUsed;
  toolResult: Record<string, unknown> | null;
  sources: ToolSource[];
  updatedAt: string | null;
}

export interface KeoBotSettings {
  STT_PROVIDER: "mock" | "openai";
  LLM_PROVIDER: "local" | "openai" | "gemini";
  TTS_PROVIDER: "edge_tts";
  WAKE_WORD_ENABLED: boolean;
  WAKE_WORD_PHRASES: string[];
  WAKE_WORD_MODE: "local_stt";
  WAKE_WORD_ENGINE: "local" | "web_speech" | "hotkey_only";
  LOCAL_WAKE_WORD_ENABLED: boolean;
  PICOVOICE_ACCESS_KEY: string;
  PORCUPINE_KEYWORD_PATH: string;
  LOCAL_WAKE_SENSITIVITY: number;
  HOTKEY_ENABLED: boolean;
  HOTKEY_VALUE: string;
  HANDSFREE_AUTO_RETURN_TO_WAKE_MODE: boolean;
  START_WITH_WINDOWS: boolean;
  BACKGROUND_ASSISTANT_ENABLED: boolean;
  OPENAI_API_KEY: string;
  GEMINI_API_KEY: string;
  GOOGLE_API_KEY: string;
  WEATHER_PROVIDER: "none" | "openweathermap";
  OPENWEATHER_API_KEY: string;
  SEARCH_PROVIDER: "none" | "tavily" | "serpapi";
  TAVILY_API_KEY: string;
  SERPAPI_API_KEY: string;
  EDGE_TTS_VOICE: string;
  PRIVACY_NOTICE_SEEN: boolean;
}

export type WakeWordStatus =
  | "off"
  | "starting"
  | "listening_for_wake_word"
  | "wake_word_detected"
  | "handoff_to_listening"
  | "unsupported"
  | "unavailable"
  | "error";

export interface WakeWordState {
  status: WakeWordStatus;
  phrase?: string | null;
}
