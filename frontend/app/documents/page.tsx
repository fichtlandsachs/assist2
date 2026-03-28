import {
  Plus,
  Upload,
  Search,
  Eye,
  Download,
  MoreHorizontal,
  FileText,
  AlertCircle,
  CheckCircle2,
  Clock,
  XCircle,
  Filter,
} from "lucide-react";
import { Sidebar } from "@/components/layout/sidebar";

/* ── Types ───────────────────────────────────────────────────────── */
type DocType = "SOP" | "Runbook" | "BIA" | "Incident" | "Richtlinie";
type DocStatus = "auditiert" | "in_bearbeitung" | "ausstehend" | "abgelaufen";

interface Document {
  id: string;
  title: string;
  type: DocType;
  status: DocStatus;
  completion: number;
  complianceScore: number;
  openPoints: number;
  frameworks: ("NIS2" | "KRITIS" | "ISO27001")[];
  lastEdited: string;
  author: string;
  version: string;
  auditDate?: string;
}

/* ── Mock Data ───────────────────────────────────────────────────── */
const documents: Document[] = [
  {
    id: "doc-001",
    title: "BIA — Kritische Dienste Q1 2026",
    type: "BIA",
    status: "auditiert",
    completion: 100,
    complianceScore: 94,
    openPoints: 0,
    frameworks: ["NIS2", "KRITIS"],
    lastEdited: "vor 2 Stunden",
    author: "Sarah Müller",
    version: "v3.2",
    auditDate: "20. Mrz 2026",
  },
  {
    id: "doc-002",
    title: "Incident Response Runbook v4",
    type: "Runbook",
    status: "in_bearbeitung",
    completion: 72,
    complianceScore: 67,
    openPoints: 3,
    frameworks: ["NIS2"],
    lastEdited: "heute, 09:12",
    author: "Tom Becker",
    version: "v4.0-draft",
  },
  {
    id: "doc-003",
    title: "Passwort- und Zugriffsrichtlinie 2026",
    type: "Richtlinie",
    status: "ausstehend",
    completion: 88,
    complianceScore: 82,
    openPoints: 1,
    frameworks: ["KRITIS", "ISO27001"],
    lastEdited: "gestern",
    author: "Petra Schmidt",
    version: "v2.1",
  },
  {
    id: "doc-004",
    title: "SOP: Backup & Recovery — Tier 1 Services",
    type: "SOP",
    status: "abgelaufen",
    completion: 55,
    complianceScore: 45,
    openPoints: 5,
    frameworks: ["NIS2", "KRITIS"],
    lastEdited: "vor 14 Tagen",
    author: "Marc Weber",
    version: "v1.8",
  },
  {
    id: "doc-005",
    title: "Notfallkommunikation — Eskalationspfade",
    type: "SOP",
    status: "in_bearbeitung",
    completion: 64,
    complianceScore: 71,
    openPoints: 2,
    frameworks: ["NIS2"],
    lastEdited: "vor 3 Tagen",
    author: "Lisa Hoffmann",
    version: "v2.0-draft",
  },
  {
    id: "doc-006",
    title: "Netzwerktopologie & Asset-Inventar",
    type: "Richtlinie",
    status: "auditiert",
    completion: 100,
    complianceScore: 89,
    openPoints: 0,
    frameworks: ["KRITIS", "ISO27001"],
    lastEdited: "vor 1 Woche",
    author: "Sarah Müller",
    version: "v5.0",
    auditDate: "15. Mrz 2026",
  },
];

/* ── Stat summary ────────────────────────────────────────────────── */
const stats = [
  { label: "Gesamt", value: 24, color: "bg-[#0A0A0A] text-white" },
  { label: "Auditiert", value: 9, color: "bg-[#22C55E] text-[#0A0A0A]" },
  { label: "In Arbeit", value: 8, color: "bg-[#FFD700] text-[#0A0A0A]" },
  { label: "Abgelaufen", value: 4, color: "bg-[#EF4444] text-white" },
];

/* ── Helpers ─────────────────────────────────────────────────────── */
const typeColorMap: Record<DocType, string> = {
  SOP: "bg-[#DBEAFE] text-[#1e40af] border-[#1e40af]",
  Runbook: "bg-[#F3E8FF] text-[#6d28d9] border-[#6d28d9]",
  BIA: "bg-[#FEF3C7] text-[#92400e] border-[#92400e]",
  Incident: "bg-[#FEE2E2] text-[#991b1b] border-[#991b1b]",
  Richtlinie: "bg-[#DCFCE7] text-[#166534] border-[#166534]",
};

const statusConfig: Record<
  DocStatus,
  { label: string; badge: string; icon: React.ReactNode }
