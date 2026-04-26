import type { ComponentStatus, OrgMetrics, ConfigMap, OrgIntegrationSettings, UserWithOrgs } from "@/types";
import { getSession, clearSession } from "@/lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";
const API_FALLBACK_BASE = process.env.NEXT_PUBLIC_API_FALLBACK_URL ?? "https://heykarl.app";

function buildCandidateUrls(path: string): string[] {
  const urls: string[] = [];
  const primary = `${API_BASE}${path}`;
  urls.push(primary);

  // If API_BASE is not explicitly configured, try known fallback host too.
  if (!API_BASE) {
    // Browser-only hint: admin host often needs backend fallback to heykarl.app.
    if (typeof window !== "undefined" && window.location.hostname.includes("admin.")) {
      urls.push(`${API_FALLBACK_BASE}${path}`);
    } else if (typeof window === "undefined") {
      // SSR/build safety fallback
      urls.push(`${API_FALLBACK_BASE}${path}`);
    }
  } else if (API_BASE !== API_FALLBACK_BASE) {
    // Optional second chance when explicit API_BASE misroutes to 404
    urls.push(`${API_FALLBACK_BASE}${path}`);
  }

  return Array.from(new Set(urls));
}

async function adminFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const session = getSession();
  if (!session) {
    window.location.href = "/login";
    throw new Error("No session");
  }

  const candidateUrls = buildCandidateUrls(path);
  let resp: Response | null = null;
  let lastErr: unknown = null;

  for (const url of candidateUrls) {
    try {
      const r = await fetch(url, {
        ...init,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session.access_token}`,
          ...init?.headers,
        },
      });
      // Stop on first non-404 response to preserve normal semantics.
      if (r.status !== 404) {
        resp = r;
        break;
      }
      resp = r; // keep for final error if all are 404
    } catch (e) {
      lastErr = e;
    }
  }

  if (!resp) {
    throw new Error(lastErr ? String(lastErr) : "Network request failed");
  }

  if (resp.status === 401 || resp.status === 403) {
    clearSession();
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }

  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

async function knowledgeFetch<T>(pathAfterPrefix: string, init?: RequestInit): Promise<T> {
  const primary = `/api/v1/superadmin/knowledge-sources/${pathAfterPrefix}`;
  const legacy = `/api/v1/knowledge-sources/${pathAfterPrefix}`;
  try {
    return await adminFetch<T>(primary, init);
  } catch (e: any) {
    if (String(e?.message || "").includes("HTTP 404")) {
      return adminFetch<T>(legacy, init);
    }
    throw e;
  }
}

export async function fetchComponentStatus(): Promise<ComponentStatus[]> {
  return adminFetch<ComponentStatus[]>("/api/v1/superadmin/status");
}

export async function fetchOrganizations(): Promise<OrgMetrics[]> {
  const data = await adminFetch<{ items: OrgMetrics[] }>("/api/v1/superadmin/organizations?page_size=100");
  return data.items;
}

export async function fetchConfig(): Promise<ConfigMap> {
  return adminFetch<ConfigMap>("/api/v1/superadmin/config/");
}

export async function patchConfig(key: string, value: string | null): Promise<void> {
  await adminFetch<void>("/api/v1/superadmin/config/", {
    method: "PATCH",
    body: JSON.stringify({ key, value }),
  });
}

export async function fetchOrgIntegrations(orgId: string): Promise<OrgIntegrationSettings> {
  return adminFetch<OrgIntegrationSettings>(`/api/v1/superadmin/organizations/${orgId}/integrations`);
}

export async function fetchUsersWithOrgs(search?: string): Promise<UserWithOrgs[]> {
  const qs = search ? `&search=${encodeURIComponent(search)}` : "";
  const data = await adminFetch<{ items: UserWithOrgs[] }>(`/api/v1/superadmin/users?page_size=100${qs}`);
  return data.items;
}

export async function patchOrgIntegration(
  orgId: string,
  type: "jira" | "confluence" | "github" | "atlassian",
  data: Record<string, unknown>,
): Promise<void> {
  await adminFetch<void>(`/api/v1/superadmin/organizations/${orgId}/integrations/${type}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

// ── External Documentation Sources ──────────────────────────────────────────

export interface ExternalSource {
  id: string;
  source_key: string;
  display_name: string;
  source_type: string;
  base_url: string;
  config_json: Record<string, unknown>;
  visibility_scope: string;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface ExternalSourceRun {
  id: string;
  source_id: string;
  run_type: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  stats_json: Record<string, unknown>;
  error_summary: string | null;
  triggered_by: string | null;
  created_at: string;
}

export interface ExternalSourcePage {
  id: string;
  source_id: string;
  raw_url: string;
  canonical_url: string;
  status: string;
  discovered_at: string | null;
  fetched_at: string | null;
  extracted_at: string | null;
  http_status: number | null;
  fetch_method: string | null;
  content_hash: string | null;
  is_active: boolean;
  error_detail: string | null;
  metadata_json: Record<string, unknown>;
}

export interface PreviewResult {
  canonical_url: string;
  title: string;
  breadcrumb: string[];
  headings: string[];
  plain_text_preview: string;
  chunk_count: number;
  fetch_method: string;
  extraction_quality_score: number;
}

export async function listExternalSources(): Promise<ExternalSource[]> {
  return knowledgeFetch<ExternalSource[]>("external");
}

export async function getExternalSource(id: string): Promise<ExternalSource> {
  return knowledgeFetch<ExternalSource>(`external/${id}`);
}

export async function createExternalSource(body: unknown): Promise<ExternalSource> {
  return knowledgeFetch<ExternalSource>("external", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function disableExternalSource(id: string): Promise<void> {
  await knowledgeFetch<void>(`external/${id}/disable`, { method: "POST" });
}

export async function startIngest(id: string): Promise<{ run_id: string; status: string; message: string }> {
  return knowledgeFetch(`external/${id}/ingest`, { method: "POST" });
}

export async function startRefresh(id: string): Promise<{ run_id: string; status: string; message: string }> {
  return knowledgeFetch(`external/${id}/refresh`, { method: "POST" });
}

export async function retryFailures(id: string): Promise<{ run_id: string; status: string; message: string }> {
  return knowledgeFetch(`external/${id}/retry-failures`, { method: "POST" });
}

export async function listRuns(id: string): Promise<ExternalSourceRun[]> {
  return knowledgeFetch<ExternalSourceRun[]>(`external/${id}/runs`);
}

export async function listPages(id: string, status?: string, limit = 100, offset = 0): Promise<ExternalSourcePage[]> {
  const qs = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (status) qs.set("page_status", status);
  return knowledgeFetch<ExternalSourcePage[]>(`external/${id}/pages?${qs}`);
}

export async function listFailures(id: string): Promise<ExternalSourcePage[]> {
  return knowledgeFetch<ExternalSourcePage[]>(`external/${id}/failures`);
}

export async function previewPage(id: string, url: string): Promise<PreviewResult> {
  return knowledgeFetch<PreviewResult>(`external/${id}/preview?page_url=${encodeURIComponent(url)}`);
}

// ── Conversation Engine ───────────────────────────────────────────────────

export interface DialogProfile {
  id: string;
  key: string;
  name: string;
  description: string | null;
  mode: string;
  tone: string;
  is_default: boolean;
  is_active: boolean;
  config_json: Record<string, unknown>;
  version: number;
}

export interface QuestionBlock {
  id: string;
  key: string;
  category: string;
  label: string;
  question_text: string;
  follow_up_text: string | null;
  priority: number;
  is_required: boolean;
  is_active: boolean;
  version: number;
}

export interface AnswerSignal {
  id: string;
  key: string;
  fact_category: string;
  pattern_type: string;
  pattern: string;
  confidence_boost: number;
  is_active: boolean;
}

export interface PromptTemplate {
  id: string;
  key: string;
  name: string;
  description: string | null;
  system_prompt: string;
  user_prompt: string;
  variables: string[];
  is_active: boolean;
  version: number;
}

export interface ConversationRule {
  id: string;
  key: string;
  rule_type: string;
  label: string;
  value_json: Record<string, unknown>;
  is_active: boolean;
  version: number;
}

export interface SizingRule {
  id: string;
  key: string;
  label: string;
  dimension: string;
  weight: number;
  thresholds_json: Record<string, unknown>;
  is_active: boolean;
}

export interface ReadinessRule {
  id: string;
  key: string;
  label: string;
  required_category: string;
  min_confidence: number;
  is_blocking: boolean;
  weight: number;
  is_active: boolean;
}

export async function listDialogProfiles(): Promise<DialogProfile[]> {
  return adminFetch<DialogProfile[]>("/api/v1/superadmin/conversation-engine/profiles");
}

export async function createDialogProfile(body: unknown): Promise<DialogProfile> {
  return adminFetch<DialogProfile>("/api/v1/superadmin/conversation-engine/profiles", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateDialogProfile(id: string, body: unknown): Promise<DialogProfile> {
  return adminFetch<DialogProfile>(`/api/v1/superadmin/conversation-engine/profiles/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function listQuestionBlocks(): Promise<QuestionBlock[]> {
  return adminFetch<QuestionBlock[]>("/api/v1/superadmin/conversation-engine/question-blocks");
}

export async function createQuestionBlock(body: unknown): Promise<QuestionBlock> {
  return adminFetch<QuestionBlock>("/api/v1/superadmin/conversation-engine/question-blocks", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateQuestionBlock(id: string, body: unknown): Promise<QuestionBlock> {
  return adminFetch<QuestionBlock>(`/api/v1/superadmin/conversation-engine/question-blocks/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function deleteQuestionBlock(id: string): Promise<void> {
  await adminFetch<void>(`/api/v1/superadmin/conversation-engine/question-blocks/${id}`, { method: "DELETE" });
}

export async function listAnswerSignals(): Promise<AnswerSignal[]> {
  return adminFetch<AnswerSignal[]>("/api/v1/superadmin/conversation-engine/answer-signals");
}

export async function createAnswerSignal(body: unknown): Promise<AnswerSignal> {
  return adminFetch<AnswerSignal>("/api/v1/superadmin/conversation-engine/answer-signals", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateAnswerSignal(id: string, body: unknown): Promise<AnswerSignal> {
  return adminFetch<AnswerSignal>(`/api/v1/superadmin/conversation-engine/answer-signals/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function listPromptTemplates(): Promise<PromptTemplate[]> {
  return adminFetch<PromptTemplate[]>("/api/v1/superadmin/conversation-engine/prompt-templates");
}

export async function createPromptTemplate(body: unknown): Promise<PromptTemplate> {
  return adminFetch<PromptTemplate>("/api/v1/superadmin/conversation-engine/prompt-templates", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function listConversationRules(): Promise<ConversationRule[]> {
  return adminFetch<ConversationRule[]>("/api/v1/superadmin/conversation-engine/rules");
}

export async function createConversationRule(body: unknown): Promise<ConversationRule> {
  return adminFetch<ConversationRule>("/api/v1/superadmin/conversation-engine/rules", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateConversationRule(id: string, body: unknown): Promise<ConversationRule> {
  return adminFetch<ConversationRule>(`/api/v1/superadmin/conversation-engine/rules/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function listSizingRules(): Promise<SizingRule[]> {
  return adminFetch<SizingRule[]>("/api/v1/superadmin/conversation-engine/sizing-rules");
}

export async function createSizingRule(body: unknown): Promise<SizingRule> {
  return adminFetch<SizingRule>("/api/v1/superadmin/conversation-engine/sizing-rules", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateSizingRule(id: string, body: unknown): Promise<SizingRule> {
  return adminFetch<SizingRule>(`/api/v1/superadmin/conversation-engine/sizing-rules/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function listReadinessRules(): Promise<ReadinessRule[]> {
  return adminFetch<ReadinessRule[]>("/api/v1/superadmin/conversation-engine/readiness-rules");
}

export async function createReadinessRule(body: unknown): Promise<ReadinessRule> {
  return adminFetch<ReadinessRule>("/api/v1/superadmin/conversation-engine/readiness-rules", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateReadinessRule(id: string, body: unknown): Promise<ReadinessRule> {
  return adminFetch<ReadinessRule>(`/api/v1/superadmin/conversation-engine/readiness-rules/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

// ── Knowledge / RAG ──────────────────────────────────────────────────────────

export interface RagStats {
  total_sources: number;
  enabled_sources: number;
  disabled_sources: number;
  total_chunks: number;
  chunks_with_embedding: number;
  chunks_missing_embedding: number;
  pending_runs: number;
  running_runs: number;
  per_source: Array<{
    id: string;
    display_name: string;
    source_key: string;
    is_enabled: boolean;
    chunk_count: number;
  }>;
}

export interface ChunkBrowserResult {
  total: number;
  limit: number;
  offset: number;
  chunks: Array<{
    id: string;
    source_ref: string;
    source_url: string | null;
    source_title: string | null;
    chunk_index: number;
    chunk_text: string;
    chunk_text_length: number;
    has_embedding: boolean;
    is_global: boolean;
    created_at: string;
  }>;
}

export interface SearchTestResult {
  mode: string;
  query: string;
  retrieval_type: string;
  chunk_count: number;
  chunks: Array<{
    text: string;
    source_url?: string | null;
    source_title?: string | null;
    source_system?: string;
    source_type?: string;
    chunk_type?: string;
    semantic_score?: number;
    bm25_score?: number;
    final_score?: number;
    score?: number;
    trust_class?: string;
    trust_score?: number;
    evidence_type?: string;
    is_global?: boolean;
    indexed_at?: string | null;
  }>;
  conflicts?: Array<{ type: string; description: string }>;
  guardrail_warnings?: string[];
}

export async function getRagStats(): Promise<RagStats> {
  return knowledgeFetch<RagStats>("stats");
}

export async function enableExternalSource(id: string): Promise<{ status: string; run_id?: string }> {
  return knowledgeFetch(`external/${id}/enable`, { method: "POST" });
}

export async function deindexExternalSource(id: string): Promise<{ status: string; chunks_removed: number }> {
  return knowledgeFetch(`external/${id}/deindex`, { method: "POST" });
}

export async function getChunkStats(id: string): Promise<{ source_id: string; indexed_chunks: number }> {
  return knowledgeFetch(`external/${id}/chunk-stats`);
}

export async function listChunks(id: string, q?: string, limit = 50, offset = 0): Promise<ChunkBrowserResult> {
  const qs = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (q) qs.set("q", q);
  return knowledgeFetch<ChunkBrowserResult>(`external/${id}/chunks?${qs}`);
}

export async function searchTest(body: {
  query: string;
  org_id?: string;
  use_hybrid?: boolean;
  min_score?: number;
  max_chunks?: number;
  source_types?: string[];
}): Promise<SearchTestResult> {
  return knowledgeFetch<SearchTestResult>("search-test", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
