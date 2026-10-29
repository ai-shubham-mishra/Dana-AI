import { API_BASE_URL, apiPost, raiseForStatus } from "./api";
import { readSse } from "./sse";
import type { ChatSummary, TodoItem } from "./types";

export type ToolCallEvent = { id: string; name: string; args: Record<string, unknown> };

export type StreamHandlers = {
  onToken?: (text: string) => void;
  onTodos?: (todos: TodoItem[]) => void;
  onToolCall?: (call: ToolCallEvent) => void;
  onToolResult?: (result: { id: string; name: string }) => void;
  onDone?: () => void;
};

export function createChat(token: string): Promise<ChatSummary> {
  return apiPost<ChatSummary>("/api/v1/chats", token);
}

export async function streamChatMessage(
  chatId: string,
  content: string,
  token: string,
  handlers: StreamHandlers,
  signal: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/v1/chats/${chatId}/messages`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({ content }),
    cache: "no-store",
    signal,
  });
  await raiseForStatus(res);
  if (!res.body) throw new Error("The server returned no stream");

  for await (const frame of readSse(res.body)) {
    const payload = JSON.parse(frame.data) as Record<string, unknown>;
    switch (frame.event) {
      case "token":
        handlers.onToken?.(String(payload.text ?? ""));
        break;
      case "todos":
        handlers.onTodos?.((payload.todos as TodoItem[]) ?? []);
        break;
      case "tool_call":
        handlers.onToolCall?.(payload as ToolCallEvent);
        break;
      case "tool_result":
        handlers.onToolResult?.(payload as { id: string; name: string });
        break;
      case "error":
        throw new Error(String(payload.message ?? "The agent run failed"));
      case "done":
        handlers.onDone?.();
        break;
    }
  }
}
