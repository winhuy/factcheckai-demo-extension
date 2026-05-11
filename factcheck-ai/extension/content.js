/* ==========================================
   FactCheckAI - Enhanced Content Script for Facebook
   Deep Integration and Contextual Verification
   ========================================== */

const BACKEND_URL = "http://127.0.0.1:8000";

// Setup dynamic observer to watch for injected Facebook posts
function initialize() {
    console.log("FactCheckAI: Injected and watching feed...");
    injectModalHtml();
    
    // Initial scan
    scanAndInject();
    
    // Observe DOM mutations for dynamic scrolling
    const observer = new MutationObserver((mutations) => {
        let shouldScan = false;
        for (let mutation of mutations) {
            if (mutation.addedNodes.length > 0) {
                shouldScan = true;
                break;
            }
        }
        if (shouldScan) {
            scanAndInject();
        }
    });
    
    observer.observe(document.body, { childList: true, subtree: true });
}

function scanAndInject() {
    // Selectors that are highly likely to be post content on Facebook
    const contentSelectors = [
        'div[data-ad-comet-preview="message"]', 
        'div[data-ad-preview="message"]',
        'div[role="article"] div[dir="auto"]' // Fallback broader selector
    ];
    
    contentSelectors.forEach(selector => {
        document.querySelectorAll(selector).forEach(element => {
            // Ensure element actually has meaningful text and isn't too tiny
            const text = element.innerText.trim();
            if (text.length < 10) return; 
            
            // Skip if already injected
            if (element.hasAttribute('data-factcheck-hooked')) return;
            
            // Mark element as processed
            element.setAttribute('data-factcheck-hooked', 'true');
            
            // Create & Inject the magical check button
            const btn = document.createElement('button');
            btn.className = 'fact-check-btn-injected';
            btn.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                </svg>
                Kiểm chứng AI
            `;
            
            btn.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                openModalAndCheck(text);
            };
            
            // Append right after the element node
            element.parentNode.insertBefore(btn, element.nextSibling);
        });
    });
}

function injectModalHtml() {
    if (document.getElementById('factcheck-ai-overlay')) return;
    
    const overlay = document.createElement('div');
    overlay.id = 'factcheck-ai-overlay';
    overlay.innerHTML = `
        <div class="fact-check-modal">
            <div class="modal-header">
                <div class="modal-title">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: #60a5fa;"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path><polyline points="9 11 12 14 22 4"></polyline></svg>
                    FactCheckAI Analysis
                </div>
                <button class="modal-close">&times;</button>
            </div>
            <div class="modal-content-area">
                <div class="claim-quote" id="factcheck-current-claim"></div>
                <div class="stream-logs" id="factcheck-logs"></div>
                <div class="verdict-card" id="factcheck-card">
                    <div class="verdict-header">
                        <div class="verdict-badge" id="factcheck-badge">VERIFIED</div>
                        <div class="confidence-ring" id="factcheck-conf">95%</div>
                    </div>
                    <p class="verdict-explanation" id="factcheck-expl"></p>
                    <div class="verdict-sources">
                        <strong>📚 Nguồn tham khảo:</strong>
                        <div class="sources-list" id="factcheck-sources"></div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(overlay);
    
    // Bind close click
    overlay.querySelector('.modal-close').onclick = () => {
        overlay.classList.remove('active');
    };
    
    // Close on clicking background
    overlay.onclick = (e) => {
        if (e.target === overlay) {
            overlay.classList.remove('active');
        }
    };
}

async function openModalAndCheck(claimText) {
    const overlay = document.getElementById('factcheck-ai-overlay');
    const claimDisplay = document.getElementById('factcheck-current-claim');
    const logContainer = document.getElementById('factcheck-logs');
    const card = document.getElementById('factcheck-card');
    
    // Reset state
    claimDisplay.innerText = `"${claimText.substring(0, 180)}${claimText.length > 180 ? '...' : ''}"`;
    logContainer.innerHTML = '';
    card.style.display = 'none';
    overlay.classList.add('active');
    
    addLog("🚀 Đang kết nối với Hệ thống Agent...");

    try {
        const response = await fetch(`${BACKEND_URL}/api/fact-check`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
                claim: claimText,
                source_url: window.location.href
            })
        });

        if (!response.ok) {
            throw new Error("Backend connection failed");
        }

        // Handle SSE stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n\n");
            buffer = lines.pop(); // Hold back partial data

            for (const line of lines) {
                if (line.startsWith("data: ")) {
                    try {
                        const rawData = JSON.parse(line.replace("data: ", "").trim());
                        if (rawData.event === "thought") {
                            addLog(rawData.message);
                        } else if (rawData.event === "result") {
                            displayVerdict(rawData.data);
                        }
                    } catch (e) {
                        console.error("JSON Parsing error in stream:", e);
                    }
                }
            }
        }
    } catch (error) {
        addLog(`❌ Lỗi: ${error.message}. Hãy chắc chắn rằng Backend đang chạy tại 127.0.0.1:8000`);
    }
}

