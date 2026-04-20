"use client";

import { useState, useEffect, useRef } from "react";
import { Device, Call } from "@twilio/voice-sdk";
import {
  Activity,
  Phone, PhoneOff, PhoneCall,
  Paperclip, Send,
  MessageSquare, Users,
  ChevronRight,
  Clock, Globe2, Target,
  AlertCircle, CheckCircle2,
  Sparkles, IndianRupee,
  PanelRightClose, PanelRightOpen,
  TrendingUp,
  SmilePlus, Frown, Meh,
  Bot, Zap,
  Loader2,
  CalendarClock,
  ShieldCheck,
  Mic,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "https://phylicia-subcerebral-laurie.ngrok-free.dev/api";
const HEADERS: Record<string, string> = { "ngrok-skip-browser-warning": "1" };

// ── Utilities ──────────────────────────────────────────────────────────

function cn(...classes: (string | boolean | undefined | null)[]) {
  return classes.filter(Boolean).join(" ");
}

function formatPhone(phone: string): string {
  const raw = phone.replace("whatsapp:", "").replace("+", "");
  if (raw.startsWith("91") && raw.length === 12) {
    return `+91 ${raw.slice(2, 7)} ${raw.slice(7)}`;
  }
  return `+${raw}`;
}

function getAvatarText(phone: string): string {
  const raw = phone.replace("whatsapp:", "").replace("+", "");
  return raw.slice(-4, -2);
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

// Deterministic avatar color from phone string
function avatarColor(phone: string): string {
  const colors = [
    "bg-violet-500", "bg-sky-500", "bg-amber-500",
    "bg-rose-500", "bg-teal-500", "bg-indigo-500",
    "bg-orange-500", "bg-cyan-500",
  ];
  let hash = 0;
  for (const c of phone) hash = (hash * 31 + c.charCodeAt(0)) & 0xffff;
  return colors[hash % colors.length];
}

// ── Types ──────────────────────────────────────────────────────────────

interface User {
  phone: string;
  phone_display: string;
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
  role: string;
  content: string;
  timestamp: string;
  media_url?: string;
  media_type?: "voice" | "file" | null;
  audio_url?: string;
}

interface Summary {
  summary: string;
  talking_points: string[];
  sentiment: string;
  goal_info: {
    collected: Record<string, unknown>;
    plan_generated: boolean;
    plan_summary: {
      goal_name: string;
      sip_required: number;
      tenure_years: number;
      risk_label: string;
      future_value: number;
    } | null;
  };
}

// ── Skeleton Components ────────────────────────────────────────────────

function SkeletonBlock({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} />;
}

function UserListSkeleton() {
  return (
    <div className="space-y-px px-2">
      {[...Array(7)].map((_, i) => (
        <div key={i} className="flex items-center gap-3 px-3 py-3 rounded-xl">
          <SkeletonBlock className="w-10 h-10 rounded-full shrink-0" />
          <div className="flex-1 space-y-2">
            <div className="flex justify-between items-center">
              <SkeletonBlock className="h-3 w-28" />
              <SkeletonBlock className="h-2.5 w-10" />
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
          <SkeletonBlock
            className={cn(
              "rounded-2xl",
              i === 0 ? "w-56 h-14" : i === 2 ? "w-72 h-20" : i === 4 ? "w-48 h-12" : "w-64 h-16",
              isBot ? "rounded-tr-sm" : "rounded-tl-sm"
            )}
          />
        </div>
      ))}
    </div>
  );
}

function SummarySkeleton() {
  return (
    <div className="p-5 space-y-6">
      {/* Section 1 */}
      <div className="space-y-2.5">
        <SkeletonBlock className="h-3 w-16" />
        <SkeletonBlock className="h-4 w-full" />
        <SkeletonBlock className="h-4 w-11/12" />
        <SkeletonBlock className="h-4 w-4/5" />
      </div>
      {/* Section 2 */}
      <div className="space-y-2">
        <SkeletonBlock className="h-3 w-20" />
        <SkeletonBlock className="h-7 w-24 rounded-full" />
      </div>
      {/* Section 3 */}
      <div className="space-y-2.5">
        <SkeletonBlock className="h-3 w-28" />
        {[1, 2, 3].map((j) => (
          <div key={j} className="flex items-center gap-2">
            <SkeletonBlock className="w-1.5 h-1.5 rounded-full shrink-0" />
            <SkeletonBlock className={cn("h-3.5", j === 2 ? "w-3/5" : j === 1 ? "w-full" : "w-4/5")} />
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Empty State ────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex-1 flex items-center justify-center bg-slate-50">
      <div className="text-center max-w-sm">
        <div className="w-20 h-20 rounded-3xl bg-emerald-50 flex items-center justify-center mx-auto mb-5 border border-emerald-100">
          <MessageSquare className="w-9 h-9 text-emerald-600" />
        </div>
        <h2 className="text-xl font-semibold text-slate-800 mb-2">Select a conversation</h2>
        <p className="text-slate-400 text-sm leading-relaxed">
          Choose a user from the sidebar to view their WhatsApp conversation, AI brief, and investment details.
        </p>
      </div>
    </div>
  );
}

// ── Sentiment Badge ────────────────────────────────────────────────────

function SentimentBadge({ sentiment }: { sentiment: string }) {
  if (sentiment === "positive") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-emerald-50 text-emerald-700 text-xs font-semibold rounded-full border border-emerald-200">
        <SmilePlus className="w-3.5 h-3.5" /> Positive
      </span>
    );
  }
  if (sentiment === "frustrated" || sentiment === "negative") {
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-red-50 text-red-700 text-xs font-semibold rounded-full border border-red-200">
        <Frown className="w-3.5 h-3.5" /> Frustrated
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-slate-100 text-slate-600 text-xs font-semibold rounded-full border border-slate-200">
      <Meh className="w-3.5 h-3.5" /> Neutral
    </span>
  );
}

// ── Main Dashboard ─────────────────────────────────────────────────────

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

  // Voice state
  const [callStatus, setCallStatus] = useState<"idle" | "connecting" | "ringing" | "active" | "error">("idle");
  const [callDuration, setCallDuration] = useState(0);
  const deviceRef = useRef<Device | null>(null);
  const activeCallRef = useRef<Call | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      deviceRef.current?.destroy();
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  async function ensureVoiceDevice(): Promise<Device | null> {
    // Reuse existing device if already registered
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
    } catch {
      return null;
    }
  }

  async function handleCall() {
    if (!selectedPhone) return;
    const rawPhone = selectedPhone.replace("whatsapp:", "");

    // Hang up if already in a call
    if (callStatus === "active" || callStatus === "connecting" || callStatus === "ringing") {
      activeCallRef.current?.disconnect();
      activeCallRef.current = null;
      setCallStatus("idle");
      setCallDuration(0);
      if (timerRef.current) clearInterval(timerRef.current);
      return;
    }

    setCallStatus("connecting");

    // Lazy-init voice device on first call attempt
    const device = await ensureVoiceDevice();
    if (!device) {
      setCallStatus("error");
      return;
    }

    try {
      const call = await device.connect({ params: { To: rawPhone } });
      activeCallRef.current = call;
      call.on("ringing", () => setCallStatus("ringing"));
      call.on("accept", () => {
        setCallStatus("active");
        setCallDuration(0);
        timerRef.current = setInterval(() => setCallDuration((d) => d + 1), 1000);
      });
      call.on("disconnect", () => {
        setCallStatus("idle");
        setCallDuration(0);
        if (timerRef.current) clearInterval(timerRef.current);
        activeCallRef.current = null;
      });
      call.on("error", () => {
        setCallStatus("error");
        if (timerRef.current) clearInterval(timerRef.current);
      });
    } catch {
      setCallStatus("error");
    }
  }

  useEffect(() => {
    fetchUsers();
    const interval = setInterval(fetchUsers, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat]);

  async function fetchUsers() {
    try {
      const res = await fetch(`${API_BASE}/users`, { headers: HEADERS });
      const data = await res.json();
      // Sort by latest activity
      const sorted = (data.users || []).sort((a: User, b: User) =>
        new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      );
      setUsers(sorted);
      setLoading(false);
    } catch {
      setLoading(false);
    }
  }

  async function selectUser(phone: string) {
    setSelectedPhone(phone);
    setSummary(null);
    setChat([]);
    setChatLoading(true);
    setSummaryLoading(true);

    const phoneClean = phone.replace("whatsapp:", "").replace("+", "");
    try {
      const [chatRes, summaryRes] = await Promise.all([
        fetch(`${API_BASE}/users/${phoneClean}/chat`, { headers: HEADERS }),
        fetch(`${API_BASE}/users/${phoneClean}/summary`, { headers: HEADERS }),
      ]);
      const chatData = await chatRes.json();
      setChat(chatData.messages || []);
      setChatLoading(false);

      const summaryData = await summaryRes.json();
      setSummary(summaryData);
      setSummaryLoading(false);
    } catch {
      setChatLoading(false);
      setSummaryLoading(false);
    }
  }

  async function handleSend() {
    if (!sendText.trim() || !selectedPhone) return;
    setSending(true);
    const phoneClean = selectedPhone.replace("whatsapp:", "").replace("+", "");
    try {
      await fetch(`${API_BASE}/users/${phoneClean}/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...HEADERS },
        body: JSON.stringify({ message: sendText }),
      });
      setSendText("");
      const chatRes = await fetch(`${API_BASE}/users/${phoneClean}/chat`, { headers: HEADERS });
      const chatData = await chatRes.json();
      setChat(chatData.messages || []);
    } catch {
      /* ignore */
    }
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
      if (!res.ok) {
        const err = await res.json();
        alert(err.detail || "Failed to send file");
      } else {
        setSendText("");
        const chatRes = await fetch(`${API_BASE}/users/${phoneClean}/chat`, { headers: HEADERS });
        const chatData = await chatRes.json();
        setChat(chatData.messages || []);
      }
    } catch {
      /* ignore */
    }
    setUploadingFile(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  const selectedUser = users.find((u) => u.phone === selectedPhone);
  const ttaCount = users.filter((u) => u.is_tta).length;

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      {/* ── Sidebar ──────────────────────────────────────────────────── */}
      <aside className="w-[300px] shrink-0 bg-slate-900 flex flex-col h-full">
        {/* Brand Header */}
        <div className="px-5 pt-5 pb-4 border-b border-slate-800 shrink-0">
          <div className="flex items-center gap-2.5 mb-0.5">
            <div className="w-8 h-8 rounded-lg bg-emerald-500 flex items-center justify-center shrink-0">
              <Activity className="w-4.5 h-4.5 text-white" strokeWidth={2.5} />
            </div>
            <div>
              <h1 className="text-[15px] font-bold text-white tracking-tight leading-none">FI Pulse</h1>
              <p className="text-[10px] text-slate-500 mt-0.5 tracking-wide uppercase">WhatsApp Command Center</p>
            </div>
          </div>
        </div>

        {/* Stats Bar */}
        <div className="px-5 py-3 border-b border-slate-800 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-1.5">
            <Users className="w-3.5 h-3.5 text-slate-500" />
            <span className="text-xs text-slate-400 font-medium">{users.length} active</span>
          </div>
          {ttaCount > 0 && (
            <div className="flex items-center gap-1.5 px-2 py-0.5 bg-red-500/10 rounded-md">
              <div className="w-1.5 h-1.5 rounded-full bg-red-500 pulse-urgent" />
              <span className="text-[11px] text-red-400 font-semibold">{ttaCount} TTA</span>
            </div>
          )}
        </div>

        {/* User List */}
        <div className="flex-1 overflow-y-auto sidebar-scroll py-2">
          {loading ? (
            <UserListSkeleton />
          ) : users.length === 0 ? (
            <div className="px-5 py-10 text-center">
              <MessageSquare className="w-8 h-8 text-slate-700 mx-auto mb-3" />
              <p className="text-sm text-slate-500 font-medium">No conversations yet</p>
              <p className="text-xs text-slate-600 mt-1">Users will appear when they message the bot</p>
            </div>
          ) : (
            <div className="px-2 space-y-px">
              {users.map((user) => {
                const isActive = selectedPhone === user.phone;
                const color = avatarColor(user.phone);
                return (
                  <button
                    key={user.phone}
                    onClick={() => selectUser(user.phone)}
                    className={cn(
                      "w-full text-left px-3 py-2.5 rounded-xl flex items-center gap-3 transition-all duration-150 group",
                      isActive
                        ? "bg-slate-700/60 ring-1 ring-slate-600"
                        : "hover:bg-slate-800/60"
                    )}
                  >
                    {/* Avatar */}
                    <div className={cn("w-10 h-10 rounded-full shrink-0 flex items-center justify-center text-white text-xs font-bold relative", color)}>
                      {getAvatarText(user.phone)}
                      {user.is_tta && (
                        <div className="absolute -top-0.5 -right-0.5 w-3 h-3 rounded-full bg-red-500 border-2 border-slate-900 pulse-urgent" />
                      )}
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1 mb-0.5">
                        <span className={cn("text-[13px] font-semibold truncate", isActive ? "text-white" : "text-slate-200")}>
                          {formatPhone(user.phone)}
                        </span>
                        <span className="text-[10px] text-slate-500 shrink-0 font-mono">
                          {relativeTime(user.updated_at)}
                        </span>
                      </div>
                      {user.last_message && (
                        <p className="text-[11px] text-slate-500 truncate">
                          {user.last_message.role === "user" ? "↑ " : "↓ "}
                          {user.last_message.content}
                        </p>
                      )}
                      {/* Badges row */}
                      <div className="flex items-center gap-1 mt-1">
                        {user.has_plan && (
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-px bg-emerald-500/15 text-emerald-400 text-[9px] font-bold rounded uppercase tracking-wide">
                            <CheckCircle2 className="w-2.5 h-2.5" /> Plan
                          </span>
                        )}
                        <span className="px-1.5 py-px bg-slate-700 text-slate-400 text-[9px] font-medium rounded uppercase tracking-wide">
                          {user.language}
                        </span>
                        {user.active_intent && (
                          <span className="px-1.5 py-px bg-slate-700/50 text-slate-500 text-[9px] rounded truncate max-w-[64px]">
                            {user.active_intent}
                          </span>
                        )}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-slate-800 shrink-0">
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            <span className="text-[11px] text-slate-500">Live · polling every 5s</span>
          </div>
        </div>
      </aside>

      {/* ── Main Content ──────────────────────────────────────────────── */}
      {selectedPhone && selectedUser ? (
        <div className="flex flex-1 min-w-0 overflow-hidden">
          {/* Chat Panel */}
          <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
            {/* Chat Header */}
            <div className="px-5 py-3 bg-white border-b border-slate-200 flex items-center justify-between shrink-0 shadow-sm gap-4">
              {/* Left — user identity */}
              <div className="flex items-center gap-3 min-w-0">
                <div className={cn("w-9 h-9 rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0", avatarColor(selectedUser.phone))}>
                  {getAvatarText(selectedUser.phone)}
                </div>
                <div className="min-w-0">
                  <h2 className="text-[15px] font-semibold text-slate-800 leading-tight whitespace-nowrap">
                    {formatPhone(selectedUser.phone)}
                  </h2>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span className="flex items-center gap-1 text-[11px] text-slate-400 shrink-0">
                      <Globe2 className="w-3 h-3 shrink-0" />
                      {selectedUser.language.toUpperCase()}
                    </span>
                    <span className="text-slate-200 shrink-0">·</span>
                    <span className="text-[11px] text-slate-400 capitalize shrink-0">
                      {selectedUser.user_segment || "new"} user
                    </span>
                    <span className="text-slate-200 shrink-0">·</span>
                    <span className="text-[11px] text-slate-400 shrink-0">
                      {selectedUser.message_count} msgs
                    </span>
                    {selectedUser.is_tta && (
                      <span className="flex items-center gap-1 text-[11px] text-red-500 font-semibold shrink-0 px-1.5 py-0.5 bg-red-50 rounded-md">
                        <AlertCircle className="w-3 h-3 shrink-0" /> TTA
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Right — actions */}
              <div className="flex items-center gap-2 shrink-0">
                {callStatus === "ringing" && (
                  <span className="text-xs text-amber-600 font-medium animate-pulse">Ringing…</span>
                )}
                {callStatus === "connecting" && (
                  <div className="flex items-center gap-1.5 text-slate-400 text-xs">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" /> Connecting
                  </div>
                )}

                {/* Call button — timer embedded when active */}
                <button
                  onClick={handleCall}
                  disabled={callStatus === "connecting"}
                  className={cn(
                    "inline-flex items-center gap-1.5 px-3 h-8 rounded-lg text-xs font-semibold whitespace-nowrap transition-all",
                    callStatus === "active" || callStatus === "ringing"
                      ? "bg-red-500 hover:bg-red-600 text-white"
                      : callStatus === "connecting"
                      ? "bg-amber-400 text-white cursor-not-allowed"
                      : "bg-emerald-600 hover:bg-emerald-700 text-white",
                    "disabled:opacity-40 disabled:cursor-not-allowed"
                  )}
                >
                  {callStatus === "active" ? (
                    <>
                      <div className="w-1.5 h-1.5 rounded-full bg-white/70 pulse-urgent" />
                      <span className="font-mono tabular-nums">{formatDuration(callDuration)}</span>
                      <span className="opacity-70">·</span>
                      <PhoneOff className="w-3.5 h-3.5" />
                      <span>Hang up</span>
                    </>
                  ) : callStatus === "ringing" ? (
                    <><PhoneOff className="w-3.5 h-3.5" /> Hang up</>
                  ) : callStatus === "connecting" ? (
                    <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Connecting</>
                  ) : (
                    <><PhoneCall className="w-3.5 h-3.5" /> Call</>
                  )}
                </button>

                {/* AI Brief toggle */}
                <button
                  onClick={() => setBriefOpen(!briefOpen)}
                  title={briefOpen ? "Hide AI Brief" : "Show AI Brief"}
                  className="inline-flex items-center gap-1.5 px-3 h-8 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50 hover:border-slate-300 text-xs font-medium whitespace-nowrap transition-all"
                >
                  {briefOpen ? (
                    <><PanelRightClose className="w-3.5 h-3.5" /> Hide Brief</>
                  ) : (
                    <><Sparkles className="w-3.5 h-3.5 text-violet-500" /> AI Brief</>
                  )}
                </button>
              </div>
            </div>

            {/* Chat Messages */}
            <div className="flex-1 overflow-y-auto px-5 py-4 bg-slate-100/60 space-y-2">
              {chatLoading ? (
                <ChatSkeleton />
              ) : chat.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-full text-slate-400 gap-2">
                  <MessageSquare className="w-8 h-8" />
                  <p className="text-sm">No messages yet</p>
                </div>
              ) : (
                chat.map((msg, i) => {
                  const isUser = msg.role === "user";
                  const isRM = msg.content.startsWith("[RM]");
                  return (
                    <div key={i} className={cn("flex msg-in", isUser ? "justify-start" : "justify-end")}>
                      <div
                        className={cn(
                          "max-w-[72%] px-4 py-2.5 text-sm whitespace-pre-wrap relative",
                          "rounded-2xl shadow-sm",
                          isUser
                            ? "bg-white text-slate-800 rounded-tl-sm border border-slate-100"
                            : isRM
                            ? "bg-sky-500 text-white rounded-tr-sm"
                            : "bg-emerald-50 text-slate-800 rounded-tr-sm border border-emerald-100"
                        )}
                      >
                        {isRM && (
                          <div className="flex items-center gap-1 text-[10px] font-bold text-sky-100 mb-1 uppercase tracking-wide">
                            <Bot className="w-3 h-3" /> RM Message
                          </div>
                        )}
                        {msg.media_type === "voice" && (
                          <div className={cn(
                            "flex items-center gap-1.5 text-[10px] font-semibold mb-1.5 uppercase tracking-wide",
                            isUser ? "text-violet-500" : "text-emerald-500"
                          )}>
                            <Mic className="w-3 h-3" /> Voice Message
                          </div>
                        )}
                        {msg.content.replace("[RM] ", "")}
                        {/* Audio player for voice messages */}
                        {msg.media_type === "voice" && (msg.audio_url || msg.media_url) && (
                          <audio
                            controls
                            className="mt-2 w-full max-w-[240px] h-8 rounded"
                            src={msg.audio_url || msg.media_url}
                          />
                        )}
                        {/* File attachment link (non-voice) */}
                        {msg.media_url && msg.media_type !== "voice" && (
                          <a
                            href={msg.media_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className={cn(
                              "mt-1.5 flex items-center gap-1.5 px-2 py-1 rounded text-xs transition",
                              isRM ? "bg-white/10 text-sky-100 hover:bg-white/20" : "bg-black/5 text-blue-600 hover:text-blue-800 hover:bg-black/10"
                            )}
                          >
                            <Paperclip className="w-3 h-3" />
                            <span className="underline truncate max-w-[200px]">
                              {msg.media_url.split("/").pop() || "attachment"}
                            </span>
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

            {/* Message Input */}
            <div className="px-4 py-3.5 bg-white border-t border-slate-200 shrink-0">
              <div className="flex items-center gap-2">
                <input
                  ref={fileInputRef}
                  type="file"
                  onChange={handleFileUpload}
                  accept=".pdf,.png,.jpg,.jpeg,.gif,.doc,.docx,.xls,.xlsx,.csv"
                  className="hidden"
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploadingFile}
                  className="p-2 text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg transition-all disabled:opacity-40"
                  title="Attach file"
                >
                  {uploadingFile ? (
                    <Loader2 className="w-4.5 h-4.5 animate-spin" />
                  ) : (
                    <Paperclip className="w-4.5 h-4.5" />
                  )}
                </button>
                <input
                  type="text"
                  value={sendText}
                  onChange={(e) => setSendText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
                  placeholder="Send a message to this user via WhatsApp…"
                  className="flex-1 px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500/30 focus:border-emerald-400 transition-all"
                />
                <button
                  onClick={handleSend}
                  disabled={sending || !sendText.trim()}
                  className="p-2.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                </button>
              </div>
            </div>
          </div>

          {/* ── AI Brief Panel ───────────────────────────────────────── */}
          <div
            className={cn(
              "brief-panel bg-white border-l border-slate-200 flex flex-col overflow-hidden shrink-0",
              briefOpen ? "brief-panel-open" : "brief-panel-closed"
            )}
          >
            {/* Brief Header */}
            <div className="px-5 py-4 border-b border-slate-100 shrink-0 flex items-center justify-between bg-gradient-to-r from-violet-50 to-white">
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-violet-100 flex items-center justify-center">
                  <Sparkles className="w-3.5 h-3.5 text-violet-600" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-800">AI Brief</h3>
                  <p className="text-[10px] text-slate-400">Generated by Claude Sonnet</p>
                </div>
              </div>
              <button
                onClick={() => setBriefOpen(false)}
                className="p-1.5 rounded-lg hover:bg-slate-100 text-slate-400 hover:text-slate-600 transition-all"
              >
                <PanelRightClose className="w-4 h-4" />
              </button>
            </div>

            {/* Brief Content */}
            <div className="flex-1 overflow-y-auto">
              {summaryLoading ? (
                <SummarySkeleton />
              ) : summary ? (
                <div className="p-5 space-y-5">
                  {/* Summary */}
                  <section>
                    <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2.5 flex items-center gap-1.5">
                      <Bot className="w-3 h-3" /> Summary
                    </h4>
                    <p className="text-sm text-slate-700 leading-relaxed bg-slate-50 rounded-xl p-3.5 border border-slate-100">
                      {summary.summary}
                    </p>
                  </section>

                  {/* Sentiment */}
                  <section>
                    <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2.5">
                      Sentiment
                    </h4>
                    <SentimentBadge sentiment={summary.sentiment} />
                  </section>

                  {/* Talking Points */}
                  {summary.talking_points?.length > 0 && (
                    <section>
                      <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2.5 flex items-center gap-1.5">
                        <Zap className="w-3 h-3" /> Talking Points
                      </h4>
                      <ul className="space-y-2">
                        {summary.talking_points.map((pt, i) => (
                          <li key={i} className="flex items-start gap-2.5 p-3 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="w-5 h-5 rounded-full bg-violet-100 text-violet-600 flex items-center justify-center text-[10px] font-bold shrink-0 mt-px">
                              {i + 1}
                            </div>
                            <span className="text-sm text-slate-700 leading-snug">{pt}</span>
                          </li>
                        ))}
                      </ul>
                    </section>
                  )}

                  {/* Plan Generated */}
                  {summary.goal_info?.plan_generated && summary.goal_info.plan_summary && (
                    <section>
                      <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2.5 flex items-center gap-1.5">
                        <CheckCircle2 className="w-3 h-3 text-emerald-500" /> Investment Plan
                      </h4>
                      <div className="rounded-xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-white overflow-hidden">
                        <div className="px-4 py-3 border-b border-emerald-100 flex items-center gap-2">
                          <Target className="w-4 h-4 text-emerald-600" />
                          <span className="text-sm font-semibold text-emerald-800">
                            {summary.goal_info.plan_summary.goal_name}
                          </span>
                          <span className="ml-auto text-[10px] px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full font-semibold">
                            {summary.goal_info.plan_summary.risk_label}
                          </span>
                        </div>
                        <div className="p-4 grid grid-cols-2 gap-3">
                          <div className="bg-white rounded-lg p-3 border border-emerald-100">
                            <div className="flex items-center gap-1 text-[10px] text-slate-400 mb-1 uppercase tracking-wide font-semibold">
                              <IndianRupee className="w-2.5 h-2.5" /> SIP / Month
                            </div>
                            <div className="text-base font-bold text-slate-800">
                              ₹{summary.goal_info.plan_summary.sip_required?.toLocaleString()}
                            </div>
                          </div>
                          <div className="bg-white rounded-lg p-3 border border-emerald-100">
                            <div className="flex items-center gap-1 text-[10px] text-slate-400 mb-1 uppercase tracking-wide font-semibold">
                              <CalendarClock className="w-2.5 h-2.5" /> Tenure
                            </div>
                            <div className="text-base font-bold text-slate-800">
                              {summary.goal_info.plan_summary.tenure_years} yrs
                            </div>
                          </div>
                          <div className="bg-white rounded-lg p-3 border border-emerald-100 col-span-2">
                            <div className="flex items-center gap-1 text-[10px] text-slate-400 mb-1 uppercase tracking-wide font-semibold">
                              <TrendingUp className="w-2.5 h-2.5" /> Future Value
                            </div>
                            <div className="text-lg font-bold text-emerald-700">
                              ₹{summary.goal_info.plan_summary.future_value?.toLocaleString()}
                            </div>
                          </div>
                        </div>
                      </div>
                    </section>
                  )}

                  {/* Goal In Progress */}
                  {summary.goal_info?.collected &&
                    Object.keys(summary.goal_info.collected).length > 0 &&
                    !summary.goal_info.plan_generated && (
                      <section>
                        <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2.5 flex items-center gap-1.5">
                          <Clock className="w-3 h-3 text-amber-500" /> Goal In Progress
                        </h4>
                        <div className="rounded-xl border border-amber-200 bg-amber-50 overflow-hidden">
                          <div className="px-4 py-2.5 border-b border-amber-100 flex items-center gap-2">
                            <Target className="w-3.5 h-3.5 text-amber-600" />
                            <span className="text-xs font-semibold text-amber-800">Collecting goal data…</span>
                          </div>
                          <div className="p-3 space-y-2">
                            {Object.entries(summary.goal_info.collected).map(([key, val]) =>
                              val !== null ? (
                                <div key={key} className="flex items-center justify-between py-1.5 px-3 bg-white rounded-lg border border-amber-100">
                                  <span className="text-xs text-slate-500 capitalize">{key.replace(/_/g, " ")}</span>
                                  <span className="text-xs font-semibold text-slate-700">{String(val)}</span>
                                </div>
                              ) : null
                            )}
                          </div>
                        </div>
                      </section>
                    )}

                  {/* Handoff state */}
                  {selectedUser.handoff_state && selectedUser.handoff_state !== "none" && (
                    <section>
                      <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2.5 flex items-center gap-1.5">
                        <ShieldCheck className="w-3 h-3" /> Handoff Status
                      </h4>
                      <div className="flex items-center gap-2 px-3 py-2.5 bg-slate-50 rounded-xl border border-slate-200">
                        <div className="w-2 h-2 rounded-full bg-amber-400 shrink-0" />
                        <span className="text-xs text-slate-600 font-medium capitalize">
                          {selectedUser.handoff_state.replace(/_/g, " ")}
                        </span>
                      </div>
                    </section>
                  )}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-48 text-slate-400 gap-2">
                  <Sparkles className="w-7 h-7 text-slate-300" />
                  <p className="text-sm">AI brief unavailable</p>
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <EmptyState />
      )}
    </div>
  );
}
