import type {
  AutoConversationStatus,
  ChatAction,
  Emotion,
  VoiceStatus,
  WakeWordStatus,
} from "../types";

export type MascotStatus =
  | "idle"
  | "listening"
  | "thinking"
  | "speaking"
  | "error"
  | "reminder"
  | "loading";

export type MascotEmotion =
  | Emotion
  | "celebrate"
  | "sleepy"
  | "calm"
  | "confused";

export type MascotVisual =
  | "idle"
  | "listening"
  | "thinking"
  | "thinking_alt"
  | "speaking_1"
  | "speaking_2"
  | "speaking_3"
  | "happy"
  | "error"
  | "reminder"
  | "blink_1"
  | "blink_2"
  | "wave"
  | "celebrate"
  | "loading"
  | "goodbye"
  | "confused"
  | "sad"
  | "sleepy"
  | "surprised"
  | "processing"
  | "calm";

const ASSET_PATHS: Record<MascotVisual, string> = {
  idle: "/keobot/keobot_idle.png",
  listening: "/keobot/keobot_listening.png",
  thinking: "/keobot/keobot_thinking.png",
  thinking_alt: "/keobot/keobot_thinking_alt.png",
  speaking_1: "/keobot/keobot_speaking_1.png",
  speaking_2: "/keobot/keobot_speaking_2.png",
  speaking_3: "/keobot/keobot_speaking_3.png",
  happy: "/keobot/keobot_happy.png",
  error: "/keobot/keobot_error.png",
  reminder: "/keobot/keobot_reminder.png",
  blink_1: "/keobot/keobot_blink_1.png",
  blink_2: "/keobot/keobot_blink_2.png",
  wave: "/keobot/keobot_wave.png",
  celebrate: "/keobot/keobot_celebrate.png",
  loading: "/keobot/keobot_loading.png",
  goodbye: "/keobot/keobot_goodbye.png",
  confused: "/keobot/keobot_confused.png",
  sad: "/keobot/keobot_sad.png",
  sleepy: "/keobot/keobot_sleepy.png",
  surprised: "/keobot/keobot_surprised_alt.png",
  processing: "/keobot/keobot_processing.png",
  calm: "/keobot/keobot_calm.png",
};

const VISUAL_FALLBACKS: Record<MascotVisual, MascotVisual[]> = {
  idle: ["calm", "happy"],
  listening: ["idle"],
  thinking: ["thinking_alt", "processing", "idle"],
  thinking_alt: ["thinking", "processing", "idle"],
  speaking_1: ["idle"],
  speaking_2: ["speaking_1", "idle"],
  speaking_3: ["speaking_2", "speaking_1", "idle"],
  happy: ["idle"],
  error: ["sad", "idle"],
  reminder: ["happy", "idle"],
  blink_1: ["idle"],
  blink_2: ["blink_1", "idle"],
  wave: ["happy", "idle"],
  celebrate: ["happy", "idle"],
  loading: ["processing", "thinking", "idle"],
  goodbye: ["wave", "idle"],
  confused: ["thinking", "idle"],
  sad: ["error", "idle"],
  sleepy: ["calm", "idle"],
  surprised: ["happy", "idle"],
  processing: ["loading", "thinking", "idle"],
  calm: ["idle"],
};

export const MASCOT_STATUS_LABELS: Record<MascotStatus, string> = {
  idle: "KeoBot đang chờ",
  listening: "Đang nghe bạn nói...",
  thinking: "KeoBot đang suy nghĩ...",
  speaking: "KeoBot đang trả lời...",
  error: "KeoBot gặp chút vấn đề",
  reminder: "KeoBot đang nhắc bạn...",
  loading: "KeoBot đang xử lý...",
};

export function getMascotAssetPath(visual: MascotVisual): string {
  return ASSET_PATHS[visual];
}

export function getMascotFallbackChain(visual: MascotVisual): string[] {
  const chain = [visual, ...VISUAL_FALLBACKS[visual]];
  return chain.map((key) => ASSET_PATHS[key]);
}

