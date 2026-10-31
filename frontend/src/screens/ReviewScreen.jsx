import React, { useEffect, useState } from "react";
import {
  approveItem, rejectItem, patchItem,
  resolveConflict, publishMeeting, submitCorrection, getReview,
} from "../api.js";

export default function ReviewScreen({ data: initialData, onPublished, onLoadDemo }) {
  const [data, setData] = useState(initialData);
  const [correction, setCorrection] = useState("");
  const [toast, setToast] = useState(null);
  const [publishing, setPublishing] = useState(false);
  const [editingItem, setEditingItem] = useState(null); // {id, task, owner, due_date}
  const [demoLoading, setDemoLoading] = useState(false);
  const [demoError, setDemoError] = useState("");

  useEffect(() => {
    if (initialData) setData(initialData);
  }, [initialData]);

  async function handleLoadDemo() {
    setDemoLoading(true);
    setDemoError("");
    try {
      await onLoadDemo();
    } catch (e) {
      setDemoError(e.message || "Could not load the demo review");
    } finally {
      setDemoLoading(false);
    }
  }

  if (!data) {
    return (
      <div className="max-w-xl mx-auto text-center py-20 space-y-4">
        <p className="text-gray-400">No meeting is open for review.</p>
        <p className="text-sm text-gray-500">Load the seeded walkthrough to see decisions, conflicts, corrections, and action items without an API key.</p>
        {demoError && <p role="alert" className="text-sm text-red-300">{demoError}</p>}
        <button onClick={handleLoadDemo} disabled={demoLoading} className="px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white text-sm font-medium">
          {demoLoading ? "Loading demo…" : "Open demo review"}
        </button>
      </div>
    );
  }

  async function refresh() {
    const updated = await getReview(data.meeting_id);
    setData(updated);
  }

  function showToast(msg, type = "success") {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  }

  async function handleApprove(id) {
    try {
      await approveItem(id);
      await refresh();
      showToast("Item approved");
    } catch (e) {
      showToast(e.message || "Could not approve item", "error");
    }
  }

  async function handleReject(id) {
    try {
      await rejectItem(id);
      await refresh();
      showToast("Item rejected", "warn");
    } catch (e) {
      showToast(e.message || "Could not reject item", "error");
    }
  }

  async function handleSaveEdit() {
    try {
      const { id, ...fields } = editingItem;
      await patchItem(id, fields);
      setEditingItem(null);
      await refresh();
      showToast("Item updated");
    } catch (e) {
      showToast(e.message || "Could not update item", "error");
    }
  }

  async function handleResolve(conflictId, resolution) {
    try {
      await resolveConflict(conflictId, resolution);
      await refresh();
      showToast(resolution === "accepted_new" ? "New decision accepted" : "Old decision kept");
    } catch (e) {
      showToast(e.message || "Could not resolve conflict", "error");
    }
  }

  async function handleCorrection() {
    if (!correction.trim()) return;
    try {
      const result = await submitCorrection(data.meeting_id, correction);
      setCorrection("");
      await refresh();
      const patch = result.patch;
      showToast(`Changed ${patch.field}: "${result.old_value}" → "${result.new_value}"`);
    } catch (e) {
      showToast(e.message, "error");
    }
  }

  async function handlePublish() {
    setPublishing(true);
    try {
      const result = await publishMeeting(data.meeting_id);
      await refresh();
      showToast(`Published ${result.published.length} item(s)`);
      setTimeout(onPublished, 1500);
    } catch (e) {
      showToast(e.message, "error");
    } finally {
      setPublishing(false);
    }
  }

  const approvedCount = data.action_items.filter((a) => a.status === "approved").length;

  return (
    <div className="review-screen space-y-7">
      {/* Toast */}
      {toast && (
        <div
          className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg text-sm shadow-lg ${
            toast.type === "error"
              ? "bg-red-800 text-red-100"
              : toast.type === "warn"
              ? "bg-amber-800 text-amber-100"
              : "bg-green-800 text-green-100"
          }`}
        >
          {toast.msg}
        </div>
      )}

      {/* Header */}
      <div className="review-header flex items-center justify-between">
        <div>
          <p className="screen-eyebrow">Meeting review · private until approved</p>
          <h1 className="screen-title !text-3xl !m-0">{data.title}</h1>
          <p className="review-date text-sm text-gray-500 mt-1">{new Date(data.held_at).toLocaleString()}</p>
        </div>
        <button
          onClick={handlePublish}
          disabled={publishing || approvedCount === 0}
          className="publish-button px-5 py-2.5 rounded-full bg-violet-600 hover:bg-violet-500 disabled:opacity-40 text-white font-semibold text-sm transition-colors"
        >
          {publishing ? "Publishing…" : `Publish ${approvedCount} approved item${approvedCount !== 1 ? "s" : ""}`}
        </button>
      </div>

      {/* Voice correction */}
      <div className="review-correction flex gap-2 bg-gray-900 border border-gray-700 rounded-xl p-3">
        <input
          value={correction}
          onChange={(e) => setCorrection(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleCorrection()}
          placeholder='Voice correction: "make that Friday" or "Rahul owns the API task"'
          className="flex-1 bg-transparent text-sm text-gray-200 placeholder-gray-600 focus:outline-none"
        />
        <button
          onClick={handleCorrection}
          className="px-3 py-1 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-sm"
        >
          Apply
        </button>
      </div>

      {/* Raw vs Cleaned */}
      <div className="review-transcripts grid grid-cols-2 gap-4">
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Raw input</p>
          <p className="text-sm text-gray-400 leading-relaxed whitespace-pre-wrap">{data.raw_input}</p>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
          <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Cleaned transcript</p>
          <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">{data.cleaned_transcript}</p>
        </div>
      </div>

      {/* Self-corrections */}
      {data.corrections?.length > 0 && (
        <Section title="Self-corrections detected">
          {data.corrections.map((c, i) => (
            <div key={i} className="bg-gray-900 border border-amber-700/40 rounded-xl p-4 text-sm">
              <span className="text-amber-400 font-medium">{c.field}:</span>{" "}
              <span className="line-through text-gray-500">{c.old_value}</span>{" → "}
              <span className="text-green-400">{c.new_value}</span>
              <p className="text-gray-500 text-xs mt-1 italic">"{c.spoken_text}"</p>
            </div>
          ))}
        </Section>
      )}

      {/* Conflicts */}
      {data.conflicts?.length > 0 && (
        <Section className="review-conflicts" title={`Conflict check · ${data.conflicts.length}`}>
          {data.conflicts.map((c) => {
            const newD = data.decisions.find((d) => d.id === c.new_decision_id);
            const oldD = data.decisions.find((d) => d.id === c.old_decision_id);
            return (
              <div key={c.id} className="review-conflict-card bg-gray-900 border border-red-700/50 rounded-xl p-4 space-y-3">
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded text-xs font-semibold uppercase ${
                    c.severity === "high" ? "bg-red-700 text-red-100" :
                    c.severity === "medium" ? "bg-amber-700 text-amber-100" : "bg-yellow-800 text-yellow-100"
                  }`}>{c.severity}</span>
                  <span className="text-sm text-red-300 font-medium capitalize">{c.type}</span>
                  {c.resolution !== "open" && (
                    <span className="ml-auto text-xs text-gray-500">Resolved: {c.resolution}</span>
                  )}
                </div>
                <p className="text-sm text-gray-300">{c.explanation}</p>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="bg-gray-800 rounded-lg p-3">
                    <p className="text-gray-500 mb-1">New decision</p>
                    <p className="text-white">{newD?.statement || `ID ${c.new_decision_id}`}</p>
                    {newD?.evidence_quote && <p className="text-gray-500 italic mt-1">"{newD.evidence_quote}"</p>}
                  </div>
                  <div className="bg-gray-800 rounded-lg p-3">
                    <p className="text-gray-500 mb-1">Old decision</p>
                    <p className="text-white">{oldD?.statement || `ID ${c.old_decision_id}`}</p>
                    {oldD?.evidence_quote && <p className="text-gray-500 italic mt-1">"{oldD.evidence_quote}"</p>}
                  </div>
                </div>
                {c.resolution === "open" && (
                  <div className="flex gap-2">
                    <button onClick={() => handleResolve(c.id, "accepted_new")} className="conflict-accept flex-1 py-1.5 rounded-lg bg-blue-700 hover:bg-blue-600 text-white text-xs font-medium">Keep new decision</button>
                    <button onClick={() => handleResolve(c.id, "kept_old")} className="conflict-keep flex-1 py-1.5 rounded-lg bg-gray-700 hover:bg-gray-600 text-white text-xs font-medium">Keep earlier decision</button>
                  </div>
                )}
              </div>
            );
          })}
        </Section>
      )}

      <div className="review-grid">
      {/* Decisions */}
      {data.decisions?.length > 0 && (
        <Section className="review-decisions" title={`Decisions · ${data.decisions.length}`}>
          {data.decisions.map((d) => (
            <div key={d.id} className={`review-decision-card bg-gray-900 border border-gray-700 rounded-xl p-4 space-y-1 ${d.status === "conflicted" ? "is-conflicted" : d.status === "superseded" ? "is-superseded" : "is-active"}`}>
              <p className="text-sm font-medium text-white">{d.statement}</p>
              {d.evidence_quote && <p className="text-xs text-gray-500 italic">"{d.evidence_quote}"</p>}
              {d.decided_by && <p className="text-xs text-gray-600">Decided by: {d.decided_by}</p>}
              <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                d.status === "conflicted" ? "bg-red-900/40 text-red-300" :
                d.status === "superseded" ? "bg-gray-700 text-gray-400" : "bg-green-900/40 text-green-300"
              }`}>{d.status}</span>
            </div>
          ))}
        </Section>
      )}

      {/* Action Items */}
      {data.action_items?.length > 0 && (
        <Section className="review-actions" title={`Action items · ${data.action_items.length}`}>
          {data.action_items.map((a) => (
            <div key={a.id} className={`review-action-card bg-gray-900 border border-gray-700 rounded-xl p-4 space-y-2 status-${a.status}`}>
              {editingItem?.id === a.id ? (
                <div className="space-y-2">
                  <input className="w-full bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none" value={editingItem.task} onChange={(e) => setEditingItem({ ...editingItem, task: e.target.value })} placeholder="Task" />
                  <div className="grid grid-cols-2 gap-2">
                    <input className="bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none" value={editingItem.owner || ""} onChange={(e) => setEditingItem({ ...editingItem, owner: e.target.value })} placeholder="Owner" />
                    <input className="bg-gray-800 border border-gray-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none" value={editingItem.due_date || ""} onChange={(e) => setEditingItem({ ...editingItem, due_date: e.target.value })} placeholder="Due date (YYYY-MM-DD)" />
                  </div>
                  <div className="flex gap-2">
                    <button onClick={handleSaveEdit} className="px-3 py-1 rounded bg-violet-600 hover:bg-violet-500 text-white text-xs">Save</button>
                    <button onClick={() => setEditingItem(null)} className="px-3 py-1 rounded bg-gray-700 hover:bg-gray-600 text-white text-xs">Cancel</button>
                  </div>
                </div>
              ) : (
                <>
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium text-white">{a.task}</p>
                    <StatusBadge status={a.status} missingFields={a.missing_fields} />
                  </div>
                  <div className="flex gap-4 text-xs text-gray-400">
                    <span>👤 {a.owner || <span className="text-amber-400">No owner</span>}</span>
                    <span>📅 {a.due_date || <span className="text-amber-400">No date</span>}</span>
                  </div>
                  {a.done_definition && <p className="text-xs text-gray-500">Done when: {a.done_definition}</p>}
                  {a.evidence_quote && <p className="text-xs text-gray-600 italic">"{a.evidence_quote}"</p>}
                  {a.status === "pending_review" && (
                    <div className="review-item-actions">
                      <button onClick={() => handleApprove(a.id)} className="action-button action-approve px-3 py-1.5 rounded-lg bg-green-700 hover:bg-green-600 text-white text-xs font-semibold">✓ Approve</button>
                      <button onClick={() => setEditingItem({ id: a.id, task: a.task, owner: a.owner, due_date: a.due_date })} className="action-button action-edit px-3 py-1.5 rounded-lg bg-gray-700 hover:bg-gray-600 text-white text-xs font-semibold">✎ Edit</button>
                      <button onClick={() => handleReject(a.id)} className="action-button action-reject px-3 py-1.5 rounded-lg bg-red-900 hover:bg-red-800 text-white text-xs font-semibold">× Reject</button>
                    </div>
                  )}
                </>
              )}
            </div>
          ))}
        </Section>
      )}
      </div>
    </div>
  );
}

function Section({ title, children, className = "" }) {
  return (
    <section className={`review-section ${className}`}>
      <h2 className="review-section-title text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">{title}</h2>
      <div className="review-section-content space-y-3">{children}</div>
    </section>
  );
}

function StatusBadge({ status, missingFields }) {
  const hasMissing = missingFields?.length > 0;
  if (hasMissing && status === "pending_review") {
    return (
      <span className="shrink-0 px-2 py-0.5 rounded text-xs font-semibold bg-amber-900/40 text-amber-300 border border-amber-700/50">
        Needs info
      </span>
    );
  }
  const map = {
    approved: "bg-green-900/40 text-green-300",
    rejected: "bg-red-900/40 text-red-400",
    created: "bg-blue-900/40 text-blue-300",
    done: "bg-gray-700 text-gray-300",
    pending_review: "bg-gray-800 text-gray-400",
  };
  return (
    <span className={`shrink-0 px-2 py-0.5 rounded text-xs font-medium capitalize ${map[status] || "bg-gray-800 text-gray-400"}`}>
      {status.replace("_", " ")}
    </span>
  );
}
