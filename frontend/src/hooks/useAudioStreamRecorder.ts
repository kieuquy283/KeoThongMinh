import { useCallback, useRef } from "react";

export interface AudioStreamRecorder {
  start: () => Promise<void>;
  stop: () => void;
  isActive: () => boolean;
}

/**
 * Hook to capture microphone audio in 100ms slices and send
 * base64-encoded webm/opus chunks over a WebSocket.
 */
export function useAudioStreamRecorder(wsRef: React.MutableRefObject<WebSocket | null>): AudioStreamRecorder {
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const start = useCallback(async () => {
    if (mediaRecorderRef.current) return;

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

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: "audio/webm;codecs=opus",
      });
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = async (event) => {
        if (event.data.size > 0 && wsRef.current?.readyState === WebSocket.OPEN) {
          const base64 = await blobToBase64(event.data);
          wsRef.current.send(
            JSON.stringify({
              event: "audio_chunk",
              data: base64,
            })
          );
        }
      };

      mediaRecorder.onerror = (e) => {
        console.error("MediaRecorder error:", e);
      };

      // 100ms slicing as required
      mediaRecorder.start(100);
    } catch (err) {
      console.error("Failed to start audio stream recorder:", err);
    }
  }, [wsRef]);

  const stop = useCallback(() => {
    if (mediaRecorderRef.current) {
      try {
        mediaRecorderRef.current.stop();
      } catch {
        // ignore
      }
      mediaRecorderRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  }, []);

  const isActive = useCallback(() => {
    return mediaRecorderRef.current !== null && mediaRecorderRef.current.state !== "inactive";
  }, []);

  return { start, stop, isActive };
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result as string;
      // Strip data:audio/webm;base64, prefix
      const base64 = result.split(",")[1] || "";
      resolve(base64);
    };
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}
