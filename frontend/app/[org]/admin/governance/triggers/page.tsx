"use client";

import { use, useState } from "react";
import { Zap, Plus, Trash2, ToggleLeft, ToggleRight, ChevronDown, ChevronUp } from "lucide-react";
import { useTriggers, createTrigger, type TriggerRule } from "@/lib/hooks/useGovernance";
import { authFetch } from "@/lib/api/client";
import { mutate as globalMutate } from "swr";

interface PageProps {
  params: Promise<{ org: string }>;
}

const TRIGGER_FIELDS = [
  { value: "product_type",        label: "Produktart" },
  { value: "market",              label: "Markt / Region" },
  { value: "customer_segment",    label: "Kundensegment" },
  { value: "failure_criticality", label: "Ausfallkritikalität" },
  { value: "revenue_risk",        label: "Umsatzrisiko" },
  { value: "cost_risk",           label: "Kostenrisiko" },
  { value: "credit_risk",         label: "Kreditrisiko" },
  { value: "supply_risk",         label: "Beschaffungsrisiko" },
  { value: "quality_risk",        label: "Qualitätsrisiko" },
  { value: "support_load",        label: "Supportlast" },
  { value: "has_software",        label: "Software/Firmware enthalten" },
  { value: "has_cloud",           label: "Cloud/App-Anteil" },
  { value: "has_battery",         label: "Batterie enthalten" },
  { value: "has_grid_connection", label: "Netzanschluss vorhanden" },
  { value: "has_single_source",   label: "Single Source vorhanden" },
  { value: "new_suppliers",       label: "Neue Lieferanten" },
  { value: "phase",               label: "Projektphase" },
  { value: "service_intensity",   label: "Serviceintensität" },
];

const TRIGGER_OPS = [
  { value: "eq",      label: "= Gleich" },
  { value: "in",      label: "∈ Enthält" },
  { value: "gte",     label: "≥ Mindestens" },
  { value: "gt",      label: "> Größer als" },
  { value: "is_true", label: "☑ Ist gesetzt" },
];

