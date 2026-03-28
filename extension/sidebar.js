// sidebar.js — Sidebar panel script

const extStatusEl = document.getElementById("ext-status");
const bgStatusEl  = document.getElementById("bg-status");

function badge(text, type) {
  return `<span class="badge ${type}">${text}</span>`;
}

// Mark sidebar as running
extStatusEl.innerHTML = badge("Active", "ok");

// Ping the background service worker to verify the full communication chain
chrome.runtime.sendMessage({ type: "PING" }, (response) => {
  if (chrome.runtime.lastError) {
    bgStatusEl.innerHTML = badge("Unreachable", "err");
    console.error("[sidebar] PING failed:", chrome.runtime.lastError.message);
    return;
  }

  if (response && response.type === "PONG") {
    bgStatusEl.innerHTML = badge("PONG ✓", "ok");
    console.log("[sidebar] PONG received:", response);
  } else {
    bgStatusEl.innerHTML = badge("Unexpected response", "err");
  }
});
