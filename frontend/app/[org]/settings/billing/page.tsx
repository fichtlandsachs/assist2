"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import useSWR from "swr";
import {
  CreditCard, Zap, TrendingUp, CheckCircle, AlertCircle,
  ExternalLink, RefreshCw, BarChart3, ChevronRight, Clock,
  Package, XCircle, FileText,
} from "lucide-react";
import { fetcher, apiRequest } from "@/lib/api/client";
import { useAuth } from "@/lib/auth/context";

// ── Types ──────────────────────────────────────────────────────────────────

interface BillingStatus {
  has_access: boolean;
  plan: string;
  status: string | null;
  trial_end: string | null;
  cancel_at_period_end: boolean;
  current_period_end: string | null;
}

interface Subscription {
  id: string;
  plan: string;
  status: string;
  provider: string;
  stripe_customer_id: string | null;
  stripe_subscription_id: string | null;
  paypal_subscription_id: string | null;
  current_period_start: string | null;
  current_period_end: string | null;
  trial_end: string | null;
  cancel_at_period_end: boolean;
  canceled_at: string | null;
  included_tokens: number;
  max_members: number | null;
  is_access_granted: boolean;
}

interface PricingPlan {
  id: string;
  plan: string;
  display_name: string;
  base_price_eur_cents: number;
  included_tokens: number;
  price_per_1k_tokens_eur_cents: number;
  max_members: number | null;
  features: Record<string, boolean> | null;
  sort_order: number;
}

interface UsageSummary {
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  included_tokens: number;
  overage_tokens: number;
  total_cost_usd: number;
  overage_cost_eur: number;
  request_count: number;
  period_start: string | null;
  period_end: string | null;
  by_model: Array<{ model: string; total_tokens: number; cost_usd: number; requests: number }>;
  by_feature: Array<{ feature: string; total_tokens: number; requests: number }>;
}

interface Payment {
  id: string;
  amount_cents: number;
  currency: string;
  status: string;
  description: string | null;
  invoice_url: string | null;
  invoice_pdf_url: string | null;
  paid_at: string | null;
  created_at: string;
}

interface InvoiceSimulation {
  plan: string;
  period_start: string;
  period_end: string;
  line_items: Array<{ description: string; quantity: number; unit_price_eur: number; total_eur: number }>;
  subtotal_eur: number;
  tax_eur: number;
  total_eur: number;
}

// ── Helpers ────────────────────────────────────────────────────────────────

function fmt(cents: number): string {
  return `€${(cents / 100).toFixed(2)}`;
}

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return String(n);
}

