import { useCallback, useEffect, useRef, useState } from "react";
import { deleteReminder, fetchReminders } from "./api";
import { ChatPanel } from "./components/ChatPanel";
import { KeoBotMascot } from "./components/KeoBotMascot";
import { KnowledgePanel } from "./components/KnowledgePanel";
import { MemoryPanel } from "./components/MemoryPanel";
import { PrivacyNotice } from "./components/PrivacyNotice";
import { ReminderPanel } from "./components/ReminderPanel";
import { ReminderToast } from "./components/ReminderToast";
import { SettingsPanel } from "./components/SettingsPanel";
import { VoiceRecorder, type VoiceRecorderHandle } from "./components/VoiceRecorder";
import { useWakeWord } from "./hooks/useWakeWord";
import { DEFAULT_SETTINGS, normalizeSettings } from "./settings";
import { mapAppStateToMascot } from "./utils/keobotMascotState";
import { voiceStatusToSessionState, getSessionLabel, isIdle, canInterrupt } from "./utils/voiceSessionState";
import { play as audioPlay, stop as audioStop, isPlaying as audioIsPlaying, subscribe as audioSubscribe } from "./utils/audioPlaybackController";
import { logDiagnostic } from "./utils/diagnostics";
import type {
  AutoConversationStatus,
  ConversationMode,
  ConversationState,
  KeoBotReminder,
  KeoBotSettings,
  VoiceChatResponse,
  VoiceSessionState,
  VoiceStatus,
  WakeWordStatus,
} from "./types";

const INITIAL_CONVERSATION: ConversationState = {
  userText: "",
  botText: "",
  emotion: "neutral",
  action: null,
  audioUrl: "",
  toolUsed: "none",
  toolResult: null,
  sources: [],
  updatedAt: null,
};

const SESSION_LABELS: Record<VoiceSessionState, string> = {
  idle: "Sẵn sàng",
  wake_listening: 'Đang lắng nghe "Kẹo Thông Minh ơi"',
  command_listening: "Đang nghe bạn nói...",
  uploading: "Đang gửi âm thanh...",
  thinking: "KeoBot đang suy nghĩ...",
  speaking: "KeoBot đang trả lời...",
  interrupted: "Đã dừng câu trả lời",
  error: "Có lỗi",
};

const WAKE_WORD_LABELS: Record<WakeWordStatus, string> = {
  off: "Off",
  starting: "Starting...",
  listening_for_wake_word: 'Listening for "Kẹo Thông Minh ơi"',
  wake_word_detected: "Detected",
  handoff_to_listening: "Handing off...",
  unsupported: "Unsupported",
  unavailable: "Unavailable",
  error: "Error",
};

function getDesktopMode(): boolean {
  return typeof window !== "undefined" && Boolean(window.keobotDesktop?.isDesktop);
}

