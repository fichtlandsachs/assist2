"use client";

import useSWR from "swr";
import { ShieldCheck, HelpCircle, CheckSquare, FileText } from "lucide-react";
import { fetcher } from "@/lib/api/client";
import type { ControlUserView } from "@/types";

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
  const { data, isLoading } = useSWR<ControlUserView[]>(
    `/api/v1/user-stories/${storyId}/relevant-controls?org_id=${orgId}`,
    fetcher,
    { revalidateOnFocus: false },
  );

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-xs text-[var(--ink-faint)] py-4">
        <div className="w-3 h-3 border border-current border-t-transparent rounded-full animate-spin" />
        Lade Hinweise…
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="rounded-lg border border-[var(--paper-rule)] bg-[var(--paper-warm)] px-4 py-6 text-center">
        <ShieldCheck size={20} className="mx-auto mb-2 text-[var(--ink-faintest)]" />
        <p className="text-sm text-[var(--ink-faint)]">
          Keine Hinweise für diese Story.
        </p>
        <p className="text-xs text-[var(--ink-faintest)] mt-1">
          Weise zuerst eine Business Capability im Prozesse-Tab zu.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-[var(--ink-faint)]">
        {data.length} {data.length === 1 ? "Hinweis" : "Hinweise"} für diese Story
      </p>
      {data.map((control) => (
        <UserHintCard key={control.id} control={control} />
      ))}
    </div>
  );
}
