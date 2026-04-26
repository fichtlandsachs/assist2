"use client";

import { use, useState } from "react";
import { PlayCircle, CheckCircle2, AlertTriangle, Zap, Lock, Plus } from "lucide-react";
import { runSimulation, type SimulationInput } from "@/lib/hooks/useGovernance";

interface PageProps {
  params: Promise<{ org: string }>;
}

const RISK_LEVELS = ["", "low", "medium", "high", "critical"];
const RISK_LABEL: Record<string, string> = { "": "–", low: "Niedrig", medium: "Mittel", high: "Hoch", critical: "Kritisch" };

const PRODUCT_TYPES = [
  { value: "wallbox", label: "Wallbox / Ladestation" },
  { value: "battery-storage", label: "Batteriespeicher" },
  { value: "inverter", label: "Wechselrichter" },
  { value: "power-supply", label: "Netzteil" },
  { value: "smart-energy", label: "Smarte Energietechnik" },
  { value: "heat-pump", label: "Wärmepumpe" },
  { value: "solar-system", label: "Solaranlage / PV" },
];

const MARKETS = [
  { value: "eu", label: "EU / Europa" },
  { value: "de", label: "Deutschland" },
  { value: "at", label: "Österreich" },
  { value: "us", label: "USA" },
  { value: "uk", label: "Großbritannien" },
  { value: "apac", label: "Asia Pacific" },
  { value: "global", label: "Global" },
];

const SEGMENTS = [
  { value: "b2b-enterprise", label: "B2B Enterprise" },
  { value: "b2b-smb", label: "B2B SMB" },
  { value: "b2c-mass", label: "B2C Massenmarkt" },
  { value: "b2c-premium", label: "B2C Premium" },
  { value: "b2b2c", label: "B2B2C" },
  { value: "installer", label: "Fachhandwerker" },
  { value: "utility", label: "Energieversorger" },
];

interface SimResult {
  fixed_controls: { id: string; name: string; slug: string; gate_phases: string[] }[];
  triggered_controls: { id: string; name: string; slug: string; gate_phases: string[] }[];
  fired_triggers: { trigger_id: string; trigger_name: string }[];
  hard_stop_controls: { id: string; name: string }[];
  estimated_gate_outcome: string;
  total_active_controls: number;
  scenario_id?: string;
}

const OUTCOME_CONFIG: Record<string, { label: string; color: string; icon: React.ElementType }> = {
  go:             { label: "Go",             color: "bg-green-100 border-green-300 text-green-800", icon: CheckCircle2 },
  conditional_go: { label: "Conditional Go", color: "bg-amber-100 border-amber-300 text-amber-800", icon: AlertTriangle },
  no_go:          { label: "No Go",          color: "bg-red-100 border-red-300 text-red-800",       icon: AlertTriangle },
};

function Select({ label, value, onChange, options }: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-[var(--ink-strong)] mb-1">{label}</label>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        className="w-full px-3 py-2 text-sm bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded-lg focus:outline-none focus:border-violet-400"
      >
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

function RiskSelect({ label, value, onChange }: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <Select label={label} value={value} onChange={onChange}
      options={RISK_LEVELS.map(r => ({ value: r, label: RISK_LABEL[r] }))} />
  );
}

function Toggle({ label, value, onChange }: {
  label: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 cursor-pointer p-2 rounded-lg hover:bg-[var(--bg-hover)]">
      <input
        type="checkbox"
        checked={value}
        onChange={e => onChange(e.target.checked)}
        className="w-4 h-4 accent-violet-600"
      />
      <span className="text-sm text-[var(--ink-mid)]">{label}</span>
    </label>
  );
}

