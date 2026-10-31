import React, { useState, useRef, useEffect } from "react";
import { submitMeeting, getDemoDictation, loadDemoReview } from "../api.js";

const TABS = ["dictate", "paste"];

export default function SpeakScreen({ onReview }) {
  const [tab, setTab] = useState("dictate");
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);
  const [error, setError] = useState(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    if (textareaRef.current) textareaRef.current.focus();
  }, [tab]);

  async function loadDemo() {
    try {
      const data = await getDemoDictation();
      setText(data.text);
      setTab("dictate");
    } catch (e) {
      setError("Could not load demo dictation");
    }
  }

  async function openDemoReview() {
    setDemoLoading(true);
    setError(null);
    try {
      onReview(await loadDemoReview());
    } catch (e) {
      setError(e.message || "Could not load the demo review");
    } finally {
      setDemoLoading(false);
    }
  }

  async function handleSubmit() {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await submitMeeting(text, title || undefined);
      onReview(data);
    } catch (e) {
      setError(e.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">New Meeting</h1>
        <div className="flex gap-2">
          <button
            onClick={loadDemo}
            className="text-sm px-3 py-1.5 rounded border border-violet-500 text-violet-400 hover:bg-violet-900/30 transition-colors"
          >
            Load demo dictation
          </button>
          <button
            onClick={openDemoReview}
            disabled={demoLoading}
            className="text-sm px-3 py-1.5 rounded bg-violet-600 text-white hover:bg-violet-500 disabled:opacity-50 transition-colors"
          >
            {demoLoading ? "Loading…" : "Open ready demo"}
          </button>
        </div>
      </div>

      {/* Title */}
      <input
        type="text"
        placeholder="Meeting title (optional)"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        className="w-full bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-violet-500"
      />

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-800">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`pb-2 px-3 text-sm font-medium transition-colors border-b-2 ${
              tab === t ? "border-violet-500 text-violet-400" : "border-transparent text-gray-500 hover:text-gray-300"
            }`}
          >
            {t === "dictate" ? "🎙 Dictate" : "📄 Paste transcript"}
          </button>
        ))}
      </div>

      {/* Textarea */}
      <textarea
        ref={textareaRef}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={
          tab === "dictate"
            ? "Press your Wispr Flow hotkey and talk through the meeting…"
            : "Paste a speaker-labelled transcript here, e.g.\nPriya: We should launch at $49/month.\nRahul: Agreed, let's do it."
        }
        className="w-full h-64 bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-violet-500 resize-none leading-relaxed"
      />

      {error && (
        <div className="bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">
          {error}
        </div>
      )}

      <button
        onClick={handleSubmit}
        disabled={loading || !text.trim()}
        className="w-full py-3 rounded-xl bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold text-sm transition-colors"
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            Processing meeting…
          </span>
        ) : (
          "Process meeting →"
        )}
      </button>
    </div>
  );
}
