import { useCallback, useEffect, useRef, useState } from "react";
import { AudioStreamPlayer } from "../utils/AudioStreamPlayer";
import { useAudioStreamRecorder } from "./useAudioStreamRecorder";
import type { Emotion } from "../types";

export interface RealtimeVoiceChatState {
  isConnected: boolean;
  isRecording: boolean;
  isPlaying: boolean;
  botText: string;
  emotion: Emotion;
  error: string | null;
}

export interface RealtimeVoiceChatActions {
  start: () => void;
  stop: () => void;
  interrupt: () => void;
}

const WS_URL = "ws://127.0.0.1:8000/v2/stream-chat";

/**
 * Hook that orchestrates the full-duplex realtime voice chat pipeline
 * via WebSocket to the backend OpenAI Realtime API proxy.
 */
export function useRealtimeVoiceChat(): [RealtimeVoiceChatState, RealtimeVoiceChatActions] {
  const wsRef = useRef<WebSocket | null>(null);
  const playerRef = useRef<AudioStreamPlayer | null>(null);
  const recorderRef = useAudioStreamRecorder(wsRef);
  const textBufferRef = useRef<string>("");
  const [isConnected, setIsConnected] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [botText, setBotText] = useState("");
  const [emotion] = useState<Emotion>("neutral");
  const [error, setError] = useState<string | null>(null);

  // Initialize AudioStreamPlayer once
  useEffect(() => {
    const player = new AudioStreamPlayer();
    playerRef.current = player;
    const unsubscribe = player.subscribe((playing) => {
      setIsPlaying(playing);
    });
    return () => {
      unsubscribe();
      player.destroy();
      playerRef.current = null;
    };
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      setError(null);
    };

    ws.onmessage = (event) => {
      try {
        const frame = JSON.parse(event.data) as { event: string; data?: string };
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
            // Response finished; optionally clear text buffer after a delay
            textBufferRef.current = "";
            break;
          }
          case "clear": {
            textBufferRef.current = "";
            setBotText("");
            break;
          }
          case "error": {
            setError(frame.data || "Realtime streaming error");
            break;
          }
        }
      } catch {
        // ignore malformed frames
      }
    };

    ws.onerror = () => {
      setError("WebSocket connection error");
      setIsConnected(false);
    };

    ws.onclose = () => {
      setIsConnected(false);
      setIsRecording(false);
      if (playerRef.current) {
        playerRef.current.clear();
      }
    };
  }, []);

  const disconnect = useCallback(() => {
    recorderRef.stop();
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    if (playerRef.current) {
      playerRef.current.clear();
    }
    setIsConnected(false);
    setIsRecording(false);
    setBotText("");
    textBufferRef.current = "";
  }, [recorderRef]);

  const start = useCallback(() => {
    setError(null);
    setBotText("");
    textBufferRef.current = "";
    connect();
    // Start recording after a short delay to ensure WebSocket is open
    setTimeout(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        recorderRef.start();
        setIsRecording(true);
      } else {
        setError("WebSocket not ready");
      }
    }, 300);
  }, [connect, recorderRef]);

  const stop = useCallback(() => {
    recorderRef.stop();
    setIsRecording(false);
    // Keep WebSocket open for a moment to let final chunks flush
    setTimeout(() => {
      disconnect();
    }, 500);
  }, [recorderRef, disconnect]);

  const interrupt = useCallback(() => {
    if (playerRef.current) {
      playerRef.current.clear();
    }
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ event: "user_interrupt" }));
    }
    setBotText("");
    textBufferRef.current = "";
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  const state: RealtimeVoiceChatState = {
    isConnected,
    isRecording,
    isPlaying,
    botText,
    emotion,
    error,
  };

  const actions: RealtimeVoiceChatActions = {
    start,
    stop,
    interrupt,
  };

  return [state, actions];
}
