import type { VoiceChatResponse } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function parseError(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: string };
    return data.detail ?? `HTTP ${response.status}`;
  } catch {
    return `HTTP ${response.status}`;
  }
}

export async function sendVoiceChat(audioBlob: Blob): Promise<VoiceChatResponse> {
  const formData = new FormData();
  formData.append("audio", audioBlob, "voice.webm");

  const response = await fetch(`${API_BASE_URL}/voice-chat`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await parseError(response));
  }

  return (await response.json()) as VoiceChatResponse;
}
