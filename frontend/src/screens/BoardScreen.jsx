import React, { useEffect, useState } from "react";
import { getBoard, getDigest, sendDigest, getNotifications, approveItem, publishItem, completeItem, patchItem } from "../api.js";

const STATUS_ORDER = ["pending_review", "approved", "created", "done"];
const STATUS_META = {
  pending_review: { label: "Needs review", color: "review", icon: "◇", next: "approved" },
  approved: { label: "Approved", color: "approved", icon: "✓", next: "created" },
  created: { label: "Published", color: "published", icon: "↗", next: "done" },
  done: { label: "Completed", color: "done", icon: "✓", next: null },
};

export default function BoardScreen({ onNewMeeting, onOpenReview }) {
  const [board, setBoard] = useState({});
  const [notifications, setNotifications] = useState([]);
  const [digestPerson, setDigestPerson] = useState("");
  const [digest, setDigest] = useState(null);
  const [digestLoading, setDigestLoading] = useState(false);
  const [digestSending, setDigestSending] = useState(false);
  const [busyItemId, setBusyItemId] = useState(null);
  const [dragOverStatus, setDragOverStatus] = useState("");
  const [ownerFilter, setOwnerFilter] = useState("all");
  const [deadlineFilter, setDeadlineFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [editingItem, setEditingItem] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => { loadAll(); }, []);

  async function loadAll() {
    setLoading(true);
    try {
      const [b, n] = await Promise.all([getBoard(), getNotifications()]);
      setBoard(b);
      setNotifications(n);
      setError("");
    } catch (e) {
      setError(e.message || "Could not load the board");
    } finally {
      setLoading(false);
    }
  }

  async function handleOpenReview(item) {
    setError("");
    try { await onOpenReview(item.meeting_id); }
    catch (e) { setError(e.message || "Could not open the meeting review"); }
  }

  async function handleTransition(item, targetStatus) {
    const expected = STATUS_META[item.status]?.next;
    if (!expected || targetStatus !== expected || busyItemId === item.id) return;
    if (targetStatus === "created" && !window.confirm(`Publish only “${item.task}” to the connected tracker?`)) return;
    setBusyItemId(item.id);
    setError("");
    try {
      if (targetStatus === "approved") await approveItem(item.id);
      else if (targetStatus === "created") await publishItem(item.id);
      else if (targetStatus === "done") await completeItem(item.id);
      await loadAll();
    } catch (e) {
      setError(e.message || "Could not move this task");
    } finally {
      setBusyItemId(null);
    }
  }

  async function handleSaveEdit() {
    if (!editingItem) return;
    setBusyItemId(editingItem.id);
    try {
      await patchItem(editingItem.id, {
        task: editingItem.task,
        owner: editingItem.owner || null,
        due_date: editingItem.due_date || null,
      });
      setEditingItem(null);
      await loadAll();
    } catch (e) {
      setError(e.message || "Could not update the task");
    } finally {
      setBusyItemId(null);
    }
  }

  async function handleDigest() {
    if (!digestPerson) return;
    setDigestLoading(true);
    setError("");
    try { setDigest(await getDigest(digestPerson)); }
    catch (e) { setError(e.message || "Could not load the digest"); }
    finally { setDigestLoading(false); }
  }

  async function handleSendDigest() {
    if (!digestPerson || !window.confirm(`Send ${digestPerson}'s weekly digest now?`)) return;
    setDigestSending(true);
    setError("");
    try { await sendDigest(digestPerson); await handleDigest(); }
    catch (e) { setError(e.message || "Could not send the digest"); }
    finally { setDigestSending(false); }
  }

  const allItems = Object.values(board).flat();
  const owners = [...new Set(allItems.filter((item) => item.owner && item.status !== "rejected").map((item) => item.owner.trim()).filter(Boolean))].sort((a, b) => a.localeCompare(b));
  const ownerKey = owners.join("|");
  useEffect(() => {
    if (!owners.length) { setDigestPerson(""); setDigest(null); return; }
    if (!owners.includes(digestPerson)) { setDigestPerson(owners[0]); setDigest(null); }
  }, [ownerKey, digestPerson]);

  const today = startOfToday();
  const weekEnd = new Date(today);
  weekEnd.setDate(weekEnd.getDate() + 7);
  const isOverdue = (item) => item.due_date && !["done", "rejected"].includes(item.status) && dueDate(item.due_date) < today;
  const visibleItems = allItems.filter((item) => {
    if (item.status === "rejected") return false;
    if (ownerFilter !== "all" && item.owner !== ownerFilter) return false;
    if (statusFilter !== "all" && item.status !== statusFilter) return false;
    const due = item.due_date ? dueDate(item.due_date) : null;
    if (deadlineFilter === "overdue" && !isOverdue(item)) return false;
    if (deadlineFilter === "this_week" && (!due || due < today || due > weekEnd || item.status === "done")) return false;
    if (deadlineFilter === "no_date" && due) return false;
    return true;
  });
  const pendingCount = allItems.filter((item) => item.status === "pending_review").length;
  const approvedCount = allItems.filter((item) => item.status === "approved").length;
  const publishedCount = allItems.filter((item) => item.status === "created").length;
  const doneCount = allItems.filter((item) => item.status === "done").length;
  const dueSoonCount = allItems.filter((item) => {
    const due = item.due_date ? dueDate(item.due_date) : null;
    return due && due >= today && due <= weekEnd && !["done", "rejected"].includes(item.status);
  }).length;

  if (loading) return <div className="text-center py-20 text-gray-500">Loading board…</div>;

  return (
    <div className="board-screen space-y-7">
      <div className="board-page-header flex flex-wrap items-end justify-between gap-4">
        <div><p className="screen-eyebrow">Your execution space</p><h1 className="screen-title !text-4xl sm:!text-5xl">Action, with a clear owner.</h1><p className="screen-subtitle">Move approved work forward. Publishing a task always asks you first.</p></div>
        <div className="flex gap-2 pb-1"><button onClick={loadAll} className="board-secondary-button" aria-label="Refresh board">↻ Refresh</button><button onClick={onNewMeeting} className="board-primary-button">＋ New meeting</button></div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 sm:gap-4">
        <Metric label="Needs review" value={pendingCount} icon="◇" color="review" />
        <Metric label="Approved" value={approvedCount} icon="✓" color="approved" />
        <Metric label="Published · in tracker" value={publishedCount} icon="↗" color="active" />
        <Metric label="Due this week" value={dueSoonCount} icon="◷" color="due" />
        <Metric label="Completed" value={doneCount} icon="✓" color="done" />
      </div>

      <section className="board-audio-banner"><div><p className="screen-eyebrow">Listen · Understand · Execute</p><h2>Every promise has a next step.</h2><p>Cross-meeting memory keeps decisions connected to the work that follows.</p></div><BoardWave /></section>

      {error && <div role="alert" className="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">{error}</div>}

      <div className="board-content-grid">
        <section className="board-panel board-lanes-panel">
          <div className="board-panel-heading board-kanban-heading"><div><p className="screen-eyebrow">Execution pipeline</p><h2>Action board</h2></div><span>{visibleItems.length} of {allItems.filter((item) => item.status !== "rejected").length} tasks</span></div>
          <div className="board-filters" aria-label="Filter the action board">
            <label>Teammate<select value={ownerFilter} onChange={(e) => setOwnerFilter(e.target.value)}><option value="all">All members</option>{owners.map((owner) => <option key={owner} value={owner}>{owner}</option>)}</select></label>
            <label>Deadline<select value={deadlineFilter} onChange={(e) => setDeadlineFilter(e.target.value)}><option value="all">Any deadline</option><option value="overdue">Overdue</option><option value="this_week">This week</option><option value="no_date">No deadline</option></select></label>
            <label>Status<select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}><option value="all">All statuses</option>{STATUS_ORDER.map((status) => <option key={status} value={status}>{STATUS_META[status].label}</option>)}</select></label>
            <span className="kanban-drag-hint">Drag a card to advance it · tracker posting asks you to confirm</span>
          </div>
          <div className="board-lanes kanban-lanes">
            {STATUS_ORDER.map((status) => {
              const meta = STATUS_META[status];
              const laneItems = visibleItems.filter((item) => item.status === status);
              return (
                <section key={status} className={`board-lane lane-${meta.color} ${dragOverStatus === status ? "is-drop-target" : ""}`} onDragOver={(event) => { event.preventDefault(); setDragOverStatus(status); }} onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setDragOverStatus(""); }} onDrop={(event) => { event.preventDefault(); setDragOverStatus(""); const id = Number(event.dataTransfer.getData("text/plain")); const item = allItems.find((candidate) => candidate.id === id); if (item) handleTransition(item, status); }}>
                  <header><span className="lane-icon">{meta.icon}</span><span>{meta.label}</span><b>{laneItems.length}</b></header>
                  <div className="kanban-cards">
                    {laneItems.map((item) => (
                      <article className={`board-task ${isOverdue(item) ? "task-is-overdue" : ""} ${item.status === "done" ? "task-is-complete" : ""}`} key={item.id} draggable={Boolean(meta.next)} onDragStart={(event) => { event.dataTransfer.setData("text/plain", String(item.id)); event.dataTransfer.effectAllowed = "move"; }}>
                        {editingItem?.id === item.id ? (
                          <div className="board-task-editor">
                            <input aria-label="Edit task title" value={editingItem.task} onChange={(e) => setEditingItem({ ...editingItem, task: e.target.value })} />
                            <input aria-label="Edit task owner" value={editingItem.owner || ""} onChange={(e) => setEditingItem({ ...editingItem, owner: e.target.value })} placeholder="Owner" />
                            <input aria-label="Edit task deadline" type="date" value={editingItem.due_date || ""} onChange={(e) => setEditingItem({ ...editingItem, due_date: e.target.value })} />
                            <div className="task-edit-actions"><button onClick={handleSaveEdit} disabled={busyItemId === item.id}>Save</button><button onClick={() => setEditingItem(null)}>Cancel</button></div>
                          </div>
                        ) : <>
                          <div className="task-card-topline"><span className="task-drag-grip" aria-hidden="true" title={meta.next ? `Drag to ${STATUS_META[meta.next].label}` : "Completed"}>⠿</span><span className={`task-status-chip status-${item.status}`}>{meta.label}</span>{isOverdue(item) && <span className="overdue-chip">Overdue</span>}</div>
                          <p className="board-task-title">{item.task}</p>
                          <button className="board-task-meeting meeting-link-button" onClick={() => handleOpenReview(item)} title="Open the source meeting">↗ {item.meeting_title}</button>
                          <div className="board-task-meta"><span>♙ {item.owner || "Unassigned"}</span><span className={isOverdue(item) ? "overdue-date" : ""}>◷ {formatDue(item.due_date)}</span></div>
                          <div className="board-task-actions">
                            <button onClick={() => handleOpenReview(item)} className="task-action task-action-review">Review</button>
                            {item.status === "approved" && <button disabled={busyItemId === item.id} onClick={() => handleTransition(item, "created")} className="task-action task-action-publish">Publish ↗</button>}
                            {item.status === "created" && <button disabled={busyItemId === item.id} onClick={() => handleTransition(item, "done")} className="task-action task-action-complete">✓ Complete</button>}
                            {item.status !== "done" && <button onClick={() => setEditingItem({ id: item.id, task: item.task, owner: item.owner || "", due_date: item.due_date || "" })} className="task-action task-action-edit">Edit</button>}
                            {item.external_ref && <a href={item.external_ref} target="_blank" rel="noopener noreferrer" className="task-action task-action-link">Tracker ↗</a>}
                          </div>
                        </>}
                      </article>
                    ))}
                    {!laneItems.length && <p className="board-lane-empty">{statusFilter !== "all" || ownerFilter !== "all" || deadlineFilter !== "all" ? "No matching tasks" : "Drop the next task here"}</p>}
                  </div>
                </section>
              );
            })}
          </div>
          {!allItems.length && <div className="board-empty"><span>✧</span><h3>Your board starts with a conversation.</h3><p>Process a meeting to bring decisions and commitments here.</p><button onClick={onNewMeeting} className="board-primary-button">Start a meeting →</button></div>}
        </section>

        <aside className="board-sidebar">
          <section className="board-panel digest-panel">
            <div className="board-panel-heading"><div><p className="screen-eyebrow">A focused weekly view</p><h2>Weekly digest</h2></div><span className="digest-spark">⌁</span></div>
            <label className="digest-select-label" htmlFor="digest-person">Choose a teammate</label>
            <select id="digest-person" value={digestPerson} onChange={(e) => { setDigestPerson(e.target.value); setDigest(null); }} disabled={!owners.length} className="digest-select">
              {!owners.length && <option value="">No owners yet</option>}{owners.map((person) => <option key={person} value={person}>{person}</option>)}
            </select>
            <div className="digest-actions"><button onClick={handleDigest} disabled={!digestPerson || digestLoading} className="board-primary-button">{digestLoading ? "Loading…" : "View digest →"}</button><button onClick={handleSendDigest} disabled={!digestPerson || digestSending} className="board-secondary-button">{digestSending ? "Sending…" : "Send digest"}</button></div>
            {!owners.length && <p className="digest-empty-note">People appear here when meetings produce owned action items.</p>}
            {digest && <div className="digest-results"><p className="digest-for">Digest for <strong>{digest.person}</strong></p><DigestSection label="Due this week" items={digest.due_this_week} color="due" /><DigestSection label="Overdue" items={digest.overdue} color="red" /><DigestSection label="Done" items={digest.done} color="green" />
              {digest.relevant_decisions?.length > 0 && <div className="digest-detail"><p>Relevant decisions</p>{digest.relevant_decisions.map((d) => <div key={d.id}>{d.statement}</div>)}</div>}
              <div className="digest-detail"><p>Open conflicts · {digest.open_conflicts}</p>{digest.open_conflict_items?.length ? digest.open_conflict_items.map((conflict) => <div className="digest-conflict" key={conflict.id}><span className={`conflict-severity severity-${(conflict.severity || "low").toLowerCase()}`}>{conflict.severity || "Review"} · {conflict.type || "decision"}</span><span>{conflict.explanation || "Earlier and newer decisions need reconciliation."}</span><small>Earlier: {conflict.old_decision}</small><small>New: {conflict.new_decision}</small></div>) : <span className="digest-muted">No open conflicts affecting {digest.person}.</span>}</div>
            </div>}
          </section>
          <section className="board-quote-card"><BoardWave /><p>“The important part of a meeting is what happens next.”</p><span>VAANIमंथन · MEETING MEMORY</span></section>
        </aside>
      </div>

      {notifications.length > 0 && <section className="board-panel notifications-panel"><h2>Notifications</h2>{notifications.slice(0, 5).map((notification) => <p key={notification.id}><small>{new Date(notification.created_at).toLocaleTimeString()}</small>{notification.message}</p>)}</section>}
    </div>
  );
}

