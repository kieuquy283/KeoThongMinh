import { useEffect, useRef, useState } from "react";
import { deleteReminder, fetchReminders } from "./api";
import { ChatPanel } from "./components/ChatPanel";
import { KeoBotMascot } from "./components/KeoBotMascot";
import { MemoryPanel } from "./components/MemoryPanel";
import { ReminderPanel } from "./components/ReminderPanel";
import { ReminderToast } from "./components/ReminderToast";
import { SettingsPanel } from "./components/SettingsPanel";
import { VoiceRecorder } from "./components/VoiceRecorder";
import { DEFAULT_SETTINGS, normalizeSettings } from "./settings";
import type {
  AutoConversationStatus,
  ConversationMode,
  ConversationState,
  KeoBotReminder,
  KeoBotSettings,
  VoiceChatResponse,
  VoiceStatus,
} from "./types";

const INITIAL_CONVERSATION: ConversationState = {
  userText: "",
  botText: "",
  emotion: "neutral",
  audioUrl: "",
  toolUsed: "none",
  toolResult: null,
  sources: [],
  updatedAt: null,
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
  const [conversationMode, setConversationMode] = useState<ConversationMode>("manual");
  const [autoStatus, setAutoStatus] = useState<AutoConversationStatus>("off");
  const [showSettings, setShowSettings] = useState(false);
  const [showMemory, setShowMemory] = useState(false);
  const [showReminders, setShowReminders] = useState(false);
  const [desktopSettings, setDesktopSettings] = useState<KeoBotSettings>(DEFAULT_SETTINGS);
  const [reminders, setReminders] = useState<KeoBotReminder[]>([]);
  const [remindersLoading, setRemindersLoading] = useState(false);
  const [remindersError, setRemindersError] = useState<string | null>(null);
  const [dueReminder, setDueReminder] = useState<KeoBotReminder | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const isDesktopMode = getDesktopMode();

  const loadReminders = async () => {
    setRemindersLoading(true);
    setRemindersError(null);
    try {
      const items = await fetchReminders();
      setReminders(items);
    } catch (loadError) {
      setRemindersError(loadError instanceof Error ? loadError.message : "Không thể tải reminders.");
    } finally {
      setRemindersLoading(false);
    }
  };

  useEffect(() => {
    void loadReminders();
  }, []);

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

  useEffect(() => {
    if (!isDesktopMode || !window.keobotDesktop?.onReminderDue) {
      return;
    }

    const unsubscribe = window.keobotDesktop.onReminderDue((reminder) => {
      setDueReminder(reminder);
      void loadReminders();
    });

    return () => {
      unsubscribe();
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

  const stopResponseAudio = () => {
    audioRef.current?.pause();
    if (audioRef.current) {
      audioRef.current.currentTime = 0;
    }
    setStatus("idle");
  };

  useEffect(() => {
    if (conversationMode === "auto") {
      return;
    }

    if (!conversation.audioUrl) {
      return;
    }

    void playResponseAudio(conversation.audioUrl);
  }, [conversation.audioUrl, conversationMode]);

  const handleVoiceResponse = (response: VoiceChatResponse) => {
    setConversation({
      userText: response.user_text,
      botText: response.bot_text,
      emotion: response.emotion,
      audioUrl: response.audio_url,
      toolUsed: response.tool_used ?? "none",
      toolResult: response.tool_result ?? null,
      sources: response.sources ?? [],
      updatedAt: response.updated_at ?? null,
    });
    setError(null);
    setAudioBlocked(false);
    setStatus("speaking");

    if (response.action === "reminder_created" && response.reminder) {
      const createdReminder = response.reminder;
      setReminders((current) => {
        const next = current.filter((item) => item.id !== createdReminder.id);
        return [...next, createdReminder].sort((left, right) => left.remind_at.localeCompare(right.remind_at));
      });
    }
  };

  const handleRecorderError = (message: string | null) => {
    setError(message);
    if (message) {
      setStatus("error");
    }
  };

  const handleDeleteReminder = async (reminderId: number) => {
    await deleteReminder(reminderId);
    setReminders((current) => current.filter((item) => item.id !== reminderId));
  };

  const statusMessage = error && status === "error" ? error : STATUS_MESSAGES[status];
  const providerSnapshot = desktopSettings ?? DEFAULT_SETTINGS;

  let mascotStatus: "idle" | "listening" | "thinking" | "speaking" | "error" = "idle";
  if (conversationMode === "auto") {
    if (autoStatus === "listening" || autoStatus === "speech_detected" || autoStatus === "silence_wait") {
      mascotStatus = "listening";
    } else if (autoStatus === "sending" || autoStatus === "thinking") {
      mascotStatus = "thinking";
    } else if (autoStatus === "speaking") {
      mascotStatus = "speaking";
    } else if (autoStatus === "error") {
      mascotStatus = "error";
    }
  } else if (status === "recording") {
    mascotStatus = "listening";
  } else if (status === "uploading" || status === "thinking") {
    mascotStatus = "thinking";
  } else if (status === "speaking") {
    mascotStatus = "speaking";
  } else if (status === "error") {
    mascotStatus = "error";
  }

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

          <div className="hero-actions">
            <button className="action-button secondary" type="button" onClick={() => setShowReminders((current) => !current)}>
              Reminders
            </button>
            <button className="action-button secondary" type="button" onClick={() => setShowMemory((current) => !current)}>
              Memory
            </button>
            <button className="action-button secondary hero-settings" type="button" onClick={() => setShowSettings((current) => !current)}>
              Cài đặt
            </button>
          </div>
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

      {showReminders ? (
        <ReminderPanel
          reminders={reminders}
          loading={remindersLoading}
          error={remindersError}
          onClose={() => setShowReminders(false)}
          onRefresh={() => void loadReminders()}
          onDelete={(reminderId) => void handleDeleteReminder(reminderId)}
        />
      ) : null}

      {showMemory ? <MemoryPanel onClose={() => setShowMemory(false)} /> : null}

      <section className="grid">
        <KeoBotMascot status={mascotStatus} emotion={conversation.emotion} />
        <ChatPanel
          userText={conversation.userText}
          botText={conversation.botText}
          emotion={conversation.emotion}
          statusMessage={statusMessage}
          error={error}
          audioUrl={conversation.audioUrl}
          toolUsed={conversation.toolUsed}
          toolResult={conversation.toolResult}
          sources={conversation.sources}
          updatedAt={conversation.updatedAt}
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
            onStopSpeaking={stopResponseAudio}
            onModeChange={setConversationMode}
            onAutoStatusChange={setAutoStatus}
          />
          <div className="status-pill recorder-status" aria-live="polite">
            <span className="status-dot" />
            {STATUS_LABELS[status]}
          </div>
        </div>
      </section>

      {dueReminder ? (
        <ReminderToast reminder={dueReminder} onDismiss={() => setDueReminder(null)} />
      ) : null}
    </main>
  );
}
