"use client";
export const dynamic = "force-dynamic";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth/context";
import type { ApiError } from "@/types";

export default function RegisterPage() {
  const { register } = useAuth();
  const [displayName, setDisplayName] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    if (password !== passwordConfirm) { setError("Die Passwörter stimmen nicht überein."); return; }
    if (password.length < 8) { setError("Das Passwort muss mindestens 8 Zeichen lang sein."); return; }
    setIsSubmitting(true);
    try {
      await register(email, password, displayName, organizationName);
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr?.error ?? "Registrierung fehlgeschlagen. Bitte versuche es erneut.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex bg-[#FDFBF7] relative overflow-hidden">
      {/* Dot grid */}
      <div
        className="absolute inset-0 opacity-[0.04] pointer-events-none"
        style={{ backgroundImage: "radial-gradient(#000 1px, transparent 1px)", backgroundSize: "28px 28px" }}
      />

      {/* Corner marks */}
      <div className="absolute top-6 left-6 w-8 h-8 border-l-2 border-t-2 border-slate-900/20" />
      <div className="absolute top-6 right-6 w-8 h-8 border-r-2 border-t-2 border-slate-900/20" />
      <div className="absolute bottom-6 left-6 w-8 h-8 border-l-2 border-b-2 border-slate-900/20" />
      <div className="absolute bottom-6 right-6 w-8 h-8 border-r-2 border-b-2 border-slate-900/20" />

      {/* Left branding panel */}
      <div className="hidden lg:flex flex-1 flex-col items-center justify-center gap-10 p-16 relative">
        <div className="relative">
          <div className="w-52 h-52 bg-amber-50 border-2 border-slate-900 rounded-[3rem] shadow-[10px_10px_0_rgba(0,0,0,1)] overflow-hidden">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/karl-9.png" alt="Karl" className="w-full h-full object-contain" />
          </div>
          <div className="absolute -bottom-4 -right-4 bg-white border-2 border-slate-900 px-4 py-2 rounded-2xl shadow-[4px_4px_0_rgba(0,0,0,1)] rotate-2">
            <span className="text-[13px] font-bold text-slate-800 font-['Architects_Daughter']">Hi, ich bin Karl! 👋</span>
          </div>
          <div className="absolute -top-3 -left-3 flex items-center gap-1.5 bg-emerald-500 text-white px-2.5 py-1 rounded-full border-2 border-slate-900 shadow-[2px_2px_0_rgba(0,0,0,1)] text-[9px] font-bold uppercase tracking-widest">
            <span className="w-1.5 h-1.5 bg-white rounded-full animate-pulse" />
            Live
          </div>
        </div>

        <div className="text-center space-y-3 max-w-sm">
          <h1 className="text-6xl font-black text-slate-900 font-['Architects_Daughter'] leading-none">Karl</h1>
          <p className="text-[11px] font-bold tracking-[0.3em] text-slate-400 uppercase font-['Architects_Daughter']">Workspace Platform</p>
          <p className="text-[15px] font-['Architects_Daughter'] text-slate-600 leading-relaxed">
            Dein KI-gestützter Assistent für agile Entwicklung — von der User Story bis zum Deployment.
          </p>
        </div>
      </div>

      {/* Vertical divider */}
      <div className="hidden lg:block w-px bg-slate-900/10 shrink-0" />

      {/* Right form panel */}
      <div className="flex-1 flex flex-col items-center justify-center p-8 lg:p-16 relative">
        {/* Mobile brand */}
        <div className="lg:hidden flex flex-col items-center mb-8 gap-3">
          <div className="w-20 h-20 bg-amber-50 border-2 border-slate-900 rounded-2xl shadow-[6px_6px_0_rgba(0,0,0,1)] overflow-hidden">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/karl-9.png" alt="Karl" className="w-full h-full object-contain" />
          </div>
          <h1 className="text-4xl font-black text-slate-900 font-['Architects_Daughter']">Karl</h1>
        </div>

        <div className="w-full max-w-md space-y-6">
          <div>
            <h2 className="text-3xl font-black text-slate-900 font-['Architects_Daughter']">Registrieren</h2>
            <p className="text-[12px] text-slate-400 font-['Architects_Daughter'] mt-1">Konto erstellen und loslegen</p>
          </div>

          <div className="bg-white border-2 border-slate-900 rounded-2xl shadow-[8px_8px_0_rgba(0,0,0,1)] p-8 space-y-5">
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="text-[11px] rounded-xl px-3 py-2.5 border-2 border-rose-500 bg-rose-50 text-rose-700 font-['Architects_Daughter']">
                  {error}
                </div>
              )}

              <div className="space-y-1.5">
                <label htmlFor="organizationName" className="block text-[10px] font-bold tracking-[0.15em] text-slate-500 uppercase font-['Architects_Daughter']">
                  Unternehmen / Organisation
                </label>
                <input
                  id="organizationName"
                  type="text"
                  required
                  value={organizationName}
                  onChange={(e) => setOrganizationName(e.target.value)}
                  placeholder="Muster GmbH"
                  autoComplete="organization"
                  className="w-full px-4 py-3 text-[14px] font-['Architects_Daughter'] border-2 border-slate-200 rounded-xl outline-none focus:border-slate-900 transition-colors bg-slate-50/50"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="displayName" className="block text-[10px] font-bold tracking-[0.15em] text-slate-500 uppercase font-['Architects_Daughter']">
                  Ihr Name
                </label>
                <input
                  id="displayName"
                  type="text"
                  required
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="Max Mustermann"
                  autoComplete="name"
                  className="w-full px-4 py-3 text-[14px] font-['Architects_Daughter'] border-2 border-slate-200 rounded-xl outline-none focus:border-slate-900 transition-colors bg-slate-50/50"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="email" className="block text-[10px] font-bold tracking-[0.15em] text-slate-500 uppercase font-['Architects_Daughter']">
                  E-Mail
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@example.com"
                  autoComplete="email"
                  className="w-full px-4 py-3 text-[14px] font-['Architects_Daughter'] border-2 border-slate-200 rounded-xl outline-none focus:border-slate-900 transition-colors bg-slate-50/50"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="password" className="block text-[10px] font-bold tracking-[0.15em] text-slate-500 uppercase font-['Architects_Daughter']">
                  Passwort
                </label>
                <input
                  id="password"
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Mindestens 8 Zeichen"
                  autoComplete="new-password"
                  className="w-full px-4 py-3 text-[14px] font-['Architects_Daughter'] border-2 border-slate-200 rounded-xl outline-none focus:border-slate-900 transition-colors bg-slate-50/50"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="passwordConfirm" className="block text-[10px] font-bold tracking-[0.15em] text-slate-500 uppercase font-['Architects_Daughter']">
                  Passwort bestätigen
                </label>
                <input
                  id="passwordConfirm"
                  type="password"
                  required
                  value={passwordConfirm}
                  onChange={(e) => setPasswordConfirm(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="new-password"
                  className="w-full px-4 py-3 text-[14px] font-['Architects_Daughter'] border-2 border-slate-200 rounded-xl outline-none focus:border-slate-900 transition-colors bg-slate-50/50"
                />
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="w-full py-3.5 bg-slate-900 text-white font-['Architects_Daughter'] text-[14px] font-bold rounded-xl border-2 border-slate-900 shadow-[4px_4px_0_rgba(0,0,0,1)] hover:shadow-[2px_2px_0_rgba(0,0,0,1)] hover:translate-x-[2px] hover:translate-y-[2px] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSubmitting ? "Registrieren…" : "Konto erstellen →"}
              </button>
            </form>

          </div>

          <p className="text-center text-[12px] text-slate-400 font-['Architects_Daughter']">
            Bereits ein Konto?{" "}
            <Link href="/login" className="text-rose-500 font-bold hover:underline underline-offset-2">
              Anmelden
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
