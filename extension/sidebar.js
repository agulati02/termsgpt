// sidebar.js — Sidebar panel script

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let currentDocId   = null;
let currentTabId   = null;
let currentSections = [];  // [{ heading, charOffset }] — for "View Clause" lookups

// ---------------------------------------------------------------------------
// DOM refs
// ---------------------------------------------------------------------------
const statusBar    = document.getElementById("status-bar");
const statusText   = document.getElementById("status-text");
const stateNotTc   = document.getElementById("state-not-tc");
const stateError   = document.getElementById("state-error");
const mainContent  = document.getElementById("main-content");

const riskList     = document.getElementById("risk-list");
const messageList  = document.getElementById("message-list");
const queryInput   = document.getElementById("query-input");
const querySubmit  = document.getElementById("query-submit");

// ---------------------------------------------------------------------------
// UI state transitions
// ---------------------------------------------------------------------------
function showStatus(text) {
  statusBar.classList.remove("hidden");
  statusText.textContent = text;
  stateNotTc.classList.add("hidden");
  stateError.classList.add("hidden");
  mainContent.classList.add("hidden");
}

function showNotTc() {
  statusBar.classList.add("hidden");
  stateNotTc.classList.remove("hidden");
  stateError.classList.add("hidden");
  mainContent.classList.add("hidden");
}

function showError(msg) {
  statusBar.classList.add("hidden");
  stateNotTc.classList.add("hidden");
  stateError.classList.remove("hidden");
  stateError.textContent = msg;
  mainContent.classList.add("hidden");
}

function showReady() {
  statusBar.classList.add("hidden");
  stateNotTc.classList.add("hidden");
  stateError.classList.add("hidden");
  mainContent.classList.remove("hidden");
}

// ---------------------------------------------------------------------------
// Risk dashboard
// ---------------------------------------------------------------------------
function renderRiskReport(riskReport) {
  riskList.innerHTML = "";
  for (const entry of riskReport) {
    const charOffset = resolveCharOffset(entry.citation?.heading);
    const viewClause = charOffset !== null
      ? `<a class="view-clause" href="#" data-offset="${charOffset}">View Clause</a>`
      : "";

    const item = document.createElement("div");
    item.className = "risk-item";
    item.innerHTML = `
      <div class="severity-badge">${entry.severity}</div>
      <div class="risk-body">
        <div class="risk-header">
          <span class="risk-category">${escapeHtml(entry.category)}</span>
          ${viewClause}
        </div>
        <div class="risk-finding">${escapeHtml(entry.finding)}</div>
      </div>`;
    riskList.appendChild(item);
  }
}

function resolveCharOffset(heading) {
  if (!heading || !currentSections.length) return null;
  const match = currentSections.find(
    (s) => s.heading.toLowerCase() === heading.toLowerCase()
  );
  return match ? match.charOffset : null;
}

// Delegate click handling to the list container
riskList.addEventListener("click", (e) => {
  const link = e.target.closest(".view-clause");
  if (!link) return;
  e.preventDefault();
  const charOffset = parseInt(link.dataset.offset, 10);
  if (!isNaN(charOffset) && currentTabId !== null) {
    chrome.runtime.sendMessage({
      type: "SCROLL_TO",
      payload: { tabId: currentTabId, charOffset },
    });
  }
});

// ---------------------------------------------------------------------------
// Chat interface
// ---------------------------------------------------------------------------
function appendUserMessage(text) {
  const el = document.createElement("div");
  el.className = "message user";
  el.innerHTML = `<div class="bubble">${escapeHtml(text)}</div>`;
  messageList.appendChild(el);
  scrollChat();
  return el;
}

function appendThinkingBubble() {
  const el = document.createElement("div");
  el.className = "message assistant";
  el.innerHTML = `<div class="bubble thinking">Searching…</div>`;
  messageList.appendChild(el);
  scrollChat();
  return el;
}

