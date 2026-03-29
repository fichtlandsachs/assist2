import type { AdminSession } from "@/types";

const SESSION_KEY = "admin_session";

// ── PKCE helpers ──────────────────────────────────────────────────────────────

function randomBase64Url(bytes = 32): string {
  const arr = new Uint8Array(bytes);
  crypto.getRandomValues(arr);
  return btoa(String.fromCharCode(...arr))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=/g, "");
}

async function sha256Base64Url(plain: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(plain);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return btoa(String.fromCharCode(...new Uint8Array(digest)))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=/g, "");
}

// ── Session storage ───────────────────────────────────────────────────────────

export function getSession(): AdminSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const session = JSON.parse(raw) as AdminSession;
    if (Date.now() >= session.expires_at) {
      sessionStorage.removeItem(SESSION_KEY);
      return null;
    }
    return session;
  } catch {
    return null;
  }
}

export function saveSession(session: AdminSession): void {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function clearSession(): void {
  sessionStorage.removeItem(SESSION_KEY);
  sessionStorage.removeItem("pkce_verifier");
  sessionStorage.removeItem("oauth_state");
}

// ── OIDC Authorization Code + PKCE ────────────────────────────────────────────

export async function startLogin(): Promise<void> {
  const authentikUrl = process.env.NEXT_PUBLIC_AUTHENTIK_URL!;
  const clientId = process.env.NEXT_PUBLIC_ADMIN_CLIENT_ID!;
  const redirectUri = process.env.NEXT_PUBLIC_ADMIN_REDIRECT_URI!;

  const verifier = randomBase64Url(32);
  const challenge = await sha256Base64Url(verifier);
  const state = randomBase64Url(16);

  sessionStorage.setItem("pkce_verifier", verifier);
  sessionStorage.setItem("oauth_state", state);

  const params = new URLSearchParams({
    response_type: "code",
    client_id: clientId,
    redirect_uri: redirectUri,
    scope: "openid email profile",
    state,
    code_challenge: challenge,
    code_challenge_method: "S256",
  });

  window.location.href = `${authentikUrl}/application/o/authorize/?${params}`;
}

export async function handleCallback(code: string, state: string): Promise<void> {
  const storedState = sessionStorage.getItem("oauth_state");
  if (state !== storedState) throw new Error("Invalid OAuth state");

  const verifier = sessionStorage.getItem("pkce_verifier");
  if (!verifier) throw new Error("Missing PKCE verifier");

  const authentikUrl = process.env.NEXT_PUBLIC_AUTHENTIK_URL!;
  const clientId = process.env.NEXT_PUBLIC_ADMIN_CLIENT_ID!;
  const redirectUri = process.env.NEXT_PUBLIC_ADMIN_REDIRECT_URI!;

  const resp = await fetch(`${authentikUrl}/application/o/token/`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "authorization_code",
      code,
      redirect_uri: redirectUri,
      client_id: clientId,
      code_verifier: verifier,
    }),
  });

  if (!resp.ok) {
    const err = await resp.text();
    throw new Error(`Token exchange failed: ${err}`);
  }

  const tokens = await resp.json() as {
    access_token: string;
    id_token: string;
    expires_in?: number;
  };
  const expiresAt = Date.now() + (tokens.expires_in ?? 3600) * 1000;

  saveSession({
    access_token: tokens.access_token,
    id_token: tokens.id_token,
    expires_at: expiresAt,
  });
}

export function logout(): void {
  const session = getSession();
  const authentikUrl = process.env.NEXT_PUBLIC_AUTHENTIK_URL!;
  const clientId = process.env.NEXT_PUBLIC_ADMIN_CLIENT_ID!;

  clearSession();

  if (session?.id_token) {
    const params = new URLSearchParams({
      id_token_hint: session.id_token,
      client_id: clientId,
      post_logout_redirect_uri: window.location.origin + "/login",
    });
    window.location.href = `${authentikUrl}/application/o/end-session/?${params}`;
  } else {
    window.location.href = "/login";
  }
}
