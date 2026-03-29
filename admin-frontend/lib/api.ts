import type { ComponentStatus, OrgMetrics } from "@/types";
import { getSession } from "@/lib/auth";

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
    window.location.href = "/login";
    throw new Error("Unauthorized");
  }

  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json() as Promise<T>;
}

export async function fetchComponentStatus(): Promise<ComponentStatus[]> {
  return adminFetch<ComponentStatus[]>("/api/v1/superadmin/status");
}

export async function fetchOrganizations(): Promise<OrgMetrics[]> {
  return adminFetch<OrgMetrics[]>("/api/v1/superadmin/organizations");
}
