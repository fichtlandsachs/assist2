import {
  ShieldCheck,
  Filter,
  Download,
  RefreshCw,
  ChevronDown,
  ExternalLink,
  AlertTriangle,
  CheckCircle2,
  MinusCircle,
  XCircle,
  TrendingUp,
  TrendingDown,
  Info,
} from "lucide-react";
import { Sidebar } from "@/components/layout/sidebar";

/* ── Types ───────────────────────────────────────────────────────── */
type ComplianceStatus = "MET" | "PARTIAL" | "MISSING";
type Framework = "NIS2" | "KRITIS";

interface Requirement {
  id: string;
  article: string;
  title: string;
  description: string;
  status: ComplianceStatus;
  evidence: number; // count of evidence docs
  gaps: string[];
  framework: Framework;
  area: string;
  priority: "HIGH" | "MEDIUM" | "LOW";
  lastReviewed: string;
}

/* ── Mock data ───────────────────────────────────────────────────── */
const requirements: Requirement[] = [
  {
    id: "req-001",
    article: "Art. 21 Abs. 2a",
    title: "Risikoanalyse und Informationssicherheitsrichtlinien",
    description:
      "Maßnahmen zur Risikoanalyse und zur Informationssicherheitspolitik sind zu implementieren und zu dokumentieren.",
    status: "MET",
    evidence: 4,
    gaps: [],
    framework: "NIS2",
    area: "Risikoanalyse",
    priority: "HIGH",
    lastReviewed: "20. Mrz 2026",
  },
  {
    id: "req-002",
    article: "Art. 21 Abs. 2b",
    title: "Behandlung von Sicherheitsvorfällen",
    description:
      "Verfahren zur Erkennung, Analyse und Behandlung von Sicherheitsvorfällen müssen etabliert sein.",
    status: "PARTIAL",
    evidence: 2,
    gaps: [
      "Eskalationsmatrix unvollständig",
      "Kommunikationsplan fehlt für Tier-2-Incidents",
    ],
    framework: "NIS2",
    area: "Incident Response",
    priority: "HIGH",
    lastReviewed: "15. Mrz 2026",
  },
  {
    id: "req-003",
    article: "Art. 21 Abs. 2c",
    title: "Business Continuity Management",
    description:
      "BCM-Konzept inklusive Backup-Management, Wiederherstellung und Krisenmanagement.",
    status: "PARTIAL",
    evidence: 3,
    gaps: ["DR-Test für Q1 2026 ausstehend", "RTO/RPO-Dokumentation lückenhaft"],
    framework: "NIS2",
    area: "BCM",
    priority: "HIGH",
    lastReviewed: "10. Mrz 2026",
  },
  {
    id: "req-004",
    article: "Art. 21 Abs. 2d",
    title: "Sicherheit der Lieferkette",
    description:
      "Sicherheitsanforderungen gegenüber Lieferanten und Dienstleistern definieren und prüfen.",
    status: "MET",
    evidence: 5,
    gaps: [],
    framework: "NIS2",
    area: "Supply Chain",
    priority: "MEDIUM",
    lastReviewed: "18. Mrz 2026",
  },
  {
    id: "req-005",
    article: "Art. 21 Abs. 2e",
    title: "Sicherheit bei Erwerb, Entwicklung und Wartung",
    description:
      "Sicherheitsanforderungen für Netz- und Informationssysteme bei Erwerb und Entwicklung.",
    status: "MET",
    evidence: 3,
    gaps: [],
    framework: "NIS2",
    area: "Entwicklung",
    priority: "MEDIUM",
    lastReviewed: "12. Mrz 2026",
  },
  {
    id: "req-006",
    article: "Art. 21 Abs. 2f",
    title: "Bewertung der Wirksamkeit von Maßnahmen",
    description:
      "Richtlinien und Verfahren zur Bewertung der Wirksamkeit von Risikomanagementmaßnahmen.",
    status: "MISSING",
    evidence: 0,
    gaps: [
      "Kein Messrahmen vorhanden",
      "KPIs nicht definiert",
      "Review-Zyklus fehlt",
    ],
    framework: "NIS2",
    area: "Bewertung",
    priority: "HIGH",
    lastReviewed: "—",
  },
  {
    id: "req-007",
    article: "Art. 21 Abs. 2g",
    title: "Grundlegende Cyber-Hygiene und Schulungen",
    description:
      "Schulungsprogramme zur Cybersicherheit und grundlegende Cyber-Hygiene-Praktiken.",
    status: "MET",
    evidence: 6,
    gaps: [],
    framework: "NIS2",
    area: "Schulung",
    priority: "MEDIUM",
    lastReviewed: "22. Mrz 2026",
  },
  {
    id: "req-008",
    article: "Art. 21 Abs. 2h",
    title: "Kryptographie und Verschlüsselung",
    description:
      "Richtlinien und Verfahren für den Einsatz von Kryptografie und Verschlüsselung.",
    status: "MET",
    evidence: 3,
    gaps: [],
    framework: "NIS2",
    area: "Kryptographie",
    priority: "MEDIUM",
    lastReviewed: "19. Mrz 2026",
  },
  {
    id: "req-009",
    article: "§8a Abs. 1",
    title: "Technische und organisatorische Maßnahmen",
    description:
      "KRITIS-Betreiber müssen angemessene technische und organisatorische Maßnahmen ergreifen.",
    status: "PARTIAL",
    evidence: 4,
    gaps: ["Nachweis-Dokumentation unvollständig"],
    framework: "KRITIS",
    area: "TOM",
    priority: "HIGH",
    lastReviewed: "8. Mrz 2026",
  },
  {
    id: "req-010",
    article: "§8a Abs. 3",
    title: "Nachweis gegenüber BSI",
    description:
      "Alle 2 Jahre Nachweis der getroffenen Maßnahmen gegenüber dem BSI zu erbringen.",
    status: "PARTIAL",
    evidence: 2,
    gaps: [
      "Prüfbericht ausstehend",
      "Dokumentation nicht BSI-konform formatiert",
    ],
    framework: "KRITIS",
    area: "Nachweispflicht",
    priority: "HIGH",
    lastReviewed: "5. Mrz 2026",
  },
  {
    id: "req-011",
    article: "§8b Abs. 4",
    title: "Meldepflicht erheblicher Störungen",
    description:
      "Erhebliche Beeinträchtigungen der kritischen Dienste sind unverzüglich dem BSI zu melden.",
    status: "MET",
    evidence: 3,
    gaps: [],
    framework: "KRITIS",
    area: "Meldepflicht",
    priority: "HIGH",
    lastReviewed: "21. Mrz 2026",
  },
  {
    id: "req-012",
    article: "§8a Abs. 1 Nr. 4",
    title: "Physische Sicherheit und Zutrittsschutz",
    description:
      "Angemessene physische Sicherheitsmaßnahmen für Rechenzentren und kritische Standorte.",
    status: "MISSING",
    evidence: 0,
    gaps: [
      "Zutrittskonzept nicht dokumentiert",
      "Videoüberwachungsrichtlinie fehlt",
    ],
    framework: "KRITIS",
    area: "Physische Sicherheit",
    priority: "MEDIUM",
    lastReviewed: "—",
  },
];

