"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type ActionType = "step_up" | "buy_sip" | "pause_sip" | "download_report";

interface Sip {
  fund: string;
  amount: number;
  day: number;
  status: string;
  started: string;
}

interface ActionData {
  token: string;
  phone: string;
  action: ActionType;
  fund_name: string | null;
  current_amount: number | null;
  suggested_amount: number | null;
  note: string | null;
  user_name: string;
  status: "pending" | "confirmed" | "expired";
  sips: Sip[];
  portfolio_value: string | null;
  portfolio_xirr: number | null;
}

const ACTION_META: Record<ActionType, { label: string; color: string; grad: string; icon: string; verb: string }> = {
  step_up: {
    label: "SIP Step-Up",
    color: "#10b981",
    grad: "linear-gradient(135deg, #064e3b, #065f46)",
    icon: "↑",
    verb: "Step Up",
  },
  buy_sip: {
    label: "Start New SIP",
    color: "#6366f1",
    grad: "linear-gradient(135deg, #1e1b4b, #312e81)",
    icon: "+",
    verb: "Start SIP",
  },
  pause_sip: {
    label: "Pause SIP",
    color: "#f59e0b",
    grad: "linear-gradient(135deg, #451a03, #78350f)",
    icon: "⏸",
    verb: "Pause SIP",
  },
  download_report: {
    label: "Download Report",
    color: "#3b82f6",
    grad: "linear-gradient(135deg, #1e3a5f, #1e40af)",
    icon: "↓",
    verb: "Download",
  },
};

