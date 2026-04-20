"use client";

import { useState, useEffect, useRef } from "react";
import { Device, Call } from "@twilio/voice-sdk";

const API_BASE = "http://localhost:8000/api";

// ── Types ────────────────────────────────────────────────────────────

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

// ── Main Dashboard ───────────────────────────────────────────────────

export default function Dashboard() {
  const [users, setUsers] = useState<User[]>([]);
  const [selectedPhone, setSelectedPhone] = useState<string | null>(null);
  const [chat, setChat] = useState<Message[]>([]);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [sendText, setSendText] = useState("");
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [uploadingFile, setUploadingFile] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Voice calling state
  const [callStatus, setCallStatus] = useState<"idle" | "connecting" | "ringing" | "active" | "error">("idle");
  const [callDuration, setCallDuration] = useState(0);
  const deviceRef = useRef<Device | null>(null);
  const activeCallRef = useRef<Call | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Initialize Twilio Device on mount
  useEffect(() => {
    initVoiceDevice();
    return () => {
      deviceRef.current?.destroy();
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  async function initVoiceDevice() {
    try {
      const res = await fetch(`${API_BASE}/voice/token`);
      const data = await res.json();
      if (data.error) {
        console.warn("Voice not configured:", data.error);
        return;
      }
      const device = new Device(data.token, { edge: "ashburn" });
      device.on("error", (err) => {
        console.error("Twilio Device error:", err);
        setCallStatus("error");
      });
      await device.register();
      deviceRef.current = device;
      console.log("Twilio Voice Device ready");
    } catch (err) {
      console.warn("Voice init failed (non-critical):", err);
    }
  }

  async function handleCall() {
    if (!selectedPhone || !deviceRef.current) return;

    // Extract raw phone number (e.g., +918473970793)
    const rawPhone = selectedPhone.replace("whatsapp:", "");
    console.log("Calling:", rawPhone, "selectedPhone:", selectedPhone);

    if (callStatus === "active" || callStatus === "connecting" || callStatus === "ringing") {
      // Hang up
      activeCallRef.current?.disconnect();
      activeCallRef.current = null;
      setCallStatus("idle");
      setCallDuration(0);
      if (timerRef.current) clearInterval(timerRef.current);
      return;
    }

    setCallStatus("connecting");
    try {
      const call = await deviceRef.current.connect({ params: { To: rawPhone } });
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
    } catch (err) {
      console.error("Call failed:", err);
      setCallStatus("error");
    }
  }

  // Fetch users on mount + poll every 5s
  useEffect(() => {
    fetchUsers();
    const interval = setInterval(fetchUsers, 5000);
    return () => clearInterval(interval);
  }, []);

  // Scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chat]);

  async function fetchUsers() {
    try {
      const res = await fetch(`${API_BASE}/users`);
      const data = await res.json();
      setUsers(data.users || []);
      setLoading(false);
    } catch {
      console.error("Failed to fetch users");
      setLoading(false);
    }
  }

  async function selectUser(phone: string) {
    setSelectedPhone(phone);
    setSummary(null);
    setSummaryLoading(true);

    const phoneClean = phone.replace("whatsapp:", "").replace("+", "");
    try {
      const [chatRes, summaryRes] = await Promise.all([
        fetch(`${API_BASE}/users/${phoneClean}/chat`),
        fetch(`${API_BASE}/users/${phoneClean}/summary`),
      ]);
      const chatData = await chatRes.json();
      setChat(chatData.messages || []);

      const summaryData = await summaryRes.json();
      setSummary(summaryData);
    } catch {
      console.error("Failed to fetch user data");
    }
    setSummaryLoading(false);
  }

  async function handleSend() {
    if (!sendText.trim() || !selectedPhone) return;
    setSending(true);
    const phoneClean = selectedPhone.replace("whatsapp:", "").replace("+", "");
    try {
      await fetch(`${API_BASE}/users/${phoneClean}/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: sendText }),
      });
      setSendText("");
      // Refresh chat
      const chatRes = await fetch(`${API_BASE}/users/${phoneClean}/chat`);
      const chatData = await chatRes.json();
      setChat(chatData.messages || []);
    } catch {
      console.error("Failed to send message");
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
      if (sendText.trim()) {
        formData.append("caption", sendText.trim());
      }

      const res = await fetch(`${API_BASE}/users/${phoneClean}/send-file`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        alert(err.detail || "Failed to send file");
      } else {
        setSendText("");
        // Refresh chat
        const chatRes = await fetch(`${API_BASE}/users/${phoneClean}/chat`);
        const chatData = await chatRes.json();
        setChat(chatData.messages || []);
      }
    } catch {
      console.error("Failed to upload file");
    }
    setUploadingFile(false);
    // Reset file input
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  const selectedUser = users.find((u) => u.phone === selectedPhone);

  return (
    <div className="flex h-screen">
      {/* Left Sidebar — User List */}
      <div className="w-80 bg-white border-r border-gray-200 flex flex-col shrink-0">
        {/* Header */}
        <div className="px-4 py-4 border-b border-gray-200 bg-[#0d7a3f]">
          <h1 className="text-lg font-bold text-white">FundsIndia RM</h1>
          <p className="text-xs text-green-100">Relationship Manager Dashboard</p>
        </div>

        {/* User List */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="p-4 text-center text-gray-400">Loading...</div>
          ) : users.length === 0 ? (
            <div className="p-6 text-center text-gray-400">
              <div className="text-4xl mb-2">📭</div>
              <p className="text-sm">No conversations yet</p>
              <p className="text-xs mt-1">Users will appear here when they message the bot</p>
            </div>
          ) : (
            users.map((user) => (
              <div
                key={user.phone}
                onClick={() => selectUser(user.phone)}
                className={`px-4 py-3 border-b border-gray-100 cursor-pointer hover:bg-gray-50 transition ${
                  selectedPhone === user.phone ? "bg-green-50 border-l-4 border-l-[#0d7a3f]" : ""
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-sm">{user.phone_display}</span>
                  <div className="flex items-center gap-1">
                    {user.is_tta && (
                      <span className="px-1.5 py-0.5 bg-red-100 text-red-700 text-[10px] font-bold rounded animate-pulse">
                        TTA
                      </span>
                    )}
                    {user.has_plan && (
                      <span className="px-1.5 py-0.5 bg-green-100 text-green-700 text-[10px] font-bold rounded">
                        PLAN
                      </span>
                    )}
                    <span className="px-1.5 py-0.5 bg-gray-100 text-gray-600 text-[10px] rounded uppercase">
                      {user.language}
                    </span>
                  </div>
                </div>
                {user.last_message && (
                  <p className="text-xs text-gray-500 truncate">
                    {user.last_message.role === "user" ? "User: " : "Bot: "}
                    {user.last_message.content}
                  </p>
                )}
                <div className="flex items-center justify-between mt-1">
                  <span className="text-[10px] text-gray-400">
                    {user.message_count} msgs
                  </span>
                  {user.active_intent && (
                    <span className="text-[10px] text-gray-400">
                      {user.active_intent}
                    </span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Right Panel — Chat + Summary */}
      {selectedPhone && selectedUser ? (
        <div className="flex-1 flex min-w-0">
          {/* Chat Panel */}
          <div className="flex-1 flex flex-col min-w-0">
            {/* Chat Header */}
            <div className="px-5 py-3 border-b border-gray-200 bg-white flex items-center justify-between shrink-0">
              <div>
                <h2 className="font-bold text-base">{selectedUser.phone_display}</h2>
                <span className="text-xs text-gray-500">
                  {selectedUser.language.toUpperCase()} &middot;{" "}
                  {selectedUser.user_segment || "new"} &middot;{" "}
                  {selectedUser.handoff_state}
                </span>
              </div>
              <div className="flex items-center gap-2">
                {callStatus === "active" && (
                  <span className="text-xs text-gray-500 font-mono">
                    {Math.floor(callDuration / 60).toString().padStart(2, "0")}:{(callDuration % 60).toString().padStart(2, "0")}
                  </span>
                )}
                {callStatus === "ringing" && (
                  <span className="text-xs text-yellow-600 animate-pulse">Ringing...</span>
                )}
                {callStatus === "connecting" && (
                  <span className="text-xs text-gray-400 animate-pulse">Connecting...</span>
                )}
                <button
                  onClick={handleCall}
                  disabled={!deviceRef.current && callStatus === "idle"}
                  className={`px-3 py-1.5 text-white text-sm rounded-lg transition flex items-center gap-1.5 ${
                    callStatus === "active" || callStatus === "ringing"
                      ? "bg-red-600 hover:bg-red-700"
                      : callStatus === "connecting"
                      ? "bg-yellow-500"
                      : "bg-[#0d7a3f] hover:bg-green-800"
                  } disabled:opacity-40`}
                >
                  <PhoneIcon />
                  {callStatus === "active" || callStatus === "ringing" ? "Hang Up" : callStatus === "connecting" ? "..." : "Call"}
                </button>
              </div>
            </div>

            {/* Chat Messages */}
            <div className="flex-1 overflow-y-auto px-5 py-4 bg-[#efeae2]">
              {chat.map((msg, i) => (
                <div
                  key={i}
                  className={`flex mb-2 ${msg.role === "user" ? "justify-start" : "justify-end"}`}
                >
                  <div
                    className={`max-w-[75%] px-3 py-2 rounded-lg text-sm whitespace-pre-wrap shadow-sm ${
                      msg.role === "user"
                        ? "bg-white text-gray-900 rounded-tl-none"
                        : msg.content.startsWith("[RM]")
                        ? "bg-blue-500 text-white rounded-tr-none"
                        : "bg-[#d9fdd3] text-gray-900 rounded-tr-none"
                    }`}
                  >
                    {msg.content.startsWith("[RM]") && (
                      <div className="text-[10px] font-bold mb-0.5 opacity-80">RM MESSAGE</div>
                    )}
                    {msg.content.replace("[RM] ", "")}
                    <div className="text-[10px] opacity-40 mt-1 text-right">
                      {msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""}
                    </div>
                  </div>
                </div>
              ))}
              <div ref={chatEndRef} />
            </div>

            {/* Send Message */}
            <div className="px-4 py-3 bg-white border-t border-gray-200 shrink-0">
              <div className="flex gap-2 items-center">
                {/* File Attach Button */}
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
                  className="p-2 text-gray-500 hover:text-[#0d7a3f] hover:bg-green-50 rounded-lg transition disabled:opacity-50"
                  title="Attach file (PDF, image, document)"
                >
                  {uploadingFile ? (
                    <span className="text-xs animate-pulse">...</span>
                  ) : (
                    <AttachIcon />
                  )}
                </button>
                <input
                  type="text"
                  value={sendText}
                  onChange={(e) => setSendText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSend()}
                  placeholder="Type a message or add caption for file..."
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#0d7a3f] focus:border-transparent"
                />
                <button
                  onClick={handleSend}
                  disabled={sending || !sendText.trim()}
                  className="px-4 py-2 bg-[#0d7a3f] text-white rounded-lg text-sm font-medium hover:bg-green-800 disabled:opacity-50 transition"
                >
                  {sending ? "..." : "Send"}
                </button>
              </div>
            </div>
          </div>

          {/* Summary Sidebar */}
          <div className="w-80 bg-white border-l border-gray-200 overflow-y-auto shrink-0">
            <div className="px-4 py-3 border-b border-gray-200">
              <h3 className="font-bold text-sm text-[#0d7a3f]">AI Brief</h3>
            </div>

            {summaryLoading ? (
              <div className="p-4 text-center text-gray-400 text-sm">Generating summary...</div>
            ) : summary ? (
              <div className="p-4 space-y-4">
                {/* Summary */}
                <div>
                  <h4 className="text-xs font-bold text-gray-500 uppercase mb-1">Summary</h4>
                  <p className="text-sm text-gray-800">{summary.summary}</p>
                </div>

                {/* Sentiment */}
                <div>
                  <h4 className="text-xs font-bold text-gray-500 uppercase mb-1">Sentiment</h4>
                  <span
                    className={`px-2 py-0.5 text-xs font-bold rounded ${
                      summary.sentiment === "positive"
                        ? "bg-green-100 text-green-700"
                        : summary.sentiment === "frustrated"
                        ? "bg-red-100 text-red-700"
                        : "bg-gray-100 text-gray-600"
                    }`}
                  >
                    {summary.sentiment}
                  </span>
                </div>

                {/* Talking Points */}
                {summary.talking_points?.length > 0 && (
                  <div>
                    <h4 className="text-xs font-bold text-gray-500 uppercase mb-1">Talking Points</h4>
                    <ul className="space-y-1.5">
                      {summary.talking_points.map((pt, i) => (
                        <li key={i} className="text-sm text-gray-700 flex gap-2">
                          <span className="text-[#0d7a3f] font-bold shrink-0">&#8226;</span>
                          <span>{pt}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Goal Info — Plan Generated */}
                {summary.goal_info?.plan_generated && summary.goal_info.plan_summary && (
                  <div className="bg-green-50 rounded-lg p-3">
                    <h4 className="text-xs font-bold text-[#0d7a3f] uppercase mb-2">Plan Generated</h4>
                    <div className="space-y-1.5 text-xs">
                      <div className="flex justify-between">
                        <span className="text-gray-600">Goal</span>
                        <span className="font-semibold">{summary.goal_info.plan_summary.goal_name}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">SIP Required</span>
                        <span className="font-semibold">
                          &#8377;{summary.goal_info.plan_summary.sip_required?.toLocaleString()}/mo
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Tenure</span>
                        <span className="font-semibold">{summary.goal_info.plan_summary.tenure_years} years</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Risk</span>
                        <span className="font-semibold">{summary.goal_info.plan_summary.risk_label}</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* Goal In Progress */}
                {summary.goal_info?.collected && Object.keys(summary.goal_info.collected).length > 0 && !summary.goal_info.plan_generated && (
                  <div className="bg-yellow-50 rounded-lg p-3">
                    <h4 className="text-xs font-bold text-yellow-700 uppercase mb-2">Goal In Progress</h4>
                    <div className="space-y-1.5 text-xs">
                      {Object.entries(summary.goal_info.collected).map(([key, val]) => (
                        val !== null && (
                          <div key={key} className="flex justify-between">
                            <span className="text-gray-600">{key.replace(/_/g, " ")}</span>
                            <span className="font-semibold">{String(val)}</span>
                          </div>
                        )
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="p-4 text-center text-gray-400 text-sm">Select a user to see AI brief</div>
            )}
          </div>
        </div>
      ) : (
        /* No user selected */
        <div className="flex-1 flex items-center justify-center bg-[#f0f2f5]">
          <div className="text-center">
            <div className="text-6xl mb-4">💬</div>
            <h2 className="text-xl font-bold text-gray-600 mb-2">FundsIndia RM Dashboard</h2>
            <p className="text-gray-400">Select a user from the left panel to view their conversation</p>
          </div>
        </div>
      )}
    </div>
  );
}

function PhoneIcon() {
  return (
    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
    </svg>
  );
}

function AttachIcon() {
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
    </svg>
  );
}
