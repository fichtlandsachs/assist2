import {
  FileText,
  TrendingUp,
  AlertTriangle,
  Server,
  Plus,
  Upload,
  RefreshCw,
  Download,
  ChevronRight,
  Clock,
  CheckCircle,
  AlertCircle,
  Circle,
} from "lucide-react";
import { Sidebar } from "@/components/layout/sidebar";

/* ── Types ───────────────────────────────────────────────────────── */
type DocStatus = "auditiert" | "in_bearbeitung" | "ausstehend" | "abgelaufen";
type ComplianceStatus = "MET" | "PARTIAL" | "MISSING";

interface RecentDoc {
  id: string;
  title: string;
  type: "SOP" | "Runbook" | "BIA" | "Incident" | "Richtlinie";
  status: DocStatus;
  compliance: number;
  lastEdited: string;
  openPoints: number;
  framework: ("NIS2" | "KRITIS")[];
}

interface BcmService {
  name: string;
  rto: string;
  rpo: string;
  criticality: "HOCH" | "MITTEL" | "NIEDRIG";
  status: "OK" | "WARNUNG" | "KRITISCH";
}

/* ── Mock Data ───────────────────────────────────────────────────── */
const recentDocs: RecentDoc[] = [
  {
    id: "1",
    title: "BIA — Kritische Dienste Q1 2026",
    type: "BIA",
    status: "auditiert",
    compliance: 94,
    lastEdited: "vor 2h",
    openPoints: 0,
    framework: ["NIS2", "KRITIS"],
  },
  {
    id: "2",
    title: "Incident Response Runbook v4",
    type: "Runbook",
    status: "in_bearbeitung",
    compliance: 67,
    lastEdited: "heute, 09:12",
    openPoints: 3,
    framework: ["NIS2"],
  },
  {
    id: "3",
    title: "Passwort-Richtlinie 2026",
    type: "Richtlinie",
    status: "ausstehend",
    compliance: 82,
    lastEdited: "gestern",
    openPoints: 1,
    framework: ["KRITIS"],
  },
  {
    id: "4",
    title: "SOP: Backup & Recovery",
    type: "SOP",
    status: "abgelaufen",
    compliance: 45,
    lastEdited: "vor 14 Tagen",
    openPoints: 5,
    framework: ["NIS2", "KRITIS"],
  },
  {
    id: "5",
    title: "Notfallkommunikation — Eskalation",
    type: "SOP",
    status: "in_bearbeitung",
    compliance: 71,
    lastEdited: "vor 3 Tagen",
    openPoints: 2,
    framework: ["NIS2"],
  },
];

const bcmServices: BcmService[] = [
  {
    name: "Kernbankensystem",
    rto: "4h",
    rpo: "1h",
    criticality: "HOCH",
    status: "OK",
  },
  {
    name: "Payment Gateway",
    rto: "2h",
    rpo: "30min",
    criticality: "HOCH",
    status: "WARNUNG",
  },
  {
    name: "Identity Provider",
    rto: "1h",
    rpo: "15min",
    criticality: "HOCH",
    status: "OK",
  },
];

const heatmapData = [
  ["high", "high", "mid", "high", "none", "mid"],
  ["mid", "high", "high", "low", "mid", "high"],
  ["high", "mid", "none", "high", "high", "mid"],
  ["low", "high", "mid", "high", "none", "high"],
  ["high", "high", "mid", "mid", "high", "low"],
];

const upcomingReviews = [
  { title: "BIA Review Q2", date: "15. Apr 2026", type: "BIA", urgent: false },
  { title: "§8a KRITIS Prüfung", date: "30. Apr 2026", type: "Audit", urgent: true },
  { title: "Richtlinien-Update", date: "5. Mai 2026", type: "Richtlinie", urgent: false },
  { title: "DR-Test Kernbank", date: "12. Mai 2026", type: "Test", urgent: false },
];

