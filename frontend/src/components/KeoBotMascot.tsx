import React from 'react';

export interface KeoBotMascotProps {
  status: "idle" | "listening" | "thinking" | "speaking" | "error";
  emotion?: "neutral" | "happy" | "thinking" | "sad" | "surprised" | "angry" | "wink";
}

const BUBBLE_MESSAGES: Record<KeoBotMascotProps["status"], string> = {
  idle: "KeoBot đang chờ",
  listening: "Đang nghe bạn nói...",
  thinking: "KeoBot đang suy nghĩ...",
  speaking: "KeoBot đang trả lời...",
  error: "Có lỗi xảy ra",
};

export function KeoBotMascot({ status, emotion = "neutral" }: KeoBotMascotProps) {
  return (
    <section className="panel keobot-card">
      <div className="panel-inner keobot-panel">
        
        <div style={{ textAlign: 'center', marginBottom: '1.5rem', display: 'flex', justifyContent: 'center' }}>
          <div className="status-bubble" style={{
            background: 'var(--surface-color, #fff)',
            border: '1px solid var(--border-color, #e5e5e5)',
            padding: '12px 24px',
            borderRadius: '24px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.05)',
            fontWeight: 500,
            color: 'var(--text-color, #111)',
            position: 'relative'
          }}>
            {BUBBLE_MESSAGES[status]}
          </div>
        </div>

        <div className="keobot-art" style={{ display: 'flex', justifyContent: 'center' }}>
          <img
            className="keobot-image"
            src="/keobot/keobot_mascot.png"
            alt={`KeoBot mascot - ${emotion}`}
            style={{ 
              width: '100%', 
              maxWidth: '300px',
              height: 'auto', 
              maxHeight: '400px', 
              objectFit: 'contain',
              transition: 'all 0.3s ease'
            }}
          />
        </div>

        <div className="keobot-copy">
          <div>
            <p className="section-kicker">Desktop companion</p>
            <h2 className="keobot-name">KeoBot</h2>
            <p className="keobot-tagline">Vietnamese Virtual AI Assistant</p>
          </div>

          <div className="keobot-status-card">
            <span className="keobot-status-label" style={{ textTransform: 'capitalize' }}>{status}</span>
            <strong>Trạng thái</strong>
            <p>{BUBBLE_MESSAGES[status]}</p>
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
