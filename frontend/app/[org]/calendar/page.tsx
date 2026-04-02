"use client";

import { use, useState } from "react";
import { useOrg } from "@/lib/hooks/useOrg";
import { apiRequest, fetcher } from "@/lib/api/client";
import useSWR from "swr";
import type { CalendarConnection, CalendarEvent, CalendarProvider } from "@/types";
import { ChevronLeft, ChevronRight, Plus, X, Calendar } from "lucide-react";

const WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];
const MONTHS = [
  "Januar", "Februar", "März", "April", "Mai", "Juni",
  "Juli", "August", "September", "Oktober", "November", "Dezember",
];

const EVENT_COLORS = [
  "bg-[var(--accent-red)]", "bg-[var(--navy)]", "bg-[var(--green)]", "bg-[var(--brown)]",
  "bg-[var(--btn-primary)]", "bg-[var(--accent-red)]", "bg-[var(--accent-red)]", "bg-[var(--green)]",
];

function getMonthStart(year: number, month: number): Date {
  return new Date(year, month, 1);
}

function getCalendarDays(year: number, month: number): (Date | null)[] {
  const firstDay = getMonthStart(year, month);
  // Monday=0 offset
  let startOffset = firstDay.getDay() - 1;
  if (startOffset < 0) startOffset = 6;

  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const cells: (Date | null)[] = [];

  for (let i = 0; i < startOffset; i++) cells.push(null);
  for (let d = 1; d <= daysInMonth; d++) cells.push(new Date(year, month, d));

  // Pad to complete last row
  while (cells.length % 7 !== 0) cells.push(null);
  return cells;
}

function isSameDay(a: Date, b: Date): boolean {
  return a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate();
}

function colorForEvent(event: CalendarEvent): string {
  let hash = 0;
  for (let i = 0; i < event.id.length; i++) hash = event.id.charCodeAt(i) + ((hash << 5) - hash);
  return EVENT_COLORS[Math.abs(hash) % EVENT_COLORS.length];
}

