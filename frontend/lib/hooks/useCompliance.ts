// lib/hooks/useCompliance.ts
"use client";

import useSWR, { mutate as globalMutate } from "swr";
import { fetcher, authFetch } from "@/lib/api/client";

const BASE = "/api/v1/compliance";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface AssessmentSummary {
  id: string;
  org_id: string;
  object_type: string;
  object_id: string;
  object_name: string;
  context_params: Record<string, unknown>;
  total_controls: number;
  fulfilled_controls: number;
  deviation_controls: number;
  not_assessed_controls: number;
  hard_stop_total: number;
  hard_stop_critical: number;
  overall_score: number | null;
  traffic_light: "green" | "yellow" | "red" | "grey";
  compliance_status: "compliant" | "partially_compliant" | "non_compliant" | "not_assessed";
  gate_readiness: Record<string, GateReadinessEntry>;
  created_at: string;
  updated_at: string;
  last_refreshed_at: string | null;
}

export interface GateReadinessEntry {
  status: "ready" | "conditional" | "blocked" | "incomplete" | "not_applicable";
  blocking_count?: number;
  blocking_controls?: string[];
  unassessed_count?: number;
  avg_score?: number;
}

export interface AssessmentItem {
  id: string;
  control_id: string;
  control_slug: string;
  control_name: string;
  control_kind: "fixed" | "dynamic";
  category_name: string | null;
  gate_phases: string[];
  hard_stop: boolean;
  activation_source: "fixed" | "trigger" | "gate" | "manual";
  activating_trigger_name: string | null;
  score: number;
  status: "open" | "in_progress" | "fulfilled" | "deviation" | "not_fulfilled" | "not_assessable";
  traffic_light: "green" | "yellow" | "red" | "grey";
  blocks_gate: boolean;
  responsible_role: string | null;
  assessed_by_name: string | null;
  assessed_at: string | null;
  evidence_status: "complete" | "partial" | "missing";
  approval_status: "pending" | "approved" | "rejected";
  updated_at: string;
}

export interface AssessmentItemDetail extends AssessmentItem {
  control_objective: string | null;
  why_relevant: string | null;
  what_to_check: string | null;
  guiding_questions: string[];
  required_evidence_types: unknown[];
  control_version: number;
  activating_trigger_id: string | null;
  activating_gate: string | null;
  rationale: string | null;
  residual_risk: string | null;
  evidence_comment: string | null;
  hard_stop_threshold: number;
  default_weight: number;
  approved_by: string | null;
  approved_at: string | null;
  evidence_links: EvidenceLink[];
  actions: ComplianceAction[];
  score_history: ScoreHistoryEntry[];
}

export interface EvidenceLink {
  id: string;
  evidence_type_slug: string | null;
  evidence_type_name: string | null;
  file_name: string | null;
  file_url: string | null;
  external_ref: string | null;
  description: string | null;
  is_mandatory: boolean;
  uploaded_at: string;
}

