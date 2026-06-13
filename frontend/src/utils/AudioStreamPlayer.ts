/**
 * Low-level audio queue stream player using Web Audio API.
 * Schedules PCM16 (or decoded Float32) audio chunks back-to-back with zero gaps.
 * Do NOT use HTML5 <audio> tags for streaming chunks.
 */
export class AudioStreamPlayer {
  private audioCtx: AudioContext;
  private nextStartTime: number = 0;
  private gainNode: GainNode;
  private isPlayingFlag: boolean = false;
  private onStateChange: ((playing: boolean) => void) | null = null;

  constructor() {
    // Realtime API outputs PCM16 24kHz mono
    this.audioCtx = new AudioContext({ sampleRate: 24000 });
    this.gainNode = this.audioCtx.createGain();
    this.gainNode.connect(this.audioCtx.destination);
  }

  /**
   * Schedule a base64-encoded PCM16 audio chunk for playback.
   * Automatically handles gapless scheduling via `nextStartTime`.
   */
  async playChunk(base64Pcm16: string): Promise<void> {
    if (!base64Pcm16) return;

    const raw = base64ToArrayBuffer(base64Pcm16);
    const float32 = this.convertPCM16ToFloat32(raw);

    const audioBuffer = this.audioCtx.createBuffer(
      1,
      float32.length,
      this.audioCtx.sampleRate
    );
    audioBuffer.copyToChannel(float32, 0);

    const source = this.audioCtx.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(this.gainNode);

    // Ensure we never schedule in the past
    if (this.nextStartTime < this.audioCtx.currentTime) {
      this.nextStartTime = this.audioCtx.currentTime;
    }

    source.start(this.nextStartTime);
    this.nextStartTime += audioBuffer.duration;

    this.isPlayingFlag = true;
    this.onStateChange?.(true);

    // Schedule a callback to check when queue depletes
    const checkEnd = () => {
      if (this.audioCtx.currentTime >= this.nextStartTime - 0.05) {
        this.isPlayingFlag = false;
        this.onStateChange?.(false);
      } else {
        window.setTimeout(checkEnd, 100);
      }
    };
    window.setTimeout(checkEnd, Math.max(50, audioBuffer.duration * 1000 + 50));
  }

  /**
   * Violently wipe the schedule queue, disconnect active buffers,
   * and silence audio output instantly. Call this on user interruption.
   */
  clear(): void {
    // Disconnect old gain node and create a new one to kill all scheduled sources
    this.gainNode.disconnect();
    this.gainNode = this.audioCtx.createGain();
    this.gainNode.connect(this.audioCtx.destination);

    // Reset schedule head
    this.nextStartTime = this.audioCtx.currentTime;
    this.isPlayingFlag = false;
    this.onStateChange?.(false);
  }

  /**
   * Check if the queue currently has scheduled audio.
   */
  get isPlaying(): boolean {
    return this.isPlayingFlag;
  }

  /**
   * Subscribe to playback state changes (true = playing, false = idle).
   */
  subscribe(callback: (playing: boolean) => void): () => void {
    this.onStateChange = callback;
    return () => {
      this.onStateChange = null;
    };
  }

  /**
   * Convert a PCM16 Int16Array buffer to Float32Array for Web Audio API.
   */
  private convertPCM16ToFloat32(pcm16Buffer: ArrayBuffer): Float32Array {
    const int16 = new Int16Array(pcm16Buffer);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / 32768.0;
    }
    return float32;
  }

  /**
   * Clean up the AudioContext. Call on component unmount.
   */
  destroy(): void {
    this.clear();
    this.audioCtx.close().catch(() => {});
  }
}

function base64ToArrayBuffer(base64: string): ArrayBuffer {
  const binary = atob(base64);
  const len = binary.length;
  const buffer = new ArrayBuffer(len);
  const view = new Uint8Array(buffer);
  for (let i = 0; i < len; i++) {
    view[i] = binary.charCodeAt(i);
  }
  return buffer;
}
