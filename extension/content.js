// content.js — Content Script (injected on every http/https page)

import { Readability } from "@mozilla/readability";

console.log("TermsGPT content script active");

// ---------------------------------------------------------------------------
// Step 1 — T&C Detection Heuristic
// ---------------------------------------------------------------------------
const TC_KEYWORDS = [
  "terms", "conditions", "privacy policy", "user agreement", "legal", "terms of service", "tos", "eula"
];

const MIN_KEYWORD_MATCHES = 2;

function detectTermsPage() {
  const signals = [
    document.title,
    document.querySelector("h1")?.textContent ?? "",
    document.body?.innerText?.slice(0, 200) ?? "",
  ];

  const combined = signals.join(" ").toLowerCase();
  const matchCount = TC_KEYWORDS.filter((kw) => combined.includes(kw)).length;

  return matchCount >= MIN_KEYWORD_MATCHES;
}

// ---------------------------------------------------------------------------
// Step 2 — Main Content Extraction
// ---------------------------------------------------------------------------
function extractMainContent() {
  // Use Readability to isolate the main article block
  try {
    const docClone = document.cloneNode(true);
    const reader = new Readability(docClone);
    const article = reader.parse();
    if (!article || !article.textContent) return null;

    return {
      title: article.title || document.title || "",
      bodyText: article.textContent.trim(),
      rootElement: (() => {
        const wrapper = document.createElement("div");
        wrapper.innerHTML = article.content || "";
        return wrapper;
      })(),
    };
  } catch (err) {
    console.warn("Readability extraction failed:", err);
    return null;
  }
}

// ---------------------------------------------------------------------------
// Step 3 — Section Heading Extraction
// ---------------------------------------------------------------------------
function extractSections(_bodyText, _rootElement) {
  const sections = [];

  // Collect h1–h4 heading nodes
  const headingNodes = Array.from(_rootElement.querySelectorAll("h1, h2, h3, h4"));

  // Collect <strong> elements that look like standalone headings:
  // their parent's trimmed text content is essentially the same as the <strong> itself,
  // meaning it's the only meaningful content in that block.
  // Also exclude <strong> elements already nested inside a heading tag.
  const HEADING_TAGS = new Set(["H1", "H2", "H3", "H4"]);
  const standaloneStrong = Array.from(_rootElement.querySelectorAll("strong")).filter((el) => {
    // Skip if it's inside a heading element
    let ancestor = el.parentElement;
    while (ancestor && ancestor !== _rootElement) {
      if (HEADING_TAGS.has(ancestor.tagName)) return false;
      ancestor = ancestor.parentElement;
    }

    const text = el.textContent.trim();
    if (!text || text.length < 3) return false;

    // The parent block's text (stripped of trailing punctuation/whitespace) should
    // match the <strong> text — indicating it's the sole content of that block.
    const parentText = el.parentElement?.textContent.trim().replace(/[:\s]+$/, "") ?? "";
    const elText = text.replace(/[:\s]+$/, "");
    return parentText === elText;
  });

  // Merge and sort by DOM order so charOffsets are monotonically increasing
  const allNodes = [...headingNodes, ...standaloneStrong];
  allNodes.sort((a, b) => {
    const rel = a.compareDocumentPosition(b);
    return rel & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
  });

  // Map each heading node to its charOffset within _bodyText
  let searchFrom = 0;
  for (const node of allNodes) {
    const text = node.textContent.trim();
    if (!text) continue;

    // Search forward from the last matched position to handle duplicate headings
    const idx = _bodyText.indexOf(text, searchFrom);
    if (idx === -1) continue;

    sections.push({ heading: text, charOffset: idx });
    searchFrom = idx + text.length;
  }

  return sections;
}

// ---------------------------------------------------------------------------
// Step 4 — Orchestrate & Send
// ---------------------------------------------------------------------------

function run() {
  const isTermsPage = detectTermsPage();

  if (!isTermsPage) {
    chrome.runtime.sendMessage({ type: "TC_RESULT", payload: { isTermsPage: false } });
    return;
  }

  const content = extractMainContent();
  if (!content) {
    chrome.runtime.sendMessage({ type: "TC_RESULT", payload: { isTermsPage: false } });
    return;
  }

  const sections = extractSections(content.bodyText, content.rootElement);

  chrome.runtime.sendMessage({
    type: "TC_RESULT",
    payload: {
      isTermsPage: true,
      title: content.title,
      bodyText: content.bodyText,
      sections,
    },
  });
}

run();
