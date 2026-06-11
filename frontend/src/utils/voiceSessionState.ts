import type { VoiceSessionState, VoiceStatus } from "../types";

const SESSION_LABELS: Record<VoiceSessionState, string> = {
  idle: "Sẵn sàng",
  wake_listening: 'Đang lắng nghe "Kẹo Thông Minh ơi"',
  command_listening: "Đang nghe bạn nói...",
  uploading: "Đang gửi âm thanh...",
  thinking: "KeoBot đang suy nghĩ...",
  speaking: "KeoBot đang trả lời...",
  interrupted: "Đã dừng câu trả lời",
  error: "Có lỗi",
};

const SESSION_STATUS_MESSAGES: Record<VoiceSessionState, string> = {
  idle: "Sẵn sàng để nghe câu hỏi tiếp theo.",
  wake_listening: 'Lắng nghe từ khóa "Kẹo Thông Minh ơi"...',
  command_listening: "Đang nghe...",
  uploading: "Đang gửi âm thanh lên backend...",
  thinking: "KeoBot đang suy nghĩ...",
  speaking: "KeoBot đang trả lời...",
  interrupted: "Đã dừng câu trả lời. Sẵn sàng nghe lệnh mới.",
  error: "Có lỗi. Hãy kiểm tra lại microphone hoặc backend.",
};

const INTERRUPTIBLE_STATES: Set<VoiceSessionState> = new Set(["speaking", "command_listening"]);
const IDLE_STATES: Set<VoiceSessionState> = new Set(["idle", "wake_listening", "interrupted"]);

function voiceStatusToSessionState(status: VoiceStatus, wakeWordActive: boolean): VoiceSessionState {
  switch (status) {
    case "recording":
      return "command_listening";
    case "uploading":
      return "uploading";
    case "thinking":
      return "thinking";
    case "speaking":
      return "speaking";
    case "error":
      return "error";
    case "idle":
    default:
      return wakeWordActive ? "wake_listening" : "idle";
  }
}

function canInterrupt(state: VoiceSessionState): boolean {
  return INTERRUPTIBLE_STATES.has(state);
}

function isIdle(state: VoiceSessionState): boolean {
  return IDLE_STATES.has(state);
}

function getSessionLabel(state: VoiceSessionState): string {
  return SESSION_LABELS[state] ?? SESSION_LABELS.idle;
}

function getSessionStatusMessage(state: VoiceSessionState): string {
  return SESSION_STATUS_MESSAGES[state] ?? SESSION_STATUS_MESSAGES.idle;
}

export {
  SESSION_LABELS,
  SESSION_STATUS_MESSAGES,
  INTERRUPTIBLE_STATES,
  IDLE_STATES,
  voiceStatusToSessionState,
  canInterrupt,
  isIdle,
  getSessionLabel,
  getSessionStatusMessage,
};
