interface KeoBotPlaceholderProps {
  status: string;
  statusLabel: string;
}

export function KeoBotPlaceholder({ status, statusLabel }: KeoBotPlaceholderProps) {
  return (
    <section className="panel keobot-card">
      <div className="panel-inner">
        <div className="keobot-avatar">KB</div>
        <h2 className="keobot-name">KeoBot</h2>
        <p className="keobot-tagline">Vietnamese Virtual AI Assistant</p>

        <div className="keobot-meta">
          <div className="meta-row">
            <span>Status</span>
            <strong>{statusLabel}</strong>
          </div>
          <div className="meta-row">
            <span>Mode</span>
            <strong>{status}</strong>
          </div>
          <div className="meta-row">
            <span>Phase</span>
            <strong>Voice pipeline</strong>
          </div>
        </div>
      </div>
    </section>
  );
}