function Metric({ label, value, icon, color }) {
  return <div className={`metric-card board-metric metric-${color}`}><div className="flex items-start justify-between"><span className="metric-number">{value}</span><span className="metric-icon">{icon}</span></div><p className="metric-label">{label}</p></div>;
}

function startOfToday() { const today = new Date(); today.setHours(0, 0, 0, 0); return today; }
function dueDate(value) { const date = new Date(`${value.slice(0, 10)}T00:00:00`); return Number.isNaN(date.getTime()) ? null : date; }
function formatDue(value) {
  if (!value) return "No deadline";
  const date = dueDate(value);
  return !date ? value : new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(date);
}

function BoardWave() {
  return <svg className="voice-wave" viewBox="0 0 720 180" aria-hidden="true" preserveAspectRatio="none"><defs><linearGradient id="boardWaveGradient" x1="0" x2="1"><stop offset="0" stopColor="#e7c7aa" /><stop offset=".5" stopColor="#9180c0" /><stop offset="1" stopColor="#e6c5a6" /></linearGradient></defs><path d="M0 94 C60 90 80 45 145 67 S224 131 292 91 375 43 435 77 522 132 584 99 660 57 720 87" fill="none" stroke="#dcbfa7" strokeWidth="2" opacity=".6" /><path d="M0 102 C60 98 86 64 145 79 S226 119 292 97 375 59 435 84 522 121 584 103 660 72 720 94" fill="none" stroke="url(#boardWaveGradient)" strokeWidth="2.4" strokeLinecap="round" /><path d="M0 113 C58 112 87 83 146 91 S225 111 292 105 375 80 435 96 521 111 584 109 660 92 720 104" fill="none" stroke="#a99acf" strokeWidth="1.3" opacity=".62" /></svg>;
}

function DigestSection({ label, items, color = "gray" }) {
  if (!items?.length) return null;
  const colors = { due: "due", red: "red", green: "green", gray: "gray" };
  return <div className={`digest-group digest-${colors[color]}`}><p>{label}<b>{items.length}</b></p>{items.map((item) => <div className="digest-task" key={item.id}><span>{item.task}</span><span className={`digest-status status-${item.status || "pending_review"}`}>{digestStatus(item.status)}</span>{item.due_date ? <small>{formatDue(item.due_date)}</small> : null}</div>)}</div>;
}

function digestStatus(status) {
  return ({ pending_review: "Needs review", approved: "Approved · ready to publish", created: "Published · in tracker", done: "Completed", rejected: "Declined" })[status] || "Needs review";
}
