import { KeoBotAnimatedMascot } from "./KeoBotAnimatedMascot";
import type { MascotEmotion, MascotStatus } from "../utils/keobotMascotState";

export interface KeoBotMascotProps {
  status: MascotStatus;
  emotion?: MascotEmotion;
  isVisible?: boolean;
  className?: string;
}

export function KeoBotMascot({ status, emotion = "neutral", isVisible = true, className }: KeoBotMascotProps) {
  return (
    <KeoBotAnimatedMascot
      status={status}
      emotion={emotion}
      isVisible={isVisible}
      className={className}
    />
  );
}
