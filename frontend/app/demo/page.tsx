"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, CheckCircle, Clock, Users, Terminal, BarChart3 } from "lucide-react";
import { MarketingTopbar } from "@/components/marketing/Topbar";
import { apiRequest } from "@/lib/api/client";

export default function DemoPage() {
  const [form, setForm] = useState({
    name: "",
    company: "",
    email: "",
    phone: "",
    team_size: "",
    message: "",
  });
  const [error, setError]     = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  function set(field: string, value: string) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await apiRequest("/api/v1/contact/demo", {
        method: "POST",
        body: JSON.stringify(form),
      });
      setSuccess(true);
    } catch {
      setError("Anfrage fehlgeschlagen. Bitte versuche es erneut oder schreib uns direkt.");
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
                <h1 className="font-heading font-800 text-[3.25rem] leading-[1.05] text-[#0A0A0A] mb-6">
                  Persönliche Demo.
                  <br />
                  <span className="text-[#FF5C00]">In 30 Minuten.</span>
                </h1>

                <p className="text-lg text-[#6B6B6B] leading-relaxed mb-8 max-w-lg">
                  Wir zeigen dir, wie Karl dein Team bei User Stories, Projektplanung
                  und AI-gestützter Entwicklung unterstützt — live, kostenlos,
                  unverbindlich.
                </p>

                <div className="flex flex-col gap-3 mb-10">
                  {[
                    { icon: CheckCircle, text: "Keine Kreditkarte, kein Vendor Lock-in" },
                    { icon: Clock,       text: "Antwort innerhalb von 24 Stunden garantiert" },
                    { icon: Users,       text: "Persönlich mit einem Produktexperten" },
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

                <div className="flex flex-wrap items-center gap-6 pt-6 border-t-2 border-[#0A0A0A]">
                  {[
                    { value: "30 min", label: "Ø Demo-Dauer" },
                    { value: "24h",    label: "Reaktionszeit" },
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

              {/* Right — Demo booking form */}
              <div className="neo-card p-8">
                {success ? (
                  <div className="text-center py-8">
                    <CheckCircle size={48} className="text-[#FF5C00] mx-auto mb-4" />
                    <h2 className="font-heading font-800 text-2xl text-[#0A0A0A] mb-3">
                      Anfrage erhalten!
                    </h2>
                    <p className="text-[#6B6B6B] text-sm leading-relaxed">
                      Wir melden uns innerhalb von 24 Stunden mit einem
                      Terminvorschlag bei dir.
                    </p>
                  </div>
                ) : (
                  <>
                    <h2 className="font-heading font-700 text-2xl text-[#0A0A0A] mb-2">
                      Demo anfragen
                    </h2>
                    <p className="text-sm text-[#6B6B6B] mb-8">
                      Wir bestätigen deinen Wunschtermin innerhalb von 24 Stunden.
                    </p>

                    <form onSubmit={handleSubmit} className="flex flex-col gap-5">
                      {error && (
                        <div className="text-sm px-4 py-3 border-2 border-[#FF5C00] text-[#FF5C00] bg-[rgba(255,92,0,.05)]">
                          {error}
                        </div>
                      )}

                      <div className="grid grid-cols-2 gap-4">
                        <FormField label="Name *">
                          <input
                            type="text"
                            required
                            minLength={2}
                            value={form.name}
                            onChange={(e) => set("name", e.target.value)}
                            placeholder="Max Muster"
                            className="neo-input"
                          />
                        </FormField>
                        <FormField label="Unternehmen *">
                          <input
                            type="text"
                            required
                            minLength={2}
                            value={form.company}
                            onChange={(e) => set("company", e.target.value)}
                            placeholder="Acme GmbH"
                            className="neo-input"
                          />
                        </FormField>
                      </div>

                      <FormField label="E-Mail *">
                        <input
                          type="email"
                          required
                          value={form.email}
                          onChange={(e) => set("email", e.target.value)}
                          placeholder="max@acme.de"
                          autoComplete="email"
                          className="neo-input"
                        />
                      </FormField>

                      <div className="grid grid-cols-2 gap-4">
                        <FormField label="Telefon">
                          <input
                            type="tel"
                            value={form.phone}
                            onChange={(e) => set("phone", e.target.value)}
                            placeholder="+49 30 …"
                            className="neo-input"
                          />
                        </FormField>
                        <FormField label="Teamgröße">
                          <select
                            value={form.team_size}
                            onChange={(e) => set("team_size", e.target.value)}
                            className="neo-input"
                          >
                            <option value="">Bitte wählen</option>
                            <option value="1-5">1–5</option>
                            <option value="6-20">6–20</option>
                            <option value="21-50">21–50</option>
                            <option value="50+">50+</option>
                          </select>
                        </FormField>
                      </div>

                      <FormField label="Nachricht">
                        <textarea
                          value={form.message}
                          onChange={(e) => set("message", e.target.value)}
                          placeholder="Was soll die Demo zeigen? Gibt es spezifische Anforderungen?"
                          rows={3}
                          className="neo-input resize-none"
                        />
                      </FormField>

                      <button
                        type="submit"
                        disabled={loading}
                        className="neo-btn neo-btn--lg neo-btn--orange w-full justify-center font-heading font-700"
                      >
                        {loading ? (
                          "Wird gesendet…"
                        ) : (
                          <>
                            <span>Demo anfragen</span>
                            <ArrowRight size={16} />
                          </>
                        )}
                      </button>

                    </form>
                  </>
                )}
              </div>

            </div>
          </div>
        </section>

      </main>

      {/* ── Footer ────────────────────────────────────────────────────────── */}
      <footer className="bg-[#0A0A0A] border-t-2 border-[#0A0A0A] px-6 py-16">
        <div className="max-w-7xl mx-auto">
          <div className="grid md:grid-cols-4 gap-12 mb-12">
            <div className="md:col-span-1">
              <div className="font-heading font-800 text-2xl text-white mb-3">
                hey<span className="text-[#FF5C00]">Karl</span>
              </div>
              <p className="text-[#888] text-sm leading-relaxed">
                Die KI-Plattform für agile Teams — von der User Story bis zur
                fertigen Software.
              </p>
            </div>

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

          <div className="border-t border-[#222] pt-8 flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="text-[#555] text-sm">
              &copy; 2026 Karl. Alle Rechte vorbehalten.
            </div>
            <div className="flex items-center gap-2 text-[#555] text-sm">
              <Terminal size={14} className="text-[#FF5C00]" />
              Built for teams that ship — with love and black borders.
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
