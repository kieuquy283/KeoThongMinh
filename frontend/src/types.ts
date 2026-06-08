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
