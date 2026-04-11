"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api/client";
import type { Project } from "@/types";
import { useT } from "@/lib/i18n/context";

interface Props {
  orgId: string;
  value: string | null;
  onChange: (projectId: string | null) => void;
  disabled?: boolean;
  label?: string;
}

export function ProjectSelector({ orgId, value, onChange, disabled, label }: Props) {
  const { t } = useT();
  const resolvedLabel = label ?? t("story_detail_field_project");
  const { data: projects } = useSWR<Project[]>(
    orgId ? `/api/v1/projects?org_id=${orgId}` : null,
    fetcher
  );

  const selected = projects?.find(p => p.id === value);

  return (
    <div>
      {resolvedLabel && <label className="block text-sm font-medium text-[var(--ink-mid)] mb-1.5">{resolvedLabel}</label>}
      {disabled ? (
        <div className="flex items-center gap-2 px-3 py-2 text-sm text-[var(--ink-mid)] bg-[var(--paper-warm)] rounded-sm border border-[var(--paper-rule)]">
          {selected?.color && (
            <span className="w-3 h-3 rounded-full shrink-0" style={{ background: selected.color }} />
          )}
          <span>{selected?.name ?? "—"}</span>
        </div>
      ) : (
        <div className="flex items-center gap-2">
          {selected?.color && (
            <span
              className="w-3 h-3 rounded-full flex-shrink-0 border border-[var(--paper-rule)]"
              style={{ background: selected.color }}
            />
          )}
          <select
            value={value ?? ""}
            onChange={e => onChange(e.target.value || null)}
            className="flex-1 px-3 py-2 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[rgba(var(--accent-red-rgb),.08)] bg-[var(--card)]"
          >
            <option value="">— {t("story_detail_field_project_none")} —</option>
            {(projects ?? []).map(project => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
}
