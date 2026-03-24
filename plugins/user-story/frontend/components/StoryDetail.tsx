"use client";

import { useState } from "react";
import useSWR, { mutate } from "swr";

import { apiRequest, fetcher } from "@/lib/api/client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type StoryStatus =
  | "draft"
  | "ready"
  | "in_progress"
  | "in_review"
  | "done"
  | "cancelled";

type StoryPriority = "low" | "medium" | "high" | "critical";
type TestCaseType = "unit" | "integration" | "e2e" | "manual";
type TestCaseStatus = "pending" | "passed" | "failed" | "skipped";

interface StoryRead {
  id: string;
  title: string;
  description: string | null;
  status: StoryStatus;
  priority: StoryPriority;
  story_points: number | null;
  assignee_id: string | null;
  reporter_id: string;
  group_id: string | null;
  parent_story_id: string | null;
  acceptance_criteria: string[] | null;
  created_at: string;
  updated_at: string | null;
}

interface TestCaseRead {
  id: string;
  story_id: string;
  title: string;
  description: string | null;
  type: TestCaseType;
  status: TestCaseStatus;
  steps: string[] | null;
  expected_result: string | null;
  actual_result: string | null;
  created_by: string;
  created_at: string;
}

interface StoryDetailProps {
  orgSlug: string;
  storyId: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STATUS_BADGE: Record<StoryStatus, string> = {
  draft: "bg-gray-100 text-gray-700",
  ready: "bg-blue-100 text-blue-700",
  in_progress: "bg-yellow-100 text-yellow-800",
  in_review: "bg-purple-100 text-purple-700",
  done: "bg-green-100 text-green-700",
  cancelled: "bg-red-100 text-red-700",
};

const STATUS_LABEL: Record<StoryStatus, string> = {
  draft: "Entwurf",
  ready: "Bereit",
  in_progress: "In Arbeit",
  in_review: "In Review",
  done: "Fertig",
  cancelled: "Abgebrochen",
};

const ALLOWED_TRANSITIONS: Record<StoryStatus, StoryStatus[]> = {
  draft: ["ready", "cancelled"],
  ready: ["in_progress", "draft"],
  in_progress: ["in_review", "draft"],
  in_review: ["done", "in_progress"],
  done: [],
  cancelled: [],
};

const TEST_CASE_STATUS_BADGE: Record<TestCaseStatus, string> = {
  pending: "bg-gray-100 text-gray-600",
  passed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  skipped: "bg-yellow-100 text-yellow-700",
};

const TEST_CASE_STATUS_LABEL: Record<TestCaseStatus, string> = {
  pending: "Ausstehend",
  passed: "Bestanden",
  failed: "Fehlgeschlagen",
  skipped: "Übersprungen",
};

// ---------------------------------------------------------------------------
// StoryDetail Component
// ---------------------------------------------------------------------------

export function StoryDetail({ orgSlug, storyId }: StoryDetailProps) {
  const storyKey = `/api/v1/organizations/${orgSlug}/stories/${storyId}`;
  const testCasesKey = `/api/v1/organizations/${orgSlug}/stories/${storyId}/test-cases`;

  const { data: story, error: storyError, isLoading: storyLoading } = useSWR<StoryRead>(
    storyKey,
    fetcher
  );
  const { data: testCases, isLoading: tcLoading } = useSWR<TestCaseRead[]>(
    testCasesKey,
    fetcher
  );

  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editPriority, setEditPriority] = useState<StoryPriority>("medium");
  const [editStoryPoints, setEditStoryPoints] = useState<string>("");
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [isTransitioning, setIsTransitioning] = useState(false);
  const [isAIDeliveryPending, setIsAIDeliveryPending] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  const startEditing = () => {
    if (!story) return;
    setEditTitle(story.title);
    setEditDescription(story.description ?? "");
    setEditPriority(story.priority);
    setEditStoryPoints(story.story_points !== null ? String(story.story_points) : "");
    setIsEditing(true);
    setSaveError(null);
  };

