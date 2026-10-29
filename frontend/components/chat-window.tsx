"use client";

import { Fragment, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { BarChart3, Cable, Circle, CircleCheck, Loader2, Send, Sparkles, Wrench } from "lucide-react";

import { ApprovalPanel } from "@/components/approval-panel";
import { Markdown } from "@/components/markdown";
import { ReasoningTicker, ThinkingBlock, ToolStatusIcon, splitReply } from "@/components/thinking";
import { apiGet } from "@/lib/api";
import { createChat, resumeChat, streamChatMessage, type StreamHandlers } from "@/lib/chat";
import { useAccessToken } from "@/lib/auth";
import { useChatSelection } from "@/lib/chat-selection";
import { useChats, useMessages, usePending } from "@/lib/queries";
import type { ChatMessage, Decision, TodoItem } from "@/lib/types";

type ToolChip = { id: string; name: string; done: boolean };
// boundary: text length at the last tool event; text before it is process, after it is the answer.
type RunState = {
  id: string;
  userContent: string | null;
  text: string;
  boundary: number;
  tools: ToolChip[];
  todos: TodoItem[];
  // Saved message count when the run started. Saved messages from this index on are shown by runs.
  baseCount: number;
  done: boolean;
};

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

function MessageBubble({
  role,
  content,
  thinking,
}: {
  role: "user" | "assistant";
  content: string;
  thinking?: string | null;
}) {
  if (role === "user") {
    return (
      <div className="ml-auto max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-cta px-4 py-2.5 text-sm text-cta-foreground">
        {content}
      </div>
    );
  }
  return (
    <div className="min-w-0 space-y-3">
      {thinking && (
        <ThinkingBlock live={false} hasContent>
          <Markdown className="text-xs text-muted-foreground">{thinking}</Markdown>
        </ThinkingBlock>
      )}
      {content && <Markdown>{content}</Markdown>}
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

function AssistantTurn({ run }: { run: RunState }) {
  const tools = run.tools.filter((tool) => !HIDDEN_TOOLS.has(tool.name));
  const { process, answer } = splitReply(run.text, run.boundary);
  const running = tools.find((tool) => !tool.done);
  const status = answer
    ? "Writing response…"
    : running
      ? `Running ${running.name.replace(/_/g, " ")}…`
      : process
        ? "Reasoning…"
        : "Thinking…";
  const hasProcess = tools.length > 0 || run.todos.length > 0 || process.length > 0;
  return (
    <div className="min-w-0 space-y-3">
      <ThinkingBlock live={!run.done} status={status} hasContent={hasProcess} defaultOpen>
          {tools.length > 0 && (
            <ul className="flex flex-wrap gap-2">
              {tools.map((tool) => (
                <li
                  key={tool.id}
                  className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1 text-xs"
                >
                  <Wrench className="size-3 text-primary" />
                  <span>{tool.name.replace(/_/g, " ")}</span>
                  <ToolStatusIcon done={tool.done} />
                </li>
              ))}
            </ul>
          )}
          {run.todos.length > 0 && <TodoPanel todos={run.todos} />}
          {process && <ReasoningTicker text={process} />}
        </ThinkingBlock>
        {answer && <Markdown animateWords>{answer}</Markdown>}
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
  runs,
  error,
  disabled,
  onSend,
  onResume,
}: {
  chatId: string;
  runs: RunState[];
  error: string | null;
  disabled: boolean;
  onSend: (content: string) => Promise<boolean>;
  onResume: (decisions: Decision[]) => Promise<boolean>;
}) {
  const messages = useMessages(chatId);
  const pending = usePending(chatId);
  const live = runs.some((run) => !run.done);
  const pendingApproval = live ? null : (pending.data ?? null);
  const pendingId = pendingApproval?.interrupt_id ?? null;
  const bottomRef = useRef<HTMLDivElement>(null);
  const firstBase = runs[0]?.baseCount;
  const history = firstBase === undefined ? messages.data : messages.data?.slice(0, firstBase);
  const latest = runs[runs.length - 1];
  const historyCount = history?.length ?? 0;
  const latestText = latest?.text ?? "";
  const latestSteps = (latest?.tools.length ?? 0) + (latest?.todos.length ?? 0);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [historyCount, runs.length, latestText, latestSteps, pendingId]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-6 py-8">
          {messages.isPending && <p className="text-sm text-muted-foreground">Loading conversation…</p>}
          {messages.error && <p className="text-sm text-destructive">{messages.error.message}</p>}
          {history?.map((message) => (
            <MessageBubble key={message.id} role={message.role} content={message.content} thinking={message.thinking} />
          ))}
          {history?.length === 0 && runs.length === 0 && (
            <p className="text-center text-sm text-muted-foreground">
              Describe the outcome you want to model. Dana will ask about your data before training.
            </p>
          )}
          {runs.map((run) => (
            <Fragment key={run.id}>
              {run.userContent !== null && <MessageBubble role="user" content={run.userContent} />}
              <AssistantTurn run={run} />
            </Fragment>
          ))}
          {pendingApproval && (
            <ApprovalPanel
              key={pendingApproval.interrupt_id}
              pending={pendingApproval}
              disabled={disabled}
              onSubmit={(decisions) => void onResume(decisions)}
            />
          )}
          <div ref={bottomRef} />
        </div>
      </div>
      <div className="border-t border-border px-6 py-4">
        <div className="mx-auto w-full max-w-3xl">
          <ErrorBanner message={error} />
          <Composer
            disabled={disabled || Boolean(pendingApproval)}
            placeholder={pendingApproval ? "Respond to the request above to continue" : "Message Dana…"}
            onSend={onSend}
          />
        </div>
      </div>
    </div>
  );
}


export function ChatWindow() {
  const token = useAccessToken();
  const queryClient = useQueryClient();
  const chats = useChats();
  const activeChatId = useChatSelection((state) => state.activeChatId);
  const selectChat = useChatSelection((state) => state.select);
  const busy = useChatSelection((state) => state.busy);
  const setBusy = useChatSelection((state) => state.setBusy);
  const [runs, setRuns] = useState<Record<string, RunState[]>>({});
  const [error, setError] = useState<{ chatId: string | null; message: string } | null>(null);
  const inFlight = useRef(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  useEffect(() => {
    void useChatSelection.persist.rehydrate();
  }, []);

  useEffect(() => {
    if (busy || !chats.data || !activeChatId) return;
    if (!chats.data.some((chat) => chat.id === activeChatId)) selectChat(null);
  }, [busy, chats.data, activeChatId, selectChat]);

  const visibleError = error && error.chatId === activeChatId ? error.message : null;

  const activeTitle = chats.data?.find((chat) => chat.id === activeChatId)?.title ?? "Chat";

  async function runTurn(
    token: string,
    chatId: string | null,
    userContent: string | null,
    start: (target: string, signal: AbortSignal, handlers: StreamHandlers) => Promise<void>,
  ): Promise<boolean> {
    if (inFlight.current) return false;
    inFlight.current = true;
    setBusy(true);
    setError(null);
    const controller = new AbortController();
    abortRef.current = controller;
    const runId = crypto.randomUUID();
    let target = chatId;
    let runChatId: string | null = null;
    let streamed = false;
    const patch = (chat: string, update: (run: RunState) => RunState) =>
      setRuns((prev) => ({
        ...prev,
        [chat]: (prev[chat] ?? []).map((run) => (run.id === runId ? update(run) : run)),
      }));
    try {
      if (!target) {
        target = (await createChat(token)).id;
        selectChat(target);
      }
      const chat = target;
      runChatId = chat;
      const saved = await queryClient.ensureQueryData({
        queryKey: ["messages", token, chat],
        queryFn: () => apiGet<ChatMessage[]>(`/api/v1/chats/${chat}/messages`, token),
      });
      const run: RunState = {
        id: runId,
        userContent,
        text: "",
        boundary: 0,
        tools: [],
        todos: [],
        baseCount: saved.length,
        done: false,
      };
      setRuns((prev) => ({ ...prev, [chat]: [...(prev[chat] ?? []), run] }));
      await start(chat, controller.signal, {
        onToken: (text) => {
          streamed = true;
          patch(chat, (current) => ({ ...current, text: current.text + text }));
        },
        onTodos: (todos) => patch(chat, (current) => ({ ...current, todos })),
        onToolCall: ({ id, name }) => {
          streamed = true;
          patch(chat, (current) => ({
            ...current,
            boundary: current.text.length,
            tools: [...current.tools, { id, name, done: false }],
          }));
        },
        onToolResult: ({ id }) =>
          patch(chat, (current) => ({
            ...current,
            boundary: current.text.length,
            tools: current.tools.map((tool) => (tool.id === id ? { ...tool, done: true } : tool)),
          })),
        onInterrupt: (pending) => queryClient.setQueryData(["pending", token, chat], pending),
      });
      return true;
    } catch (err) {
      if (controller.signal.aborted) return true;
      setError({ chatId: target, message: err instanceof Error ? err.message : "Something went wrong" });
      return streamed;
    } finally {
      if (runChatId) {
        const finished = runChatId;
        await queryClient.invalidateQueries({ queryKey: ["messages", token, finished] });
        await queryClient.invalidateQueries({ queryKey: ["pending", token, finished] });
        await queryClient.invalidateQueries({ queryKey: ["chats", token] });
        setRuns((prev) => ({
          ...prev,
          [finished]: (prev[finished] ?? []).map((run) => (run.id === runId ? { ...run, done: true } : run)),
        }));
      }
      abortRef.current = null;
      inFlight.current = false;
      setBusy(false);
    }
  }

  function sendMessage(content: string): Promise<boolean> {
    if (!token) return Promise.resolve(false);
    return runTurn(token, activeChatId, content, (target, signal, handlers) =>
      streamChatMessage(target, content, token, handlers, signal),
    );
  }

  function resumeRun(decisions: Decision[]): Promise<boolean> {
    if (!token || !activeChatId) return Promise.resolve(false);
    return runTurn(token, activeChatId, null, (target, signal, handlers) => {
      queryClient.setQueryData(["pending", token, target], null);
      return resumeChat(target, decisions, token, handlers, signal);
    });
  }

  const composerDisabled = !token || busy;

  return (
    <div className="flex h-dvh min-h-0 min-w-0 flex-1 flex-col">
      <header className="flex items-center border-b border-border px-6 py-4 md:px-10">
        <h1 className="truncate text-sm font-semibold">{activeChatId ? activeTitle : "Chat"}</h1>
      </header>

      {activeChatId ? (
        <ChatThread
          key={activeChatId}
          chatId={activeChatId}
          runs={activeChatId ? (runs[activeChatId] ?? []) : []}
          error={visibleError}
          disabled={composerDisabled}
          onSend={sendMessage}
          onResume={resumeRun}
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
              <ErrorBanner message={visibleError} />
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
  );
}