export function getEmotionVisual(emotion?: MascotEmotion): MascotVisual | null {
  switch (emotion) {
    case "happy":
      return "happy";
    case "thinking":
      return "thinking_alt";
    case "sad":
      return "sad";
    case "surprised":
      return "surprised";
    case "wink":
      return "wave";
    case "celebrate":
      return "celebrate";
    case "sleepy":
      return "sleepy";
    case "calm":
      return "calm";
    case "confused":
      return "confused";
    case "neutral":
    case "angry":
    default:
      return null;
  }
}

export function getBaseVisualForStatus(status: MascotStatus, emotion?: MascotEmotion): MascotVisual {
  if (status === "speaking") {
    return "speaking_1";
  }

  if (status === "listening") {
    return "listening";
  }

  if (status === "thinking") {
    return emotion === "thinking" || emotion === "confused" ? "thinking_alt" : "thinking";
  }

  if (status === "loading") {
    return emotion === "thinking" ? "processing" : "loading";
  }

  if (status === "error") {
    return emotion === "sad" ? "sad" : "error";
  }

  if (status === "reminder") {
    return "reminder";
  }

  if (status === "idle") {
    const emotionalVisual = getEmotionVisual(emotion);
    if (emotionalVisual === "happy" || emotionalVisual === "celebrate" || emotionalVisual === "sleepy" || emotionalVisual === "calm" || emotionalVisual === "confused" || emotionalVisual === "surprised" || emotionalVisual === "wave") {
      return emotionalVisual;
    }
    return emotion === "calm" || emotion === "neutral" ? "calm" : "idle";
  }

  return "idle";
}

export function shouldBlink(status: MascotStatus, emotion?: MascotEmotion): boolean {
  return status === "idle" && ["neutral", "happy", "calm", undefined].includes(emotion);
}

export function mapAppStateToMascot(input: {
  voiceStatus: VoiceStatus;
  autoStatus: AutoConversationStatus;
  conversationMode: "manual" | "auto";
  wakeWordEnabled: boolean;
  wakeWordStatus: WakeWordStatus;
  hasError: boolean;
  hasDueReminder: boolean;
  latestAction?: ChatAction | null;
  emotion?: MascotEmotion;
}): {
  status: MascotStatus;
  emotion: MascotEmotion;
} {
  const {
    voiceStatus,
    autoStatus,
    conversationMode,
    wakeWordEnabled,
    wakeWordStatus,
    hasError,
    hasDueReminder,
    latestAction,
    emotion,
  } = input;

  if (hasError || (wakeWordEnabled && (wakeWordStatus === "error" || wakeWordStatus === "unavailable"))) {
    return { status: "error", emotion: emotion === "sad" ? "sad" : "confused" };
  }

  if (hasDueReminder || latestAction === "reminder_created") {
    return { status: "reminder", emotion: "happy" };
  }

  if (wakeWordEnabled && ["starting", "listening_for_wake_word"].includes(wakeWordStatus)) {
    return { status: "idle", emotion: "calm" };
  }

  if (wakeWordEnabled && ["wake_word_detected", "handoff_to_listening"].includes(wakeWordStatus)) {
    return { status: "listening", emotion: "calm" };
  }

  if (conversationMode === "auto") {
    switch (autoStatus) {
      case "listening":
      case "speech_detected":
      case "silence_wait":
        return { status: "listening", emotion: "calm" };
      case "sending":
        return { status: "loading", emotion: "thinking" };
      case "thinking":
        return { status: "thinking", emotion: emotion ?? "thinking" };
      case "speaking":
        return { status: "speaking", emotion: emotion === "celebrate" ? "happy" : emotion ?? "happy" };
      case "error":
        return { status: "error", emotion: "sad" };
      case "off":
      default:
        break;
    }
  }

  switch (voiceStatus) {
    case "recording":
      return { status: "listening", emotion: "calm" };
    case "uploading":
      return { status: "loading", emotion: "thinking" };
    case "thinking":
      return { status: "thinking", emotion: emotion ?? "thinking" };
    case "speaking":
      return { status: "speaking", emotion: emotion === "neutral" ? "happy" : emotion ?? "happy" };
    case "error":
      return { status: "error", emotion: "sad" };
    case "idle":
    default:
      return {
        status: "idle",
        emotion: latestAction === "memory_updated" ? "happy" : emotion ?? "calm",
      };
  }
}
