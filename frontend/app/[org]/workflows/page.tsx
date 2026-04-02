"use client";

import { use, useState } from "react";
import { useOrg } from "@/lib/hooks/useOrg";
import { apiRequest, fetcher } from "@/lib/api/client";
import useSWR from "swr";
import type { WorkflowDefinition, WorkflowExecution } from "@/types";
import { ExternalLink, Workflow, Play, CheckCircle2, XCircle, Clock, AlertCircle, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";

const TRIGGER_LABELS: Record<string, string> = {
  webhook:  "Webhook",
  schedule: "Zeitplan",
  event:    "Ereignis",
  manual:   "Manuell",
};

const STATUS_META: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  pending:   { label: "Ausstehend",   color: "bg-[var(--paper-warm)] text-[var(--ink-mid)]",                       icon: <Clock size={13} /> },
  running:   { label: "Läuft",        color: "bg-[rgba(74,85,104,.06)] text-[var(--navy)]",             icon: <RefreshCw size={13} className="animate-spin" /> },
  success:   { label: "Erfolgreich",  color: "bg-[rgba(82,107,94,.1)] text-[var(--green)]",             icon: <CheckCircle2 size={13} /> },
  failed:    { label: "Fehlgeschlagen",color: "bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)]",           icon: <XCircle size={13} /> },
  cancelled: { label: "Abgebrochen",  color: "bg-[rgba(122,100,80,.1)] text-[var(--brown)]",             icon: <AlertCircle size={13} /> },
};