/* ── Framework score calculation ────────────────────────────────── */
function getScore(fw: Framework) {
  const fwReqs = requirements.filter((r) => r.framework === fw);
  const met = fwReqs.filter((r) => r.status === "MET").length;
  const partial = fwReqs.filter((r) => r.status === "PARTIAL").length;
  const total = fwReqs.length;
  return Math.round(((met + partial * 0.5) / total) * 100);
}

/* ── Status config ───────────────────────────────────────────────── */
const statusConfig: Record<
  ComplianceStatus,
  {
    label: string;
    badge: string;
    icon: React.ReactNode;
    rowBg: string;
  }
> = {
  MET: {
    label: "Erfüllt",
    badge: "badge-met",
    icon: <CheckCircle2 size={14} className="text-[#0A0A0A]" />,
    rowBg: "",
  },
  PARTIAL: {
    label: "Teilweise",
    badge: "badge-partial",
    icon: <MinusCircle size={14} className="text-[#0A0A0A]" />,
    rowBg: "bg-[#FFFBEB]",
  },
  MISSING: {
    label: "Fehlend",
    badge: "badge-missing",
    icon: <XCircle size={14} className="text-white" />,
    rowBg: "bg-[#FEF2F2]",
  },
};

const priorityBadge: Record<string, string> = {
  HIGH: "bg-[#EF4444] text-white border-[#EF4444]",
  MEDIUM: "bg-[#FFD700] text-[#0A0A0A] border-[#0A0A0A]",
  LOW: "bg-[#E5E5E5] text-[#6B6B6B] border-[#6B6B6B]",
};