export default function CalendarPage({ params }: { params: Promise<{ org: string }> }) {
  const resolvedParams = use(params);
  const { org } = useOrg(resolvedParams.org);
  const today = new Date();
  const [viewYear, setViewYear] = useState(today.getFullYear());
  const [viewMonth, setViewMonth] = useState(today.getMonth());
  const [selectedDay, setSelectedDay] = useState<Date | null>(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [showConnectModal, setShowConnectModal] = useState(false);

  // Create form state
  const [formTitle, setFormTitle] = useState("");
  const [formDate, setFormDate] = useState("");
  const [formTime, setFormTime] = useState("09:00");
  const [formEndTime, setFormEndTime] = useState("10:00");
  const [formDescription, setFormDescription] = useState("");
  const [saving, setSaving] = useState(false);

  // Connect modal state
  const [connectProvider, setConnectProvider] = useState<CalendarProvider>("google");
  const [connectEmail, setConnectEmail] = useState("");
  const [connecting, setConnecting] = useState(false);

  const monthStart = new Date(viewYear, viewMonth, 1);
  const monthEnd = new Date(viewYear, viewMonth + 1, 0, 23, 59, 59);

  const { data: events, isLoading, mutate } = useSWR<CalendarEvent[]>(
    org
      ? `/api/v1/calendar/events?org_id=${org.id}&from=${monthStart.toISOString()}&to=${monthEnd.toISOString()}`
      : null,
    fetcher
  );

  const { data: connections } = useSWR<CalendarConnection[]>(
    org ? `/api/v1/calendar/connections?org_id=${org.id}` : null,
    fetcher
  );

  const calDays = getCalendarDays(viewYear, viewMonth);

  function eventsForDay(date: Date): CalendarEvent[] {
    if (!events) return [];
    return events.filter((ev) => isSameDay(new Date(ev.start_at), date));
  }

  function prevMonth() {
    if (viewMonth === 0) { setViewYear(y => y - 1); setViewMonth(11); }
    else setViewMonth(m => m - 1);
  }

  function nextMonth() {
    if (viewMonth === 11) { setViewYear(y => y + 1); setViewMonth(0); }
    else setViewMonth(m => m + 1);
  }

  async function handleCreateEvent(e: React.FormEvent) {
    e.preventDefault();
    if (!org || !formTitle.trim() || !formDate) return;
    setSaving(true);
    try {
      const startAt = new Date(`${formDate}T${formTime}`).toISOString();
      const endAt = new Date(`${formDate}T${formEndTime}`).toISOString();
      await apiRequest("/api/v1/calendar/events", {
        method: "POST",
        body: JSON.stringify({
          organization_id: org.id,
          title: formTitle,
          description: formDescription || null,
          start_at: startAt,
          end_at: endAt,
          all_day: false,
        }),
      });
      await mutate();
      setFormTitle("");
      setFormDate("");
      setFormTime("09:00");
      setFormEndTime("10:00");
      setFormDescription("");
      setShowCreateForm(false);
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  }

  async function handleConnect(e: React.FormEvent) {
    e.preventDefault();
    if (!org || !connectEmail.trim()) return;
    setConnecting(true);
    try {
      await apiRequest("/api/v1/calendar/connections", {
        method: "POST",
        body: JSON.stringify({
          organization_id: org.id,
          provider: connectProvider,
          email_address: connectEmail,
        }),
      });
      setShowConnectModal(false);
      setConnectEmail("");
    } catch {
      // ignore
    } finally {
      setConnecting(false);
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-[var(--ink)]">Kalender</h1>
          <p className="text-[var(--ink-faint)] mt-1 text-sm">Termine und Ereignisse</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowConnectModal(true)}
            className="flex items-center gap-2 px-4 py-2 border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:bg-[var(--paper-warm)] rounded-sm text-sm font-medium transition-colors"
          >
            <Calendar size={15} />
            Kalender verbinden
          </button>
          <button
            onClick={() => setShowCreateForm(true)}
            className="flex items-center gap-2 px-4 py-2 bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] text-white rounded-sm text-sm font-medium transition-colors"
          >
            <Plus size={16} />
            Termin erstellen
          </button>
        </div>
      </div>

      {/* Calendar */}
      <div className="bg-[var(--paper)] rounded-sm border border-[var(--paper-rule)] overflow-hidden">
        {/* Navigation */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--paper-rule)]">
          <button
            onClick={prevMonth}
            className="p-2 rounded-sm hover:bg-[var(--paper-warm)] text-[var(--ink-mid)] transition-colors"
          >
            <ChevronLeft size={18} />
          </button>
          <h2 className="text-lg font-semibold text-[var(--ink)]">
            {MONTHS[viewMonth]} {viewYear}
          </h2>
          <button
            onClick={nextMonth}
            className="p-2 rounded-sm hover:bg-[var(--paper-warm)] text-[var(--ink-mid)] transition-colors"
          >
            <ChevronRight size={18} />
          </button>
        </div>

        {/* Day headers */}
        <div className="grid grid-cols-7 border-b border-[var(--paper-rule)]">
          {WEEKDAYS.map((d) => (
            <div key={d} className="text-center text-xs font-semibold text-[var(--ink-faint)] py-2 uppercase tracking-wide">
              {d}
            </div>
          ))}
        </div>

        {/* Calendar grid */}
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--accent-red)]" />
          </div>
        ) : (
          <div className="grid grid-cols-7">
            {calDays.map((date, idx) => {
              const isToday = date ? isSameDay(date, today) : false;
              const isSelected = date && selectedDay ? isSameDay(date, selectedDay) : false;
              const dayEvents = date ? eventsForDay(date) : [];
              return (
                <div
                  key={idx}
                  onClick={() => date && setSelectedDay(date)}
                  className={`min-h-[90px] p-2 border-r border-b border-[var(--paper-rule)] last:border-r-0 transition-colors ${
                    date ? "cursor-pointer hover:bg-[var(--paper-warm)]" : "bg-[var(--paper-warm)]/50"
                  } ${isSelected ? "bg-[rgba(var(--accent-red-rgb),.08)]" : ""}`}
                >
                  {date && (
                    <>
                      <span className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-medium mb-1 ${
                        isToday
                          ? "bg-[var(--accent-red)] text-white"
                          : "text-[var(--ink-mid)]"
                      }`}>
                        {date.getDate()}
                      </span>
                      <div className="space-y-0.5">
                        {dayEvents.slice(0, 3).map((ev) => (
                          <div
                            key={ev.id}
                            className={`${colorForEvent(ev)} text-white text-xs rounded-sm px-1 py-0.5 truncate`}
                            title={ev.title}
                          >
                            {ev.title}
                          </div>
                        ))}
                        {dayEvents.length > 3 && (
                          <p className="text-xs text-[var(--ink-faint)]">+{dayEvents.length - 3} mehr</p>
                        )}
                      </div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Selected day events panel */}
      {selectedDay && (
        <div className="bg-[var(--paper)] rounded-sm border border-[var(--paper-rule)] p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-[var(--ink)]">
              {selectedDay.toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}
            </h3>
            <button onClick={() => setSelectedDay(null)} className="p-1 rounded-sm hover:bg-[var(--paper-warm)] text-[var(--ink-faint)]">
              <X size={16} />
            </button>
          </div>
          {eventsForDay(selectedDay).length === 0 ? (
            <p className="text-sm text-[var(--ink-faint)]">Keine Termine an diesem Tag.</p>
          ) : (
            <div className="space-y-2">
              {eventsForDay(selectedDay).map((ev) => (
                <div key={ev.id} className="flex items-start gap-3">
                  <div className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${colorForEvent(ev)}`} />
                  <div>
                    <p className="text-sm font-medium text-[var(--ink)]">{ev.title}</p>
                    <p className="text-xs text-[var(--ink-faint)]">
                      {new Date(ev.start_at).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}
                      {" – "}
                      {new Date(ev.end_at).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}
                    </p>
                    {ev.description && <p className="text-xs text-[var(--ink-faint)] mt-0.5">{ev.description}</p>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Connected Calendars */}
      {connections && connections.length > 0 && (
        <div className="bg-[var(--paper)] rounded-sm border border-[var(--paper-rule)] p-4">
          <h3 className="text-sm font-semibold text-[var(--ink)] mb-3">Verbundene Kalender</h3>
          <div className="space-y-3">
            {connections.map((conn) => (
              <div key={conn.id} className="flex flex-col gap-1 pb-3 border-b border-[var(--paper-rule)] last:border-0 last:pb-0">
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full shrink-0 ${conn.is_active ? "bg-[var(--green)]" : "bg-[var(--paper-rule)]"}`} />
                  <span className="text-sm font-medium text-[var(--ink)]">
                    {conn.display_name ?? conn.email_address}
                  </span>
                  <span className="text-xs text-[var(--ink-faint)] capitalize">{conn.provider}</span>
                </div>
                {conn.display_name && (
                  <p className="text-xs text-[var(--ink-faint)] pl-4">{conn.email_address}</p>
                )}
                {/* Sync Interval */}
                <div className="flex items-center gap-2 mt-2 pl-4">
                  <label className="text-xs text-[var(--ink-faint)] whitespace-nowrap">Sync-Intervall:</label>
                  <select
                    defaultValue={conn.sync_interval_minutes ?? 30}
                    onChange={async (e) => {
                      const interval = Number(e.target.value);
                      await apiRequest(`/api/v1/calendar/connections/${conn.id}`, {
                        method: "PATCH",
                        body: JSON.stringify({ sync_interval_minutes: interval }),
                      });
                    }}
                    className="text-xs border border-[var(--paper-rule)] rounded-sm px-2 py-1 bg-[var(--paper)] text-[var(--ink-mid)]"
                  >
                    <option value={15}>15 Minuten</option>
                    <option value={30}>30 Minuten</option>
                    <option value={60}>60 Minuten</option>
                    <option value={120}>2 Stunden</option>
                  </select>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Create Event Modal */}
      {showCreateForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-[var(--paper)] rounded-sm border border-[var(--paper-rule)] w-full max-w-md">
            <div className="flex items-center justify-between p-4 border-b border-[var(--paper-rule)]">
              <h3 className="text-base font-semibold text-[var(--ink)]">Termin erstellen</h3>
              <button onClick={() => setShowCreateForm(false)} className="p-1 rounded-sm hover:bg-[var(--paper-warm)] text-[var(--ink-faint)]">
                <X size={18} />
              </button>
            </div>
            <form onSubmit={(e) => void handleCreateEvent(e)} className="p-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-[var(--ink-mid)] mb-1.5">
                  Titel <span className="text-[var(--accent-red)]">*</span>
                </label>
                <input
                  type="text"
                  value={formTitle}
                  onChange={(e) => setFormTitle(e.target.value)}
                  placeholder="Termin Titel"
                  className="w-full px-3 py-2 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[var(--accent-red)] bg-[var(--paper)]"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-[var(--ink-mid)] mb-1.5">
                  Datum <span className="text-[var(--accent-red)]">*</span>
                </label>
                <input
                  type="date"
                  value={formDate}
                  onChange={(e) => setFormDate(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[var(--accent-red)] bg-[var(--paper)]"
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-[var(--ink-mid)] mb-1.5">Startzeit</label>
                  <input
                    type="time"
                    value={formTime}
                    onChange={(e) => setFormTime(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[var(--accent-red)] bg-[var(--paper)]"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-[var(--ink-mid)] mb-1.5">Endzeit</label>
                  <input
                    type="time"
                    value={formEndTime}
                    onChange={(e) => setFormEndTime(e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[var(--accent-red)] bg-[var(--paper)]"
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-[var(--ink-mid)] mb-1.5">Beschreibung</label>
                <textarea
                  value={formDescription}
                  onChange={(e) => setFormDescription(e.target.value)}
                  placeholder="Optionale Beschreibung..."
                  rows={3}
                  className="w-full px-3 py-2 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[var(--accent-red)] bg-[var(--paper)] resize-none"
                />
              </div>
              <div className="flex gap-2 pt-2">
                <button
                  type="submit"
                  disabled={saving || !formTitle.trim() || !formDate}
                  className="flex-1 flex items-center justify-center gap-2 py-2 bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] disabled:bg-[rgba(var(--accent-red-rgb),.08)] text-white rounded-sm text-sm font-medium transition-colors"
                >
                  {saving ? (
                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                  ) : null}
                  Erstellen
                </button>
                <button
                  type="button"
                  onClick={() => setShowCreateForm(false)}
                  className="px-4 py-2 border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:bg-[var(--paper-warm)] rounded-sm text-sm font-medium transition-colors"
                >
                  Abbrechen
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Connect Calendar Modal */}
      {showConnectModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-[var(--paper)] rounded-sm border border-[var(--paper-rule)] w-full max-w-md">
            <div className="flex items-center justify-between p-4 border-b border-[var(--paper-rule)]">
              <h3 className="text-base font-semibold text-[var(--ink)]">Kalender verbinden</h3>
              <button onClick={() => setShowConnectModal(false)} className="p-1 rounded-sm hover:bg-[var(--paper-warm)] text-[var(--ink-faint)]">
                <X size={18} />
              </button>
            </div>
            <form onSubmit={(e) => void handleConnect(e)} className="p-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-[var(--ink-mid)] mb-1.5">Anbieter</label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setConnectProvider("google")}
                    className={`flex-1 py-2 rounded-sm border text-sm font-medium transition-colors ${
                      connectProvider === "google"
                        ? "border-[var(--accent-red)] bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)]"
                        : "border-[var(--paper-rule)] hover:bg-[var(--paper-warm)] text-[var(--ink-mid)]"
                    }`}
                  >
                    🗓 Google
                  </button>
                  <button
                    type="button"
                    onClick={() => setConnectProvider("outlook")}
                    className={`flex-1 py-2 rounded-sm border text-sm font-medium transition-colors ${
                      connectProvider === "outlook"
                        ? "border-[var(--accent-red)] bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)]"
                        : "border-[var(--paper-rule)] hover:bg-[var(--paper-warm)] text-[var(--ink-mid)]"
                    }`}
                  >
                    📅 Outlook
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-[var(--ink-mid)] mb-1.5">
                  E-Mail-Adresse <span className="text-[var(--accent-red)]">*</span>
                </label>
                <input
                  type="email"
                  value={connectEmail}
                  onChange={(e) => setConnectEmail(e.target.value)}
                  placeholder="name@example.com"
                  className="w-full px-3 py-2 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[var(--accent-red)] bg-[var(--paper)]"
                  required
                />
              </div>
              <div className="flex gap-2 pt-2">
                <button
                  type="submit"
                  disabled={connecting || !connectEmail.trim()}
                  className="flex-1 flex items-center justify-center gap-2 py-2 bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] disabled:bg-[rgba(var(--accent-red-rgb),.08)] text-white rounded-sm text-sm font-medium transition-colors"
                >
                  {connecting ? (
                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                  ) : null}
                  Verbinden
                </button>
                <button
                  type="button"
                  onClick={() => setShowConnectModal(false)}
                  className="px-4 py-2 border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:bg-[var(--paper-warm)] rounded-sm text-sm font-medium transition-colors"
                >
                  Abbrechen
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
