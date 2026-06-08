import { useRef } from "react";
import { sendVoiceChat } from "../api";
import type { VoiceChatResponse, VoiceStatus } from "../types";

interface VoiceRecorderProps {
  status: VoiceStatus;
  onStatusChange: (status: VoiceStatus) => void;
  onResponse: (response: VoiceChatResponse) => void;
  onError: (message: string | null) => void;
}

const BUTTON_LABELS: Record<VoiceStatus, string> = {
  idle: "Bắt đầu ghi âm",
  recording: "Dừng ghi âm",
  uploading: "Đang tải lên...",
  thinking: "KeoBot đang nghĩ...",
  speaking: "Đang phát...",
  error: "Ghi âm lại",
};

export function VoiceRecorder({ status, onStatusChange, onResponse, onError }: VoiceRecorderProps) {
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);

  const stopStream = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    mediaRecorderRef.current = null;
  };

  const startRecording = async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      onError("Trình duyệt không hỗ trợ ghi âm.");
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
      const message = error instanceof Error ? error.message : "Không lấy được quyền microphone.";
      onError(message);
      onStatusChange("error");
      stopStream();
    }
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
  };

  const handleClick = () => {
    if (status === "recording") {
      stopRecording();
      return;
    }

    if (status === "uploading" || status === "thinking" || status === "speaking") {
      return;
    }

    void startRecording();
  };

  return (
    <div className="recorder-copy">
      <div>
        <h3>Điều khiển ghi âm</h3>
        <p>Nhấn để bắt đầu, nhấn lại để dừng. Sau đó frontend sẽ gửi audio lên backend.</p>
      </div>

      <button
        className={`action-button${status === "recording" ? " danger" : ""}`}
        type="button"
        onClick={handleClick}
        disabled={status === "uploading" || status === "thinking" || status === "speaking"}
      >
        {BUTTON_LABELS[status]}
      </button>
    </div>
  );
}
