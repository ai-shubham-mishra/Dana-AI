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
  todos?: TodoItem[];
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
  value?: unknown;
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

export type DeleteJobsResult = {
  deleted: string[];
  skipped: { id: string; reason: string }[];
};

export type JobDetail = JobSummary & {
  params: Record<string, unknown> | null;
  metrics: Record<string, unknown> | null;
  artifact: JobArtifact | null;
  artifacts: JobArtifact[];
  events: JobEvent[];
};

export type ModelSummary = {
  id: string;
  name: string;
  latest_version: number;
  version_count: number;
  created_at: string;
  updated_at: string;
};

export type ModelVersion = {
  model_id: string;
  version: number;
  job_id: string;
  source: string;
  source_version: number | null;
  kpi: string | null;
  params: Record<string, unknown> | null;
  metrics: Record<string, unknown> | null;
  created_by_email: string | null;
  tags: string[];
  created_at: string;
};

export type ModelEvent = {
  action: string;
  version: number | null;
  actor_email: string | null;
  detail: string | null;
  created_at: string;
};

export type ModelDetail = ModelSummary & {
  versions: ModelVersion[];
  events: ModelEvent[];
};

export type DeploymentStatus = "provisioning" | "running" | "stopped" | "failed" | string;

export type DeploymentHealthState = "live" | "unhealthy" | "unreachable" | DeploymentStatus;

export type Deployment = {
  id: string;
  model_id: string;
  version: number;
  job_id: string;
  status: DeploymentStatus;
  host_port: number;
  url: string;
  container: string;
  message: string | null;
  stage: string | null;
  percent: number;
  error: string | null;
  created_by_email: string | null;
  created_at: string;
  updated_at: string;
  health: { state: DeploymentHealthState; detail: string | null };
};

export type ArchivedDeployment = {
  id: string;
  model_id: string;
  version: number;
  status: DeploymentStatus;
  host_port: number;
  container: string;
  created_by_email: string | null;
  created_at: string;
  archived_at: string;
  purge_at: string;
  days_remaining: number;
};

export type RetrainResult = { job_id: string };

export type DeleteModelResult = {
  outcome: "deleted" | "archived" | "blocked" | string;
  versions?: number[];
  deleted?: number[];
  deallocated?: unknown[];
};

export type PlanVisibility = "private" | "org";

export type PlanSpec = Record<string, unknown>;

export type Plan = {
  id: string;
  name: string;
  description: string;
  visibility: PlanVisibility;
  spec: PlanSpec;
  owner_id: string;
  owner_email: string | null;
  is_owner: boolean;
};

export type PlanInput = {
  name: string;
  description: string;
  visibility: PlanVisibility;
  spec: PlanSpec;
};

export type PlanRunResult = { job_id: string };

export type PlanNameConflict = {
  code: "name_taken";
  name: string;
  suggestions: string[];
};