export default function App() {
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [sessionState, setSessionState] = useState<VoiceSessionState>("idle");
  const [conversation, setConversation] = useState<ConversationState>(INITIAL_CONVERSATION);
  const [error, setError] = useState<string | null>(null);
  const [audioBlocked, setAudioBlocked] = useState(false);
  const [conversationMode, setConversationMode] = useState<ConversationMode>("manual");
  const [autoStatus, setAutoStatus] = useState<AutoConversationStatus>("off");
  const [showSettings, setShowSettings] = useState(false);
  const [showMemory, setShowMemory] = useState(false);
  const [showKnowledge, setShowKnowledge] = useState(false);
  const [showReminders, setShowReminders] = useState(false);
  const [handsfreeMessage, setHandsfreeMessage] = useState<string | null>(null);
  const [desktopSettings, setDesktopSettings] = useState<KeoBotSettings>(DEFAULT_SETTINGS);
  const [privacyNotified, setPrivacyNotified] = useState(false);
  const [reminders, setReminders] = useState<KeoBotReminder[]>([]);
  const [remindersLoading, setRemindersLoading] = useState(false);
  const [remindersError, setRemindersError] = useState<string | null>(null);
  const [dueReminder, setDueReminder] = useState<KeoBotReminder | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const voiceRecorderRef = useRef<VoiceRecorderHandle | null>(null);
  const wakeWordCommandPendingRef = useRef(false);
  const isRequestInFlightRef = useRef(false);
  const isDesktopMode = getDesktopMode();
  const wakeWordEnabled = isDesktopMode && desktopSettings.BACKGROUND_ASSISTANT_ENABLED && desktopSettings.WAKE_WORD_ENABLED;
  const wakeWord = useWakeWord({
    enabled: wakeWordEnabled,
    phrases: desktopSettings.WAKE_WORD_PHRASES,
    engine: desktopSettings.WAKE_WORD_ENGINE,
  });

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

      const normalized = normalizeSettings(loaded);
      setDesktopSettings(normalized);
      setPrivacyNotified(normalized.PRIVACY_NOTICE_SEEN);
    });

    return () => {
      active = false;
    };
  }, [isDesktopMode]);

  const handlePrivacyAction = async (action: "enable_memory" | "keep_memory_off") => {
    if (!window.keobotDesktop) return;
    try {
      const updated = { ...desktopSettings, PRIVACY_NOTICE_SEEN: true };
      await window.keobotDesktop.saveSettings(updated);
      setDesktopSettings(normalizeSettings(updated));
      setPrivacyNotified(true);
    } catch {
      // Silently fail — user can still dismiss
    }
  };

  const handleOpenPrivacySettings = () => {
    setPrivacyNotified(true);
    setShowSettings(true);
  };

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

  useEffect(() => {
    if (!isDesktopMode || !window.keobotDesktop?.onWakeWordDetected) {
      return;
    }

    const unsubscribe = window.keobotDesktop.onWakeWordDetected((phrase) => {
      logDiagnostic("wake_word", "Wake word detected", { phrase, wasSpeaking: audioIsPlaying() });

      if (isRequestInFlightRef.current) {
        logDiagnostic("wake_word", "Wake word ignored — request in flight");
        return;
      }

      wakeWordCommandPendingRef.current = true;
      setHandsfreeMessage(phrase ? `Kẹo Thông Minh đã nghe bạn gọi: ${phrase}` : "Kẹo Thông Minh đã nghe bạn gọi.");

      if (audioIsPlaying()) {
        logDiagnostic("audio_playback", "Audio stopped by wake word");
        audioStop();
        setSessionState("command_listening");
        setStatus("recording");
      }
    });

    return () => {
      unsubscribe();
    };
  }, [isDesktopMode]);

  useEffect(() => {
    if (!isDesktopMode || !window.keobotDesktop?.onWakeWordStatus) {
      return;
    }

    const unsubscribe = window.keobotDesktop.onWakeWordStatus((state) => {
      if (state.status === "unsupported") {
        setHandsfreeMessage("Wake word is not supported in this environment. Use Ctrl+Shift+K instead.");
        return;
      }

      if (state.status === "error") {
        setHandsfreeMessage("Wake word error.");
      }
    });

    return () => {
      unsubscribe();
    };
  }, [isDesktopMode]);

  useEffect(() => {
    if (!isDesktopMode || !window.keobotDesktop) {
      return;
    }

    const unsubscribeStart = window.keobotDesktop.onStartListening(() => {
      logDiagnostic("voice_session", "Desktop requested start listening", { isWakeWordTurn: wakeWordCommandPendingRef.current });

      if (isRequestInFlightRef.current) {
        logDiagnostic("voice_session", "Start listening ignored — request in flight");
        return;
      }

      const isWakeWordTurn = wakeWordCommandPendingRef.current;

      if (wakeWord.enabled) {
        wakeWord.stopWakeWord();
      }

      if (audioIsPlaying()) {
        logDiagnostic("audio_playback", "Audio stopped by hotkey start");
        audioStop();
        setSessionState("command_listening");
        setStatus("recording");
      }

      if (isWakeWordTurn) {
        setHandsfreeMessage("Kẹo Thông Minh đã nghe bạn gọi.");
      } else {
        setHandsfreeMessage("Hands-free listening activated. Press Ctrl+Shift+K again or Stop to cancel.");
      }

      if (isWakeWordTurn) {
        voiceRecorderRef.current?.startWakeWordTurn();
      } else {
        voiceRecorderRef.current?.startHandsFree();
      }

      wakeWordCommandPendingRef.current = false;
    });

    const unsubscribeStop = window.keobotDesktop.onStopListening(() => {
      logDiagnostic("voice_session", "Desktop requested stop listening");
      wakeWordCommandPendingRef.current = false;
      setHandsfreeMessage(null);
      stopResponseAudio();
      voiceRecorderRef.current?.stopHandsFree();
      if (wakeWord.enabled && wakeWord.supported) {
        wakeWord.startWakeWord();
      }
    });

    const unsubscribeOpenSettings = window.keobotDesktop.onOpenSettings(() => {
      setShowSettings(true);
    });

    const unsubscribeSettingsChanged = window.keobotDesktop.onSettingsChanged((nextSettings) => {
      setDesktopSettings((current) => normalizeSettings({
        ...current,
        ...nextSettings,
      }));
    });

    return () => {
      unsubscribeStart();
      unsubscribeStop();
      unsubscribeOpenSettings();
      unsubscribeSettingsChanged();
    };
  }, [isDesktopMode, wakeWord, wakeWord.enabled, wakeWord.supported]);

  // Subscribe to audio playback state and pause/resume wake word to prevent self-triggering
  useEffect(() => {
    const unsubscribe = audioSubscribe((state) => {
      if (state === "playing") {
        if (wakeWord.enabled && wakeWord.supported) {
          wakeWord.pauseWakeWord();
        }
      } else if (state === "idle" || state === "stopped" || state === "error") {
        if (wakeWord.enabled && wakeWord.supported && desktopSettings.HANDSFREE_AUTO_RETURN_TO_WAKE_MODE && sessionState !== "interrupted" && autoStatus !== "speaking") {
          wakeWord.resumeWakeWord();
        }
      }
    });
    return () => {
      unsubscribe();
    };
  }, [wakeWord.enabled, wakeWord.supported, wakeWord.pauseWakeWord, wakeWord.resumeWakeWord, desktopSettings.HANDSFREE_AUTO_RETURN_TO_WAKE_MODE, sessionState, autoStatus]);

  // Also pause wake word when auto conversation is speaking (it uses its own Audio element)
  useEffect(() => {
    if (autoStatus === "speaking" || autoStatus === "sending" || autoStatus === "thinking") {
      if (wakeWord.enabled && wakeWord.supported) {
        wakeWord.pauseWakeWord();
      }
    } else if (autoStatus === "listening" || autoStatus === "off" || autoStatus === "speech_detected" || autoStatus === "silence_wait") {
      if (wakeWord.enabled && wakeWord.supported && desktopSettings.HANDSFREE_AUTO_RETURN_TO_WAKE_MODE && sessionState !== "interrupted") {
        wakeWord.resumeWakeWord();
      }
    }
  }, [autoStatus, wakeWord.enabled, wakeWord.supported, wakeWord.pauseWakeWord, wakeWord.resumeWakeWord, desktopSettings.HANDSFREE_AUTO_RETURN_TO_WAKE_MODE, sessionState]);

  useEffect(() => {
    if (!wakeWord.enabled) {
      if (handsfreeMessage?.includes("Wake word") || handsfreeMessage?.includes("Kẹo Thông Minh đã nghe bạn gọi")) {
        setHandsfreeMessage(null);
      }
      return;
    }

    if (wakeWord.status === "wake_word_detected") {
      wakeWordCommandPendingRef.current = true;
      setHandsfreeMessage(
        wakeWord.lastDetectedPhrase ? `Kẹo Thông Minh đã nghe bạn gọi: ${wakeWord.lastDetectedPhrase}` : "Kẹo Thông Minh đã nghe bạn gọi.",
      );
      return;
    }

    if (wakeWord.status === "listening_for_wake_word") {
      setHandsfreeMessage(
        `Wake word: đang lắng nghe "${desktopSettings.WAKE_WORD_PHRASES[0] ?? "Kẹo Thông Minh ơi"}".`,
      );
      return;
    }

    if (wakeWord.status === "unsupported") {
      setHandsfreeMessage("Wake word is not supported in this environment. Use Ctrl+Shift+K instead.");
      return;
    }

    if (wakeWord.status === "unavailable") {
      setHandsfreeMessage("Local wake word engine is not available. Use Ctrl+Shift+K or switch to Web Speech engine.");
      return;
    }

    if (wakeWord.status === "error") {
      setHandsfreeMessage(wakeWord.error ?? "Wake word error.");
    }
  }, [
    desktopSettings.WAKE_WORD_PHRASES,
    handsfreeMessage,
    wakeWord.enabled,
    wakeWord.error,
    wakeWord.lastDetectedPhrase,
    wakeWord.status,
  ]);

  const playResponseAudio = async (audioUrl?: string) => {
    const url = audioUrl ?? conversation.audioUrl;
    if (!url) {
      return;
    }

    logDiagnostic("audio_playback", "Playing response audio", { url });
    setAudioBlocked(false);
    setStatus("speaking");
    setSessionState("speaking");

    // Pause wake word detection while bot is speaking to prevent self-triggering
    if (wakeWord.enabled && wakeWord.supported) {
      wakeWord.pauseWakeWord();
    }

    try {
      await audioPlay(url);
      if (!audioIsPlaying()) {
        logDiagnostic("audio_playback", "Audio playback finished");
        setAudioBlocked(false);
        setStatus("idle");
        setSessionState((current) => (current === "interrupted" ? "interrupted" : "idle"));
        if (wakeWord.enabled && wakeWord.supported && desktopSettings.HANDSFREE_AUTO_RETURN_TO_WAKE_MODE && sessionState !== "interrupted") {
          wakeWord.resumeWakeWord();
        }
      }
    } catch {
      logDiagnostic("audio_playback", "Audio playback error");
      setAudioBlocked(true);
      setError("Không thể phát file audio phản hồi.");
      setStatus("error");
      setSessionState("error");
      // Resume wake word on error too
      if (wakeWord.enabled && wakeWord.supported && desktopSettings.HANDSFREE_AUTO_RETURN_TO_WAKE_MODE) {
        wakeWord.resumeWakeWord();
      }
    }
  };

  const stopResponseAudio = (reason: "manual" | "interrupt" = "manual") => {
    logDiagnostic("audio_playback", `Audio stopped (${reason})`);
    audioStop();
    setAudioBlocked(false);
    setSessionState("interrupted");
    setStatus("idle");
    if (reason === "interrupt") {
      wakeWordCommandPendingRef.current = true;
    }
  };

  const interruptForNewTurn = useCallback(() => {
    const wasSpeaking = audioIsPlaying();
    if (wasSpeaking) {
      logDiagnostic("audio_playback", "Audio stopped by interruptForNewTurn");
      audioStop();
    }
    if (wakeWord.enabled) {
      wakeWord.stopWakeWord();
    }
    setSessionState("command_listening");
    setStatus("recording");
    return wasSpeaking;
  }, [wakeWord]);

  useEffect(() => {
    if (conversationMode === "auto") {
      return;
    }

    if (!conversation.audioUrl) {
      return;
    }

    if (sessionState === "interrupted") {
      return;
    }

    void playResponseAudio(conversation.audioUrl);
  }, [conversation.audioUrl, conversationMode, sessionState]);

  const handleVoiceResponse = (response: VoiceChatResponse) => {
    setConversation({
      userText: response.user_text,
      botText: response.bot_text,
      emotion: response.emotion,
      action: response.action ?? null,
      audioUrl: response.audio_url,
      toolUsed: response.tool_used ?? "none",
      toolResult: response.tool_result ?? null,
      sources: response.sources ?? [],
      updatedAt: response.updated_at ?? null,
    });
    setError(null);
    setAudioBlocked(false);
    setStatus("speaking");
    setSessionState("speaking");
    isRequestInFlightRef.current = false;

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
      setSessionState("error");
      isRequestInFlightRef.current = false;
    }
  };

  const handleDeleteReminder = async (reminderId: number) => {
    await deleteReminder(reminderId);
    setReminders((current) => current.filter((item) => item.id !== reminderId));
  };

  useEffect(() => {
    setSessionState(voiceStatusToSessionState(status, wakeWord.enabled && wakeWord.supported && wakeWord.status === "listening_for_wake_word"));
  }, [status, wakeWord.enabled, wakeWord.supported, wakeWord.status]);

  const statusMessage = error && status === "error" ? error : getSessionLabel(sessionState);
  const providerSnapshot = desktopSettings ?? DEFAULT_SETTINGS;
  const mascotState = mapAppStateToMascot({
    voiceStatus: status,
    autoStatus,
    conversationMode,
    wakeWordEnabled: wakeWord.enabled,
    wakeWordStatus: wakeWord.status,
    hasError: Boolean(error),
    hasDueReminder: Boolean(dueReminder),
    latestAction: conversation.action,
    emotion: conversation.emotion,
  });

  return (
    <main className="app-shell">
      <div className="ambient ambient-a" />
      <div className="ambient ambient-b" />

      <header className="hero">
        <div className="hero-topline">
          <div>
            <p className="eyebrow">Kẹo Thông Minh Desktop v0.3.0</p>
            <h1>Trợ lý giọng nói tiếng Việt cho máy tính để bàn.</h1>
            <p className="hero-copy">
              Ghi âm, gửi lên backend, nhận câu trả lời và phát audio phản hồi trong một UI desktop gọn, rõ, dễ dùng.
            </p>
          </div>

          <div className="hero-actions">
            <button className="action-button secondary" type="button" onClick={() => setShowReminders((current) => !current)}>
              Reminders
            </button>
            <button className="action-button secondary" type="button" onClick={() => setShowKnowledge((current) => !current)}>
              Knowledge
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
          <span>Wake: {wakeWord.enabled ? "On" : "Off"}</span>
          <span>Engine: {desktopSettings.WAKE_WORD_ENGINE}</span>
          <span>Wake status: {WAKE_WORD_LABELS[wakeWord.status]}</span>
          <span>Background: {desktopSettings.BACKGROUND_ASSISTANT_ENABLED ? "On" : "Off"}</span>
          <span>Hotkey: {desktopSettings.HOTKEY_ENABLED ? desktopSettings.HOTKEY_VALUE : "Off"}</span>
          <span>Auto wake: {desktopSettings.HANDSFREE_AUTO_RETURN_TO_WAKE_MODE ? "On" : "Off"}</span>
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

      {showKnowledge ? <KnowledgePanel onClose={() => setShowKnowledge(false)} /> : null}

      {showMemory ? <MemoryPanel onClose={() => setShowMemory(false)} /> : null}

      {isDesktopMode && !privacyNotified ? (
        <PrivacyNotice
          onEnableMemory={() => void handlePrivacyAction("enable_memory")}
          onKeepMemoryOff={() => void handlePrivacyAction("keep_memory_off")}
          onOpenPrivacySettings={handleOpenPrivacySettings}
        />
      ) : null}

      {handsfreeMessage ? (
        <section className="panel handsfree-banner" aria-live="polite">
          <div className="panel-inner">
            <div className="status-pill recorder-status">
              <span className="status-dot" />
              Hands-free
            </div>
            <p>{handsfreeMessage}</p>
          </div>
        </section>
      ) : null}

      <section className="grid">
        <KeoBotMascot status={mascotState.status} emotion={mascotState.emotion} />
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
            ref={voiceRecorderRef}
            status={status}
            sessionState={sessionState}
            onStatusChange={setStatus}
            onResponse={handleVoiceResponse}
            onError={handleRecorderError}
            onStopSpeaking={() => stopResponseAudio("manual")}
            onModeChange={setConversationMode}
            onAutoStatusChange={setAutoStatus}
          />
          <div className="status-pill recorder-status" aria-live="polite">
            <span className="status-dot" />
            {SESSION_LABELS[sessionState]}
          </div>
          {sessionState === "speaking" ? (
            <div className="audio-actions" style={{ marginTop: "0.5rem" }}>
              <button className="action-button secondary" type="button" onClick={() => stopResponseAudio("manual")}>
                Dừng nói
              </button>
            </div>
          ) : null}
        </div>
      </section>

      {dueReminder ? (
        <ReminderToast reminder={dueReminder} onDismiss={() => setDueReminder(null)} />
      ) : null}
    </main>
  );
}
