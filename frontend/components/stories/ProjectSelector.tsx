"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api/client";
import type { Project } from "@/types";

interface Props {
  orgId: string;
  value: string | null;
  onChange: (projectId: string | null) => void;
  disabled?: boolean;
  label?: string;
}

export function ProjectSelector({ orgId, value, onChange, disabled, label = "Projekt" }: Props) {
  const { data: projects } = useSWR<Project[]>(
    orgId ? `/api/v1/projects?org_id=${orgId}` : null,
    fetcher
  );

  const selected = projects?.find(p => p.id === value);

  return (
    <div>
      {label && <label className="block text-sm font-medium text-slate-700 mb-1.5">{label}</label>}
      <div className="flex items-center gap-2">
        {selected?.color && (
          <span
            className="w-3 h-3 rounded-full flex-shrink-0 border border-slate-200"
            style={{ background: selected.color }}
          />
        )}
        <select
          value={value ?? ""}
          onChange={e => onChange(e.target.value || null)}
          disabled={disabled}
          className="flex-1 px-3 py-2 text-sm border border-slate-300 rounded-lg outline-none focus:border-teal-400 focus:ring-2 focus:ring-teal-100 bg-white disabled:bg-slate-50 disabled:text-slate-500"
        >
          <option value="">— Kein Projekt —</option>
          {(projects ?? []).map(project => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
