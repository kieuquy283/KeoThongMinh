import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { WakeWordState, WakeWordStatus } from "../types";

interface UseWakeWordOptions {
  enabled: boolean;
  phrases?: string[];
  language?: string;
}

interface UseWakeWordResult {
  enabled: boolean;
  supported: boolean;
  status: WakeWordStatus;
  lastDetectedPhrase: string | null;
  startWakeWord: () => void;
  stopWakeWord: () => void;
  error: string | null;
}

interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onstart: null | (() => void);
  onresult: null | ((event: { resultIndex: number; results: Array<{ 0: { transcript?: string } }> }) => void);
  onerror: null | ((event: { error: string }) => void);
  onend: null | (() => void);
}

type SpeechRecognitionConstructorLike = new () => SpeechRecognitionLike;

function getSpeechRecognitionConstructor(): SpeechRecognitionConstructorLike | null {
  if (typeof window === "undefined") {
    return null;
  }

  const browserWindow = window as Window & {
    SpeechRecognition?: SpeechRecognitionConstructorLike;
    webkitSpeechRecognition?: SpeechRecognitionConstructorLike;
  };

  return browserWindow.SpeechRecognition ?? browserWindow.webkitSpeechRecognition ?? null;
}

function normalizeText(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function findMatchedPhrase(transcript: string, phrases: string[]): string | null {
  const normalizedTranscript = normalizeText(transcript);
  for (const phrase of phrases) {
    if (normalizedTranscript.includes(normalizeText(phrase))) {
      return phrase;
    }
  }

  return null;
}

export function useWakeWord({ enabled, phrases = ["keobot oi", "nay keobot", "hey keobot"], language = "vi-VN" }: UseWakeWordOptions): UseWakeWordResult {
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const activeRef = useRef(false);
  const stopRequestedRef = useRef(false);
  const phrasesRef = useRef(phrases);
  const [supported, setSupported] = useState(Boolean(getSpeechRecognitionConstructor()));
  const [status, setStatus] = useState<WakeWordStatus>(enabled ? "starting" : "off");
  const [lastDetectedPhrase, setLastDetectedPhrase] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const notifyWakeWordStatus = useCallback((payload: WakeWordState) => {
    if (typeof window === "undefined" || !window.keobotDesktop?.notifyWakeWordStatus) {
      return;
    }

    void window.keobotDesktop.notifyWakeWordStatus(payload);
  }, []);

  const stopWakeWord = useCallback(() => {
    stopRequestedRef.current = true;
    activeRef.current = false;

    const recognition = recognitionRef.current;
    recognitionRef.current = null;

    try {
      recognition?.abort();
    } catch {
      try {
        recognition?.stop();
      } catch {
        // Ignore cleanup errors.
      }
    }

    setStatus(enabled ? "off" : "off");
    notifyWakeWordStatus({ status: "off", phrase: null });
  }, [enabled, notifyWakeWordStatus]);

  const startWakeWord = useCallback(() => {
    const Recognition = getSpeechRecognitionConstructor();
    if (!Recognition) {
      setSupported(false);
      setError("Wake word is not supported in this environment. Use Ctrl+Shift+K instead.");
      setStatus("unsupported");
      notifyWakeWordStatus({ status: "unsupported", phrase: null });
      return;
    }

    if (!enabled) {
      stopWakeWord();
      return;
    }

    if (activeRef.current) {
      return;
    }

    setSupported(true);
    setError(null);
    setLastDetectedPhrase(null);
    setStatus("starting");
    notifyWakeWordStatus({ status: "starting", phrase: null });

    try {
      const recognition = new Recognition();
      recognitionRef.current = recognition;
      stopRequestedRef.current = false;
      activeRef.current = true;

      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = language;

      recognition.onstart = () => {
        if (!activeRef.current) {
          return;
        }

        setStatus("listening_for_wake_word");
        notifyWakeWordStatus({ status: "listening_for_wake_word", phrase: null });
      };

      recognition.onresult = (event: { resultIndex: number; results: Array<{ 0: { transcript?: string } }> }) => {
        if (!activeRef.current) {
          return;
        }

        const transcripts: string[] = [];
        for (let index = event.resultIndex; index < event.results.length; index += 1) {
          const result = event.results[index];
          const alternative = result[0];
          if (alternative?.transcript) {
            transcripts.push(alternative.transcript);
          }
        }

        const transcript = transcripts.join(" ").trim();
        if (!transcript) {
          return;
        }

        const matchedPhrase = findMatchedPhrase(transcript, phrasesRef.current);
        if (!matchedPhrase) {
          return;
        }

        setLastDetectedPhrase(matchedPhrase);
        setStatus("wake_word_detected");
        notifyWakeWordStatus({ status: "wake_word_detected", phrase: matchedPhrase });
        void window.keobotDesktop?.notifyWakeWordDetected?.(matchedPhrase);
        activeRef.current = false;
        stopRequestedRef.current = true;

        try {
          recognition.stop();
        } catch {
          // Ignore stop errors.
        }
      };

      recognition.onerror = (event: { error: string }) => {
        if (!activeRef.current) {
          return;
        }

        const message = event.error === "not-allowed"
          ? "Wake word microphone permission was denied."
          : event.error === "no-speech"
            ? "Wake word listener could not hear the microphone."
            : `Wake word error: ${event.error}`;
        setError(message);
        setStatus("error");
        notifyWakeWordStatus({ status: "error", phrase: null });
      };

      recognition.onend = () => {
        recognitionRef.current = null;
        if (stopRequestedRef.current) {
          return;
        }

        if (!enabled) {
          return;
        }

        activeRef.current = false;
        setStatus("listening_for_wake_word");
        notifyWakeWordStatus({ status: "listening_for_wake_word", phrase: null });
        window.setTimeout(() => {
          if (enabled && !stopRequestedRef.current) {
            startWakeWord();
          }
        }, 250);
      };

      recognition.start();
    } catch (startError) {
      activeRef.current = false;
      const message = startError instanceof Error ? startError.message : "Wake word could not start.";
      setError(message);
      setStatus("error");
      notifyWakeWordStatus({ status: "error", phrase: null });
    }
  }, [enabled, language, notifyWakeWordStatus]);

  useEffect(() => {
    phrasesRef.current = phrases;
  }, [phrases]);

  useEffect(() => {
    if (!enabled) {
      stopWakeWord();
      return;
    }

    startWakeWord();
    return () => {
      stopWakeWord();
    };
  }, [enabled, startWakeWord, stopWakeWord]);

  useEffect(() => {
    if (typeof window === "undefined" || !window.keobotDesktop?.notifyWakeWordStatus) {
      return;
    }

    void window.keobotDesktop.notifyWakeWordStatus({ status, phrase: lastDetectedPhrase });
  }, [lastDetectedPhrase, status]);

  return useMemo(
    () => ({
      enabled,
      supported,
      status,
      lastDetectedPhrase,
      startWakeWord,
      stopWakeWord,
      error,
    }),
    [enabled, supported, status, lastDetectedPhrase, startWakeWord, stopWakeWord, error],
  );
}
