import { useCallback, useEffect, useRef, useState } from "react";

import { sendVoiceChat } from "../api";
import type { AutoConversationStatus, VoiceChatResponse } from "../types";
import { useSilenceDetection } from "./useSilenceDetection";
import { play as audioPlay, stop as audioStop } from "../utils/audioPlaybackController";

interface AutoVoiceConversationResult {
  status: AutoConversationStatus;
  isActive: boolean;
  start: () => Promise<void>;
  stop: () => void;
  cancelCurrentTurn: () => void;
  lastResponse: VoiceChatResponse | null;
  error: string | null;
}

function createRecorder(stream: MediaStream): MediaRecorder {
  const mimeType =
    MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : "";

  return mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
}

function generateSessionId(): string {
  const bytes = new Uint8Array(6);
  crypto.getRandomValues(bytes);
  return Array.from(bytes).map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function useAutoVoiceConversation(): AutoVoiceConversationResult {
  const [status, setStatus] = useState<AutoConversationStatus>("off");
  const [isActive, setIsActive] = useState(false);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [lastResponse, setLastResponse] = useState<VoiceChatResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isDetectingTurn, setIsDetectingTurn] = useState(false);

  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const activeRef = useRef(false);
  const shouldSendRef = useRef(false);
  const speechStateTimerRef = useRef<number | null>(null);
  const ignoreNextResponseRef = useRef(false);
  const abortControllerRef = useRef<AbortController | null>(null);
  const sessionIdRef = useRef<string | null>(null);

  const clearSpeechStateTimer = useCallback(() => {
    if (speechStateTimerRef.current !== null) {
      window.clearTimeout(speechStateTimerRef.current);
      speechStateTimerRef.current = null;
    }
  }, []);

  const cleanupStream = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    setStream(null);
  }, []);

  const cleanupRecorder = useCallback(() => {
    recorderRef.current = null;
    chunksRef.current = [];
    setIsDetectingTurn(false);
    clearSpeechStateTimer();
  }, [clearSpeechStateTimer]);

  const restartListeningRef = useRef<(() => void) | null>(null);

  const stop = useCallback(() => {
    activeRef.current = false;
    setIsActive(false);
    setStatus("off");
    clearSpeechStateTimer();
    audioStop();
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;

    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      shouldSendRef.current = false;
      recorder.stop();
      // handleRecorderStop runs async but won't reset isDetectingTurn
      // because activeRef is already false; reset here explicitly.
      setIsDetectingTurn(false);
    } else {
      cleanupRecorder();
    }

    cleanupStream();
  }, [cleanupRecorder, cleanupStream, clearSpeechStateTimer]);

  const handleRecorderStop = useCallback(async (audioType: string, chunkSnapshot: BlobPart[]) => {
    const currentStream = streamRef.current;
    const shouldSend = shouldSendRef.current;
    const wasActive = activeRef.current;

    clearSpeechStateTimer();
    chunksRef.current = [];

    if (!currentStream) {
      return;
    }

    if (!wasActive || !shouldSend) {
      // Cancel case: a new turn may have started (via startListeningTurn),
      // so don't nullify recorderRef or disable isDetectingTurn.
      return;
    }

    setIsDetectingTurn(false);

    const audioBlob = new Blob(chunkSnapshot, { type: audioType });
    if (audioBlob.size === 0) {
      setError("Không ghi được âm thanh hợp lệ.");
      setStatus("error");
      return;
    }

    try {
      setStatus("sending");
      const abortController = new AbortController();
      abortControllerRef.current = abortController;
      const response = await sendVoiceChat(audioBlob, abortController.signal, sessionIdRef.current ?? undefined);
      abortControllerRef.current = null;
      if (ignoreNextResponseRef.current) {
        ignoreNextResponseRef.current = false;
        if (activeRef.current) {
          restartListeningRef.current?.();
        }
        return;
      }

      setStatus("thinking");
      setLastResponse(response);
      setError(null);

      setStatus("speaking");
      try {
        await audioPlay(response.audio_url);
        if (activeRef.current) {
          restartListeningRef.current?.();
        } else {
          setStatus("off");
        }
      } catch {
        setError("Không thể phát audio phản hồi.");
        setStatus("error");
      }
    } catch (responseError) {
      abortControllerRef.current = null;
      if (!activeRef.current) {
        return;
      }

      if (responseError instanceof DOMException) {
        if (responseError.name === "AbortError") {
          if (activeRef.current) {
            restartListeningRef.current?.();
          }
          return;
        }
        if (responseError.name === "NotAllowedError") {
          setError("Trình duyệt chặn phát audio. Bấm 'Dừng trò chuyện' rồi thử lại.");
          if (activeRef.current) {
            restartListeningRef.current?.();
          }
          return;
        }
      }

      const message =
        responseError instanceof Error ? responseError.message : "Không gửi được audio lên backend.";
      setError(message);
      setStatus("error");
    }
  }, [clearSpeechStateTimer]);

  const startListeningTurn = useCallback(() => {
    const currentStream = streamRef.current;
    if (!activeRef.current || !currentStream) {
      return;
    }

    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      return;
    }

    try {
      shouldSendRef.current = false;
      chunksRef.current = [];
      clearSpeechStateTimer();

      const recorder = createRecorder(currentStream);
      recorderRef.current = recorder;
      setIsDetectingTurn(true);

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      recorder.onstop = () => {
        const chunkSnapshot = [...chunksRef.current];
        const audioType = recorder.mimeType || "audio/webm";
        void handleRecorderStop(audioType, chunkSnapshot);
      };

      recorder.start();
      setStatus("listening");
    } catch (recorderError) {
      const message =
        recorderError instanceof Error ? recorderError.message : "Không thể bắt đầu auto conversation.";
      setError(message);
      setStatus("error");
    }
  }, [clearSpeechStateTimer, handleRecorderStop]);

  restartListeningRef.current = startListeningTurn;

  const start = useCallback(async () => {
    if (activeRef.current) {
      return;
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Trình duyệt không hỗ trợ microphone.");
      setStatus("error");
      return;
    }

    sessionIdRef.current = generateSessionId();

    try {
      const nextStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = nextStream;
      setStream(nextStream);
      setError(null);
      setLastResponse(null);
      activeRef.current = true;
      setIsActive(true);
      startListeningTurn();
    } catch (permissionError) {
      const message =
        permissionError instanceof Error
          ? permissionError.message
          : "Không lấy được quyền microphone.";
      setError(message);
      setStatus("error");
    }
  }, [startListeningTurn]);

  const stopRecorderForSend = useCallback(() => {
    const recorder = recorderRef.current;
    if (!recorder || recorder.state === "inactive") {
      return;
    }

    shouldSendRef.current = true;
    recorder.stop();
  }, []);

  const cancelCurrentTurn = useCallback(() => {
    clearSpeechStateTimer();

    if (status === "speaking") {
      audioStop();
      if (activeRef.current) {
        startListeningTurn();
      } else {
        setStatus("off");
      }
      return;
    }

    if (status === "sending" || status === "thinking") {
      ignoreNextResponseRef.current = true;
      abortControllerRef.current?.abort();
      abortControllerRef.current = null;
      if (activeRef.current) {
        startListeningTurn();
      } else {
        setStatus("off");
      }
      return;
    }

    if (status === "listening" || status === "speech_detected" || status === "silence_wait") {
      const recorder = recorderRef.current;
      if (recorder && recorder.state !== "inactive") {
        shouldSendRef.current = false;
        recorder.stop();
      }
      if (activeRef.current) {
        startListeningTurn();
      }
    }
  }, [clearSpeechStateTimer, startListeningTurn, status]);

  useSilenceDetection({
    stream,
    enabled: isActive && isDetectingTurn,
    onSpeechStart: () => {
      audioStop();
      setStatus("speech_detected");
      clearSpeechStateTimer();
      speechStateTimerRef.current = window.setTimeout(() => {
        if (activeRef.current) {
          setStatus("silence_wait");
        }
      }, 250);
    },
    onSilence: () => {
      clearSpeechStateTimer();
      stopRecorderForSend();
    },
  });

  useEffect(() => {
    return () => {
      stop();
    };
  }, [stop]);

  return {
    status,
    isActive,
    start,
    stop,
    cancelCurrentTurn,
    lastResponse,
    error,
  };
}
