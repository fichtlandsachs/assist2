"use client";

import { useState } from "react";
import { Save, X, Plus, Trash2 } from "lucide-react";
import { apiRequest } from "@/lib/api/client";
import type { Control } from "@/types";

interface Props {
  control: Control;
  orgId: string;
  onSaved: (updated: Control) => void;
  onClose: () => void;
}

function StringListEditor({
  label,
  items,
  onChange,
}: {
  label: string;
  items: string[];
  onChange: (items: string[]) => void;
}) {
  const add = () => onChange([...items, ""]);
  const remove = (i: number) => onChange(items.filter((_, idx) => idx !== i));
  const update = (i: number, v: string) =>
    onChange(items.map((item, idx) => (idx === i ? v : item)));

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label className="text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide">
          {label}
        </label>
        <button
          onClick={add}
          className="text-xs text-[var(--btn-primary)] hover:underline flex items-center gap-0.5"
        >
          <Plus size={11} /> Hinzufügen
        </button>
      </div>
      <div className="space-y-1.5">
        {items.map((item, i) => (
          <div key={i} className="flex gap-1.5">
            <input
              value={item}
              onChange={(e) => update(i, e.target.value)}
              className="flex-1 text-sm border border-[var(--paper-rule)] rounded px-2 py-1 bg-[var(--card)] text-[var(--ink)] focus:outline-none focus:border-[var(--btn-primary)]"
            />
            <button
              onClick={() => remove(i)}
              className="p-1 text-[var(--ink-faint)] hover:text-red-500 transition-colors"
            >
              <Trash2 size={13} />
            </button>
          </div>
        ))}
        {items.length === 0 && (
          <p className="text-xs text-[var(--ink-faintest)] italic">Noch keine Einträge</p>
        )}
      </div>
    </div>
  );
}