export default function SimulationPage({ params }: PageProps) {
  const { org } = use(params);
  const [input, setInput] = useState<SimulationInput>({
    product_type: "",
    market: "",
    customer_segment: "",
    failure_criticality: "",
    revenue_risk: "",
    cost_risk: "",
    credit_risk: "",
    supply_risk: "",
    quality_risk: "",
    support_load: "",
    has_software: false,
    has_cloud: false,
    has_battery: false,
    has_grid_connection: false,
    has_single_source: false,
    new_suppliers: false,
    phase: "",
    save_as_scenario: false,
    scenario_name: "",
  });
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<SimResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const set = (key: keyof SimulationInput, value: unknown) =>
    setInput(i => ({ ...i, [key]: value }));

  const handleRun = async () => {
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const res = await runSimulation(input);
      setResult(res);
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setRunning(false);
    }
  };

  const outcomeConfig = result ? (OUTCOME_CONFIG[result.estimated_gate_outcome] ?? OUTCOME_CONFIG.conditional_go) : null;
  const OutcomeIcon = outcomeConfig?.icon ?? CheckCircle2;

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-bold text-[var(--ink-strong)] flex items-center gap-2">
          <PlayCircle className="h-5 w-5 text-teal-500" />
          Simulation / Vorschau
        </h1>
        <p className="text-sm text-[var(--ink-muted)] mt-0.5">
          Prüfmodell testen — welche Controls werden aktiv, welche Trigger feuern, was wäre das Gate-Ergebnis?
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input Panel */}
        <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] p-5 space-y-5">
          <h2 className="text-sm font-semibold text-[var(--ink-strong)]">Produktparameter eingeben</h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Select label="Produktart" value={input.product_type ?? ""}
              onChange={v => set("product_type", v)}
              options={[{ value: "", label: "Wählen…" }, ...PRODUCT_TYPES]} />
            <Select label="Markt / Region" value={input.market ?? ""}
              onChange={v => set("market", v)}
              options={[{ value: "", label: "Wählen…" }, ...MARKETS]} />
            <Select label="Kundensegment" value={input.customer_segment ?? ""}
              onChange={v => set("customer_segment", v)}
              options={[{ value: "", label: "Wählen…" }, ...SEGMENTS]} />
            <Select label="Projektphase" value={input.phase ?? ""}
              onChange={v => set("phase", v)}
              options={[
                { value: "", label: "–" },
                { value: "pilot", label: "Pilotphase" },
                { value: "series", label: "Serienphase" },
                { value: "existing", label: "Bestandsprodukt" },
              ]} />
          </div>

          <div>
            <p className="text-xs font-medium text-[var(--ink-muted)] uppercase tracking-wider mb-3">Risikobewertung</p>
            <div className="grid grid-cols-2 gap-3">
              <RiskSelect label="Ausfallkritikalität" value={input.failure_criticality ?? ""} onChange={v => set("failure_criticality", v)} />
              <RiskSelect label="Umsatzrisiko" value={input.revenue_risk ?? ""} onChange={v => set("revenue_risk", v)} />
              <RiskSelect label="Kostenrisiko" value={input.cost_risk ?? ""} onChange={v => set("cost_risk", v)} />
              <RiskSelect label="Kreditrisiko" value={input.credit_risk ?? ""} onChange={v => set("credit_risk", v)} />
              <RiskSelect label="Beschaffungsrisiko" value={input.supply_risk ?? ""} onChange={v => set("supply_risk", v)} />
              <RiskSelect label="Qualitätsrisiko" value={input.quality_risk ?? ""} onChange={v => set("quality_risk", v)} />
              <RiskSelect label="Supportlast" value={input.support_load ?? ""} onChange={v => set("support_load", v)} />
            </div>
          </div>

          <div>
            <p className="text-xs font-medium text-[var(--ink-muted)] uppercase tracking-wider mb-2">Produktmerkmale</p>
            <div className="grid grid-cols-2 gap-1">
              <Toggle label="Software/Firmware" value={!!input.has_software} onChange={v => set("has_software", v)} />
              <Toggle label="Cloud/App-Anteil" value={!!input.has_cloud} onChange={v => set("has_cloud", v)} />
              <Toggle label="Batterie enthalten" value={!!input.has_battery} onChange={v => set("has_battery", v)} />
              <Toggle label="Netzanschluss" value={!!input.has_grid_connection} onChange={v => set("has_grid_connection", v)} />
              <Toggle label="Single Source" value={!!input.has_single_source} onChange={v => set("has_single_source", v)} />
              <Toggle label="Neue Lieferanten" value={!!input.new_suppliers} onChange={v => set("new_suppliers", v)} />
            </div>
          </div>

          <div className="border-t border-[var(--border-subtle)] pt-4">
            <Toggle label="Als Szenario speichern" value={!!input.save_as_scenario} onChange={v => set("save_as_scenario", v)} />
            {input.save_as_scenario && (
              <input
                className="mt-2 w-full px-3 py-2 text-sm bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded-lg focus:outline-none focus:border-violet-400"
                placeholder="Szenario-Name"
                value={input.scenario_name ?? ""}
                onChange={e => set("scenario_name", e.target.value)}
              />
            )}
          </div>

          <button
            onClick={handleRun}
            disabled={running}
            className="w-full flex items-center justify-center gap-2 py-2.5 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700 transition-colors disabled:opacity-60"
          >
            <PlayCircle className="h-4 w-4" />
            {running ? "Simulation läuft…" : "Simulation starten"}
          </button>

          {error && <div className="p-3 rounded-lg bg-red-50 text-red-700 text-sm">{error}</div>}
        </div>

        {/* Result Panel */}
        <div className="space-y-4">
          {!result ? (
            <div className="flex items-center justify-center h-full min-h-64 bg-[var(--bg-card)] rounded-xl border border-dashed border-[var(--border-subtle)]">
              <div className="text-center">
                <PlayCircle className="h-10 w-10 text-slate-200 mx-auto mb-2" />
                <p className="text-sm text-[var(--ink-muted)]">Simulation noch nicht gestartet</p>
              </div>
            </div>
          ) : (
            <>
              {/* Gate Outcome */}
              <div className={`flex items-center gap-4 p-5 rounded-xl border-2 ${outcomeConfig?.color}`}>
                <OutcomeIcon className="h-8 w-8 shrink-0" />
                <div>
                  <p className="text-xs font-medium uppercase tracking-wider opacity-75">Geschätztes Gate-Ergebnis</p>
                  <p className="text-xl font-bold">{outcomeConfig?.label}</p>
                </div>
                <div className="ml-auto text-right">
                  <p className="text-2xl font-bold">{result.total_active_controls}</p>
                  <p className="text-xs opacity-75">Aktive Controls</p>
                </div>
              </div>

              {/* Fired Triggers */}
              {result.fired_triggers.length > 0 && (
                <div className="bg-[var(--bg-card)] rounded-xl border border-amber-200 p-4">
                  <p className="text-xs font-semibold text-amber-700 uppercase tracking-wider mb-2 flex items-center gap-1">
                    <Zap className="h-3.5 w-3.5" /> Ausgelöste Trigger ({result.fired_triggers.length})
                  </p>
                  <div className="space-y-1">
                    {result.fired_triggers.map(t => (
                      <div key={t.trigger_id} className="flex items-center gap-2 text-sm">
                        <Zap className="h-3.5 w-3.5 text-amber-400 shrink-0" />
                        <span className="text-[var(--ink-mid)]">{t.trigger_name}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Hard Stops */}
              {result.hard_stop_controls.length > 0 && (
                <div className="bg-red-50 rounded-xl border border-red-200 p-4">
                  <p className="text-xs font-semibold text-red-700 uppercase tracking-wider mb-2 flex items-center gap-1">
                    <AlertTriangle className="h-3.5 w-3.5" /> Hard-Stop Controls ({result.hard_stop_controls.length})
                  </p>
                  <div className="space-y-1">
                    {result.hard_stop_controls.map(c => (
                      <div key={c.id} className="flex items-center gap-2 text-sm">
                        <AlertTriangle className="h-3.5 w-3.5 text-red-400 shrink-0" />
                        <span className="text-red-700">{c.name}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Fixed Controls */}
              <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] p-4">
                <p className="text-xs font-semibold text-[var(--ink-muted)] uppercase tracking-wider mb-2 flex items-center gap-1">
                  <Lock className="h-3.5 w-3.5" /> Feste Controls ({result.fixed_controls.length})
                </p>
                <div className="space-y-1 max-h-40 overflow-auto">
                  {result.fixed_controls.map(c => (
                    <div key={c.id} className="flex items-center justify-between text-sm">
                      <span className="text-[var(--ink-mid)] truncate">{c.name}</span>
                      <div className="flex gap-1 shrink-0">
                        {c.gate_phases.map(g => (
                          <span key={g} className="px-1.5 py-0.5 rounded text-xs bg-violet-50 text-violet-600">{g}</span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Triggered Controls */}
              {result.triggered_controls.length > 0 && (
                <div className="bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)] p-4">
                  <p className="text-xs font-semibold text-[var(--ink-muted)] uppercase tracking-wider mb-2 flex items-center gap-1">
                    <Plus className="h-3.5 w-3.5" /> Trigger-aktivierte Controls ({result.triggered_controls.length})
                  </p>
                  <div className="space-y-1">
                    {result.triggered_controls.map(c => (
                      <div key={c.id} className="flex items-center justify-between text-sm">
                        <span className="text-[var(--ink-mid)]">{c.name}</span>
                        <div className="flex gap-1">
                          {c.gate_phases.map(g => (
                            <span key={g} className="px-1.5 py-0.5 rounded text-xs bg-amber-50 text-amber-600">{g}</span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {result.scenario_id && (
                <div className="p-3 rounded-lg bg-green-50 border border-green-200 text-xs text-green-700">
                  ✓ Szenario gespeichert (ID: {result.scenario_id})
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