function StatusBadge({ status }: { status: string | null }) {
  const map: Record<string, { label: string; color: string }> = {
    active:    { label: "Aktiv",          color: "bg-[rgba(82,107,94,.15)] text-[var(--green)]" },
    trialing:  { label: "Testphase",      color: "bg-blue-50 text-blue-600" },
    past_due:  { label: "Zahlung fällig", color: "bg-amber-50 text-amber-600" },
    canceled:  { label: "Gekündigt",      color: "bg-red-50 text-red-500" },
    unpaid:    { label: "Unbezahlt",      color: "bg-red-50 text-red-500" },
    incomplete:{ label: "Ausstehend",     color: "bg-[var(--paper-warm)] text-[var(--ink-faint)]" },
  };
  const cfg = status ? map[status] : null;
  if (!cfg) return null;
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium ${cfg.color}`}>
      {status === "active" && <CheckCircle size={11} />}
      {status === "trialing" && <Clock size={11} />}
      {(status === "past_due" || status === "unpaid") && <AlertCircle size={11} />}
      {(status === "canceled") && <XCircle size={11} />}
      {cfg.label}
    </span>
  );
}

function UsageBar({ used, total }: { used: number; total: number }) {
  const pct = total > 0 ? Math.min(100, (used / total) * 100) : 0;
  const color = pct >= 90 ? "bg-red-500" : pct >= 70 ? "bg-amber-400" : "bg-[var(--accent-red)]";
  return (
    <div className="w-full h-2 bg-[var(--paper-warm)] rounded-full overflow-hidden">
      <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

// ── Main Page ──────────────────────────────────────────────────────────────

export default function BillingPage() {
  const params = useParams();
  const orgSlug = params.org as string;
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user } = useAuth();

  const [tab, setTab] = useState<"overview" | "usage" | "payments" | "plans">("overview");
  const [upgrading, setUpgrading] = useState<string | null>(null);
  const [canceling, setCanceling] = useState(false);
  const [checkoutMsg, setCheckoutMsg] = useState<string | null>(null);

  // Detect redirect from Stripe Checkout
  useEffect(() => {
    const result = searchParams.get("checkout");
    if (result === "success") setCheckoutMsg("Zahlung erfolgreich! Ihr Abonnement ist jetzt aktiv.");
    if (result === "cancel") setCheckoutMsg("Zahlung abgebrochen. Sie können jederzeit erneut starten.");
  }, [searchParams]);

  // Resolve org_id from slug (we need the UUID for API calls)
  const { data: orgs } = useSWR<Array<{ id: string; slug: string }>>("/api/v1/organizations", fetcher);
  const orgId = orgs?.find((o) => o.slug === orgSlug)?.id;

  const { data: sub, mutate: mutateSub } = useSWR<Subscription | null>(
    orgId ? `/api/v1/orgs/${orgId}/billing/subscription` : null, fetcher,
  );
  const { data: usage } = useSWR<UsageSummary>(
    orgId ? `/api/v1/orgs/${orgId}/billing/usage` : null, fetcher,
  );
  const { data: payments } = useSWR<{ total: number; items: Payment[] }>(
    orgId && tab === "payments" ? `/api/v1/orgs/${orgId}/billing/payments` : null, fetcher,
  );
  const { data: invoice } = useSWR<InvoiceSimulation | null>(
    orgId && tab === "overview" && sub ? `/api/v1/orgs/${orgId}/billing/invoice/preview` : null, fetcher,
  );
  const { data: plans } = useSWR<PricingPlan[]>("/api/v1/billing/pricing", fetcher);

  const handleUpgrade = async (plan: string) => {
    if (!orgId) return;
    setUpgrading(plan);
    try {
      const { url } = await apiRequest<{ url: string }>(`/api/v1/orgs/${orgId}/billing/checkout?plan=${plan}`, { method: "POST" });
      if (url) window.location.href = url;
    } catch (e: any) {
      alert("Fehler beim Erstellen der Checkout-Session: " + (e?.message || ""));
    } finally {
      setUpgrading(null);
    }
  };

  const handlePortal = async () => {
    if (!orgId) return;
    try {
      const { url } = await apiRequest<{ url: string }>(`/api/v1/orgs/${orgId}/billing/portal`, { method: "POST" });
      if (url) window.open(url, "_blank");
    } catch (e: any) {
      alert("Stripe Portal konnte nicht geöffnet werden: " + (e?.message || ""));
    }
  };

  const handleCancel = async () => {
    if (!orgId || !confirm("Abonnement wirklich kündigen? Zugriff endet am Ende des aktuellen Abrechnungszeitraums.")) return;
    setCanceling(true);
    try {
      await apiRequest(`/api/v1/orgs/${orgId}/billing/cancel`, {
        method: "POST",
        body: JSON.stringify({ cancel_at_period_end: true }),
      });
      await mutateSub();
    } catch (e: any) {
      alert("Kündigung fehlgeschlagen: " + (e?.message || ""));
    } finally {
      setCanceling(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-[var(--ink)]">Abrechnung & Nutzung</h1>
        <p className="text-sm text-[var(--ink-faint)] mt-1">
          Verwalten Sie Ihr Abonnement, Zahlungsmethoden und Token-Verbrauch.
        </p>
      </div>

      {/* Checkout feedback */}
      {checkoutMsg && (
        <div className={`flex items-center gap-2 p-3 rounded-sm text-sm border ${
          checkoutMsg.includes("erfolgreich")
            ? "bg-[rgba(82,107,94,.1)] border-[var(--green)] text-[var(--green)]"
            : "bg-amber-50 border-amber-200 text-amber-700"
        }`}>
          {checkoutMsg.includes("erfolgreich") ? <CheckCircle size={15} /> : <AlertCircle size={15} />}
          {checkoutMsg}
          <button onClick={() => setCheckoutMsg(null)} className="ml-auto text-xs opacity-60 hover:opacity-100">✕</button>
        </div>
      )}

      {/* Current plan card */}
      <div className="bg-[var(--card)] border border-[var(--ink-faintest)] rounded-sm p-5">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Package size={16} className="text-[var(--ink-mid)]" />
              <span className="text-sm font-medium text-[var(--ink-mid)]">Aktueller Plan</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xl font-bold text-[var(--ink)] capitalize">
                {sub?.plan ?? "Free"}
              </span>
              <StatusBadge status={sub?.status ?? null} />
              {sub?.cancel_at_period_end && (
                <span className="text-xs text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full">
                  Kündigung zum {sub.current_period_end ? new Date(sub.current_period_end).toLocaleDateString("de") : "—"}
                </span>
              )}
            </div>
            {sub?.current_period_end && (
              <p className="text-xs text-[var(--ink-faint)] mt-1">
                Nächste Verlängerung: {new Date(sub.current_period_end).toLocaleDateString("de-DE")}
              </p>
            )}
            {sub?.trial_end && new Date(sub.trial_end) > new Date() && (
              <p className="text-xs text-blue-500 mt-1">
                Testphase endet: {new Date(sub.trial_end).toLocaleDateString("de-DE")}
              </p>
            )}
          </div>
          <div className="flex gap-2 flex-wrap">
            {sub?.stripe_customer_id && (
              <button
                onClick={handlePortal}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-[var(--ink-faintest)] rounded-sm hover:bg-[var(--paper-warm)] transition-colors"
              >
                <CreditCard size={14} />
                Zahlungsdetails
                <ExternalLink size={11} className="opacity-50" />
              </button>
            )}
            {sub?.is_access_granted && !sub.cancel_at_period_end && (
              <button
                onClick={handleCancel}
                disabled={canceling}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-red-500 border border-red-200 rounded-sm hover:bg-red-50 transition-colors disabled:opacity-50"
              >
                {canceling ? <RefreshCw size={14} className="animate-spin" /> : <XCircle size={14} />}
                Kündigen
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-0 border-b border-[var(--ink-faintest)]">
        {(["overview", "usage", "payments", "plans"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
              tab === t
                ? "border-[var(--accent-red)] text-[var(--accent-red)]"
                : "border-transparent text-[var(--ink-faint)] hover:text-[var(--ink-mid)]"
            }`}
          >
            {t === "overview" && "Übersicht"}
            {t === "usage" && "Nutzung"}
            {t === "payments" && "Zahlungen"}
            {t === "plans" && "Pläne"}
          </button>
        ))}
      </div>

      {/* ── Overview Tab ── */}
      {tab === "overview" && (
        <div className="space-y-4">
          {/* Quick usage stats */}
          {usage && sub?.is_access_granted && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: "Tokens verbraucht", value: fmtTokens(usage.total_tokens), icon: <Zap size={16} /> },
                { label: "Inklusiv-Kontingent", value: fmtTokens(usage.included_tokens), icon: <Package size={16} /> },
                { label: "Mehrverbrauch", value: fmtTokens(usage.overage_tokens), icon: <TrendingUp size={16} /> },
                { label: "Anfragen", value: usage.request_count.toLocaleString("de"), icon: <BarChart3 size={16} /> },
              ].map((s) => (
                <div key={s.label} className="bg-[var(--card)] border border-[var(--ink-faintest)] rounded-sm p-3">
                  <div className="flex items-center gap-1.5 text-[var(--ink-faint)] mb-1">
                    {s.icon}
                    <span className="text-xs">{s.label}</span>
                  </div>
                  <span className="text-lg font-bold text-[var(--ink)]">{s.value}</span>
                </div>
              ))}
            </div>
          )}

          {/* Token progress */}
          {usage && sub?.is_access_granted && usage.included_tokens > 0 && (
            <div className="bg-[var(--card)] border border-[var(--ink-faintest)] rounded-sm p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-[var(--ink-mid)]">Token-Verbrauch</span>
                <span className="text-xs text-[var(--ink-faint)]">
                  {fmtTokens(usage.total_tokens)} / {fmtTokens(usage.included_tokens)}
                </span>
              </div>
              <UsageBar used={usage.total_tokens} total={usage.included_tokens} />
              {usage.overage_tokens > 0 && (
                <p className="text-xs text-amber-600 mt-2">
                  Mehrverbrauch: {fmtTokens(usage.overage_tokens)} Tokens → ca. €{usage.overage_cost_eur.toFixed(2)}
                </p>
              )}
            </div>
          )}

          {/* Invoice preview */}
          {invoice && (
            <div className="bg-[var(--card)] border border-[var(--ink-faintest)] rounded-sm p-4">
              <div className="flex items-center gap-2 mb-3">
                <FileText size={15} className="text-[var(--ink-faint)]" />
                <span className="text-sm font-medium text-[var(--ink-mid)]">Vorschau nächste Rechnung</span>
              </div>
              <div className="space-y-1.5">
                {invoice.line_items.map((item, i) => (
                  <div key={i} className="flex items-start justify-between text-sm">
                    <span className="text-[var(--ink-mid)]">{item.description}</span>
                    <span className="text-[var(--ink)] font-medium ml-4 shrink-0">€{item.total_eur.toFixed(2)}</span>
                  </div>
                ))}
                <div className="border-t border-[var(--ink-faintest)] pt-2 mt-2">
                  <div className="flex justify-between text-xs text-[var(--ink-faint)]">
                    <span>Netto</span><span>€{invoice.subtotal_eur.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-xs text-[var(--ink-faint)]">
                    <span>MwSt. 19%</span><span>€{invoice.tax_eur.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-sm font-bold text-[var(--ink)] mt-1">
                    <span>Gesamt</span><span>€{invoice.total_eur.toFixed(2)}</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* No subscription CTA */}
          {!sub?.is_access_granted && (
            <div className="bg-[var(--card)] border border-[var(--ink-faintest)] rounded-sm p-6 text-center">
              <Package size={32} className="mx-auto mb-3 text-[var(--ink-faintest)]" />
              <h3 className="text-base font-semibold text-[var(--ink)] mb-1">Kein aktives Abonnement</h3>
              <p className="text-sm text-[var(--ink-faint)] mb-4">
                Starten Sie ein Abonnement, um alle AI-Features freizuschalten.
              </p>
              <button
                onClick={() => setTab("plans")}
                className="inline-flex items-center gap-2 px-4 py-2 bg-[var(--accent-red)] text-white rounded-sm text-sm font-medium hover:bg-[var(--btn-primary-hover)] transition-colors"
              >
                Pläne ansehen
                <ChevronRight size={15} />
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── Usage Tab ── */}
      {tab === "usage" && usage && (
        <div className="space-y-4">
          <div className="bg-[var(--card)] border border-[var(--ink-faintest)] rounded-sm p-4">
            <h3 className="text-sm font-semibold text-[var(--ink-mid)] mb-3">Nach Modell</h3>
            {usage.by_model.length === 0 ? (
              <p className="text-sm text-[var(--ink-faint)]">Noch keine Nutzung in diesem Zeitraum.</p>
            ) : (
              <div className="space-y-2">
                {usage.by_model.map((m) => (
                  <div key={m.model} className="flex items-center justify-between text-sm">
                    <span className="text-[var(--ink-mid)] font-mono text-xs">{m.model}</span>
                    <div className="flex gap-4 text-right text-xs text-[var(--ink-faint)]">
                      <span>{fmtTokens(m.total_tokens)} Tokens</span>
                      <span>{m.requests} Req.</span>
                      <span>${m.cost_usd.toFixed(4)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="bg-[var(--card)] border border-[var(--ink-faintest)] rounded-sm p-4">
            <h3 className="text-sm font-semibold text-[var(--ink-mid)] mb-3">Nach Feature</h3>
            {usage.by_feature.length === 0 ? (
              <p className="text-sm text-[var(--ink-faint)]">Noch keine Nutzung.</p>
            ) : (
              <div className="space-y-2">
                {usage.by_feature.map((f) => (
                  <div key={f.feature} className="flex items-center justify-between text-sm">
                    <span className="text-[var(--ink-mid)] capitalize">{f.feature}</span>
                    <div className="flex gap-4 text-right text-xs text-[var(--ink-faint)]">
                      <span>{fmtTokens(f.total_tokens)} Tokens</span>
                      <span>{f.requests} Req.</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <div className="bg-[var(--card)] border border-[var(--ink-faintest)] rounded-sm p-3">
              <p className="text-xs text-[var(--ink-faint)] mb-0.5">Input Tokens</p>
              <p className="text-lg font-bold text-[var(--ink)]">{fmtTokens(usage.total_input_tokens)}</p>
            </div>
            <div className="bg-[var(--card)] border border-[var(--ink-faintest)] rounded-sm p-3">
              <p className="text-xs text-[var(--ink-faint)] mb-0.5">Output Tokens</p>
              <p className="text-lg font-bold text-[var(--ink)]">{fmtTokens(usage.total_output_tokens)}</p>
            </div>
            <div className="bg-[var(--card)] border border-[var(--ink-faintest)] rounded-sm p-3">
              <p className="text-xs text-[var(--ink-faint)] mb-0.5">Kosten (USD)</p>
              <p className="text-lg font-bold text-[var(--ink)]">${usage.total_cost_usd.toFixed(4)}</p>
            </div>
          </div>
        </div>
      )}

      {/* ── Payments Tab ── */}
      {tab === "payments" && (
        <div className="bg-[var(--card)] border border-[var(--ink-faintest)] rounded-sm overflow-hidden">
          {!payments?.items.length ? (
            <div className="p-6 text-center text-sm text-[var(--ink-faint)]">
              Noch keine Zahlungen vorhanden.
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-[var(--paper-warm)] text-xs text-[var(--ink-faint)] text-left">
                  <th className="px-4 py-2.5 font-medium">Beschreibung</th>
                  <th className="px-4 py-2.5 font-medium">Betrag</th>
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium">Datum</th>
                  <th className="px-4 py-2.5 font-medium"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--ink-faintest)]">
                {payments.items.map((p) => (
                  <tr key={p.id} className="hover:bg-[var(--paper-warm)] transition-colors">
                    <td className="px-4 py-3 text-[var(--ink-mid)]">{p.description ?? "—"}</td>
                    <td className="px-4 py-3 font-medium text-[var(--ink)]">
                      {fmt(p.amount_cents)} {p.currency}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        p.status === "succeeded" ? "bg-[rgba(82,107,94,.1)] text-[var(--green)]" :
                        p.status === "failed" ? "bg-red-50 text-red-500" :
                        "bg-[var(--paper-warm)] text-[var(--ink-faint)]"
                      }`}>
                        {p.status === "succeeded" ? "Bezahlt" : p.status === "failed" ? "Fehlgeschlagen" : p.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-[var(--ink-faint)] text-xs">
                      {p.paid_at ? new Date(p.paid_at).toLocaleDateString("de-DE") : "—"}
                    </td>
                    <td className="px-4 py-3">
                      {p.invoice_url && (
                        <a
                          href={p.invoice_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 text-xs text-[var(--accent-red)] hover:underline"
                        >
                          <FileText size={12} />
                          Rechnung
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ── Plans Tab ── */}
      {tab === "plans" && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {(plans ?? []).filter((p) => p.plan !== "free").map((plan) => {
            const isCurrent = sub?.plan === plan.plan;
            const baseEur = plan.base_price_eur_cents / 100;
            const priceStr = plan.base_price_eur_cents === 0 ? "Auf Anfrage" : `€${baseEur.toFixed(0)}/Mo.`;
            return (
              <div
                key={plan.id}
                className={`bg-[var(--card)] border rounded-sm p-5 flex flex-col gap-3 ${
                  isCurrent
                    ? "border-[var(--accent-red)] ring-1 ring-[var(--accent-red)]"
                    : "border-[var(--ink-faintest)]"
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <h3 className="font-bold text-[var(--ink)]">{plan.display_name}</h3>
                    {isCurrent && (
                      <span className="text-xs bg-[rgba(var(--accent-red-rgb),.1)] text-[var(--accent-red)] px-2 py-0.5 rounded-full font-medium">
                        Aktuell
                      </span>
                    )}
                  </div>
                  <p className="text-2xl font-extrabold text-[var(--ink)]">{priceStr}</p>
                </div>

                <div className="space-y-1.5 text-sm text-[var(--ink-mid)] flex-1">
                  <div className="flex items-center gap-2">
                    <Zap size={13} className="text-[var(--accent-red)]" />
                    {fmtTokens(plan.included_tokens)} inkl. Tokens/Mo.
                  </div>
                  <div className="flex items-center gap-2">
                    <Package size={13} className="text-[var(--accent-red)]" />
                    {plan.max_members ? `${plan.max_members} Mitglieder` : "Unbegrenzte Mitglieder"}
                  </div>
                  {plan.price_per_1k_tokens_eur_cents > 0 && (
                    <div className="flex items-center gap-2 text-xs text-[var(--ink-faint)]">
                      <TrendingUp size={12} />
                      €{(plan.price_per_1k_tokens_eur_cents / 100).toFixed(2)} je 1K Tokens danach
                    </div>
                  )}
                  {plan.features && Object.entries(plan.features)
                    .filter(([, v]) => v)
                    .map(([k]) => (
                      <div key={k} className="flex items-center gap-2 text-xs">
                        <CheckCircle size={12} className="text-[var(--green)]" />
                        <span className="capitalize">{k.replace(/_/g, " ")}</span>
                      </div>
                    ))}
                </div>

                {!isCurrent && plan.base_price_eur_cents > 0 && (
                  <button
                    onClick={() => handleUpgrade(plan.plan)}
                    disabled={!!upgrading}
                    className="w-full py-2 px-4 bg-[var(--accent-red)] text-white rounded-sm text-sm font-medium hover:bg-[var(--btn-primary-hover)] transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {upgrading === plan.plan ? (
                      <RefreshCw size={14} className="animate-spin" />
                    ) : null}
                    {isCurrent ? "Aktueller Plan" : "Upgraden"}
                  </button>
                )}
                {plan.base_price_eur_cents === 0 && (
                  <a
                    href="mailto:info@heykarl.app?subject=Enterprise%20Anfrage"
                    className="w-full py-2 px-4 border border-[var(--ink-faintest)] text-[var(--ink-mid)] rounded-sm text-sm font-medium text-center hover:bg-[var(--paper-warm)] transition-colors"
                  >
                    Kontakt aufnehmen
                  </a>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
