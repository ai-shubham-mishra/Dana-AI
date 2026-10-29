"use client";

import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { BarChart3, Cable, Circle, CircleCheck, Loader2, Plus, Send, Sparkles, Wrench } from "lucide-react";

import { createChat, streamChatMessage } from "@/lib/chat";
import { useAccessToken } from "@/lib/auth";
import { relativeTime } from "@/lib/format";
import { useChats, useMessages } from "@/lib/queries";
import type { ChatSummary, TodoItem } from "@/lib/types";

type ToolChip = { id: string; name: string; done: boolean };
type RunState = { chatId: string; userContent: string; text: string; tools: ToolChip[]; todos: TodoItem[] };

const HIDDEN_TOOLS = new Set(["write_todos"]);

const CAPABILITIES = [
  {
    icon: Cable,
    title: "Connect your data",
    body: "Link Meta Ads, Google Ads and other connectors. Dana reads each connector table in your organization's schema.",
  },
  {
    icon: Sparkles,
    title: "Shape the model",
    body: "Describe the outcome you want. Dana asks about channels, date ranges and constraints, then drafts the training code.",
  },
  {
    icon: BarChart3,
    title: "Train and track",
    body: "Run MMM training locally or on Azure ML, with live progress, approvals and results saved per job.",
  },
];

function ChatHistory({
  signedIn,
  items,
  isPending,
  error,
  activeChatId,
  disabled,
  onSelect,
}: {
  signedIn: boolean;
  items: ChatSummary[];
  isPending: boolean;
  error: Error | null;
  activeChatId: string | null;
  disabled: boolean;
  onSelect: (id: string) => void;
}) {
  if (!signedIn) return <p className="px-3 py-2 text-sm text-muted-foreground">Sign in to see your chats</p>;
  if (isPending) return <p className="px-3 py-2 text-sm text-muted-foreground">Loading…</p>;
  if (error) return <p className="px-3 py-2 text-sm text-destructive">{error.message}</p>;
  if (items.length === 0) return <p className="px-3 py-2 text-sm text-muted-foreground">No chats yet</p>;

  return (
    <div className="space-y-1">
      {items.map((chat) => {
        const active = chat.id === activeChatId;
        return (
          <button
            key={chat.id}
            type="button"
            aria-current={active ? "true" : undefined}
            disabled={disabled}
            onClick={() => onSelect(chat.id)}
            className={`flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${
              active ? "bg-magenta-wash text-primary" : "hover:bg-muted"
            }`}
          >
            <span className="truncate">{chat.title}</span>
            <span className="shrink-0 text-[11px] text-muted-foreground">{relativeTime(chat.updated_at)}</span>
          </button>
        );
      })}
    </div>
  );
}

function Avatar() {
  return (
    <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-magenta-wash text-primary">
      <Sparkles className="size-3.5" />
    </div>
  );
}

function MessageBubble({ role, content }: { role: "user" | "assistant"; content: string }) {
  if (role === "user") {
    return (
      <div className="ml-auto max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-cta px-4 py-2.5 text-sm text-cta-foreground">
        {content}
      </div>
    );
  }
  return (
    <div className="flex gap-3">
      <Avatar />
      <p className="min-w-0 flex-1 whitespace-pre-wrap pt-0.5 text-sm leading-6">{content}</p>
    </div>
  );
}

