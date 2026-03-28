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
        setError(
          "Ungültige Zugangsdaten. Falls du dein Passwort noch nicht zurückgesetzt hast, besuche: authentik.fichtlworks.com"
        );
      } else {
        setError(apiErr?.error ?? "Login fehlgeschlagen. Bitte versuche es erneut.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="w-full max-w-md">
      <div className="bg-white rounded-2xl shadow-xl p-8">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-slate-900">Anmelden</h1>
          <p className="text-slate-500 mt-1 text-sm">Workspace Platform</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-slate-700 mb-1">
              E-Mail
            </label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
              placeholder="name@example.com"
              autoComplete="email"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-slate-700 mb-1">
              Passwort
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
              placeholder="••••••••"
              autoComplete="current-password"
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-brand-600 hover:bg-brand-500 disabled:opacity-60 disabled:cursor-not-allowed text-white font-medium py-2.5 px-4 rounded-lg text-sm transition-colors"
          >
            {isSubmitting ? "Anmelden..." : "Anmelden"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-500">
          Noch kein Konto?{" "}
          <Link href="/register" className="text-brand-600 hover:text-brand-500 font-medium">
            Registrieren
          </Link>
        </p>
      </div>
    </div>
  );
}
