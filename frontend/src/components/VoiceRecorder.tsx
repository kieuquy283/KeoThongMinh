import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";

import { sendVoiceChat } from "../api";
import { useAutoVoiceConversation } from "../hooks/useAutoVoiceConversation";
import type {
  AutoConversationStatus,
  ConversationMode,
  VoiceChatResponse,
  VoiceStatus,
} from "../types";

interface VoiceRecorderProps {
  status: VoiceStatus;
  onStatusChange: (status: VoiceStatus) => void;
  onResponse: (response: VoiceChatResponse) => void;
  onError: (message: string | null) => void;
  onStopSpeaking?: () => void;
  onModeChange?: (mode: ConversationMode) => void;
  onAutoStatusChange?: (status: AutoConversationStatus) => void;
}

export interface VoiceRecorderHandle {
  startHandsFree: () => void;
  startWakeWordTurn: () => void;
  stopHandsFree: () => void;
  cancelCurrentTurn: () => void;
}

const BUTTON_LABELS: Record<VoiceStatus, string> = {
  idle: "Bắt đầu nghe",
  recording: "Dừng nghe",
  uploading: "Đang tải lên...",
  thinking: "KeoBot đang suy nghĩ...",
  speaking: "Đang phát...",
  error: "Ghi âm lại",
};

const AUTO_STATUS_LABELS: Record<AutoConversationStatus, string> = {
  off: "Auto conversation đang tắt.",
  listening: "Đang nghe...",
  speech_detected: "Đã phát hiện giọng nói...",
  silence_wait: "Đang chờ bạn nói xong...",
  sending: "Đang gửi audio...",
  thinking: "KeoBot đang suy nghĩ...",
  speaking: "KeoBot đang trả lời...",
  error: "Có lỗi trong auto conversation.",
};

function mapAutoStatusToVoiceStatus(status: AutoConversationStatus): VoiceStatus {
  switch (status) {
    case "listening":
    case "speech_detected":
    case "silence_wait":
      return "recording";
    case "sending":
      return "uploading";
    case "thinking":
      return "thinking";
    case "speaking":
      return "speaking";
    case "error":
      return "error";
    case "off":
    default:
      return "idle";
  }
}

