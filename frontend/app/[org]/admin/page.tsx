"use client";

import { useOrg } from "@/lib/hooks/useOrg";
import { useAuth } from "@/lib/auth/context";
import { apiRequest, fetcher } from "@/lib/api/client";
import useSWR from "swr";
import { use, useState, useEffect } from "react";
import {
  Brain, Database, MessageSquare, GitMerge, Shield, BarChart2,
  Save, Clock, CheckCircle, XCircle, ChevronDown, ChevronUp,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ConfigSection {
  config_type: string;
  config_payload: Record<string, unknown>;
  version: number;
  updated_at: string;
}

interface MergedConfig {
  organization_id: string;
  sections: Record<string, ConfigSection>;
}

interface HistoryEntry {
  id: string;
  config_id: string;
  changed_by_id: string | null;
  previous_value: Record<string, unknown> | null;
  new_value: Record<string, unknown>;
  timestamp: string;
}

type TabId = "learning" | "retrieval" | "prompt" | "workflow" | "governance" | "analytics";

// ---------------------------------------------------------------------------
// UI helpers
// ---------------------------------------------------------------------------

function Toggle({
  checked, onChange, label,
}: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <label className="flex items-center gap-3 cursor-pointer select-none">
      <div
        onClick={() => onChange(!checked)}
        className={`relative w-11 h-6 rounded-full transition-colors ${checked ? "bg-[#5a5068]" : "bg-[#e2ddd4]"}`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${checked ? "translate-x-5" : ""}`}
        />
      </div>
      <span className="text-sm text-[#5a5040]">{label}</span>
    </label>
  );
}

function Slider({
  label, value, min, max, step = 0.01, onChange, format,
}: {
  label: string; value: number; min: number; max: number;
  step?: number; onChange: (v: number) => void; format?: (v: number) => string;
}) {
  const fmt = format ?? ((v: number) => v.toString());
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm text-[#5a5040]">{label}</span>
        <span className="text-sm font-semibold text-[#1c1810]">{fmt(value)}</span>
      </div>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(parseFloat(e.target.value))}
        className="w-full accent-[#5a5068]"
      />
    </div>
  );
}

function SectionHeader({
  title, icon: Icon, version, saving, onSave,
}: {
  title: string; icon: React.ElementType; version: number;
  saving: boolean; onSave: () => void;
}) {
  return (
    <div className="flex items-center justify-between mb-5">
      <div className="flex items-center gap-3">
        <div className="p-2 bg-[rgba(139,94,82,.08)] rounded-sm"><Icon size={18} className="text-[#8b5e52]" /></div>
        <div>
          <h2 className="text-base font-semibold text-[#1c1810]">{title}</h2>
          {version > 0 && (
            <span className="text-xs text-[#a09080]">Version {version}</span>
          )}
        </div>
      </div>
      <button
        onClick={onSave}
        disabled={saving}
        className="flex items-center gap-2 px-4 py-2 bg-[#5a5068] hover:bg-[#5a5068] disabled:opacity-50 text-white rounded-sm text-sm font-medium transition-colors"
      >
        <Save size={14} />
        {saving ? "Speichern…" : "Speichern"}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Section components
// ---------------------------------------------------------------------------

function LearningSensitivitySection({
  section, orgId, onSaved,
}: { section: ConfigSection; orgId: string; onSaved: (updated: ConfigSection) => void }) {
  const [mode, setMode] = useState<string>(
    (section.config_payload.mode as string) ?? "conservative"
  );
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setMode((section.config_payload.mode as string) ?? "conservative");
  }, [section]);

  async function save() {
    setSaving(true);
    try {
      const updated = await apiRequest<ConfigSection>(`/api/v1/admin/${orgId}/config`, {
        method: "POST",
        body: JSON.stringify({ config_type: "learning_sensitivity", config_payload: { mode } }),
      });
      onSaved(updated);
    } finally { setSaving(false); }
  }

  return (
    <div className="bg-[#faf9f6] rounded-sm border border-[#e2ddd4] p-6">
      <SectionHeader title="Lernverhalten" icon={Brain} version={section.version} saving={saving} onSave={save} />
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-[#5a5040] mb-2">Lernmodus</label>
          <select
            value={mode}
            onChange={e => setMode(e.target.value)}
            className="w-full max-w-xs border border-[#cec8bc] rounded-sm px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#8b5e52]"
          >
            <option value="conservative">Conservative — langsam, sicher</option>
            <option value="balanced">Balanced — ausgewogen</option>
            <option value="aggressive">Aggressive — schnell, risikobereit</option>
          </select>
        </div>
        <div className={`rounded-sm p-3 text-xs ${
          mode === "conservative" ? "bg-[rgba(74,85,104,.06)] text-[#4a5568]" :
          mode === "balanced" ? "bg-[rgba(122,100,80,.1)] text-[#7a6450]" :
          "bg-[rgba(139,94,82,.08)] text-[#8b5e52]"
        }`}>
          {mode === "conservative" && "Das System lernt vorsichtig und ändert Verhalten nur bei hoher Sicherheit."}
          {mode === "balanced" && "Das System lernt ausgewogen — gute Balance zwischen Stabilität und Optimierung."}
          {mode === "aggressive" && "Das System lernt aggressiv. Erhöhtes Risiko für unerwartete Verhaltensänderungen."}
        </div>
      </div>
    </div>
  );
}

function RetrievalSection({
  section, orgId, onSaved,
}: { section: ConfigSection; orgId: string; onSaved: (updated: ConfigSection) => void }) {
  const p = section.config_payload;
  const [topK, setTopK] = useState<number>((p.top_k as number) ?? 5);
  const [simW, setSimW] = useState<number>((p.similarity_weight as number) ?? 0.7);
  const [recW, setRecW] = useState<number>((p.recency_weight as number) ?? 0.1);
  const [useW, setUseW] = useState<number>((p.usage_weight as number) ?? 0.1);
  const [orgW, setOrgW] = useState<number>((p.organization_weight as number) ?? 0.1);
  const [lbr, setLbr] = useState<boolean>((p.learning_based_ranking as boolean) ?? false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setTopK((p.top_k as number) ?? 5);
    setSimW((p.similarity_weight as number) ?? 0.7);
    setRecW((p.recency_weight as number) ?? 0.1);
    setUseW((p.usage_weight as number) ?? 0.1);
    setOrgW((p.organization_weight as number) ?? 0.1);
    setLbr((p.learning_based_ranking as boolean) ?? false);
  }, [section]);

  async function save() {
    setSaving(true);
    try {
      const updated = await apiRequest<ConfigSection>(`/api/v1/admin/${orgId}/config`, {
        method: "POST",
        body: JSON.stringify({
          config_type: "retrieval",
          config_payload: {
            top_k: topK, similarity_weight: simW, recency_weight: recW,
            usage_weight: useW, organization_weight: orgW, learning_based_ranking: lbr,
          },
        }),
      });
      onSaved(updated);
    } finally { setSaving(false); }
  }

  return (
    <div className="bg-[#faf9f6] rounded-sm border border-[#e2ddd4] p-6">
      <SectionHeader title="Retrieval-Einstellungen" icon={Database} version={section.version} saving={saving} onSave={save} />
      <div className="space-y-5">
        <Slider label="Top-K Ergebnisse" value={topK} min={1} max={50} step={1}
          onChange={setTopK} format={v => `${Math.round(v)}`} />
        <div className="border-t border-[#e2ddd4] pt-4">
          <p className="text-xs font-semibold text-[#a09080] uppercase tracking-wide mb-3">Ranking-Gewichtungen</p>
          <div className="space-y-4">
            <Slider label="Ähnlichkeit (Similarity)" value={simW} min={0} max={1} onChange={setSimW} format={v => `${Math.round(v * 100)}%`} />
            <Slider label="Aktualität (Recency)" value={recW} min={0} max={1} onChange={setRecW} format={v => `${Math.round(v * 100)}%`} />
            <Slider label="Nutzungshäufigkeit (Usage)" value={useW} min={0} max={1} onChange={setUseW} format={v => `${Math.round(v * 100)}%`} />
            <Slider label="Organisations-Kontext" value={orgW} min={0} max={1} onChange={setOrgW} format={v => `${Math.round(v * 100)}%`} />
          </div>
        </div>
        <div className="border-t border-[#e2ddd4] pt-4">
          <Toggle checked={lbr} onChange={setLbr} label="Learning-based Ranking aktivieren" />
          <p className="text-xs text-[#a09080] mt-1 ml-14">Passt Ranking-Gewichtungen automatisch anhand von Nutzungsmustern an.</p>
        </div>
      </div>
    </div>
  );
}

function PromptLearningSection({
  section, orgId, onSaved,
}: { section: ConfigSection; orgId: string; onSaved: (updated: ConfigSection) => void }) {
  const p = section.config_payload;
  const [enabled, setEnabled] = useState<boolean>((p.enabled as boolean) ?? false);
  const [maxVersions, setMaxVersions] = useState<number>((p.max_parallel_versions as number) ?? 2);
  const [minAccept, setMinAccept] = useState<number>((p.min_acceptance_rate as number) ?? 0.7);
  const [maxRework, setMaxRework] = useState<number>((p.max_rework_rate as number) ?? 0.3);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setEnabled((p.enabled as boolean) ?? false);
    setMaxVersions((p.max_parallel_versions as number) ?? 2);
    setMinAccept((p.min_acceptance_rate as number) ?? 0.7);
    setMaxRework((p.max_rework_rate as number) ?? 0.3);
  }, [section]);

  async function save() {
    setSaving(true);
    try {
      const updated = await apiRequest<ConfigSection>(`/api/v1/admin/${orgId}/config`, {
        method: "POST",
        body: JSON.stringify({
          config_type: "prompt_learning",
          config_payload: {
            enabled, max_parallel_versions: maxVersions,
            min_acceptance_rate: minAccept, max_rework_rate: maxRework,
            affected_agents: (p.affected_agents as string[]) ?? [],
          },
        }),
      });
      onSaved(updated);
    } finally { setSaving(false); }
  }

  return (
    <div className="bg-[#faf9f6] rounded-sm border border-[#e2ddd4] p-6">
      <SectionHeader title="Prompt-Learning" icon={MessageSquare} version={section.version} saving={saving} onSave={save} />
      <div className="space-y-5">
        <Toggle checked={enabled} onChange={setEnabled} label="Prompt-Learning aktivieren" />
        {enabled && (
          <div className="space-y-4 pt-2">
            <Slider label="Max. parallele Prompt-Versionen" value={maxVersions} min={1} max={10} step={1}
              onChange={setMaxVersions} format={v => Math.round(v).toString()} />
            <Slider label="Min. Akzeptanzrate" value={minAccept} min={0} max={1}
              onChange={setMinAccept} format={v => `${Math.round(v * 100)}%`} />
            <Slider label="Max. Überarbeitungsrate" value={maxRework} min={0} max={1}
              onChange={setMaxRework} format={v => `${Math.round(v * 100)}%`} />
          </div>
        )}
      </div>
    </div>
  );
}

function WorkflowLearningSection({
  section, orgId, onSaved,
}: { section: ConfigSection; orgId: string; onSaved: (updated: ConfigSection) => void }) {
  const p = section.config_payload;
  const [enabled, setEnabled] = useState<boolean>((p.enabled as boolean) ?? false);
  const [autoSuggestions, setAutoSuggestions] = useState<boolean>((p.auto_suggestions as boolean) ?? false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setEnabled((p.enabled as boolean) ?? false);
    setAutoSuggestions((p.auto_suggestions as boolean) ?? false);
  }, [section]);

  async function save() {
    setSaving(true);
    try {
      const updated = await apiRequest<ConfigSection>(`/api/v1/admin/${orgId}/config`, {
        method: "POST",
        body: JSON.stringify({
          config_type: "workflow_learning",
          config_payload: {
            enabled, auto_suggestions: autoSuggestions,
            observed_workflows: (p.observed_workflows as string[]) ?? [],
          },
        }),
      });
      onSaved(updated);
    } finally { setSaving(false); }
  }

  return (
    <div className="bg-[#faf9f6] rounded-sm border border-[#e2ddd4] p-6">
      <SectionHeader title="Workflow-Learning" icon={GitMerge} version={section.version} saving={saving} onSave={save} />
      <div className="space-y-4">
        <Toggle checked={enabled} onChange={setEnabled} label="Workflow-Optimierung aktivieren" />
        {enabled && (
          <div className="pt-2">
            <Toggle checked={autoSuggestions} onChange={setAutoSuggestions}
              label="Automatische Optimierungsvorschläge erlauben" />
            <p className="text-xs text-[#a09080] mt-1 ml-14">
              Wenn aktiv, schlägt das System Workflow-Optimierungen vor — ohne automatische Anwendung.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function GovernanceSection({
  section, orgId, onSaved,
}: { section: ConfigSection; orgId: string; onSaved: (updated: ConfigSection) => void }) {
  const p = section.config_payload;
  const ar = (p.approval_required as Record<string, boolean>) ?? {};
  const [promptApproval, setPromptApproval] = useState<boolean>(ar.prompt_updates ?? true);
  const [rankingApproval, setRankingApproval] = useState<boolean>(ar.ranking_changes ?? true);
  const [workflowApproval, setWorkflowApproval] = useState<boolean>(ar.workflow_changes ?? true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const ar2 = (p.approval_required as Record<string, boolean>) ?? {};
    setPromptApproval(ar2.prompt_updates ?? true);
    setRankingApproval(ar2.ranking_changes ?? true);
    setWorkflowApproval(ar2.workflow_changes ?? true);
  }, [section]);

  async function save() {
    setSaving(true);
    try {
      const updated = await apiRequest<ConfigSection>(`/api/v1/admin/${orgId}/config`, {
        method: "POST",
        body: JSON.stringify({
          config_type: "governance",
          config_payload: {
            approval_required: {
              prompt_updates: promptApproval,
              ranking_changes: rankingApproval,
              workflow_changes: workflowApproval,
            },
            approver_roles: (p.approver_roles as string[]) ?? ["admin", "architect_ai", "security_ai"],
          },
        }),
      });
      onSaved(updated);
    } finally { setSaving(false); }
  }

  return (
    <div className="bg-[#faf9f6] rounded-sm border border-[#e2ddd4] p-6">
      <SectionHeader title="Governance & Freigabe" icon={Shield} version={section.version} saving={saving} onSave={save} />
      <div className="space-y-4">
        <p className="text-sm text-[#a09080] mb-4">
          Definiere, welche Änderungen eine explizite Freigabe erfordern, bevor sie in Produktion gehen.
        </p>
        <div className="space-y-3 border border-[#e2ddd4] rounded-sm p-4 bg-[#f7f4ee]">
          <Toggle checked={promptApproval} onChange={setPromptApproval} label="Prompt-Updates freigabepflichtig" />
          <Toggle checked={rankingApproval} onChange={setRankingApproval} label="Ranking-Änderungen freigabepflichtig" />
          <Toggle checked={workflowApproval} onChange={setWorkflowApproval} label="Workflow-Änderungen freigabepflichtig" />
        </div>
        <div>
          <p className="text-xs font-semibold text-[#a09080] uppercase tracking-wide mb-2">Freigabe-Rollen</p>
          <div className="flex flex-wrap gap-2">
            {((p.approver_roles as string[]) ?? ["admin", "architect_ai", "security_ai"]).map(role => (
              <span key={role} className="px-2 py-1 bg-[rgba(139,94,82,.08)] text-[#8b5e52] rounded-sm text-xs font-medium">
                {role}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function LLMTriggerSection({
  section, orgId, onSaved,
}: { section: ConfigSection; orgId: string; onSaved: (updated: ConfigSection) => void }) {
  const p = section.config_payload;
  const [minInputLen, setMinInputLen] = useState<number>((p.min_input_length as number) ?? 50);
  const [idleThresh, setIdleThresh] = useState<number>((p.idle_time_threshold as number) ?? 300);
  const [retrievalOnly, setRetrievalOnly] = useState<boolean>((p.retrieval_only as boolean) ?? false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setMinInputLen((p.min_input_length as number) ?? 50);
    setIdleThresh((p.idle_time_threshold as number) ?? 300);
    setRetrievalOnly((p.retrieval_only as boolean) ?? false);
  }, [section]);

  async function save() {
    setSaving(true);
    try {
      const updated = await apiRequest<ConfigSection>(`/api/v1/admin/${orgId}/config`, {
        method: "POST",
        body: JSON.stringify({
          config_type: "llm_trigger",
          config_payload: {
            min_input_length: minInputLen,
            idle_time_threshold: idleThresh,
            retrieval_only: retrievalOnly,
          },
        }),
      });
      onSaved(updated);
    } finally { setSaving(false); }
  }

  return (
    <div className="bg-[#faf9f6] rounded-sm border border-[#e2ddd4] p-6">
      <SectionHeader title="LLM-Trigger-Regeln" icon={Brain} version={section.version} saving={saving} onSave={save} />
      <div className="space-y-5">
        <Slider label="Minimale Eingabelänge (Zeichen)" value={minInputLen} min={0} max={500} step={10}
          onChange={setMinInputLen} format={v => `${Math.round(v)} Zeichen`} />
        <Slider label="Inaktivitätsschwelle (Sekunden)" value={idleThresh} min={0} max={3600} step={30}
          onChange={setIdleThresh} format={v => `${Math.round(v)} s`} />
        <div className="border-t border-[#e2ddd4] pt-4">
          <Toggle checked={retrievalOnly} onChange={setRetrievalOnly} label="Retrieval-only Modus (kein LLM)" />
          {retrievalOnly && (
            <p className="text-xs text-[#7a6450] bg-[rgba(122,100,80,.1)] rounded-sm p-2 mt-2 ml-14">
              Achtung: Im Retrieval-only Modus werden keine KI-Generierungen durchgeführt.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function AnalyticsSection({
  orgId,
}: { orgId: string }) {
  const [expanded, setExpanded] = useState<string | null>(null);

  const configTypes = ["retrieval", "prompt_learning", "workflow_learning", "governance", "learning_sensitivity", "llm_trigger"];
  const labels: Record<string, string> = {
    retrieval: "Retrieval", prompt_learning: "Prompt-Learning",
    workflow_learning: "Workflow-Learning", governance: "Governance",
    learning_sensitivity: "Lernverhalten", llm_trigger: "LLM-Trigger",
  };

  const { data: history } = useSWR<HistoryEntry[]>(
    expanded ? `/api/v1/admin/${orgId}/config/${expanded}/history` : null,
    fetcher
  );

  return (
    <div className="space-y-3">
      {configTypes.map(ct => (
        <div key={ct} className="bg-[#faf9f6] rounded-sm border border-[#e2ddd4] overflow-hidden">
          <button
            onClick={() => setExpanded(expanded === ct ? null : ct)}
            className="w-full flex items-center justify-between px-5 py-4 hover:bg-[#f7f4ee] transition-colors"
          >
            <span className="text-sm font-semibold text-[#1c1810]">{labels[ct]}</span>
            {expanded === ct ? <ChevronUp size={16} className="text-[#a09080]" /> : <ChevronDown size={16} className="text-[#a09080]" />}
          </button>
          {expanded === ct && (
            <div className="border-t border-[#e2ddd4] px-5 pb-4">
              {!history || history.length === 0 ? (
                <p className="text-sm text-[#a09080] py-4 text-center">Keine Änderungen aufgezeichnet.</p>
              ) : (
                <table className="w-full text-xs mt-3">
                  <thead>
                    <tr className="text-[#a09080] border-b border-[#e2ddd4]">
                      <th className="text-left pb-2 font-medium">Zeitpunkt</th>
                      <th className="text-left pb-2 font-medium">Geändert von</th>
                      <th className="text-left pb-2 font-medium">Aktion</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map(h => (
                      <tr key={h.id} className="border-b border-[#f7f4ee] last:border-0">
                        <td className="py-2 text-[#5a5040] flex items-center gap-1">
                          <Clock size={11} className="text-[#a09080]" />
                          {new Date(h.timestamp).toLocaleString("de-DE")}
                        </td>
                        <td className="py-2 text-[#a09080] truncate max-w-[120px]">
                          {h.changed_by_id ? h.changed_by_id.slice(0, 8) + "…" : "System"}
                        </td>
                        <td className="py-2">
                          {h.previous_value
                            ? <span className="flex items-center gap-1 text-[#7a6450]"><CheckCircle size={11} />Aktualisiert</span>
                            : <span className="flex items-center gap-1 text-[#526b5e]"><CheckCircle size={11} />Erstellt</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

const TABS: { id: TabId; label: string; icon: React.ElementType }[] = [
  { id: "learning",  label: "Lernverhalten",  icon: Brain },
  { id: "retrieval", label: "Retrieval",       icon: Database },
  { id: "prompt",    label: "Prompt",          icon: MessageSquare },
  { id: "workflow",  label: "Workflow",        icon: GitMerge },
  { id: "governance",label: "Governance",      icon: Shield },
  { id: "analytics", label: "Analytics",       icon: BarChart2 },
];

export default function AdminPage({ params }: { params: Promise<{ org: string }> }) {
  const resolvedParams = use(params);
  const { org } = useOrg(resolvedParams.org);
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<TabId>("learning");

  const { data: config, mutate } = useSWR<MergedConfig>(
    org ? `/api/v1/admin/${org.id}/config` : null,
    fetcher
  );

  function handleSectionSaved(updated: ConfigSection) {
    mutate(
      (current) =>
        current
          ? { ...current, sections: { ...current.sections, [updated.config_type]: updated } }
          : current,
      false
    );
  }

  // Only superusers and admins access this page
  if (user && !user.is_superuser) {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-center">
        <Shield size={40} className="text-[#cec8bc] mb-3" />
        <h2 className="text-lg font-semibold text-[#5a5040]">Kein Zugriff</h2>
        <p className="text-sm text-[#a09080] mt-1">Dieser Bereich ist nur für Administratoren zugänglich.</p>
      </div>
    );
  }

  const s = config?.sections ?? {};
  const def = (ct: string): ConfigSection => s[ct] ?? {
    config_type: ct, config_payload: {}, version: 0, updated_at: new Date().toISOString(),
  };

  return (
    <div className="space-y-6 min-w-0">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-[#1c1810]">Admin-Konfiguration</h1>
        <p className="text-[#a09080] mt-1 text-sm">
          Steuere das Lernverhalten, Retrieval-Gewichtungen und Governance-Regeln der Plattform.
          Alle Änderungen sind versioniert und auditierbar.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[#e2ddd4] overflow-x-auto">
        {TABS.map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 whitespace-nowrap transition-colors ${
                activeTab === tab.id
                  ? "border-[#8b5e52] text-[#8b5e52]"
                  : "border-transparent text-[#a09080] hover:text-[#5a5040]"
              }`}
            >
              <Icon size={15} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      {!config ? (
        <div className="flex items-center justify-center py-16">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#8b5e52]" />
        </div>
      ) : (
        <div className="space-y-4">
          {activeTab === "learning" && (
            <>
              <LearningSensitivitySection section={def("learning_sensitivity")} orgId={org!.id} onSaved={handleSectionSaved} />
              <LLMTriggerSection section={def("llm_trigger")} orgId={org!.id} onSaved={handleSectionSaved} />
            </>
          )}
          {activeTab === "retrieval" && (
            <RetrievalSection section={def("retrieval")} orgId={org!.id} onSaved={handleSectionSaved} />
          )}
          {activeTab === "prompt" && (
            <PromptLearningSection section={def("prompt_learning")} orgId={org!.id} onSaved={handleSectionSaved} />
          )}
          {activeTab === "workflow" && (
            <WorkflowLearningSection section={def("workflow_learning")} orgId={org!.id} onSaved={handleSectionSaved} />
          )}
          {activeTab === "governance" && (
            <GovernanceSection section={def("governance")} orgId={org!.id} onSaved={handleSectionSaved} />
          )}
          {activeTab === "analytics" && (
            <AnalyticsSection orgId={org!.id} />
          )}
        </div>
      )}
    </div>
  );
}
