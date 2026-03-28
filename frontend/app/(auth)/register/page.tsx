"use client";
export const dynamic = "force-dynamic";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth/context";
import type { ApiError } from "@/types";

export default function RegisterPage() {
  const { register } = useAuth();
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);

    if (password !== passwordConfirm) {
      setError("Die Passwörter stimmen nicht überein.");
      return;
    }

    if (password.length < 8) {
      setError("Das Passwort muss mindestens 8 Zeichen lang sein.");
      return;
    }

    setIsSubmitting(true);
    try {
      await register(email, password, displayName);
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr?.error ?? "Registrierung fehlgeschlagen. Bitte versuche es erneut.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="w-full max-w-md">
      <div className="bg-white rounded-2xl shadow-xl p-8">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-bold text-slate-900">Registrieren</h1>
          <p className="text-slate-500 mt-1 text-sm">Workspace Platform</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="displayName" className="block text-sm font-medium text-slate-700 mb-1">
              Anzeigename
            </label>
            <input
              id="displayName"
              type="text"
              required
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
              placeholder="Max Mustermann"
              autoComplete="name"
            />
          </div>

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
              placeholder="Mindestens 8 Zeichen"
              autoComplete="new-password"
            />
          </div>

          <div>
            <label htmlFor="passwordConfirm" className="block text-sm font-medium text-slate-700 mb-1">
              Passwort bestätigen
            </label>
            <input
              id="passwordConfirm"
              type="password"
              required
              value={passwordConfirm}
              onChange={(e) => setPasswordConfirm(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent"
              placeholder="••••••••"
              autoComplete="new-password"
            />
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-brand-600 hover:bg-brand-500 disabled:opacity-60 disabled:cursor-not-allowed text-white font-medium py-2.5 px-4 rounded-lg text-sm transition-colors"
          >
            {isSubmitting ? "Registrieren..." : "Konto erstellen"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-slate-500">
          Bereits ein Konto?{" "}
          <Link href="/login" className="text-brand-600 hover:text-brand-500 font-medium">
            Anmelden
          </Link>
        </p>
      </div>
    </div>
  );
}
