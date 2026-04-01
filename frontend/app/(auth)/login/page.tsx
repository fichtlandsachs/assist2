"use client";
export const dynamic = "force-dynamic";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth/context";
import type { ApiError } from "@/types";

export default function LoginPage() {
  const { login, loginWithAtlassian } = useAuth();
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

  const inputCls = "w-full px-3 py-2 text-sm outline-none transition-colors rounded-sm bg-[#faf9f6] border border-[#cec8bc] focus:border-[#a09080] focus:ring-1 focus:ring-[rgba(160,144,128,.2)]";

  return (
    <div className="w-full max-w-sm">
      <div className="mb-6 text-center">
        <span style={{ fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: "22px", color: "#1c1810" }}>assist2</span>
        <p style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".1em", textTransform: "uppercase", color: "#a09080", marginTop: "4px" }}>Workspace Platform</p>
      </div>

      <div className="rounded-sm p-8 space-y-5" style={{ background: "#faf9f6", border: "0.5px solid #e2ddd4", boxShadow: "0 2px 12px rgba(28,24,16,.06)" }}>
        <h1 style={{ fontFamily: "var(--font-serif)", fontStyle: "italic", fontSize: "18px", color: "#1c1810", fontWeight: 400 }}>Anmelden</h1>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="text-sm rounded-sm px-3 py-2.5" style={{ background: "rgba(139,94,82,.07)", border: "0.5px solid #8b5e52", color: "#8b5e52" }}>
              {error}
            </div>
          )}

          <div>
            <label htmlFor="email" className="block mb-1.5" style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase", color: "#5a5040" }}>E-Mail</label>
            <input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className={inputCls} placeholder="name@example.com" autoComplete="email" />
          </div>

          <div>
            <label htmlFor="password" className="block mb-1.5" style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase", color: "#5a5040" }}>Passwort</label>
            <input id="password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className={inputCls} placeholder="••••••••" autoComplete="current-password" />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full py-2.5 rounded-sm transition-colors disabled:opacity-50"
            style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase", background: "#1c1810", color: "#faf9f6", border: "0.5px solid #1c1810" }}
          >
            {isSubmitting ? "Anmelden…" : "Anmelden"}
          </button>
        </form>

        {/* Divider */}
        <div className="flex items-center gap-3">
          <div className="flex-1 h-px" style={{ background: "#e2ddd4" }} />
          <span style={{ fontFamily: "var(--font-mono)", fontSize: "8px", letterSpacing: ".08em", textTransform: "uppercase", color: "#a09080" }}>oder</span>
          <div className="flex-1 h-px" style={{ background: "#e2ddd4" }} />
        </div>

        {/* Atlassian Login */}
        <button
          type="button"
          onClick={loginWithAtlassian}
          className="w-full py-2.5 rounded-sm transition-colors flex items-center justify-center gap-2"
          style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase", background: "transparent", color: "#1c1810", border: "0.5px solid #cec8bc" }}
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

        <p className="text-center" style={{ fontFamily: "var(--font-body)", fontSize: "13px", color: "#a09080" }}>
          Noch kein Konto?{" "}
          <Link href="/register" style={{ color: "#5a5040", textDecoration: "underline", textUnderlineOffset: "2px" }}>Registrieren</Link>
        </p>
      </div>
    </div>
  );
}
