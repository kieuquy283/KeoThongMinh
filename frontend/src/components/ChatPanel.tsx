import { useEffect, useState } from "react";
import type { Emotion, ToolSource, ToolUsed } from "../types";

interface ChatPanelProps {
  userText: string;
  botText: string;
  emotion: Emotion;
  statusMessage: string;
  error: string | null;
  audioUrl: string;
  toolUsed: ToolUsed;
  toolResult: Record<string, unknown> | null;
  sources: ToolSource[];
  updatedAt: string | null;
  audioBlocked: boolean;
  onPlayAudio: () => void;
}

export function ChatPanel({
  userText,
  botText,
  emotion,
  statusMessage,
  error,
  audioUrl,
  toolUsed,
  toolResult,
  sources,
  updatedAt,
  audioBlocked,
  onPlayAudio,
}: ChatPanelProps) {
  const [showAllSources, setShowAllSources] = useState(false);
  const hasConversation = Boolean(userText || botText);
  const toolMessage = typeof toolResult?.message === "string" ? toolResult.message : null;
  const toolStatus = typeof toolResult?.status === "string" ? toolResult.status : null;
  const toolUnavailable = toolResult?.is_available === false;
  const visibleSources = showAllSources ? sources : sources.slice(0, 3);

  useEffect(() => {
    setShowAllSources(false);
  }, [toolUsed, updatedAt, sources.length]);

  const formatDomain = (url: string) => {
    try {
      return new URL(url).hostname.replace(/^www\./, "");
    } catch {
      return null;
    }
  };

  return (
    <section className="panel">
      <div className="panel-inner conversation">
        <div className="panel-title">
          <h2>Hoi thoai</h2>
          <span className="status-pill">
            <span className="status-dot" />
            Emotion: {emotion}
          </span>
        </div>

        <div className="status-callout" aria-live="polite">
          <span className="status-callout-label">Trang thai</span>
          <strong>{statusMessage}</strong>
        </div>

        <article className="chat-bubble">
          <p className="chat-label">User</p>
          <p className={`chat-text ${hasConversation ? "" : "chat-empty"}`}>
            {hasConversation ? userText : "Chua co doan hoi thoai nao duoc gui len."}
          </p>
        </article>

        <article className="chat-bubble">
          <p className="chat-label">KeoBot</p>
          <p className={`chat-text ${botText ? "" : "chat-empty"}`}>
            {botText || "Cau tra loi cua KeoBot se xuat hien o day."}
          </p>
        </article>

        <div className="chat-footer">
          {error ? <div className="error-banner">{error}</div> : null}
          {toolUnavailable ? (
            <div className="tool-warning">
              <strong>Cong cu khong san sang</strong>
              <span>{toolMessage ?? "Cong cu chua san sang."}</span>
            </div>
          ) : null}

          <div className="audio-actions">
            {audioUrl ? (
              <button className="action-button secondary" type="button" onClick={onPlayAudio}>
                {audioBlocked ? "Phat cau tra loi" : "Phat lai audio"}
              </button>
            ) : null}
          </div>

          <div className="meta-row">
            <span>Audio</span>
            <strong>{audioUrl ? (audioBlocked ? "Autoplay bi chan" : "San sang phat") : "Chua co file"}</strong>
          </div>

          {toolUsed !== "none" ? (
            <div className="tool-meta">
              <div className="meta-row">
                <span>Tool</span>
                <strong>{toolUsed}</strong>
              </div>
              {toolStatus ? (
                <div className="meta-row">
                  <span>Status</span>
                  <strong>{toolStatus}</strong>
                </div>
              ) : null}
              {updatedAt ? (
                <div className="meta-row">
                  <span>Updated at</span>
                  <strong>{new Date(updatedAt).toLocaleString()}</strong>
                </div>
              ) : null}
              {sources.length > 0 ? (
                <div className="tool-sources">
                  <span className="tool-sources-label">Nguon</span>
                  <ul>
                    {visibleSources.map((source) => (
                      <li key={`${source.url}-${source.title}`}>
                        <a href={source.url} target="_blank" rel="noreferrer">
                          {source.title}
                        </a>
                        <span className="tool-source-meta">
                          {formatDomain(source.url) ? <span>{formatDomain(source.url)}</span> : null}
                          {source.published_at ? <span>{new Date(source.published_at).toLocaleString()}</span> : null}
                        </span>
                      </li>
                    ))}
                  </ul>
                  {sources.length > 3 ? (
                    <button className="action-button secondary tool-sources-toggle" type="button" onClick={() => setShowAllSources((current) => !current)}>
                      {showAllSources ? "An bot nguon" : `Hien them ${sources.length - 3} nguon`}
                    </button>
                  ) : null}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