  const handleSave = async () => {
    if (!story) return;
    setIsSaving(true);
    setSaveError(null);
    try {
      await apiRequest(`/api/v1/organizations/${orgSlug}/stories/${storyId}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: editTitle,
          description: editDescription || null,
          priority: editPriority,
          story_points: editStoryPoints ? parseInt(editStoryPoints, 10) : null,
        }),
      });
      await mutate(storyKey);
      setIsEditing(false);
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Fehler beim Speichern");
    } finally {
      setIsSaving(false);
    }
  };

  const handleTransition = async (newStatus: StoryStatus) => {
    setIsTransitioning(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      await apiRequest(`/api/v1/organizations/${orgSlug}/stories/${storyId}/transition`, {
        method: "POST",
        body: JSON.stringify({ status: newStatus }),
      });
      await mutate(storyKey);
      setActionSuccess(`Status geändert zu: ${STATUS_LABEL[newStatus]}`);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Statusübergang fehlgeschlagen");
    } finally {
      setIsTransitioning(false);
    }
  };

  const handleAIDelivery = async () => {
    setIsAIDeliveryPending(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      await apiRequest(`/api/v1/organizations/${orgSlug}/stories/${storyId}/ai-delivery`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      setActionSuccess("AI Delivery wurde gestartet. Der Prozess läuft im Hintergrund.");
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "AI Delivery fehlgeschlagen");
    } finally {
      setIsAIDeliveryPending(false);
    }
  };

  if (storyLoading) {
    return (
      <div className="p-6 space-y-4">
        <div className="h-8 bg-gray-100 rounded animate-pulse w-1/2" />
        <div className="h-4 bg-gray-100 rounded animate-pulse w-3/4" />
        <div className="h-4 bg-gray-100 rounded animate-pulse w-2/3" />
      </div>
    );
  }

  if (storyError || !story) {
    return (
      <div className="p-6">
        <div className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          Story konnte nicht geladen werden.
        </div>
      </div>
    );
  }

  const allowedTransitions = ALLOWED_TRANSITIONS[story.status] ?? [];

  return (
    <div className="p-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-start justify-between mb-6 gap-4">
        <div className="flex-1">
          {isEditing ? (
            <input
              type="text"
              value={editTitle}
              onChange={(e) => setEditTitle(e.target.value)}
              className="w-full text-2xl font-semibold border-b-2 border-blue-500 outline-none pb-1"
            />
          ) : (
            <h1 className="text-2xl font-semibold text-gray-900">{story.title}</h1>
          )}
          <div className="flex items-center gap-2 mt-2">
            <span className={`inline-flex items-center px-2.5 py-1 rounded text-xs font-medium ${STATUS_BADGE[story.status]}`}>
              {STATUS_LABEL[story.status]}
            </span>
            {story.story_points !== null && (
              <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">
                {story.story_points} SP
              </span>
            )}
          </div>
        </div>

        <div className="flex gap-2 shrink-0">
          {isEditing ? (
            <>
              <button
                onClick={() => setIsEditing(false)}
                className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50"
              >
                Abbrechen
              </button>
              <button
                onClick={handleSave}
                disabled={isSaving}
                className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
              >
                {isSaving ? "Speichern..." : "Speichern"}
              </button>
            </>
          ) : (
            <button
              onClick={startEditing}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50 text-gray-700"
            >
              Bearbeiten
            </button>
          )}
        </div>
      </div>

      {saveError && (
        <div className="mb-4 rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {saveError}
        </div>
      )}
      {actionError && (
        <div className="mb-4 rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {actionError}
        </div>
      )}
      {actionSuccess && (
        <div className="mb-4 rounded border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">
          {actionSuccess}
        </div>
      )}

      <div className="grid grid-cols-3 gap-6">
        {/* Main content */}
        <div className="col-span-2 space-y-6">
          {/* Description */}
          <div>
            <h2 className="text-sm font-medium text-gray-700 mb-2">Beschreibung</h2>
            {isEditing ? (
              <textarea
                value={editDescription}
                onChange={(e) => setEditDescription(e.target.value)}
                rows={5}
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            ) : (
              <p className="text-sm text-gray-600 whitespace-pre-wrap">
                {story.description ?? <span className="text-gray-400 italic">Keine Beschreibung</span>}
              </p>
            )}
          </div>

          {/* Acceptance Criteria */}
          <div>
            <h2 className="text-sm font-medium text-gray-700 mb-2">Acceptance Criteria</h2>
            {story.acceptance_criteria && story.acceptance_criteria.length > 0 ? (
              <ul className="space-y-1">
                {story.acceptance_criteria.map((ac, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                    <span className="text-green-500 mt-0.5">✓</span>
                    <span>{ac}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-gray-400 italic">Keine Acceptance Criteria definiert.</p>
            )}
          </div>

          {/* Test Cases */}
          <div>
            <h2 className="text-sm font-medium text-gray-700 mb-2">Test Cases</h2>
            {tcLoading ? (
              <div className="h-16 bg-gray-100 rounded animate-pulse" />
            ) : testCases && testCases.length > 0 ? (
              <div className="space-y-2">
                {testCases.map((tc) => (
                  <div
                    key={tc.id}
                    className="flex items-center justify-between border border-gray-200 rounded p-3"
                  >
                    <div>
                      <p className="text-sm font-medium text-gray-800">{tc.title}</p>
                      <p className="text-xs text-gray-500 capitalize">{tc.type}</p>
                    </div>
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${TEST_CASE_STATUS_BADGE[tc.status]}`}
                    >
                      {TEST_CASE_STATUS_LABEL[tc.status]}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-400 italic">Keine Test Cases vorhanden.</p>
            )}
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-5">
          {/* Meta fields */}
          <div className="space-y-3">
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Priorität</p>
              {isEditing ? (
                <select
                  value={editPriority}
                  onChange={(e) => setEditPriority(e.target.value as StoryPriority)}
                  className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm"
                >
                  <option value="low">Niedrig</option>
                  <option value="medium">Mittel</option>
                  <option value="high">Hoch</option>
                  <option value="critical">Kritisch</option>
                </select>
              ) : (
                <p className="text-sm text-gray-800 capitalize">{story.priority}</p>
              )}
            </div>

            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Story Points</p>
              {isEditing ? (
                <select
                  value={editStoryPoints}
                  onChange={(e) => setEditStoryPoints(e.target.value)}
                  className="w-full border border-gray-300 rounded px-2 py-1.5 text-sm"
                >
                  <option value="">—</option>
                  {[1, 2, 3, 5, 8, 13].map((v) => (
                    <option key={v} value={v}>{v}</option>
                  ))}
                </select>
              ) : (
                <p className="text-sm text-gray-800">{story.story_points ?? "—"}</p>
              )}
            </div>

            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">Erstellt</p>
              <p className="text-sm text-gray-800">
                {new Date(story.created_at).toLocaleDateString("de-DE")}
              </p>
            </div>
          </div>

          {/* Status Transitions */}
          {allowedTransitions.length > 0 && (
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
                Status ändern
              </p>
              <div className="space-y-1.5">
                {allowedTransitions.map((nextStatus) => (
                  <button
                    key={nextStatus}
                    onClick={() => handleTransition(nextStatus)}
                    disabled={isTransitioning}
                    className="w-full text-left px-3 py-2 text-sm border border-gray-200 rounded hover:bg-gray-50 disabled:opacity-50 transition-colors"
                  >
                    → {STATUS_LABEL[nextStatus]}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* AI Delivery */}
          {(story.status === "ready" || story.status === "draft") && (
            <div>
              <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
                AI Delivery
              </p>
              <button
                onClick={handleAIDelivery}
                disabled={isAIDeliveryPending}
                className="w-full px-3 py-2 text-sm bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50 transition-colors"
              >
                {isAIDeliveryPending ? "Wird gestartet..." : "AI Delivery starten"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