function TodoPanel({ todos }: { todos: TodoItem[] }) {
  return (
    <div className="rounded-xl border border-border bg-card p-3 shadow-sm">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Plan</p>
      <ul className="space-y-1.5">
        {todos.map((todo, index) => {
          const done = todo.status === "completed";
          const inProgress = todo.status === "in_progress";
          return (
            <li key={`${index}-${todo.content}`} className="flex items-start gap-2 text-sm">
              {done ? (
                <CircleCheck className="mt-0.5 size-4 shrink-0 text-primary" />
              ) : inProgress ? (
                <Loader2 className="mt-0.5 size-4 shrink-0 animate-spin text-primary" />
              ) : (
                <Circle className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
              )}
              <span className={done ? "text-muted-foreground line-through" : ""}>{todo.content}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function LiveAssistant({ run }: { run: RunState }) {
  const tools = run.tools.filter((tool) => !HIDDEN_TOOLS.has(tool.name));
  return (
    <div className="flex gap-3">
      <Avatar />
      <div className="min-w-0 flex-1 space-y-3 pt-0.5">
        {tools.length > 0 && (
          <ul className="flex flex-wrap gap-2">
            {tools.map((tool) => (
              <li
                key={tool.id}
                className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1 text-xs"
              >
                <Wrench className="size-3 text-primary" />
                <span>{tool.name.replace(/_/g, " ")}</span>
                {tool.done ? (
                  <CircleCheck className="size-3 text-primary" />
                ) : (
                  <Loader2 className="size-3 animate-spin text-muted-foreground" />
                )}
              </li>
            ))}
          </ul>
        )}
        {run.todos.length > 0 && <TodoPanel todos={run.todos} />}
        {run.text ? (
          <p className="whitespace-pre-wrap text-sm leading-6">{run.text}</p>
        ) : (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" />
            Thinking…
          </p>
        )}
      </div>
    </div>
  );
}

function ErrorBanner({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="mb-3 rounded-md border border-destructive bg-card px-4 py-2 text-sm text-destructive">
      {message}
    </p>
  );
}

function Composer({
  disabled,
  placeholder,
  onSend,
}: {
  disabled: boolean;
  placeholder: string;
  onSend: (content: string) => Promise<boolean>;
}) {
  const [draft, setDraft] = useState("");

  async function submit() {
    const content = draft.trim();
    if (!content || disabled) return;
    setDraft("");
    const accepted = await onSend(content);
    if (!accepted) setDraft((current) => current || content);
  }

  return (
    <div className="rounded-2xl border border-border bg-card p-3 shadow-elevated">
      <textarea
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault();
            void submit();
          }
        }}
        disabled={disabled}
        maxLength={8000}
        rows={2}
        placeholder={placeholder}
        aria-label="Message Dana"
        className="w-full resize-none bg-transparent px-2 py-1 text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed"
      />
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs text-muted-foreground">Enter to send · Shift+Enter for a new line</span>
        <button
          type="button"
          onClick={() => void submit()}
          disabled={disabled || !draft.trim()}
          className="inline-flex items-center gap-1.5 rounded-md bg-cta px-4 py-1.5 text-sm font-medium text-cta-foreground transition-colors hover:bg-cta-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Send className="size-3.5" />
          Send
        </button>
      </div>
    </div>
  );
}

function ChatThread({
  chatId,
  run,
  error,
  disabled,
  onSend,
}: {
  chatId: string;
  run: RunState | null;
  error: string | null;
  disabled: boolean;
  onSend: (content: string) => Promise<boolean>;
}) {
  const messages = useMessages(chatId);
  const liveRun = run?.chatId === chatId ? run : null;
  const bottomRef = useRef<HTMLDivElement>(null);
  const messageCount = messages.data?.length ?? 0;
  const liveText = liveRun?.text ?? "";
  const liveSteps = (liveRun?.tools.length ?? 0) + (liveRun?.todos.length ?? 0);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [messageCount, liveText, liveSteps]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-6 py-8">
          {messages.isPending && <p className="text-sm text-muted-foreground">Loading conversation…</p>}
          {messages.error && <p className="text-sm text-destructive">{messages.error.message}</p>}
          {messages.data?.map((message) => (
            <MessageBubble key={message.id} role={message.role} content={message.content} />
          ))}
          {messages.data?.length === 0 && !liveRun && (
            <p className="text-center text-sm text-muted-foreground">
              Describe the outcome you want to model. Dana will ask about your data before training.
            </p>
          )}
          {liveRun && (
            <>
              <MessageBubble role="user" content={liveRun.userContent} />
              <LiveAssistant run={liveRun} />
            </>
          )}
          <div ref={bottomRef} />
        </div>
      </div>
      <div className="border-t border-border px-6 py-4">
        <div className="mx-auto w-full max-w-3xl">
          <ErrorBanner message={error} />
          <Composer disabled={disabled} placeholder="Message Dana…" onSend={onSend} />
        </div>
      </div>
    </div>
  );
}

export function ChatWindow() {
  const token = useAccessToken();
  const queryClient = useQueryClient();
  const chats = useChats();
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [run, setRun] = useState<RunState | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inFlight = useRef(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  const activeTitle = chats.data?.find((chat) => chat.id === activeChatId)?.title ?? "Chat";

  async function sendMessage(content: string): Promise<boolean> {
    if (!token || inFlight.current) return false;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    const controller = new AbortController();
    abortRef.current = controller;
    let chatId = activeChatId;
    let streamed = false;
    try {
      if (!chatId) {
        chatId = (await createChat(token)).id;
        setActiveChatId(chatId);
      }
      const targetChatId = chatId;
      setRun({ chatId: targetChatId, userContent: content, text: "", tools: [], todos: [] });
      await streamChatMessage(
        targetChatId,
        content,
        token,
        {
          onToken: (text) => {
            streamed = true;
            setRun((current) => (current ? { ...current, text: current.text + text } : current));
          },
          onTodos: (todos) => setRun((current) => (current ? { ...current, todos } : current)),
          onToolCall: ({ id, name }) => {
            streamed = true;
            setRun((current) =>
              current ? { ...current, tools: [...current.tools, { id, name, done: false }] } : current,
            );
          },
          onToolResult: ({ id }) =>
            setRun((current) =>
              current
                ? { ...current, tools: current.tools.map((tool) => (tool.id === id ? { ...tool, done: true } : tool)) }
                : current,
            ),
        },
        controller.signal,
      );
      return true;
    } catch (err) {
      if (controller.signal.aborted) return true;
      setError(err instanceof Error ? err.message : "Something went wrong");
      return streamed;
    } finally {
      if (chatId) await queryClient.invalidateQueries({ queryKey: ["messages", token, chatId] });
      await queryClient.invalidateQueries({ queryKey: ["chats", token] });
      setRun(null);
      abortRef.current = null;
      inFlight.current = false;
      setBusy(false);
    }
  }

  const composerDisabled = !token || busy;

  return (
    <div className="flex h-dvh min-h-0 min-w-0 flex-1">
      <section aria-label="Chat history" className="hidden w-64 shrink-0 flex-col border-r border-border lg:flex">
        <div className="p-3">
          <button
            type="button"
            disabled={composerDisabled}
            aria-label="New chat"
            onClick={() => {
              setActiveChatId(null);
              setError(null);
            }}
            className="flex w-full items-center gap-2 rounded-md bg-cta px-3 py-2 text-sm font-medium text-cta-foreground transition-colors hover:bg-cta-hover disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Plus className="size-4" />
            New chat
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
          <ChatHistory
            signedIn={Boolean(token)}
            items={chats.data ?? []}
            isPending={chats.isPending}
            error={chats.error}
            activeChatId={activeChatId}
            disabled={busy}
            onSelect={(id) => {
              setActiveChatId(id);
              setError(null);
            }}
          />
        </div>
      </section>

      <div className="flex min-h-0 min-w-0 flex-1 flex-col">
        <header className="flex items-center border-b border-border px-6 py-4 md:px-10">
          <h1 className="truncate text-sm font-semibold">{activeChatId ? activeTitle : "Chat"}</h1>
        </header>

        {activeChatId ? (
          <ChatThread
            key={activeChatId}
            chatId={activeChatId}
            run={run}
            error={error}
            disabled={composerDisabled}
            onSend={sendMessage}
          />
        ) : (
          <div className="min-h-0 flex-1 overflow-y-auto">
            <section className="mx-auto flex w-full max-w-3xl flex-col items-center justify-center px-6 py-16 text-center">
              <h2 className="text-4xl font-semibold tracking-tight md:text-5xl">
                What should we <span className="text-primary">train</span> today?
              </h2>
              <p className="mt-4 max-w-xl text-base text-muted-foreground">
                Dana AI turns your marketing data into predictive models. It asks the right questions, writes the training
                code for your data, and keeps you updated while jobs run.
              </p>

              {!token && (
                <p className="mt-6 rounded-md border border-border bg-card px-4 py-2 text-sm text-muted-foreground">
                  Sign in with an access token from the sidebar to load your chats and jobs.
                </p>
              )}

              <div className="mt-10 grid w-full gap-4 md:grid-cols-3">
                {CAPABILITIES.map(({ icon: Icon, title, body }) => (
                  <div
                    key={title}
                    className="rounded-xl border border-border bg-card p-5 text-left shadow-sm transition-shadow hover:shadow-elevated"
                  >
                    <div className="mb-3 inline-flex size-9 items-center justify-center rounded-lg bg-magenta-wash text-primary">
                      <Icon className="size-4" />
                    </div>
                    <h3 className="text-sm font-semibold">{title}</h3>
                    <p className="mt-1.5 text-sm text-muted-foreground">{body}</p>
                  </div>
                ))}
              </div>

              <div className="mt-10 w-full text-left">
                <ErrorBanner message={error} />
                <Composer
                  disabled={composerDisabled}
                  placeholder={token ? "Describe the model you want to train…" : "Sign in to start a chat"}
                  onSend={sendMessage}
                />
              </div>
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
