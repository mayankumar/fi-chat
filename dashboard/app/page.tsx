"use client";

import { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { Device, Call } from "@twilio/voice-sdk";
import {
  Activity, Phone, PhoneOff, PhoneCall, Paperclip, Send,
  MessageSquare, Users, ChevronRight, Globe2, Target,
  AlertCircle, CheckCircle2, Sparkles, IndianRupee,
  PanelRightClose, TrendingUp, TrendingDown,
  SmilePlus, Frown, Meh, Bot, Zap, Loader2, CalendarClock,
  ShieldCheck, Mic, MicOff, Bell, Home, BarChart2,
  PhoneMissed, Volume2, Headphones, Timer,
  AlertTriangle,
} from "lucide-react";

const API_ROOT = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
const API_BASE = `${API_ROOT.replace(/\/$/, "")}/api`;
const HEADERS: Record<string, string> = { "ngrok-skip-browser-warning": "1" };

// ── Demo Analytics (baseline metrics so dashboard never looks empty) ──

const DEMO_STATS = {
  totalToday: 127,
  activeNow: 47,
  ttaQueueBase: 6,
  avgResponseMin: 2.4,
  conversionPct: 31,
  plansGenerated: 41,
  callsToday: 18,
  avgCallMin: 7.2,
};

const WORD_CLOUD_DATA = [
  { word: "Retirement Planning", weight: 10, color: "#a78bfa" },
  { word: "SIP Setup",           weight: 9,  color: "#34d399" },
  { word: "Portfolio Review",    weight: 8,  color: "#60a5fa" },
  { word: "Goal Planning",       weight: 8,  color: "#fbbf24" },
  { word: "Mutual Funds",        weight: 7,  color: "#818cf8" },
  { word: "Wealth Creation",     weight: 7,  color: "#c084fc" },
  { word: "Market Returns",      weight: 6,  color: "#fb7185" },
  { word: "Risk Profile",        weight: 6,  color: "#2dd4bf" },
  { word: "Tax Saving",          weight: 5,  color: "#38bdf8" },
  { word: "Talk to Advisor",     weight: 5,  color: "#7dd3fc" },
  { word: "Education Fund",      weight: 5,  color: "#fb923c" },
  { word: "SIP Step-Up",         weight: 4,  color: "#f472b6" },
  { word: "House Down Payment",  weight: 4,  color: "#4ade80" },
  { word: "Index Funds",         weight: 3,  color: "#93c5fd" },
  { word: "ELSS",                weight: 3,  color: "#86efac" },
  { word: "Gold Funds",          weight: 3,  color: "#fde68a" },
  { word: "Emergency Fund",      weight: 3,  color: "#fca5a5" },
  { word: "Debt Funds",          weight: 2,  color: "#94a3b8" },
];

const INTENT_DATA = [
  { intent: "Goal Discovery",    pct: 85, grad: "linear-gradient(90deg,#7c3aed,#a78bfa)", glow: "rgba(124,58,237,0.3)" },
  { intent: "Portfolio Query",   pct: 60, grad: "linear-gradient(90deg,#059669,#34d399)", glow: "rgba(5,150,105,0.3)" },
  { intent: "Research Question", pct: 50, grad: "linear-gradient(90deg,#2563eb,#60a5fa)", glow: "rgba(37,99,235,0.3)" },
  { intent: "SIP Action",        pct: 40, grad: "linear-gradient(90deg,#d97706,#fbbf24)", glow: "rgba(217,119,6,0.3)" },
  { intent: "Talk to Advisor",   pct: 30, grad: "linear-gradient(90deg,#dc2626,#f87171)", glow: "rgba(220,38,38,0.3)" },
  { intent: "General Chat",      pct: 25, grad: "linear-gradient(90deg,#475569,#94a3b8)", glow: "rgba(71,85,105,0.2)" },
];

const PAIN_POINTS_DATA = [
  { label: "Wanted human advisor sooner", count: 7, pct: 70 },
  { label: "Bot didn't understand query", count: 6, pct: 60 },
  { label: "Too many steps before advice", count: 5, pct: 50 },
  { label: "PDF generation delay",         count: 3, pct: 30 },
  { label: "Language switch confusion",    count: 2, pct: 20 },
];

const FUNNEL_DATA = [
  { stage: "Conversations Started", pct: 100, grad: "linear-gradient(90deg,#475569,#94a3b8)" },
  { stage: "Completed Onboarding",  pct: 78,  grad: "linear-gradient(90deg,#2563eb,#60a5fa)" },
  { stage: "Explored Goals",        pct: 52,  grad: "linear-gradient(90deg,#7c3aed,#a78bfa)" },
  { stage: "Generated Plan",        pct: 31,  grad: "linear-gradient(90deg,#059669,#34d399)" },
  { stage: "Requested Advisor",     pct: 18,  grad: "linear-gradient(90deg,#d97706,#fbbf24)" },
];

// 7-day chat volume (line chart)
const CHAT_VOLUME_7D = [
  { day: "Mon", total: 82,  tta: 6,  plans: 22 },
  { day: "Tue", total: 108, tta: 9,  plans: 28 },
  { day: "Wed", total: 95,  tta: 7,  plans: 26 },
  { day: "Thu", total: 131, tta: 12, plans: 38 },
  { day: "Fri", total: 154, tta: 14, plans: 45 },
  { day: "Sat", total: 118, tta: 9,  plans: 32 },
  { day: "Sun", total: 89,  tta: 5,  plans: 24 },
];

// Language breakdown for donut
const LANGUAGE_DATA = [
  { lang: "English",  pct: 48, color: "#60a5fa", glow: "rgba(96,165,250,0.5)" },
  { lang: "Hinglish", pct: 32, color: "#f472b6", glow: "rgba(244,114,182,0.5)" },
  { lang: "Hindi",    pct: 20, color: "#fbbf24", glow: "rgba(251,191,36,0.5)" },
];

// Activity heatmap — 7 days × 24 hours, deterministic values
const HEATMAP: number[][] = [
  // Mon
  [1,0,0,0,0,1,2,5,12,22,28,26,18,21,26,24,19,14,11,16,21,18,12,5],
  // Tue
  [0,0,0,0,0,1,3,8,14,24,30,27,21,23,29,26,22,16,13,18,23,20,13,7],
  // Wed
  [1,0,0,0,0,1,2,4,11,20,25,22,17,19,23,21,18,13,10,15,20,16,11,6],
  // Thu
  [0,0,0,0,1,1,3,9,15,26,31,28,23,25,30,28,24,19,15,20,25,22,15,9],
  // Fri
  [1,0,0,1,1,2,4,10,17,28,34,31,26,27,33,31,27,22,18,23,28,25,17,11],
  // Sat
  [2,1,0,0,0,1,2,5,10,15,21,19,17,18,20,18,15,12,9,12,16,14,10,6],
  // Sun
  [1,0,0,0,0,0,1,3,7,10,14,13,11,12,14,13,11,8,6,9,12,10,7,4],
];
const HEATMAP_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const HEATMAP_MAX = 34;

// Top funds by interest (horizontal bar)
const TOP_FUNDS = [
  { fund: "Parag Parikh Flexi Cap",     queries: 87, grad: "linear-gradient(90deg,#059669,#34d399)" },
  { fund: "UTI Flexi Cap Fund",         queries: 72, grad: "linear-gradient(90deg,#2563eb,#60a5fa)" },
  { fund: "Mirae Asset Large & Mid",    queries: 64, grad: "linear-gradient(90deg,#7c3aed,#a78bfa)" },
  { fund: "ICICI Pru NASDAQ 100",       queries: 58, grad: "linear-gradient(90deg,#d97706,#fbbf24)" },
  { fund: "DSP Midcap Fund",            queries: 51, grad: "linear-gradient(90deg,#c026d3,#e879f9)" },
  { fund: "Bandhan Arbitrage FOF",      queries: 42, grad: "linear-gradient(90deg,#0891b2,#22d3ee)" },
];

// TTA response time bucket
const TTA_RESPONSE = [
  { bucket: "< 1m",   count: 24, color: "#34d399" },
  { bucket: "1-3m",   count: 18, color: "#60a5fa" },
  { bucket: "3-5m",   count: 9,  color: "#fbbf24" },
  { bucket: "5-10m",  count: 5,  color: "#fb923c" },
  { bucket: "> 10m",  count: 2,  color: "#f87171" },
];
const TTA_TOTAL = TTA_RESPONSE.reduce((s, r) => s + r.count, 0);

// ── Utilities ────────────────────────────────────────────────────────

function cn(...classes: (string | boolean | undefined | null)[]) {
  return classes.filter(Boolean).join(" ");
}
function formatPhone(phone: string): string {
  const raw = phone.replace("whatsapp:", "").replace("+", "");
  if (raw.startsWith("91") && raw.length === 12) return `+91 ${raw.slice(2, 7)} ${raw.slice(7)}`;
  return `+${raw}`;
}
function maskPhone(phone: string): string {
  const raw = phone.replace("whatsapp:", "").replace("+", "");
  if (raw.startsWith("91") && raw.length === 12) return `+91 ••••• ${raw.slice(9)}`;
  return `+••••${raw.slice(-4)}`;
}
function getAvatarText(phone: string): string {
  const raw = phone.replace("whatsapp:", "").replace("+", "");
  return raw.slice(-4, -2);
}
function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}
function relativeTime(dateStr: string): string {
  if (!dateStr) return "";
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}
function formatDuration(s: number): string {
  return `${Math.floor(s / 60).toString().padStart(2, "0")}:${(s % 60).toString().padStart(2, "0")}`;
}
function formatTimestamp(ts: string): string {
  if (!ts) return "";
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
function avatarColor(phone: string): string {
  const colors = ["bg-violet-500","bg-sky-500","bg-amber-500","bg-rose-500","bg-teal-500","bg-indigo-500","bg-orange-500","bg-cyan-500"];
  let hash = 0;
  for (const c of phone) hash = (hash * 31 + c.charCodeAt(0)) & 0xffff;
  return colors[hash % colors.length];
}
function wordRotation(word: string): number {
  let hash = 0;
  for (const c of word) hash = (hash * 31 + c.charCodeAt(0)) & 0xffff;
  return ([-12, -8, -5, -3, 0, 0, 0, 3, 5, 8, 12])[hash % 11];
}
function wordSize(weight: number): string {
  if (weight >= 10) return "text-[2.1rem] font-black";
  if (weight >= 8)  return "text-[1.55rem] font-extrabold";
  if (weight >= 6)  return "text-[1.2rem] font-bold";
  if (weight >= 4)  return "text-[0.95rem] font-semibold";
  return "text-[0.78rem] font-medium";
}

// ── Chime Sound (Web Audio API) ──────────────────────────────────────

function playIncomingChime() {
  try {
    const Ctx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    const now = ctx.currentTime;
    const notes = [
      { freq: 880,  start: 0.0, dur: 0.18 },
      { freq: 1320, start: 0.18, dur: 0.22 },
      { freq: 880,  start: 0.55, dur: 0.18 },
      { freq: 1320, start: 0.73, dur: 0.22 },
    ];
    for (const n of notes) {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = n.freq;
      osc.connect(gain);
      gain.connect(ctx.destination);
      gain.gain.setValueAtTime(0.0001, now + n.start);
      gain.gain.exponentialRampToValueAtTime(0.22, now + n.start + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + n.start + n.dur);
      osc.start(now + n.start);
      osc.stop(now + n.start + n.dur + 0.02);
    }
    setTimeout(() => ctx.close().catch(() => {}), 1300);
  } catch { /* ignore */ }
}

// ── Types ────────────────────────────────────────────────────────────

interface User {
  phone: string;
  phone_display: string;
  name?: string | null;
  language: string;
  user_segment: string | null;
  active_intent: string | null;
  handoff_state: string;
  is_tta: boolean;
  message_count: number;
  last_message: { role: string; content: string; timestamp: string } | null;
  has_plan: boolean;
  updated_at: string;
}
interface Message {
  role: string; content: string; timestamp: string;
  media_url?: string; media_type?: "voice" | "file" | null; audio_url?: string;
}
interface Summary {
  summary: string;
  talking_points: string[];
  sentiment: string;
  goal_info: {
    collected: Record<string, unknown>;
    plan_generated: boolean;
    plan_summary: { goal_name: string; sip_required: number; tenure_years: number; risk_label: string; future_value: number } | null;
  };
}

// ── Skeletons ────────────────────────────────────────────────────────

function SkeletonBlock({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} />;
}
function UserListSkeleton() {
  return (
    <div className="space-y-px px-2">
      {[...Array(5)].map((_, i) => (
        <div key={i} className="flex items-center gap-3 px-3 py-3 rounded-xl">
          <SkeletonBlock className="w-10 h-10 rounded-full shrink-0" />
          <div className="flex-1 space-y-2">
            <div className="flex justify-between items-center">
              <SkeletonBlock className="h-3 w-28" /><SkeletonBlock className="h-2.5 w-10" />
            </div>
            <SkeletonBlock className="h-2.5 w-40" />
          </div>
        </div>
      ))}
    </div>
  );
}
function ChatSkeleton() {
  return (
    <div className="flex-1 px-6 py-5 space-y-4 overflow-hidden">
      {[false, true, false, false, true].map((isBot, i) => (
        <div key={i} className={cn("flex", isBot ? "justify-end" : "justify-start")}>
          <SkeletonBlock className={cn("rounded-2xl", i===0?"w-56 h-14":i===2?"w-72 h-20":i===4?"w-48 h-12":"w-64 h-16", isBot?"rounded-tr-sm":"rounded-tl-sm")} />
        </div>
      ))}
    </div>
  );
}
function SummarySkeleton() {
  return (
    <div className="p-5 space-y-6">
      <div className="space-y-2.5">
        <SkeletonBlock className="h-3 w-16" /><SkeletonBlock className="h-4 w-full" />
        <SkeletonBlock className="h-4 w-11/12" /><SkeletonBlock className="h-4 w-4/5" />
      </div>
      <div className="space-y-2"><SkeletonBlock className="h-3 w-20" /><SkeletonBlock className="h-7 w-24 rounded-full" /></div>
      <div className="space-y-2.5">
        <SkeletonBlock className="h-3 w-28" />
        {[1,2,3].map(j=>(
          <div key={j} className="flex items-center gap-2">
            <SkeletonBlock className="w-1.5 h-1.5 rounded-full shrink-0" />
            <SkeletonBlock className={cn("h-3.5", j===2?"w-3/5":j===1?"w-full":"w-4/5")} />
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Sentiment Badge ──────────────────────────────────────────────────

function SentimentBadge({ sentiment }: { sentiment: string }) {
  if (sentiment === "positive") return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-emerald-50 text-emerald-700 text-xs font-semibold rounded-full border border-emerald-200">
      <SmilePlus className="w-3.5 h-3.5" /> Positive
    </span>
  );
  if (sentiment === "frustrated" || sentiment === "negative") return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-red-50 text-red-700 text-xs font-semibold rounded-full border border-red-200">
      <Frown className="w-3.5 h-3.5" /> Frustrated
    </span>
  );
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-slate-100 text-slate-600 text-xs font-semibold rounded-full border border-slate-200">
      <Meh className="w-3.5 h-3.5" /> Neutral
    </span>
  );
}

// ── KPI Card ─────────────────────────────────────────────────────────

interface KpiCardProps {
  label: string; value: string | number; icon: React.ReactNode;
  accentGrad: string; glowColor: string; sub?: string; urgent?: boolean;
  trend?: number; // percentage change
}
function KpiCard({ label, value, icon, accentGrad, glowColor, sub, urgent, trend }: KpiCardProps) {
  const trendUp = trend !== undefined && trend >= 0;
  return (
    <div className="card-lift relative overflow-hidden rounded-2xl bg-white border border-slate-100 p-5"
      style={{ boxShadow: `0 4px 24px rgba(0,0,0,0.07), 0 1px 4px rgba(0,0,0,0.04)` }}>
      <div className="absolute top-0 left-0 right-0 h-[3px] rounded-t-2xl" style={{ background: accentGrad }} />
      <div className="absolute -top-6 -right-6 w-24 h-24 rounded-full blur-2xl opacity-20 pointer-events-none"
        style={{ background: glowColor }} />
      {urgent && <div className="absolute top-3.5 right-3.5 w-2 h-2 rounded-full bg-red-500 pulse-urgent" />}
      <div className="flex items-start justify-between mb-4">
        <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0"
          style={{ background: glowColor.replace("0.3","0.12") }}>
          {icon}
        </div>
        {trend !== undefined && (
          <div className={cn("inline-flex items-center gap-0.5 text-[10px] font-bold px-1.5 py-0.5 rounded-md",
            trendUp ? "text-emerald-600 bg-emerald-50" : "text-red-500 bg-red-50")}>
            {trendUp ? <TrendingUp className="w-2.5 h-2.5" /> : <TrendingDown className="w-2.5 h-2.5" />}
            {Math.abs(trend)}%
          </div>
        )}
      </div>
      <div className={cn("text-[2rem] font-black leading-none tracking-tight mb-1", urgent ? "text-red-600" : "text-slate-900")}>
        {value}
      </div>
      <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">{label}</div>
      {sub && <div className="text-[10px] text-slate-400 mt-0.5">{sub}</div>}
    </div>
  );
}

// ── Sentiment Bar ────────────────────────────────────────────────────

function SentimentBar({ label, pct, grad, textColor, icon }: {
  label: string; pct: number; grad: string; textColor: string; icon: React.ReactNode;
}) {
  return (
    <div className="group">
      <div className="flex items-center justify-between mb-2">
        <div className={cn("flex items-center gap-2 text-[13px] font-semibold", textColor)}>
          {icon} {label}
        </div>
        <span className="text-sm font-black text-slate-700 tabular-nums">{pct}%</span>
      </div>
      <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
        <div className="h-full rounded-full bar-fill" style={{ background: grad, width: `${pct}%` }} />
      </div>
    </div>
  );
}

// ── SVG Line Chart (Chat Volume) ─────────────────────────────────────

function LineChart({ data }: { data: typeof CHAT_VOLUME_7D }) {
  const W = 520, H = 200, PAD = { l: 36, r: 16, t: 16, b: 28 };
  const maxVal = Math.max(...data.map(d => d.total)) * 1.15;
  const xStep = (W - PAD.l - PAD.r) / (data.length - 1);
  const yScale = (v: number) => PAD.t + (H - PAD.t - PAD.b) * (1 - v / maxVal);
  const xPos = (i: number) => PAD.l + xStep * i;

  const totalPath = data.map((d, i) => `${i === 0 ? "M" : "L"}${xPos(i).toFixed(1)},${yScale(d.total).toFixed(1)}`).join(" ");
  const plansPath = data.map((d, i) => `${i === 0 ? "M" : "L"}${xPos(i).toFixed(1)},${yScale(d.plans).toFixed(1)}`).join(" ");
  const totalFill = `${totalPath} L${xPos(data.length - 1)},${H - PAD.b} L${xPos(0)},${H - PAD.b} Z`;

  const yTicks = [0, Math.round(maxVal * 0.5), Math.round(maxVal)];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-full">
      <defs>
        <linearGradient id="lineFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor="#60a5fa" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#60a5fa" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="lineStroke" x1="0" x2="1">
          <stop offset="0%"   stopColor="#2563eb" />
          <stop offset="100%" stopColor="#60a5fa" />
        </linearGradient>
        <linearGradient id="plansStroke" x1="0" x2="1">
          <stop offset="0%"   stopColor="#059669" />
          <stop offset="100%" stopColor="#34d399" />
        </linearGradient>
      </defs>
      {/* y grid */}
      {yTicks.map((t, i) => (
        <g key={i}>
          <line x1={PAD.l} x2={W - PAD.r} y1={yScale(t)} y2={yScale(t)} stroke="#e2e8f0" strokeDasharray="3 3" />
          <text x={PAD.l - 8} y={yScale(t) + 3} fontSize="10" fill="#94a3b8" textAnchor="end">{t}</text>
        </g>
      ))}
      {/* total fill */}
      <path d={totalFill} fill="url(#lineFill)" />
      {/* total line */}
      <path d={totalPath} fill="none" stroke="url(#lineStroke)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="chart-line" />
      {/* plans line (dashed) */}
      <path d={plansPath} fill="none" stroke="url(#plansStroke)" strokeWidth="2" strokeLinecap="round" strokeDasharray="4 4" className="chart-line" />
      {/* points */}
      {data.map((d, i) => (
        <g key={i}>
          <circle cx={xPos(i)} cy={yScale(d.total)} r="3.5" fill="#2563eb" stroke="#fff" strokeWidth="2" />
          <circle cx={xPos(i)} cy={yScale(d.plans)} r="2.5" fill="#059669" />
          <text x={xPos(i)} y={H - 8} fontSize="10" fill="#94a3b8" textAnchor="middle" fontWeight="600">{d.day}</text>
        </g>
      ))}
      {/* active point */}
      <circle cx={xPos(data.length - 1)} cy={yScale(data[data.length - 1].total)} r="5" fill="#2563eb" className="spark-point-active" style={{ transformOrigin: `${xPos(data.length - 1)}px ${yScale(data[data.length - 1].total)}px` }} />
    </svg>
  );
}

// ── SVG Donut Chart (Language Mix) ───────────────────────────────────

function DonutChart({ data, total }: { data: typeof LANGUAGE_DATA; total: number }) {
  const R = 56, STROKE = 22;
  const CIRC = 2 * Math.PI * R;
  let offset = 0;
  const segments = data.map((d) => {
    const len = (d.pct / 100) * CIRC;
    const seg = { ...d, offset, len, gap: CIRC - len };
    offset += len;
    return seg;
  });

  return (
    <div className="flex items-center gap-5">
      <div className="relative w-[160px] h-[160px] shrink-0">
        <svg viewBox="0 0 160 160" className="w-full h-full -rotate-90">
          <circle cx="80" cy="80" r={R} fill="none" stroke="#f1f5f9" strokeWidth={STROKE} />
          {segments.map((s, i) => (
            <circle
              key={i}
              cx="80" cy="80" r={R}
              fill="none"
              stroke={s.color}
              strokeWidth={STROKE}
              strokeDasharray={`${s.len} ${s.gap}`}
              strokeDashoffset={-s.offset}
              strokeLinecap="butt"
              style={{ filter: `drop-shadow(0 0 6px ${s.glow})` }}
            />
          ))}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <div className="text-[22px] font-black text-slate-800 tabular-nums leading-none">{total}</div>
          <div className="text-[9px] text-slate-400 font-semibold uppercase tracking-widest mt-0.5">Sessions</div>
        </div>
      </div>
      <div className="flex-1 space-y-2.5">
        {data.map(d => (
          <div key={d.lang} className="flex items-center gap-2.5">
            <div className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: d.color, boxShadow: `0 0 6px ${d.glow}` }} />
            <span className="text-[12px] font-semibold text-slate-700 flex-1">{d.lang}</span>
            <span className="text-[12px] font-black text-slate-800 tabular-nums">{d.pct}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── SVG Activity Heatmap ─────────────────────────────────────────────

function Heatmap() {
  const cellSize = 14, gap = 2;
  const width = 24 * (cellSize + gap);
  const height = 7 * (cellSize + gap);

  function colorFor(value: number): string {
    const t = value / HEATMAP_MAX;
    if (t === 0) return "#eef2ff";
    if (t < 0.2) return "#c7d2fe";
    if (t < 0.4) return "#a5b4fc";
    if (t < 0.6) return "#818cf8";
    if (t < 0.8) return "#6366f1";
    return "#4f46e5";
  }

  return (
    <div className="flex gap-2 items-start">
      <div className="flex flex-col gap-[2px] pt-px">
        {HEATMAP_DAYS.map((d) => (
          <div key={d} className="text-[9px] font-semibold text-slate-400 uppercase tracking-wider h-[14px] flex items-center">
            {d}
          </div>
        ))}
      </div>
      <div className="flex-1">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full" preserveAspectRatio="none">
          {HEATMAP.map((row, rIdx) =>
            row.map((val, cIdx) => {
              const tooltip = HEATMAP_DAYS[rIdx] + " " + cIdx + ":00 — " + val + " chats";
              return (
                <rect
                  key={`${rIdx}-${cIdx}`}
                  x={cIdx * (cellSize + gap)}
                  y={rIdx * (cellSize + gap)}
                  width={cellSize}
                  height={cellSize}
                  rx={3}
                  fill={colorFor(val)}
                  className="heatmap-cell"
                  style={{ animationDelay: `${(rIdx * 24 + cIdx) * 4}ms` }}
                >
                  <title>{tooltip}</title>
                </rect>
              );
            })
          )}
        </svg>
        <div className="flex justify-between mt-1 text-[9px] text-slate-400 font-mono">
          <span>12a</span><span>6a</span><span>12p</span><span>6p</span><span>11p</span>
        </div>
      </div>
    </div>
  );
}

// ── Radial Progress Ring ─────────────────────────────────────────────

function RadialProgress({ pct, color, glow, label, value, sub }: {
  pct: number; color: string; glow: string; label: string; value: string; sub?: string;
}) {
  const R = 38, STROKE = 8;
  const CIRC = 2 * Math.PI * R;
  const dashEnd = CIRC * (1 - pct / 100);
  return (
    <div className="flex items-center gap-4">
      <div className="relative w-[100px] h-[100px] shrink-0">
        <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
          <circle cx="50" cy="50" r={R} fill="none" stroke="#f1f5f9" strokeWidth={STROKE} />
          <circle cx="50" cy="50" r={R} fill="none" stroke={color} strokeWidth={STROKE}
            strokeLinecap="round"
            strokeDasharray={CIRC}
            strokeDashoffset={dashEnd}
            className="ring-fill-arc"
            style={{ filter: `drop-shadow(0 0 8px ${glow})`, "--ring-len": CIRC, "--ring-end": dashEnd } as React.CSSProperties}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <div className="text-[20px] font-black text-slate-800 tabular-nums leading-none">{value}</div>
          {sub && <div className="text-[9px] text-slate-400 font-semibold mt-0.5">{sub}</div>}
        </div>
      </div>
      <div className="min-w-0">
        <p className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">{label}</p>
        <p className="text-[10px] text-slate-400 mt-0.5">{pct}% of target</p>
      </div>
    </div>
  );
}

// ── TTA Response Distribution (Stacked Bar) ──────────────────────────

function TtaResponseDistribution() {
  return (
    <div>
      <div className="flex h-9 rounded-xl overflow-hidden border border-slate-100">
        {TTA_RESPONSE.map((r) => {
          const pct = (r.count / TTA_TOTAL) * 100;
          return (
            <div key={r.bucket} className="relative group" style={{ width: `${pct}%`, background: r.color }}>
              <div className="absolute inset-0 flex items-center justify-center text-[10px] font-black text-white opacity-90">
                {r.count}
              </div>
            </div>
          );
        })}
      </div>
      <div className="flex justify-between mt-2">
        {TTA_RESPONSE.map((r) => (
          <div key={r.bucket} className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-full" style={{ background: r.color }} />
            <span className="text-[10px] font-semibold text-slate-500">{r.bucket}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Home Dashboard ────────────────────────────────────────────────────

function HomeDashboard({ users, onSelectUser }: { users: User[]; onSelectUser: (phone: string) => void }) {
  const stats = useMemo(() => {
    const realActive = users.filter(u => u.updated_at && Date.now() - new Date(u.updated_at).getTime() < 3600000).length;
    const realTta = users.filter(u => u.is_tta).length;
    const realPlans = users.filter(u => u.has_plan).length;
    const total = users.length + DEMO_STATS.totalToday;
    const activeNow = realActive + DEMO_STATS.activeNow;
    const tta = realTta + (realTta > 0 ? 0 : DEMO_STATS.ttaQueueBase);
    return { total, activeNow, tta, plans: realPlans + DEMO_STATS.plansGenerated, conversion: DEMO_STATS.conversionPct };
  }, [users]);

  const recentUsers = useMemo(
    () => [...users].sort((a,b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()).slice(0, 6),
    [users]
  );

  const today = new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const weekTotal = CHAT_VOLUME_7D.reduce((s, d) => s + d.total, 0);

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-5" style={{ background: "#f4f6fb" }}>

      {/* ── Hero Header ─────────────────────────────────────────── */}
      <div className="relative overflow-hidden rounded-2xl p-6"
        style={{ background: "linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%)" }}>
        <div className="orb-float absolute -top-12 -left-12 w-48 h-48 rounded-full pointer-events-none"
          style={{ background: "radial-gradient(circle, rgba(16,185,129,0.25) 0%, transparent 70%)" }} />
        <div className="orb-float-delay absolute -bottom-10 right-16 w-36 h-36 rounded-full pointer-events-none"
          style={{ background: "radial-gradient(circle, rgba(139,92,246,0.3) 0%, transparent 70%)" }} />
        <div className="absolute top-6 right-32 w-20 h-20 rounded-full pointer-events-none"
          style={{ background: "radial-gradient(circle, rgba(56,189,248,0.15) 0%, transparent 70%)" }} />

        <div className="relative flex items-center justify-between">
          <div>
            <p className="text-slate-500 text-[11px] font-bold uppercase tracking-widest mb-1">{today}</p>
            <h1 className="text-[1.9rem] font-black text-white tracking-tight leading-tight">Command Center</h1>
            <p className="text-slate-400 text-sm mt-1">FundsIndia WhatsApp Advisory Platform</p>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right hidden md:block">
              <div className="text-3xl font-black text-white tabular-nums">{stats.activeNow}</div>
              <div className="text-xs text-slate-400 mt-0.5">active now</div>
            </div>
            <div className="w-px h-12 bg-white/10" />
            <div className="text-right hidden md:block">
              <div className="text-3xl font-black text-white tabular-nums">{stats.total}</div>
              <div className="text-xs text-slate-400 mt-0.5">total today</div>
            </div>
            <div className="w-px h-12 bg-white/10" />
            <div className="text-right hidden lg:block">
              <div className="text-3xl font-black text-white tabular-nums">{DEMO_STATS.avgResponseMin}m</div>
              <div className="text-xs text-slate-400 mt-0.5">avg response</div>
            </div>
            <div className="flex items-center gap-2 ml-2 px-4 py-2 rounded-full border"
              style={{ background: "rgba(16,185,129,0.15)", borderColor: "rgba(16,185,129,0.35)" }}>
              <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-[11px] font-bold text-emerald-300 uppercase tracking-widest">Live</span>
            </div>
          </div>
        </div>
      </div>

      {/* ── KPI Row ─────────────────────────────────────────────── */}
      <div className="grid grid-cols-4 gap-4">
        <KpiCard label="Conversations Today" value={stats.total}
          icon={<MessageSquare className="w-5 h-5" style={{ color: "#60a5fa" }} />}
          accentGrad="linear-gradient(90deg,#2563eb,#60a5fa)"
          glowColor="rgba(37,99,235,0.3)"
          sub="all sessions" trend={12}
        />
        <KpiCard label="Active Now" value={stats.activeNow}
          icon={<Activity className="w-5 h-5" style={{ color: "#34d399" }} />}
          accentGrad="linear-gradient(90deg,#059669,#34d399)"
          glowColor="rgba(5,150,105,0.3)"
          sub="last hour" trend={8}
        />
        <KpiCard label="TTA Queue" value={stats.tta}
          icon={<Bell className="w-5 h-5" style={{ color: stats.tta > 0 ? "#f87171" : "#94a3b8" }} />}
          accentGrad={stats.tta > 0 ? "linear-gradient(90deg,#dc2626,#fb7185)" : "linear-gradient(90deg,#94a3b8,#cbd5e1)"}
          glowColor="rgba(220,38,38,0.3)"
          sub="awaiting advisor"
          urgent={stats.tta > 0}
        />
        <KpiCard label="Conversion Rate" value={`${stats.conversion}%`}
          icon={<TrendingUp className="w-5 h-5" style={{ color: "#a78bfa" }} />}
          accentGrad="linear-gradient(90deg,#7c3aed,#a78bfa)"
          glowColor="rgba(124,58,237,0.3)"
          sub={`${stats.plans} plans`} trend={5}
        />
      </div>

      {/* ── Row 2: Line chart + Donut + Radial progress ───────── */}
      <div className="grid grid-cols-6 gap-4">

        {/* Line Chart — spans 3 */}
        <div className="col-span-3 rounded-2xl bg-white p-5 border border-slate-100"
          style={{ boxShadow: "0 4px 24px rgba(0,0,0,0.06)" }}>
          <div className="flex items-start justify-between mb-2">
            <div>
              <h3 className="text-[14px] font-bold text-slate-800 flex items-center gap-2">
                <Activity className="w-4 h-4 text-blue-500" /> Weekly Activity
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">Total vs Plans generated · last 7 days</p>
            </div>
            <div className="flex gap-4">
              <Legend label="Total" color="#2563eb" />
              <Legend label="Plans" color="#059669" dashed />
            </div>
          </div>
          <div className="flex items-baseline gap-3 mb-1">
            <span className="text-[1.9rem] font-black text-slate-800 tabular-nums leading-none">{weekTotal}</span>
            <span className="inline-flex items-center gap-1 text-[11px] text-emerald-600 font-bold">
              <TrendingUp className="w-3 h-3" /> +18.4% vs last week
            </span>
          </div>
          <div className="h-[200px]">
            <LineChart data={CHAT_VOLUME_7D} />
          </div>
        </div>

        {/* Donut — spans 2 */}
        <div className="col-span-2 rounded-2xl bg-white p-5 border border-slate-100"
          style={{ boxShadow: "0 4px 24px rgba(0,0,0,0.06)" }}>
          <div className="mb-4">
            <h3 className="text-[14px] font-bold text-slate-800 flex items-center gap-2">
              <Globe2 className="w-4 h-4 text-pink-500" /> Language Mix
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">User preferences</p>
          </div>
          <DonutChart data={LANGUAGE_DATA} total={stats.total} />
        </div>

        {/* Radial progress — spans 1 */}
        <div className="col-span-1 rounded-2xl p-5 relative overflow-hidden"
          style={{ background: "linear-gradient(135deg,#0f172a,#1e1b4b)", boxShadow: "0 4px 24px rgba(0,0,0,0.12)" }}>
          <div className="absolute inset-0 dot-grid opacity-30 pointer-events-none" />
          <div className="relative">
            <p className="text-[10px] font-bold uppercase tracking-widest text-emerald-300/70 mb-3">Target</p>
            <RadialProgress pct={72} color="#34d399" glow="rgba(52,211,153,0.4)"
              label="Daily goal" value="72%" sub="target 175" />
          </div>
        </div>
      </div>

      {/* ── Row 3: Word Cloud + Sentiment + Funnel ─────────── */}
      <div className="grid grid-cols-6 gap-4">
        {/* Word Cloud */}
        <div className="col-span-3 rounded-2xl overflow-hidden relative"
          style={{ background: "linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%)", boxShadow: "0 8px 32px rgba(0,0,0,0.18)" }}>
          <div className="absolute inset-0 dot-grid pointer-events-none opacity-60" />
          <div className="relative p-5">
            <div className="flex items-center justify-between mb-5">
              <div>
                <h3 className="text-[15px] font-bold text-white">What Users Are Asking</h3>
                <p className="text-xs text-slate-500 mt-0.5">Topic frequency from all conversations</p>
              </div>
              <span className="text-[10px] px-2.5 py-1 font-bold rounded-full uppercase tracking-widest"
                style={{ background: "rgba(139,92,246,0.2)", color: "#a78bfa", border: "1px solid rgba(139,92,246,0.3)" }}>
                Word Cloud
              </span>
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-3 items-center justify-center min-h-[220px] py-3 px-2">
              {WORD_CLOUD_DATA.map(({ word, weight, color }) => (
                <span key={word} className={cn("word-tag leading-none select-none", wordSize(weight))}
                  style={{
                    color,
                    transform: `rotate(${wordRotation(word)}deg)`,
                    opacity: 0.55 + weight * 0.045,
                    textShadow: `0 0 20px ${color}55`,
                    paddingTop: "2px", paddingBottom: "2px",
                  }}>
                  {word}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Right column */}
        <div className="col-span-3 space-y-4 flex flex-col">

          {/* Sentiment */}
          <div className="rounded-2xl bg-white p-5 border border-slate-100"
            style={{ boxShadow: "0 4px 24px rgba(0,0,0,0.06)" }}>
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-[14px] font-bold text-slate-800 flex items-center gap-2">
                <SmilePlus className="w-4 h-4 text-emerald-500" /> Overall Sentiment
              </h3>
              <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">Today</span>
            </div>
            <p className="text-xs text-slate-400 mb-4">Across all active conversations</p>
            <div className="space-y-4">
              <SentimentBar label="Positive" pct={48}
                grad="linear-gradient(90deg,#059669,#34d399)"
                textColor="text-emerald-600"
                icon={<SmilePlus className="w-3.5 h-3.5" />} />
              <SentimentBar label="Neutral" pct={31}
                grad="linear-gradient(90deg,#475569,#94a3b8)"
                textColor="text-slate-500"
                icon={<Meh className="w-3.5 h-3.5" />} />
              <SentimentBar label="Frustrated" pct={21}
                grad="linear-gradient(90deg,#dc2626,#fb7185)"
                textColor="text-red-500"
                icon={<Frown className="w-3.5 h-3.5" />} />
            </div>
          </div>

          {/* Funnel */}
          <div className="rounded-2xl bg-white p-5 border border-slate-100 flex-1"
            style={{ boxShadow: "0 4px 24px rgba(0,0,0,0.06)" }}>
            <h3 className="text-[14px] font-bold text-slate-800 flex items-center gap-2">
              <Target className="w-4 h-4 text-violet-500" /> Conversion Funnel
            </h3>
            <p className="text-xs text-slate-400 mb-4">User journey stages</p>
            <div className="space-y-3">
              {FUNNEL_DATA.map(({ stage, pct, grad }) => (
                <div key={stage}>
                  <div className="flex justify-between items-center mb-1.5">
                    <span className="text-[12px] text-slate-600 truncate pr-2">{stage}</span>
                    <span className="text-[12px] font-black text-slate-700 shrink-0 tabular-nums">{pct}%</span>
                  </div>
                  <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full rounded-full bar-fill" style={{ background: grad, width: `${pct}%` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ── Row 4: Heatmap + TTA response + Top Funds ───────── */}
      <div className="grid grid-cols-6 gap-4">
        {/* Heatmap — spans 3 */}
        <div className="col-span-3 rounded-2xl bg-white p-5 border border-slate-100"
          style={{ boxShadow: "0 4px 24px rgba(0,0,0,0.06)" }}>
          <div className="flex items-start justify-between mb-4">
            <div>
              <h3 className="text-[14px] font-bold text-slate-800 flex items-center gap-2">
                <Timer className="w-4 h-4 text-indigo-500" /> Activity Heatmap
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">Chat volume by day × hour</p>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-slate-400 font-semibold">Less</span>
              {["#eef2ff", "#c7d2fe", "#818cf8", "#6366f1", "#4f46e5"].map((c) => (
                <div key={c} className="w-2.5 h-2.5 rounded-sm" style={{ background: c }} />
              ))}
              <span className="text-[10px] text-slate-400 font-semibold">More</span>
            </div>
          </div>
          <Heatmap />
        </div>

        {/* TTA response distribution + KPI — spans 3 */}
        <div className="col-span-3 grid grid-cols-1 gap-4">
          <div className="rounded-2xl bg-white p-5 border border-slate-100"
            style={{ boxShadow: "0 4px 24px rgba(0,0,0,0.06)" }}>
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-[14px] font-bold text-slate-800 flex items-center gap-2">
                <Zap className="w-4 h-4 text-amber-500" /> TTA Response Times
              </h3>
              <span className="text-[10px] font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full uppercase tracking-widest">
                {DEMO_STATS.avgResponseMin}m avg
              </span>
            </div>
            <p className="text-xs text-slate-400 mb-4">How fast advisors respond to TTA requests</p>
            <TtaResponseDistribution />
          </div>

          {/* Mini KPI row */}
          <div className="grid grid-cols-2 gap-4">
            <MiniKpi icon={<PhoneCall className="w-4 h-4" />} label="Calls today" value={DEMO_STATS.callsToday.toString()} accent="#34d399" glow="rgba(52,211,153,0.15)" />
            <MiniKpi icon={<Timer className="w-4 h-4" />} label="Avg call time" value={`${DEMO_STATS.avgCallMin}m`} accent="#60a5fa" glow="rgba(96,165,250,0.15)" />
          </div>
        </div>
      </div>

      {/* ── Row 5: Top Funds + Intents + Pain Points ───────── */}
      <div className="grid grid-cols-3 gap-4">
        {/* Top Funds */}
        <div className="rounded-2xl bg-white p-5 border border-slate-100"
          style={{ boxShadow: "0 4px 24px rgba(0,0,0,0.06)" }}>
          <div className="flex items-center gap-2 mb-4">
            <IndianRupee className="w-4 h-4 text-emerald-500" />
            <h3 className="text-[14px] font-bold text-slate-800">Most-Asked Funds</h3>
          </div>
          <div className="space-y-3">
            {TOP_FUNDS.map(({ fund, queries, grad }, idx) => {
              const maxQ = TOP_FUNDS[0].queries;
              const pct = (queries / maxQ) * 100;
              return (
                <div key={fund}>
                  <div className="flex justify-between items-center mb-1.5 gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-[10px] font-bold text-slate-400 w-4 shrink-0">#{idx + 1}</span>
                      <span className="text-[12px] text-slate-600 truncate">{fund}</span>
                    </div>
                    <span className="text-[11px] font-black text-slate-700 tabular-nums shrink-0">{queries}</span>
                  </div>
                  <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full rounded-full bar-fill"
                      style={{ background: grad, width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Top Intents */}
        <div className="rounded-2xl bg-white p-5 border border-slate-100"
          style={{ boxShadow: "0 4px 24px rgba(0,0,0,0.06)" }}>
          <div className="flex items-center gap-2 mb-4">
            <BarChart2 className="w-4 h-4 text-violet-500" />
            <h3 className="text-[14px] font-bold text-slate-800">Top Intents</h3>
          </div>
          <div className="space-y-3">
            {INTENT_DATA.map(({ intent, pct, grad, glow }) => (
              <div key={intent}>
                <div className="flex justify-between items-center mb-1.5">
                  <span className="text-[12px] text-slate-600">{intent}</span>
                  <span className="text-[12px] font-black text-slate-700 tabular-nums">{pct}%</span>
                </div>
                <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full rounded-full bar-fill"
                    style={{ background: grad, width: `${pct}%`, boxShadow: `0 0 8px ${glow}` }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Pain Points */}
        <div className="rounded-2xl bg-white p-5 border border-slate-100"
          style={{ boxShadow: "0 4px 24px rgba(0,0,0,0.06)" }}>
          <div className="flex items-center gap-2 mb-4">
            <TrendingDown className="w-4 h-4 text-red-500" />
            <h3 className="text-[14px] font-bold text-slate-800">What Users Dislike</h3>
          </div>
          <div className="space-y-3.5">
            {PAIN_POINTS_DATA.map(({ label, count, pct }, idx) => (
              <div key={label} className="flex items-start gap-3">
                <div className="w-6 h-6 rounded-lg flex items-center justify-center shrink-0 mt-0.5 text-[10px] font-black text-rose-600"
                  style={{ background: "rgba(244,63,94,0.1)" }}>
                  {idx + 1}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex justify-between items-center mb-1.5">
                    <span className="text-[11px] text-slate-600 truncate pr-2">{label}</span>
                    <span className="text-[11px] font-black text-red-500 shrink-0">{count}</span>
                  </div>
                  <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full rounded-full bar-fill"
                      style={{ background: "linear-gradient(90deg,#e11d48,#fb7185)", width: `${pct}%`, boxShadow: "0 0 6px rgba(225,29,72,0.3)" }} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Recent Conversations (RM-assigned only) ────────────── */}
      <div className="rounded-2xl bg-white border border-slate-100 overflow-hidden"
        style={{ boxShadow: "0 4px 24px rgba(0,0,0,0.06)" }}>
        <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between"
          style={{ background: "linear-gradient(90deg,#f8faff,#ffffff)" }}>
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center"
              style={{ background: "rgba(99,102,241,0.1)" }}>
              <Users className="w-3.5 h-3.5 text-indigo-500" />
            </div>
            <h3 className="text-[14px] font-bold text-slate-800">My Recent Conversations</h3>
          </div>
          <span className="text-xs font-semibold text-slate-400 px-2.5 py-1 bg-slate-100 rounded-full">{users.length} assigned</span>
        </div>
        {recentUsers.length === 0 ? (
          <div className="py-12 text-center text-slate-400 text-sm">No active conversations assigned to you yet.</div>
        ) : (
          <div className="divide-y divide-slate-50">
            {recentUsers.map((user) => (
              <button
                key={user.phone}
                onClick={() => onSelectUser(user.phone)}
                className="conv-row w-full flex items-center gap-4 px-5 py-4 text-left"
                style={{ paddingLeft: "20px" }}
              >
                <div className={cn("w-10 h-10 rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0 relative", avatarColor(user.phone))}
                  style={{ boxShadow: "0 2px 8px rgba(0,0,0,0.15)" }}>
                  {user.name ? getInitials(user.name) : getAvatarText(user.phone)}
                  {user.is_tta && (
                    <div className="absolute -top-0.5 -right-0.5 w-3.5 h-3.5 rounded-full bg-red-500 border-2 border-white pulse-urgent" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-[13px] font-bold text-slate-800 truncate">
                      {user.name || formatPhone(user.phone)}
                    </span>
                    {user.is_tta && (
                      <span className="flex items-center gap-0.5 text-[9px] text-red-500 font-black px-1.5 py-0.5 bg-red-50 rounded-md shrink-0 uppercase tracking-wide">
                        <AlertCircle className="w-2.5 h-2.5" /> TTA
                      </span>
                    )}
                    {user.has_plan && (
                      <span className="text-[9px] text-emerald-600 font-black px-1.5 py-0.5 bg-emerald-50 rounded-md shrink-0 uppercase tracking-wide">
                        Plan
                      </span>
                    )}
                  </div>
                  {user.last_message && (
                    <p className="text-[11px] text-slate-400 truncate">
                      {user.last_message.role === "user" ? "↑ " : "↓ "}{user.last_message.content}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <div className="text-right">
                    <div className="text-[11px] text-slate-400 font-mono">{relativeTime(user.updated_at)}</div>
                    <div className="text-[10px] text-slate-300 capitalize mt-0.5">{user.user_segment || "new"}</div>
                  </div>
                  <ChevronRight className="conv-arrow w-4 h-4 text-slate-400" />
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Helper components ────────────────────────────────────────────────

function Legend({ label, color, dashed }: { label: string; color: string; dashed?: boolean }) {
  return (
    <div className="flex items-center gap-1.5">
      <div className="w-5 h-[2px] rounded-full" style={{
        background: color,
        borderTop: dashed ? `2px dashed ${color}` : "none",
        height: dashed ? 0 : 2,
      }} />
      <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide">{label}</span>
    </div>
  );
}

function MiniKpi({ icon, label, value, accent, glow }: { icon: React.ReactNode; label: string; value: string; accent: string; glow: string }) {
  return (
    <div className="card-lift rounded-2xl bg-white p-4 border border-slate-100 flex items-center gap-3"
      style={{ boxShadow: "0 4px 24px rgba(0,0,0,0.06)" }}>
      <div className="w-10 h-10 rounded-xl flex items-center justify-center shrink-0" style={{ background: glow, color: accent }}>
        {icon}
      </div>
      <div className="min-w-0">
        <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">{label}</div>
        <div className="text-xl font-black text-slate-800 tabular-nums mt-0.5">{value}</div>
      </div>
    </div>
  );
}

// ── Full-screen Incoming TTA Warning Modal ───────────────────────────

function IncomingTtaModal({ user, onAccept, onDismiss }: {
  user: User; onAccept: () => void; onDismiss: () => void;
}) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onDismiss();
      if (e.key === "Enter") onAccept();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onAccept, onDismiss]);

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-6">
      <div className="absolute inset-0 warn-backdrop" />

      {/* Edge pulse */}
      <div className="absolute inset-0 tta-alert-active pointer-events-none" />

      {/* Banner at top */}
      <div className="absolute top-0 left-0 right-0 incoming-banner">
        <div className="bg-gradient-to-r from-red-600 via-red-500 to-red-600 text-white py-2 px-6 flex items-center justify-center gap-3">
          <AlertTriangle className="w-4 h-4 animate-pulse" />
          <span className="text-sm font-black uppercase tracking-widest">Incoming Handoff Request</span>
          <AlertTriangle className="w-4 h-4 animate-pulse" />
        </div>
      </div>

      <div className="relative modal-scale w-full max-w-md rounded-3xl overflow-hidden"
        style={{ boxShadow: "0 32px 80px rgba(220,38,38,0.35), 0 8px 32px rgba(0,0,0,0.4)" }}>
        {/* Dark gradient hero */}
        <div className="relative px-8 pt-10 pb-8 overflow-hidden"
          style={{ background: "linear-gradient(135deg, #7f1d1d 0%, #1e1b4b 60%, #0f172a 100%)" }}>
          <div className="absolute inset-0 dot-grid opacity-30" />
          <div className="absolute -top-12 -right-12 w-48 h-48 rounded-full blur-2xl pointer-events-none"
            style={{ background: "radial-gradient(circle, rgba(239,68,68,0.35) 0%, transparent 70%)" }} />

          <div className="relative flex flex-col items-center">
            {/* Avatar with pulsing rings */}
            <div className="relative mb-5">
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div className="incoming-ring-1 absolute w-24 h-24 rounded-full border-2" />
                <div className="incoming-ring-2 absolute w-24 h-24 rounded-full border-2" />
                <div className="incoming-ring-3 absolute w-24 h-24 rounded-full border-2" />
              </div>
              <div className={cn("relative w-24 h-24 rounded-full flex items-center justify-center text-white text-2xl font-black", avatarColor(user.phone))}
                style={{ boxShadow: "0 0 40px rgba(239,68,68,0.4), 0 0 0 4px rgba(255,255,255,0.1)" }}>
                {user.name ? getInitials(user.name) : getAvatarText(user.phone)}
              </div>
              <div className="absolute -bottom-1 -right-1 w-8 h-8 rounded-full bg-red-500 border-[3px] border-slate-900 flex items-center justify-center">
                <PhoneMissed className="w-3.5 h-3.5 text-white" />
              </div>
            </div>

            {/* Identity */}
            <div className="text-white text-xl font-black mb-1">
              {user.name || formatPhone(user.phone)}
            </div>
            <div className="flex items-center gap-1.5 text-[11px] text-slate-400 font-mono tracking-widest mb-1">
              <ShieldCheck className="w-3 h-3 text-emerald-400" />
              {maskPhone(user.phone)}
            </div>
            <div className="flex items-center gap-2 mt-2">
              <span className="text-[10px] px-2.5 py-0.5 rounded-full font-bold capitalize"
                style={{ background: "rgba(239,68,68,0.15)", color: "#fca5a5", border: "1px solid rgba(239,68,68,0.3)" }}>
                {user.user_segment || "new"} user
              </span>
              {user.language && (
                <span className="text-[10px] px-2.5 py-0.5 rounded-full font-bold uppercase"
                  style={{ background: "rgba(255,255,255,0.08)", color: "#cbd5e1" }}>
                  {user.language}
                </span>
              )}
              <span className="inline-flex items-center gap-1 text-[10px] px-2.5 py-0.5 rounded-full font-bold"
                style={{ background: "rgba(251,191,36,0.15)", color: "#fbbf24", border: "1px solid rgba(251,191,36,0.3)" }}>
                <Volume2 className="w-2.5 h-2.5" />
                ringing
              </span>
            </div>
          </div>
        </div>

        {/* Body */}
        <div className="bg-white p-6 space-y-4">
          <div className="rounded-xl p-3.5 flex items-start gap-2.5" style={{ background: "#fef2f2", border: "1px solid #fecaca" }}>
            <MessageSquare className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
            <div className="min-w-0 flex-1">
              <p className="text-[10px] font-bold text-red-600 uppercase tracking-widest mb-1">Last message</p>
              <p className="text-[12px] text-slate-700 italic leading-snug">
                &ldquo;{user.last_message?.content ?? "Wants to talk to a human advisor"}&rdquo;
              </p>
            </div>
          </div>

          <div className="flex gap-2.5">
            <button onClick={onAccept}
              className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl text-white text-sm font-bold transition-all hover:brightness-110 active:scale-95"
              style={{ background: "linear-gradient(135deg,#059669,#047857)", boxShadow: "0 8px 24px rgba(5,150,105,0.4)" }}>
              <PhoneCall className="w-4 h-4" />
              Take call
            </button>
            <button onClick={onDismiss}
              className="px-4 py-3 rounded-xl text-slate-600 bg-slate-100 hover:bg-slate-200 text-sm font-semibold transition-colors">
              Snooze
            </button>
          </div>
          <p className="text-[10px] text-slate-400 text-center font-mono">
            <kbd className="px-1.5 py-0.5 bg-slate-100 rounded">Enter</kbd> accept · <kbd className="px-1.5 py-0.5 bg-slate-100 rounded">Esc</kbd> snooze
          </p>
        </div>
      </div>
    </div>
  );
}

// ── Call Panel (inline center section) ───────────────────────────────

function InlineCallPanel({ user, callStatus, callDuration, isMuted, onMute, onHangUp }: {
  user: User; callStatus: string; callDuration: number; isMuted: boolean;
  onMute: () => void; onHangUp: () => void;
}) {
  return (
    <div className="w-[380px] shrink-0 flex flex-col overflow-hidden relative call-panel-enter"
      style={{ background: "linear-gradient(160deg, #0f172a 0%, #1e1b4b 50%, #0c1222 100%)",
        borderLeft: "1px solid rgba(255,255,255,0.06)", borderRight: "1px solid rgba(255,255,255,0.06)" }}>
      <div className="absolute inset-0 dot-grid opacity-50 pointer-events-none" />

      {/* Ambient orbs */}
      <div className="absolute -top-10 -left-10 w-40 h-40 rounded-full pointer-events-none"
        style={{ background: "radial-gradient(circle, rgba(139,92,246,0.25) 0%, transparent 70%)" }} />
      <div className="absolute -bottom-10 -right-10 w-40 h-40 rounded-full pointer-events-none"
        style={{ background: "radial-gradient(circle, rgba(16,185,129,0.2) 0%, transparent 70%)" }} />

      {/* Header */}
      <div className="relative px-5 py-3 shrink-0 border-b border-white/5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className={cn("w-6 h-6 rounded-md flex items-center justify-center",
            callStatus === "active" ? "bg-emerald-500/20" : "bg-amber-500/20")}>
            <PhoneCall className={cn("w-3 h-3", callStatus === "active" ? "text-emerald-400" : "text-amber-400")} />
          </div>
          <span className="text-[11px] font-bold text-slate-300 uppercase tracking-widest">
            {callStatus === "active" ? "On call" : callStatus === "ringing" ? "Ringing" : "Connecting"}
          </span>
        </div>
        {callStatus === "active" && (
          <div className="flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-[10px] text-emerald-400 font-bold uppercase tracking-widest">Live</span>
          </div>
        )}
      </div>

      {/* Main call area */}
      <div className="relative flex-1 flex flex-col items-center justify-center p-6">
        {/* Pulse rings when active */}
        {callStatus === "active" && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none mt-[-40px]">
            <div className="ring-pulse-1 absolute w-32 h-32 rounded-full border border-emerald-500/40" />
            <div className="ring-pulse-2 absolute w-32 h-32 rounded-full border border-emerald-500/30" />
            <div className="ring-pulse-3 absolute w-32 h-32 rounded-full border border-emerald-500/20" />
          </div>
        )}

        {/* Avatar */}
        <div className="relative mb-5 z-10">
          <div className={cn("w-24 h-24 rounded-full flex items-center justify-center text-white text-2xl font-black", avatarColor(user.phone))}
            style={{ boxShadow: "0 0 40px rgba(0,0,0,0.5), 0 0 0 4px rgba(255,255,255,0.08)" }}>
            {user.name ? getInitials(user.name) : getAvatarText(user.phone)}
          </div>
          {callStatus === "active" && (
            <div className="absolute -bottom-1 -right-1 w-6 h-6 rounded-full bg-emerald-500 border-2 border-slate-900 flex items-center justify-center">
              <Headphones className="w-3 h-3 text-white" />
            </div>
          )}
        </div>

        {/* Identity */}
        <div className="text-center mb-2 z-10">
          <div className="text-white font-bold text-lg">{user.name || "Customer"}</div>
          <div className="flex items-center justify-center gap-1.5 mt-1.5 text-slate-400 text-[12px]">
            <ShieldCheck className="w-3 h-3 text-emerald-400" />
            <span className="font-mono tracking-wider">{maskPhone(user.phone)}</span>
          </div>
        </div>

        {/* Timer */}
        <div className="my-5 z-10 text-center min-h-[52px] flex flex-col items-center justify-center">
          {callStatus === "connecting" && (
            <div className="flex items-center gap-2 text-amber-400 text-sm">
              <Loader2 className="w-4 h-4 animate-spin" /> Connecting…
            </div>
          )}
          {callStatus === "ringing" && (
            <div className="flex items-center gap-2 text-amber-300 text-sm animate-pulse">
              <Phone className="w-4 h-4" /> Ringing…
            </div>
          )}
          {callStatus === "active" && (
            <>
              <div className="text-[2.4rem] font-black font-mono text-white tabular-nums tracking-tighter leading-none">
                {formatDuration(callDuration)}
              </div>
              <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-widest mt-1.5">Duration</div>
            </>
          )}
        </div>

        {/* Controls */}
        <div className="flex items-center gap-4 z-10">
          <button onClick={onMute}
            className={cn("w-12 h-12 rounded-full flex items-center justify-center transition-all hover:scale-105 active:scale-95", isMuted ? "text-white" : "text-slate-300 hover:text-white")}
            style={{ background: isMuted ? "linear-gradient(135deg,#d97706,#f59e0b)" : "rgba(255,255,255,0.08)", boxShadow: isMuted ? "0 4px 16px rgba(217,119,6,0.4)" : "none" }}
            title={isMuted ? "Unmute" : "Mute"}>
            {isMuted ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
          </button>
          <button onClick={onHangUp}
            className="w-14 h-14 rounded-full flex items-center justify-center text-white transition-all hover:scale-105 active:scale-95"
            style={{ background: "linear-gradient(135deg,#dc2626,#b91c1c)", boxShadow: "0 8px 24px rgba(220,38,38,0.5)" }}
            title="End call">
            <PhoneOff className="w-5 h-5" />
          </button>
        </div>

        {isMuted && (
          <div className="mt-4 flex items-center gap-1.5 text-amber-400 text-xs font-semibold z-10">
            <MicOff className="w-3 h-3" /> Microphone muted
          </div>
        )}
      </div>

      {/* Footer info */}
      <div className="relative px-5 py-3 shrink-0 border-t border-white/5 grid grid-cols-2 gap-3">
        <div className="text-center">
          <div className="text-[9px] text-slate-500 font-bold uppercase tracking-widest">Segment</div>
          <div className="text-xs text-slate-300 font-semibold capitalize mt-0.5">{user.user_segment || "new"}</div>
        </div>
        <div className="text-center border-l border-white/5">
          <div className="text-[9px] text-slate-500 font-bold uppercase tracking-widest">Language</div>
          <div className="text-xs text-slate-300 font-semibold uppercase mt-0.5">{user.language}</div>
        </div>
      </div>
    </div>
  );
}

// ── Main Dashboard ────────────────────────────────────────────────────

export default function Dashboard() {
  const [users, setUsers] = useState<User[]>([]);
  const [selectedPhone, setSelectedPhone] = useState<string | null>(null);
  const [chat, setChat] = useState<Message[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [sendText, setSendText] = useState("");
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [chatLoading, setChatLoading] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [uploadingFile, setUploadingFile] = useState(false);
  const [briefOpen, setBriefOpen] = useState(true);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [callStatus, setCallStatus] = useState<"idle"|"connecting"|"ringing"|"active"|"error">("idle");
  const [callDuration, setCallDuration] = useState(0);
  const [isMuted, setIsMuted] = useState(false);
  const deviceRef = useRef<Device | null>(null);
  const activeCallRef = useRef<Call | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [ttaNotification, setTtaNotification] = useState<User | null>(null);
  const seenTTARef = useRef<Set<string>>(new Set());
  const audioUnlockedRef = useRef(false);

  // Unlock audio on first user interaction (browsers block autoplay)
  useEffect(() => {
    const unlock = () => { audioUnlockedRef.current = true; window.removeEventListener("click", unlock); window.removeEventListener("keydown", unlock); };
    window.addEventListener("click", unlock);
    window.addEventListener("keydown", unlock);
    return () => { window.removeEventListener("click", unlock); window.removeEventListener("keydown", unlock); };
  }, []);

  useEffect(() => {
    return () => { deviceRef.current?.destroy(); if (timerRef.current) clearInterval(timerRef.current); };
  }, []);

  // Filter users visible to this RM — only TTA-assigned or in handoff state
  const myUsers = useMemo(
    () => users.filter(u => u.is_tta || (u.handoff_state && u.handoff_state !== "bot_active")),
    [users]
  );

  useEffect(() => {
    const newTTA = myUsers.find(u => u.is_tta && !seenTTARef.current.has(u.phone));
    if (newTTA) {
      setTtaNotification(newTTA);
      seenTTARef.current.add(newTTA.phone);
      if (audioUnlockedRef.current) playIncomingChime();
    }
  }, [myUsers]);

  async function ensureVoiceDevice(): Promise<Device | null> {
    if (deviceRef.current) return deviceRef.current;
    try {
      const res = await fetch(`${API_BASE}/voice/token`, { headers: HEADERS });
      const data = await res.json();
      if (data.error) return null;
      const device = new Device(data.token, { edge: "ashburn" });
      device.on("error", () => setCallStatus("error"));
      await device.register();
      deviceRef.current = device;
      return device;
    } catch { return null; }
  }

  const handleCall = useCallback(async () => {
    if (!selectedPhone) return;
    const rawPhone = selectedPhone.replace("whatsapp:", "");
    if (callStatus === "active" || callStatus === "connecting" || callStatus === "ringing") {
      activeCallRef.current?.disconnect();
      activeCallRef.current = null;
      setCallStatus("idle"); setCallDuration(0); setIsMuted(false);
      if (timerRef.current) clearInterval(timerRef.current);
      return;
    }
    setCallStatus("connecting");
    const device = await ensureVoiceDevice();
    if (!device) { setCallStatus("error"); return; }
    try {
      const call = await device.connect({ params: { To: rawPhone } });
      activeCallRef.current = call;
      call.on("ringing", () => setCallStatus("ringing"));
      call.on("accept", () => {
        setCallStatus("active"); setCallDuration(0);
        timerRef.current = setInterval(() => setCallDuration(d => d + 1), 1000);
      });
      call.on("disconnect", () => {
        setCallStatus("idle"); setCallDuration(0); setIsMuted(false);
        if (timerRef.current) clearInterval(timerRef.current);
        activeCallRef.current = null;
      });
      call.on("error", () => { setCallStatus("error"); if (timerRef.current) clearInterval(timerRef.current); });
    } catch { setCallStatus("error"); }
  }, [selectedPhone, callStatus]);

  function handleMute() {
    if (activeCallRef.current) { const next = !isMuted; activeCallRef.current.mute(next); setIsMuted(next); }
  }

  useEffect(() => {
    fetchUsers();
    const interval = setInterval(fetchUsers, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [chat]);

  async function fetchUsers() {
    try {
      const res = await fetch(`${API_BASE}/users`, { headers: HEADERS });
      const data = await res.json();
      const sorted = (data.users || []).sort((a: User, b: User) =>
        new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      );
      setUsers(sorted); setLoading(false);
    } catch { setLoading(false); }
  }

  async function selectUser(phone: string) {
    setSelectedPhone(phone); setSummary(null); setChat([]);
    setChatLoading(true); setSummaryLoading(true);
    const phoneClean = phone.replace("whatsapp:", "").replace("+", "");
    try {
      const [chatRes, summaryRes] = await Promise.all([
        fetch(`${API_BASE}/users/${phoneClean}/chat`, { headers: HEADERS }),
        fetch(`${API_BASE}/users/${phoneClean}/summary`, { headers: HEADERS }),
      ]);
      const chatData = await chatRes.json();
      setChat(chatData.messages || []); setChatLoading(false);
      const summaryData = await summaryRes.json();
      setSummary(summaryData); setSummaryLoading(false);
    } catch { setChatLoading(false); setSummaryLoading(false); }
  }

  async function handleSend() {
    if (!sendText.trim() || !selectedPhone) return;
    setSending(true);
    const phoneClean = selectedPhone.replace("whatsapp:", "").replace("+", "");
    try {
      await fetch(`${API_BASE}/users/${phoneClean}/send`, {
        method: "POST", headers: { "Content-Type": "application/json", ...HEADERS },
        body: JSON.stringify({ message: sendText }),
      });
      setSendText("");
      const chatRes = await fetch(`${API_BASE}/users/${phoneClean}/chat`, { headers: HEADERS });
      const chatData = await chatRes.json();
      setChat(chatData.messages || []);
    } catch { /* ignore */ }
    setSending(false);
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !selectedPhone) return;
    setUploadingFile(true);
    const phoneClean = selectedPhone.replace("whatsapp:", "").replace("+", "");
    try {
      const formData = new FormData();
      formData.append("file", file);
      if (sendText.trim()) formData.append("caption", sendText.trim());
      const res = await fetch(`${API_BASE}/users/${phoneClean}/send-file`, { method: "POST", headers: HEADERS, body: formData });
      if (!res.ok) { const err = await res.json(); alert(err.detail || "Failed to send file"); }
      else {
        setSendText("");
        const chatRes = await fetch(`${API_BASE}/users/${phoneClean}/chat`, { headers: HEADERS });
        const chatData = await chatRes.json();
        setChat(chatData.messages || []);
      }
    } catch { /* ignore */ }
    setUploadingFile(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  const selectedUser = users.find(u => u.phone === selectedPhone);
  const ttaCount = myUsers.filter(u => u.is_tta).length;
  const isOnCall = callStatus !== "idle" && callStatus !== "error";

  // Automatically collapse brief when call starts to make room for 3-column layout
  useEffect(() => {
    if (isOnCall) setBriefOpen(true);
  }, [isOnCall]);

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: "#f4f6fb" }}>

      {/* Full-screen warning TTA */}
      {ttaNotification && (
        <IncomingTtaModal
          user={ttaNotification}
          onAccept={() => { selectUser(ttaNotification.phone); setTtaNotification(null); }}
          onDismiss={() => setTtaNotification(null)}
        />
      )}

      {/* ── Sidebar ──────────────────────────────────────────────── */}
      <aside className="w-[280px] shrink-0 flex flex-col h-full"
        style={{ background: "linear-gradient(180deg, #0c1220 0%, #0f172a 100%)", borderRight: "1px solid rgba(255,255,255,0.05)" }}>

        {/* Brand */}
        <div className="px-5 pt-5 pb-4 shrink-0" style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
              style={{ background: "linear-gradient(135deg,#059669,#34d399)", boxShadow: "0 4px 12px rgba(5,150,105,0.4)" }}>
              <Activity className="w-4.5 h-4.5 text-white" strokeWidth={2.5} />
            </div>
            <div>
              <h1 className="text-[15px] font-black text-white tracking-tight leading-none">FI Pulse</h1>
              <p className="text-[9px] text-slate-500 mt-0.5 tracking-widest uppercase">Advisor Console</p>
            </div>
          </div>
          {/* RM identity chip */}
          <div className="mt-3 flex items-center gap-2 px-2.5 py-1.5 rounded-lg"
            style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.05)" }}>
            <div className="w-6 h-6 rounded-full bg-emerald-500/20 flex items-center justify-center text-[9px] font-black text-emerald-300">AK</div>
            <div className="flex-1 min-w-0">
              <div className="text-[11px] font-bold text-slate-200 truncate">Arun Kumar</div>
              <div className="flex items-center gap-1">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                <div className="text-[9px] text-emerald-400 font-semibold uppercase tracking-wide">Online</div>
              </div>
            </div>
          </div>
        </div>

        {/* Home nav button */}
        <div className="px-3 pt-3 shrink-0">
          <button onClick={() => setSelectedPhone(null)}
            className={cn(
              "w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm font-semibold transition-all",
              !selectedPhone ? "sidebar-active text-emerald-300" : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
            )}>
            <Home className="w-4 h-4 shrink-0" />
            Dashboard
            {ttaCount > 0 && (
              <span className="ml-auto flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[9px] font-black"
                style={{ background: "rgba(239,68,68,0.15)", color: "#f87171" }}>
                <div className="w-1.5 h-1.5 rounded-full bg-red-500 pulse-urgent" />
                {ttaCount}
              </span>
            )}
          </button>
        </div>

        {/* User list — filtered to RM assignments */}
        <div className="flex-1 overflow-y-auto sidebar-scroll py-2">
          {loading ? <UserListSkeleton /> : myUsers.length === 0 ? (
            <div className="px-5 py-10 text-center">
              <div className="w-12 h-12 rounded-2xl mx-auto mb-3 flex items-center justify-center"
                style={{ background: "rgba(16,185,129,0.1)", border: "1px solid rgba(16,185,129,0.2)" }}>
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              </div>
              <p className="text-sm text-slate-400 font-semibold">Queue is clear</p>
              <p className="text-[11px] text-slate-600 mt-1">You&apos;ll see new TTA requests here</p>
            </div>
          ) : (
            <div className="px-2 space-y-px">
              {myUsers.map(user => {
                const isActive = selectedPhone === user.phone;
                return (
                  <button key={user.phone} onClick={() => selectUser(user.phone)}
                    className={cn(
                      "w-full text-left px-3 py-2.5 rounded-xl flex items-center gap-3 transition-all duration-150 relative",
                      isActive
                        ? "bg-white/8 ring-1 ring-white/10 text-white"
                        : "hover:bg-white/5 text-slate-300",
                      user.is_tta && !isActive && "bg-red-500/5"
                    )}>
                    {user.is_tta && <div className="absolute left-0 top-2.5 bottom-2.5 w-[3px] rounded-r bg-red-500" />}
                    <div className={cn("w-10 h-10 rounded-full shrink-0 flex items-center justify-center text-white text-xs font-bold relative", avatarColor(user.phone))}>
                      {user.name ? getInitials(user.name) : getAvatarText(user.phone)}
                      {user.is_tta && (
                        <div className="absolute -top-0.5 -right-0.5 w-3 h-3 rounded-full bg-red-500 border-2 border-slate-900 pulse-urgent" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1 mb-0.5">
                        <span className={cn("text-[13px] font-semibold truncate", isActive ? "text-white" : "text-slate-300")}>
                          {user.name || formatPhone(user.phone)}
                        </span>
                        <span className="text-[10px] text-slate-600 shrink-0 font-mono">{relativeTime(user.updated_at)}</span>
                      </div>
                      {user.last_message && (
                        <p className="text-[11px] text-slate-600 truncate">
                          {user.last_message.role === "user" ? "↑ " : "↓ "}{user.last_message.content}
                        </p>
                      )}
                      <div className="flex items-center gap-1 mt-1">
                        {user.is_tta && (
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-px text-[9px] font-bold rounded uppercase tracking-wide"
                            style={{ background: "rgba(239,68,68,0.18)", color: "#fca5a5" }}>
                            <AlertCircle className="w-2.5 h-2.5" /> TTA
                          </span>
                        )}
                        {user.has_plan && (
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-px text-[9px] font-bold rounded uppercase tracking-wide"
                            style={{ background: "rgba(16,185,129,0.15)", color: "#34d399" }}>
                            <CheckCircle2 className="w-2.5 h-2.5" /> Plan
                          </span>
                        )}
                        <span className="px-1.5 py-px text-[9px] font-medium rounded uppercase tracking-wide"
                          style={{ background: "rgba(255,255,255,0.07)", color: "#64748b" }}>
                          {user.language}
                        </span>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}

        </div>

        {/* Footer */}
        <div className="px-5 py-3 shrink-0" style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-emerald-500 pulse-urgent" />
              <span className="text-[11px] text-slate-500">Live sync · 5s</span>
            </div>
            <span className="text-[10px] text-slate-600 font-mono">v2.4.1</span>
          </div>
        </div>
      </aside>

      {/* ── Main content ─────────────────────────────────────────── */}
      {selectedPhone && selectedUser ? (
        <div className="flex flex-1 min-w-0 overflow-hidden">
          {/* Chat panel */}
          <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
            {/* Chat header */}
            <div className="px-5 py-3 bg-white border-b border-slate-200 flex items-center justify-between shrink-0 gap-4"
              style={{ boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
              <div className="flex items-center gap-3 min-w-0">
                <button onClick={() => setSelectedPhone(null)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-all shrink-0">
                  <Home className="w-4 h-4" />
                </button>
                <div className={cn("w-9 h-9 rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0", avatarColor(selectedUser.phone))}>
                  {selectedUser.name ? getInitials(selectedUser.name) : getAvatarText(selectedUser.phone)}
                </div>
                <div className="min-w-0">
                  <h2 className="text-[15px] font-bold text-slate-800 leading-tight whitespace-nowrap">
                    {selectedUser.name || formatPhone(selectedUser.phone)}
                  </h2>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span className="flex items-center gap-1 text-[11px] text-slate-400 shrink-0">
                      <ShieldCheck className="w-3 h-3 shrink-0 text-emerald-500" />
                      <span className="font-mono">{maskPhone(selectedUser.phone)}</span>
                    </span>
                    <span className="text-slate-200 shrink-0">·</span>
                    <span className="flex items-center gap-1 text-[11px] text-slate-400 shrink-0">
                      <Globe2 className="w-3 h-3 shrink-0" />{selectedUser.language.toUpperCase()}
                    </span>
                    <span className="text-slate-200 shrink-0">·</span>
                    <span className="text-[11px] text-slate-400 capitalize shrink-0">{selectedUser.user_segment || "new"}</span>
                    {selectedUser.is_tta && (
                      <span className="flex items-center gap-1 text-[11px] text-red-500 font-semibold shrink-0 px-1.5 py-0.5 bg-red-50 rounded-md">
                        <AlertCircle className="w-3 h-3 shrink-0" /> TTA
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                {!isOnCall && (
                  <button onClick={handleCall}
                    className="inline-flex items-center gap-1.5 px-3 h-8 rounded-lg text-xs font-semibold whitespace-nowrap transition-all bg-emerald-600 hover:bg-emerald-700 text-white">
                    <PhoneCall className="w-3.5 h-3.5" /> Start Call
                  </button>
                )}
                <button onClick={() => setBriefOpen(!briefOpen)}
                  className="inline-flex items-center gap-1.5 px-3 h-8 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 hover:border-slate-300 text-xs font-medium whitespace-nowrap transition-all">
                  {briefOpen ? <><PanelRightClose className="w-3.5 h-3.5" /> Hide Brief</> : <><Sparkles className="w-3.5 h-3.5 text-violet-500" /> AI Brief</>}
                </button>
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-2" style={{ background: "#f1f5fb" }}>
              {chatLoading ? <ChatSkeleton /> : chat.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-2">
                  <MessageSquare className="w-8 h-8" /><p className="text-sm">No messages yet</p>
                </div>
              ) : (
                chat.map((msg, i) => {
                  const isUser = msg.role === "user";
                  const isRM = msg.content.startsWith("[RM]");
                  return (
                    <div key={i} className={cn("flex msg-in", isUser ? "justify-start" : "justify-end")}>
                      <div className={cn(
                        "max-w-[72%] px-4 py-2.5 text-sm whitespace-pre-wrap rounded-2xl shadow-sm",
                        isUser ? "bg-white text-slate-800 rounded-tl-sm border border-slate-100"
                          : isRM ? "bg-sky-500 text-white rounded-tr-sm"
                          : "bg-emerald-50 text-slate-800 rounded-tr-sm border border-emerald-100"
                      )}>
                        {isRM && <div className="flex items-center gap-1 text-[10px] font-bold text-sky-100 mb-1 uppercase tracking-wide"><Bot className="w-3 h-3" /> RM Message</div>}
                        {msg.media_type === "voice" && (
                          <div className={cn("flex items-center gap-1.5 text-[10px] font-semibold mb-1.5 uppercase tracking-wide", isUser ? "text-violet-500" : "text-emerald-500")}>
                            <Mic className="w-3 h-3" /> Voice Message
                          </div>
                        )}
                        {msg.content.replace("[RM] ", "")}
                        {msg.media_type === "voice" && (msg.audio_url || msg.media_url) && (
                          <audio controls className="mt-2 w-full max-w-[240px] h-8 rounded" src={msg.audio_url || msg.media_url} />
                        )}
                        {msg.media_url && msg.media_type !== "voice" && (
                          <a href={msg.media_url} target="_blank" rel="noopener noreferrer"
                            className={cn("mt-1.5 flex items-center gap-1.5 px-2 py-1 rounded text-xs transition",
                              isRM ? "bg-white/10 text-sky-100 hover:bg-white/20" : "bg-black/5 text-blue-600 hover:text-blue-800 hover:bg-black/10")}>
                            <Paperclip className="w-3 h-3" />
                            <span className="underline truncate max-w-[200px]">{msg.media_url.split("/").pop() || "attachment"}</span>
                          </a>
                        )}
                        <div className={cn("text-[10px] mt-1.5 text-right", isUser ? "text-slate-300" : isRM ? "text-sky-200" : "text-emerald-300")}>
                          {formatTimestamp(msg.timestamp)}
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Input */}
            <div className="px-4 py-3.5 bg-white border-t border-slate-200 shrink-0">
              <div className="flex items-center gap-2">
                <input ref={fileInputRef} type="file" onChange={handleFileUpload}
                  accept=".pdf,.png,.jpg,.jpeg,.gif,.doc,.docx,.xls,.xlsx,.csv" className="hidden" />
                <button onClick={() => fileInputRef.current?.click()} disabled={uploadingFile}
                  className="p-2 text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg transition-all disabled:opacity-40">
                  {uploadingFile ? <Loader2 className="w-4.5 h-4.5 animate-spin" /> : <Paperclip className="w-4.5 h-4.5" />}
                </button>
                <input type="text" value={sendText} onChange={e => setSendText(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && !e.shiftKey && handleSend()}
                  placeholder="Send a message to this user via WhatsApp…"
                  className="flex-1 px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-400 transition-all" />
                <button onClick={handleSend} disabled={sending || !sendText.trim()}
                  className="p-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl transition-all disabled:opacity-40 disabled:cursor-not-allowed">
                  {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                </button>
              </div>
            </div>
          </div>

          {/* Center Call Panel (inline, only when on call) */}
          {isOnCall && selectedUser && (
            <InlineCallPanel
              user={selectedUser}
              callStatus={callStatus}
              callDuration={callDuration}
              isMuted={isMuted}
              onMute={handleMute}
              onHangUp={handleCall}
            />
          )}

          {/* AI Brief panel */}
          <div className={cn("brief-panel bg-white border-l border-slate-200 flex flex-col overflow-hidden shrink-0", briefOpen ? "brief-panel-open" : "brief-panel-closed")}>
            <div className="px-5 py-4 border-b border-slate-100 shrink-0 flex items-center justify-between"
              style={{ background: "linear-gradient(90deg,#f5f3ff,#ffffff)" }}>
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: "rgba(139,92,246,0.1)" }}>
                  <Sparkles className="w-3.5 h-3.5 text-violet-600" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-800">AI Brief</h3>
                  <p className="text-[10px] text-slate-400">{isOnCall ? "Live talking points · on call" : "Generated by Claude Sonnet"}</p>
                </div>
              </div>
              <button onClick={() => setBriefOpen(false)} className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-all">
                <PanelRightClose className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto">
              {summaryLoading ? <SummarySkeleton /> : summary ? (
                <div className="p-5 space-y-5">
                  <section>
                    <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2.5 flex items-center gap-1.5">
                      <Bot className="w-3 h-3" /> Summary
                    </h4>
                    <p className="text-sm text-slate-700 leading-relaxed bg-slate-50 rounded-xl p-3.5 border border-slate-100">{summary.summary}</p>
                  </section>
                  <section>
                    <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2.5">Sentiment</h4>
                    <SentimentBadge sentiment={summary.sentiment} />
                  </section>
                  {summary.talking_points?.length > 0 && (
                    <section>
                      <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2.5 flex items-center gap-1.5">
                        <Zap className="w-3 h-3" /> Talking Points
                      </h4>
                      <ul className="space-y-2">
                        {summary.talking_points.map((pt, i) => (
                          <li key={i} className="flex items-start gap-2.5 p-3 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="w-5 h-5 rounded-full bg-violet-100 text-violet-600 flex items-center justify-center text-[10px] font-bold shrink-0 mt-px">{i + 1}</div>
                            <span className="text-sm text-slate-700 leading-snug">{pt}</span>
                          </li>
                        ))}
                      </ul>
                    </section>
                  )}
                  {summary.goal_info?.plan_generated && summary.goal_info.plan_summary && (
                    <section>
                      <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2.5 flex items-center gap-1.5">
                        <CheckCircle2 className="w-3 h-3 text-emerald-500" /> Investment Plan
                      </h4>
                      <div className="rounded-xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-white overflow-hidden">
                        <div className="px-4 py-3 border-b border-emerald-100 flex items-center gap-2">
                          <Target className="w-4 h-4 text-emerald-600" />
                          <span className="text-sm font-semibold text-emerald-800">{summary.goal_info.plan_summary.goal_name}</span>
                          <span className="ml-auto text-[10px] px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full font-semibold">{summary.goal_info.plan_summary.risk_label}</span>
                        </div>
                        <div className="p-4 grid grid-cols-2 gap-3">
                          <div className="bg-white rounded-lg p-3 border border-emerald-100">
                            <div className="flex items-center gap-1 text-[10px] text-slate-400 mb-1 uppercase tracking-wide font-semibold"><IndianRupee className="w-2.5 h-2.5" /> SIP / Month</div>
                            <div className="text-base font-bold text-slate-800">₹{summary.goal_info.plan_summary.sip_required?.toLocaleString()}</div>
                          </div>
                          <div className="bg-white rounded-lg p-3 border border-emerald-100">
                            <div className="flex items-center gap-1 text-[10px] text-slate-400 mb-1 uppercase tracking-wide font-semibold"><CalendarClock className="w-2.5 h-2.5" /> Tenure</div>
                            <div className="text-base font-bold text-slate-800">{summary.goal_info.plan_summary.tenure_years} yrs</div>
                          </div>
                          <div className="bg-white rounded-lg p-3 border border-emerald-100 col-span-2">
                            <div className="flex items-center gap-1 text-[10px] text-slate-400 mb-1 uppercase tracking-wide font-semibold"><TrendingUp className="w-2.5 h-2.5" /> Future Value</div>
                            <div className="text-lg font-bold text-emerald-700">₹{summary.goal_info.plan_summary.future_value?.toLocaleString()}</div>
                          </div>
                        </div>
                      </div>
                    </section>
                  )}
                  {selectedUser.handoff_state && selectedUser.handoff_state !== "none" && (
                    <section>
                      <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2.5 flex items-center gap-1.5">
                        <ShieldCheck className="w-3 h-3" /> Handoff Status
                      </h4>
                      <div className="flex items-center gap-2 px-3 py-2.5 bg-slate-50 rounded-xl border border-slate-200">
                        <div className="w-2 h-2 rounded-full bg-amber-400 shrink-0" />
                        <span className="text-xs text-slate-600 font-medium capitalize">{selectedUser.handoff_state.replace(/_/g, " ")}</span>
                      </div>
                    </section>
                  )}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-48 text-slate-400 gap-2">
                  <Sparkles className="w-7 h-7 text-slate-300" /><p className="text-sm">AI brief unavailable</p>
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <HomeDashboard users={myUsers} onSelectUser={selectUser} />
      )}
    </div>
  );
}
