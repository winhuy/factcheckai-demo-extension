/* ==========================================
   FactCheckAI - Interactive Frontend Controller
   ========================================== */

const API_BASE = window.location.origin;

// Predefined sample claims for quick filling
const SAMPLES = [
    "Chính phủ Việt Nam chính thức phê duyệt Đề án phát triển nguồn nhân lực ngành bán dẫn đến năm 2030.",
    "Thành phố Hồ Chí Minh có tuyết rơi dày đặc lần đầu tiên trong lịch sử vào tháng 5 năm nay.",
    "Trạm vũ trụ quốc tế ISS vừa phát hiện sinh vật ngoài hành tinh di động bám ngoài vỏ khoang tàu."
];

// State variables
let activeStreaming = false;

// Initialize elements on load
document.addEventListener("DOMContentLoaded", () => {
    initApp();
});

async function initApp() {
    setupEventListeners();
    await fetchWhitelist();
    await fetchCacheStats();
}

function setupEventListeners() {
    document.getElementById("verifyBtn").addEventListener("click", startFactCheck);
    document.getElementById("addDomainBtn").addEventListener("click", addDomain);
    document.getElementById("resetWhitelistBtn").addEventListener("click", resetWhitelist);
    document.getElementById("clearCacheBtn").addEventListener("click", clearCache);
    
    // Add domain on enter
    document.getElementById("newDomainInput").addEventListener("keydown", (e) => {
        if (e.key === "Enter") addDomain();
    });
}

function fillSample(index) {
    if (activeStreaming) return;
    document.getElementById("claimInput").value = SAMPLES[index];
}

// Write to Live Terminal Panel
function logToTerminal(message, type = "info") {
    const terminal = document.getElementById("terminalBody");
    const now = new Date();
    const timeStr = `[${now.toTimeString().split(' ')[0]}]`;
    
    const line = document.createElement("div");
    line.className = `terminal-line ${type === 'warning' ? 'warning-msg' : ''}`;
    
    let prefix = "AGENT:";
    if (type === "system") prefix = "SYSTEM:";
    if (type === "warning") prefix = "WARNING:";
    
    line.innerHTML = `<span class="term-time">${timeStr}</span> <span class="term-prefix">${prefix}</span> ${message}`;
    terminal.appendChild(line);
    terminal.scrollTop = terminal.scrollHeight;
}

// Fetch and render Whitelist Domains
async function fetchWhitelist() {
    try {
        const response = await fetch(`${API_BASE}/api/whitelist`);
        const data = await response.json();
        renderWhitelist(data.domains);
    } catch (err) {
        console.error("Error fetching whitelist:", err);
    }
}

function renderWhitelist(domains) {
    const container = document.getElementById("domainsGrid");
    container.innerHTML = "";
    domains.forEach(domain => {
        const pill = document.createElement("div");
        pill.className = "domain-pill";
        pill.innerHTML = `
            <span>${domain}</span>
            <button class="remove-domain-btn" onclick="removeDomain('${domain}')">
                <i class="fa-solid fa-xmark"></i>
            </button>
        `;
        container.appendChild(pill);
    });
}

async function addDomain() {
    const input = document.getElementById("newDomainInput");
    const domain = input.value.trim();
    if (!domain) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/whitelist`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ domain })
        });
        const data = await response.json();
        renderWhitelist(data.domains);
        input.value = "";
        logToTerminal(`Đã thêm thành công tên miền \`${domain}\` vào danh sách Whitelist.`, "system");
    } catch (err) {
        console.error("Error adding domain:", err);
    }
}

async function removeDomain(domain) {
    try {
        const response = await fetch(`${API_BASE}/api/whitelist/${domain}`, { method: "DELETE" });
        const data = await response.json();
        renderWhitelist(data.domains);
        logToTerminal(`Đã gỡ bỏ tên miền \`${domain}\` khỏi danh sách Whitelist.`, "system");
    } catch (err) {
        console.error("Error removing domain:", err);
    }
}

