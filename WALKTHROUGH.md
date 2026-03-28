# 🧩 TermsGPT — Chrome Extension Walkthrough

> A complete guide to how this Chrome extension is structured, what every file does, and how all the pieces talk to each other.

---

## 📚 Table of Contents

1. [How Chrome Extensions Work](#1--how-chrome-extensions-work)
2. [Files We Created](#2--files-we-created)
3. [What Each File Does (Summary)](#3--what-each-file-does-summary)
4. [Detailed Walkthrough](#4--detailed-walkthrough)
   - [manifest.json](#-manifestjson)
   - [background.js](#-backgroundjs)
   - [content.js](#-contentjs)
   - [sidebar.html](#-sidebarhtml)
   - [sidebar.js](#-sidebarjs)
5. [The Full Communication Chain](#5--the-full-communication-chain)

---

## 1. 🌐 How Chrome Extensions Work

A Chrome extension is a small web application that runs **inside the browser** and has privileged access to browser APIs that normal webpages cannot touch — things like reading tabs, intercepting network requests, injecting scripts, and opening side panels.

### 🏛️ The Three Worlds of a Chrome Extension

Chrome extensions are split into three isolated environments. Each has different capabilities and a different lifecycle:

---

#### 🔧 World 1 — The Background Service Worker
- Runs **in the background**, completely separate from any webpage.
- Has access to the full Chrome extension API (`chrome.*`).
- **No DOM** — it cannot read or modify any webpage's HTML.
- In Manifest V3 (MV3), the background script is a **service worker**, meaning it is event-driven and can be killed by Chrome when idle to save memory. It wakes up automatically when an event fires.
- Typical job: react to browser events (tab opened, icon clicked, alarm fired), orchestrate logic, and relay messages between other parts of the extension.

---

#### 📄 World 2 — Content Scripts
- JavaScript files that Chrome **injects directly into webpages**.
- They run in the context of the visited page, so they **can read and modify the DOM**.
- They are **sandboxed** — they share the page's DOM but run in an isolated JavaScript environment (they cannot access the page's own JavaScript variables or libraries).
- They communicate with the background worker through **message passing** — they cannot call `chrome.*` APIs directly (only a safe subset is available).
- Typical job: scrape page content, observe DOM changes, inject UI elements.

---

#### 🖼️ World 3 — Extension Pages (Popups, Sidebars, Options)
- These are plain HTML/CSS/JS pages bundled inside the extension.
- They run in the **extension's own origin**, not the webpage's origin.
- They have full access to `chrome.*` APIs (like the background service worker does).
- Examples: a popup that opens when you click the icon, an options settings page, or (in our case) a **side panel** that docks to the right of the browser.
- Typical job: display the extension's UI and react to user input.

---

### ✉️ How These Worlds Communicate

Because these environments are isolated, they can't share variables or call each other's functions directly. Instead, Chrome provides a **message passing API**:

```
Content Script  ──sendMessage──▶  Background Worker  ──sendMessage──▶  Sidebar / Popup
                ◀──response────                       ◀──response────
```

- **`chrome.runtime.sendMessage()`** — sends a one-time message to the background worker or to another extension page.
- **`chrome.tabs.sendMessage()`** — sends a message from the background worker to a content script running in a specific tab.
- **`chrome.runtime.onMessage.addListener()`** — listens for incoming messages on either end.

All messages are plain JSON objects, so any data you want to pass must be serialisable.

---

### 🗂️ The Manifest — The Extension's Constitution

Every Chrome extension must have a `manifest.json` at its root. This file is the **single source of truth** that tells Chrome:
- What the extension is named and versioned.
- Which permissions it needs (e.g. access to tabs, side panels, scripting).
- Which scripts to run as the background service worker.
- Which scripts to inject into webpages (content scripts).
- Which HTML pages to use for the popup, sidebar, or options page.

Chrome reads this file when you load the extension and enforces every rule declared in it. If `manifest.json` is malformed or missing a required field, the extension will fail to load.

---

### 🔐 Manifest V3 vs. Manifest V2

We use **Manifest V3 (MV3)**, the current standard. Key differences from the older V2:
- Background pages → replaced by **service workers** (event-driven, can be terminated when idle).
- `webRequestBlocking` → replaced by `declarativeNetRequest` (safer, declarative rules).
- Remote code execution is disallowed — all code must be bundled in the extension.
- Stronger permission controls and better privacy for users.

---

## 2. 📁 Files We Created

```
ai-trip-planner/
├── manifest.json   ← Extension blueprint (required)
├── background.js   ← Background service worker
├── content.js      ← Content script (injected into webpages)
├── sidebar.html    ← Sidebar panel UI
└── sidebar.js      ← Sidebar panel logic
```

5 files total. No build step, no bundler — Chrome loads them directly.

---

## 3. 🗺️ What Each File Does (Summary)

| 📄 File | 🌍 World | 📋 Role |
|---|---|---|
| `manifest.json` | — | Declares the extension's identity, permissions, and entry points |
| `background.js` | Background Service Worker | Opens the sidebar when the icon is clicked; handles PING/PONG messages |
| `content.js` | Content Script (webpage) | Injected into every page; confirms injection and pings the background worker |
| `sidebar.html` | Extension Page (sidebar) | The visual shell of the sidebar — HTML structure and CSS styles |
| `sidebar.js` | Extension Page (sidebar) | Runs inside the sidebar; updates status badges and pings the background worker |

---

## 4. 🔍 Detailed Walkthrough

---

### 📋 `manifest.json`

**The extension's constitution.** Chrome reads this before anything else.

```json
{
  "manifest_version": 3,
  "name": "TermsGPT",
  "version": "0.1.0",
  "description": "Extracts and analyses Terms & Conditions from any webpage using AI.",

  "permissions": [
    "sidePanel",
    "activeTab",
    "scripting"
  ],

  "background": {
    "service_worker": "background.js"
  },

  "content_scripts": [
    {
      "matches": ["http://*/*", "https://*/*"],
      "js": ["content.js"]
    }
  ],

  "side_panel": {
    "default_path": "sidebar.html"
  },

  "action": {
    "default_title": "Open TermsGPT"
  }
}
```

**Line-by-line breakdown:**

| Key | What it does |
|---|---|
| `manifest_version: 3` | Tells Chrome this is a Manifest V3 extension. Required. |
| `name`, `version`, `description` | Displayed in `chrome://extensions` and the Chrome Web Store. |
| `permissions.sidePanel` | Grants access to the `chrome.sidePanel` API so we can open a docked sidebar. |
| `permissions.activeTab` | Grants temporary access to the currently active tab when the user clicks the icon — without requiring blanket access to all tabs. |
| `permissions.scripting` | Allows the extension to programmatically inject scripts into pages (needed for later features). |
| `background.service_worker` | Points Chrome to `background.js` as the background service worker. Only one allowed. |
| `content_scripts[].matches` | Glob patterns for which pages to inject `content.js` into. `http://*/*` and `https://*/*` covers every real website. |
| `content_scripts[].js` | The list of scripts to inject, in order. |
| `side_panel.default_path` | Tells Chrome which HTML file to render in the side panel when it opens. |
| `action.default_title` | The tooltip shown when the user hovers over the extension's toolbar icon. |

---

### ⚙️ `background.js`

**The brain of the extension.** Runs as a service worker in the background, invisible to the user.

```js
// Open the side panel when the extension icon is clicked
chrome.action.onClicked.addListener((tab) => {
  chrome.sidePanel.open({ tabId: tab.id });
});
```

🔹 `chrome.action.onClicked` fires when the user clicks the extension's icon in the Chrome toolbar.
🔹 `chrome.sidePanel.open({ tabId })` opens the sidebar panel docked to the right of the current tab. We pass `tabId` so Chrome knows which tab to attach the panel to.

```js
// Handle messages from content scripts and the sidebar
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "PING") {
    const source = sender.tab
      ? `content script (tab ${sender.tab.id})`
      : "sidebar";
    console.log(`[background] PING received from ${source}`);
    sendResponse({ type: "PONG", from: "background", echo: source });
  }
  return true; // ← keeps the channel open for async sendResponse
});
```

🔹 `chrome.runtime.onMessage.addListener` registers a handler for all incoming messages.
🔹 The `sender` object tells us who sent the message — if `sender.tab` exists, it came from a content script in a real tab; otherwise it came from an extension page (like our sidebar).
🔹 `sendResponse(...)` sends a reply back to whoever sent the message.
🔹 **`return true`** is critical — without it, Chrome closes the message channel before `sendResponse` can be called asynchronously. Always return `true` when you intend to respond.

---

### 📄 `content.js`

**The extension's eyes inside the webpage.** Injected automatically by Chrome into every `http://` and `https://` page the user visits.

```js
console.log("TermsGPT content script active");
```

🔹 Simple confirmation log. You'll see this in the **webpage's DevTools console** (not the extension's) whenever the script loads successfully.

```js
chrome.runtime.sendMessage({ type: "PING" }, (response) => {
  if (chrome.runtime.lastError) {
    console.warn("[content] PING failed:", chrome.runtime.lastError.message);
    return;
  }
  console.log("[content] PONG received from background:", response);
});
```

🔹 `chrome.runtime.sendMessage` sends a `PING` message to the background service worker.
🔹 `chrome.runtime.lastError` must always be checked in the callback — if the background worker isn't running yet (which can happen on the very first page load), Chrome will set this error and the callback will be called with `undefined`. Ignoring it causes an uncaught error.
🔹 On success, the response (`{ type: "PONG", from: "background", echo: "..." }`) is logged to confirm the content → background communication path works.

> **Why is this in `content.js` and not `sidebar.js`?**
> Content scripts run in the page's world and are a distinct communication endpoint from extension pages. Testing the PING from both `content.js` and `sidebar.js` validates two different communication paths independently.

---

### 🖼️ `sidebar.html`

**The visual shell of the sidebar.** A standard HTML file that Chrome renders inside the side panel. It owns all the layout and styles.

**Structure overview:**

```
<body>
  <header>          ← Dark branding bar with extension name
  <main>
    <div.status-card>   ← "Extension Status" badge (Active / Loading)
    <div.status-card>   ← "Background Worker" badge (PONG ✓ / Unreachable)
    <div.placeholder>   ← Static "TermsGPT loading…" message
  <script src="sidebar.js">  ← Logic loaded at end of body
```

**Notable CSS decisions:**

| Style | Why |
|---|---|
| `height: 100vh` + `display: flex; flex-direction: column` on `body` | Makes the sidebar fill the full panel height, with header pinned at top and main content scrollable below. |
| `.badge.ok / .badge.err / .badge.idle` | Three colour states for status indicators — green (working), red (error), grey (loading). Driven dynamically by `sidebar.js`. |
| `<script src="sidebar.js">` at bottom of `<body>` | Ensures the DOM elements (`#ext-status`, `#bg-status`) exist before the script tries to query them. |

**The two status cards** start in the `idle` (grey) state with placeholder text. `sidebar.js` updates them as soon as it runs:

```html
<div class="value" id="ext-status">
  <span class="badge idle">Loading…</span>   <!-- replaced by sidebar.js -->
</div>

<div class="value" id="bg-status">
  <span class="badge idle">Pinging…</span>   <!-- replaced by sidebar.js -->
</div>
```

---

### 🧠 `sidebar.js`

**The logic layer of the sidebar.** Runs inside the sidebar page, has full access to `chrome.*` APIs.

```js
const extStatusEl = document.getElementById("ext-status");
const bgStatusEl  = document.getElementById("bg-status");

function badge(text, type) {
  return `<span class="badge ${type}">${text}</span>`;
}
```

🔹 Grabs references to both status card value elements from the DOM.
🔹 `badge()` is a tiny helper that builds the coloured badge HTML string, keeping the status-update code DRY.

```js
// Mark sidebar as running
extStatusEl.innerHTML = badge("Active", "ok");
```

🔹 The moment this line executes, the "Extension Status" card turns green. This is instant — it confirms the sidebar page itself loaded and JavaScript is running.

```js
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
```

🔹 Sends a `PING` to the background worker — same message type as `content.js` uses.
🔹 **Error path:** If the background worker is unreachable, the badge turns red with "Unreachable".
🔹 **Happy path:** When `PONG` arrives, the badge turns green with "PONG ✓", confirming the sidebar → background communication path works.
🔹 **Unexpected response path:** Defensive guard in case the response shape changes in future iterations.

---

## 5. 🔄 The Full Communication Chain

Here is the end-to-end message flow that validates all three worlds are connected:

```
┌─────────────────────────────────────────────────────────────────────┐
│  WEBPAGE                                                            │
│                                                                     │
│  content.js                                                         │
│    1. Logs "TermsGPT content script active" to page console         │
│    2. Sends PING ──────────────────────────────────────────────┐    │
└────────────────────────────────────────────────────────────────│────┘
                                                                 │
                         ┌───────────────────────────────────────▼───┐
                         │  BACKGROUND SERVICE WORKER                │
                         │                                           │
                         │  background.js                            │
                         │    Receives PING from content script      │
                         │    Logs source to extension console       │
                         │    Sends PONG back ◀──────────────────────┤
                         │                                           │
                         │    Also receives PING from sidebar ───────┤
                         │    Sends PONG back to sidebar ────────────┤
                         └───────────────────────────────────────────┘
                                                                 │
┌────────────────────────────────────────────────────────────────│────┐
│  SIDEBAR (Extension Page)                                       │    │
│                                                                 │    │
│  sidebar.js                                                     │    │
│    1. Sets "Extension Status" → 🟢 Active (immediate)          │    │
│    2. Sends PING ───────────────────────────────────────────────┘   │
│    3. Receives PONG → sets "Background Worker" → 🟢 PONG ✓         │
└─────────────────────────────────────────────────────────────────────┘
```

**When all three badges are green, the scaffold is working correctly:**

| ✅ Signal | ✅ What it confirms |
|---|---|
| "TermsGPT content script active" in page console | `content.js` was injected into the page |
| "[content] PONG received" in page console | content script → background two-way communication works |
| "Extension Status: Active" badge in sidebar | `sidebar.html` + `sidebar.js` loaded correctly |
| "Background Worker: PONG ✓" badge in sidebar | sidebar → background two-way communication works |

---

> **Next step:** Feature 2 will add the Terms & Conditions extraction logic inside `content.js`, using the DOM access it already has to scrape and send page text to the backend.