export interface ComplianceAction {
  id: string;
  title: string;
  description: string | null;
  status: "open" | "in_progress" | "done" | "escalated" | "overdue";
  priority: "low" | "medium" | "high";
  owner_name: string | null;
  due_date: string | null;
  escalation_note: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface ScoreHistoryEntry {
  id: string;
  from_score: number;
  to_score: number;
  from_status: string | null;
  to_status: string | null;
  rationale: string | null;
  gate_impact: string | null;
  changed_by_name: string | null;
  created_at: string;
}

export interface StatusSnapshot {
  id: string;
  trigger_reason: string;
  compliance_status: string;
  overall_score: number | null;
  traffic_light: string;
  gate_readiness: Record<string, GateReadinessEntry>;
  summary: Record<string, number>;
  created_at: string;
}

export interface ItemsResponse {
  total: number;
  page: number;
  page_size: number;
  items: AssessmentItem[];
}

// ── Hooks ─────────────────────────────────────────────────────────────────────

export function useAssessmentByObject(objectType: string, objectId: string | null) {
  return useSWR<AssessmentSummary>(
    objectId ? `${BASE}/assessments/by-object?object_type=${objectType}&object_id=${objectId}` : null,
    fetcher,
    { revalidateOnFocus: false }
  );
}

export function useAssessment(assessmentId: string | null) {
  return useSWR<AssessmentSummary>(
    assessmentId ? `${BASE}/assessments/${assessmentId}` : null,
    fetcher
  );
}

export function useAssessmentItems(
  assessmentId: string | null,
  filters?: {
    gate_phase?: string;
    control_kind?: string;
    activation_source?: string;
    status_filter?: string;
    hard_stop_only?: boolean;
    blocks_gate_only?: boolean;
    no_evidence_only?: boolean;
    search?: string;
    page?: number;
    page_size?: number;
  }
) {
  const query = new URLSearchParams();
  if (filters?.gate_phase) query.set("gate_phase", filters.gate_phase);
  if (filters?.control_kind) query.set("control_kind", filters.control_kind);
  if (filters?.activation_source) query.set("activation_source", filters.activation_source);
  if (filters?.status_filter) query.set("status_filter", filters.status_filter);
  if (filters?.hard_stop_only) query.set("hard_stop_only", "true");
  if (filters?.blocks_gate_only) query.set("blocks_gate_only", "true");
  if (filters?.no_evidence_only) query.set("no_evidence_only", "true");
  if (filters?.search) query.set("search", filters.search);
  if (filters?.page) query.set("page", String(filters.page));
  if (filters?.page_size) query.set("page_size", String(filters.page_size));

  return useSWR<ItemsResponse>(
    assessmentId ? `${BASE}/assessments/${assessmentId}/items?${query.toString()}` : null,
    fetcher
  );
}

export function useAssessmentItem(assessmentId: string | null, itemId: string | null) {
  return useSWR<AssessmentItemDetail>(
    assessmentId && itemId
      ? `${BASE}/assessments/${assessmentId}/items/${itemId}`
      : null,
    fetcher
  );
}

export function useSnapshots(assessmentId: string | null) {
  return useSWR<StatusSnapshot[]>(
    assessmentId ? `${BASE}/assessments/${assessmentId}/snapshots` : null,
    fetcher
  );
}

export function useGateReadiness(assessmentId: string | null) {
  return useSWR(
    assessmentId ? `${BASE}/assessments/${assessmentId}/gate-readiness` : null,
    fetcher
  );
}

// ── Mutations ─────────────────────────────────────────────────────────────────

export async function createOrGetAssessment(data: {
  org_id: string;
  object_type: string;
  object_id: string;
  object_name: string;
  context_params?: Record<string, unknown>;
}): Promise<AssessmentSummary> {
  const res = await authFetch(`${BASE}/assessments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...data, context_params: data.context_params ?? {} }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Fehler beim Erstellen");
  }
  return res.json();
}

export async function refreshAssessment(
  assessmentId: string,
  contextParams?: Record<string, unknown>
): Promise<AssessmentSummary> {
  const res = await authFetch(`${BASE}/assessments/${assessmentId}/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(contextParams ?? null),
  });
  if (!res.ok) throw new Error("Refresh fehlgeschlagen");
  await globalMutate((key: string) => typeof key === "string" && key.includes(assessmentId));
  return res.json();
}

export async function submitScore(
  assessmentId: string,
  itemId: string,
  score: number,
  rationale?: string,
  residualRisk?: string
) {
  const res = await authFetch(`${BASE}/assessments/${assessmentId}/items/${itemId}/score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ score, rationale, residual_risk: residualRisk }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Bewertung fehlgeschlagen");
  }
  await globalMutate((key: string) => typeof key === "string" && key.includes(assessmentId));
  return res.json();
}

export async function addEvidence(
  assessmentId: string,
  itemId: string,
  data: {
    evidence_type_slug?: string;
    evidence_type_name?: string;
    file_name?: string;
    file_url?: string;
    external_ref?: string;
    description?: string;
    is_mandatory?: boolean;
  }
) {
  const res = await authFetch(`${BASE}/assessments/${assessmentId}/items/${itemId}/evidence`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Fehler beim Hinzufügen");
  }
  await globalMutate((key: string) => typeof key === "string" && key.includes(itemId));
  return res.json();
}

export async function removeEvidence(assessmentId: string, itemId: string, evId: string) {
  await authFetch(`${BASE}/assessments/${assessmentId}/items/${itemId}/evidence/${evId}`, {
    method: "DELETE",
  });
  await globalMutate((key: string) => typeof key === "string" && key.includes(itemId));
}

export async function createAction(
  assessmentId: string,
  itemId: string,
  data: { title: string; description?: string; priority?: string; owner_name?: string; due_date?: string }
) {
  const res = await authFetch(`${BASE}/assessments/${assessmentId}/items/${itemId}/actions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Fehler");
  }
  await globalMutate((key: string) => typeof key === "string" && key.includes(itemId));
  return res.json();
}

export async function updateAction(
  assessmentId: string,
  itemId: string,
  actionId: string,
  data: Record<string, unknown>
) {
  const res = await authFetch(`${BASE}/assessments/${assessmentId}/items/${itemId}/actions/${actionId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error("Fehler beim Aktualisieren");
  await globalMutate((key: string) => typeof key === "string" && key.includes(itemId));
  return res.json();
}

export async function takeSnapshot(assessmentId: string, triggerReason = "manual") {
  const res = await authFetch(`${BASE}/assessments/${assessmentId}/snapshots`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ trigger_reason: triggerReason }),
  });
  if (!res.ok) throw new Error("Snapshot fehlgeschlagen");
  await globalMutate((key: string) => typeof key === "string" && key.includes(assessmentId));
  return res.json();
}