function addLog(msg) {
    const container = document.getElementById('factcheck-logs');
    const div = document.createElement('div');
    div.className = 'log-item';
    div.innerText = msg;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function displayVerdict(data) {
    const card = document.getElementById('factcheck-card');
    const badge = document.getElementById('factcheck-badge');
    const conf = document.getElementById('factcheck-conf');
    const expl = document.getElementById('factcheck-expl');
    const sourcesDiv = document.getElementById('factcheck-sources');
    
    badge.className = 'verdict-badge';
    if (data.verdict === 'VERIFIED') {
        badge.innerText = '✓ CHÍNH XÁC';
        badge.classList.add('badge-verified');
    } else if (data.verdict === 'FALSE') {
        badge.innerText = '✗ SAI LỆCH';
        badge.classList.add('badge-false');
    } else {
        badge.innerText = '⚠ CHỜ XÁC MINH';
        badge.classList.add('badge-pending');
    }
    
    conf.innerText = `Độ tin cậy: ${data.confidence}%`;
    expl.innerText = data.explanation;
    
    sourcesDiv.innerHTML = '';
    if (data.sources && data.sources.length > 0) {
        const official = data.sources.filter(s => s.is_whitelist || s.is_trusted);
        const unverified = data.sources.filter(s => !(s.is_whitelist || s.is_trusted));
        
        if (official.length > 0) {
            const header = document.createElement('div');
            header.style.margin = '8px 0 4px 0';
            header.style.fontSize = '12px';
            header.style.color = '#34d399';
            header.innerHTML = '✅ Nguồn Chính Thống';
            sourcesDiv.appendChild(header);
            
            const wrap = document.createElement('div');
            wrap.className = 'sources-list';
            official.forEach(src => {
                const link = document.createElement('a');
                link.className = 'source-tag source-official';
                link.href = src.url;
                link.target = '_blank';
                link.innerText = src.domain || 'Source';
                wrap.appendChild(link);
            });
            sourcesDiv.appendChild(wrap);
        }
        
        if (unverified.length > 0) {
            const header = document.createElement('div');
            header.style.margin = '14px 0 4px 0';
            header.style.fontSize = '12px';
            header.style.color = '#fbbf24';
            header.innerHTML = '⚠️ Nguồn Chưa Xác Minh';
            sourcesDiv.appendChild(header);
            
            const wrap = document.createElement('div');
            wrap.className = 'sources-list';
            unverified.forEach(src => {
                const link = document.createElement('a');
                link.className = 'source-tag source-unverified';
                link.href = src.url;
                link.target = '_blank';
                link.innerText = src.domain || 'Source';
                wrap.appendChild(link);
            });
            sourcesDiv.appendChild(wrap);
        }
    } else {
        sourcesDiv.innerHTML = '<span style="color:#94a3b8;font-style:italic;">Không có nguồn nào được trả về.</span>';
    }
    
    card.style.display = 'block';
    
    // Scroll to bottom to reveal card
    const modal = document.querySelector('.fact-check-modal');
    setTimeout(() => {
        modal.scrollTo({ top: modal.scrollHeight, behavior: 'smooth' });
    }, 100);
}

// Start logic
if (document.readyState === "complete" || document.readyState === "interactive") {
    initialize();
} else {
    window.addEventListener("DOMContentLoaded", initialize);
}
