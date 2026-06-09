import React, { useRef, useEffect } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { useGLTF, OrbitControls, Environment, ContactShadows } from '@react-three/drei';
import * as THREE from 'three';
import { useLipSync } from './useLipSync';

// Component chứa mô hình 3D
function Model({ url, audioElement }: { url: string; audioElement: HTMLAudioElement | null }) {
  const { scene } = useGLTF(url);
  const modelRef = useRef<THREE.Group>(null);

  // Setup Toon Shader
  useEffect(() => {
    if (scene) {
      scene.traverse((child) => {
        if ((child as THREE.Mesh).isMesh) {
          const mesh = child as THREE.Mesh;
          const oldMat = mesh.material as THREE.MeshStandardMaterial;
          
          // Chuyển đổi sang MeshToonMaterial để có phong cách 2D/Anime
          const toonMat = new THREE.MeshToonMaterial({
            color: oldMat.color,
            map: oldMat.map,
            transparent: oldMat.transparent,
            opacity: oldMat.opacity,
          });
          mesh.material = toonMat;
        }
      });
    }
  }, [scene]);

  // Idle Animation đơn giản (nhấp nhô nhẹ)
  useFrame((state) => {
    if (modelRef.current) {
      modelRef.current.position.y = Math.sin(state.clock.elapsedTime * 2) * 0.02 - 1; // -1 là base y
    }
  });

  // Gọi hook cấu hình lip-sync
  useLipSync(audioElement, modelRef);

  return <primitive ref={modelRef} object={scene} scale={[1, 1, 1]} position={[0, -1, 0]} />;
}

export default function KeoBot3D({ audioElement }: { audioElement: HTMLAudioElement | null }) {
  return (
    <div style={{ width: '100%', height: '100%' }}>
      <Canvas camera={{ position: [0, 1.5, 4], fov: 45 }}>
        {/* Ánh sáng cơ bản */}
        <ambientLight intensity={0.6} />
        <directionalLight position={[5, 5, 5]} intensity={1.5} />
        <directionalLight position={[-5, 5, -5]} intensity={0.5} />
        
        {/* Model chính */}
        {/* Hiện tại sử dụng file mẫu keobot_billboard.glb, sau sẽ thay bằng file chuẩn */}
        <React.Suspense fallback={null}>
          <Model url="/keobot_billboard.glb" audioElement={audioElement} />
        </React.Suspense>
        
        {/* Môi trường phản xạ & Bóng đổ */}
        <Environment preset="city" />
        <ContactShadows position={[0, -1, 0]} opacity={0.5} scale={10} blur={2} far={4} />
        
        {/* Tương tác chuột cơ bản (Chỉ cho phép xoay nhẹ, không cho zoom/pan) */}
        <OrbitControls 
          enableZoom={false} 
          enablePan={false} 
          minPolarAngle={Math.PI / 3} 
          maxPolarAngle={Math.PI / 2}
          minAzimuthAngle={-Math.PI / 4}
          maxAzimuthAngle={Math.PI / 4}
        />
      </Canvas>
    </div>
  );
}
