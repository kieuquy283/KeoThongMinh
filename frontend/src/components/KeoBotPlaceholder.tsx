interface KeoBotPlaceholderProps {
  status: string;
  statusLabel: string;
  statusMessage: string;
}

const MASCOT_LABELS: Record<string, string> = {
  idle: "Idle",
  recording: "Listening",
  uploading: "Thinking",
  thinking: "Thinking",
  speaking: "Speaking",
  error: "Error",
};

export function KeoBotPlaceholder({ status, statusLabel, statusMessage }: KeoBotPlaceholderProps) {
  return (
    <section className="panel keobot-card">
      <div className="panel-inner keobot-panel">
        <div className="keobot-art">
          <img
            className="keobot-image"
            src="/keobot/keobot_mascot.png"
            alt="KeoBot mascot"
          />
        </div>

        <div className="keobot-copy">
          <div>
            <p className="section-kicker">Desktop companion</p>
            <h2 className="keobot-name">KeoBot</h2>
            <p className="keobot-tagline">Vietnamese Virtual AI Assistant</p>
          </div>

          <div className="keobot-status-card">
            <span className="keobot-status-label">{MASCOT_LABELS[status] ?? "Idle"}</span>
            <strong>{statusLabel}</strong>
            <p>{statusMessage}</p>
          </div>

          <div className="keobot-meta">
            <div className="meta-row">
              <span>Mode</span>
              <strong>Desktop</strong>
            </div>
            <div className="meta-row">
              <span>Pipeline</span>
              <strong>Voice assistant</strong>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
