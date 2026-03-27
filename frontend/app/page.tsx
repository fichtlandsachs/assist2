import Link from "next/link";
import {
  ArrowRight,
  CheckCircle,
  Shield,
  FileText,
  GitBranch,
  Zap,
  Lock,
  BarChart3,
  ChevronRight,
  Star,
  Terminal,
} from "lucide-react";

/* ── Topbar ────────────────────────────────────────────────────── */
function Topbar() {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-[#0A0A0A] border-b-2 border-[#0A0A0A]">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2">
          <span className="font-heading font-800 text-xl text-white tracking-tight">
            assist
            <span className="text-[#FF5C00]">2</span>
          </span>
          <span className="hidden sm:inline-block text-[10px] font-heading font-700 bg-[#FF5C00] text-[#0A0A0A] px-1.5 py-0.5 uppercase tracking-widest">
            BCM
          </span>
        </Link>

        {/* Nav */}
        <nav className="hidden md:flex items-center gap-1">
          {["Funktionen", "Preise", "Docs"].map((item) => (
            <Link
              key={item}
              href={`/${item.toLowerCase()}`}
              className="font-heading font-500 text-sm text-white/80 hover:text-white px-4 py-2 transition-colors"
            >
              {item}
            </Link>
          ))}
        </nav>

        {/* CTAs */}
        <div className="flex items-center gap-3">
          <Link
            href="/demo"
            className="neo-btn neo-btn--outline neo-btn--sm hidden sm:inline-flex bg-transparent text-white border-white hover:bg-white hover:text-[#0A0A0A]"
          >
            Demo buchen
          </Link>
          <Link
            href="/dashboard"
            className="neo-btn neo-btn--orange neo-btn--sm font-heading font-700"
          >
            Kostenlos starten
            <ArrowRight size={14} />
          </Link>
        </div>
      </div>
    </header>
  );
}

