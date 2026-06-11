import { KeoBotAnimatedMascot } from "./KeoBotAnimatedMascot";
import type { MascotEmotion, MascotStatus } from "../utils/keobotMascotState";

interface KeoBotPlaceholderProps {
  status: MascotStatus;
  statusLabel?: string;
  statusMessage?: string;
  audioElement?: HTMLAudioElement | null;
  emotion?: MascotEmotion;
}

export function KeoBotPlaceholder({ status, emotion = "neutral" }: KeoBotPlaceholderProps) {
  return <KeoBotAnimatedMascot status={status} emotion={emotion} />;
}
