"use client";
export const dynamic = "force-dynamic";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth/context";
import type { ApiError } from "@/types";

export default function LoginPage() {
  const { login, loginWithAtlassian, loginWithGitHub } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await login(email, password);
    } catch (err) {
      const apiErr = err as ApiError & { status?: number };
      if (apiErr?.code === "HTTP_401" || apiErr?.status === 401) {
        setError("Ungültige Zugangsdaten. Falls du dein Passwort noch nicht zurückgesetzt hast, besuche: authentik.fichtlworks.com");
      } else {
        setError(apiErr?.error ?? "Login fehlgeschlagen. Bitte versuche es erneut.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const inputCls = "w-full px-3 py-2 text-sm outline-none transition-colors rounded-sm bg-[var(--paper)] border border-[var(--ink-faintest)] focus:border-[var(--ink-faint)] focus:ring-1 focus:ring-[rgba(160,144,128,.2)]";

  return (
    <div className="w-full max-w-sm">
      <div className="mb-6 text-center">
        <span style={{ fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: "22px", color: "var(--ink)" }}>assist2</span>
        <p style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".1em", textTransform: "uppercase", color: "var(--ink-faint)", marginTop: "4px" }}>Workspace Platform</p>
      </div>

      <div className="rounded-sm p-8 space-y-5" style={{ background: "var(--paper)", border: "0.5px solid var(--paper-rule)", boxShadow: "0 2px 12px rgba(28,24,16,.06)" }}>
        <h1 style={{ fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: "18px", color: "var(--ink)", fontWeight: 400 }}>Anmelden</h1>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="text-sm rounded-sm px-3 py-2.5" style={{ background: "rgba(var(--accent-red-rgb),.07)", border: "0.5px solid var(--accent-red)", color: "var(--accent-red)" }}>
              {error}
            </div>
          )}

          <div>
            <label htmlFor="email" className="block mb-1.5" style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase", color: "var(--ink-mid)" }}>E-Mail</label>
            <input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className={inputCls} placeholder="name@example.com" autoComplete="email" />
          </div>

          <div>
            <label htmlFor="password" className="block mb-1.5" style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase", color: "var(--ink-mid)" }}>Passwort</label>
            <input id="password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className={inputCls} placeholder="••••••••" autoComplete="current-password" />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-2.5 rounded-sm transition-colors disabled:opacity-50"
            style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase", background: "var(--ink)", color: "var(--paper)", border: "0.5px solid var(--ink)" }}
          >
            {isSubmitting ? "Anmelden…" : "Anmelden"}
          </button>
        </form>

        {/* Divider */}
        <div className="flex items-center gap-3">
          <div className="flex-1 h-px" style={{ background: "var(--paper-rule)" }} />
          <span style={{ fontFamily: "var(--font-mono)", fontSize: "8px", letterSpacing: ".08em", textTransform: "uppercase", color: "var(--ink-faint)" }}>oder</span>
          <div className="flex-1 h-px" style={{ background: "var(--paper-rule)" }} />
        </div>

        {/* Atlassian Login */}
        <button
          type="button"
          onClick={loginWithAtlassian}
          className="w-full py-2.5 rounded-sm transition-colors flex items-center justify-center gap-2"
          style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase", background: "transparent", color: "var(--ink)", border: "0.5px solid var(--ink-faintest)" }}
        >
          <svg width="14" height="14" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M15.218 1.137a.932.932 0 00-1.476 0L.518 21.895a.931.931 0 00.738 1.476h8.448l5.514-9.54 5.514 9.54h8.448a.931.931 0 00.738-1.476L15.218 1.137z" fill="#2684FF"/>
            <path d="M15.218 14.29l-5.514 9.08h11.028L15.218 14.29z" fill="url(#atlassian-gradient)"/>
            <defs>
              <linearGradient id="atlassian-gradient" x1="15.218" y1="14.29" x2="15.218" y2="23.37" gradientUnits="userSpaceOnUse">
                <stop stopColor="#0052CC"/>
                <stop offset="1" stopColor="#2684FF"/>
              </linearGradient>
            </defs>
          </svg>
          Mit Atlassian anmelden
        </button>

        {/* GitHub Login */}
        <button
          type="button"
          onClick={loginWithGitHub}
          className="w-full py-2.5 rounded-sm transition-colors flex items-center justify-center gap-2"
          style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase", background: "transparent", color: "var(--ink)", border: "0.5px solid var(--ink-faintest)" }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 0C5.374 0 0 5.373 0 12c0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23A11.509 11.509 0 0112 5.803c1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576C20.566 21.797 24 17.3 24 12c0-6.627-5.373-12-12-12z"/>
          </svg>
          Mit GitHub anmelden
        </button>

        <p className="text-center" style={{ fontFamily: "var(--font-body)", fontSize: "13px", color: "var(--ink-faint)" }}>
          Noch kein Konto?{" "}
          <Link href="/register" style={{ color: "var(--ink-mid)", textDecoration: "underline", textUnderlineOffset: "2px" }}>Registrieren</Link>
        </p>
      </div>
    </div>
  );
}
