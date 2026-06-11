import type {
  KeoBotReminder,
  MemoryContextResponse,
  MemoryItem,
  MemoryUpdateRequest,
  MemoryUpsertRequest,
  ToolTestRequest,
  ToolTestResponse,
  ToolsStatusResponse,
  VoiceChatResponse,
} from "./types";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function parseError(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: string };
    return data.detail ?? `HTTP ${response.status}`;
  } catch {
    return `HTTP ${response.status}`;
  }
}

export async function sendVoiceChat(audioBlob: Blob, signal?: AbortSignal): Promise<VoiceChatResponse> {
  const formData = new FormData();
  formData.append("audio", audioBlob, "voice.webm");

  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}/voice-chat`, {
      method: "POST",
      body: formData,
      signal,
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

export async function cancelVoiceTurn(sessionId: string): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/voice-turn/${encodeURIComponent(sessionId)}/cancel`, {
      method: "POST",
    });
    return response.ok;
  } catch {
    return false;
  }
}

export type VoiceTurnEvent =
  | { event: "session_started"; session_id: string }
  | { event: "transcribing"; session_id: string }
  | { event: "thinking"; session_id: string }
  | { event: "tts_ready"; session_id: string; audio_url: string }
  | { event: "completed"; session_id: string }
  | { event: "cancelled"; session_id: string }
  | { event: "error"; session_id: string; message: string }
  | { event: "pong"; session_id: string };

export function createVoiceTurnWebSocket(): WebSocket | null {
  try {
    const wsUrl = API_BASE_URL.replace(/^http:/, "ws:").replace(/\/$/, "") + "/ws/voice-turn";
    return new WebSocket(wsUrl);
  } catch {
    return null;
  }
}

export async function fetchReminders(): Promise<KeoBotReminder[]> {
  const response = await fetch(`${API_BASE_URL}/reminders`);
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return (await response.json()) as KeoBotReminder[];
}

export async function deleteReminder(reminderId: number): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/reminders/${reminderId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
}

export async function fetchToolsStatus(): Promise<ToolsStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/tools/status`);
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return (await response.json()) as ToolsStatusResponse;
}

export async function testTool(request: ToolTestRequest): Promise<ToolTestResponse> {
  const response = await fetch(`${API_BASE_URL}/tools/test`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return (await response.json()) as ToolTestResponse;
}

export async function fetchMemory(): Promise<MemoryItem[]> {
  const response = await fetch(`${API_BASE_URL}/memory`);
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return (await response.json()) as MemoryItem[];
}

export async function saveMemoryItem(request: MemoryUpsertRequest): Promise<MemoryItem> {
  const response = await fetch(`${API_BASE_URL}/memory`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return (await response.json()) as MemoryItem;
}

export async function deleteMemoryItem(key: MemoryItem["key"]): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/memory/${encodeURIComponent(key)}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
}

export async function updateMemoryItem(key: string, request: MemoryUpdateRequest): Promise<MemoryItem> {
  const response = await fetch(`${API_BASE_URL}/memory/${encodeURIComponent(key)}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return (await response.json()) as MemoryItem;
}

export async function enableMemoryItem(key: string): Promise<MemoryItem> {
  const response = await fetch(`${API_BASE_URL}/memory/${encodeURIComponent(key)}/enable`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return (await response.json()) as MemoryItem;
}

export async function disableMemoryItem(key: string): Promise<MemoryItem> {
  const response = await fetch(`${API_BASE_URL}/memory/${encodeURIComponent(key)}/disable`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return (await response.json()) as MemoryItem;
}

export async function fetchMemoryContext(): Promise<MemoryContextResponse> {
  const response = await fetch(`${API_BASE_URL}/memory/context`);
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return (await response.json()) as MemoryContextResponse;
}

export async function clearMemory(): Promise<{ ok: boolean; deleted: number }> {
  const response = await fetch(`${API_BASE_URL}/memory`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return (await response.json()) as { ok: boolean; deleted: number };
}
