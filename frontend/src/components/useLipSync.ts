import { useEffect, useRef } from 'react';
import * as THREE from 'three';

export function useLipSync(audioElement: HTMLAudioElement | null, modelRef: React.RefObject<THREE.Group>) {
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<MediaElementAudioSourceNode | null>(null);
  const reqFrameRef = useRef<number>(0);

  useEffect(() => {
    if (!audioElement) return;

    // Chỉ khởi tạo AudioContext nếu chưa có để tránh lỗi tạo nhiều lần
    if (!audioContextRef.current) {
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
      audioContextRef.current = ctx;

      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      analyserRef.current = analyser;

      try {
        const source = ctx.createMediaElementSource(audioElement);
        sourceRef.current = source;
        source.connect(analyser);
        analyser.connect(ctx.destination);
      } catch (e) {
        console.warn("Không thể kết nối Audio Source (có thể do đã connect trước đó):", e);
      }
    }

    const updateLipSync = () => {
      if (analyserRef.current && modelRef.current && !audioElement.paused) {
        const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
        analyserRef.current.getByteFrequencyData(dataArray);
        
        let sum = 0;
        for (let i = 0; i < dataArray.length; i++) {
          sum += dataArray[i];
        }
        const average = sum / dataArray.length;
        
        // Map average sang giá trị (0 - 1) để mở miệng
        const influence = Math.min(1, (average / 128) * 1.5); 

        modelRef.current.traverse((child) => {
          if ((child as THREE.Mesh).isMesh && (child as THREE.Mesh).morphTargetInfluences) {
            const mesh = child as THREE.Mesh;
            const dict = mesh.morphTargetDictionary;
            if (dict) {
              const openMouthKeys = ['v_aa', 'jawOpen', 'mouthOpen', 'viseme_aa'];
              for (const key of openMouthKeys) {
                if (dict[key] !== undefined) {
                  mesh.morphTargetInfluences![dict[key]] = influence;
                }
              }
            }
          }
        });
      }

      reqFrameRef.current = requestAnimationFrame(updateLipSync);
    };

    updateLipSync();

    return () => {
      cancelAnimationFrame(reqFrameRef.current);
      // Khi audio thay đổi, reset miệng về 0
      if (modelRef.current) {
        modelRef.current.traverse((child) => {
          if ((child as THREE.Mesh).isMesh && (child as THREE.Mesh).morphTargetInfluences) {
            const mesh = child as THREE.Mesh;
            const dict = mesh.morphTargetDictionary;
            if (dict) {
              const openMouthKeys = ['v_aa', 'jawOpen', 'mouthOpen', 'viseme_aa'];
              for (const key of openMouthKeys) {
                if (dict[key] !== undefined) {
                  mesh.morphTargetInfluences![dict[key]] = 0;
                }
              }
            }
          }
        });
      }
    };
  }, [audioElement, modelRef]);
}
