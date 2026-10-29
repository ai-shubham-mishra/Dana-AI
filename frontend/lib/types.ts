export type Me = {
  user_id: string;
  org_id: string;
  email: string | null;
  role: string;
};

export type ChatSummary = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
};

export type TodoItem = {
  content: string;
  status: "pending" | "in_progress" | "completed" | string;
};

export type DecisionType = "approve" | "edit" | "reject" | "respond";

export type PendingAction = {
  name: string;
  args: Record<string, unknown>;
  description: string;
  allowed_decisions: DecisionType[];
};

export type PendingApproval = {
  interrupt_id: string;
  actions: PendingAction[];
};

export type Decision = {
  type: DecisionType;
  message?: string;
  edited_action?: { name: string; args: Record<string, unknown> };
};

export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled" | string;

export type JobSummary = {
  id: string;
  title: string;
  kind: string;
  status: JobStatus;
  created_at: string;
  updated_at: string;
};