async function resetWhitelist() {
    try {
        const response = await fetch(`${API_BASE}/api/whitelist/reset`, { method: "POST" });
        const data = await response.json();
        renderWhitelist(data.domains);
        logToTerminal("Đã đặt lại danh sách Whitelist mặc định.", "system");
    } catch (err) {
        console.error("Error resetting whitelist:", err);
    }
}

// Fetch and render Cache stats
async function fetchCacheStats() {
    try {
        const response = await fetch(`${API_BASE}/api/cache-stats`);
        const data = await response.json();
        document.getElementById("cacheTotal").innerText = data.total_cache_entries;
        document.getElementById("cacheVerified").innerText = data.verified_count;
        document.getElementById("cacheFalse").innerText = data.false_count;
        document.getElementById("cachePending").innerText = data.pending_count;
    } catch (err) {
        console.error("Error fetching cache stats:", err);
    }
}

async function clearCache() {
    try {
        await fetch(`${API_BASE}/api/cache/clear`, { method: "POST" });
        await fetchCacheStats();
        logToTerminal("Đã xóa sạch bộ nhớ đệm Cache và tải lại mặc định.", "system");
    } catch (err) {
        console.error("Error clearing cache:", err);
    }
}

// Core Fact Check Action using SSE (Streaming)
async function startFactCheck() {
    const claim = document.getElementById("claimInput").value.trim();
    if (!claim) {
        alert("Vui lòng nhập nội dung cần xác minh!");
        return;
    }
    
    if (activeStreaming) return;
    activeStreaming = true;
    
    // UI states resetting
    document.getElementById("verifyBtn").disabled = true;
    document.getElementById("verifyBtn").innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Agent đang chạy...`;
    document.getElementById("verdictCard").classList.add("hidden");
    document.getElementById("graphPlaceholder").classList.remove("hidden");
    clearGraph();
    
    logToTerminal(`Gửi yêu cầu kiểm chứng tuyên bố: "${claim}"`, "system");
    
    try {
        const response = await fetch(`${API_BASE}/api/fact-check`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ claim })
        });
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";
        
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n\n");
            buffer = lines.pop(); // keep last incomplete line
            
            for (const line of lines) {
                if (line.startsWith("data: ")) {
                    const parsed = JSON.parse(line.substring(6));
                    handleStreamEvent(parsed);
                }
            }
        }
    } catch (err) {
        console.error("Error checking claim:", err);
        logToTerminal(`Gặp lỗi kết nối server: ${err.message}`, "warning");
    } finally {
        activeStreaming = false;
        document.getElementById("verifyBtn").disabled = false;
        document.getElementById("verifyBtn").innerHTML = `<i class="fa-solid fa-wand-magic-sparkles"></i> Xác minh ngay`;
        await fetchCacheStats();
    }
}

function handleStreamEvent(eventObj) {
    if (eventObj.event === "thought") {
        let type = "info";
        if (eventObj.message.includes("CẢNH BÁO")) type = "warning";
        logToTerminal(eventObj.message, type);
    } else if (eventObj.event === "result") {
        logToTerminal("Đã hoàn tất tiến trình phân tích. Đang hiển thị kết quả...", "system");
        renderVerdict(eventObj.data);
        if (eventObj.data.graph) {
            document.getElementById("graphPlaceholder").classList.add("hidden");
            renderGraph(eventObj.data.graph);
        }
    }
}

function renderVerdict(result) {
    const card = document.getElementById("verdictCard");
    const banner = document.getElementById("verdictBanner");
    const icon = document.getElementById("verdictIcon");
    const title = document.getElementById("verdictTitle");
    const confidence = document.getElementById("confidenceVal");
    
    document.getElementById("verdictClaim").innerText = result.claim;
    document.getElementById("verdictExplanation").innerText = result.explanation;
    
    // Set banner classes based on verdict
    banner.className = "verdict-banner";
    if (result.verdict === "VERIFIED") {
        banner.classList.add("verified");
        icon.className = "fa-solid fa-circle-check";
        title.innerText = "CHÍNH XÁC (VERIFIED)";
    } else if (result.verdict === "FALSE") {
        banner.classList.add("false");
        icon.className = "fa-solid fa-circle-xmark";
        title.innerText = "SAI SỰ THẬT (FALSE)";
    } else {
        banner.classList.add("pending");
        icon.className = "fa-solid fa-circle-minus";
        title.innerText = "CẦN CHỜ XÁC MINH (PENDING)";
    }
    
    confidence.innerText = `${result.confidence}%`;
    
    // Render sources
    const sourcesContainer = document.getElementById("verdictSources");
    sourcesContainer.innerHTML = "";
    
    if (result.sources && result.sources.length > 0) {
        result.sources.forEach(source => {
            const item = document.createElement("div");
            item.className = "source-item";
            item.innerHTML = `
                <div class="source-info">
                    <span class="source-title">${source.title}</span>
                    <span class="source-domain">${source.domain}</span>
                </div>
                <a href="${source.url}" target="_blank" class="source-link" title="Đến bài báo kiểm chứng">
                    <i class="fa-solid fa-arrow-up-right-from-square"></i>
                </a>
            `;
            sourcesContainer.appendChild(item);
        });
    } else {
        sourcesContainer.innerHTML = `<div class="source-item"><span class="source-title">Không tìm thấy nguồn kiểm chứng từ Whitelist</span></div>`;
    }
    
    card.classList.remove("hidden");
}

// SVG Graph Rendering (No heavy library, super stable & neat!)
function clearGraph() {
    const svg = document.getElementById("graphSvg");
    svg.innerHTML = "";
}

function renderGraph(graph) {
    const svg = document.getElementById("graphSvg");
    clearGraph();
    
    const width = svg.clientWidth || 500;
    const height = svg.clientHeight || 300;
    
    const nodes = graph.nodes;
    const edges = graph.edges;
    
    // Calculate layout coordinates using a circle network distribution
    const nodeCount = nodes.length;
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) * 0.35;
    
    const coords = {};
    nodes.forEach((node, i) => {
        const angle = (i * 2 * Math.PI) / nodeCount;
        coords[node.id] = {
            x: centerX + radius * Math.cos(angle),
            y: centerY + radius * Math.sin(angle)
        };
    });
    
    // Draw links / Edges first so nodes are layered on top
    edges.forEach(edge => {
        const from = coords[edge.source];
        const to = coords[edge.target];
        if (!from || !to) return;
        
        const isConflict = edge.is_conflict === true;
        
        // Link Line
        const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
        line.setAttribute("x1", from.x);
        line.setAttribute("y1", from.y);
        line.setAttribute("x2", to.x);
        line.setAttribute("y2", to.y);
        line.setAttribute("stroke", isConflict ? "#ef4444" : "rgba(255, 255, 255, 0.15)");
        line.className.baseVal = `edge ${isConflict ? 'conflict' : ''}`;
        svg.appendChild(line);
        
        // Link Text (Relation label)
        const labelX = (from.x + to.x) / 2;
        const labelY = (from.y + to.y) / 2 - 5;
        const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
        text.setAttribute("x", labelX);
        text.setAttribute("y", labelY);
        text.setAttribute("text-anchor", "middle");
        text.className.baseVal = `edge-label ${isConflict ? 'conflict' : ''}`;
        text.textContent = edge.relation;
        svg.appendChild(text);
    });
    
    // Draw Nodes
    nodes.forEach(node => {
        const coord = coords[node.id];
        
        // Group container
        const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
        g.className.baseVal = `node ${node.type}`;
        g.setAttribute("transform", `translate(${coord.x}, ${coord.y})`);
        
        // Circle background glow
        const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        circle.setAttribute("r", 12);
        
        // Label Text
        const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
        text.setAttribute("y", 22);
        text.setAttribute("text-anchor", "middle");
        text.textContent = node.label;
        
        g.appendChild(circle);
        g.appendChild(text);
        svg.appendChild(g);
    });
}
