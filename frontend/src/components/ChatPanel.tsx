import type { Emotion } from "../types";

interface ChatPanelProps {
  userText: string;
  botText: string;
  emotion: Emotion;
  error: string | null;
  audioUrl: string;
  audioBlocked: boolean;
  onPlayAudio: () => void;
}

export function ChatPanel({ userText, botText, emotion, error, audioUrl, audioBlocked, onPlayAudio }: ChatPanelProps) {
  const hasConversation = Boolean(userText || botText);

  return (
    <section className="panel">
      <div className="panel-inner conversation">
        <div className="panel-title">
          <h2>Hội thoại</h2>
          <span className="status-pill">
            <span className="status-dot" />
            Emotion: {emotion}
          </span>
        </div>

        <article className="chat-bubble">
          <p className="chat-label">User</p>
          <p className={`chat-text ${hasConversation ? "" : "chat-empty"}`}>
            {hasConversation ? userText : "Chưa có đoạn ghi âm nào được gửi lên."}
          </p>
        </article>

        <article className="chat-bubble">
          <p className="chat-label">KeoBot</p>
          <p className={`chat-text ${botText ? "" : "chat-empty"}`}>
            {botText || "Câu trả lời của KeoBot sẽ xuất hiện ở đây."}
          </p>
        </article>

        <div className="chat-footer">
          {error ? <div className="error-banner">{error}</div> : null}

          <div className="audio-actions">
            {audioUrl ? (
              <button className="action-button secondary" type="button" onClick={onPlayAudio}>
                {audioBlocked ? "Phát audio phản hồi" : "Phát lại audio"}
              </button>
            ) : null}
          </div>

          <div className="meta-row">
            <span>Audio</span>
            <strong>{audioUrl ? (audioBlocked ? "Autoplay bị chặn" : "Sẵn sàng phát") : "Chưa có file"}</strong>
          </div>
        </div>
      </div>
    </section>
  );
}