> = {
  auditiert: {
    label: "Auditiert",
    badge: "bg-[#22C55E] text-[#0A0A0A]",
    icon: <CheckCircle2 size={12} />,
  },
  in_bearbeitung: {
    label: "In Bearbeitung",
    badge: "bg-[#FFD700] text-[#0A0A0A]",
    icon: <Clock size={12} />,
  },
  ausstehend: {
    label: "Ausstehend",
    badge: "bg-[#FF5C00] text-[#0A0A0A]",
    icon: <AlertCircle size={12} />,
  },
  abgelaufen: {
    label: "Abgelaufen",
    badge: "bg-[#EF4444] text-white",
    icon: <XCircle size={12} />,
  },
};

/* ── Filter Tabs ─────────────────────────────────────────────────── */
const filterTabs = ["Alle", "SOP", "Runbook", "BIA", "Incident", "Richtlinie"];

/* ── Document Card ───────────────────────────────────────────────── */
function DocumentCard({ doc }: { doc: Document }) {
  const status = statusConfig[doc.status];
  const progressColor =
    doc.complianceScore >= 80
      ? "bg-[#00D4AA]"
      : doc.complianceScore >= 60
      ? "bg-[#FFD700]"
      : "bg-[#FF5C00]";

  return (
    <div className="neo-card p-0 overflow-hidden group hover:-translate-x-px hover:-translate-y-px hover:shadow-neo-lg transition-all duration-150">
      {/* Top accent bar */}
      <div
        className={`h-1 w-full ${
          doc.status === "abgelaufen"
            ? "bg-[#EF4444]"
            : doc.status === "auditiert"
            ? "bg-[#22C55E]"
            : "bg-[#FFD700]"
        }`}
      />

      <div className="p-5">
        {/* Header row */}
        <div className="flex items-start gap-3 mb-4">
          <div className="w-9 h-9 bg-[#F5F0E8] border-2 border-[#0A0A0A] flex items-center justify-center flex-shrink-0">
            <FileText size={16} className="text-[#6B6B6B]" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-heading font-700 text-sm leading-tight truncate">
              {doc.title}
            </h3>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <span className="text-xs text-[#6B6B6B]">
                {doc.author}
              </span>
              <span className="text-[#6B6B6B]">·</span>
              <span className="text-xs text-[#6B6B6B]">{doc.version}</span>
              <span className="text-[#6B6B6B]">·</span>
              <span className="text-xs text-[#6B6B6B]">{doc.lastEdited}</span>
            </div>
          </div>
          <button className="w-8 h-8 border-2 border-[#0A0A0A] flex items-center justify-center hover:bg-[#F5F0E8] transition-colors flex-shrink-0 opacity-0 group-hover:opacity-100">
            <MoreHorizontal size={14} />
          </button>
        </div>

        {/* Badges row */}
        <div className="flex flex-wrap gap-2 mb-4">
          {/* Type */}
          <span
            className={`inline-flex items-center px-2 py-0.5 text-[0.65rem] font-heading font-700 border-2 uppercase tracking-wide ${typeColorMap[doc.type]}`}
          >
            {doc.type}
          </span>

          {/* Status */}
          <span
            className={`inline-flex items-center gap-1 px-2 py-0.5 text-[0.65rem] font-heading font-700 border-2 border-[#0A0A0A] shadow-[2px_2px_0px_#0A0A0A] uppercase tracking-wide ${status.badge}`}
          >
            {status.icon}
            {status.label}
          </span>

          {/* Frameworks */}
          {doc.frameworks.map((fw) => (
            <span
              key={fw}
              className={`inline-flex items-center px-2 py-0.5 text-[0.65rem] font-heading font-700 border-2 border-[#0A0A0A] shadow-[2px_2px_0px_#0A0A0A] uppercase tracking-wide ${
                fw === "NIS2"
                  ? "bg-[#0A0A0A] text-white"
                  : fw === "KRITIS"
                  ? "bg-[#FF5C00] text-[#0A0A0A]"
                  : "bg-[#00D4AA] text-[#0A0A0A]"
              }`}
            >
              {fw}
            </span>
          ))}

          {/* Audit date */}
          {doc.auditDate && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[0.65rem] font-heading font-600 text-[#6B6B6B]">
              <CheckCircle2 size={10} className="text-[#22C55E]" />
              Audit: {doc.auditDate}
            </span>
          )}
        </div>

        {/* Progress & score */}
        <div className="grid grid-cols-2 gap-4 mb-4">
          {/* Completion */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-[0.6875rem] font-heading font-600 text-[#6B6B6B] uppercase tracking-wide">
                Fertigstellung
              </span>
              <span className="text-xs font-heading font-700">
                {doc.completion}%
              </span>
            </div>
            <div className="neo-progress">
              <div
                className="neo-progress__bar neo-progress__bar--teal"
                style={{ width: `${doc.completion}%` }}
              />
            </div>
          </div>

          {/* Compliance */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-[0.6875rem] font-heading font-600 text-[#6B6B6B] uppercase tracking-wide">
                Compliance
              </span>
              <span className="text-xs font-heading font-700">
                {doc.complianceScore}%
              </span>
            </div>
            <div className="neo-progress">
              <div
                className={`neo-progress__bar ${progressColor}`}
                style={{ width: `${doc.complianceScore}%` }}
              />
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between pt-3 border-t-2 border-[#0A0A0A]">
          <div className="flex items-center gap-2">
            {doc.openPoints > 0 ? (
              <div className="flex items-center gap-1.5">
                <AlertCircle size={13} className="text-[#FF5C00]" />
                <span className="text-xs font-heading font-700 text-[#FF5C00]">
                  {doc.openPoints} offen
                  {doc.openPoints > 1 ? "e Punkte" : "r Punkt"}
                </span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5">
                <CheckCircle2 size={13} className="text-[#22C55E]" />
                <span className="text-xs font-heading font-600 text-[#6B6B6B]">
                  Keine offenen Punkte
                </span>
              </div>
            )}
          </div>

          <div className="flex gap-2">
            <button className="neo-btn neo-btn--outline neo-btn--sm font-heading text-xs py-1 px-3">
              <Eye size={12} />
              Ansehen
            </button>
            <button className="neo-btn neo-btn--orange neo-btn--sm font-heading text-xs py-1 px-3">
              <Download size={12} />
              Export
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Page ────────────────────────────────────────────────────────── */
export default function DocumentsPage() {
  return (
    <div className="flex min-h-screen bg-[#F5F0E8]">
      <Sidebar activePath="/documents" />

      <div className="flex-1 flex flex-col min-w-0 ml-[15rem]">
        {/* Page header */}
        <div className="h-16 bg-white border-b-2 border-[#0A0A0A] flex items-center justify-between px-8 sticky top-0 z-30">
          <div>
            <h1 className="font-heading font-800 text-xl">
              Dokumentations-Studio
            </h1>
            <p className="text-xs text-[#6B6B6B] mt-0.5">
              24 Dokumente · 3 ausstehend · 4 abgelaufen
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

        <div className="flex-1 p-8">
          {/* Stats row */}
          <div className="flex gap-4 mb-6">
            {stats.map((s) => (
              <div
                key={s.label}
                className={`flex items-center gap-2 px-4 py-2.5 border-2 border-[#0A0A0A] shadow-neo-sm font-heading ${s.color}`}
              >
                <span className="font-800 text-xl">{s.value}</span>
                <span className="font-600 text-xs uppercase tracking-wide opacity-80">
                  {s.label}
                </span>
              </div>
            ))}
          </div>

          {/* Filter & search bar */}
          <div className="flex items-center gap-3 mb-6 flex-wrap">
            {/* Type tabs */}
            <div className="flex border-2 border-[#0A0A0A] overflow-hidden shadow-neo-sm">
              {filterTabs.map((tab, i) => (
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

            {/* Spacer */}
            <div className="flex-1" />

            {/* Framework filter */}
            <button className="neo-btn neo-btn--outline neo-btn--sm font-heading">
              <Filter size={13} />
              Framework
            </button>

            {/* Search */}
            <div className="relative">
              <Search
                size={14}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-[#6B6B6B]"
              />
              <input
                type="search"
                placeholder="Dokumente durchsuchen…"
                className="neo-input pl-9 py-2 text-sm w-64"
              />
            </div>
          </div>

          {/* Document grid */}
          <div className="grid lg:grid-cols-2 xl:grid-cols-3 gap-5">
            {documents.map((doc) => (
              <DocumentCard key={doc.id} doc={doc} />
            ))}

            {/* New document CTA card */}
            <button className="border-2 border-dashed border-[#0A0A0A] p-8 flex flex-col items-center justify-center gap-3 hover:bg-white hover:border-solid hover:shadow-neo transition-all duration-150 group min-h-[16rem]">
              <div className="w-12 h-12 border-2 border-[#0A0A0A] border-dashed flex items-center justify-center group-hover:border-solid group-hover:bg-[#FF5C00] transition-all">
                <Plus size={22} className="text-[#6B6B6B] group-hover:text-[#0A0A0A]" />
              </div>
              <div className="text-center">
                <div className="font-heading font-700 text-sm text-[#0A0A0A]">
                  Neues Dokument
                </div>
                <div className="text-xs text-[#6B6B6B] mt-1">
                  Aus Template erstellen
                  <br />
                  oder von Jira importieren
                </div>
              </div>
            </button>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between mt-8 pt-6 border-t-2 border-[#0A0A0A]">
            <span className="text-sm text-[#6B6B6B] font-heading">
              Zeige 6 von 24 Dokumenten
            </span>
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
      </div>
    </div>
  );
}
