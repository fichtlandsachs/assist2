import type { ComponentStatus, OrgMetrics, ConfigMap, OrgIntegrationSettings } from "@/types";
import { getSession, clearSession } from "@/lib/auth";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

async function adminFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const session = getSession();
  if (!session) {
    window.location.href = "/login";
    throw new Error("No session");
  }

  const resp = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.access_token}`,
      ...init?.headers,
    },
  });

  if (resp.status === 401 || resp.status === 403) {
    clearSession();
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }

  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
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
