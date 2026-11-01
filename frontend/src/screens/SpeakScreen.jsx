import React, { useState, useRef, useEffect } from "react";
import { submitMeeting } from "../api.js";

const TABS = ["dictate", "paste"];

export default function SpeakScreen({ onReview, onOpenReview }) {
  const [tab, setTab] = useState("dictate");
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const textareaRef = useRef(null);

  useEffect(() => {
    if (textareaRef.current) textareaRef.current.focus();
  }, [tab]);

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
    <div className="space-y-8">
      <div className="flex flex-wrap items-end justify-between gap-5">
        <div>
          <p className="screen-eyebrow">Voice intelligence interface</p>
          <h1 className="screen-title">Where conversations<br className="hidden sm:block" /> become action.</h1>
          <p className="screen-subtitle">Capture what was said. Leave with decisions, owners, and a clear next step.</p>
        </div>
      </div>

      <section className="voice-hero">
        <div className="relative z-10 grid lg:grid-cols-[1.05fr_.95fr] gap-6 p-5 sm:p-7 lg:p-9">
          <div className="flex flex-col justify-between min-h-[330px]">
            <div>
              <span className="inline-flex items-center gap-2 rounded-full border border-white/70 bg-white/60 px-3 py-1.5 text-xs text-gray-500 shadow-sm">
                <span className="status-dot" /> Ready when you are
              </span>
              <h2 className="mt-5 max-w-lg font-serif text-3xl sm:text-4xl leading-tight text-gray-900">A better way to remember what matters.</h2>
              <p className="mt-3 max-w-md text-sm leading-6 text-gray-500">Speak naturally. Vaaniमंथन finds decisions, self-corrections, and commitments across your meetings.</p>
            </div>
            <div className="mt-5">
              <VoiceWave />
              <div className="mt-4 flex flex-wrap gap-x-8 gap-y-4">
                <Step label="LISTEN" detail="Capture every voice" icon="♩" />
                <Step label="UNDERSTAND" detail="Find what matters" icon="✦" />
                <Step label="EXECUTE" detail="Turn decisions into action" icon="↗" />
              </div>
            </div>
          </div>

          <div className="paper-card p-4 sm:p-5 flex flex-col">
            <div className="flex items-center justify-between gap-4 mb-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[.14em] text-violet-400">New meeting</p>
                <p className="mt-1 text-sm text-gray-500">Start with your voice or a transcript</p>
              </div>
              <span className="step-orb !w-10 !h-10">✳</span>
            </div>

            <input
              type="text"
              placeholder="Meeting title (optional)"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-violet-500"
            />

            <div className="mt-4 flex gap-2 border-b border-gray-800">
              {TABS.map((t) => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={`pb-2.5 px-3 text-sm font-medium transition-colors border-b-2 ${
                    tab === t ? "border-violet-500 text-violet-400" : "border-transparent text-gray-500 hover:text-gray-300"
                  }`}
                >
                  {t === "dictate" ? "◉ Dictate" : "▤ Paste transcript"}
                </button>
              ))}
            </div>

            <textarea
              ref={textareaRef}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={tab === "dictate" ? "Press your Wispr Flow hotkey and talk through the meeting…" : "Paste a speaker-labelled transcript here, e.g.\nPriya: We should launch at $49/month.\nRahul: Agreed, let's do it."}
              className="mt-3 w-full min-h-[142px] flex-1 bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-sm text-gray-100 placeholder-gray-600 focus:outline-none focus:border-violet-500 resize-y leading-relaxed"
            />

            {error && <div role="alert" className="mt-3 bg-red-900/40 border border-red-700 text-red-300 rounded-lg px-4 py-3 text-sm">{error}</div>}

            <button
              onClick={handleSubmit}
              disabled={loading || !text.trim()}
              className="mt-4 w-full py-3 rounded-full bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold text-sm transition-colors"
            >
              {loading ? "Finding decisions and action items…" : "Process meeting  →"}
            </button>
          </div>
        </div>
      </section>

      <div className="flex flex-wrap items-center justify-between gap-3 px-1 text-xs text-gray-500">
        <span>Private until you choose to publish.</span>
        <button onClick={() => onOpenReview?.()} className="hover:text-violet-400 transition-colors">Go to review workspace →</button>
      </div>
    </div>
  );
}

function Step({ label, detail, icon }) {
  return <div className="step-chip"><span className="step-orb">{icon}</span><span><strong>{label}</strong><small>{detail}</small></span></div>;
}

function VoiceWave() {
  return (
    <svg className="voice-wave max-w-[560px]" viewBox="0 0 920 220" aria-hidden="true" preserveAspectRatio="none">
      <defs><linearGradient id="waveGradient" x1="0" x2="1" y1="0" y2="0"><stop offset="0" stopColor="#e7c7aa" /><stop offset=".48" stopColor="#9180c0" /><stop offset="1" stopColor="#e6c5a6" /></linearGradient></defs>
      <path className="wave-glow" d="M0 117 C90 115 98 74 176 92 S270 157 356 110 456 50 536 88 633 164 716 119 823 64 920 107" />
      <path className="wave-purple" d="M0 128 C74 125 108 94 176 105 S270 146 354 118 442 69 524 97 632 149 712 123 830 82 920 116" />
      <path className="wave-purple" d="M0 105 C86 108 115 143 187 124 S278 77 362 105 452 151 535 125 627 75 711 102 824 146 920 111" />
      <path className="wave-core" d="M0 116 C83 116 121 85 184 99 S280 149 357 115 455 62 535 96 628 153 715 119 831 78 920 112" />
      <path className="wave-glow" d="M0 92 C80 94 126 127 194 113 S281 77 360 94 453 135 538 116 631 81 710 95 831 130 920 101" />
    </svg>
  );
}
