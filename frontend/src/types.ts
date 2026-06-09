export type Emotion =
  | "neutral"
  | "happy"
  | "thinking"
  | "sad"
  | "surprised"
  | "angry"
  | "wink";

export interface VoiceChatResponse {
  user_text: string;
  bot_text: string;
  audio_url: string;
  emotion: Emotion;
}

export type VoiceStatus = "idle" | "recording" | "uploading" | "thinking" | "speaking" | "error";

export interface ConversationState {
  userText: string;
  botText: string;
  emotion: Emotion;
  audioUrl: string;
}

export interface KeoBotSettings {
  STT_PROVIDER: "mock" | "openai";
  LLM_PROVIDER: "local" | "openai" | "gemini";
  TTS_PROVIDER: "edge_tts";
  OPENAI_API_KEY: string;
  GEMINI_API_KEY: string;
  GOOGLE_API_KEY: string;
  EDGE_TTS_VOICE: string;
}
