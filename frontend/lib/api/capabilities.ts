import { apiRequest } from "@/lib/api/client";
import type {
  OrgInitStatus,
  OrgInitializationStatus,
  CapabilityTreeNode,
  ImportValidationResult,
  CapabilityTemplate,
} from "@/types";

export async function fetchOrgInitStatus(orgId: string): Promise<OrgInitStatus> {
  return apiRequest<OrgInitStatus>(`/api/v1/capabilities/orgs/${orgId}/init-status`);
}

export async function advanceOrgInitStatus(
  orgId: string,
  status: OrgInitializationStatus,
  source?: string,
): Promise<OrgInitStatus> {
  return apiRequest<OrgInitStatus>(`/api/v1/capabilities/orgs/${orgId}/init-status`, {
    method: "PATCH",
    body: JSON.stringify({ status, source }),
  });
}

export async function fetchCapabilityTree(orgId: string): Promise<CapabilityTreeNode[]> {
  const data = await apiRequest<{ items: CapabilityTreeNode[] }>(
    `/api/v1/capabilities/orgs/${orgId}/tree`,
  );
  return data.items;
}

export async function fetchCapabilityTemplates(orgId: string): Promise<CapabilityTemplate[]> {
  return apiRequest<CapabilityTemplate[]>(
    `/api/v1/capabilities/orgs/${orgId}/import/templates`,
  );
}

export async function importDemo(orgId: string, dryRun: boolean): Promise<ImportValidationResult> {
  return apiRequest<ImportValidationResult>(
    `/api/v1/capabilities/orgs/${orgId}/import/demo?dry_run=${dryRun}`,
    { method: "POST" },
  );
}

export async function importTemplate(
  orgId: string,
  key: string,
  dryRun: boolean,
): Promise<ImportValidationResult> {
  return apiRequest<ImportValidationResult>(
    `/api/v1/capabilities/orgs/${orgId}/import/template/${key}?dry_run=${dryRun}`,
    { method: "POST" },
  );
}

export async function importExcel(
  orgId: string,
  file: File,
  dryRun: boolean,
): Promise<ImportValidationResult> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1/capabilities/orgs/${orgId}/import/excel?dry_run=${dryRun}`,
    {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    },
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: "Upload failed" }));
    throw err;
  }
  return res.json() as Promise<ImportValidationResult>;
}
