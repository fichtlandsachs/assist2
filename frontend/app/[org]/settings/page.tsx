"use client";

import { use, useState, useEffect, useCallback } from "react";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { MembersSection } from "@/components/settings/MembersSection";
import { useOrg } from "@/lib/hooks/useOrg";
import { useAuth } from "@/lib/auth/context";
import { useTheme, type ThemeId } from "@/lib/theme/context";
import { useT, type Locale } from "@/lib/i18n/context";
import { apiRequest, fetcher } from "@/lib/api/client";
import useSWR from "swr";
import type { User, UserStory, Process } from "@/types";
import {
  Building2, Mail, CalendarDays, AlertCircle,
  Layers, Cloud, CheckCircle, Trash2, Plus, Eye, EyeOff, RefreshCw, UserCircle2, Sparkles, CreditCard, Shield,
} from "lucide-react";
import { RagZonesSection } from "@/components/settings/RagZonesSection";

// ── Types ──────────────────────────────────────────────────────────────────

interface MailConnection { id: string; provider: string; email_address: string; display_name: string | null; is_active: boolean; last_sync_at: string | null; imap_host?: string | null; imap_port?: number | null; imap_use_ssl?: boolean | null; }
interface CalendarConnection { id: string; provider: string; email_address: string; display_name: string | null; is_active: boolean; last_sync_at: string | null; }
interface IntegrationSettings {
  jira: { base_url: string; user: string; api_token_set: boolean };
  confluence: { base_url: string; user: string; api_token_set: boolean; default_space_key?: string; default_parent_page_id?: string };
  ai: {
    dor_rules: string[];
    min_quality_score: number;
  };
}

// ── Helpers ────────────────────────────────────────────────────────────────

function SaveButton({ saving, label }: { saving: boolean; label: string }) {
  return (
    <button
      type="submit"
      disabled={saving}
      className="flex items-center gap-2 px-4 py-2 bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] disabled:bg-[var(--ink-faint)] text-white rounded-sm text-sm font-medium transition-colors"
    >
      {saving && <div className="animate-spin rounded-full h-3.5 w-3.5 border-2 border-white border-t-transparent" />}
      {saving ? "…" : label}
    </button>
  );
}

function StatusBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${ok ? "bg-[rgba(82,107,94,.1)] text-[var(--green)]" : "bg-[var(--paper-warm)] text-[var(--ink-faint)]"}`}>
      {ok ? <CheckCircle size={11} /> : <AlertCircle size={11} />}
      {label}
    </span>
  );
}

function TokenField({
  id, label, placeholder, value, onChange, isSet, hint,
}: {
  id: string; label: string; placeholder: string;
  value: string; onChange: (v: string) => void;
  isSet: boolean; hint?: string;
}) {
  const { t } = useT();
  const [show, setShow] = useState(false);
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label htmlFor={id} className="block text-sm font-medium text-[var(--ink-mid)]">{label}</label>
        {isSet && <StatusBadge ok label={t("settings_status_set")} />}
      </div>
      <div className="relative">
        <input
          id={id}
          type={show ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={isSet ? "••••••••••••••••••••" : placeholder}
          className="w-full px-3 py-2 pr-9 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[var(--accent-red)] bg-[var(--card)]"
        />
        <button type="button" onClick={() => setShow((v) => !v)}
          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--ink-faint)] hover:text-[var(--ink-mid)]">
          {show ? <EyeOff size={15} /> : <Eye size={15} />}
        </button>
      </div>
      {hint && <p className="text-xs text-[var(--ink-faint)] mt-1">{hint}</p>}
    </div>
  );
}

function FormField({ id, label, value, onChange, placeholder, type = "text" }: {
  id: string; label: string; value: string; onChange: (v: string) => void;
  placeholder?: string; type?: string;
}) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-[var(--ink-mid)] mb-1">{label}</label>
      <input id={id} type={type} value={value} onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[var(--accent-red)] bg-[var(--card)]" />
    </div>
  );
}

function SectionMessage({ msg }: { msg: { type: "success" | "error"; text: string } | null }) {
  if (!msg) return null;
  return (
    <div className={`px-4 py-3 rounded-sm text-sm ${msg.type === "success" ? "bg-[rgba(82,107,94,.1)] border border-[var(--green)] text-[var(--green)]" : "bg-[rgba(var(--accent-red-rgb),.08)] border border-[var(--accent-red)] text-[var(--accent-red)]"}`}>
      {msg.text}
    </div>
  );
}

// ── Tab definitions ────────────────────────────────────────────────────────

const TAB_IDS = ["profile", "general", "email", "calendar", "jira", "confluence", "processes", "ai", "billing", "zones"] as const;
type TabId = typeof TAB_IDS[number];

// ── Section: Profile ───────────────────────────────────────────────────────

function ProfileSection({ user, refreshUser }: { user: User; refreshUser: () => Promise<void> }) {
  const { t, setLocale, locale } = useT();
  const { linkAtlassian } = useAuth();
  const [displayName, setDisplayName] = useState(user.display_name ?? "");
  const [timezone, setTimezone] = useState(user.timezone ?? "");
  const [selectedLocale, setSelectedLocale] = useState<Locale>((user.locale as Locale) ?? locale);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [atlassianLinking, setAtlassianLinking] = useState(false);

  const isAtlassianConnected = !!user.atlassian_account_id;
  const isGitHubConnected = !!user.github_id;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true); setMsg(null);
    try {
      await apiRequest("/api/v1/users/me", {
        method: "PATCH",
        body: JSON.stringify({ display_name: displayName, locale: selectedLocale, timezone: timezone || null }),
      });
      setLocale(selectedLocale);
      await refreshUser();
      setMsg({ type: "success", text: t("settings_profile_saved") });
      setTimeout(() => setMsg(null), 3000);
    } catch { setMsg({ type: "error", text: t("settings_profile_error") }); }
    finally { setSaving(false); }
  };

  const handleLinkAtlassian = () => {
    setAtlassianLinking(true);
    linkAtlassian();
  };

  return (
    <div className="space-y-6 max-w-lg">
      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
        <SectionMessage msg={msg} />
        <FormField id="profile-name" label={t("settings_profile_name")} value={displayName} onChange={setDisplayName} />
        <div>
          <label className="block text-sm font-medium text-[var(--ink-mid)] mb-1">{t("settings_profile_email")}</label>
          <input
            value={user.email ?? "—"}
            disabled
            className="w-full px-3 py-2 text-sm border border-[var(--paper-rule)] rounded-sm bg-[var(--paper-warm)] text-[var(--ink-faint)] cursor-not-allowed"
          />
        </div>
        <div>
          <label htmlFor="profile-locale" className="block text-sm font-medium text-[var(--ink-mid)] mb-1">{t("settings_profile_language")}</label>
          <select
            id="profile-locale"
            value={selectedLocale}
            onChange={(e) => setSelectedLocale(e.target.value as Locale)}
            className="w-full px-3 py-2 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[var(--accent-red)] bg-[var(--card)]"
          >
            <option value="de">{t("settings_profile_language_de")}</option>
            <option value="en">{t("settings_profile_language_en")}</option>
          </select>
        </div>
        <FormField id="profile-timezone" label={t("settings_profile_timezone")} value={timezone} onChange={setTimezone} placeholder="Europe/Berlin" />
        <SaveButton saving={saving} label={t("settings_profile_save")} />
      </form>

      {/* Atlassian connection */}
      <div className="pt-4 border-t border-[var(--paper-rule)]">
        <div className="rounded-sm p-4 space-y-3" style={{ border: "0.5px solid var(--paper-rule)", background: "var(--paper-warm)" }}>
          <div className="flex items-center justify-between">
            <div>
              <p style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase", color: "var(--ink-mid)" }}>{t("settings_profile_atlassian")}</p>
              <p style={{ fontFamily: "var(--font-body)", fontSize: "13px", color: "var(--ink-faint)", marginTop: "2px" }}>
                {isAtlassianConnected
                  ? `${t("settings_profile_atlassian_connected")} — ${user.atlassian_email ?? user.email}`
                  : "—"}
              </p>
            </div>
            {!isAtlassianConnected && (
              <button
                type="button"
                onClick={handleLinkAtlassian}
                disabled={atlassianLinking}
                className="px-3 py-1.5 rounded-sm transition-colors disabled:opacity-50"
                style={{ fontFamily: "var(--font-mono)", fontSize: "8px", letterSpacing: ".06em", textTransform: "uppercase", border: "0.5px solid var(--paper-rule)", color: "var(--ink)" }}
              >
                {atlassianLinking ? t("settings_profile_atlassian_linking") : t("settings_profile_atlassian_connect")}
              </button>
            )}
            {isAtlassianConnected && (
              <StatusBadge ok label={t("settings_profile_atlassian_connected")} />
            )}
          </div>
        </div>
      </div>

      {/* GitHub connection */}
      <div className="rounded-sm p-4 space-y-3" style={{ border: "0.5px solid var(--paper-rule)", background: "var(--paper-warm)" }}>
        <div className="flex items-center justify-between">
          <div>
            <p style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase", color: "var(--ink-mid)" }}>{t("settings_profile_github")}</p>
            <p style={{ fontFamily: "var(--font-body)", fontSize: "13px", color: "var(--ink-faint)", marginTop: "2px" }}>
              {isGitHubConnected
                ? `${t("settings_profile_github_connected")} — ${user.github_username ?? user.github_email ?? user.email}`
                : "—"}
            </p>
          </div>
          {isGitHubConnected && (
            <StatusBadge ok label={t("settings_profile_github_connected")} />
          )}
        </div>
      </div>
    </div>
  );
}

// ── Section: General ───────────────────────────────────────────────────────

function GeneralSection({ org, mutateOrg }: { org: any; mutateOrg: () => void }) {
  const { t } = useT();
  const [name, setName] = useState(org.name);
  const [description, setDescription] = useState(org.description ?? "");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true); setMsg(null);
    try {
      await apiRequest(`/api/v1/organizations/${org.id}`, { method: "PATCH", body: JSON.stringify({ name, description }) });
      await mutateOrg();
      setMsg({ type: "success", text: t("settings_general_saved") });
    } catch { setMsg({ type: "error", text: t("settings_general_error") }); }
    finally { setSaving(false); }
  };

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4 max-w-lg">
      <SectionMessage msg={msg} />
      <FormField id="name" label={t("settings_general_name")} value={name} onChange={setName} />
      <div>
        <label className="block text-sm font-medium text-[var(--ink-mid)] mb-1">{t("settings_general_slug")}</label>
        <input value={org.slug} disabled className="w-full px-3 py-2 text-sm border border-[var(--paper-rule)] rounded-sm bg-[var(--paper-warm)] text-[var(--ink-faint)] cursor-not-allowed" />
      </div>
      <div>
        <label className="block text-sm font-medium text-[var(--ink-mid)] mb-1">{t("settings_general_desc")}</label>
        <textarea rows={3} value={description} onChange={(e) => setDescription(e.target.value)}
          className="w-full px-3 py-2 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[var(--accent-red)] resize-none" />
      </div>
      <div>
        <label className="block text-sm font-medium text-[var(--ink-mid)] mb-1">{t("settings_general_plan")}</label>
        <input value={org.plan} disabled className="w-full px-3 py-2 text-sm border border-[var(--paper-rule)] rounded-sm bg-[var(--paper-warm)] text-[var(--ink-faint)] cursor-not-allowed" />
      </div>
      <SaveButton saving={saving} label={t("settings_general_save")} />
    </form>
  );
}

// ── Organisation Tab (Allgemein + Benutzer sub-tabs) ──────────────────────

function OrgTabWithSubTabs({ org, mutateOrg }: { org: any; mutateOrg: () => void }) {
  const [subTab, setSubTab] = useState<"allgemein" | "benutzer">("allgemein");
  return (
    <>
      <div className="flex gap-1 mb-6 border-b border-[var(--paper-rule)]">
        {(["allgemein", "benutzer"] as const).map(id => (
          <button key={id} onClick={() => setSubTab(id)}
            className={`px-3 py-1.5 text-xs font-medium capitalize transition-colors border-b-2 -mb-px ${subTab === id ? "border-[var(--accent-red)] text-[var(--ink)]" : "border-transparent text-[var(--ink-faint)] hover:text-[var(--ink)]"}`}>
            {id === "allgemein" ? "Allgemein" : "Benutzer"}
          </button>
        ))}
      </div>
      {subTab === "allgemein" && (
        <>
          <h2 className="text-base font-semibold text-[var(--ink)] mb-5">Organisation</h2>
          <GeneralSection org={org} mutateOrg={mutateOrg} />
        </>
      )}
      {subTab === "benutzer" && <MembersSection orgId={org.id} />}
    </>
  );
}

// ── Section: Email ─────────────────────────────────────────────────────────

function EmailSection({ orgId }: { orgId: string }) {
  const { t } = useT();
  const { data: connections, mutate } = useSWR<MailConnection[]>(
    `/api/v1/inbox/connections?org_id=${orgId}`, fetcher
  );
  const [provider, setProvider] = useState("imap");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [imapHost, setImapHost] = useState("");
  const [imapPort, setImapPort] = useState("993");
  const [imapPassword, setImapPassword] = useState("");
  const [imapEncryption, setImapEncryption] = useState("ssl");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  function handleEncryptionChange(enc: string) {
    setImapEncryption(enc);
    if (enc === "ssl") setImapPort("993");
    else if (enc === "starttls") setImapPort("587");
    else setImapPort("143");
  }

  function resetForm() {
    setEmail(""); setDisplayName("");
    setImapHost(""); setImapPort("993"); setImapPassword(""); setImapEncryption("ssl");
    setProvider("imap");
  }

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setMsg(null);
    try {
      const body: Record<string, unknown> = {
        provider,
        email_address: email,
        display_name: displayName || null,
      };
      if (provider === "imap") {
        if (!imapHost.trim()) { setMsg({ type: "error", text: t("settings_email_error_server") }); setSaving(false); return; }
        if (!imapPassword) { setMsg({ type: "error", text: t("settings_email_error_password") }); setSaving(false); return; }
        body.imap_host = imapHost.trim();
        body.imap_port = parseInt(imapPort) || 993;
        body.imap_password = imapPassword;
        body.imap_use_ssl = imapEncryption === "ssl";
      }
      await apiRequest(`/api/v1/inbox/connections?org_id=${orgId}`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      await mutate();
      resetForm();
      setMsg({ type: "success", text: t("settings_email_success") });
    } catch { setMsg({ type: "error", text: t("settings_email_error") }); }
    finally { setSaving(false); }
  }

  async function handleDelete(id: string) {
    setDeleting(id);
    try { await apiRequest(`/api/v1/inbox/connections/${id}`, { method: "DELETE" }); await mutate(); }
    catch { /* ignore */ }
    finally { setDeleting(null); }
  }

  const selectCls = "w-full px-3 py-2 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[var(--accent-red)] bg-[var(--card)]";

  return (
    <div className="space-y-5 max-w-xl">
      {/* Existing connections */}
      {connections && connections.length > 0 && (
        <div className="space-y-2">
          {connections.map((c) => (
            <div key={c.id} className="flex items-center justify-between p-3 border border-[var(--paper-rule)] rounded-sm bg-[var(--card)]">
              <div className="flex items-center gap-3">
                <Mail size={16} className="text-[var(--ink-faint)] shrink-0" />
                <div>
                  <p className="text-sm font-medium text-[var(--ink)]">{c.display_name ?? c.email_address}</p>
                  <p className="text-xs text-[var(--ink-faint)]">{c.email_address} · {c.provider.toUpperCase()}{c.provider === "imap" && c.imap_host ? ` · ${c.imap_host}:${c.imap_port ?? 993}` : ""}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge ok={c.is_active} label={c.is_active ? t("settings_email_status_active") : t("settings_email_status_inactive")} />
                <button type="button" onClick={() => void handleDelete(c.id)} disabled={deleting === c.id}
                  className="p-1.5 text-[var(--ink-faint)] hover:text-[var(--accent-red)] hover:bg-[rgba(var(--accent-red-rgb),.08)] rounded transition-colors">
                  {deleting === c.id ? <div className="animate-spin rounded-full h-3.5 w-3.5 border-2 border-[var(--accent-red)] border-t-transparent" /> : <Trash2 size={14} />}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add connection form — always visible */}
      <form onSubmit={(e) => void handleAdd(e)} className="border border-[var(--paper-rule)] rounded-sm bg-[var(--paper-warm)]">
        <div className="px-4 py-3 border-b border-[var(--paper-rule)]">
          <p className="text-sm font-semibold text-[var(--ink)]">{t("settings_email_title")}</p>
        </div>

        <div className="p-4 space-y-3">
          <SectionMessage msg={msg} />

          {/* Provider */}
          <div>
            <label htmlFor="email-provider" className="block text-sm font-medium text-[var(--ink-mid)] mb-1">{t("settings_email_protocol")}</label>
            <select
              id="email-provider"
              value={provider}
              onChange={(e) => {
                setProvider(e.target.value);
                if (e.target.value === "imap") handleEncryptionChange("ssl");
              }}
              className={selectCls}
            >
              <option value="imap">IMAP</option>
              <option value="gmail">Gmail</option>
              <option value="outlook">Outlook</option>
            </select>
          </div>

          <FormField id="new-email-addr" label={t("settings_email_address")} value={email} onChange={setEmail} placeholder={t("settings_email_address_placeholder")} type="email" />
          <FormField id="new-email-name" label={t("settings_email_display")} value={displayName} onChange={setDisplayName} placeholder={t("settings_email_display_placeholder")} />

          {/* IMAP-specific fields */}
          {provider === "imap" && (
            <div className="space-y-3 pt-3 mt-1 border-t border-[var(--paper-rule)]">
              <p className="text-xs font-semibold text-[var(--ink-faint)] uppercase tracking-wide">{t("settings_email_server_section")}</p>

              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-2">
                  <label htmlFor="imap-host" className="block text-sm font-medium text-[var(--ink-mid)] mb-1">{t("settings_email_host")}</label>
                  <input
                    id="imap-host"
                    type="text"
                    value={imapHost}
                    onChange={(e) => setImapHost(e.target.value)}
                    placeholder={t("settings_email_host_placeholder")}
                    className={selectCls}
                  />
                </div>
                <div>
                  <label htmlFor="imap-port" className="block text-sm font-medium text-[var(--ink-mid)] mb-1">{t("settings_email_port")}</label>
                  <input
                    id="imap-port"
                    type="number"
                    value={imapPort}
                    onChange={(e) => setImapPort(e.target.value)}
                    placeholder="993"
                    className={selectCls}
                  />
                </div>
              </div>

              <div>
                <label htmlFor="imap-enc" className="block text-sm font-medium text-[var(--ink-mid)] mb-1">{t("settings_email_encryption")}</label>
                <select
                  id="imap-enc"
                  value={imapEncryption}
                  onChange={(e) => handleEncryptionChange(e.target.value)}
                  className={selectCls}
                >
                  <option value="ssl">{t("settings_email_ssl")}</option>
                  <option value="starttls">{t("settings_email_starttls")}</option>
                  <option value="none">{t("settings_email_none")}</option>
                </select>
              </div>

              <div>
                <label htmlFor="imap-pass" className="block text-sm font-medium text-[var(--ink-mid)] mb-1">{t("settings_email_password")}</label>
                <TokenField id="imap-pass" label="" placeholder="••••••••" value={imapPassword} onChange={setImapPassword} isSet={false} />
              </div>
            </div>
          )}

          <div className="pt-1">
            <button
              type="submit"
              disabled={saving}
              className="flex items-center gap-2 px-4 py-2 bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] disabled:bg-[var(--ink-faint)] text-white rounded-sm text-sm font-medium transition-colors"
            >
              {saving && <div className="animate-spin rounded-full h-3.5 w-3.5 border-2 border-white border-t-transparent" />}
              {saving ? t("settings_email_connecting") : t("settings_email_connect")}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}

// ── Section: Calendar ──────────────────────────────────────────────────────

function CalendarSection({ orgId }: { orgId: string }) {
  const { t } = useT();
  const { data: connections, mutate } = useSWR<CalendarConnection[]>(
    `/api/v1/calendar/connections?org_id=${orgId}`, fetcher
  );
  const [showForm, setShowForm] = useState(false);
  const [provider, setProvider] = useState("google");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true); setMsg(null);
    try {
      await apiRequest(`/api/v1/calendar/connections?org_id=${orgId}`, {
        method: "POST",
        body: JSON.stringify({ provider, email_address: email, display_name: displayName || null }),
      });
      await mutate();
      setEmail(""); setDisplayName(""); setShowForm(false);
      setMsg({ type: "success", text: t("settings_calendar_connected") });
    } catch { setMsg({ type: "error", text: t("settings_calendar_error") }); }
    finally { setSaving(false); }
  }

  async function handleDelete(id: string) {
    setDeleting(id);
    try { await apiRequest(`/api/v1/calendar/connections/${id}`, { method: "DELETE" }); await mutate(); }
    catch { /* ignore */ }
    finally { setDeleting(null); }
  }

  return (
    <div className="space-y-4 max-w-xl">
      <div className="flex items-center justify-between">
        <p className="text-sm text-[var(--ink-mid)]">{t("settings_calendar_title")}</p>
        <button onClick={() => setShowForm((v) => !v)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--accent-red)] hover:bg-[var(--btn-primary-hover)] text-white rounded-sm text-xs font-medium transition-colors">
          <Plus size={13} /> {t("settings_calendar_add")}
        </button>
      </div>

      <SectionMessage msg={msg} />

      {showForm && (
        <form onSubmit={(e) => void handleAdd(e)} className="border border-[var(--paper-rule)] rounded-sm p-4 space-y-3 bg-[var(--paper-warm)]">
          <div>
            <label className="block text-xs font-medium text-[var(--ink-mid)] mb-1">{t("settings_calendar_provider")}</label>
            <select value={provider} onChange={(e) => setProvider(e.target.value)}
              className="w-full px-3 py-1.5 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] bg-[var(--card)]">
              <option value="google">{t("settings_calendar_google")}</option>
              <option value="outlook">{t("settings_calendar_outlook")}</option>
            </select>
          </div>
          <FormField id="cal-email" label={t("settings_calendar_email")} value={email} onChange={setEmail} placeholder={t("settings_calendar_email_placeholder")} type="email" />
          <FormField id="cal-name" label={t("settings_calendar_display")} value={displayName} onChange={setDisplayName} placeholder={t("settings_calendar_display_placeholder")} />
          <div className="flex gap-2">
            <SaveButton saving={saving} label={t("settings_calendar_submit")} />
            <button type="button" onClick={() => setShowForm(false)}
              className="px-3 py-2 border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:bg-[var(--paper-warm)] rounded-sm text-sm font-medium transition-colors">
              {t("settings_calendar_cancel")}
            </button>
          </div>
        </form>
      )}

      {!connections ? (
        <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-[var(--accent-red)]" />
      ) : connections.length === 0 ? (
        <p className="text-sm text-[var(--ink-faint)] text-center py-6">{t("settings_calendar_empty")}</p>
      ) : (
        <div className="space-y-2">
          {connections.map((c) => (
            <div key={c.id} className="flex items-center justify-between p-3 border border-[var(--paper-rule)] rounded-sm bg-[var(--card)]">
              <div className="flex items-center gap-3">
                <CalendarDays size={16} className="text-[var(--ink-faint)] shrink-0" />
                <div>
                  <p className="text-sm font-medium text-[var(--ink)]">{c.display_name ?? c.email_address}</p>
                  <p className="text-xs text-[var(--ink-faint)]">{c.email_address} · {c.provider === "google" ? "Google" : "Outlook"}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge ok={c.is_active} label={c.is_active ? t("settings_calendar_active") : t("settings_calendar_inactive")} />
                <button onClick={() => void handleDelete(c.id)} disabled={deleting === c.id}
                  className="p-1.5 text-[var(--ink-faint)] hover:text-[var(--accent-red)] hover:bg-[rgba(var(--accent-red-rgb),.08)] rounded transition-colors">
                  {deleting === c.id ? <div className="animate-spin rounded-full h-3.5 w-3.5 border-2 border-[var(--accent-red)] border-t-transparent" /> : <Trash2 size={14} />}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Section: Jira ──────────────────────────────────────────────────────────

function JiraSection({ orgId, settings }: { orgId: string; settings: IntegrationSettings["jira"]; onSaved: () => void }) {
  const { t } = useT();
  const [baseUrl, setBaseUrl] = useState(settings.base_url);
  const [user, setUser] = useState(settings.user);
  const [token, setToken] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault(); setSaving(true); setMsg(null);
    try {
      await apiRequest(`/api/v1/organizations/${orgId}/integrations/jira`, {
        method: "PATCH",
        body: JSON.stringify({ base_url: baseUrl, user, api_token: token || null }),
      });
      setToken("");
      setMsg({ type: "success", text: t("settings_jira_saved") });
    } catch { setMsg({ type: "error", text: t("settings_general_error") }); }
    finally { setSaving(false); }
  };

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4 max-w-lg">
      <p className="text-sm text-[var(--ink-mid)]">
        {t("settings_jira_desc")}
      </p>
      <SectionMessage msg={msg} />
      <FormField id="jira-url" label={t("settings_jira_url")} value={baseUrl} onChange={setBaseUrl}
        placeholder={t("settings_jira_url_placeholder")} />
      <FormField id="jira-user" label={t("settings_jira_user")} value={user} onChange={setUser}
        placeholder={t("settings_jira_user_placeholder")} />
      <TokenField id="jira-token" label={t("settings_jira_token")} placeholder="Atlassian API-Token"
        value={token} onChange={setToken} isSet={settings.api_token_set}
        hint={t("settings_jira_token_hint")} />
      <SaveButton saving={saving} label={t("settings_general_save")} />
    </form>
  );
}

// ── Section: Process Management ────────────────────────────────────────────

function ProcessManageSection({ orgId }: { orgId: string }) {
  const { t } = useT();
  const { data: processes, mutate } = useSWR<Process[]>(
    `/api/v1/processes?org_id=${orgId}`,
    fetcher,
  );
  const [name, setName] = useState("");
  const [pageId, setPageId] = useState("");
  const [saving, setSaving] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const inputClass = "w-full px-3 py-2 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[var(--accent-red)] bg-[var(--card)]";

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    try {
      await apiRequest(`/api/v1/processes?org_id=${orgId}`, {
        method: "POST",
        body: JSON.stringify({ name: name.trim(), confluence_page_id: pageId.trim() || null }),
      });
      setName(""); setPageId("");
      await mutate();
    } catch { /* ignore */ }
    finally { setSaving(false); }
  };

  const handleDelete = async (id: string) => {
    try {
      await apiRequest(`/api/v1/processes/${id}`, { method: "DELETE" });
      await mutate();
    } catch { /* ignore */ }
    finally { setConfirmDeleteId(null); }
  };

  return (
    <div className="space-y-6 max-w-lg">
      <p className="text-sm text-[var(--ink-mid)]">{t("process_manage_desc")}</p>

      {/* Create form */}
      <form onSubmit={(e) => void handleCreate(e)} className="space-y-3 p-4 bg-[var(--paper-warm)] rounded-sm border border-[var(--paper-rule)]">
        <div>
          <label className="text-xs font-medium text-[var(--ink-mid)] block mb-1">{t("process_new_name")}</label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="z. B. Onboarding-Prozess" className={inputClass} />
        </div>
        <div>
          <label className="text-xs font-medium text-[var(--ink-mid)] block mb-1">{t("process_new_page_id")}</label>
          <input value={pageId} onChange={(e) => setPageId(e.target.value)} placeholder="z. B. 152731649" className={inputClass} />
        </div>
        <button type="submit" disabled={!name.trim() || saving}
          className="flex items-center gap-2 px-4 py-2 bg-[var(--accent-red)] text-white rounded-sm text-sm font-medium disabled:opacity-50">
          <Plus size={14} />
          {saving ? "…" : t("process_create")}
        </button>
      </form>

      {/* Process list */}
      <div className="space-y-2">
        {(processes ?? []).map((p) => (
          <div key={p.id} className="flex items-center justify-between gap-3 px-4 py-3 bg-[var(--card)] border border-[var(--paper-rule)] rounded-sm">
            <div className="min-w-0">
              <p className="text-sm font-medium text-[var(--ink)] truncate">{p.name}</p>
              {p.confluence_page_id && (
                <p className="text-xs text-[var(--ink-faint)]">Page ID: {p.confluence_page_id}</p>
              )}
            </div>
            {confirmDeleteId === p.id ? (
              <div className="flex gap-1 shrink-0">
                <button onClick={() => void handleDelete(p.id)}
                  className="px-2 py-1 text-xs bg-[var(--accent-red)] text-white rounded-sm">
                  {t("common_yes_delete")}
                </button>
                <button onClick={() => setConfirmDeleteId(null)}
                  className="px-2 py-1 text-xs border border-[var(--ink-faintest)] text-[var(--ink-mid)] rounded-sm">
                  {t("common_cancel")}
                </button>
              </div>
            ) : (
              <button onClick={() => setConfirmDeleteId(p.id)}
                className="text-[var(--ink-faint)] hover:text-[var(--accent-red)] shrink-0">
                <Trash2 size={14} />
              </button>
            )}
          </div>
        ))}
        {(processes ?? []).length === 0 && (
          <p className="text-sm text-[var(--ink-faint)] text-center py-4">Noch keine Prozesse angelegt.</p>
        )}
      </div>
    </div>
  );
}

// ── Section: Confluence ────────────────────────────────────────────────────

function ConfluenceSection({ orgId, settings }: { orgId: string; settings: IntegrationSettings["confluence"]; onSaved: () => void }) {
  const { t } = useT();
  const [baseUrl, setBaseUrl] = useState(settings.base_url);
  const [user, setUser] = useState(settings.user);
  const [token, setToken] = useState("");
  const [defaultSpaceKey, setDefaultSpaceKey] = useState(settings.default_space_key ?? "");
  const [defaultParentPageId, setDefaultParentPageId] = useState(settings.default_parent_page_id ?? "");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [confluenceIndexing, setConfluenceIndexing] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault(); setSaving(true); setMsg(null); setTestResult(null);
    try {
      await apiRequest(`/api/v1/organizations/${orgId}/integrations/confluence`, {
        method: "PATCH",
        body: JSON.stringify({ base_url: baseUrl, user, api_token: token || null, default_space_key: defaultSpaceKey || null, default_parent_page_id: defaultParentPageId || null }),
      });
      setToken("");
      setMsg({ type: "success", text: t("settings_confluence_saved") });
    } catch { setMsg({ type: "error", text: t("settings_general_error") }); }
    finally { setSaving(false); }
  };

  const handleTest = async () => {
    setTestLoading(true); setTestResult(null);
    try {
      const res = await apiRequest<{ configured: boolean; spaces: { key: string; name: string }[]; error?: string }>(
        `/api/v1/confluence/spaces?org_id=${orgId}`, { method: "GET" }
      );
      if (res.configured && res.spaces.length > 0) {
        setTestResult(t("settings_confluence_test_ok", {
          count: String(res.spaces.length),
          spaces: res.spaces.slice(0, 3).map((s) => s.name).join(", ") + (res.spaces.length > 3 ? "…" : ""),
        }));
      } else if (res.configured) {
        setTestResult(t("settings_confluence_test_ok_empty"));
      } else {
        setTestResult(t("settings_confluence_test_fail"));
      }
    } catch { setTestResult(t("settings_confluence_test_error")); }
    finally { setTestLoading(false); }
  };

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4 max-w-lg">
      <p className="text-sm text-[var(--ink-mid)]">
        {t("settings_confluence_desc")}
      </p>
      <SectionMessage msg={msg} />
      <FormField id="conf-url" label={t("settings_confluence_url")} value={baseUrl} onChange={setBaseUrl}
        placeholder={t("settings_confluence_url_placeholder")} />
      <FormField id="conf-user" label={t("settings_confluence_user")} value={user} onChange={setUser}
        placeholder={t("settings_confluence_user_placeholder")} />
      <TokenField id="conf-token" label={t("settings_confluence_token")} placeholder="Atlassian API-Token"
        value={token} onChange={setToken} isSet={settings.api_token_set}
        hint={t("settings_confluence_token_hint")} />
      <FormField id="conf-default-space" label={t("settings_confluence_default_space")} value={defaultSpaceKey} onChange={setDefaultSpaceKey}
        placeholder={t("settings_confluence_default_space_placeholder")} />
      <FormField id="conf-default-parent" label={t("settings_confluence_default_parent_page")} value={defaultParentPageId} onChange={setDefaultParentPageId}
        placeholder={t("settings_confluence_default_parent_page_placeholder")} />
      {testResult && (
        <p className={`text-xs px-3 py-2 rounded-sm ${testResult.startsWith("✓") || testResult.includes("erfolgreich") || testResult.includes("successful") || testResult.includes("Connection") ? "bg-[rgba(82,107,94,.1)] text-[var(--green)]" : "bg-[rgba(var(--accent-red-rgb),.08)] text-[var(--accent-red)]"}`}>
          {testResult}
        </p>
      )}
      <div className="flex gap-2">
        <SaveButton saving={saving} label={t("settings_general_save")} />
        <button type="button" onClick={() => void handleTest()} disabled={testLoading}
          className="flex items-center gap-2 px-4 py-2 border border-[var(--ink-faintest)] text-[var(--ink-mid)] hover:bg-[var(--paper-warm)] disabled:opacity-50 rounded-sm text-sm font-medium transition-colors">
          {testLoading ? <div className="animate-spin rounded-full h-3.5 w-3.5 border-2 border-[var(--ink-faint)] border-t-transparent" /> : <RefreshCw size={14} />}
          {t("settings_confluence_test")}
        </button>
      </div>
      <div className="mt-4 pt-4 border-t border-[var(--paper-rule)]">
        <button
          type="button"
          disabled={confluenceIndexing}
          onClick={async () => {
            setConfluenceIndexing(true);
            try {
              await apiRequest(`/api/v1/confluence/index`, {
                method: "POST",
                body: JSON.stringify({ org_id: orgId }),
              });
            } catch {
              // Ignore
            } finally {
              setConfluenceIndexing(false);
            }
          }}
          className="inline-flex items-center gap-2 px-4 py-2 bg-[var(--accent-red)] text-white rounded-sm text-sm font-medium disabled:opacity-50 transition-colors"
        >
          {confluenceIndexing ? t("settings_confluence_indexing") : t("settings_confluence_index")}
        </button>
        <p className="text-xs text-[var(--ink-faint)] mt-1">
          {t("settings_confluence_index_desc")}
        </p>
      </div>
    </form>
  );
}

// ── Section: AI ────────────────────────────────────────────────────────────

const DEFAULT_DOR_RULES = [
  "Hat die Story einen klaren Titel?",
  'Ist die Beschreibung im Format "Als [Rolle] möchte ich [Funktion], damit [Nutzen]"?',
  "Sind die Akzeptanzkriterien konkret, testbar und vollständig?",
  "Ist die Story klein genug für einen Sprint?",
  "Sind Abhängigkeiten bekannt?",
];

function AISection({ orgId, settings }: { orgId: string; settings: IntegrationSettings["ai"] }) {
  const { t } = useT();
  const [dorRules, setDorRules] = useState<string[]>(settings.dor_rules?.length ? settings.dor_rules : DEFAULT_DOR_RULES);
  const [newRule, setNewRule] = useState("");
  const [minQualityScore, setMinQualityScore] = useState(settings.min_quality_score ?? 50);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  function addRule() {
    const r = newRule.trim();
    if (r && !dorRules.includes(r)) {
      setDorRules([...dorRules, r]);
      setNewRule("");
    }
  }

  function removeRule(i: number) {
    setDorRules(dorRules.filter((_, idx) => idx !== i));
  }

  function updateRule(i: number, val: string) {
    setDorRules(dorRules.map((r, idx) => (idx === i ? val : r)));
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault(); setSaving(true); setMsg(null);
    try {
      await apiRequest(`/api/v1/organizations/${orgId}/integrations/ai`, {
        method: "PATCH",
        body: JSON.stringify({
          dor_rules: dorRules.filter(Boolean),
          min_quality_score: minQualityScore,
        }),
      });
      setMsg({ type: "success", text: t("settings_ai_saved") });
    } catch { setMsg({ type: "error", text: t("settings_ai_error") }); }
    finally { setSaving(false); }
  };

  const inputCls = "w-full px-3 py-2 text-sm border border-[var(--ink-faintest)] rounded-sm outline-none focus:border-[var(--accent-red)] focus:ring-2 focus:ring-[var(--accent-red)] bg-[var(--card)]";

  return (
    <form onSubmit={(e) => void handleSubmit(e)} className="space-y-6 max-w-lg">
      <p className="text-sm text-[var(--ink-mid)]">
        {t("settings_ai_dor_title")}
      </p>
      <SectionMessage msg={msg} />

      {/* DoR Rules */}
      <div>
        <label className="block text-sm font-medium text-[var(--ink-mid)] mb-1">
          {t("settings_ai_dor_title")}
          <span className="font-normal text-[var(--ink-faint)] text-xs ml-2">
            {t("settings_ai_add_rule")}
          </span>
        </label>
        <div className="space-y-1.5 mb-2">
          {dorRules.map((rule, i) => (
            <div key={i} className="flex items-center gap-2">
              <input
                type="text"
                value={rule}
                onChange={(e) => updateRule(i, e.target.value)}
                className={`${inputCls} flex-1`}
              />
              <button
                type="button"
                onClick={() => removeRule(i)}
                className="shrink-0 w-7 h-7 flex items-center justify-center rounded text-[var(--ink-faint)] hover:text-[var(--accent-red)] hover:bg-[rgba(var(--accent-red-rgb),.08)] transition-colors text-lg leading-none"
              >
                ×
              </button>
            </div>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            value={newRule}
            onChange={(e) => setNewRule(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addRule(); } }}
            placeholder={t("settings_ai_rule_placeholder")}
            className={`${inputCls} flex-1`}
          />
          <button
            type="button"
            onClick={addRule}
            className="px-3 py-2 text-sm border border-[var(--ink-faintest)] rounded-sm text-[var(--ink-mid)] hover:border-[var(--accent-red)] hover:text-[var(--accent-red)] transition-colors"
          >
            + {t("settings_ai_add_rule")}
          </button>
        </div>
        <button
          type="button"
          onClick={() => setDorRules([...DEFAULT_DOR_RULES])}
          className="mt-1.5 text-xs text-[var(--ink-faint)] hover:text-[var(--ink-mid)] transition-colors"
        >
          {t("common_back")}
        </button>
      </div>

      {/* Min quality score */}
      <div>
        <label htmlFor="min-quality-score" className="block text-sm font-medium text-[var(--ink-mid)] mb-1">
          {t("settings_ai_min_score")}
        </label>
        <div className="flex items-center gap-3">
          <input
            id="min-quality-score"
            type="range"
            min={0}
            max={100}
            step={5}
            value={minQualityScore}
            onChange={(e) => setMinQualityScore(Number(e.target.value))}
            className="flex-1 accent-[var(--accent-red)]"
          />
          <span className="w-10 text-center text-sm font-semibold text-[var(--ink)]">{minQualityScore}</span>
        </div>
      </div>

      <SaveButton saving={saving} label={t("settings_general_save")} />
    </form>
  );
}

// ── Section: Atlassian Connection ─────────────────────────────────────────

function AtlassianConnectionSection({ user }: { user: User }) {
  const { t } = useT();
  const { linkAtlassian } = useAuth();
  const [disconnecting, setDisconnecting] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const isConnected = !!user.atlassian_account_id;

  const disconnect = async () => {
    setDisconnecting(true);
    setMsg(null);
    try {
      await apiRequest("/api/v1/auth/atlassian/disconnect", { method: "POST" });
      setMsg("Atlassian-Verbindung getrennt.");
      window.location.reload();
    } catch (e: unknown) {
      const err = e as { error?: string };
      setMsg(err?.error ?? "Fehler beim Trennen der Verbindung.");
    } finally {
      setDisconnecting(false);
    }
  };

  return (
    <div className="rounded-sm p-4 space-y-3" style={{ border: "0.5px solid var(--paper-rule)", background: "var(--paper-warm)" }}>
      <div className="flex items-center justify-between">
        <div>
          <p style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase", color: "var(--ink-mid)" }}>{t("settings_profile_atlassian")}</p>
          <p style={{ fontFamily: "var(--font-body)", fontSize: "13px", color: "var(--ink-faint)", marginTop: "2px" }}>
            {isConnected
              ? `${t("settings_profile_atlassian_connected")} — ${user.atlassian_email ?? user.email}`
              : "—"}
          </p>
        </div>
        {isConnected ? (
          <button
            onClick={() => void disconnect()}
            disabled={disconnecting}
            className="px-3 py-1.5 rounded-sm transition-colors disabled:opacity-50"
            style={{ fontFamily: "var(--font-mono)", fontSize: "8px", letterSpacing: ".06em", textTransform: "uppercase", border: "0.5px solid var(--accent-red)", color: "var(--accent-red)" }}
          >
            {disconnecting ? t("settings_profile_atlassian_linking") : "Trennen"}
          </button>
        ) : (
          <button
            onClick={linkAtlassian}
            className="px-3 py-1.5 rounded-sm transition-colors"
            style={{ fontFamily: "var(--font-mono)", fontSize: "8px", letterSpacing: ".06em", textTransform: "uppercase", border: "0.5px solid var(--paper-rule)", color: "var(--ink)" }}
          >
            {t("settings_profile_atlassian_connect")}
          </button>
        )}
      </div>
      {msg && (
        <p style={{ fontFamily: "var(--font-body)", fontSize: "12px", color: "var(--ink-faint)" }}>{msg}</p>
      )}
    </div>
  );
}

// ── Section: GitHub Connection ────────────────────────────────────────────

function GitHubConnectionSection({ user }: { user: User }) {
  const { t } = useT();
  const { loginWithGitHub } = useAuth();
  const [disconnecting, setDisconnecting] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const isConnected = !!user.github_id;

  const disconnect = async () => {
    setDisconnecting(true);
    setMsg(null);
    try {
      await apiRequest("/api/v1/auth/github/disconnect", { method: "POST" });
      setMsg("GitHub-Verbindung getrennt.");
      window.location.reload();
    } catch (e: unknown) {
      const err = e as { error?: string };
      setMsg(err?.error ?? "Fehler beim Trennen der Verbindung.");
    } finally {
      setDisconnecting(false);
    }
  };

  return (
    <div className="rounded-sm p-4 space-y-3" style={{ border: "0.5px solid var(--paper-rule)", background: "var(--paper-warm)" }}>
      <div className="flex items-center justify-between">
        <div>
          <p style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase", color: "var(--ink-mid)" }}>{t("settings_profile_github")}</p>
          <p style={{ fontFamily: "var(--font-body)", fontSize: "13px", color: "var(--ink-faint)", marginTop: "2px" }}>
            {isConnected
              ? `${t("settings_profile_github_connected")} — ${user.github_username ?? user.github_email ?? user.email}`
              : "—"}
          </p>
        </div>
        {isConnected ? (
          <button
            onClick={() => void disconnect()}
            disabled={disconnecting}
            className="px-3 py-1.5 rounded-sm transition-colors disabled:opacity-50"
            style={{ fontFamily: "var(--font-mono)", fontSize: "8px", letterSpacing: ".06em", textTransform: "uppercase", border: "0.5px solid var(--accent-red)", color: "var(--accent-red)" }}
          >
            {disconnecting ? "…" : "Trennen"}
          </button>
        ) : (
          <button
            onClick={loginWithGitHub}
            className="px-3 py-1.5 rounded-sm transition-colors"
            style={{ fontFamily: "var(--font-mono)", fontSize: "8px", letterSpacing: ".06em", textTransform: "uppercase", border: "0.5px solid var(--paper-rule)", color: "var(--ink)" }}
          >
            {t("settings_profile_github_connect")}
          </button>
        )}
      </div>
      {msg && (
        <p style={{ fontFamily: "var(--font-body)", fontSize: "12px", color: "var(--ink-faint)" }}>{msg}</p>
      )}
    </div>
  );
}

// ── Section: User Profile ─────────────────────────────────────────────────

function UserSection({ user }: { user: User }) {
  const { t } = useT();
  const parts = (user.display_name ?? "").split(" ");
  const [firstName, setFirstName] = useState(parts[0] ?? "");
  const [lastName, setLastName] = useState(parts.slice(1).join(" "));
  const [organisation, setOrganisation] = useState(user.display_name ?? "");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true); setMsg(null);
    const displayName = [firstName.trim(), lastName.trim()].filter(Boolean).join(" ") || organisation.trim();
    try {
      await apiRequest("/api/v1/users/me", {
        method: "PATCH",
        body: JSON.stringify({ display_name: displayName }),
      });
      setOrganisation(displayName);
      setMsg({ type: "success", text: t("settings_profile_saved") });
      setTimeout(() => setMsg(null), 3000);
    } catch { setMsg({ type: "error", text: t("settings_profile_error") }); }
    finally { setSaving(false); }
  };

  return (
    <form onSubmit={e => void handleSubmit(e)} className="space-y-5 max-w-lg">
      <SectionMessage msg={msg} />
      <div className="grid grid-cols-2 gap-4">
        <FormField id="firstName" label="Vorname" value={firstName} onChange={setFirstName} />
        <FormField id="lastName" label="Nachname" value={lastName} onChange={setLastName} />
      </div>
      <FormField id="organisation" label="Organisation" value={organisation} onChange={setOrganisation} />
      <div>
        <label className="block text-sm font-medium text-[var(--ink-mid)] mb-1">{t("settings_profile_email")}</label>
        <input
          value={user.email ?? "—"}
          disabled
          className="w-full px-3 py-2 text-sm border border-[var(--paper-rule)] rounded-sm bg-[var(--paper-warm)] text-[var(--ink-faint)] cursor-not-allowed"
        />
      </div>
      <SaveButton saving={saving} label={t("settings_general_save")} />
    </form>
  );
}

// ── Section: Password Change ───────────────────────────────────────────────

function PasswordChangeSection() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (next !== confirm) { setMsg({ type: "error", text: "Die neuen Passwörter stimmen nicht überein." }); return; }
    if (next.length < 8) { setMsg({ type: "error", text: "Das neue Passwort muss mindestens 8 Zeichen lang sein." }); return; }
    setSaving(true); setMsg(null);
    try {
      await apiRequest("/api/v1/users/me/password", {
        method: "POST",
        body: JSON.stringify({ current_password: current, new_password: next }),
      });
      setCurrent(""); setNext(""); setConfirm("");
      setMsg({ type: "success", text: "Passwort erfolgreich geändert." });
      setTimeout(() => setMsg(null), 4000);
    } catch (err: any) {
      const detail = err?.detail ?? "Fehler beim Ändern des Passworts.";
      setMsg({ type: "error", text: detail });
    } finally { setSaving(false); }
  };

  return (
    <form onSubmit={e => void handleSubmit(e)} className="space-y-4 max-w-lg">
      <SectionMessage msg={msg} />
      <TokenField id="pw-current" label="Aktuelles Passwort" placeholder="Aktuelles Passwort" value={current} onChange={setCurrent} isSet={false} />
      <TokenField id="pw-new" label="Neues Passwort" placeholder="Mindestens 8 Zeichen" value={next} onChange={setNext} isSet={false} />
      <TokenField id="pw-confirm" label="Neues Passwort bestätigen" placeholder="Wiederholen" value={confirm} onChange={setConfirm} isSet={false} />
      <SaveButton saving={saving} label="Passwort ändern" />
    </form>
  );
}

// ── Theme Selector ────────────────────────────────────────────────────────

const THEMES: { id: ThemeId; name: string; desc: string; preview: { bg: string; sidebar: string; text: string; accent: string; font: string } }[] = [
  {
    id: "paperwork",
    name: "Paperwork",
    desc: "Analoges Papier-Ästhetik mit Serifenschrift und Karo-Hintergrund",
    preview: { bg: "var(--paper)", sidebar: "var(--binding)", text: "var(--ink)", accent: "var(--accent-red)", font: "Georgia, serif" },
  },
  {
    id: "agile",
    name: "Agile",
    desc: "Cleanes, modernes Interface mit kräftigen Kontrasten",
    preview: { bg: "#FDFBF7", sidebar: "#231F1F", text: "#231F1F", accent: "#534D5F", font: "Inter, sans-serif" },
  },
  {
    id: "karl",
    name: "Karl",
    desc: "Landing-Page-Design: Orange, Cream und harte Schatten",
    preview: { bg: "#F5F0E8", sidebar: "#FFFFFF", text: "#0A0A0A", accent: "#FF5C00", font: "-apple-system, sans-serif" },
  },
];

function ThemeSelector() {
  const { theme, setTheme } = useTheme();

  return (
    <div className="space-y-3">
      <div className="flex gap-3">
        {THEMES.map((t) => {
          const active = theme === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setTheme(t.id)}
              className="flex-1 text-left rounded-sm transition-all focus-visible:outline-none"
              style={{
                border: active ? `1.5px solid var(--accent-red)` : "1px solid var(--paper-rule)",
                background: active ? "rgba(var(--accent-red-rgb),.04)" : "var(--paper-warm)",
                boxShadow: active ? "0 0 0 3px rgba(var(--accent-red-rgb),.1)" : "none",
              }}
            >
              {/* Mini-Vorschau */}
              <div
                className="rounded-t-sm overflow-hidden"
                style={{ height: "72px", background: t.preview.bg, display: "flex", borderBottom: "1px solid var(--paper-rule)" }}
              >
                {/* Fake-Sidebar */}
                <div style={{ width: "28px", background: t.preview.sidebar, flexShrink: 0, display: "flex", flexDirection: "column", gap: "4px", padding: "6px 4px", borderRight: t.preview.sidebar === "#FFFFFF" ? "2px solid #0A0A0A" : "none" }}>
                  {[1, 2, 3].map(i => (
                    <div key={i} style={{ height: "3px", borderRadius: "1px", background: t.preview.sidebar === "#FFFFFF" ? "rgba(10,10,10,.2)" : "rgba(255,255,255,.25)" }} />
                  ))}
                </div>
                {/* Fake-Content */}
                <div style={{ flex: 1, padding: "8px", display: "flex", flexDirection: "column", gap: "5px" }}>
                  <div style={{ height: "5px", width: "55%", borderRadius: "2px", background: t.preview.text, opacity: .7, fontFamily: t.preview.font }} />
                  <div style={{ height: "3px", width: "80%", borderRadius: "2px", background: t.preview.text, opacity: .2 }} />
                  <div style={{ height: "3px", width: "65%", borderRadius: "2px", background: t.preview.text, opacity: .2 }} />
                  <div style={{ marginTop: "4px", height: "14px", width: "40%", borderRadius: "2px", background: t.preview.accent, opacity: .8 }} />
                </div>
              </div>

              {/* Label */}
              <div className="px-3 py-2.5">
                <div className="flex items-center justify-between">
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: "9px", letterSpacing: ".08em", textTransform: "uppercase", color: active ? "var(--accent-red)" : "var(--ink)", fontWeight: active ? 600 : 400 }}>
                    {t.name}
                  </span>
                  {active && (
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: "7px", letterSpacing: ".06em", textTransform: "uppercase", color: "var(--accent-red)" }}>
                      Aktiv
                    </span>
                  )}
                </div>
                <p style={{ fontFamily: "var(--font-body)", fontSize: "11px", color: "var(--ink-faint)", marginTop: "2px", lineHeight: 1.4 }}>
                  {t.desc}
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────

export default function SettingsPage({ params }: { params: Promise<{ org: string }> }) {
  const resolvedParams = use(params);
  const { org, mutate: mutateOrg } = useOrg(resolvedParams.org);
  const { user, refreshUser } = useAuth();
  const { t } = useT();
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const TABS = [
    { id: "profile" as const,    label: t("settings_tab_profile"),    Icon: UserCircle2 },
    { id: "general" as const,    label: t("settings_tab_general"),    Icon: Building2 },
    { id: "email" as const,      label: t("settings_tab_email"),      Icon: Mail },
    { id: "calendar" as const,   label: t("settings_tab_calendar"),   Icon: CalendarDays },
    { id: "jira" as const,       label: t("settings_tab_jira"),       Icon: Layers },
    { id: "confluence" as const, label: t("settings_tab_confluence"), Icon: Cloud },
    { id: "processes" as const,  label: t("process_manage_title"),    Icon: Layers },
    { id: "ai" as const,         label: t("settings_tab_ai"),         Icon: Sparkles },
    { id: "billing" as const,    label: "Abrechnung",                 Icon: CreditCard },
    { id: "zones" as const,      label: "RAG Zonen",                  Icon: Shield },
  ];

  const tabFromUrl = searchParams.get("tab") as TabId | null;
  const validTab = TAB_IDS.some(id => id === tabFromUrl) ? tabFromUrl! : "profile";
  const [activeTab, setActiveTab] = useState<TabId>(validTab);

  // Sync tab from URL when navigating via sidebar links
  useEffect(() => {
    const tabParam = searchParams.get("tab") as TabId | null;
    if (tabParam && (TAB_IDS as readonly string[]).includes(tabParam)) setActiveTab(tabParam);
  }, [searchParams]);

  const handleTabChange = useCallback((id: TabId) => {
    setActiveTab(id);
    router.replace(`${pathname}?tab=${id}`, { scroll: false });
  }, [pathname, router]);

  const { data: integrationSettings, mutate: mutateIntegrations } = useSWR<IntegrationSettings>(
    org ? `/api/v1/organizations/${org.id}/integrations` : null,
    fetcher,
    { revalidateOnFocus: false }
  );

  if (!org) {
    return (
      <div className="flex items-center justify-center h-48">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[var(--accent-red)]" />
      </div>
    );
  }

  return (
    <div>
      {/* Tab content — full width, sidebar navigation drives tabs via ?tab= param */}
      <div className="rounded-sm p-4 md:p-6" style={{ background: "var(--paper)", border: "1px solid var(--paper-rule)" }}>
          {activeTab === "profile" && user && (
            <>
              <h2 className="text-base font-semibold text-[var(--ink)] mb-5">{t("settings_profile_title")}</h2>
              <ProfileSection user={user} refreshUser={refreshUser} />
              <div className="mt-8 max-w-lg space-y-6">
                <UserSection user={user} />
                <div className="pt-4 border-t border-[var(--paper-rule)] space-y-2">
                  <h3 className="text-sm font-semibold text-[var(--ink)]">{t("settings_user_password_heading")}</h3>
                  <PasswordChangeSection />
                </div>
                <div className="pt-4 border-t border-[var(--paper-rule)] space-y-2">
                  <h3 className="text-sm font-semibold text-[var(--ink)]">{t("settings_user_appearance_heading")}</h3>
                  <ThemeSelector />
                </div>
                <div className="pt-4 border-t border-[var(--paper-rule)] space-y-2">
                  <h3 className="text-sm font-semibold text-[var(--ink)]">{t("settings_user_linked_accounts")}</h3>
                  <AtlassianConnectionSection user={user} />
                  <GitHubConnectionSection user={user} />
                </div>
              </div>
            </>
          )}
          {activeTab === "general" && (
            <OrgTabWithSubTabs org={org} mutateOrg={mutateOrg} />
          )}
          {activeTab === "email" && (
            <>
              <h2 className="text-base font-semibold text-[var(--ink)] mb-5">{t("settings_tab_email")}</h2>
              <EmailSection orgId={org.id} />
            </>
          )}
          {activeTab === "calendar" && (
            <>
              <h2 className="text-base font-semibold text-[var(--ink)] mb-5">{t("settings_tab_calendar")}</h2>
              <CalendarSection orgId={org.id} />
            </>
          )}
          {activeTab === "jira" && (
            <>
              <h2 className="text-base font-semibold text-[var(--ink)] mb-5">{t("settings_tab_jira")}</h2>
              {integrationSettings ? (
                <JiraSection orgId={org.id} settings={integrationSettings.jira} onSaved={mutateIntegrations} />
              ) : (
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-[var(--accent-red)]" />
              )}
            </>
          )}
          {activeTab === "confluence" && (
            <>
              <h2 className="text-base font-semibold text-[var(--ink)] mb-5">{t("settings_tab_confluence")}</h2>
              {integrationSettings ? (
                <ConfluenceSection orgId={org.id} settings={integrationSettings.confluence} onSaved={mutateIntegrations} />
              ) : (
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-[var(--accent-red)]" />
              )}
            </>
          )}
          {activeTab === "processes" && (
            <>
              <h2 className="text-base font-semibold text-[var(--ink)] mb-5">{t("process_manage_title")}</h2>
              <ProcessManageSection orgId={org.id} />
            </>
          )}
          {activeTab === "ai" && (
            <>
              <h2 className="text-base font-semibold text-[var(--ink)] mb-5">{t("settings_tab_ai")}</h2>
              {integrationSettings ? (
                <AISection orgId={org.id} settings={integrationSettings.ai} />
              ) : (
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-[var(--accent-red)]" />
              )}
            </>
          )}
          {activeTab === "billing" && (
            <BillingInline orgSlug={resolvedParams.org} orgId={org.id} />
          )}
          {activeTab === "zones" && (
            <>
              <h2 className="text-base font-semibold text-[var(--ink)] mb-5">RAG Zonen & Zugriffssteuerung</h2>
              <RagZonesSection orgId={org.id} />
            </>
          )}
      </div>
    </div>
  );
}

// ── Billing Inline component ───────────────────────────────────────────────

function BillingInline({ orgSlug, orgId }: { orgSlug: string; orgId: string }) {
  const billingPath = `/${orgSlug}/settings/billing`;
  // Use Link to navigate to the dedicated billing sub-page
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-12">
      <p className="text-sm text-[var(--ink-faint)]">Abrechnung & Nutzung wird auf der nächsten Seite angezeigt.</p>
      <a
        href={billingPath}
        className="inline-flex items-center gap-2 px-4 py-2 bg-[var(--accent-red)] text-white rounded-sm text-sm font-medium hover:bg-[var(--btn-primary-hover)] transition-colors"
      >
        <CreditCard size={15} />
        Zur Abrechnung
      </a>
    </div>
  );
}
