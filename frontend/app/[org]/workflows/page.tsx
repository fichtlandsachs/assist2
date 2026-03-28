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
  pending:   { label: "Ausstehend",   color: "bg-[#f7f4ee] text-[#5a5040]",                       icon: <Clock size={13} /> },
  running:   { label: "Läuft",        color: "bg-[rgba(30,58,95,.06)] text-[#1e3a5f]",             icon: <RefreshCw size={13} className="animate-spin" /> },
  success:   { label: "Erfolgreich",  color: "bg-[rgba(45,106,79,.1)] text-[#2d6a4f]",             icon: <CheckCircle2 size={13} /> },
  failed:    { label: "Fehlgeschlagen",color: "bg-[rgba(192,57,43,.08)] text-[#c0392b]",           icon: <XCircle size={13} /> },
  cancelled: { label: "Abgebrochen",  color: "bg-[rgba(139,69,19,.1)] text-[#8b4513]",             icon: <AlertCircle size={13} /> },
};

function ExecutionRow({ execution }: { execution: WorkflowExecution }) {
  const meta = STATUS_META[execution.status] ?? STATUS_META.pending;
  const started = new Date(execution.started_at);
  const duration = execution.completed_at
    ? Math.round((new Date(execution.completed_at).getTime() - started.getTime()) / 1000)
    : null;

  return (
    <div className="flex items-center gap-3 px-4 py-2.5 border-t border-[#e2ddd4] text-sm">
      <span className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium ${meta.color}`}>
        {meta.icon}
        {meta.label}
      </span>
      <span className="text-[#a09080] text-xs">
        {started.toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" })}
      </span>
      {duration !== null && (
        <span className="text-[#a09080] text-xs">{duration}s</span>
      )}
      {execution.error_message && (
        <span className="flex-1 text-xs text-[#c0392b] truncate">{execution.error_message}</span>
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
    <div className="bg-[#faf9f6] rounded-sm border border-[#e2ddd4] overflow-hidden">
      <div className="flex items-start gap-4 p-4 sm:p-5">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <span className={`w-2 h-2 rounded-full shrink-0 ${workflow.is_active ? "bg-[#2d6a4f]" : "bg-[#e2ddd4]"}`} />
            <h3 className="font-semibold text-[#1c1810] text-sm">{workflow.name}</h3>
            <span className="px-1.5 py-0.5 rounded-sm bg-[#f7f4ee] text-[#a09080] text-xs font-medium">
              {TRIGGER_LABELS[workflow.trigger_type] ?? workflow.trigger_type}
            </span>
            <span className="text-xs text-[#a09080]">v{workflow.version}</span>
          </div>
          {workflow.description && (
            <p className="text-xs text-[#a09080] mt-0.5 line-clamp-2">{workflow.description}</p>
          )}
          {triggerError && (
            <p className="text-xs text-[#c0392b] mt-1">{triggerError}</p>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0">
          {workflow.trigger_type === "manual" && workflow.is_active && (
            <button
              onClick={() => void handleTrigger()}
              disabled={triggering}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[#c0392b] hover:bg-[#a93226] disabled:bg-[#a09080] text-white rounded-sm text-xs font-medium transition-colors"
            >
              {triggering
                ? <RefreshCw size={12} className="animate-spin" />
                : <Play size={12} />}
              Auslösen
            </button>
          )}
          <button
            onClick={() => setExpanded((v) => !v)}
            className="flex items-center gap-1 px-2 py-1.5 border border-[#e2ddd4] text-[#a09080] hover:bg-[#f7f4ee] rounded-sm text-xs transition-colors"
          >
            Läufe
            {expanded ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-[#e2ddd4]">
          {!executions ? (
            <div className="flex justify-center py-4">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-[#c0392b]" />
            </div>
          ) : executions.length === 0 ? (
            <p className="text-center text-xs text-[#a09080] py-4">Noch keine Ausführungen.</p>
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
          <h1 className="text-2xl font-bold text-[#1c1810] flex items-center gap-2">
            <Workflow size={24} className="text-[#c0392b]" />
            Workflows
          </h1>
          {workflows && (
            <p className="text-[#a09080] mt-1 text-sm">
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
      <div className="flex items-start gap-3 p-4 bg-[#f7f4ee] border border-[#e2ddd4] rounded-sm">
        <div className="w-8 h-8 rounded-sm bg-[#EA4B71] flex items-center justify-center shrink-0">
          <Workflow size={16} className="text-white" />
        </div>
        <div>
          <p className="text-sm font-medium text-[#1c1810]">n8n Workflow-Automatisierung</p>
          <p className="text-xs text-[#a09080] mt-0.5">
            Workflows werden in n8n erstellt und verwaltet. Hier siehst du eine Übersicht der registrierten Workflows und kannst manuelle Ausführungen starten.
          </p>
        </div>
      </div>

      {/* Workflow list */}
      {isLoading && (
        <div className="flex justify-center py-12">
          <div className="animate-spin rounded-full h-7 w-7 border-b-2 border-[#c0392b]" />
        </div>
      )}

      {error && (
        <div className="p-4 bg-[rgba(192,57,43,.08)] border border-[#c0392b] rounded-sm text-[#c0392b] text-sm">
          Fehler beim Laden der Workflows.
        </div>
      )}

      {workflows && workflows.length === 0 && (
        <div className="text-center py-16 bg-[#faf9f6] rounded-sm border border-[#e2ddd4]">
          <Workflow size={40} className="mx-auto mb-3 text-[#a09080]" />
          <h3 className="text-base font-semibold text-[#5a5040] mb-1">Noch keine Workflows</h3>
          <p className="text-sm text-[#a09080] mb-5">
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
