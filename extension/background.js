// background.js — Service Worker (Manifest V3)

const BACKEND_URL = "http://localhost:8000";

// ---------------------------------------------------------------------------
// Per-tab state
// { status: "loading" | "ready" | "error" | "not-tc",
//   docId:      string | null,
//   riskReport: Array  | null,
//   sections:   Array  | null,   ← charOffsets for "View Clause"
//   error:      string | null }
// ---------------------------------------------------------------------------
const tabState = new Map();

// ---------------------------------------------------------------------------
// Open the side panel when the extension icon is clicked
// ---------------------------------------------------------------------------
chrome.action.onClicked.addListener((tab) => {
  chrome.sidePanel.open({ tabId: tab.id });
});

// ---------------------------------------------------------------------------
// Ingest helper — called when TC_EXTRACTED arrives from the content script
// ---------------------------------------------------------------------------
async function ingest(tabId, payload) {
  const sections = payload.sections || [];
  tabState.set(tabId, { status: "loading", docId: null, riskReport: null, sections, error: null });

  // Notify sidebar if already open (state (b): analysing)
  chrome.runtime.sendMessage({ type: "INGEST_LOADING" }).catch(() => {});

  try {
    const res = await fetch(`${BACKEND_URL}/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: payload.text, sections }),
    });

    if (!res.ok) {
      const detail = await res.text().catch(() => res.statusText);
      throw new Error(`Ingest failed (${res.status}): ${detail}`);
    }

    const data = await res.json();
    tabState.set(tabId, {
      status: "ready",
      docId: data.doc_id,
      riskReport: data.risk_report,
      sections,
      error: null,
    });

    chrome.runtime.sendMessage({
      type: "INGEST_COMPLETE",
      tabId,
      payload: { docId: data.doc_id, riskReport: data.risk_report, sections },
    }).catch(() => {});
  } catch (err) {
    const message = err.message.includes("Failed to fetch")
      ? "Could not reach TermsGPT backend — is the server running?"
      : err.message;

    tabState.set(tabId, { status: "error", docId: null, riskReport: null, sections: [], error: message });

    chrome.runtime.sendMessage({
      type: "INGEST_ERROR",
      tabId,
      payload: { error: message },
    }).catch(() => {});
  }
}

// ---------------------------------------------------------------------------
// Message router
// ---------------------------------------------------------------------------
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  switch (message.type) {

    // ---- Content script: T&C extracted, start ingest ----------------------
    case "TC_EXTRACTED": {
      const tabId = sender.tab?.id;
      if (!tabId) break;
      ingest(tabId, message.payload);
      break;
    }

    // ---- Content script: not a T&C page -----------------------------------
    case "NOT_TC_PAGE": {
      const tabId = sender.tab?.id;
      if (!tabId) break;
      tabState.set(tabId, { status: "not-tc", docId: null, riskReport: null, sections: [], error: null });
      chrome.runtime.sendMessage({ type: "NOT_TC_PAGE", tabId }).catch(() => {});
      break;
    }

    // ---- Sidebar: opened, wants current state for the active tab ----------
    case "SIDEBAR_READY": {
      chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
        if (!tab) { sendResponse({ type: "NOT_TC_PAGE" }); return; }

        const state = tabState.get(tab.id);
        if (!state) {
          // Content script hasn't reported yet — show "extracting" state
          sendResponse({ type: "INGEST_EXTRACTING" });
          return;
        }
        switch (state.status) {
          case "loading":
            sendResponse({ type: "INGEST_LOADING" });
            break;
          case "ready":
            sendResponse({
              type: "INGEST_COMPLETE",
              payload: { docId: state.docId, riskReport: state.riskReport, sections: state.sections },
            });
            break;
          case "error":
            sendResponse({ type: "INGEST_ERROR", payload: { error: state.error } });
            break;
          case "not-tc":
          default:
            sendResponse({ type: "NOT_TC_PAGE" });
        }
      });
      return true; // async sendResponse
    }

    // ---- Sidebar: freeform query ------------------------------------------
    case "QUERY": {
      const { docId, query } = message.payload;
      fetch(`${BACKEND_URL}/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ doc_id: docId, query }),
      })
        .then((res) => {
          if (!res.ok) return res.text().then((t) => { throw new Error(`Query failed (${res.status}): ${t}`); });
          return res.json();
        })
        .then((data) => sendResponse({ type: "QUERY_RESULT", payload: data }))
        .catch((err) => {
          const msg = err.message.includes("Failed to fetch")
            ? "Could not reach TermsGPT backend — is the server running?"
            : err.message;
          sendResponse({ type: "QUERY_ERROR", payload: { error: msg } });
        });
      return true; // async sendResponse
    }

    // ---- Sidebar: scroll host page to a charOffset ------------------------
    case "SCROLL_TO": {
      const { tabId, charOffset } = message.payload;
      chrome.tabs.sendMessage(tabId, { type: "SCROLL_TO", charOffset }).catch(() => {});
      break;
    }

    // ---- Legacy ping (keep for debugging) ---------------------------------
    case "PING": {
      const source = sender.tab ? `content script (tab ${sender.tab.id})` : "sidebar";
      sendResponse({ type: "PONG", from: "background", echo: source });
      break;
    }
  }

  return false;
});
