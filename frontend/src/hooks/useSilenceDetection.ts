import { useEffect, useRef } from "react";

interface SilenceDetectionOptions {
  stream: MediaStream | null;
  enabled?: boolean;
  volumeThreshold?: number;
  silenceMs?: number;
  minSpeechMs?: number;
  onSpeechStart?: () => void;
  onSilence?: () => void;
}

const DEFAULT_VOLUME_THRESHOLD = 0.02;
const DEFAULT_SILENCE_MS = 1000;
const DEFAULT_MIN_SPEECH_MS = 500;

export function useSilenceDetection({
  stream,
  enabled = true,
  volumeThreshold = DEFAULT_VOLUME_THRESHOLD,
  silenceMs = DEFAULT_SILENCE_MS,
  minSpeechMs = DEFAULT_MIN_SPEECH_MS,
  onSpeechStart,
  onSilence,
}: SilenceDetectionOptions): void {
  const onSpeechStartRef = useRef(onSpeechStart);
  const onSilenceRef = useRef(onSilence);

  useEffect(() => {
    onSpeechStartRef.current = onSpeechStart;
  }, [onSpeechStart]);

  useEffect(() => {
    onSilenceRef.current = onSilence;
  }, [onSilence]);

  useEffect(() => {
    if (!stream || !enabled) {
      return;
    }

    const AudioContextCtor = window.AudioContext || (window as typeof window & {
      webkitAudioContext?: typeof AudioContext;
    }).webkitAudioContext;

    if (!AudioContextCtor) {
      return;
    }

    const audioContext = new AudioContextCtor();
    const source = audioContext.createMediaStreamSource(stream);
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 2048;
    analyser.smoothingTimeConstant = 0.2;
    source.connect(analyser);

    const buffer = new Float32Array(analyser.fftSize);
    let frameId = 0;
    let speechStartedAt = 0;
    let lastAboveThresholdAt = 0;
    let isSpeechActive = false;
    let silenceEmitted = false;
    let cancelled = false;

    const tick = () => {
      if (cancelled) {
        return;
      }

      analyser.getFloatTimeDomainData(buffer);
      let sumSquares = 0;
      for (let index = 0; index < buffer.length; index += 1) {
        const sample = buffer[index];
        sumSquares += sample * sample;
      }

      const rms = Math.sqrt(sumSquares / buffer.length);
      const now = performance.now();

      if (rms >= volumeThreshold) {
        lastAboveThresholdAt = now;
        silenceEmitted = false;

        if (!isSpeechActive) {
          isSpeechActive = true;
          speechStartedAt = now;
          onSpeechStartRef.current?.();
        }
      } else if (isSpeechActive) {
        const speechDuration = now - speechStartedAt;
        const silenceDuration = now - lastAboveThresholdAt;
        if (!silenceEmitted && speechDuration >= minSpeechMs && silenceDuration >= silenceMs) {
          silenceEmitted = true;
          isSpeechActive = false;
          speechStartedAt = 0;
          lastAboveThresholdAt = 0;
          onSilenceRef.current?.();
        }
      }

      frameId = window.requestAnimationFrame(tick);
    };

    void audioContext.resume().then(() => {
      frameId = window.requestAnimationFrame(tick);
    }).catch(() => {
      frameId = window.requestAnimationFrame(tick);
    });

    return () => {
      cancelled = true;
      if (frameId) {
        window.cancelAnimationFrame(frameId);
      }
      source.disconnect();
      analyser.disconnect();
      void audioContext.close().catch(() => {
        // Ignore close errors during cleanup.
      });
    };
  }, [enabled, minSpeechMs, silenceMs, stream, volumeThreshold]);
}

export const silenceDetectionDefaults = {
  volumeThreshold: DEFAULT_VOLUME_THRESHOLD,
  silenceMs: DEFAULT_SILENCE_MS,
  minSpeechMs: DEFAULT_MIN_SPEECH_MS,
};