/* ── Helper Components ───────────────────────────────────────────── */
function DocStatusBadge({ status }: { status: DocStatus }) {
  const map: Record<DocStatus, { label: string; cls: string }> = {
    auditiert: { label: "Auditiert", cls: "badge-met" },
    in_bearbeitung: { label: "In Bearbeitung", cls: "badge-partial" },
    ausstehend: { label: "Ausstehend", cls: "badge-open" },
    abgelaufen: { label: "Abgelaufen", cls: "badge-missing" },
  };
  const { label, cls } = map[status];
  return <span className={`badge-base ${cls}`}>{label}</span>;
}

function TypeBadge({ type }: { type: RecentDoc["type"] }) {
  const colorMap: Record<RecentDoc["type"], string> = {
    SOP: "bg-[#E0F2FE] text-[#0369a1]",
    Runbook: "bg-[#F3E8FF] text-[#7c3aed]",
    BIA: "bg-[#FEF3C7] text-[#92400e]",
    Incident: "bg-[#FEE2E2] text-[#991b1b]",
    Richtlinie: "bg-[#DCFCE7] text-[#166534]",
  };
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 text-xs font-heading font-600 border border-[#0A0A0A] ${colorMap[type]}`}
    >
      {type}
    </span>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  accent,
}: {
  icon: React.ComponentType<{ size?: number | string; className?: string }>;
  label: string;
  value: string | number;
  sub: string;
  accent: string;
}) {
  return (
    <div className={`neo-card p-6 neo-card--${accent}`}>
      <div className="flex items-start justify-between mb-4">
        <div className="text-[#6B6B6B] font-heading font-600 text-sm uppercase tracking-widest">
          {label}
        </div>
        <div
          className={`w-8 h-8 border-2 border-[#0A0A0A] flex items-center justify-center ${
            accent === "orange"
              ? "bg-[#FF5C00]"
              : accent === "teal"
              ? "bg-[#00D4AA]"
              : accent === "yellow"
              ? "bg-[#FFD700]"
              : "bg-[#0A0A0A]"
          }`}
        >
          <Icon
            size={16}
            className={
              accent === "orange" || accent === "teal" || accent === "yellow"
                ? "text-[#0A0A0A]"
                : "text-white"
            }
          />
        </div>
      </div>
      <div className="font-heading font-800 text-4xl text-[#0A0A0A] mb-1">
        {value}
      </div>
      <div className="text-sm text-[#6B6B6B]">{sub}</div>
    </div>
  );
}

