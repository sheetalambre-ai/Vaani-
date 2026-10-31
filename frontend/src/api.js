const BASE = "/api";

async function request(path, options) {
  const res = await fetch(`${BASE}${path}`, options);
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      message = body.detail || message;
    } catch {
      // Keep the readable status message when the server did not return JSON.
    }
    throw new Error(message);
  }
  return res.json();
}

export async function submitMeeting(text, title) {
  return request("/meetings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, title }),
  });
}

export async function getReview(meetingId) {
  return request(`/meetings/${meetingId}/review`);
}

export async function approveItem(itemId) {
  return request(`/items/${itemId}/approve`, { method: "POST" });
}

export async function rejectItem(itemId) {
  return request(`/items/${itemId}/reject`, { method: "POST" });
}

export async function patchItem(itemId, data) {
  return request(`/items/${itemId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function submitCorrection(meetingId, spokenText) {
  return request(`/meetings/${meetingId}/correct`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ spoken_text: spokenText }),
  });
}

export async function resolveConflict(conflictId, resolution) {
  return request(`/conflicts/${conflictId}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resolution }),
  });
}

export async function publishMeeting(meetingId) {
  return request(`/meetings/${meetingId}/publish`, { method: "POST" });
}

export async function getBoard() {
  return request("/board");
}

export async function getDigest(person) {
  return request(`/digest/${encodeURIComponent(person)}`);
}

export async function sendDigest(person) {
  return request(`/digest/${encodeURIComponent(person)}/send`, { method: "POST" });
}

export async function simulateTime() {
  return request("/debug/simulate-time", { method: "POST" });
}

export async function getNotifications() {
  return request("/notifications");
}

export async function getDemoDictation() {
  return request("/demo-dictation");
}

export async function loadDemoReview() {
  return request("/demo/review", { method: "POST" });
}
