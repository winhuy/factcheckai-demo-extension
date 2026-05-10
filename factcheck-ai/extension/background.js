/* ==========================================
   FactCheckAI - Chrome Extension Background worker
   ========================================== */

chrome.runtime.onInstalled.addListener(() => {
    chrome.contextMenus.create({
        id: "factCheckSelection",
        title: "Xác minh tin tức qua FactCheckAI",
        contexts: ["selection"]
    });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
    if (info.menuItemId === "factCheckSelection") {
        const text = info.selectionText;
        // Save to chrome storage so popup can read it
        chrome.storage.local.set({ selectedText: text }, () => {
            // Open Extension Action popup (Supported in newer Chrome versions, or simply let the user open the popup manually)
            console.log("Selected text saved to storage: ", text);
        });
    }
});
