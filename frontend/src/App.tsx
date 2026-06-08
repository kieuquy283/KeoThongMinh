import { useEffect, useRef, useState } from "react";
import { ChatPanel } from "./components/ChatPanel";
import { KeoBotPlaceholder } from "./components/KeoBotPlaceholder";
import { VoiceRecorder } from "./components/VoiceRecorder";
import type { ConversationState, VoiceChatResponse, VoiceStatus } from "./types";

const INITIAL_CONVERSATION: ConversationState = {
  userText: "",
  botText: "",
  emotion: "neutral",
  audioUrl: "",
};

const STATUS_LABELS: Record<VoiceStatus, string> = {
  idle: "Sẵn sàng",
  recording: "Đang ghi âm",
  uploading: "Đang tải lên",
  thinking: "KeoBot đang nghĩ",
  speaking: "Đang phát",
  error: "Có lỗi",
};

export default function App() {
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [conversation, setConversation] = useState<ConversationState>(INITIAL_CONVERSATION);
  const [error, setError] = useState<string | null>(null);
  const [audioBlocked, setAudioBlocked] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

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
    setStatus("speaking");
  };

  const handleRecorderError = (message: string | null) => {
    setError(message);
    if (message) {
      setStatus("error");
    }
  };

  return (
    <main className="app-shell">
      <div className="ambient ambient-a" />
      <div className="ambient ambient-b" />

      <header className="hero">
        <p className="eyebrow">KeoBot Voice MVP</p>
        <h1>Speak Vietnamese. Hear KeoBot answer.</h1>
        <p>
          Browser ghi âm giọng nói, backend nhận audio, chuyển sang text, sinh câu trả lời theo persona KeoBot,
          rồi phát lại bằng giọng Việt.
        </p>
      </header>

      <section className="grid">
        <KeoBotPlaceholder status={status} statusLabel={STATUS_LABELS[status]} />
        <ChatPanel
          userText={conversation.userText}
          botText={conversation.botText}
          emotion={conversation.emotion}
          error={error}
          audioUrl={conversation.audioUrl}
          audioBlocked={audioBlocked}
          onPlayAudio={() => void playResponseAudio()}
        />

        <div className="panel recorder-shell">
          <div className="panel-inner recorder-card">
            <VoiceRecorder
              status={status}
              onStatusChange={setStatus}
              onResponse={handleVoiceResponse}
              onError={handleRecorderError}
            />
            <div className="status-pill" aria-live="polite">
              <span className="status-dot" />
              {STATUS_LABELS[status]}
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