/* ── Hero Mock UI ───────────────────────────────────────────────── */
function HeroMockUI() {
  return (
    <div className="relative">
      {/* Outer frame */}
      <div className="bg-[#0A0A0A] border-2 border-[#0A0A0A] shadow-[8px_8px_0px_#FF5C00] p-0 overflow-hidden">
        {/* Window chrome */}
        <div className="flex items-center gap-2 px-4 py-3 bg-[#1a1a1a] border-b border-[#333]">
          <span className="w-3 h-3 rounded-full bg-[#EF4444] border border-[#cc0000]" />
          <span className="w-3 h-3 rounded-full bg-[#FFD700] border border-[#cc9900]" />
          <span className="w-3 h-3 rounded-full bg-[#22C55E] border border-[#16a34a]" />
          <span className="ml-3 font-mono text-xs text-[#666]">
            assist2 — BIA_Kritische_Dienste_v3.md
          </span>
        </div>

        {/* Sidebar + content */}
        <div className="flex">
          {/* Mini sidebar */}
          <div className="w-40 bg-[#111] border-r border-[#333] py-3 hidden sm:block">
            {[
              { label: "Dashboard", active: false },
              { label: "Dokumente", active: true },
              { label: "Compliance", active: false },
              { label: "BCM", active: false },
              { label: "Diagramme", active: false },
            ].map(({ label, active }) => (
              <div
                key={label}
                className={`px-3 py-2 text-xs font-heading ${
                  active
                    ? "bg-[#FF5C00] text-[#0A0A0A] font-700 border-l-4 border-[#0A0A0A]"
                    : "text-[#888] hover:text-white"
                }`}
              >
                {label}
              </div>
            ))}
          </div>

          {/* Main content */}
          <div className="flex-1 p-4 bg-[#0d0d0d] min-h-64">
            {/* Doc header */}
            <div className="flex items-center justify-between mb-4">
              <div>
                <div className="text-white font-heading font-700 text-sm">
                  BIA — Kritische Dienste
                </div>
                <div className="text-[#666] text-xs mt-0.5">
                  Zuletzt bearbeitet: heute, 09:41
                </div>
              </div>
              <div className="flex gap-2">
                <span className="badge-base badge-direct text-[10px] px-2 py-0.5">
                  NIS2
                </span>
                <span className="badge-base badge-partial text-[10px] px-2 py-0.5">
                  KRITIS
                </span>
              </div>
            </div>

            {/* Terminal-style content */}
            <div className="font-mono text-xs space-y-1.5">
              <div className="flex items-start gap-2">
                <span className="text-[#00D4AA]">##</span>
                <span className="text-white">
                  Business Impact Analysis
                </span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-[#666]">01</span>
                <span className="text-[#aaa]">
                  **Service:** Kernbankensystem
                </span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-[#666]">02</span>
                <span className="text-[#aaa]">
                  **RTO:** 4h &nbsp; **RPO:** 1h
                </span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-[#666]">03</span>
                <span className="text-[#FFD700]">
                  **Kritikalität:** HOCH
                </span>
              </div>
              <div className="flex items-start gap-2 mt-2">
                <span className="text-[#00D4AA]">##</span>
                <span className="text-white">Notfallmaßnahmen</span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-[#FF5C00]">✓</span>
                <span className="text-[#aaa]">
                  Failover-Prozedur dokumentiert
                </span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-[#FF5C00]">✓</span>
                <span className="text-[#aaa]">
                  Eskalationskette definiert
                </span>
              </div>
              <div className="flex items-start gap-2">
                <span className="text-[#666]">○</span>
                <span className="text-[#666]">
                  DR-Test ausstehend (Q1 2026)
                </span>
              </div>
            </div>

            {/* Status bar */}
            <div className="mt-4 pt-3 border-t border-[#222] flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="text-xs text-[#666]">Compliance</div>
                <div className="flex gap-1">
                  {[1, 2, 3, 4].map((i) => (
                    <div
                      key={i}
                      className={`w-4 h-2 border border-[#333] ${
                        i <= 3 ? "bg-[#00D4AA]" : "bg-[#333]"
                      }`}
                    />
                  ))}
                </div>
                <span className="text-xs text-[#00D4AA]">75%</span>
              </div>
              <div className="text-xs text-[#666] flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-[#22C55E] inline-block" />
                Auditierbar
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Floating annotation */}
      <div className="absolute -right-4 top-12 bg-[#FFD700] border-2 border-[#0A0A0A] shadow-neo px-3 py-2 rotate-2 hidden lg:block">
        <div className="font-heading font-700 text-xs text-[#0A0A0A]">
          Keine Halluzinationen
        </div>
        <div className="text-[10px] text-[#0A0A0A] mt-0.5">
          100% verifizierbar
        </div>
      </div>
    </div>
  );
}

/* ── Hero Section ───────────────────────────────────────────────── */
function HeroSection() {
  return (
    <section className="pt-32 pb-20 px-6 bg-[#F5F0E8]">
      <div className="max-w-7xl mx-auto">
        <div className="grid lg:grid-cols-2 gap-16 items-center">
          {/* Left */}
          <div className="animate-fade-in-up">
            {/* Eyebrow */}
            <div className="flex items-center gap-3 mb-6">
              <span className="badge-base badge-nis2">NIS2-ready</span>
              <span className="badge-base badge-kritis">KRITIS</span>
              <span className="badge-base badge-direct">ISO 27001</span>
            </div>

            {/* Headline */}
            <h1 className="font-heading font-800 text-[3.25rem] leading-[1.05] text-[#0A0A0A] mb-6">
              Compliance-
              <br />
              Dokumentation.
              <br />
              <span className="text-[#FF5C00]">Automatisiert.</span>
              <br />
              Auditierbar.
            </h1>

            {/* Sub */}
            <p className="text-lg text-[#6B6B6B] leading-relaxed mb-8 max-w-lg">
              assist2 verwandelt Ihre Jira-Tickets und Prozesse in
              vollständige NIS2- und KRITIS-konforme Dokumentation —
              ohne Halluzinationen, mit vollständigem Audit-Trail.
            </p>

            {/* CTAs */}
            <div className="flex flex-wrap gap-4 mb-10">
              <Link
                href="/dashboard"
                className="neo-btn neo-btn--orange neo-btn--lg font-heading font-700"
              >
                Kostenlos starten
                <ArrowRight size={18} />
              </Link>
              <Link
                href="/demo"
                className="neo-btn neo-btn--outline neo-btn--lg font-heading font-600"
              >
                Live-Demo ansehen
              </Link>
            </div>

            {/* Trust strip */}
            <div className="flex flex-wrap items-center gap-6 pt-6 border-t-2 border-[#0A0A0A]">
              {[
                { icon: CheckCircle, label: "DSGVO-konform" },
                { icon: Lock, label: "On-Premise möglich" },
                { icon: Star, label: "4.9/5 von 120+ Teams" },
              ].map(({ icon: Icon, label }) => (
                <div key={label} className="flex items-center gap-2">
                  <Icon size={16} className="text-[#FF5C00]" />
                  <span className="text-sm font-heading font-600 text-[#0A0A0A]">
                    {label}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Right — Mock UI */}
          <div className="relative lg:pl-8">
            <HeroMockUI />
          </div>
        </div>
      </div>
    </section>
  );
}

/* ── Features Section ───────────────────────────────────────────── */
function FeaturesSection() {
  const features = [
    {
      icon: Shield,
      accent: "bg-[#00D4AA]",
      title: "Keine Halluzinationen",
      desc: "Alle Inhalte werden ausschließlich aus Ihren eigenen Daten generiert. Kein erfundenes Wissen, keine generischen Textbausteine — nur verifizierbare Fakten aus Ihrem System.",
      points: [
        "Quellverweise auf jedes Ticket",
        "Vollständiger Änderungsverlauf",
        "Diff-Ansicht für Audits",
      ],
    },
    {
      icon: FileText,
      accent: "bg-[#FFD700]",
      title: "Template-Engine",
      desc: "Vorgefertigte NIS2-, KRITIS- und ISO-27001-Templates. Einmal konfigurieren, immer konsistente Dokumentation — für SOPs, Runbooks, BIA und mehr.",
      points: [
        "50+ regulatorische Templates",
        "Eigene Templates erstellen",
        "Versionierte Template-Bibliothek",
      ],
    },
    {
      icon: GitBranch,
      accent: "bg-[#FF5C00]",
      title: "Draw.io Export",
      desc: "Prozessdiagramme, Netzwerktopologien und BCM-Flussdiagramme werden automatisch als Draw.io-Dateien exportiert — bereit für Ihren Auditor.",
      points: [
        "Automatische Topologie-Erkennung",
        "Bidirektionaler Sync",
        "Confluence-Integration",
      ],
    },
  ];

  return (
    <section className="py-24 px-6 bg-[#0A0A0A]">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-16">
          <div className="inline-block mb-4">
            <span className="badge-base bg-[#FF5C00] text-[#0A0A0A] border-[#FF5C00]">
              Kernfunktionen
            </span>
          </div>
          <h2 className="font-heading font-800 text-[2.5rem] text-white leading-tight max-w-2xl">
            Alles, was Ihr Compliance-Team
            <span className="text-[#FF5C00]"> wirklich braucht</span>
          </h2>
        </div>

        {/* Cards */}
        <div className="grid md:grid-cols-3 gap-6">
          {features.map((f) => (
            <div
              key={f.title}
              className="bg-[#111] border-2 border-[#333] p-8 hover:border-[#FF5C00] transition-colors group"
            >
              <div
                className={`w-12 h-12 ${f.accent} border-2 border-[#0A0A0A] flex items-center justify-center mb-6`}
              >
                <f.icon size={22} className="text-[#0A0A0A]" />
              </div>
              <h3 className="font-heading font-700 text-xl text-white mb-3">
                {f.title}
              </h3>
              <p className="text-[#888] text-sm leading-relaxed mb-6">
                {f.desc}
              </p>
              <ul className="space-y-2">
                {f.points.map((p) => (
                  <li key={p} className="flex items-center gap-2">
                    <ChevronRight
                      size={14}
                      className="text-[#FF5C00] flex-shrink-0"
                    />
                    <span className="text-[#aaa] text-sm">{p}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ── How It Works ───────────────────────────────────────────────── */
function HowItWorksSection() {
  const steps = [
    {
      num: "01",
      title: "Daten verbinden",
      desc: "Verbinden Sie Jira, Confluence oder laden Sie bestehende Dokumente hoch. assist2 liest Ihre vorhandenen Prozesse und Tickets.",
      accent: "bg-[#FF5C00]",
    },
    {
      num: "02",
      title: "Mapping & Analyse",
      desc: "Die Engine mappt automatisch Ihre Prozesse gegen NIS2-Anforderungen und KRITIS-Vorgaben. Lücken werden sofort sichtbar.",
      accent: "bg-[#FFD700]",
    },
    {
      num: "03",
      title: "Exportieren & Prüfen",
      desc: "Ein Klick — vollständige auditierbare Dokumentation. PDF, Word, Draw.io oder direkt in Confluence veröffentlicht.",
      accent: "bg-[#00D4AA]",
    },
  ];

  return (
    <section className="py-24 px-6 bg-[#F5F0E8]">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-16">
          <span className="badge-base badge-nis2 mb-4 inline-block">
            So funktioniert&apos;s
          </span>
          <h2 className="font-heading font-800 text-[2.5rem] text-[#0A0A0A] leading-tight">
            Von Jira-Ticket zur
            <br />
            <span className="text-[#FF5C00]">audit-fähigen Dokumentation</span>
          </h2>
          <p className="text-[#6B6B6B] text-lg mt-4 max-w-2xl mx-auto">
            In drei Schritten von Ihren bestehenden Daten zur vollständigen
            Compliance-Dokumentation.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8 relative">
          {/* Connector line */}
          <div className="hidden md:block absolute top-12 left-[calc(16.67%+1.5rem)] right-[calc(16.67%+1.5rem)] h-0.5 bg-[#0A0A0A] z-0" />

          {steps.map((step, i) => (
            <div
              key={step.num}
              className="neo-card p-8 relative z-10 animate-fade-in-up"
              style={{ animationDelay: `${i * 0.12}s` }}
            >
              <div
                className={`w-16 h-16 ${step.accent} border-2 border-[#0A0A0A] flex items-center justify-center mb-6`}
              >
                <span className="font-heading font-800 text-2xl text-[#0A0A0A]">
                  {step.num}
                </span>
              </div>
              <h3 className="font-heading font-700 text-xl text-[#0A0A0A] mb-3">
                {step.title}
              </h3>
              <p className="text-[#6B6B6B] text-sm leading-relaxed">
                {step.desc}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ── Compliance Coverage Section ────────────────────────────────── */
function ComplianceSection() {
  const frameworks = [
    {
      name: "NIS2",
      subtitle: "Network & Information Security Directive",
      score: 94,
      color: "bg-[#00D4AA]",
      badge: "badge-direct",
      areas: [
        { name: "Risikomgmt.", pct: 100 },
        { name: "Incident Resp.", pct: 92 },
        { name: "BCM", pct: 89 },
        { name: "Supply Chain", pct: 95 },
        { name: "Kryptographie", pct: 97 },
      ],
    },
    {
      name: "KRITIS",
      subtitle: "Kritische Infrastrukturen §8a BSIG",
      score: 88,
      color: "bg-[#FF5C00]",
      badge: "badge-kritis",
      areas: [
        { name: "Org. Maßnahmen", pct: 95 },
        { name: "Technische Maßn.", pct: 88 },
        { name: "Nachweispflicht", pct: 80 },
        { name: "Meldepflicht", pct: 92 },
        { name: "Prüfung §8a", pct: 83 },
      ],
    },
  ];

  return (
    <section className="py-24 px-6 bg-[#FFFFFF] border-y-2 border-[#0A0A0A]">
      <div className="max-w-7xl mx-auto">
        <div className="text-center mb-16">
          <span className="badge-base badge-nis2 mb-4 inline-block">
            Framework-Abdeckung
          </span>
          <h2 className="font-heading font-800 text-[2.5rem] text-[#0A0A0A] leading-tight">
            Volle Abdeckung für NIS2{" "}
            <span className="text-[#FF5C00]">&amp; KRITIS</span>
          </h2>
        </div>

        <div className="grid md:grid-cols-2 gap-8">
          {frameworks.map((fw) => (
            <div key={fw.name} className="neo-card p-8">
              <div className="flex items-start justify-between mb-6">
                <div>
                  <span className={`badge-base ${fw.badge} mb-2 inline-block`}>
                    {fw.name}
                  </span>
                  <div className="text-sm text-[#6B6B6B]">{fw.subtitle}</div>
                </div>
                <div className="text-right">
                  <div className="font-heading font-800 text-4xl text-[#0A0A0A]">
                    {fw.score}
                    <span className="text-xl">%</span>
                  </div>
                  <div className="text-xs text-[#6B6B6B] mt-0.5">
                    Template-Abdeckung
                  </div>
                </div>
              </div>

              {/* Area breakdown */}
              <div className="space-y-3">
                {fw.areas.map((area) => (
                  <div key={area.name}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-heading font-600">
                        {area.name}
                      </span>
                      <span className="text-sm font-heading font-700">
                        {area.pct}%
                      </span>
                    </div>
                    <div className="neo-progress">
                      <div
                        className={`neo-progress__bar ${
                          fw.name === "NIS2"
                            ? "neo-progress__bar--teal"
                            : ""
                        }`}
                        style={{ width: `${area.pct}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ── CTA Section ────────────────────────────────────────────────── */
function CTASection() {
  return (
    <section className="py-24 px-6 bg-[#FF5C00] border-y-2 border-[#0A0A0A]">
      <div className="max-w-4xl mx-auto text-center">
        <div className="inline-flex items-center gap-2 mb-6 bg-[#0A0A0A] text-white px-4 py-2 border-2 border-[#0A0A0A]">
          <Zap size={16} className="text-[#FFD700]" />
          <span className="font-heading font-700 text-sm uppercase tracking-widest">
            Jetzt loslegen
          </span>
        </div>
        <h2 className="font-heading font-800 text-[3rem] text-[#0A0A0A] leading-tight mb-6">
          Compliance-Dokumentation,
          <br />
          die Ihr Auditor liebt.
        </h2>
        <p className="text-[#0A0A0A] text-lg mb-10 opacity-80 max-w-xl mx-auto">
          Starten Sie kostenlos. Keine Kreditkarte. Kein Vendor Lock-in.
          Volle Datenkontrolle von Tag 1.
        </p>
        <div className="flex flex-wrap gap-4 justify-center">
          <Link
            href="/dashboard"
            className="neo-btn neo-btn--default neo-btn--lg font-heading font-700 shadow-[4px_4px_0px_#FFD700] hover:shadow-[6px_6px_0px_#FFD700]"
          >
            Kostenlos starten — 0 EUR
            <ArrowRight size={20} />
          </Link>
          <Link
            href="/demo"
            className="neo-btn neo-btn--lg font-heading font-600 bg-transparent border-[#0A0A0A] text-[#0A0A0A] hover:bg-[#0A0A0A] hover:text-white"
          >
            Demo buchen
          </Link>
        </div>

        {/* Social proof */}
        <div className="mt-12 flex flex-wrap justify-center gap-8">
          {[
            { value: "120+", label: "Teams vertrauen assist2" },
            { value: "94%", label: "NIS2-Abdeckung ab Tag 1" },
            { value: "8h", label: "Ø Zeit bis zur ersten Prüfung" },
          ].map(({ value, label }) => (
            <div key={label} className="text-center">
              <div className="font-heading font-800 text-3xl text-[#0A0A0A]">
                {value}
              </div>
              <div className="text-sm text-[#0A0A0A] opacity-70 mt-1">
                {label}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ── Footer ─────────────────────────────────────────────────────── */
function Footer() {
  return (
    <footer className="bg-[#0A0A0A] border-t-2 border-[#0A0A0A] px-6 py-16">
      <div className="max-w-7xl mx-auto">
        <div className="grid md:grid-cols-4 gap-12 mb-12">
          {/* Brand */}
          <div className="md:col-span-1">
            <div className="font-heading font-800 text-2xl text-white mb-3">
              assist<span className="text-[#FF5C00]">2</span>
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

          {/* Links */}
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

        {/* Bottom */}
        <div className="border-t border-[#222] pt-8 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="text-[#555] text-sm">
            &copy; 2026 assist2 GmbH. Alle Rechte vorbehalten.
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
  );
}

/* ── Page ────────────────────────────────────────────────────────── */
export default function LandingPage() {
  return (
    <>
      <Topbar />
      <main>
        <HeroSection />
        <FeaturesSection />
        <HowItWorksSection />
        <ComplianceSection />
        <CTASection />
      </main>
      <Footer />
    </>
  );
}
