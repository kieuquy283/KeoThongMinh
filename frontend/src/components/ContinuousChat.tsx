import { useContinuousChat } from "../hooks/useContinuousChat";
import { KeoBotAnimatedMascot } from "./KeoBotAnimatedMascot";

export function ContinuousChat() {
  const state = useContinuousChat();

  const status = state.isListening
    ? "listening"
    : state.isProcessing || state.isPlaying
    ? "speaking"
    : "idle";

  return (
    <div className="continuous-chat" style={{ padding: "1rem", textAlign: "center" }}>
      <div className="mascot-area" style={{ marginBottom: "1rem" }}>
        <KeoBotAnimatedMascot
          status={status}
          emotion={state.emotion}
          isVisible={true}
        />
      </div>

      <div className="conversation" style={{ minHeight: "120px", marginBottom: "1rem" }}>
        {state.userText && !state.botText && (
          <div className="user-text" style={{ color: "#666", fontStyle: "italic", marginBottom: "0.5rem" }}>
            {state.userText}
          </div>
        )}
        {state.botText && (
          <div className="bot-text" style={{ fontSize: "1.1rem", lineHeight: 1.5 }}>
            <strong style={{ color: "#e91e63" }}>Kẹo Thông Minh:</strong>{" "}
            {state.botText}
          </div>
        )}
      </div>

      <div className="status-indicator" style={{ fontSize: "0.9rem", color: "#888" }}>
        {state.isListening && (
          <span style={{ color: "#4caf50" }}>
            🎤 Đang lắng nghe bạn...
          </span>
        )}
        {state.isProcessing && (
          <span style={{ color: "#ff9800" }}>
            ⚙️ Đang xử lý...
          </span>
        )}
        {state.isPlaying && (
          <span style={{ color: "#2196f3" }}>
            🔊 Đang trả lời...
          </span>
        )}
        {!state.isListening && !state.isProcessing && !state.isPlaying && (
          <span style={{ color: "#888" }}>
            👋 Sẵn sàng lắng nghe
          </span>
        )}
      </div>

      {state.error && (
        <div className="error-text" style={{ color: "#f44336", marginTop: "1rem" }}>
          ⚠️ {state.error}
        </div>
      )}
    </div>
  );
}