const priorityLabel: Record<string, string> = {
  HIGH: "Hoch",
  MEDIUM: "Mittel",
  LOW: "Niedrig",
};

/* ── Score display ───────────────────────────────────────────────── */
function ScoreCard({
  framework,
  score,
  delta,
  reqs,
}: {
  framework: Framework;
  score: number;
  delta: number;
  reqs: Requirement[];
}) {
  const met = reqs.filter((r) => r.status === "MET").length;
  const partial = reqs.filter((r) => r.status === "PARTIAL").length;
  const missing = reqs.filter((r) => r.status === "MISSING").length;

  return (
    <div
      className={`neo-card p-8 ${
        framework === "NIS2" ? "neo-card--teal" : "neo-card--orange"
      }`}
    >
      <div className="flex items-start justify-between mb-6">
        <div>
          <span
            className={`badge-base mb-2 inline-block ${
              framework === "NIS2" ? "badge-nis2" : "badge-kritis"
            }`}
          >
            {framework}
          </span>
          <div className="text-sm text-[#6B6B6B]">
            {framework === "NIS2"
              ? "Network & Information Security Directive 2"
              : "Kritische Infrastrukturen §8a BSIG"}
          </div>
        </div>
        <div className="text-right">
          <div className="font-heading font-800 text-5xl text-[#0A0A0A] leading-none">
            {score}
            <span className="text-2xl">%</span>
          </div>
          <div
            className={`flex items-center gap-1 justify-end mt-1 text-sm font-heading font-600 ${
              delta >= 0 ? "text-[#22C55E]" : "text-[#EF4444]"
            }`}
          >
            {delta >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
            {delta >= 0 ? "+" : ""}
            {delta}% diese Woche
          </div>
        </div>
      </div>

      {/* Big progress bar */}
      <div className="mb-6">
        <div className="neo-progress h-3">
          <div
            className={`neo-progress__bar ${
              framework === "NIS2"
                ? "neo-progress__bar--teal"
                : ""
            }`}
            style={{ width: `${score}%` }}
          />
        </div>
      </div>

      {/* Breakdown pills */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: "Erfüllt", count: met, color: "bg-[#22C55E]" },
          { label: "Teilweise", count: partial, color: "bg-[#FFD700]" },
          { label: "Fehlend", count: missing, color: "bg-[#EF4444]" },
        ].map(({ label, count, color }) => (
          <div
            key={label}
            className="p-3 bg-[#F5F0E8] border-2 border-[#0A0A0A] text-center"
          >
            <div className="flex items-center justify-center gap-1.5 mb-1">
              <div className={`w-2.5 h-2.5 border border-[#0A0A0A] ${color}`} />
              <span className="text-[0.65rem] font-heading font-600 text-[#6B6B6B] uppercase tracking-wide">
                {label}
              </span>
            </div>
            <div className="font-heading font-800 text-2xl text-[#0A0A0A]">
              {count}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Requirements table row ──────────────────────────────────────── */
function RequirementRow({ req }: { req: Requirement }) {
  const st = statusConfig[req.status];

  return (
    <tr className={`cursor-pointer ${st.rowBg}`}>
      {/* Article */}
      <td>
        <div className="font-mono text-xs font-600 text-[#6B6B6B]">
          {req.article}
        </div>
      </td>

      {/* Title & area */}
      <td>
        <div className="font-heading font-700 text-sm">{req.title}</div>
        <div className="text-xs text-[#6B6B6B] mt-0.5">{req.area}</div>
      </td>

      {/* Priority */}
      <td>
        <span
          className={`inline-flex items-center px-2 py-0.5 text-[0.625rem] font-heading font-700 border-2 uppercase tracking-wide ${priorityBadge[req.priority]}`}
        >
          {priorityLabel[req.priority]}
        </span>
      </td>

      {/* Status */}
      <td>
        <span className={`badge-base ${st.badge} flex items-center gap-1 w-fit`}>
          {st.icon}
          {st.label}
        </span>
      </td>

      {/* Evidence */}
      <td>
        <div className="flex items-center gap-1.5">
          <span className="font-heading font-700 text-sm">
            {req.evidence}
          </span>
          <span className="text-xs text-[#6B6B6B]">
            {req.evidence === 1 ? "Dok." : "Dok."}
          </span>
          {req.evidence > 0 && (
            <ExternalLink
              size={12}
              className="text-[#6B6B6B] hover:text-[#FF5C00] transition-colors"
            />
          )}
        </div>
      </td>

      {/* Gaps */}
      <td>
        {req.gaps.length > 0 ? (
          <div className="space-y-1">
            {req.gaps.slice(0, 2).map((gap, i) => (
              <div key={i} className="flex items-start gap-1.5">
                <AlertTriangle
                  size={11}
                  className="text-[#FF5C00] mt-0.5 flex-shrink-0"
                />
                <span className="text-xs text-[#0A0A0A] leading-tight">
                  {gap}
                </span>
              </div>
            ))}
            {req.gaps.length > 2 && (
              <span className="text-xs text-[#6B6B6B]">
                +{req.gaps.length - 2} weitere
              </span>
            )}
          </div>
        ) : (
          <span className="text-xs text-[#22C55E] font-heading font-600 flex items-center gap-1">
            <CheckCircle2 size={12} />
            Keine Lücken
          </span>
        )}
      </td>

      {/* Last reviewed */}
      <td>
        <span className="text-xs text-[#6B6B6B]">{req.lastReviewed}</span>
      </td>

      {/* Actions */}
      <td>
        <div className="flex gap-1.5">
          <button className="neo-btn neo-btn--outline neo-btn--sm text-xs py-1 px-2 font-heading">
            Details
          </button>
          {req.status !== "MET" && (
            <button className="neo-btn neo-btn--orange neo-btn--sm text-xs py-1 px-2 font-heading">
              Beheben
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}

/* ── Page ────────────────────────────────────────────────────────── */
export default function CompliancePage() {
  const nis2Reqs = requirements.filter((r) => r.framework === "NIS2");
  const kritisReqs = requirements.filter((r) => r.framework === "KRITIS");
  const nis2Score = getScore("NIS2");
  const kritisScore = getScore("KRITIS");

  const totalMissing = requirements.filter((r) => r.status === "MISSING").length;
  const totalPartial = requirements.filter((r) => r.status === "PARTIAL").length;
  const highPriority = requirements.filter(
    (r) => r.priority === "HIGH" && r.status !== "MET"
  ).length;

  return (
    <div className="flex min-h-screen bg-[#F5F0E8]">
      <Sidebar activePath="/compliance" />

      <div className="flex-1 flex flex-col min-w-0 ml-[15rem]">
        {/* Page header */}
        <div className="h-16 bg-white border-b-2 border-[#0A0A0A] flex items-center justify-between px-8 sticky top-0 z-30">
          <div>
            <h1 className="font-heading font-800 text-xl">
              Compliance-Übersicht
            </h1>
            <p className="text-xs text-[#6B6B6B] mt-0.5">
              NIS2 · KRITIS · Stand: 27. März 2026
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button className="neo-btn neo-btn--outline neo-btn--sm font-heading">
              <RefreshCw size={14} />
              Neu scannen
            </button>
            <button className="neo-btn neo-btn--orange neo-btn--sm font-heading font-700">
              <Download size={14} />
              Audit-Paket
            </button>
          </div>
        </div>

        <div className="flex-1 p-8 space-y-8">
          {/* Alert banner for critical gaps */}
          {totalMissing > 0 && (
            <div className="flex items-start gap-3 p-4 bg-[#FEE2E2] border-2 border-[#EF4444] shadow-[4px_4px_0px_#EF4444]">
              <AlertTriangle
                size={18}
                className="text-[#EF4444] flex-shrink-0 mt-0.5"
              />
              <div>
                <div className="font-heading font-700 text-sm text-[#0A0A0A]">
                  {totalMissing} fehlende Anforderung
                  {totalMissing !== 1 ? "en" : ""} erfordern Ihre Aufmerksamkeit
                </div>
                <div className="text-xs text-[#6B6B6B] mt-0.5">
                  Außerdem {totalPartial} teilweise erfüllte und {highPriority} hochpriorisierte offene Punkte.
                </div>
              </div>
              <button className="neo-btn neo-btn--sm font-heading bg-[#EF4444] text-white border-[#0A0A0A] ml-auto flex-shrink-0">
                Alle anzeigen
              </button>
            </div>
          )}

          {/* Score cards */}
          <div className="grid md:grid-cols-2 gap-6">
            <ScoreCard
              framework="NIS2"
              score={nis2Score}
              delta={4}
              reqs={nis2Reqs}
            />
            <ScoreCard
              framework="KRITIS"
              score={kritisScore}
              delta={-1}
              reqs={kritisReqs}
            />
          </div>

          {/* Requirements table section */}
          <div className="neo-card overflow-hidden">
            {/* Table header */}
            <div className="flex items-center justify-between p-6 border-b-2 border-[#0A0A0A]">
              <div className="flex items-center gap-3">
                <ShieldCheck size={20} className="text-[#0A0A0A]" />
                <h2 className="font-heading font-700 text-lg">
                  Anforderungs-Matrix
                </h2>
                <span className="badge-base badge-nis2">
                  {requirements.length} Anforderungen
                </span>
              </div>

              <div className="flex items-center gap-3">
                {/* Framework filter tabs */}
                <div className="flex border-2 border-[#0A0A0A] overflow-hidden">
                  {["Alle", "NIS2", "KRITIS"].map((tab, i) => (
                    <button
                      key={tab}
                      className={`px-4 py-2 text-xs font-heading font-700 uppercase tracking-wide transition-colors border-r-2 border-[#0A0A0A] last:border-r-0 ${
                        i === 0
                          ? "bg-[#0A0A0A] text-white"
                          : "bg-white text-[#0A0A0A] hover:bg-[#F5F0E8]"
                      }`}
                    >
                      {tab}
                    </button>
                  ))}
                </div>

                {/* Filter button */}
                <button className="neo-btn neo-btn--outline neo-btn--sm font-heading">
                  <Filter size={13} />
                  Filter
                  <ChevronDown size={13} />
                </button>

                {/* Info */}
                <button className="w-8 h-8 border-2 border-[#0A0A0A] flex items-center justify-center hover:bg-[#F5F0E8] transition-colors">
                  <Info size={14} className="text-[#6B6B6B]" />
                </button>
              </div>
            </div>

            {/* Table */}
            <div className="overflow-x-auto">
              <table className="neo-table">
                <thead>
                  <tr>
                    <th className="w-32">Artikel</th>
                    <th>Anforderung</th>
                    <th className="w-24">Priorität</th>
                    <th className="w-28">Status</th>
                    <th className="w-24">Nachweise</th>
                    <th>Lücken</th>
                    <th className="w-28">Geprüft</th>
                    <th className="w-32">Aktionen</th>
                  </tr>
                </thead>
                <tbody>
                  {requirements.map((req) => (
                    <RequirementRow key={req.id} req={req} />
                  ))}
                </tbody>
              </table>
            </div>

            {/* Table footer */}
            <div className="flex items-center justify-between px-6 py-4 border-t-2 border-[#0A0A0A] bg-[#F5F0E8]">
              <div className="flex gap-4 text-xs font-heading">
                {[
                  {
                    label: "Erfüllt",
                    count: requirements.filter((r) => r.status === "MET").length,
                    color: "text-[#22C55E]",
                  },
                  {
                    label: "Teilweise",
                    count: requirements.filter((r) => r.status === "PARTIAL").length,
                    color: "text-[#92400e]",
                  },
                  {
                    label: "Fehlend",
                    count: requirements.filter((r) => r.status === "MISSING").length,
                    color: "text-[#EF4444]",
                  },
                ].map(({ label, count, color }) => (
                  <span key={label} className={`font-700 ${color}`}>
                    {count} {label}
                  </span>
                ))}
              </div>
              <div className="flex gap-2">
                <button className="neo-btn neo-btn--outline neo-btn--sm font-heading opacity-40 cursor-not-allowed">
                  Zurück
                </button>
                <button className="neo-btn neo-btn--outline neo-btn--sm font-heading">
                  Weiter
                </button>
              </div>
            </div>
          </div>

          {/* Coverage area breakdown */}
          <div className="neo-card p-6">
            <h3 className="font-heading font-700 text-lg mb-5">
              Abdeckung nach Bereichen (NIS2)
            </h3>
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {[
                { area: "Risikoanalyse", score: 100, status: "MET" as ComplianceStatus },
                { area: "Incident Response", score: 67, status: "PARTIAL" as ComplianceStatus },
                { area: "BCM", score: 75, status: "PARTIAL" as ComplianceStatus },
                { area: "Supply Chain", score: 100, status: "MET" as ComplianceStatus },
                { area: "Entwicklung", score: 100, status: "MET" as ComplianceStatus },
                { area: "Bewertung", score: 0, status: "MISSING" as ComplianceStatus },
                { area: "Schulung", score: 100, status: "MET" as ComplianceStatus },
                { area: "Kryptographie", score: 100, status: "MET" as ComplianceStatus },
              ].map(({ area, score, status }) => {
                const barColor =
                  status === "MET"
                    ? "neo-progress__bar--teal"
                    : status === "PARTIAL"
                    ? "neo-progress__bar--yellow"
                    : "";
                return (
                  <div
                    key={area}
                    className={`p-4 border-2 border-[#0A0A0A] ${
                      status === "MISSING"
                        ? "bg-[#FEF2F2]"
                        : status === "PARTIAL"
                        ? "bg-[#FFFBEB]"
                        : "bg-white"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-heading font-700 truncate">
                        {area}
                      </span>
                      <span className="text-xs font-heading font-800 ml-2">
                        {score}%
                      </span>
                    </div>
                    <div className="neo-progress">
                      <div
                        className={`neo-progress__bar ${barColor}`}
                        style={{ width: `${score}%` }}
                      />
                    </div>
                    <span
                      className={`badge-base mt-2 inline-block text-[0.6rem] px-1.5 py-0.5 ${statusConfig[status].badge}`}
                    >
                      {statusConfig[status].label}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
