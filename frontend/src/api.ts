import type { VoiceChatResponse } from "./types";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

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

  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}/voice-chat`, {
      method: "POST",
      body: formData,
    });
  } catch {
    throw new Error("Backend chưa sẵn sàng, hãy thử lại sau.");
  }

  if (!response.ok) {
    const detail = await parseError(response);
    if (response.status === 503) {
      throw new Error("Backend chưa sẵn sàng, hãy thử lại sau.");
    }

    throw new Error(detail);
  }

  return (await response.json()) as VoiceChatResponse;
}
