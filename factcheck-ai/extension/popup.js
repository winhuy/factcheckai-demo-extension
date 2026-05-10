/* ==========================================
   FactCheckAI - Chrome Extension Popup Logic
   ========================================== */

const BACKEND_URL = "http://127.0.0.1:8000";

document.addEventListener("DOMContentLoaded", () => {
    initPopup();
});

function initPopup() {
    document.getElementById("popupVerifyBtn").addEventListener("click", startVerification);
    
    // Automatically load selected text from the browser tab
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (!tabs || tabs.length === 0) return;
        chrome.tabs.sendMessage(tabs[0].id, { method: "getSelection" }, (response) => {
            if (response && response.text) {
                document.getElementById("popupClaimInput").value = response.text;
                logToPopupTerminal("Đã thu thập văn bản bôi đen từ trang web thành công.", "system");
            }
        });
    });
}

function logToPopupTerminal(message, type = "info") {
    const terminal = document.getElementById("popupTerminal");
    const body = document.getElementById("popupTerminalBody");
    
    terminal.style.display = "flex";
    
    const div = document.createElement("div");
    div.style.lineHeight = "1.4";
    div.style.marginBottom = "2px";
    
    if (type === "system") {
        div.style.color = "#6b7280";
        div.style.fontStyle = "italic";
        div.textContent = `[SYSTEM] ${message}`;
    } else if (type === "warning") {
        div.style.color = "#ef4444";
        div.style.fontWeight = "bold";
        div.textContent = `[WARNING] ${message}`;
    } else {
        div.textContent = `[AGENT] ${message}`;
    }
    
    body.appendChild(div);
    body.scrollTop = body.scrollHeight;
}

async function startVerification() {
    const claim = document.getElementById("popupClaimInput").value.trim();
    if (!claim) {
        alert("Vui lòng nhập nội dung cần xác thực!");
        return;
    }

    const btn = document.getElementById("popupVerifyBtn");
    const terminalBody = document.getElementById("popupTerminalBody");
    const verdictCard = document.getElementById("popupVerdictCard");
    
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Đang xác thực...`;
    verdictCard.classList.add("hidden");
    terminalBody.innerHTML = "";
    
    logToPopupTerminal(`Xác thực tuyên bố...`, "system");
    
    try {
        // Get active tab URL to provide source verification
        const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
        const activeTabUrl = (tabs && tabs[0]) ? tabs[0].url : null;

        const response = await fetch(`${BACKEND_URL}/api/fact-check`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                claim: claim,
                source_url: activeTabUrl
            })
        });
        
        if (!response.ok) {
            throw new Error(`Server returned code ${response.status}`);
        }
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n\n");
            buffer = lines.pop();
            
            for (const line of lines) {
                if (line.startsWith("data: ")) {
                    const parsed = JSON.parse(line.substring(6));
                    if (parsed.event === "thought") {
                        let type = "info";
                        if (parsed.message.includes("CẢNH BÁO")) type = "warning";
                        logToPopupTerminal(parsed.message, type);
                    } else if (parsed.event === "result") {
                        renderPopupVerdict(parsed.data);
                    }
                }
            }
        }
    } catch (err) {
        console.error(err);
        logToPopupTerminal(`Lỗi kết nối tới Backend (${BACKEND_URL}): Hãy đảm bảo Backend đã chạy.`, "warning");
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles"></i> Kiểm chứng ngay`;
    }
}

function renderPopupVerdict(result) {
    const card = document.getElementById("popupVerdictCard");
    const badge = document.getElementById("popupVerdictBadge");
    const confidence = document.getElementById("popupConfidence");
    const explanation = document.getElementById("popupExplanation");
    const sourcesContainer = document.getElementById("popupSources");
    
    badge.className = "verdict-badge";
    if (result.verdict === "VERIFIED") {
        badge.classList.add("verified");
        badge.innerText = "CHÍNH XÁC (VERIFIED)";
    } else if (result.verdict === "FALSE") {
        badge.classList.add("false");
        badge.innerText = "SAI SỰ THẬT (FALSE)";
    } else {
        badge.classList.add("pending");
        badge.innerText = "CẦN CHỜ XÁC MINH (PENDING)";
    }
    
    confidence.innerText = `${result.confidence}%`;
    explanation.innerText = result.explanation;
    
    sourcesContainer.innerHTML = "";
    if (result.sources && result.sources.length > 0) {
        result.sources.forEach(source => {
            const item = document.createElement("div");
            item.className = "pop-source-item";
            const isWhitelisted = source.is_whitelist ? `<span style="color:#10b981; font-size:10px; font-weight:bold; margin-right:4px;">[✓]</span>` : "";
            item.innerHTML = `
                <span>${isWhitelisted}${source.title.substring(0, 32)}... (${source.domain})</span>
                <a href="${source.url}" target="_blank"><i class="fa-solid fa-arrow-up-right-from-square"></i></a>
            `;
            sourcesContainer.appendChild(item);
        });
    } else {
        sourcesContainer.innerHTML = `<div class="pop-source-item"><span>Không có nguồn</span></div>`;
    }
    
    card.classList.remove("hidden");
}
