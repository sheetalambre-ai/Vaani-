import React, { useState, useEffect } from "react";
import { getBoard, getDigest, sendDigest, simulateTime, getNotifications } from "../api.js";

export default function BoardScreen({ onNewMeeting }) {
  const [board, setBoard] = useState({});
  const [notifications, setNotifications] = useState([]);
  const [digestPerson, setDigestPerson] = useState("");
  const [digest, setDigest] = useState(null);
  const [simResult, setSimResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    loadAll();
  }, []);

  async function loadAll() {
    setLoading(true);
    try {
      const [b, n] = await Promise.all([getBoard(), getNotifications()]);
      setBoard(b);
      setNotifications(n);
    } catch (e) {
      setError(e.message || "Could not load the board");
    } finally {
      setLoading(false);
    }
  }

  async function handleDigest() {
    if (!digestPerson.trim()) return;
    setError("");
    try {
      const d = await getDigest(digestPerson);
      setDigest(d);
    } catch (e) {
      setError(e.message || "Could not load the digest");
    }
  }

  async function handleSendDigest() {
    if (!digestPerson.trim()) return;
    setError("");
    try {
      await sendDigest(digestPerson);
      await loadAll();
    } catch (e) {
      setError(e.message || "Could not send the digest");
    }
  }

  async function handleSimulate() {
    setError("");
    try {
      const result = await simulateTime();
      setSimResult(result);
      await loadAll();
    } catch (e) {
      setError(e.message || "Could not simulate reminder time");
    }
  }

  const STATUS_ORDER = ["pending_review", "approved", "created", "done", "rejected"];
  const STATUS_LABELS = {
    pending_review: "Pending Review",
    approved: "Approved",
    created: "Created",
    done: "Done",
    rejected: "Rejected",
  };
  const allItems = Object.values(board).flat();
  const pendingCount = allItems.filter((item) => item.status === "pending_review").length;
  const approvedCount = allItems.filter((item) => item.status === "approved" || item.status === "created").length;
  const doneCount = allItems.filter((item) => item.status === "done").length;
  const dueSoonCount = allItems.filter((item) => {
    if (!item.due_date || ["done", "rejected"].includes(item.status)) return false;
    const due = new Date(item.due_date);
    const now = new Date();
    const nextWeek = new Date(now);
    nextWeek.setDate(now.getDate() + 7);
    return due >= new Date(now.toDateString()) && due <= nextWeek;
  }).length;

  if (loading) return <div className="text-center py-20 text-gray-500">Loading board…</div>;

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="screen-eyebrow">Your execution space</p>
          <h1 className="screen-title !text-4xl sm:!text-5xl">Good morning.</h1>
          <p className="screen-subtitle">Here’s what’s moving forward across your meetings.</p>
        </div>
        <div className="flex gap-2 pb-1">
          <button onClick={handleSimulate} className="px-4 py-2.5 rounded-full border border-violet-500 text-violet-400 hover:bg-violet-900/30 text-sm transition-colors">◷ Simulate time</button>
          <button onClick={onNewMeeting} className="px-4 py-2.5 rounded-full bg-violet-600 text-white hover:bg-violet-500 text-sm font-medium">＋ New meeting</button>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <Metric label="Pending review" value={pendingCount} icon="◇" />
        <Metric label="Approved / created" value={approvedCount} icon="↗" />
        <Metric label="Due this week" value={dueSoonCount} icon="◷" />
        <Metric label="Completed" value={doneCount} icon="✓" />
      </div>

      <section className="voice-hero">
        <div className="relative z-10 grid md:grid-cols-[1fr_.8fr] gap-5 items-center p-5 sm:p-7">
          <div>
            <p className="screen-eyebrow">Listen · Understand · Execute</p>
            <h2 className="mt-2 font-serif text-2xl sm:text-3xl text-gray-900">Turn the next conversation into momentum.</h2>
            <p className="mt-2 text-sm text-gray-500">Capture what matters. Vaaniमंथन will help keep every commitment in view.</p>
            <button onClick={onNewMeeting} className="mt-4 px-4 py-2 rounded-full bg-violet-600 text-white text-sm hover:bg-violet-500">Start a meeting →</button>
          </div>
          <BoardWave />
        </div>
      </section>

      {error && (
        <div role="alert" className="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {simResult && (
        <div className="bg-amber-900/20 border border-amber-700/40 text-amber-300 rounded-lg px-4 py-2 text-sm">
          Fired {simResult.fired_reminder_ids?.length || 0} reminder(s)
        </div>
      )}

      {/* Board columns */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {STATUS_ORDER.filter((s) => board[s]?.length > 0).map((status) => (
          <div key={status} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
              {STATUS_LABELS[status]} ({board[status].length})
            </h3>
            <div className="space-y-2">
              {board[status].map((item) => (
                <div key={item.id} className="bg-gray-800 rounded-lg p-3">
                  <p className="text-sm text-white font-medium">{item.task}</p>
                  <div className="flex gap-3 text-xs text-gray-500 mt-1">
                    <span>👤 {item.owner || "—"}</span>
                    <span>📅 {item.due_date || "—"}</span>
                  </div>
                  {item.external_ref && (
                    <a href={item.external_ref} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-400 hover:underline mt-1 block truncate">
                      {item.external_ref}
                    </a>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}
        {Object.keys(board).length === 0 && (
          <div className="col-span-3 text-center py-12 text-gray-600">No items yet</div>
        )}
      </div>

      {/* Digest */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-4">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Weekly Digest</h2>
        <div className="flex gap-2">
          <input
            value={digestPerson}
            onChange={(e) => setDigestPerson(e.target.value)}
            placeholder="Person name (e.g. Priya)"
            className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-violet-500"
          />
          <button onClick={handleDigest} className="px-3 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-sm">View</button>
          <button onClick={handleSendDigest} className="px-3 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-white text-sm">Send now</button>
        </div>
        {digest && (
          <div className="space-y-3 text-sm">
            <p className="text-gray-400">Digest for <span className="text-white font-medium">{digest.person}</span></p>
            <DigestSection label="Due this week" items={digest.due_this_week} />
            <DigestSection label="Overdue" items={digest.overdue} color="red" />
            <DigestSection label="Done" items={digest.done} color="green" />
            {digest.relevant_decisions?.length > 0 && (
              <div>
                <p className="text-gray-500 mb-1">Relevant decisions:</p>
                {digest.relevant_decisions.map((d) => (
                  <p key={d.id} className="text-gray-300">• {d.statement}</p>
                ))}
              </div>
            )}
            <div className="text-xs">
              <p className="text-gray-500 mb-1">Open conflicts affecting {digest.person} ({digest.open_conflicts}):</p>
              {digest.open_conflict_items?.length ? digest.open_conflict_items.map((conflict) => (
                <div key={conflict.id} className="text-amber-300 mb-1">
                  • {conflict.explanation || `${conflict.type} conflict`}
                  {conflict.old_decision && <span className="block text-gray-500 ml-3">Earlier: {conflict.old_decision}</span>}
                  {conflict.new_decision && <span className="block text-gray-500 ml-3">Current: {conflict.new_decision}</span>}
                </div>
              )) : <p className="text-gray-600">None</p>}
            </div>
          </div>
        )}
      </div>

      {/* Notifications */}
      {notifications.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 space-y-3">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Notifications</h2>
          {notifications.slice(0, 10).map((n) => (
            <div key={n.id} className="flex gap-3 text-sm">
              <span className="text-gray-600 text-xs shrink-0 pt-0.5">{new Date(n.created_at).toLocaleTimeString()}</span>
              <p className="text-gray-300">{n.message}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value, icon }) {
  return <div className="metric-card"><div className="flex items-start justify-between"><span className="metric-number">{value}</span><span className="metric-icon">{icon}</span></div><p className="metric-label">{label}</p></div>;
}

function BoardWave() {
  return (
    <svg className="voice-wave" viewBox="0 0 720 180" aria-hidden="true" preserveAspectRatio="none">
      <defs><linearGradient id="boardWaveGradient" x1="0" x2="1"><stop offset="0" stopColor="#e7c7aa" /><stop offset=".5" stopColor="#9180c0" /><stop offset="1" stopColor="#e6c5a6" /></linearGradient></defs>
      <path d="M0 94 C60 90 80 45 145 67 S224 131 292 91 375 43 435 77 522 132 584 99 660 57 720 87" fill="none" stroke="#dcbfa7" strokeWidth="2" opacity=".6" />
      <path d="M0 102 C60 98 86 64 145 79 S226 119 292 97 375 59 435 84 522 121 584 103 660 72 720 94" fill="none" stroke="url(#boardWaveGradient)" strokeWidth="2.4" strokeLinecap="round" />
      <path d="M0 113 C58 112 87 83 146 91 S225 111 292 105 375 80 435 96 521 111 584 109 660 92 720 104" fill="none" stroke="#a99acf" strokeWidth="1.3" opacity=".62" />
    </svg>
  );
}

function DigestSection({ label, items, color = "gray" }) {
  if (!items?.length) return null;
  const colors = { red: "text-red-400", green: "text-green-400", gray: "text-gray-300" };
  return (
    <div>
      <p className="text-gray-500 mb-1">{label} ({items.length}):</p>
      {items.map((i) => (
        <p key={i.id} className={`${colors[color]}`}>• {i.task} {i.due_date ? `(${i.due_date})` : ""}</p>
      ))}
    </div>
  );
}
