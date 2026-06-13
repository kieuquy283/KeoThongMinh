import { useCallback, useEffect, useRef, useState } from "react";
import { AudioStreamPlayer } from "../utils/AudioStreamPlayer";
import type { Emotion } from "../types";

const WS_URL = "ws://127.0.0.1:8000/v2/stream-chat";

export interface ContinuousChatState {
  isListening: boolean;
  isProcessing: boolean;
  isPlaying: boolean;
  botText: string;
  userText: string;
  emotion: Emotion;
  error: string | null;
}

/**
 * Continuous conversation: always listening, auto-detect speech/silence,
 * auto-send, auto-play, and auto-return to listening.
 * Zero button presses required for the core flow.
 */
export function useContinuousChat(): ContinuousChatState {
  const wsRef = useRef<WebSocket | null>(null);
  const playerRef = useRef<AudioStreamPlayer | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioBufferRef = useRef<string[]>([]);
  const silenceTimerRef = useRef<number>(0);
  const vadStateRef = useRef<"idle" | "speaking" | "silence">("idle");
  const textBufferRef = useRef<string>("");
  const userTextRef = useRef<string>("");
  const isTurnPendingRef = useRef(false);
  const isPlayingRef = useRef(false);
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [botText, setBotText] = useState("");
  const [userText, setUserText] = useState("");
  const [emotion] = useState<Emotion>("neutral");
  const [error, setError] = useState<string | null>(null);

  // Initialize AudioStreamPlayer
  useEffect(() => {
    const player = new AudioStreamPlayer();
    playerRef.current = player;
    const unsubscribe = player.subscribe((playing) => {
      isPlayingRef.current = playing;
      setIsPlaying(playing);
      // When playback ends and we're not processing, auto-return to listening
      if (!playing && !isTurnPendingRef.current) {
        startListening();
      }
    });
    return () => {
      unsubscribe();
      player.destroy();
    };
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    connectWebSocket();
    return () => {
      disconnect();
    };
  }, []);

  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setError(null);
      // Auto-start listening once connected
      startListening();
    };

    ws.onmessage = (event) => {
      try {
        const frame = JSON.parse(event.data) as {
          event: string;
          data?: string;
        };
        switch (frame.event) {
          case "audio_response": {
            if (playerRef.current && frame.data) {
              playerRef.current.playChunk(frame.data);
            }
            break;
          }
          case "text_response": {
            if (frame.data) {
              textBufferRef.current += frame.data;
              setBotText(textBufferRef.current);
            }
            break;
          }
          case "response_done": {
            isTurnPendingRef.current = false;
            setIsProcessing(false);
            textBufferRef.current = "";
            // If nothing is playing, return to listening
            setTimeout(() => {
              if (!isPlayingRef.current && !isTurnPendingRef.current) {
                startListening();
              }
            }, 500);
            break;
          }
          case "clear": {
            textBufferRef.current = "";
            setBotText("");
            break;
          }
          case "error": {
            setError(frame.data || "Streaming error");
            isTurnPendingRef.current = false;
            setIsProcessing(false);
            startListening();
            break;
          }
        }
      } catch {
        // ignore
      }
    };

    ws.onerror = () => {
      setError("WebSocket error, reconnecting...");
      setIsListening(false);
      setIsProcessing(false);
      // Auto-reconnect after 2s
      setTimeout(() => {
        disconnect();
        connectWebSocket();
      }, 2000);
    };

    ws.onclose = () => {
      setIsListening(false);
      setIsProcessing(false);
      if (playerRef.current) {
        playerRef.current.clear();
      }
    };
  }, []);

  const startListening = useCallback(async () => {
    if (recorderRef.current) return;
    if (wsRef.current?.readyState !== WebSocket.OPEN) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 24000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      streamRef.current = stream;

      const audioCtx = new AudioContext({ sampleRate: 24000 });
      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 512;
      source.connect(analyser);

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: "audio/webm;codecs=opus",
      });
      recorderRef.current = mediaRecorder;

      // VAD monitoring
      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      const checkVolume = () => {
        if (!recorderRef.current) return;
        analyser.getByteFrequencyData(dataArray);
        const average =
          dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
        const volume = average / 255;
        const currentState = vadStateRef.current;

        if (volume > 0.03) {
          // Speech detected
          if (currentState === "idle") {
            vadStateRef.current = "speaking";
            setIsListening(true);
            setUserText("Đang nghe...");
            // Clear any pending silence timer
            if (silenceTimerRef.current) {
              window.clearTimeout(silenceTimerRef.current);
              silenceTimerRef.current = 0;
            }
            // If bot was playing, interrupt immediately
            if (isPlayingRef.current) {
              interruptBot();
            }
          } else if (currentState === "silence") {
            vadStateRef.current = "speaking";
            if (silenceTimerRef.current) {
              window.clearTimeout(silenceTimerRef.current);
              silenceTimerRef.current = 0;
            }
          }
        } else if (currentState === "speaking") {
          // Transition to silence
          vadStateRef.current = "silence";
          silenceTimerRef.current = window.setTimeout(() => {
            // Silence persisted for 800ms -> finish the turn
            if (vadStateRef.current === "silence" && recorderRef.current) {
              finishTurn();
            }
          }, 800);
        }

        // Continue monitoring
        if (recorderRef.current) {
          requestAnimationFrame(checkVolume);
        }
      };

      mediaRecorder.ondataavailable = async (event) => {
        if (event.data.size > 0 && wsRef.current?.readyState === WebSocket.OPEN) {
          const base64 = await blobToBase64(event.data);
          audioBufferRef.current.push(base64);
          wsRef.current.send(
            JSON.stringify({ event: "audio_chunk", data: base64 })
          );
        }
      };

      mediaRecorder.start(100);
      requestAnimationFrame(checkVolume);
      setIsListening(true);
    } catch (err) {
      console.error("Failed to start microphone:", err);
      setError("Không thể truy cập microphone");
    }
  }, []);

  const stopListening = useCallback(() => {
    if (recorderRef.current) {
      recorderRef.current.stop();
      recorderRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (silenceTimerRef.current) {
      window.clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = 0;
    }
    vadStateRef.current = "idle";
    setIsListening(false);
    setUserText("");
  }, []);

  const finishTurn = useCallback(() => {
    if (!recorderRef.current) return;
    // Stop recording
    recorderRef.current.stop();
    recorderRef.current = null;
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    vadStateRef.current = "idle";
    setIsListening(false);
    setIsProcessing(true);
    isTurnPendingRef.current = true;
    setUserText("Đang xử lý...");

    // Send finish_turn to trigger backend processing
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ event: "finish_turn" }));
    }

    // Clear buffers
    audioBufferRef.current = [];
  }, []);

  const interruptBot = useCallback(() => {
    if (playerRef.current) {
      playerRef.current.clear();
    }
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ event: "user_interrupt" }));
    }
    textBufferRef.current = "";
    setBotText("");
    isTurnPendingRef.current = false;
    setIsProcessing(false);
    // Immediately restart listening
    setTimeout(() => startListening(), 100);
  }, [startListening]);

  const disconnect = useCallback(() => {
    stopListening();
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (playerRef.current) {
      playerRef.current.clear();
    }
    setIsListening(false);
    setIsProcessing(false);
    setIsPlaying(false);
    setBotText("");
    setUserText("");
    textBufferRef.current = "";
  }, [stopListening]);

  const state: ContinuousChatState = {
    isListening,
    isProcessing,
    isPlaying,
    botText,
    userText,
    emotion,
    error,
  };

  return state;
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result as string;
      const base64 = result.split(",")[1] || "";
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}
