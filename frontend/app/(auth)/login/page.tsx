"use client";
export const dynamic = "force-dynamic";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth/context";
import type { ApiError } from "@/types";

export default function LoginPage() {
  const { login } = useAuth();
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

        <p className="text-center" style={{ fontFamily: "var(--font-body)", fontSize: "13px", color: "#a09080" }}>
          Noch kein Konto?{" "}
          <Link href="/register" style={{ color: "#5a5040", textDecoration: "underline", textUnderlineOffset: "2px" }}>Registrieren</Link>
        </p>
      </div>
    </div>
  );
}
