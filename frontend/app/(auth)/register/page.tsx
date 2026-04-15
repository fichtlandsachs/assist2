"use client";
export const dynamic = "force-dynamic";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useAuth } from "@/lib/auth/context";
import { useT } from "@/lib/i18n/context";
import type { ApiError } from "@/types";

export default function RegisterPage() {
  const { register } = useAuth();
  const { t, setLocale } = useT();
  const [displayName, setDisplayName] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirm, setPasswordConfirm] = useState("");
  const [locale, setLocaleState] = useState<"de" | "en">("de");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError(null);
    if (password !== passwordConfirm) { setError(t("auth_register_error_mismatch")); return; }
    if (password.length < 8) { setError(t("auth_register_error_short")); return; }
    setIsSubmitting(true);
    try {
      setLocale(locale);
      await register(email, password, displayName, organizationName, locale);
    } catch (err) {
      const apiErr = err as ApiError;
      setError(apiErr?.error ?? t("auth_register_error"));
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
      <div className="absolute top-6 left-6 w-8 h-8 border-l-2 border-t-2 border-[var(--ink)]/20" />
      <div className="absolute top-6 right-6 w-8 h-8 border-r-2 border-t-2 border-[var(--ink)]/20" />
      <div className="absolute bottom-6 left-6 w-8 h-8 border-l-2 border-b-2 border-[var(--ink)]/20" />
      <div className="absolute bottom-6 right-6 w-8 h-8 border-r-2 border-b-2 border-[var(--ink)]/20" />

      {/* Left branding panel */}
      <div className="hidden lg:flex flex-1 flex-col items-center justify-center gap-10 p-16 relative">
        <div className="relative">
          <div className="w-52 h-52 bg-amber-50 border-2 border-[var(--ink)] rounded-[3rem] shadow-[10px_10px_0_rgba(0,0,0,1)] overflow-hidden">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/karl-9.png" alt="Karl" className="w-full h-full object-contain" />
          </div>
          <div className="absolute -bottom-4 -right-4 bg-white border-2 border-[var(--ink)] px-4 py-2 rounded-2xl shadow-[4px_4px_0_rgba(0,0,0,1)] rotate-2">
            <span className="text-[13px] font-bold text-[var(--ink)]">{t("auth_brand_greeting")} 👋</span>
          </div>
          <div className="absolute -top-3 -left-3 flex items-center gap-1.5 bg-emerald-500 text-white px-2.5 py-1 rounded-full border-2 border-[var(--ink)] shadow-[2px_2px_0_rgba(0,0,0,1)] text-[9px] font-bold uppercase tracking-widest">
            <span className="w-1.5 h-1.5 bg-white rounded-full animate-pulse" />
            Live
          </div>
        </div>

        <div className="text-center space-y-3 max-w-sm">
          <h1 className="text-6xl font-black text-[var(--ink)] leading-none">Karl</h1>
          <p className="text-[11px] font-bold tracking-[0.3em] text-[var(--ink-faint)] uppercase">Workspace Platform</p>
          <p className="text-[15px] text-[var(--ink-mid)] leading-relaxed">
            {t("auth_brand_desc")}
          </p>
        </div>

        <div className="flex flex-col gap-2.5 w-full max-w-xs">
          {[
            t("auth_brand_feature_1"),
            t("auth_brand_feature_2"),
            t("auth_brand_feature_3"),
            t("auth_brand_feature_4"),
          ].map((feat) => (
            <div key={feat} className="flex items-center gap-2.5">
              <div className="w-2 h-2 rounded-full shrink-0" style={{ background: "var(--accent-red)", border: "2px solid var(--btn-primary-hover)" }} />
              <span className="text-[12px] font-bold text-[var(--ink-mid)]">{feat}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Vertical divider */}
      <div className="hidden lg:block w-px shrink-0" style={{ background: "var(--paper-rule)" }} />

      {/* Right form panel */}
      <div className="flex-1 flex flex-col items-center justify-center p-8 lg:p-16 relative">
        {/* Mobile brand */}
        <div className="lg:hidden flex flex-col items-center mb-8 gap-3">
          <div className="w-20 h-20 bg-amber-50 border-2 border-[var(--ink)] rounded-2xl shadow-[6px_6px_0_rgba(0,0,0,1)] overflow-hidden">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/karl-9.png" alt="Karl" className="w-full h-full object-contain" />
          </div>
          <h1 className="text-4xl font-black text-[var(--ink)]">Karl</h1>
        </div>

        <div className="w-full max-w-md space-y-6">
          <div>
            <h2 className="text-3xl font-black text-[var(--ink)]">{t("auth_register_title")}</h2>
            <p className="text-[12px] text-[var(--ink-faint)] mt-1">{t("auth_register_subtitle")}</p>
          </div>

          <div className="bg-white border-2 border-[var(--ink)] rounded-2xl shadow-[8px_8px_0_rgba(0,0,0,1)] p-8 space-y-5">
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="text-[11px] rounded-xl px-3 py-2.5 border-2" style={{ borderColor: "var(--accent-red)", background: "rgba(var(--accent-red-rgb),.06)", color: "var(--accent-red)" }}>
                  {error}
                </div>
              )}

              <div className="space-y-1.5">
                <label htmlFor="organizationName" className="block text-[10px] font-bold tracking-[0.15em] text-[var(--ink-faint)] uppercase">
                  {t("auth_register_org")}
                </label>
                <input
                  id="organizationName"
                  type="text"
                  required
                  value={organizationName}
                  onChange={(e) => setOrganizationName(e.target.value)}
                  placeholder={t("auth_register_org_placeholder")}
                  autoComplete="organization"
                  className="w-full px-4 py-3 text-[14px] border-2 border-[var(--paper-rule)] rounded-xl outline-none focus:border-[var(--ink)] transition-colors bg-[var(--paper-warm)]/50"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="displayName" className="block text-[10px] font-bold tracking-[0.15em] text-[var(--ink-faint)] uppercase">
                  {t("auth_register_name")}
                </label>
                <input
                  id="displayName"
                  type="text"
                  required
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder={t("auth_register_name_placeholder")}
                  autoComplete="name"
                  className="w-full px-4 py-3 text-[14px] border-2 border-[var(--paper-rule)] rounded-xl outline-none focus:border-[var(--ink)] transition-colors bg-[var(--paper-warm)]/50"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="email" className="block text-[10px] font-bold tracking-[0.15em] text-[var(--ink-faint)] uppercase">
                  {t("auth_register_email")}
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@example.com"
                  autoComplete="email"
                  className="w-full px-4 py-3 text-[14px] border-2 border-[var(--paper-rule)] rounded-xl outline-none focus:border-[var(--ink)] transition-colors bg-[var(--paper-warm)]/50"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="password" className="block text-[10px] font-bold tracking-[0.15em] text-[var(--ink-faint)] uppercase">
                  {t("auth_register_password")}
                </label>
                <input
                  id="password"
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={t("auth_register_password_placeholder")}
                  autoComplete="new-password"
                  className="w-full px-4 py-3 text-[14px] border-2 border-[var(--paper-rule)] rounded-xl outline-none focus:border-[var(--ink)] transition-colors bg-[var(--paper-warm)]/50"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="passwordConfirm" className="block text-[10px] font-bold tracking-[0.15em] text-[var(--ink-faint)] uppercase">
                  {t("auth_register_confirm")}
                </label>
                <input
                  id="passwordConfirm"
                  type="password"
                  required
                  value={passwordConfirm}
                  onChange={(e) => setPasswordConfirm(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="new-password"
                  className="w-full px-4 py-3 text-[14px] border-2 border-[var(--paper-rule)] rounded-xl outline-none focus:border-[var(--ink)] transition-colors bg-[var(--paper-warm)]/50"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="locale" className="block text-[10px] font-bold tracking-[0.15em] text-[var(--ink-faint)] uppercase">
                  {t("auth_register_language")}
                </label>
                <select
                  id="locale"
                  value={locale}
                  onChange={(e) => setLocaleState(e.target.value as "de" | "en")}
                  className="w-full px-4 py-3 text-[14px] border-2 border-[var(--paper-rule)] rounded-xl outline-none focus:border-[var(--ink)] transition-colors bg-[var(--paper-warm)]/50"
                >
                  <option value="de">Deutsch</option>
                  <option value="en">English</option>
                </select>
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                className="neo-btn neo-btn--default w-full py-3.5 text-[14px] font-bold disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSubmitting ? t("auth_register_loading") : t("auth_register_button")}
              </button>
            </form>

          </div>

          <p className="text-center text-[12px] text-[var(--ink-faint)]">
            {t("auth_register_has_account")}{" "}
            <Link href="/login" className="font-bold hover:underline underline-offset-2" style={{ color: "var(--accent-red)" }}>
              {t("auth_register_login_link")}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
