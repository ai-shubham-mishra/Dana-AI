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
  thinking?: string | null;
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
  stage: string | null;
  percent: number;
  message: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
};

export type ConnectorColumn = { name: string; data_type: string };

export type ConnectorSummary = {
  name: string;
  row_estimate: number | null;
  org_scoped: boolean;
  columns: ConnectorColumn[];
};

export type ConnectorPage = {
  name: string;
  org_scoped: boolean;
  columns: ConnectorColumn[];
  rows: (string | number | boolean | null)[][];
  page: number;
  page_size: number;
  total_rows: number;
  total_pages: number;
};

export type JobEvent = {
  stage: string;
  percent: number;
  message: string;
  created_at: string;
};

export type JobArtifact = {
  name: string;
  bytes: number;
};

export type JobDetail = JobSummary & {
  params: Record<string, unknown> | null;
  metrics: Record<string, unknown> | null;
  artifact: JobArtifact | null;
  events: JobEvent[];
};
