export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const ACCESS_TOKEN_KEY = "access_token";
const REFRESH_TOKEN_KEY = "refresh_token";

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setTokens(access: string, refresh: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, access);
  localStorage.setItem(REFRESH_TOKEN_KEY, refresh);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

async function refreshTokens(): Promise<boolean> {
  const refresh = localStorage.getItem(REFRESH_TOKEN_KEY);
  if (!refresh) return false;
  try {
    const res = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh })
    });
    if (!res.ok) return false;
    const data = await res.json();
    setTokens(data.access_token, data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getAccessToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>)
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401) {
    const errBody = await res.json().catch(() => ({ error: "Unauthorized", code: "HTTP_401", details: {} }));
    const refreshed = await refreshTokens();
    if (refreshed) {
      const newToken = getAccessToken();
      if (newToken) headers["Authorization"] = `Bearer ${newToken}`;
      const retry = await fetch(`${API_BASE}${path}`, { ...options, headers });
      if (retry.ok) return retry.json() as Promise<T>;
    }
    if (typeof window !== "undefined" && window.location.pathname !== "/login") {
      clearTokens();
      window.location.href = "/login";
    }
    throw errBody;
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: "Unknown error", code: "UNKNOWN", details: {} }));
    // Normalize FastAPI's `detail` field into `error` so callers get a consistent string
    if (!err.error && err.detail) {
      err.error = typeof err.detail === "string" ? err.detail : JSON.stringify(err.detail);
    }
    throw err;
  }

  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// SWR fetcher
export const fetcher = <T>(path: string) => apiRequest<T>(path);

/**
 * Low-level authenticated fetch — returns raw Response.
 * Automatically adds Authorization + Content-Type headers.
 * Attempts token refresh on 401 before returning the response.
 */
export async function authFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const isAbsolute = path.startsWith("http");
  const url = isAbsolute ? path : `${API_BASE}${path}`;

  function buildHeaders(token: string | null): Record<string, string> {
    const h: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };
    if (token) h["Authorization"] = `Bearer ${token}`;
    return h;
  }

  let token = getAccessToken();
  let res = await fetch(url, { ...options, headers: buildHeaders(token) });

  // On 401 try a token refresh once
  if (res.status === 401) {
    const refreshed = await refreshTokens();
    if (refreshed) {
      token = getAccessToken();
      res = await fetch(url, { ...options, headers: buildHeaders(token) });
    }
  }

  return res;
}
