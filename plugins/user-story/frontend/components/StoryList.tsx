"use client";

import Link from "next/link";
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

interface StoryRead {
  id: string;
  title: string;
  status: StoryStatus;
  priority: StoryPriority;
  story_points: number | null;
  assignee_id: string | null;
  reporter_id: string;
  group_id: string | null;
  description: string | null;
  acceptance_criteria: string[];
  created_at: string;
  updated_at: string | null;
}

interface PaginatedResponse {
  items: StoryRead[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

interface StoryListProps {
  orgSlug: string;
}

// ---------------------------------------------------------------------------
// Badge helpers
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

const PRIORITY_BADGE: Record<StoryPriority, string> = {
  low: "bg-gray-100 text-gray-600",
  medium: "bg-blue-100 text-blue-600",
  high: "bg-orange-100 text-orange-700",
  critical: "bg-red-100 text-red-700",
};

const PRIORITY_LABEL: Record<StoryPriority, string> = {
  low: "Niedrig",
  medium: "Mittel",
  high: "Hoch",
  critical: "Kritisch",
};

// ---------------------------------------------------------------------------
// Create Story Modal
// ---------------------------------------------------------------------------

interface CreateStoryModalProps {
  orgSlug: string;
  onClose: () => void;
  onCreated: () => void;
}

function CreateStoryModal({ orgSlug, onClose, onCreated }: CreateStoryModalProps) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<StoryPriority>("medium");
  const [storyPoints, setStoryPoints] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      await apiRequest(`/api/v1/organizations/${orgSlug}/stories`, {
        method: "POST",
        body: JSON.stringify({
          title,
          description: description || null,
          priority,
          story_points: storyPoints ? parseInt(storyPoints, 10) : null,
          acceptance_criteria: [],
        }),
      });
      onCreated();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fehler beim Erstellen der Story");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl p-6 w-full max-w-md">
        <h2 className="text-lg font-semibold mb-4">Neue User Story</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Titel *
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              maxLength={500}
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Als [Rolle] möchte ich [Aktion]..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Beschreibung
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Damit [Nutzen]..."
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Priorität
              </label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value as StoryPriority)}
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="low">Niedrig</option>
                <option value="medium">Mittel</option>
                <option value="high">Hoch</option>
                <option value="critical">Kritisch</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Story Points
              </label>
              <select
                value={storyPoints}
                onChange={(e) => setStoryPoints(e.target.value)}
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">—</option>
                {[1, 2, 3, 5, 8, 13].map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {error && (
            <p className="text-sm text-red-600">{error}</p>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm border border-gray-300 rounded hover:bg-gray-50"
            >
              Abbrechen
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !title.trim()}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {isSubmitting ? "Erstellen..." : "Erstellen"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// StoryList Component
// ---------------------------------------------------------------------------

export function StoryList({ orgSlug }: StoryListProps) {
  const [statusFilter, setStatusFilter] = useState<StoryStatus | "">("");
  const [priorityFilter, setPriorityFilter] = useState<StoryPriority | "">("");
  const [page, setPage] = useState(1);
  const [showCreateModal, setShowCreateModal] = useState(false);

  const params = new URLSearchParams({ page: String(page), page_size: "20" });
  if (statusFilter) params.set("status", statusFilter);
  if (priorityFilter) params.set("priority", priorityFilter);

  const swrKey = `/api/v1/organizations/${orgSlug}/stories?${params.toString()}`;
  const { data, error, isLoading } = useSWR<PaginatedResponse>(swrKey, fetcher);

  const handleCreated = () => {
    mutate(swrKey);
  };

  const handleAIDelivery = async (storyId: string) => {
    try {
      await apiRequest(`/api/v1/organizations/${orgSlug}/stories/${storyId}/ai-delivery`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      alert("AI Delivery wurde gestartet.");
    } catch (err) {
      alert("Fehler beim Starten von AI Delivery.");
    }
  };

  return (
    <div className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">User Stories</h1>
        <button
          onClick={() => setShowCreateModal(true)}
          className="px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors"
        >
          + Neue Story
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value as StoryStatus | "");
            setPage(1);
          }}
          className="border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Alle Status</option>
          {(Object.keys(STATUS_LABEL) as StoryStatus[]).map((s) => (
            <option key={s} value={s}>
              {STATUS_LABEL[s]}
            </option>
          ))}
        </select>

        <select
          value={priorityFilter}
          onChange={(e) => {
            setPriorityFilter(e.target.value as StoryPriority | "");
            setPage(1);
          }}
          className="border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Alle Prioritäten</option>
          {(Object.keys(PRIORITY_LABEL) as StoryPriority[]).map((p) => (
            <option key={p} value={p}>
              {PRIORITY_LABEL[p]}
            </option>
          ))}
        </select>
      </div>

      {/* Story Cards */}
      {isLoading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 bg-gray-100 rounded animate-pulse" />
          ))}
        </div>
      )}

      {error && (
        <div className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          Fehler beim Laden der Stories.
        </div>
      )}

      {data && (
        <>
          {data.items.length === 0 ? (
            <div className="text-center py-12 text-gray-500 text-sm">
              Keine Stories gefunden.
            </div>
          ) : (
            <div className="space-y-3">
              {data.items.map((story) => (
                <div
                  key={story.id}
                  className="bg-white border border-gray-200 rounded-lg p-4 hover:border-blue-300 transition-colors"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <Link
                        href={`/${orgSlug}/stories/${story.id}`}
                        className="text-sm font-medium text-gray-900 hover:text-blue-600 line-clamp-2"
                      >
                        {story.title}
                      </Link>
                      <div className="flex flex-wrap items-center gap-2 mt-2">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${STATUS_BADGE[story.status]}`}
                        >
                          {STATUS_LABEL[story.status]}
                        </span>
                        <span
                          className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${PRIORITY_BADGE[story.priority]}`}
                        >
                          {PRIORITY_LABEL[story.priority]}
                        </span>
                        {story.story_points !== null && (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-600">
                            {story.story_points} SP
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {story.status === "ready" && (
                        <button
                          onClick={() => handleAIDelivery(story.id)}
                          className="px-3 py-1.5 text-xs bg-indigo-600 text-white rounded hover:bg-indigo-700 transition-colors"
                        >
                          AI Delivery
                        </button>
                      )}
                      <Link
                        href={`/${orgSlug}/stories/${story.id}`}
                        className="px-3 py-1.5 text-xs border border-gray-300 rounded hover:bg-gray-50 text-gray-700 transition-colors"
                      >
                        Details
                      </Link>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Pagination */}
          {data.pages > 1 && (
            <div className="flex items-center justify-between mt-6 pt-4 border-t border-gray-200">
              <p className="text-sm text-gray-600">
                {data.total} Stories · Seite {data.page} von {data.pages}
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-40"
                >
                  Zurück
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
                  disabled={page === data.pages}
                  className="px-3 py-1.5 text-sm border border-gray-300 rounded hover:bg-gray-50 disabled:opacity-40"
                >
                  Weiter
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <CreateStoryModal
          orgSlug={orgSlug}
          onClose={() => setShowCreateModal(false)}
          onCreated={handleCreated}
        />
      )}
    </div>
  );
}
