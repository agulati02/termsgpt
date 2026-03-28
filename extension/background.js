// background.js — Service Worker (Manifest V3)

// Open the side panel when the extension icon is clicked
chrome.action.onClicked.addListener((tab) => {
  chrome.sidePanel.open({ tabId: tab.id });
});

// Handle messages from content scripts and the sidebar
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "PING") {
    const source = sender.tab ? `content script (tab ${sender.tab.id})` : "sidebar";
    console.log(`[background] PING received from ${source}`);
    sendResponse({ type: "PONG", from: "background", echo: source });
  }
  // Return true to keep the message channel open for async sendResponse
  return true;
});