function ExecutionRow({ execution }: { execution: WorkflowExecution }) {
  const meta = STATUS_META[execution.status] ?? STATUS_META.pending;
  const started = new Date(execution.started_at);
  const duration = execution.completed_at
    ? Math.round((new Date(execution.completed_at).getTime() - started.getTime()) / 1000)
    : null;

  return (
    <div className="flex items-center gap-3 px-4 py-2.5 border-t border-[var(--paper-rule)] text-sm">
      <span className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${meta.color}`}>
        {meta.icon}
        {meta.label}
      </span>
      <span className="text-[var(--ink-faint)] text-xs">
        {started.toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" })}
      </span>
      {duration !== null && (
        <span className="text-[var(--ink-faint)] text-xs">{duration}s</span>
      )}
      {execution.error_message && (
        <span className="flex-1 text-xs text-[var(--accent-red)] truncate">{execution.error_message}</span>
      )}
    </div>
  );
}

function WorkflowCard({
  workflow,
  orgId,
}: {
  workflow: WorkflowDefinition;
  orgId: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const [triggering, setTriggering] = useState(false);
  const [triggerError, setTriggerError] = useState<string | null>(null);

  const { data: executions, mutate } = useSWR<WorkflowExecution[]>(
    expanded ? `/api/v1/organizations/${orgId}/workflows/${workflow.id}/executions` : null,
    fetcher
  );

  async function handleTrigger() {
    setTriggering(true);
    setTriggerError(null);
    try {
      await apiRequest(
        `/api/v1/organizations/${orgId}/workflows/${workflow.id}/trigger`,
        { method: "POST", body: JSON.stringify({ input: {} }) }
      );
      if (expanded) void mutate();
    } catch (err: unknown) {
      setTriggerError((err as { error?: string })?.error ?? "Fehler beim Auslösen.");
    } finally {
      setTriggering(false);
    }
  }

  return (
    <div className="bg-[var(--card)] rounded-sm border border-[var(--paper-rule)] overflow-hidden">
      <div className="flex items-start gap-4 p-4 sm:p-5">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className={`w-2 h-2 rounded-full shrink-0 ${workflow.is_active ? "bg-[var(--green)]" : "bg-[var(--paper-rule)]"}`} />
            <h3 className="font-semibold text-[var(--ink)] text-sm">{workflow.name}</h3>
            <span className="px-1.5 py-0.5 rounded-sm bg-[var(--paper-warm)] text-[var(--ink-faint)] text-xs font-medium">
              {TRIGGER_LABELS[workflow.trigger_type] ?? workflow.trigger_type}
            </span>
            <span className="text-xs text-[var(--ink-faint)]">v{workflow.version}</span>
          </div>
          {workflow.description && (
            <p className="text-xs text-[var(--ink-faint)] mt-0.5 line-clamp-2">{workflow.description}</p>
          )}
          {triggerError && (
            <p className="text-xs text-[var(--accent-red)] mt-1">{triggerError}</p>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {workflow.trigger_type === "manual" && workflow.is_active && (
            <button
              onClick={() => void handleTrigger()}
              disabled={triggering}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] disabled:bg-[var(--ink-faint)] text-white rounded-sm text-xs font-medium transition-colors"
            >
              {triggering
                ? <RefreshCw size={12} className="animate-spin" />
                : <Play size={12} />}
              Auslösen
            </button>
          )}
          <button
            onClick={() => setExpanded((v) => !v)}
            className="flex items-center gap-1 px-2 py-1.5 border border-[var(--paper-rule)] text-[var(--ink-faint)] hover:bg-[var(--paper-warm)] rounded-sm text-xs transition-colors"
          >
            Läufe
            {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-[var(--paper-rule)]">
          {!executions ? (
            <div className="flex justify-center py-4">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-[var(--accent-red)]" />
            </div>
          ) : executions.length === 0 ? (
            <p className="text-center text-xs text-[var(--ink-faint)] py-4">Noch keine Ausführungen.</p>
          ) : (
            <div>
              {executions.slice(0, 10).map((e) => (
                <ExecutionRow key={e.id} execution={e} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function WorkflowsPage({ params }: { params: Promise<{ org: string }> }) {
  const resolvedParams = use(params);
  const { org } = useOrg(resolvedParams.org);

  const { data: workflows, isLoading, error } = useSWR<WorkflowDefinition[]>(
    org ? `/api/v1/organizations/${org.id}/workflows` : null,
    fetcher
  );

  const n8nUrl = typeof window !== "undefined"
    ? `${window.location.origin}/n8n/`
    : "/n8n/";

  const activeCount = workflows?.filter((w) => w.is_active).length ?? 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-[var(--ink)] flex items-center gap-2">
            <Workflow size={24} className="text-[var(--accent-red)]" />
            Workflows
          </h1>
          {workflows && (
            <p className="text-[var(--ink-faint)] mt-1 text-sm">
              {workflows.length} {workflows.length === 1 ? "Workflow" : "Workflows"}{" "}
              · {activeCount} aktiv
            </p>
          )}
        </div>

        <a
          href={n8nUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 px-4 py-2 bg-[#EA4B71] hover:bg-[#d43d63] text-white rounded-sm text-sm font-medium transition-colors"
        >
          <ExternalLink size={16} />
          n8n öffnen
        </a>
      </div>

      {/* n8n Info Banner */}
      <div className="flex items-start gap-3 p-4 bg-[var(--paper-warm)] border border-[var(--paper-rule)] rounded-sm">
        <div className="w-8 h-8 rounded-sm bg-[#EA4B71] flex items-center justify-center shrink-0">
          <Workflow size={16} className="text-white" />
        </div>
        <div>
          <p className="text-sm font-medium text-[var(--ink)]">n8n Workflow-Automatisierung</p>
          <p className="text-xs text-[var(--ink-faint)] mt-0.5">
            Workflows werden in n8n erstellt und verwaltet. Hier siehst du eine Übersicht der registrierten Workflows und kannst manuelle Ausführungen starten.
          </p>
        </div>
      </div>

      {/* Workflow list */}
      {isLoading && (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-7 w-7 border-b-2 border-[var(--accent-red)]" />
        </div>
      )}

      {error && (
        <div className="p-4 bg-[rgba(var(--accent-red-rgb),.08)] border border-[var(--accent-red)] rounded-sm text-[var(--accent-red)] text-sm">
          Fehler beim Laden der Workflows.
        </div>
      )}

      {workflows && workflows.length === 0 && (
        <div className="text-center py-16 bg-[var(--card)] rounded-sm border border-[var(--paper-rule)]">
          <Workflow size={40} className="mx-auto mb-3 text-[var(--ink-faint)]" />
          <h3 className="text-base font-semibold text-[var(--ink-mid)] mb-1">Noch keine Workflows</h3>
          <p className="text-sm text-[var(--ink-faint)] mb-5">
            Erstelle Workflows in n8n und registriere sie hier über die API.
          </p>
          <a
            href={n8nUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2 bg-[#EA4B71] hover:bg-[#d43d63] text-white rounded-sm text-sm font-medium transition-colors"
          >
            <ExternalLink size={15} />
            n8n öffnen
          </a>
        </div>
      )}

      {workflows && workflows.length > 0 && (
        <div className="space-y-3">
          {workflows.map((w) => (
            <WorkflowCard key={w.id} workflow={w} orgId={org!.id} />
          ))}
        </div>
      )}
    </div>
  );
}