function ConditionLeaf({
  condition, onChange, onRemove,
}: {
  condition: Record<string, unknown>;
  onChange: (c: Record<string, unknown>) => void;
  onRemove: () => void;
}) {
  return (
    <div className="flex items-center gap-2 p-3 rounded-lg bg-[var(--bg-base)] border border-[var(--border-subtle)]">
      <select
        value={condition.field as string ?? ""}
        onChange={e => onChange({ ...condition, field: e.target.value })}
        className="flex-1 px-2 py-1.5 text-xs bg-white border border-[var(--border-subtle)] rounded focus:outline-none"
      >
        <option value="">Feld wählen…</option>
        {TRIGGER_FIELDS.map(f => <option key={f.value} value={f.value}>{f.label}</option>)}
      </select>
      <select
        value={condition.op as string ?? "eq"}
        onChange={e => onChange({ ...condition, op: e.target.value })}
        className="px-2 py-1.5 text-xs bg-white border border-[var(--border-subtle)] rounded focus:outline-none"
      >
        {TRIGGER_OPS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      {condition.op !== "is_true" && (
        <input
          type="text"
          value={Array.isArray(condition.value) ? (condition.value as string[]).join(",") : (condition.value as string) ?? ""}
          onChange={e => onChange({
            ...condition,
            value: condition.op === "in"
              ? e.target.value.split(",").map(v => v.trim())
              : e.target.value
          })}
          placeholder={condition.op === "in" ? "val1,val2" : "Wert"}
          className="flex-1 px-2 py-1.5 text-xs bg-white border border-[var(--border-subtle)] rounded focus:outline-none"
        />
      )}
      <button onClick={onRemove} className="p-1.5 rounded hover:bg-red-50 text-red-400">
        <Trash2 className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

function ConditionGroup({
  node, onChange, onRemove, depth = 0,
}: {
  node: Record<string, unknown>;
  onChange: (n: Record<string, unknown>) => void;
  onRemove?: () => void;
  depth?: number;
}) {
  const conditions = (node.conditions as Record<string, unknown>[] ?? []);
  const op = node.operator as string ?? "AND";

  const addLeaf = () => onChange({
    ...node,
    conditions: [...conditions, { field: "", op: "eq", value: "" }],
  });

  const addGroup = () => onChange({
    ...node,
    conditions: [...conditions, { operator: "AND", conditions: [] }],
  });

  const updateChild = (i: number, child: Record<string, unknown>) => {
    const updated = [...conditions];
    updated[i] = child;
    onChange({ ...node, conditions: updated });
  };

  const removeChild = (i: number) => {
    onChange({ ...node, conditions: conditions.filter((_, idx) => idx !== i) });
  };

  return (
    <div className={`rounded-lg border ${depth === 0 ? "border-violet-200 bg-violet-50/30" : "border-slate-200 bg-slate-50/50"} p-3 space-y-2`}>
      <div className="flex items-center gap-2">
        <div className="flex gap-1">
          {["AND", "OR", "NOT"].map(o => (
            <button
              key={o}
              onClick={() => onChange({ ...node, operator: o })}
              className={`px-2.5 py-1 rounded text-xs font-medium ${
                op === o ? "bg-violet-600 text-white" : "bg-white border border-[var(--border-subtle)] text-[var(--ink-mid)]"
              }`}
            >
              {o}
            </button>
          ))}
        </div>
        <span className="text-xs text-[var(--ink-muted)]">Verknüpfung</span>
        {onRemove && (
          <button onClick={onRemove} className="ml-auto p-1 rounded hover:bg-red-50 text-red-400">
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
      <div className="space-y-2 pl-2">
        {conditions.map((child, i) =>
          "operator" in child ? (
            <ConditionGroup
              key={i}
              node={child}
              onChange={c => updateChild(i, c)}
              onRemove={() => removeChild(i)}
              depth={depth + 1}
            />
          ) : (
            <ConditionLeaf
              key={i}
              condition={child}
              onChange={c => updateChild(i, c)}
              onRemove={() => removeChild(i)}
            />
          )
        )}
      </div>
      <div className="flex gap-2 pt-1">
        <button onClick={addLeaf} className="flex items-center gap-1 px-2.5 py-1.5 text-xs bg-white border border-[var(--border-subtle)] rounded hover:border-violet-400">
          <Plus className="h-3 w-3" /> Bedingung
        </button>
        <button onClick={addGroup} className="flex items-center gap-1 px-2.5 py-1.5 text-xs bg-white border border-[var(--border-subtle)] rounded hover:border-violet-400">
          <Plus className="h-3 w-3" /> Gruppe
        </button>
      </div>
    </div>
  );
}

function TriggerCard({ trigger, onToggle, onDelete }: {
  trigger: TriggerRule;
  onToggle: () => void;
  onDelete: () => void;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className={`bg-[var(--bg-card)] rounded-xl border ${trigger.is_active ? "border-[var(--border-subtle)]" : "border-dashed border-slate-200"} overflow-hidden`}>
      <div className="flex items-center gap-3 px-4 py-3">
        <Zap className={`h-4 w-4 shrink-0 ${trigger.is_active ? "text-amber-500" : "text-slate-300"}`} />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-[var(--ink-strong)] truncate">{trigger.name}</p>
          <p className="text-xs text-[var(--ink-muted)] font-mono">{trigger.slug}</p>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <span className="text-xs text-[var(--ink-muted)] mr-1">P{trigger.priority}</span>
          <button onClick={onToggle} title={trigger.is_active ? "Deaktivieren" : "Aktivieren"}>
            {trigger.is_active
              ? <ToggleRight className="h-5 w-5 text-green-500" />
              : <ToggleLeft className="h-5 w-5 text-slate-300" />
            }
          </button>
          <button onClick={() => setExpanded(e => !e)} className="p-1 rounded hover:bg-[var(--bg-hover)]">
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>
      </div>
      {expanded && (
        <div className="px-4 pb-4 border-t border-[var(--border-subtle)] pt-3 space-y-3">
          {trigger.description && (
            <p className="text-xs text-[var(--ink-muted)]">{trigger.description}</p>
          )}
          <div>
            <p className="text-xs font-medium text-[var(--ink-muted)] mb-1">Bedingungsbaum:</p>
            <pre className="text-xs bg-[var(--bg-base)] p-2 rounded border border-[var(--border-subtle)] overflow-auto max-h-48 text-[var(--ink-mid)]">
              {JSON.stringify(trigger.condition_tree, null, 2)}
            </pre>
          </div>
          <p className="text-xs text-[var(--ink-muted)]">
            Aktiviert: {trigger.activates_control_ids.length} Control(s) · v{trigger.version}
          </p>
          <button
            onClick={onDelete}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-red-600 hover:bg-red-50 rounded"
          >
            <Trash2 className="h-3.5 w-3.5" /> Trigger löschen
          </button>
        </div>
      )}
    </div>
  );
}

export default function TriggersPage({ params }: PageProps) {
  const { org } = use(params);
  const { data: triggers, mutate } = useTriggers();
  const [creating, setCreating] = useState(false);
  const [newTrigger, setNewTrigger] = useState({
    slug: "",
    name: "",
    description: "",
    condition_tree: { operator: "AND", conditions: [] } as Record<string, unknown>,
    activates_control_ids: [] as string[],
    priority: 100,
    is_active: true,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleToggle = async (trigger: TriggerRule) => {
    try {
      await authFetch(`/api/v1/governance/triggers/${trigger.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: !trigger.is_active }),
      });
      mutate();
    } catch {}
  };

  const handleDelete = async (trigger: TriggerRule) => {
    if (!confirm(`Trigger "${trigger.name}" löschen?`)) return;
    try {
      await authFetch(`/api/v1/governance/triggers/${trigger.id}`, { method: "DELETE" });
      mutate();
    } catch (e: unknown) {
      alert((e as Error).message);
    }
  };

  const handleCreate = async () => {
    if (!newTrigger.name || !newTrigger.slug) {
      setError("Name und Slug erforderlich");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await createTrigger(newTrigger);
      mutate();
      setCreating(false);
      setNewTrigger({ slug: "", name: "", description: "", condition_tree: { operator: "AND", conditions: [] }, activates_control_ids: [], priority: 100, is_active: true });
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const cls = "w-full px-3 py-2 text-sm bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded-lg focus:outline-none focus:border-violet-400";

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-[var(--ink-strong)] flex items-center gap-2">
            <Zap className="h-5 w-5 text-amber-500" />
            Trigger-Regeln
          </h1>
          <p className="text-sm text-[var(--ink-muted)] mt-0.5">
            Kontextsensitive Regeln, die zusätzliche Controls aktivieren
          </p>
        </div>
        <button
          onClick={() => setCreating(c => !c)}
          className="flex items-center gap-2 px-4 py-2 bg-amber-600 text-white rounded-lg text-sm hover:bg-amber-700 transition-colors"
        >
          <Plus className="h-4 w-4" />
          Neuer Trigger
        </button>
      </div>

      {/* Create Form */}
      {creating && (
        <div className="bg-[var(--bg-card)] rounded-xl border border-amber-200 p-5 space-y-4">
          <h2 className="text-sm font-semibold text-[var(--ink-strong)]">Neuen Trigger erstellen</h2>
          {error && <div className="p-2 rounded bg-red-50 text-red-700 text-xs">{error}</div>}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium mb-1 text-[var(--ink-strong)]">Name *</label>
              <input className={cls} value={newTrigger.name} onChange={e => setNewTrigger(t => ({ ...t, name: e.target.value }))} />
            </div>
            <div>
              <label className="block text-xs font-medium mb-1 text-[var(--ink-strong)]">Slug *</label>
              <input className={cls} value={newTrigger.slug} onChange={e => setNewTrigger(t => ({ ...t, slug: e.target.value }))} />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium mb-1 text-[var(--ink-strong)]">Beschreibung</label>
            <textarea className={cls + " resize-y"} rows={2} value={newTrigger.description}
              onChange={e => setNewTrigger(t => ({ ...t, description: e.target.value }))} />
          </div>
          <div>
            <label className="block text-xs font-medium mb-2 text-[var(--ink-strong)]">Bedingungsbaum</label>
            <ConditionGroup
              node={newTrigger.condition_tree}
              onChange={tree => setNewTrigger(t => ({ ...t, condition_tree: tree }))}
            />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1 text-[var(--ink-strong)]">Priorität</label>
            <input type="number" min={1} className="w-24 px-3 py-2 text-sm bg-[var(--bg-base)] border border-[var(--border-subtle)] rounded-lg focus:outline-none"
              value={newTrigger.priority} onChange={e => setNewTrigger(t => ({ ...t, priority: parseInt(e.target.value) }))} />
          </div>
          <div className="flex gap-3">
            <button onClick={handleCreate} disabled={saving}
              className="px-4 py-2 bg-amber-600 text-white rounded-lg text-sm hover:bg-amber-700 disabled:opacity-60">
              {saving ? "Speichern…" : "Trigger erstellen"}
            </button>
            <button onClick={() => { setCreating(false); setError(null); }}
              className="px-4 py-2 text-sm text-[var(--ink-muted)] hover:text-[var(--ink-mid)]">
              Abbrechen
            </button>
          </div>
        </div>
      )}

      {/* Trigger List */}
      <div className="space-y-3">
        {!triggers || triggers.length === 0 ? (
          <div className="text-center py-12 bg-[var(--bg-card)] rounded-xl border border-[var(--border-subtle)]">
            <Zap className="h-10 w-10 text-slate-300 mx-auto mb-3" />
            <p className="text-sm text-[var(--ink-muted)]">Keine Trigger-Regeln konfiguriert.</p>
            <p className="text-xs text-[var(--ink-muted)] mt-1">Lade Seed-Daten um Beispiel-Trigger zu erhalten.</p>
          </div>
        ) : (
          triggers.map(trigger => (
            <TriggerCard
              key={trigger.id}
              trigger={trigger}
              onToggle={() => handleToggle(trigger)}
              onDelete={() => handleDelete(trigger)}
            />
          ))
        )}
      </div>
    </div>
  );
}