export const VoiceRecorder = forwardRef<VoiceRecorderHandle, VoiceRecorderProps>(function VoiceRecorder({
  status,
  onStatusChange,
  onResponse,
  onError,
  onStopSpeaking,
  onModeChange,
  onAutoStatusChange,
}: VoiceRecorderProps,
  ref,
) {
  const [mode, setMode] = useState<ConversationMode>("manual");
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const lastAutoResponseRef = useRef<VoiceChatResponse | null>(null);

  const autoConversation = useAutoVoiceConversation();

  useEffect(() => {
    if (mode !== "auto") {
      onAutoStatusChange?.("off");
      return;
    }

    onAutoStatusChange?.(autoConversation.status);
    onStatusChange(mapAutoStatusToVoiceStatus(autoConversation.status));
  }, [autoConversation.status, mode, onAutoStatusChange, onStatusChange]);

  useEffect(() => {
    if (mode !== "auto") {
      return;
    }

    onError(autoConversation.error);
  }, [autoConversation.error, mode, onError]);

  useEffect(() => {
    if (mode !== "auto" || !autoConversation.lastResponse) {
      return;
    }

    if (lastAutoResponseRef.current === autoConversation.lastResponse) {
      return;
    }

    lastAutoResponseRef.current = autoConversation.lastResponse;
    onResponse(autoConversation.lastResponse);
  }, [autoConversation.lastResponse, mode, onResponse]);

  const stopStream = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    mediaRecorderRef.current = null;
  };

  const startRecording = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      onError("Trình duyệt không hỗ trợ ghi âm. Hãy dùng bản desktop hoặc một trình duyệt hỗ trợ microphone.");
      onStatusChange("error");
      return;
    }

    try {
      onError(null);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];

      const mimeType =
        MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : MediaRecorder.isTypeSupported("audio/webm")
            ? "audio/webm"
            : "";

      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        try {
          onStatusChange("uploading");
          const audioBlob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
          await new Promise((resolve) => window.setTimeout(resolve, 100));
          onStatusChange("thinking");
          const response = await sendVoiceChat(audioBlob);
          onResponse(response);
        } catch (error) {
          const message = error instanceof Error ? error.message : "Không gửi được audio lên backend.";
          onError(message);
          onStatusChange("error");
        } finally {
          stopStream();
        }
      };

      recorder.start();
      onStatusChange("recording");
    } catch (error) {
      const message =
        error instanceof Error && (error.name === "NotAllowedError" || error.name === "SecurityError")
          ? "Không lấy được quyền microphone. Hãy cho phép microphone trong Windows hoặc trình duyệt rồi thử lại."
          : error instanceof Error
            ? error.message
            : "Không lấy được quyền microphone. Hãy kiểm tra lại quyền truy cập microphone.";
      onError(message);
      onStatusChange("error");
      stopStream();
    }
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
  };

  const handleManualClick = () => {
    if (status === "recording") {
      stopRecording();
      return;
    }

    if (status === "uploading" || status === "thinking" || status === "speaking") {
      return;
    }

    void startRecording();
  };

  const handleModeChange = (nextMode: ConversationMode) => {
    if (mode === nextMode) {
      return;
    }

    if (mode === "auto" && autoConversation.isActive) {
      autoConversation.stop();
    }

    if (mode === "manual" && mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.stop();
    }

    setMode(nextMode);
    onModeChange?.(nextMode);
    onError(null);
    onStatusChange("idle");
  };

  const startHandsFree = () => {
    if (mode === "auto") {
      if (!autoConversation.isActive) {
        void autoConversation.start();
        return;
      }

      if (autoConversation.status === "speaking" || autoConversation.status === "sending" || autoConversation.status === "thinking") {
        autoConversation.cancelCurrentTurn();
      }
      return;
    }

    if (status === "speaking") {
      onStopSpeaking?.();
      void startRecording();
      return;
    }

    if (status === "idle" || status === "error") {
      void startRecording();
    }
  };

  const startWakeWordTurn = () => {
    if (status === "speaking") {
      onStopSpeaking?.();
    }

    if (status === "recording" || status === "idle" || status === "error") {
      void startRecording();
    }
  };

  const stopHandsFree = () => {
    if (mode === "auto") {
      autoConversation.stop();
      return;
    }

    if (status === "recording") {
      stopRecording();
      return;
    }

    if (status === "speaking") {
      onStopSpeaking?.();
      onStatusChange("idle");
    }
  };

  useImperativeHandle(
    ref,
    () => ({
      startHandsFree,
      startWakeWordTurn,
      stopHandsFree,
      cancelCurrentTurn: autoConversation.cancelCurrentTurn,
    }),
    [autoConversation.cancelCurrentTurn, mode, onStopSpeaking, startHandsFree, startWakeWordTurn, stopHandsFree, status],
  );

  return (
    <div className="recorder-copy">
      <div>
        <h3>Điều khiển ghi âm</h3>
        <p>
          Manual mode hoạt động như cũ. Auto conversation sẽ tự nghe, tự phát hiện im lặng, tự gửi audio
          và tự quay lại listening sau khi KeoBot trả lời xong.
        </p>
      </div>

      <div className="audio-actions">
        <button
          className={`action-button${mode === "manual" ? "" : " secondary"}`}
          type="button"
          onClick={() => handleModeChange("manual")}
        >
          Manual
        </button>
        <button
          className={`action-button${mode === "auto" ? "" : " secondary"}`}
          type="button"
          onClick={() => handleModeChange("auto")}
        >
          Auto conversation
        </button>
      </div>

      {mode === "manual" ? (
        <>
          <p className="muted-copy">Nhấn để bắt đầu, nhấn lại để dừng. Sau đó frontend sẽ gửi audio lên backend.</p>
          <div className="audio-actions">
            <button
              className={`action-button${status === "recording" ? " danger" : ""}`}
              type="button"
              onClick={handleManualClick}
              disabled={status === "uploading" || status === "thinking" || status === "speaking"}
            >
              {BUTTON_LABELS[status]}
            </button>
            {status === "speaking" ? (
              <button className="action-button secondary" type="button" onClick={onStopSpeaking}>
                Dừng trả lời
              </button>
            ) : null}
          </div>
        </>
      ) : (
        <>
          <p className="muted-copy">{AUTO_STATUS_LABELS[autoConversation.status]}</p>
          <div className="audio-actions">
            {!autoConversation.isActive ? (
              <button className="action-button" type="button" onClick={() => void autoConversation.start()}>
                Bắt đầu trò chuyện
              </button>
            ) : (
              <button className="action-button danger" type="button" onClick={autoConversation.stop}>
                Dừng trò chuyện
              </button>
            )}
            {autoConversation.isActive && autoConversation.status === "speaking" ? (
              <button className="action-button secondary" type="button" onClick={autoConversation.cancelCurrentTurn}>
                Dừng trả lời
              </button>
            ) : null}
            {autoConversation.isActive && (autoConversation.status === "sending" || autoConversation.status === "thinking") ? (
              <button className="action-button secondary" type="button" onClick={autoConversation.cancelCurrentTurn}>
                Hủy lượt hiện tại
              </button>
            ) : null}
          </div>
        </>
      )}
    </div>
  );
});