/* ── Compliance Heatmap ──────────────────────────────────────────── */
function ComplianceHeatmap() {
  const areas = ["Risikomgmt.", "Incident", "BCM", "Supply Chain", "Krypto", "Meldung"];
  const colorMap: Record<string, string> = {
    high: "heatmap-high",
    mid: "heatmap-mid",
    low: "heatmap-low",
    none: "heatmap-none",
  };

  return (
    <div className="neo-card p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-heading font-700 text-lg">Compliance-Heatmap</h3>
        <span className="badge-base badge-nis2">NIS2</span>
      </div>

      {/* Column headers */}
      <div className="grid grid-cols-6 gap-1 mb-1">
        {areas.map((a) => (
          <div
            key={a}
            className="text-[9px] font-heading font-600 text-[#6B6B6B] text-center leading-tight truncate"
          >
            {a}
          </div>
        ))}
      </div>

      {/* Grid */}
      <div className="space-y-1">
        {heatmapData.map((row, ri) => (
          <div key={ri} className="grid grid-cols-6 gap-1">
            {row.map((cell, ci) => (
              <div
                key={ci}
                className={`heatmap-cell ${colorMap[cell]} h-6 cursor-pointer`}
                title={`${areas[ci]}: ${cell}`}
              />
            ))}
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="flex gap-4 mt-4">
        {[
          { cls: "heatmap-high", label: "Erfüllt" },
          { cls: "heatmap-mid", label: "Teilweise" },
          { cls: "heatmap-low", label: "Fehlt" },
          { cls: "heatmap-none", label: "N/A" },
        ].map(({ cls, label }) => (
          <div key={label} className="flex items-center gap-1.5">
            <div className={`w-3 h-3 border border-[#0A0A0A] ${cls}`} />
            <span className="text-xs text-[#6B6B6B]">{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Upcoming Reviews ────────────────────────────────────────────── */
function UpcomingReviews() {
  return (
    <div className="neo-card p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-heading font-700 text-lg">Anstehende Reviews</h3>
        <Clock size={18} className="text-[#6B6B6B]" />
      </div>
      <div className="space-y-3">
        {upcomingReviews.map((r) => (
          <div
            key={r.title}
            className={`flex items-center gap-3 p-3 border-2 ${
              r.urgent
                ? "border-[#FF5C00] bg-[#FFF8F5]"
                : "border-[#0A0A0A] bg-[#F5F0E8]"
            }`}
          >
            <div
              className={`w-2 h-full min-h-8 flex-shrink-0 ${
                r.urgent ? "bg-[#FF5C00]" : "bg-[#00D4AA]"
              }`}
            />
            <div className="flex-1 min-w-0">
              <div className="font-heading font-600 text-sm truncate">
                {r.title}
              </div>
              <div className="text-xs text-[#6B6B6B] mt-0.5">{r.date}</div>
            </div>
            <span
              className={`badge-base text-[10px] px-2 py-0.5 flex-shrink-0 ${
                r.urgent ? "badge-open" : "badge-direct"
              }`}
            >
              {r.type}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── BCM Quick View ──────────────────────────────────────────────── */
function BcmQuickView() {
  const statusIcon = (s: BcmService["status"]) => {
    if (s === "OK") return <CheckCircle size={16} className="text-[#22C55E]" />;
    if (s === "WARNUNG") return <AlertCircle size={16} className="text-[#FFD700]" />;
    return <AlertTriangle size={16} className="text-[#EF4444]" />;
  };

  const criticityBadge = (c: BcmService["criticality"]) => {
    const map = {
      HOCH: "badge-open",
      MITTEL: "badge-partial",
      NIEDRIG: "badge-direct",
    };
    return <span className={`badge-base ${map[c]} text-[10px]`}>{c}</span>;
  };

  return (
    <div className="neo-card p-6 neo-card--teal">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-heading font-700 text-lg">BCM — Kritische Services</h3>
        <Server size={18} className="text-[#00D4AA]" />
      </div>
      <div className="space-y-3">
        {bcmServices.map((svc) => (
          <div
            key={svc.name}
            className="flex items-center gap-3 p-3 bg-[#F5F0E8] border-2 border-[#0A0A0A]"
          >
            <div className="flex-shrink-0">{statusIcon(svc.status)}</div>
            <div className="flex-1 min-w-0">
              <div className="font-heading font-600 text-sm truncate">
                {svc.name}
              </div>
              <div className="flex gap-3 mt-1">
                <span className="text-xs text-[#6B6B6B]">
                  <span className="font-heading font-700 text-[#0A0A0A]">RTO</span>{" "}
                  {svc.rto}
                </span>
                <span className="text-xs text-[#6B6B6B]">
                  <span className="font-heading font-700 text-[#0A0A0A]">RPO</span>{" "}
                  {svc.rpo}
                </span>
              </div>
            </div>
            {criticityBadge(svc.criticality)}
          </div>
        ))}
      </div>
      <button className="neo-btn neo-btn--outline neo-btn--sm w-full mt-4 font-heading">
        Alle Services anzeigen
        <ChevronRight size={14} />
      </button>
    </div>
  );
}

/* ── Recent Docs Table ───────────────────────────────────────────── */
function RecentDocsTable() {
  return (
    <div className="neo-card overflow-hidden">
      <div className="flex items-center justify-between p-6 border-b-2 border-[#0A0A0A]">
        <h3 className="font-heading font-700 text-lg">Zuletzt bearbeitet</h3>
        <button className="neo-btn neo-btn--ghost neo-btn--sm font-heading text-[#6B6B6B]">
          Alle Dokumente
          <ChevronRight size={14} />
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="neo-table">
          <thead>
            <tr>
              <th>Dokument</th>
              <th>Typ</th>
              <th>Status</th>
              <th>Compliance</th>
              <th>Frameworks</th>
              <th>Offen</th>
              <th>Bearbeitet</th>
            </tr>
          </thead>
          <tbody>
            {recentDocs.map((doc) => (
              <tr key={doc.id} className="cursor-pointer">
                <td>
                  <div className="font-heading font-600 text-sm max-w-xs truncate">
                    {doc.title}
                  </div>
                </td>
                <td>
                  <TypeBadge type={doc.type} />
                </td>
                <td>
                  <DocStatusBadge status={doc.status} />
                </td>
                <td>
                  <div className="flex items-center gap-2 min-w-24">
                    <div className="neo-progress flex-1">
                      <div
                        className={`neo-progress__bar ${
                          doc.compliance >= 80
                            ? "neo-progress__bar--teal"
                            : doc.compliance >= 60
                            ? "neo-progress__bar--yellow"
                            : ""
                        }`}
                        style={{ width: `${doc.compliance}%` }}
                      />
                    </div>
                    <span className="text-xs font-heading font-700 min-w-[2.5rem] text-right">
                      {doc.compliance}%
                    </span>
                  </div>
                </td>
                <td>
                  <div className="flex gap-1">
                    {doc.framework.map((fw) => (
                      <span
                        key={fw}
                        className={`badge-base text-[10px] px-1.5 py-0.5 ${
                          fw === "NIS2" ? "badge-nis2" : "badge-kritis"
                        }`}
                      >
                        {fw}
                      </span>
                    ))}
                  </div>
                </td>
                <td>
                  {doc.openPoints > 0 ? (
                    <span className="font-heading font-700 text-[#FF5C00]">
                      {doc.openPoints}
                    </span>
                  ) : (
                    <Circle size={14} className="text-[#22C55E]" />
                  )}
                </td>
                <td>
                  <span className="text-sm text-[#6B6B6B]">{doc.lastEdited}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── Page ────────────────────────────────────────────────────────── */
export default function DashboardPage() {
  return (
    <div className="flex min-h-screen bg-[#F5F0E8]">
      <Sidebar activePath="/dashboard" />

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0 ml-[15rem]">
        {/* Topbar */}
        <div className="h-16 bg-white border-b-2 border-[#0A0A0A] flex items-center justify-between px-8 sticky top-0 z-30">
          <div>
            <h1 className="font-heading font-800 text-xl">
              Guten Morgen, Sarah.
            </h1>
            <p className="text-xs text-[#6B6B6B] mt-0.5">
              Freitag, 27. März 2026 — 3 offene Punkte erfordern Ihre Aufmerksamkeit
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button className="neo-btn neo-btn--outline neo-btn--sm font-heading">
              <Upload size={14} />
              Aus Jira importieren
            </button>
            <button className="neo-btn neo-btn--orange neo-btn--sm font-heading font-700">
              <Plus size={14} />
              Neues Dokument
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 p-8 space-y-8">
          {/* Stats row */}
          <div className="grid grid-cols-2 xl:grid-cols-4 gap-6">
            <StatCard
              icon={FileText}
              label="Dokumente"
              value={24}
              sub="3 ausstehend"
              accent="teal"
            />
            <StatCard
              icon={TrendingUp}
              label="Compliance Score"
              value="67%"
              sub="+4% diese Woche"
              accent="yellow"
            />
            <StatCard
              icon={AlertTriangle}
              label="Offene Punkte"
              value={8}
              sub="2 kritisch"
              accent="orange"
            />
            <StatCard
              icon={Server}
              label="Kritische Services"
              value={3}
              sub="1 mit Warnung"
              accent="flat"
            />
          </div>

          {/* Quick actions */}
          <div className="flex flex-wrap gap-3">
            {[
              { icon: RefreshCw, label: "Compliance-Scan starten" },
              { icon: Download, label: "Audit-Paket exportieren" },
              { icon: FileText, label: "Letzten Bericht ansehen" },
            ].map(({ icon: Icon, label }) => (
              <button
                key={label}
                className="neo-btn neo-btn--outline neo-btn--sm font-heading"
              >
                <Icon size={14} />
                {label}
              </button>
            ))}
          </div>

          {/* Main content grid */}
          <div className="grid xl:grid-cols-3 gap-6">
            {/* Docs table — spans 2 cols */}
            <div className="xl:col-span-2">
              <RecentDocsTable />
            </div>

            {/* Right column */}
            <div className="space-y-6">
              <ComplianceHeatmap />
              <UpcomingReviews />
              <BcmQuickView />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
