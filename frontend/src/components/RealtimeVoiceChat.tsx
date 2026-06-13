import { useCallback } from "react";
import { useRealtimeVoiceChat } from "../hooks/useRealtimeVoiceChat";
import { KeoBotAnimatedMascot } from "./KeoBotAnimatedMascot";

export function RealtimeVoiceChat() {
  const [state, actions] = useRealtimeVoiceChat();

  const handleInterrupt = useCallback(() => {
    actions.interrupt();
  }, [actions]);

  const status = state.isRecording
    ? "listening"
    : state.isProcessing || state.isPlaying
    ? "speaking"
    : "idle";

  return (
    <div className="realtime-voice-chat">
      <div className="mascot-area">
        <KeoBotAnimatedMascot
          status={status}
          emotion={state.emotion}
          isVisible={true}
        />
      </div>

      <div className="text-display">
        {state.botText && (
          <div className="bot-text">
            <strong>Kẹo Thông Minh:</strong> {state.botText}
          </div>
        )}
        {state.error && (
          <div className="error-text" style={{ color: "red" }}>
            {state.error}
          </div>
        )}
      </div>

      <div className="controls">
        {!state.isConnected ? (
          <button onClick={actions.start} className="btn-start">
            Bắt đầu trò chuyện (Realtime)
          </button>
        ) : (
          <>
            {state.isRecording ? (
              <button onClick={actions.stop} className="btn-stop">
                Dừng nói & Gửi
              </button>
            ) : null}
            <button onClick={handleInterrupt} className="btn-interrupt">
              Ngắt lời
            </button>
          </>
        )}
      </div>

      <div className="status-bar">
        {state.isConnected ? "🟢 Đã kết nối" : "🔴 Chưa kết nối"} |
        {state.isRecording ? " 🎤 Đang thu" : ""} |
        {state.isProcessing ? " ⚙️ Đang xử lý" : ""} |
        {state.isPlaying ? " 🔊 Đang phát" : ""}
      </div>
    </div>
  );
}
