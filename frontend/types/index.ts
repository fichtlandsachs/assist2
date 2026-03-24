// ─── Auth ───────────────────────────────────────────────────────
export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
}

// ─── User ────────────────────────────────────────────────────────
export interface IdentityLink {
  id: string;
  provider: "google" | "github" | "apple";
  provider_email: string | null;
}

export interface User {
  id: string;
  email: string;
  display_name: string;
  avatar_url: string | null;
  locale: string;
  timezone: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  identity_links?: IdentityLink[];
}

// ─── Organization ────────────────────────────────────────────────
export interface Organization {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  logo_url: string | null;
  plan: "free" | "pro" | "enterprise";
  is_active: boolean;
  max_members: number | null;
  created_at: string;
}

// ─── Membership ──────────────────────────────────────────────────
export interface Membership {
  id: string;
  user: User;
  organization_id: string;
  status: "active" | "invited" | "suspended";
  roles: Role[];
  joined_at: string | null;
  invited_at: string | null;
}

// ─── Role & Permission ───────────────────────────────────────────
export interface Permission {
  id: string;
  resource: string;
  action: string;
  description: string | null;
}

export interface Role {
  id: string;
  name: string;
  description: string | null;
  is_system: boolean;
  organization_id: string | null;
  permissions: Permission[];
}

// ─── Group ───────────────────────────────────────────────────────
export type GroupType = "team" | "department" | "project";

export interface Group {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  type: GroupType;
  is_active: boolean;
  parent_group_id: string | null;
  created_at: string;
}

export interface GroupMember {
  id: string;
  member_type: "user" | "agent";
  user?: User;
  agent_id?: string;
  role: "member" | "lead";
  added_at: string;
}

// ─── Agent ───────────────────────────────────────────────────────
export type AgentRole =
  | "scrum_master" | "architect" | "coding" | "security"
  | "performance" | "ux" | "database" | "network"
  | "deploy" | "testing" | "documentation_training";

export interface Agent {
  id: string;
  organization_id: string;
  name: string;
  role: AgentRole;
  model: string;
  is_active: boolean;
  created_at: string;
}

// ─── Plugin ──────────────────────────────────────────────────────
export type PluginType = "ui" | "provider" | "action" | "hybrid";
export type PluginCapability =
  | "ai_assistance" | "workflow_integration" | "group_assignment"
  | "notification_push" | "file_upload" | "real_time_updates"
  | "export_pdf" | "import_csv";

export interface PluginNavEntry {
  id: string;
  label: string;
  icon: string;
  route: string;
  slot: string;
  position: number;
}

export interface PluginSlotMount {
  pluginSlug: string;
  slotId: string;
  component: string;
  position: number;
}

export interface Plugin {
  id: string;
  slug: string;
  name: string;
  version: string;
  type: PluginType;
  is_active: boolean;
  requires_config: boolean;
}

export interface OrgPlugin {
  plugin: Plugin;
  is_enabled: boolean;
  config: Record<string, unknown>;
  activated_at: string;
}

// ─── Workflow ────────────────────────────────────────────────────
export type TriggerType = "webhook" | "schedule" | "event" | "manual";
export type ExecutionStatus = "pending" | "running" | "success" | "failed" | "cancelled";

export interface WorkflowDefinition {
  id: string;
  name: string;
  slug: string;
  version: number;
  description: string | null;
  trigger_type: TriggerType;
  is_active: boolean;
  created_at: string;
}

export interface WorkflowExecution {
  id: string;
  definition_id: string;
  definition_version: number;
  status: ExecutionStatus;
  triggered_by: string | null;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
}

// ─── User Story ──────────────────────────────────────────────────
export type StoryStatus = "draft" | "in_review" | "ready" | "in_progress" | "testing" | "done" | "archived";
export type StoryPriority = "low" | "medium" | "high" | "critical";
export type EpicStatus = "planning" | "in_progress" | "done" | "archived";
export type FeatureStatus = "draft" | "in_progress" | "testing" | "done" | "archived";

export interface Epic {
  id: string;
  organization_id: string;
  created_by_id: string;
  title: string;
  description: string | null;
  status: EpicStatus;
  created_at: string;
  updated_at: string;
}

export interface UserStory {
  id: string;
  organization_id: string;
  created_by_id: string;
  title: string;
  description: string | null;
  acceptance_criteria: string | null;
  status: StoryStatus;
  priority: StoryPriority;
  story_points: number | null;
  dor_passed: boolean;
  quality_score: number | null;
  ai_suggestions: string | null;
  is_split: boolean;
  epic_id: string | null;
  parent_story_id: string | null;
  definition_of_done: string | null;
  doc_additional_info: string | null;
  doc_workarounds: string | null;
  created_at: string;
  updated_at: string;
}

export interface Feature {
  id: string;
  organization_id: string;
  story_id: string;
  story_title: string | null;
  epic_id: string | null;
  created_by_id: string;
  title: string;
  description: string | null;
  status: FeatureStatus;
  priority: StoryPriority;
  story_points: number | null;
  created_at: string;
  updated_at: string;
}

export interface DoDItem {
  text: string;
  done: boolean;
}

export interface AISuggestion {
  title: string | null;
  description: string | null;
  acceptance_criteria: string | null;
  explanation: string;
  dor_issues: string[];
  quality_score: number;
}

// ─── Pagination ──────────────────────────────────────────────────
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

// ─── API Error ───────────────────────────────────────────────────
export interface ApiError {
  error: string;
  code: string;
  details: Record<string, unknown>;
}

// ─── TestCase ─────────────────────────────────────────────────────
export type TestResult = "pending" | "passed" | "failed" | "skipped";
export interface TestCase {
  id: string;
  story_id: string;
  organization_id: string;
  created_by_id: string;
  title: string;
  description: string | null;
  steps: string | null;
  expected_result: string | null;
  result: TestResult;
  notes: string | null;
  is_ai_generated: boolean;
  created_at: string;
  updated_at: string;
}

// ─── Mail ─────────────────────────────────────────────────────────
export type MailProvider = "gmail" | "outlook" | "imap";
export type MessageStatus = "unread" | "read" | "archived" | "deleted";
export interface MailConnection {
  id: string;
  organization_id: string;
  provider: MailProvider;
  email_address: string;
  display_name: string | null;
  is_active: boolean;
  last_sync_at: string | null;
  created_at: string;
}
export interface Message {
  id: string;
  connection_id: string;
  subject: string | null;
  sender_email: string;
  sender_name: string | null;
  snippet: string | null;
  body_text: string | null;
  status: MessageStatus;
  topic_cluster: string | null;
  received_at: string | null;
  created_at: string;
}

// ─── Calendar ─────────────────────────────────────────────────────
export type CalendarProvider = "google" | "outlook";
export type EventStatus = "confirmed" | "tentative" | "cancelled";
export interface CalendarConnection {
  id: string;
  organization_id: string;
  provider: CalendarProvider;
  email_address: string;
  display_name: string | null;
  is_active: boolean;
  last_sync_at: string | null;
  created_at: string;
}
export interface CalendarEvent {
  id: string;
  connection_id: string;
  external_id: string;
  title: string;
  description: string | null;
  location: string | null;
  start_at: string;
  end_at: string;
  all_day: boolean;
  status: EventStatus;
  organizer_email: string | null;
  created_at: string;
}
