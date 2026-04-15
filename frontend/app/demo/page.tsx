"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, CheckCircle, Lock, Star, Terminal, BarChart3 } from "lucide-react";
import { MarketingTopbar } from "@/components/marketing/Topbar";
import { useAuth } from "@/lib/auth/context";

/* ─────────────────────────────────────────────────────────────────────────────
   Demo / Login page
   Design token source: app/page.tsx (landing) + app/globals.css
   Rules: no inline styles, no new colors, no new fonts, no new spacing.
   ───────────────────────────────────────────────────────────────────────────── */

export default function DemoPage() {
  const { login } = useAuth();
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [error, setError]       = useState<string | null>(null);
  const [loading, setLoading]   = useState(false);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
    } catch (err: unknown) {
      const e = err as { status?: number; code?: string; error?: string };
      if (e?.status === 401 || e?.code === "HTTP_401") {
        setError("E-Mail oder Passwort ungültig.");
      } else {
        setError(e?.error ?? "Anmeldung fehlgeschlagen.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <MarketingTopbar activePage="demo" />

      <main>
        {/* ── Hero ──────────────────────────────────────────────────────── */}
        <section className="pt-32 pb-20 px-6 bg-[#F5F0E8] border-b-2 border-[#0A0A0A]">
          <div className="max-w-7xl mx-auto">
            <div className="grid lg:grid-cols-2 gap-16 items-start">

              {/* Left — Info */}
              <div className="animate-fade-in-up">
                {/* Eyebrow */}
                <div className="flex items-center gap-3 mb-6">
                  <span className="badge-base badge-nis2">NIS2-ready</span>
                  <span className="badge-base badge-kritis">KRITIS</span>
                  <span className="badge-base badge-direct">ISO 27001</span>
                </div>

                {/* Headline */}
                <h1 className="font-heading font-800 text-[3.25rem] leading-[1.05] text-[#0A0A0A] mb-6">
                  Persönliche Demo.
                  <br />
                  <span className="text-[#FF5C00]">In 30 Minuten.</span>
                </h1>

                {/* Sub */}
                <p className="text-lg text-[#6B6B6B] leading-relaxed mb-8 max-w-lg">
                  Wir zeigen dir, wie Karl dein Team bei User Stories und
                  Compliance-Dokumentation unterstützt — live, kostenlos,
                  unverbindlich.
                </p>

                {/* Trust items */}
                <div className="flex flex-col gap-3 mb-10">
                  {[
                    { icon: CheckCircle, text: "Keine Kreditkarte, kein Vendor Lock-in" },
                    { icon: Lock,        text: "DSGVO-konform, On-Premise möglich" },
                    { icon: Star,        text: "Antwort innerhalb von 24 Stunden garantiert" },
                  ].map(({ icon: Icon, text }) => (
                    <div
                      key={text}
                      className="flex items-center gap-3 text-sm font-heading font-600 text-[#0A0A0A]"
                    >
                      <Icon size={16} className="text-[#FF5C00] flex-shrink-0" />
                      {text}
                    </div>
                  ))}
                </div>

                {/* Stats */}
                <div className="flex flex-wrap items-center gap-6 pt-6 border-t-2 border-[#0A0A0A]">
                  {[
                    { value: "30 min", label: "Ø Demo-Dauer" },
                    { value: "24h",    label: "Reaktionszeit" },
                    { value: "120+",   label: "Teams vertrauen Karl" },
                  ].map(({ value, label }) => (
                    <div key={label} className="text-center">
                      <div className="font-heading font-800 text-3xl text-[#0A0A0A]">
                        {value}
                      </div>
                      <div className="text-xs text-[#6B6B6B] font-heading font-600 uppercase tracking-widest mt-1">
                        {label}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Right — Login card */}
              <div className="neo-card p-8">
                <h2 className="font-heading font-700 text-2xl text-[#0A0A0A] mb-2">
                  Jetzt einloggen
                </h2>
                <p className="text-sm text-[#6B6B6B] mb-8">
                  Noch kein Konto?{" "}
                  <Link
                    href="/register"
                    className="text-[#FF5C00] font-heading font-600 hover:underline"
                  >
                    Kostenlos registrieren →
                  </Link>
                </p>

                <form onSubmit={handleLogin} className="flex flex-col gap-5">
                  {error && (
                    <div className="text-sm px-4 py-3 border-2 border-[#FF5C00] text-[#FF5C00] bg-[rgba(255,92,0,.05)]">
                      {error}
                    </div>
                  )}

                  <FormField label="E-Mail">
                    <input
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="name@example.com"
                      autoComplete="email"
                      className="neo-input"
                    />
                  </FormField>

                  <FormField label="Passwort">
                    <input
                      type="password"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="••••••••"
                      autoComplete="current-password"
                      className="neo-input"
                    />
                  </FormField>

                  <button
                    type="submit"
                    disabled={loading}
                    className="neo-btn neo-btn--lg neo-btn--orange w-full justify-center font-heading font-700"
                  >
                    {loading ? (
                      "Wird angemeldet…"
                    ) : (
                      <>
                        <span>Einloggen</span>
                        <ArrowRight size={16} />
                      </>
                    )}
                  </button>

                  <p className="text-xs text-center text-[#6B6B6B]">
                    Mit der Anmeldung stimmst du den{" "}
                    <Link href="/datenschutz" className="text-[#0A0A0A] hover:underline">
                      Datenschutzbestimmungen
                    </Link>{" "}
                    zu.
                  </p>
                </form>
              </div>

            </div>
          </div>
        </section>

        {/* ── CTA strip ──────────────────────────────────────────────────── */}
        <section className="py-16 px-6 bg-[#0A0A0A] border-b-2 border-[#0A0A0A]">
          <div className="max-w-7xl mx-auto text-center">
            <h2 className="font-heading font-800 text-[2rem] text-white leading-tight mb-4">
              Compliance-Dokumentation,{" "}
              <span className="text-[#FF5C00]">die Ihr Auditor liebt.</span>
            </h2>
            <p className="text-[#888] text-base mb-8 max-w-xl mx-auto">
              Starten Sie kostenlos. Keine Kreditkarte. Kein Vendor Lock-in.
              Volle Datenkontrolle von Tag 1.
            </p>
            <Link
              href="/dashboard"
              className="neo-btn neo-btn--lg neo-btn--orange font-heading font-700 text-white"
            >
              Kostenlos starten — 0 EUR
              <ArrowRight size={18} />
            </Link>
          </div>
        </section>
      </main>

      {/* ── Footer — identical to landing ─────────────────────────────── */}
      <footer className="bg-[#0A0A0A] border-t-2 border-[#0A0A0A] px-6 py-16">
        <div className="max-w-7xl mx-auto">
          <div className="grid md:grid-cols-4 gap-12 mb-12">
            {/* Brand */}
            <div className="md:col-span-1">
              <div className="font-heading font-800 text-2xl text-white mb-3">
                hey<span className="text-[#FF5C00]">Karl</span>
              </div>
              <p className="text-[#888] text-sm leading-relaxed mb-6">
                Die Compliance-Dokumentationsplattform für NIS2, KRITIS und
                ISO 27001.
              </p>
              <div className="flex gap-3">
                <span className="badge-base badge-nis2 text-[10px]">NIS2</span>
                <span className="badge-base badge-kritis text-[10px]">KRITIS</span>
                <span className="badge-base badge-direct text-[10px]">ISO27001</span>
              </div>
            </div>

            {/* Link columns */}
            {[
              {
                heading: "Produkt",
                links: ["Funktionen", "Preise", "Changelog", "Roadmap"],
              },
              {
                heading: "Ressourcen",
                links: ["Dokumentation", "API-Referenz", "Blog", "Templates"],
              },
              {
                heading: "Unternehmen",
                links: ["Über uns", "Datenschutz", "Impressum", "Kontakt"],
              },
            ].map(({ heading, links }) => (
              <div key={heading}>
                <div className="font-heading font-700 text-white text-sm uppercase tracking-widest mb-4">
                  {heading}
                </div>
                <ul className="space-y-2.5">
                  {links.map((l) => (
                    <li key={l}>
                      <Link
                        href="#"
                        className="text-[#888] hover:text-white text-sm transition-colors"
                      >
                        {l}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          {/* Bottom bar */}
          <div className="border-t border-[#222] pt-8 flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="text-[#555] text-sm">
              &copy; 2026 Karl. Alle Rechte vorbehalten.
            </div>
            <div className="flex items-center gap-2 text-[#555] text-sm">
              <Terminal size={14} className="text-[#FF5C00]" />
              Made for KRITIS Operators — with love and black borders.
            </div>
            <div className="flex items-center gap-2">
              <BarChart3 size={14} className="text-[#00D4AA]" />
              <span className="text-[#555] text-sm">Status: Alle Systeme operativ</span>
            </div>
          </div>
        </div>
      </footer>
    </>
  );
}

/* ── FormField helper ─────────────────────────────────────────────────────── */
function FormField({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-xs font-heading font-700 uppercase tracking-widest text-[#6B6B6B] mb-2">
        {label}
      </label>
      {children}
    </div>
  );
}