function replaceThinkingBubble(thinkingEl, data) {
  const citations = (data.citations || []).filter((c) => c.heading || c.snippet);
  let sourcesHtml = "";
  if (citations.length) {
    const items = citations
      .map(
        (c) => `
        <div class="citation-entry">
          ${c.heading ? `<strong>${escapeHtml(c.heading)}</strong>` : ""}
          ${c.snippet ? escapeHtml(truncate(c.snippet, 140)) : ""}
        </div>`
      )
      .join("");
    sourcesHtml = `<details class="sources"><summary>Sources (${citations.length})</summary>${items}</details>`;
  }

  thinkingEl.innerHTML = `
    <div class="bubble">
      ${escapeHtml(data.answer)}
      ${sourcesHtml}
    </div>`;
  scrollChat();
}

function appendErrorMessage(msg) {
  const el = document.createElement("div");
  el.className = "message assistant";
  el.innerHTML = `<div class="bubble thinking">${escapeHtml(msg)}</div>`;
  messageList.appendChild(el);
  scrollChat();
}

function scrollChat() {
  messageList.scrollTop = messageList.scrollHeight;
}

// ---------------------------------------------------------------------------
// Query submission
// ---------------------------------------------------------------------------
querySubmit.addEventListener("click", submitQuery);
queryInput.addEventListener("keydown", (e) => { if (e.key === "Enter") submitQuery(); });

function submitQuery() {
  const q = queryInput.value.trim();
  if (!q || !currentDocId) return;

  queryInput.value = "";
  querySubmit.disabled = true;

  appendUserMessage(q);
  const thinkingEl = appendThinkingBubble(); // state (c): answering

  chrome.runtime.sendMessage(
    { type: "QUERY", payload: { docId: currentDocId, query: q } },
    (response) => {
      querySubmit.disabled = false;

      if (chrome.runtime.lastError) {
        replaceThinkingBubble(thinkingEl, {
          answer: "Could not reach TermsGPT backend — is the server running?",
          citations: [],
        });
        return;
      }

      if (response.type === "QUERY_RESULT") {
        replaceThinkingBubble(thinkingEl, response.payload);
      } else {
        replaceThinkingBubble(thinkingEl, {
          answer: response.payload?.error || "An unexpected error occurred.",
          citations: [],
        });
      }
    }
  );
}

// ---------------------------------------------------------------------------
// Inbound push messages from background (ingest completes while sidebar is open)
// ---------------------------------------------------------------------------
chrome.runtime.onMessage.addListener((message) => {
  switch (message.type) {
    case "INGEST_LOADING":
      showStatus("Analysing terms…"); // state (b)
      break;
    case "INGEST_COMPLETE":
      currentDocId      = message.payload.docId;
      currentSections   = message.payload.sections || [];
      renderRiskReport(message.payload.riskReport);
      showReady();
      break;
    case "INGEST_ERROR":
      showError(message.payload.error);
      break;
    case "NOT_TC_PAGE":
      showNotTc();
      break;
  }
});

// ---------------------------------------------------------------------------
// Bootstrap — query active tab, then ask background for current state
// ---------------------------------------------------------------------------
showStatus("Extracting document…"); // state (a): default until response arrives

chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
  currentTabId = tab?.id ?? null;

  chrome.runtime.sendMessage({ type: "SIDEBAR_READY" }, (response) => {
    if (chrome.runtime.lastError || !response) {
      showError("Could not connect to TermsGPT background worker.");
      return;
    }

    switch (response.type) {
      case "INGEST_EXTRACTING":
        showStatus("Extracting document…"); // state (a): wait for push
        break;
      case "INGEST_LOADING":
        showStatus("Analysing terms…");     // state (b): wait for push
        break;
      case "INGEST_COMPLETE":
        currentDocId    = response.payload.docId;
        currentSections = response.payload.sections || [];
        renderRiskReport(response.payload.riskReport);
        showReady();
        break;
      case "INGEST_ERROR":
        showError(response.payload.error);
        break;
      case "NOT_TC_PAGE":
      default:
        showNotTc();
    }
  });
});

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function truncate(str, maxLen) {
  return str.length > maxLen ? str.slice(0, maxLen) + "…" : str;
}
