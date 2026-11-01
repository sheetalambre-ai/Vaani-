import React, { useState } from "react";
import SpeakScreen from "./screens/SpeakScreen.jsx";
import ReviewScreen from "./screens/ReviewScreen.jsx";
import BoardScreen from "./screens/BoardScreen.jsx";
import { getReview } from "./api.js";

export default function App() {
  const [screen, setScreen] = useState("speak"); // speak | review | board
  const [reviewData, setReviewData] = useState(null);

  const nav = (s) => setScreen(s);

  async function openMeetingReview(meetingId) {
    const review = await getReview(meetingId);
    setReviewData(review);
    setScreen("review");
  }

  return (
    <div className="app-shell min-h-screen font-sans">
      <header className="app-topbar">
        <button className="wordmark" onClick={() => nav("speak")} aria-label="Vaaniमंथन home">
          Vaani<span>मंथन</span>
        </button>
        <nav className="app-nav" aria-label="Main navigation">
          {["speak", "review", "board"].map((s) => (
            <button
              key={s}
              onClick={() => nav(s)}
              className={`nav-link ${screen === s ? "nav-link-active" : ""}`}
            >
              <span className="nav-link-icon" aria-hidden="true">
                {s === "speak" ? "◉" : s === "review" ? "◇" : "▦"}
              </span>
              {s === "speak" ? "Speak" : s === "review" ? "Review" : "Board"}
            </button>
          ))}
        </nav>
        <div className="topbar-note"><span className="status-dot" /> Voice intelligence workspace</div>
      </header>

      {/* Screens */}
      <main className="app-main">
        {screen === "speak" && (
          <SpeakScreen
            onReview={(data) => {
              setReviewData(data);
              setScreen("review");
            }}
            onOpenReview={() => setScreen("review")}
          />
        )}
        {screen === "review" && (
          <ReviewScreen
            data={reviewData}
            onNewMeeting={() => setScreen("speak")}
            onPublished={() => setScreen("board")}
          />
        )}
        {screen === "board" && <BoardScreen onNewMeeting={() => setScreen("speak")} onOpenReview={openMeetingReview} />}
      </main>
      <footer className="app-footer"><span>Vaaniमंथन</span><span>Listen · Understand · Execute</span></footer>
    </div>
  );
}
