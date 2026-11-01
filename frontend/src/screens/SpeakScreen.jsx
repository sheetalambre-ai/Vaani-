import React, { useRef, useState } from "react";
import { submitMeeting } from "../api.js";

const SAMPLE_TITLE = "Launch planning · sample";
const SAMPLE_TRANSCRIPT = `Speaker 1: We will launch onboarding on November 21 instead of December 5.\nSpeaker 2: I will publish the onboarding checklist by November 14.\nSpeaker 1: Keep the monthly price at $39 through launch.\nSpeaker 2: I can finish the checklist by Friday—no, make that Thursday.`;

const MODES = [
  { id: "wispr", icon: "◉", title: "Wispr Flow", detail: "Recommended · dictate by voice" },
  { id: "transcript", icon: "▤", title: "Existing transcript", detail: "Upload a text file or paste" },
  { id: "notes", icon: "✎", title: "Manual notes", detail: "Type rough notes in your words" },
];

export default function SpeakScreen({ onReview, onOpenReview }) {
  const [mode, setMode] = useState("wispr");
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [captureStatus, setCaptureStatus] = useState("");
  const [fileName, setFileName] = useState("");
  const textareaRef = useRef(null);
  const fileRef = useRef(null);

  async function handleSubmit() {
    if (!text.trim() || loading) return;
    setLoading(true);
    setError("");
    setCaptureStatus("Vaani is extracting decisions, action items, and cross-meeting conflicts…");
    try {
      const data = await submitMeeting(text, title.trim() || undefined);
      onReview(data);
    } catch (e) {
      setError(e.message || "Could not process this meeting");
      setCaptureStatus("");
    } finally {
      setLoading(false);
    }
  }

  function chooseMode(nextMode) {
    setMode(nextMode);
    setCaptureStatus("");
    requestAnimationFrame(() => textareaRef.current?.focus());
  }

  function focusWisprField() {
    textareaRef.current?.focus();
    setCaptureStatus("Transcript field focused. Use your configured Wispr Flow shortcut to dictate; the words will appear here.");
  }

  async function handleTranscriptFile(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const contents = await file.text();
      setText(contents);
      setFileName(file.name);
      setTitle((current) => current || file.name.replace(/\.[^.]+$/, ""));
      setMode("transcript");
      setCaptureStatus(hasSpeakerLabels(contents)
        ? `Loaded ${file.name}. Speaker labels were found; review them before processing.`
        : `Loaded ${file.name}. No speaker labels found—add “Speaker: words” lines for attribution.`);
      requestAnimationFrame(() => textareaRef.current?.focus());
    } catch {
      setError("Could not read that transcript file. Try a .txt or .md file.");
    } finally {
      event.target.value = "";
    }
  }

  function loadSample() {
    setMode("transcript");
    setTitle(SAMPLE_TITLE);
    setText(SAMPLE_TRANSCRIPT);
    setFileName("");
    setError("");
    setCaptureStatus("Sample loaded locally. Nothing is saved until you choose Process meeting.");
    requestAnimationFrame(() => textareaRef.current?.focus());
  }

  const currentMode = MODES.find((option) => option.id === mode);
  const labelsPresent = hasSpeakerLabels(text);

  return (
    <div className="speak-screen">
      <header className="capture-page-header">
        <div>
          <p className="screen-eyebrow">Meeting-to-execution agent</p>
          <h1 className="screen-title">From conversation to clear action.</h1>
          <p className="screen-subtitle">Start with Wispr Flow, add the conversation, then review what Vaani finds.</p>
        </div>
        <button type="button" className="board-secondary-button sample-load-button" onClick={loadSample}>Try a sample transcript</button>
      </header>

      <ol className="capture-workflow" aria-label="Meeting capture steps">
        <li className="is-current"><span>01</span><div><b>Start meeting</b><small>Name this conversation</small></div></li>
        <li className={text.trim() ? "is-current" : ""}><span>02</span><div><b>Add conversation</b><small>Wispr, transcript, or notes</small></div></li>
        <li><span>03</span><div><b>Extract actions</b><small>Review before anything posts</small></div></li>
      </ol>

      <section className="capture-workspace">
        <aside className="capture-mode-panel">
          <p className="screen-eyebrow">Step 2 · Add conversation</p>
          <h2>Choose your input</h2>
          <div className="capture-mode-list" role="tablist" aria-label="Meeting input type">
            {MODES.map((option) => (
              <button
                key={option.id}
                type="button"
                role="tab"
                aria-selected={mode === option.id}
                className={`capture-mode-option ${mode === option.id ? "is-selected" : ""}`}
                onClick={() => chooseMode(option.id)}
              >
                <span className="capture-mode-icon" aria-hidden="true">{option.icon}</span>
                <span><b>{option.title}</b><small>{option.detail}</small></span>
                <span className="capture-mode-check" aria-hidden="true">{mode === option.id ? "✓" : ""}</span>
              </button>
            ))}
          </div>
          <div className="capture-memory-note"><span aria-hidden="true">✦</span><p><b>After capture</b><br />Vaani compares decisions with your meeting memory, then prepares actions, reminders, and a weekly digest.</p></div>
        </aside>

        <div className="capture-editor">
          <div className="capture-editor-heading">
            <div><p className="screen-eyebrow">New meeting</p><h2>{mode === "wispr" ? "Speak with Wispr Flow" : mode === "transcript" ? "Add an existing transcript" : "Write meeting notes"}</h2></div>
            <span className="capture-private-pill"><span className="status-dot" /> Private until you approve</span>
          </div>

          <label className="capture-title-label" htmlFor="meeting-title">Meeting title <span>Optional</span></label>
          <input id="meeting-title" type="text" placeholder="e.g. Product roadmap sync" value={title} onChange={(event) => setTitle(event.target.value)} className="capture-title-input" />

          {mode === "wispr" && (
            <div className="wispr-live-card">
              <div className="wispr-live-heading"><span className="wispr-mic-icon" aria-hidden="true">♩</span><div><b>Wispr Flow dictation</b><p>Focus this field, then dictate with the Wispr Flow shortcut on your computer.</p></div><span className="live-state"><i /> READY</span></div>
              <div className="wispr-steps">
                <p><span>1</span> Click <b>Focus field for Wispr</b> below.</p>
                <p><span>2</span> On Windows, use the default <b>Ctrl+Win</b> push-to-talk shortcut (hold while speaking). Hands-free defaults to <b>Ctrl+Win+Space</b>.</p>
                <p><span>3</span> Release the shortcut. Wispr Flow inserts your words into the field; say speaker names aloud for attribution.</p>
              </div>
              <p className="wispr-integration-note">Vaani does not open Wispr or request browser microphone access. Wispr Flow handles dictation; Vaani analyzes the text inserted here.</p>
            </div>
          )}

          {mode === "transcript" && (
            <div className="transcript-import-row">
              <div><b>Speaker-labelled transcript</b><small>Use one “Speaker: words” line per turn. Plain .txt and .md files work best.</small></div>
              <input ref={fileRef} type="file" accept=".txt,.md,text/plain,text/markdown" onChange={handleTranscriptFile} className="transcript-file-input" aria-label="Upload a transcript text file" />
              <button type="button" className="board-secondary-button" onClick={() => fileRef.current?.click()}>↑ Upload transcript</button>
            </div>
          )}

          {mode === "notes" && <p className="manual-notes-hint">Write rough notes freely. Vaani will treat unlabeled notes as one speaker; add names like “Speaker 1:” if you know who said what.</p>}

          <div className="live-transcript-heading"><label htmlFor="meeting-transcript">{mode === "wispr" ? "Live transcription area" : mode === "transcript" ? "Transcript text" : "Meeting notes"}</label>{mode === "wispr" && <span className={text ? "transcript-ready" : "transcript-waiting"}>{text ? "● Text received" : "○ Waiting for dictation"}</span>}</div>
          <textarea
            id="meeting-transcript"
            ref={textareaRef}
            value={text}
            onChange={(event) => { setText(event.target.value); setError(""); setCaptureStatus(""); }}
            placeholder={mode === "wispr"
              ? "Click Focus field for Wispr, then use the Wispr Flow hotkey. Dictated words will appear here…"
              : mode === "transcript"
                ? "Paste a transcript here…\nSpeaker 1: We should launch at $49/month.\nSpeaker 2: I’ll own the pricing page by Friday."
                : "Write notes in your own words…\nExample: The team agreed to keep the current price. One person will update the launch checklist by Friday."}
            className="capture-transcript-input"
            spellCheck="true"
          />

          {mode !== "wispr" && text.trim() && <p className={`speaker-check ${labelsPresent ? "has-labels" : "needs-labels"}`}>{labelsPresent ? "✓ Speaker labels detected" : "! No speaker labels detected — Vaani will attribute these notes to Unknown"}</p>}
          {fileName && mode === "transcript" && <p className="file-loaded-note">Loaded locally: <b>{fileName}</b></p>}

          <div className="capture-actions-row">
            {mode === "wispr" ? <button type="button" className="board-secondary-button focus-wispr-button" onClick={focusWisprField}>♩ Focus field for Wispr</button> : <button type="button" className="text-action-button" onClick={() => { setText(""); setFileName(""); setCaptureStatus(""); }}>Clear input</button>}
            <span className="capture-actions-spacer" />
            {mode === "wispr" && <button type="button" className="text-action-button" onClick={loadSample}>Load sample input</button>}
            <button type="button" onClick={handleSubmit} disabled={loading || !text.trim()} className="board-primary-button process-meeting-button">
              {loading ? <><span className="processing-spinner" aria-hidden="true" /> Extracting decisions & actions…</> : "Process meeting →"}
            </button>
          </div>

          {captureStatus && <p className="capture-status" role="status">{captureStatus}</p>}
          {loading && <div className="capture-progress" role="status"><span /><p>Checking decisions against meeting memory and extracting owners and deadlines…</p></div>}
          {error && <div role="alert" className="capture-error">{error}</div>}
          <p className="capture-no-save-note">A sample or transcript stays in this form until you press Process meeting.</p>
        </div>
      </section>

      <footer className="capture-footer"><span>Listen · Understand · Execute</span><button type="button" onClick={() => onOpenReview?.()}>Open review workspace →</button></footer>
    </div>
  );
}

function hasSpeakerLabels(value) {
  return value.split(/\r?\n/).some((line) => /^[^:\n]{1,30}:\s+\S/.test(line.trim()));
}
