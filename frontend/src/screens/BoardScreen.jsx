import React, { useState, useEffect } from "react";
import { getBoard, getDigest, sendDigest, simulateTime, getNotifications } from "../api.js";

export default function BoardScreen() {
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

  if (loading) return <div className="text-center py-20 text-gray-500">Loading board…</div>;

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Board & Digest</h1>
        <button
          onClick={handleSimulate}
          className="px-3 py-1.5 rounded border border-amber-600 text-amber-400 hover:bg-amber-900/30 text-sm transition-colors"
        >
          🕐 Simulate time
        </button>
      </div>

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
      <div className="grid grid-cols-3 gap-4">
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
            <p className="text-gray-500 text-xs">Open conflicts: {digest.open_conflicts}</p>
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
