import React, { useState } from "react";
import SpeakScreen from "./screens/SpeakScreen.jsx";
import ReviewScreen from "./screens/ReviewScreen.jsx";
import BoardScreen from "./screens/BoardScreen.jsx";
import { loadDemoReview } from "./api.js";

export default function App() {
  const [screen, setScreen] = useState("speak"); // speak | review | board
  const [reviewData, setReviewData] = useState(null);

  const nav = (s) => setScreen(s);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 font-sans">
      {/* Nav */}
      <nav className="flex items-center gap-1 px-6 py-3 border-b border-gray-800 bg-gray-900">
        <span className="text-violet-400 font-bold text-lg mr-6">Vaaniमंथन</span>
        {["speak", "review", "board"].map((s) => (
          <button
            key={s}
            onClick={() => nav(s)}
            className={`px-4 py-1.5 rounded text-sm font-medium transition-colors ${
              screen === s
                ? "bg-violet-600 text-white"
                : "text-gray-400 hover:text-white hover:bg-gray-800"
            }`}
          >
            {s === "speak" ? "🎙 Speak" : s === "review" ? "📋 Review" : "📊 Board"}
          </button>
        ))}
      </nav>

      {/* Screens */}
      <main className="max-w-5xl mx-auto px-4 py-8">
        {screen === "speak" && (
          <SpeakScreen
            onReview={(data) => {
              setReviewData(data);
              setScreen("review");
            }}
          />
        )}
        {screen === "review" && (
          <ReviewScreen
            data={reviewData}
            onLoadDemo={async () => setReviewData(await loadDemoReview())}
            onPublished={() => setScreen("board")}
          />
        )}
        {screen === "board" && <BoardScreen />}
      </main>
    </div>
  );
}
