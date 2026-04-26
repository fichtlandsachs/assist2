"use client";

import { useState } from "react";
import useSWR from "swr";
import { ShieldCheck, HelpCircle, CheckSquare, FileText, MapPin, MessageSquare, X } from "lucide-react";
import { fetcher } from "@/lib/api/client";
import type { ControlUserView, UserStory } from "@/types";
import { StoryCapabilityChatPanel } from "@/components/stories/StoryCapabilityChatPanel";

interface CapabilityAssignment {
  assignment_id: string;
  node_id: string;
  node_path: string;
}

interface Props {
  storyId: string;
  orgId: string;
}

function UserHintCard({ control }: { control: ControlUserView }) {
  return (
    <div className="rounded-lg border border-[var(--paper-rule)] bg-[var(--card)] overflow-hidden">
      <div className="px-4 py-3 bg-[var(--paper-warm)] border-b border-[var(--paper-rule)] flex items-center gap-2">
        <ShieldCheck size={14} className="text-[var(--green,#527b5e)] shrink-0" />
        <span className="text-sm font-semibold text-[var(--ink)]">{control.user_title}</span>
        {control.is_inherited && (
          <span className="ml-auto text-[10px] text-[var(--ink-faint)] italic">(vererbt)</span>
        )}
      </div>

      <div className="px-4 py-3 space-y-4">
        {control.user_explanation && (
          <p className="text-sm text-[var(--ink-mid)]">{control.user_explanation}</p>
        )}

        {control.user_action && (
          <div className="rounded-md bg-[rgba(82,123,94,.08)] border border-[var(--green,#527b5e)] px-3 py-2.5">
            <p className="text-xs font-semibold text-[var(--green,#527b5e)] uppercase tracking-wide mb-1">
              Was zu tun ist
            </p>
            <p className="text-sm text-[var(--ink)]">{control.user_action}</p>
          </div>
        )}

        {control.user_guiding_questions && control.user_guiding_questions.length > 0 && (
          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <HelpCircle size={12} className="text-[var(--ink-faint)]" />
              <p className="text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide">
                Leitfragen
              </p>
            </div>
            <ol className="space-y-1">
              {control.user_guiding_questions.map((q, i) => (
                <li key={i} className="text-sm text-[var(--ink-mid)] flex gap-2">
                  <span className="text-[var(--ink-faint)] shrink-0">{i + 1}.</span>
                  <span>{q}</span>
                </li>
              ))}
            </ol>
          </div>
        )}

        {control.user_evidence_needed && control.user_evidence_needed.length > 0 && (
          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <FileText size={12} className="text-[var(--ink-faint)]" />
              <p className="text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide">
                Benötigte Nachweise
              </p>
            </div>
            <ul className="space-y-1">
              {control.user_evidence_needed.map((e, i) => (
                <li key={i} className="flex items-start gap-2 text-sm text-[var(--ink-mid)]">
                  <CheckSquare size={13} className="text-[var(--green,#527b5e)] shrink-0 mt-0.5" />
                  <span>{e}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

export function StoryCompliancePanel({ storyId, orgId }: Props) {
  const [chatOpen, setChatOpen] = useState(false);

  const { data: assignment, mutate: mutateAssignment, isLoading: assignmentLoading } = useSWR<CapabilityAssignment | null>(
    `/api/v1/user-stories/${storyId}/capability-assignment?org_id=${orgId}`,
    fetcher,
    { revalidateOnFocus: false },
  );

  const { data: controls, isLoading: controlsLoading, mutate: mutateControls } = useSWR<ControlUserView[]>(
    assignment ? `/api/v1/user-stories/${storyId}/relevant-controls?org_id=${orgId}` : null,
    fetcher,
    { revalidateOnFocus: false },
  );

  const isLoading = assignmentLoading || (!!assignment && controlsLoading);

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-xs text-[var(--ink-faint)] py-4">
        <div className="w-3 h-3 border border-current border-t-transparent rounded-full animate-spin" />
        Lade…
      </div>
    );
  }

  // No capability assigned → prompt user to assign one
  if (!assignment) {
    return (
      <div className="rounded-lg border border-[var(--btn-primary)] bg-[var(--paper-warm)] overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-[var(--paper-rule2)]">
          <div className="w-8 h-8 rounded-full bg-[rgba(var(--btn-primary-rgb),.08)] flex items-center justify-center shrink-0">
            <MapPin size={15} className="text-[var(--btn-primary)]" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-[var(--ink)]">Kein Prozess zugewiesen</p>
            <p className="text-xs text-[var(--ink-faint)] mt-0.5">
              Ohne Prozesszuordnung können keine Compliance-Hinweise angezeigt werden.
            </p>
          </div>
        </div>

        {/* CTA */}
        {!chatOpen ? (
          <div className="px-4 py-4 flex flex-col gap-3">
            <p className="text-sm text-[var(--ink-mid)]">
              Weise dieser Story einen Prozess aus der Business Capability Map zu — Karl hilft dir dabei.
            </p>
            <button
              onClick={() => setChatOpen(true)}
              className="flex items-center gap-2 self-start px-3 py-1.5 rounded-lg bg-[var(--btn-primary)] text-[var(--paper)] text-sm font-medium hover:opacity-85 transition-opacity"
            >
              <MessageSquare size={13} />
              Prozess via Chat zuweisen
            </button>
          </div>
        ) : (
          <div className="px-4 py-4 space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide">
                Prozesszuordnung
              </p>
              <button
                onClick={() => setChatOpen(false)}
                className="text-[var(--ink-faint)] hover:text-[var(--ink)] transition-colors"
              >
                <X size={13} />
              </button>
            </div>
            <StoryCapabilityChatPanel
              storyId={storyId}
              orgId={orgId}
              story={{} as UserStory}
              onAssigned={async () => {
                await mutateAssignment();
                await mutateControls();
                setChatOpen(false);
              }}
            />
          </div>
        )}
      </div>
    );
  }

  // Capability assigned but no controls configured
  if (!controls || controls.length === 0) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--paper-warm)] border border-[var(--paper-rule2)]">
          <MapPin size={12} className="text-[var(--ink-faint)] shrink-0" />
          <p className="text-xs text-[var(--ink-faint)] truncate">{assignment.node_path}</p>
        </div>
        <div className="rounded-lg border border-[var(--paper-rule)] bg-[var(--paper-warm)] px-4 py-6 text-center">
          <ShieldCheck size={20} className="mx-auto mb-2 text-[var(--ink-faintest)]" />
          <p className="text-sm text-[var(--ink-faint)]">Keine Compliance-Hinweise für diesen Prozess.</p>
          <p className="text-xs text-[var(--ink-faintest)] mt-1">
            Der zugewiesene Prozess hat noch keine Controls hinterlegt.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-[var(--ink-faint)]">
          {controls.length} {controls.length === 1 ? "Hinweis" : "Hinweise"} für diese Story
        </p>
        <div className="flex items-center gap-1.5 text-xs text-[var(--ink-faint)]">
          <MapPin size={11} />
          <span className="truncate max-w-[200px]">{assignment.node_path}</span>
        </div>
      </div>
      {controls.map((control) => (
        <UserHintCard key={control.id} control={control} />
      ))}
    </div>
  );
}