function fmt(n: number) {
  return "₹" + n.toLocaleString("en-IN");
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export default function ActionPage() {
  const { token } = useParams<{ token: string }>();
  const [data, setData] = useState<ActionData | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "confirming" | "success" | "error" | "expired">("loading");
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    if (!token) return;
    fetch(`${API}/api/actions/${token}`)
      .then((r) => {
        if (r.status === 410) { setState("expired"); return null; }
        if (!r.ok) throw new Error("Action not found");
        return r.json();
      })
      .then((d) => {
        if (!d) return;
        setData(d);
        if (d.status === "confirmed") setState("success");
        else if (d.status === "expired") setState("expired");
        else setState("ready");
      })
      .catch((e) => { setErrorMsg(e.message); setState("error"); });
  }, [token]);

  async function confirm() {
    setState("confirming");
    try {
      const r = await fetch(`${API}/api/actions/${token}/confirm`, { method: "POST" });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.detail ?? "Confirmation failed");
      }
      setState("success");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Something went wrong";
      setErrorMsg(msg);
      setState("error");
    }
  }

  if (state === "loading") return <Loader />;
  if (state === "expired") return <StatusScreen type="expired" />;
  if (state === "error") return <StatusScreen type="error" message={errorMsg} />;
  if (state === "success") return <SuccessScreen data={data} />;
  if (!data) return null;

  const meta = ACTION_META[data.action] ?? ACTION_META.buy_sip;

  return (
    <div className="min-h-screen" style={{ background: "#0f172a" }}>
      {/* Header */}
      <div className="relative overflow-hidden px-5 pt-8 pb-10" style={{ background: meta.grad }}>
        <div className="absolute inset-0 dot-grid opacity-30" />
        <div className="relative z-10">
          <div className="flex items-center gap-2 mb-6">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center text-white font-bold text-sm"
              style={{ background: "rgba(255,255,255,0.15)" }}>Fi</div>
            <span className="text-white/70 text-sm font-medium">FundsIndia</span>
          </div>
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl flex items-center justify-center text-2xl font-bold text-white"
              style={{ background: "rgba(255,255,255,0.12)", backdropFilter: "blur(10px)" }}>
              {meta.icon}
            </div>
            <div>
              <p className="text-white/60 text-xs font-medium uppercase tracking-widest mb-1">{meta.label}</p>
              <h1 className="text-white text-2xl font-bold">Hi, {data.user_name.split(" ")[0]} 👋</h1>
            </div>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="px-4 -mt-4 pb-24 space-y-4">
        {/* Action card */}
        <div className="rounded-2xl overflow-hidden" style={{ background: "#1e293b", border: "1px solid rgba(255,255,255,0.06)" }}>
          <div className="h-1" style={{ background: `linear-gradient(90deg, ${meta.color}, transparent)` }} />
          <div className="p-5 space-y-4">
            {data.action === "step_up" && (
              <StepUpDetails data={data} meta={meta} />
            )}
            {data.action === "buy_sip" && (
              <BuySipDetails data={data} meta={meta} />
            )}
            {data.action === "pause_sip" && (
              <PauseSipDetails data={data} meta={meta} />
            )}
            {data.action === "download_report" && (
              <DownloadReportDetails data={data} meta={meta} />
            )}
            {data.note && (
              <div className="rounded-xl p-3" style={{ background: "rgba(255,255,255,0.04)" }}>
                <p className="text-white/50 text-xs font-medium mb-1">Note from your advisor</p>
                <p className="text-white/80 text-sm">{data.note}</p>
              </div>
            )}
          </div>
        </div>

        {/* Portfolio snapshot */}
        {(data.portfolio_value || data.sips.length > 0) && (
          <div className="rounded-2xl p-5 space-y-3" style={{ background: "#1e293b", border: "1px solid rgba(255,255,255,0.06)" }}>
            <p className="text-white/40 text-xs font-medium uppercase tracking-widest">Your Portfolio</p>
            {data.portfolio_value && (
              <div className="flex items-baseline gap-2">
                <span className="text-white text-2xl font-bold">{data.portfolio_value}</span>
                {data.portfolio_xirr && (
                  <span className="text-emerald-400 text-sm font-semibold">+{data.portfolio_xirr}% XIRR</span>
                )}
              </div>
            )}
            {data.sips.filter(s => s.status === "active").length > 0 && (
              <div className="space-y-2 pt-1">
                {data.sips.filter(s => s.status === "active").slice(0, 3).map((sip) => (
                  <div key={sip.fund} className="flex items-center justify-between">
                    <span className="text-white/60 text-xs truncate flex-1 mr-3">{sip.fund}</span>
                    <span className="text-white/80 text-xs font-medium whitespace-nowrap">{fmt(sip.amount)}/mo</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Security note */}
        <div className="flex items-start gap-3 px-1">
          <div className="mt-0.5 w-4 h-4 shrink-0 rounded-full flex items-center justify-center"
            style={{ background: "rgba(16,185,129,0.15)" }}>
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
          </div>
          <p className="text-white/30 text-xs leading-relaxed">
            This is a secure, one-time link valid for 24 hours. Your confirmation will be processed within 1 business day and you&apos;ll receive an SMS update.
          </p>
        </div>
      </div>

      {/* Sticky CTA */}
      <div className="fixed bottom-0 left-0 right-0 p-4"
        style={{ background: "linear-gradient(to top, #0f172a 60%, transparent)", paddingBottom: "max(1rem, env(safe-area-inset-bottom))" }}>
        <button
          onClick={confirm}
          disabled={state === "confirming"}
          className="w-full py-4 rounded-2xl font-bold text-white text-base transition-all duration-150 active:scale-[0.98]"
          style={{
            background: state === "confirming"
              ? "rgba(255,255,255,0.1)"
              : `linear-gradient(135deg, ${meta.color}, ${meta.color}cc)`,
            boxShadow: state === "confirming" ? "none" : `0 8px 32px ${meta.color}40`,
          }}>
          {state === "confirming" ? "Processing…" : `Confirm ${meta.verb}`}
        </button>
        <button
          className="w-full py-3 mt-2 text-white/30 text-sm font-medium"
          onClick={() => window.close()}>
          Not now
        </button>
      </div>
    </div>
  );
}

function StepUpDetails({ data, meta }: { data: ActionData; meta: typeof ACTION_META[ActionType] }) {
  const curr = data.current_amount ?? 0;
  const next = data.suggested_amount ?? 0;
  const increase = next - curr;
  const pct = curr > 0 ? Math.round((increase / curr) * 100) : 0;

  return (
    <div className="space-y-4">
      <div>
        <p className="text-white/40 text-xs font-medium uppercase tracking-widest mb-1">Fund</p>
        <p className="text-white font-semibold text-sm">{data.fund_name ?? "—"}</p>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <AmountChip label="Current SIP" value={fmt(curr)} muted />
        <div className="flex items-center justify-center">
          <div className="px-2 py-1 rounded-full text-xs font-bold" style={{ background: `${meta.color}20`, color: meta.color }}>
            +{pct}%
          </div>
        </div>
        <AmountChip label="New SIP" value={fmt(next)} highlight color={meta.color} />
      </div>
      <div className="rounded-xl p-3 flex items-center gap-3" style={{ background: `${meta.color}15` }}>
        <span className="text-lg">{meta.icon}</span>
        <div>
          <p className="text-xs font-semibold" style={{ color: meta.color }}>₹{increase.toLocaleString("en-IN")} extra/month</p>
          <p className="text-white/50 text-xs mt-0.5">Invested from your next SIP date (day {data.sips.find(s => s.fund === data.fund_name)?.day ?? "—"})</p>
        </div>
      </div>
    </div>
  );
}

function BuySipDetails({ data, meta }: { data: ActionData; meta: typeof ACTION_META[ActionType] }) {
  return (
    <div className="space-y-4">
      <div>
        <p className="text-white/40 text-xs font-medium uppercase tracking-widest mb-1">New Fund</p>
        <p className="text-white font-semibold">{data.fund_name ?? "—"}</p>
      </div>
      <div className="rounded-xl p-4 flex items-center justify-between" style={{ background: `${meta.color}15` }}>
        <div>
          <p className="text-white/50 text-xs mb-1">Monthly SIP Amount</p>
          <p className="text-white font-bold text-2xl">{fmt(data.suggested_amount ?? 0)}</p>
        </div>
        <div className="w-12 h-12 rounded-2xl flex items-center justify-center text-xl"
          style={{ background: `${meta.color}25`, color: meta.color }}>
          {meta.icon}
        </div>
      </div>
      <p className="text-white/40 text-xs">Auto-debit will be set up from your registered bank account.</p>
    </div>
  );
}

function PauseSipDetails({ data, meta }: { data: ActionData; meta: typeof ACTION_META[ActionType] }) {
  const sip = data.sips.find(s => s.fund === data.fund_name);
  return (
    <div className="space-y-4">
      <div>
        <p className="text-white/40 text-xs font-medium uppercase tracking-widest mb-1">Fund to Pause</p>
        <p className="text-white font-semibold">{data.fund_name ?? "—"}</p>
      </div>
      <div className="rounded-xl p-4 space-y-3" style={{ background: `${meta.color}15` }}>
        <div className="flex justify-between">
          <span className="text-white/50 text-sm">Current SIP</span>
          <span className="text-white font-semibold">{fmt(sip?.amount ?? data.current_amount ?? 0)}/mo</span>
        </div>
        {sip?.started && (
          <div className="flex justify-between">
            <span className="text-white/50 text-sm">Active since</span>
            <span className="text-white/70 text-sm">{formatDate(sip.started)}</span>
          </div>
        )}
      </div>
      <div className="rounded-xl p-3 flex items-start gap-2" style={{ background: "rgba(251,191,36,0.08)", border: "1px solid rgba(251,191,36,0.15)" }}>
        <span className="text-amber-400 text-sm mt-0.5">⚠</span>
        <p className="text-amber-400/80 text-xs leading-relaxed">Pausing your SIP will interrupt your investment journey. You can resume anytime.</p>
      </div>
    </div>
  );
}

function DownloadReportDetails({ data, meta }: { data: ActionData; meta: typeof ACTION_META[ActionType] }) {
  return (
    <div className="space-y-4">
      <div className="rounded-xl p-4 flex items-center gap-4" style={{ background: `${meta.color}15` }}>
        <div className="w-12 h-12 rounded-2xl flex items-center justify-center text-xl"
          style={{ background: `${meta.color}25`, color: meta.color }}>
          📊
        </div>
        <div>
          <p className="text-white font-semibold">Portfolio Report</p>
          <p className="text-white/50 text-xs mt-0.5">Holdings, XIRR, SIP summary</p>
        </div>
      </div>
      {data.portfolio_value && (
        <div className="flex justify-between px-1">
          <span className="text-white/40 text-sm">Current Value</span>
          <span className="text-white font-semibold">{data.portfolio_value}</span>
        </div>
      )}
      <p className="text-white/40 text-xs">The report will be sent to your WhatsApp as a PDF.</p>
    </div>
  );
}

function AmountChip({ label, value, muted, highlight, color }: {
  label: string; value: string; muted?: boolean; highlight?: boolean; color?: string
}) {
  return (
    <div className="rounded-xl p-3 text-center" style={{ background: "rgba(255,255,255,0.04)" }}>
      <p className="text-white/40 text-xs mb-1">{label}</p>
      <p className={`font-bold text-sm ${muted ? "text-white/50 line-through" : ""}`}
        style={highlight ? { color } : undefined}>
        {value}
      </p>
    </div>
  );
}

function SuccessScreen({ data }: { data: ActionData | null }) {
  const meta = data ? ACTION_META[data.action] : ACTION_META.buy_sip;
  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-8 text-center" style={{ background: "#0f172a" }}>
      <div className="w-20 h-20 rounded-full flex items-center justify-center mb-6"
        style={{ background: `${meta.color}20`, boxShadow: `0 0 60px ${meta.color}30` }}>
        <svg viewBox="0 0 24 24" fill="none" stroke={meta.color} strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" className="w-10 h-10">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      </div>
      <h2 className="text-white text-2xl font-bold mb-2">Request Confirmed!</h2>
      <p className="text-white/50 text-sm leading-relaxed max-w-xs">
        Your {meta.label.toLowerCase()} request has been received. We&apos;ll process it within 1 business day and send you an SMS confirmation.
      </p>
      <div className="mt-8 px-4 py-3 rounded-xl text-white/40 text-xs" style={{ background: "rgba(255,255,255,0.05)" }}>
        You can close this window now 🙏
      </div>
    </div>
  );
}

function StatusScreen({ type, message }: { type: "expired" | "error"; message?: string }) {
  const isExpired = type === "expired";
  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-8 text-center" style={{ background: "#0f172a" }}>
      <div className="w-20 h-20 rounded-full flex items-center justify-center mb-6"
        style={{ background: isExpired ? "rgba(251,191,36,0.1)" : "rgba(239,68,68,0.1)" }}>
        <span className="text-4xl">{isExpired ? "⏰" : "⚠️"}</span>
      </div>
      <h2 className="text-white text-2xl font-bold mb-2">
        {isExpired ? "Link Expired" : "Something went wrong"}
      </h2>
      <p className="text-white/50 text-sm leading-relaxed max-w-xs">
        {isExpired
          ? "This action link has expired. Please contact your advisor for a new link."
          : message ?? "We couldn't process your request. Please try again or contact support."}
      </p>
    </div>
  );
}

function Loader() {
  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: "#0f172a" }}>
      <div className="w-10 h-10 rounded-full border-2 border-white/10 border-t-emerald-400 animate-spin" />
    </div>
  );
}
