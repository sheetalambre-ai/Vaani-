import React, { useState, useEffect } from "react";
import { getBoard, getDigest, sendDigest, getNotifications, completeItem } from "../api.js";

const STATUS_ORDER = ["pending_review", "approved", "created", "done", "rejected"];
const STATUS_META = {
  pending_review: { label: "Needs review", color: "review", icon: "◇" },
  approved: { label: "Approved", color: "approved", icon: "✓" },
  created: { label: "Published · in tracker", color: "active", icon: "↗" },
  done: { label: "Completed", color: "done", icon: "✓" },
  rejected: { label: "Declined", color: "rejected", icon: "×" },
};

export default function BoardScreen({ onNewMeeting, onOpenReview }) {
  const [board, setBoard] = useState({});
  const [notifications, setNotifications] = useState([]);
  const [digestPerson, setDigestPerson] = useState("");
  const [digest, setDigest] = useState(null);
  const [digestLoading, setDigestLoading] = useState(false);
  const [digestSending, setDigestSending] = useState(false);
  const [busyItemId, setBusyItemId] = useState(null);
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
    setDigestLoading(true);
    try {
      const d = await getDigest(digestPerson);
      setDigest(d);
    } catch (e) {
      setError(e.message || "Could not load the digest");
    } finally {
      setDigestLoading(false);
    }
  }

  async function handleSendDigest() {
    if (!digestPerson.trim()) return;
    if (!window.confirm(`Send ${digestPerson}'s weekly digest now?`)) return;
    setError("");
    setDigestSending(true);
    try {
      await sendDigest(digestPerson);
      await loadAll();
    } catch (e) {
      setError(e.message || "Could not send the digest");
    } finally {
      setDigestSending(false);
    }
  }

  async function handleOpenReview(item) {
    setError("");
    try {
      await onOpenReview(item.meeting_id);
    } catch (e) {
      setError(e.message || "Could not open the meeting review");
    }
  }

  async function handleComplete(item) {
    setError("");
    setBusyItemId(item.id);
    try {
      await completeItem(item.id);
      await loadAll();
    } catch (e) {
      setError(e.message || "Could not complete the task");
    } finally {
      setBusyItemId(null);
    }
  }

  const allItems = Object.values(board).flat();
  const people = [...new Set(allItems
    .filter((item) => item.owner && item.status !== "rejected")
    .map((item) => item.owner.trim())
    .filter(Boolean))].sort((a, b) => a.localeCompare(b));
  const peopleKey = people.join("|");
  useEffect(() => {
    if (people.length && !people.includes(digestPerson)) {
      setDigestPerson(people[0]);
      setDigest(null);
    }
    if (!people.length) {
      setDigestPerson("");
      setDigest(null);
    }
  }, [peopleKey, digestPerson]);
  const pendingCount = allItems.filter((item) => item.status === "pending_review").length;
  const approvedCount = allItems.filter((item) => item.status === "approved").length;
  const publishedCount = allItems.filter((item) => item.status === "created").length;
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
    <div className="board-screen space-y-7">
      <div className="board-page-header flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="screen-eyebrow">Your execution space</p>
          <h1 className="screen-title !text-4xl sm:!text-5xl">Meetings, into momentum.</h1>
          <p className="screen-subtitle">A clear view of decisions, owners, and what needs to happen next.</p>
        </div>
        <div className="flex gap-2 pb-1">
          <button onClick={loadAll} className="board-secondary-button" aria-label="Refresh board">↻ Refresh</button>
          <button onClick={onNewMeeting} className="board-primary-button">＋ New meeting</button>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 sm:gap-4">
        <Metric label="Needs review" value={pendingCount} icon="◇" color="review" />
        <Metric label="Approved" value={approvedCount} icon="✓" color="approved" />
        <Metric label="Published · in tracker" value={publishedCount} icon="↗" color="active" />
        <Metric label="Due this week" value={dueSoonCount} icon="◷" color="due" />
        <Metric label="Completed" value={doneCount} icon="✓" color="done" />
      </div>

      <section className="board-audio-banner">
        <div><p className="screen-eyebrow">Listen · Understand · Execute</p><h2>Every promise has a next step.</h2><p>Decisions stay connected to the people and deadlines that move them forward.</p></div>
        <BoardWave />
      </section>

      {error && (
        <div role="alert" className="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">
          {error}
        </div>
      )}

      <div className="board-content-grid">
        <section className="board-panel board-lanes-panel">
          <div className="board-panel-heading"><div><p className="screen-eyebrow">From conversation to action</p><h2>Action board</h2></div><span>{allItems.length} commitments</span></div>
          <div className="board-lanes">
            {STATUS_ORDER.map((status) => {
              const meta = STATUS_META[status];
              const laneItems = board[status] || [];
              return <section key={status} className={`board-lane lane-${meta.color}`}>
                <header><span className="lane-icon">{meta.icon}</span><span>{meta.label}</span><b>{laneItems.length}</b></header>
                {laneItems.length ? laneItems.map((item) => <article className="board-task" key={item.id}>
                  <p className="board-task-title">{item.task}</p>
                  <p className="board-task-meeting">{item.meeting_title}</p>
                  <div className="board-task-meta"><span>♙ {item.owner || "Unassigned"}</span><span>◷ {formatDue(item.due_date)}</span></div>
                  <div className="board-task-actions">
                    {status === "created" ? <button disabled={busyItemId === item.id} onClick={() => handleComplete(item)} className="task-action task-action-complete">{busyItemId === item.id ? "Saving…" : "✓ Mark complete"}</button> : status === "pending_review" || status === "approved" ? <button onClick={() => handleOpenReview(item)} className="task-action task-action-review">Review meeting →</button> : null}
                    {item.external_ref && <a href={item.external_ref} target="_blank" rel="noopener noreferrer" className="task-action task-action-link">Open tracker ↗</a>}
                  </div>
                </article>) : <p className="board-lane-empty">Nothing here yet</p>}
              </section>;
            })}
          </div>
          {!allItems.length && <div className="board-empty"><span>✧</span><h3>Your board starts with a conversation.</h3><p>Process a meeting to bring its decisions and commitments here.</p><button onClick={onNewMeeting} className="board-primary-button">Start a meeting →</button></div>}
        </section>

        <aside className="board-sidebar">
          <section className="board-panel digest-panel">
            <div className="board-panel-heading"><div><p className="screen-eyebrow">A focused weekly view</p><h2>Weekly digest</h2></div><span className="digest-spark">⌁</span></div>
            <label className="digest-select-label" htmlFor="digest-person">Choose a teammate</label>
            <select id="digest-person" value={digestPerson} onChange={(e) => { setDigestPerson(e.target.value); setDigest(null); }} disabled={!people.length} className="digest-select">
              {!people.length && <option value="">No owners yet</option>}
              {people.map((person) => <option key={person} value={person}>{person}</option>)}
            </select>
            <div className="digest-actions">
              <button onClick={handleDigest} disabled={!digestPerson || digestLoading} className="board-primary-button">{digestLoading ? "Loading…" : "View digest →"}</button>
              <button onClick={handleSendDigest} disabled={!digestPerson || digestSending} className="board-secondary-button">{digestSending ? "Sending…" : "Send digest"}</button>
            </div>
            {!people.length && <p className="digest-empty-note">People appear here when meetings produce owned action items.</p>}
        {digest && (
          <div className="digest-results">
            <p className="digest-for">Digest for <strong>{digest.person}</strong></p>
            <DigestSection label="Due this week" items={digest.due_this_week} color="due" />
            <DigestSection label="Overdue" items={digest.overdue} color="red" />
            <DigestSection label="Done" items={digest.done} color="green" />
            {digest.relevant_decisions?.length > 0 && <div className="digest-detail"><p>Relevant decisions</p>{digest.relevant_decisions.map((d) => <div key={d.id}>{d.statement}</div>)}</div>}
            <div className="digest-detail"><p>Open conflicts · {digest.open_conflicts}</p>{digest.open_conflict_items?.length ? digest.open_conflict_items.map((conflict) => <div className="digest-conflict" key={conflict.id}>
              <span className={`conflict-severity severity-${(conflict.severity || "low").toLowerCase()}`}>{conflict.severity || "Review"} · {conflict.type || "decision"}</span>
              <span>{conflict.explanation || "Earlier and newer decisions need reconciliation."}</span>
              <small>Earlier: {conflict.old_decision}</small><small>New: {conflict.new_decision}</small>
            </div>) : <span className="digest-muted">No open conflicts affecting {digest.person}.</span>}</div>
          </div>
        )}
          </section>
          <section className="board-quote-card"><BoardWave /><p>“The important part of a meeting is what happens next.”</p><span>VAANIमंथन · MEETING MEMORY</span></section>
        </aside>
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

function Metric({ label, value, icon, color }) {
  return <div className={`metric-card board-metric metric-${color}`}><div className="flex items-start justify-between"><span className="metric-number">{value}</span><span className="metric-icon">{icon}</span></div><p className="metric-label">{label}</p></div>;
}

function formatDue(value) {
  if (!value) return "No deadline";
  const date = new Date(`${value.slice(0, 10)}T00:00:00`);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(date);
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
  const colors = { due: "due", red: "red", green: "green", gray: "gray" };
  return (
    <div className={`digest-group digest-${colors[color]}`}>
      <p>{label}<b>{items.length}</b></p>
      {items.map((i) => (
        <div className="digest-task" key={i.id}>
          <span>{i.task}</span>
          <span className={`digest-status status-${i.status || "pending_review"}`}>{digestStatus(i.status)}</span>
          {i.due_date ? <small>{formatDue(i.due_date)}</small> : null}
        </div>
      ))}
    </div>
  );
}

function digestStatus(status) {
  return ({
    pending_review: "Needs review",
    approved: "Approved · ready to publish",
    created: "Published · in tracker",
    done: "Completed",
    rejected: "Declined",
  })[status] || "Needs review";
}