export function ControlEditor({ control, orgId, onSaved, onClose }: Props) {
  const [saving, setSaving] = useState(false);

  const [userTitle, setUserTitle] = useState(control.user_title ?? "");
  const [userExplanation, setUserExplanation] = useState(control.user_explanation ?? "");
  const [userAction, setUserAction] = useState(control.user_action ?? "");
  const [userQuestions, setUserQuestions] = useState<string[]>(
    control.user_guiding_questions ?? [],
  );
  const [userEvidence, setUserEvidence] = useState<string[]>(
    control.user_evidence_needed ?? [],
  );

  const [govTitle, setGovTitle] = useState(control.title);
  const [govDescription, setGovDescription] = useState(control.description ?? "");
  const [govType, setGovType] = useState(control.control_type);
  const [govStatus, setGovStatus] = useState(control.implementation_status);
  const [govInterval, setGovInterval] = useState(control.review_interval_days);
  const [govRefs, setGovRefs] = useState<string[]>(control.framework_refs ?? []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const updated = await apiRequest<Control>(
        `/api/v1/controls/orgs/${orgId}/${control.id}`,
        {
          method: "PATCH",
          body: JSON.stringify({
            title: govTitle,
            description: govDescription,
            control_type: govType,
            implementation_status: govStatus,
            review_interval_days: govInterval,
            framework_refs: govRefs,
            user_title: userTitle,
            user_explanation: userExplanation,
            user_action: userAction,
            user_guiding_questions: userQuestions,
            user_evidence_needed: userEvidence,
          }),
        },
      );
      onSaved(updated);
    } finally {
      setSaving(false);
    }
  };

  const inputCls =
    "w-full text-sm border border-[var(--paper-rule)] rounded px-2.5 py-1.5 bg-[var(--card)] text-[var(--ink)] focus:outline-none focus:border-[var(--btn-primary)]";
  const labelCls =
    "block text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide mb-1";
  const textareaCls = inputCls + " resize-none";

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--paper-rule)]">
        <h3 className="text-sm font-semibold text-[var(--ink)] truncate flex-1 mr-4">
          Control bearbeiten
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-[var(--btn-primary)] text-white hover:opacity-90 transition-opacity disabled:opacity-60"
          >
            <Save size={12} />
            {saving ? "Speichern…" : "Speichern"}
          </button>
          <button
            onClick={onClose}
            className="p-1.5 text-[var(--ink-faint)] hover:text-[var(--ink)]"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto grid grid-cols-2 divide-x divide-[var(--paper-rule)]">
        <div className="px-4 py-4 space-y-4 overflow-auto">
          <div className="flex items-center gap-2 mb-2 pb-2 border-b border-[var(--paper-rule)]">
            <div className="w-2 h-2 rounded-full bg-[var(--green,#527b5e)]" />
            <span className="text-xs font-bold text-[var(--green,#527b5e)] uppercase tracking-wide">
              Nutzer-Ebene
            </span>
            <span className="text-[10px] text-[var(--ink-faintest)]">(sichtbar für alle)</span>
          </div>

          <div>
            <label className={labelCls}>Titel (verständlich)</label>
            <input
              value={userTitle}
              onChange={(e) => setUserTitle(e.target.value)}
              placeholder={govTitle}
              className={inputCls}
            />
          </div>

          <div>
            <label className={labelCls}>Warum wichtig?</label>
            <textarea
              value={userExplanation}
              onChange={(e) => setUserExplanation(e.target.value)}
              rows={3}
              className={textareaCls}
            />
          </div>

          <div>
            <label className={labelCls}>Was zu tun ist</label>
            <textarea
              value={userAction}
              onChange={(e) => setUserAction(e.target.value)}
              rows={3}
              className={textareaCls}
            />
          </div>

          <StringListEditor
            label="Leitfragen"
            items={userQuestions}
            onChange={setUserQuestions}
          />

          <StringListEditor
            label="Benötigte Nachweise"
            items={userEvidence}
            onChange={setUserEvidence}
          />
        </div>

        <div className="px-4 py-4 space-y-4 overflow-auto">
          <div className="flex items-center gap-2 mb-2 pb-2 border-b border-[var(--paper-rule)]">
            <div className="w-2 h-2 rounded-full bg-[var(--navy,#2d3a8c)]" />
            <span className="text-xs font-bold text-[var(--navy,#2d3a8c)] uppercase tracking-wide">
              Governance-Ebene
            </span>
            <span className="text-[10px] text-[var(--ink-faintest)]">(nur Admins)</span>
          </div>

          <div>
            <label className={labelCls}>Technischer Titel</label>
            <input
              value={govTitle}
              onChange={(e) => setGovTitle(e.target.value)}
              className={inputCls}
            />
          </div>

          <div>
            <label className={labelCls}>Beschreibung</label>
            <textarea
              value={govDescription}
              onChange={(e) => setGovDescription(e.target.value)}
              rows={3}
              className={textareaCls}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>Typ</label>
              <select
                value={govType}
                onChange={(e) => setGovType(e.target.value as Control["control_type"])}
                className={inputCls}
              >
                <option value="preventive">Preventive</option>
                <option value="detective">Detective</option>
                <option value="corrective">Corrective</option>
                <option value="compensating">Compensating</option>
              </select>
            </div>
            <div>
              <label className={labelCls}>Status</label>
              <select
                value={govStatus}
                onChange={(e) => setGovStatus(e.target.value as Control["implementation_status"])}
                className={inputCls}
              >
                <option value="not_started">Nicht gestartet</option>
                <option value="in_progress">In Arbeit</option>
                <option value="implemented">Implementiert</option>
                <option value="verified">Verifiziert</option>
              </select>
            </div>
          </div>

          <div>
            <label className={labelCls}>Prüfintervall (Tage)</label>
            <input
              type="number"
              value={govInterval}
              onChange={(e) => setGovInterval(Number(e.target.value))}
              min={1}
              className={inputCls}
            />
          </div>

          <StringListEditor
            label="Framework-Referenzen (ISO 27001:A.x, NIS2:Art.x …)"
            items={govRefs}
            onChange={setGovRefs}
          />
        </div>
      </div>
    </div>
  );
}
