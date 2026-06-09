import { useEffect, useRef, useState } from "react";
import { ChatPanel } from "./components/ChatPanel";
import { KeoBotPlaceholder } from "./components/KeoBotPlaceholder";
import { SettingsPanel } from "./components/SettingsPanel";
import { VoiceRecorder } from "./components/VoiceRecorder";
import { DEFAULT_SETTINGS, normalizeSettings } from "./settings";
import type { ConversationState, KeoBotSettings, VoiceChatResponse, VoiceStatus } from "./types";

const INITIAL_CONVERSATION: ConversationState = {
  userText: "",
  botText: "",
  emotion: "neutral",
  audioUrl: "",
};

const STATUS_LABELS: Record<VoiceStatus, string> = {
  idle: "Sẵn sàng",
  recording: "Đang nghe...",
  uploading: "Đang tải lên...",
  thinking: "KeoBot đang suy nghĩ...",
  speaking: "KeoBot đang trả lời...",
  error: "Có lỗi",
};

const STATUS_MESSAGES: Record<VoiceStatus, string> = {
  idle: "Sẵn sàng để nghe câu hỏi tiếp theo.",
  recording: "Đang nghe...",
  uploading: "Đang tải audio lên backend...",
  thinking: "KeoBot đang suy nghĩ...",
  speaking: "KeoBot đang trả lời...",
  error: "Có lỗi. Hãy kiểm tra lại microphone hoặc backend.",
};

function getDesktopMode(): boolean {
  return typeof window !== "undefined" && Boolean(window.keobotDesktop?.isDesktop);
}

export default function App() {
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [conversation, setConversation] = useState<ConversationState>(INITIAL_CONVERSATION);
  const [error, setError] = useState<string | null>(null);
  const [audioBlocked, setAudioBlocked] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [desktopSettings, setDesktopSettings] = useState<KeoBotSettings>(DEFAULT_SETTINGS);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const isDesktopMode = getDesktopMode();

  useEffect(() => {
    if (!isDesktopMode || !window.keobotDesktop) {
      return;
    }

    let active = true;
    void window.keobotDesktop.getSettings().then((loaded) => {
      if (!active) {
        return;
      }

      setDesktopSettings(normalizeSettings(loaded));
    });

    return () => {
      active = false;
    };
  }, [isDesktopMode]);

  const playResponseAudio = async (audioUrl?: string) => {
    const url = audioUrl ?? conversation.audioUrl;
    if (!url) {
      return;
    }

    setAudioBlocked(false);
    setStatus("speaking");

    audioRef.current?.pause();
    const audio = new Audio(url);
    audioRef.current = audio;
    audio.onended = () => {
      setStatus("idle");
    };
    audio.onerror = () => {
      setAudioBlocked(true);
      setError("Không thể phát file audio phản hồi.");
      setStatus("error");
    };

    try {
      await audio.play();
    } catch {
      setAudioBlocked(true);
      setStatus("idle");
    }
  };

  useEffect(() => {
    if (!conversation.audioUrl) {
      return;
    }

    void playResponseAudio(conversation.audioUrl);
  }, [conversation.audioUrl]);

  const handleVoiceResponse = (response: VoiceChatResponse) => {
    setConversation({
      userText: response.user_text,
      botText: response.bot_text,
      emotion: response.emotion,
      audioUrl: response.audio_url,
    });
    setError(null);
    setAudioBlocked(false);
    setStatus("speaking");
  };

  const handleRecorderError = (message: string | null) => {
    setError(message);
    if (message) {
      setStatus("error");
    }
  };

  const statusMessage = error && status === "error" ? error : STATUS_MESSAGES[status];
  const providerSnapshot = desktopSettings ?? DEFAULT_SETTINGS;

  return (
    <main className="app-shell">
      <div className="ambient ambient-a" />
      <div className="ambient ambient-b" />

      <header className="hero">
        <div className="hero-topline">
          <div>
            <p className="eyebrow">KeoBot Desktop v0.3.0</p>
            <h1>Vietnamese voice assistant for the desktop.</h1>
            <p className="hero-copy">
              Ghi âm, gửi lên backend, nhận câu trả lời và phát audio phản hồi trong một UI desktop gọn, rõ, dễ dùng.
            </p>
          </div>

          <button className="action-button secondary hero-settings" type="button" onClick={() => setShowSettings((current) => !current)}>
            Cài đặt
          </button>
        </div>

        <div className="provider-strip" aria-label="Current provider configuration">
          <span>STT: {providerSnapshot.STT_PROVIDER}</span>
          <span>LLM: {providerSnapshot.LLM_PROVIDER}</span>
          <span>TTS: {providerSnapshot.TTS_PROVIDER}</span>
          <span>Mode: {isDesktopMode ? "Desktop" : "Browser"}</span>
        </div>
      </header>

      {showSettings ? (
        isDesktopMode ? (
          <SettingsPanel
            onClose={() => setShowSettings(false)}
            onSaved={(saved) => setDesktopSettings(normalizeSettings(saved))}
          />
        ) : (
          <section className="panel settings-modal">
            <div className="panel-inner">
              <div className="panel-title">
                <h2>Cài đặt</h2>
                <button className="action-button secondary" type="button" onClick={() => setShowSettings(false)}>
                  Đóng
                </button>
              </div>
              <p className="muted-copy">Settings chỉ khả dụng trong bản desktop.</p>
            </div>
          </section>
        )
      ) : null}

      <section className="grid">
        <KeoBotPlaceholder status={status} statusLabel={STATUS_LABELS[status]} statusMessage={statusMessage} />
        <ChatPanel
          userText={conversation.userText}
          botText={conversation.botText}
          emotion={conversation.emotion}
          statusMessage={statusMessage}
          error={error}
          audioUrl={conversation.audioUrl}
          audioBlocked={audioBlocked}
          onPlayAudio={() => void playResponseAudio()}
        />
      </section>

      <section className="panel recorder-shell">
        <div className="panel-inner recorder-card">
          <VoiceRecorder
            status={status}
            onStatusChange={setStatus}
            onResponse={handleVoiceResponse}
            onError={handleRecorderError}
          />
          <div className="status-pill recorder-status" aria-live="polite">
            <span className="status-dot" />
            {STATUS_LABELS[status]}
          </div>
        </div>
      </section>
    </main>
  );
}
