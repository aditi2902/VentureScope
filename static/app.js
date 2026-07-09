/* ═══════════════════════════════════════════════════════
   AI Startup Agent — Frontend Logic
   ═══════════════════════════════════════════════════════ */

const API_BASE = "http://localhost:5000/api";

// ── State ──
let state = {
    step: 1,
    market: "",
    sector: "B2B SaaS",
    team_size: "1-2 (Solo/Co-founders)",
    budget: "$10k-$50k (Pre-seed)",
    pain_points: [],
    selected_pain_point: null,
    sessionId: crypto.randomUUID()
};

// ── DOM Elements ──
const steps = [
    document.getElementById("step-1"),
    document.getElementById("step-2"),
    document.getElementById("step-3")
];
const indicators = document.querySelectorAll(".step-indicator");
const connectors = document.querySelectorAll(".step-connector");

const formStep1 = document.getElementById("form-step-1");
const btnFindPain = document.getElementById("btn-find-pain");
const painPointCards = document.getElementById("pain-point-cards");
const rawPainPoints = document.getElementById("raw-pain-points");
const btnGenerateIdea = document.getElementById("btn-generate-idea");
const btnBack1 = document.getElementById("btn-back-1");
const btnStartOver = document.getElementById("btn-start-over");

const logEntries = document.getElementById("log-entries");
const resultStream = document.getElementById("result-stream");
const finalDashboard = document.getElementById("final-dashboard");

// Theme
const themeToggle = document.getElementById("btn-theme-toggle");
const body = document.body;

// Ideas Panel
const btnOpenIdeas = document.getElementById("btn-open-ideas");
const btnCloseIdeas = document.getElementById("btn-close-ideas");
const ideasOverlay = document.getElementById("ideas-overlay");
const ideasPanel = document.getElementById("ideas-panel");
const ideasList = document.getElementById("ideas-list");

// ── Initialization ──
document.addEventListener("DOMContentLoaded", () => {
    // Theme setup
    const savedTheme = localStorage.getItem("theme") || "light";
    body.setAttribute("data-theme", savedTheme);
    updateThemeIcon(savedTheme);

    themeToggle.addEventListener("click", () => {
        const currentTheme = body.getAttribute("data-theme");
        const newTheme = currentTheme === "light" ? "dark" : "light";
        body.setAttribute("data-theme", newTheme);
        localStorage.setItem("theme", newTheme);
        updateThemeIcon(newTheme);
    });

    // Ideas Panel
    btnOpenIdeas.addEventListener("click", () => {
        ideasOverlay.classList.add("open");
        ideasPanel.classList.add("open");
        loadSavedIdeas();
    });
    
    const closeIdeas = () => {
        ideasOverlay.classList.remove("open");
        ideasPanel.classList.remove("open");
    };
    btnCloseIdeas.addEventListener("click", closeIdeas);
    ideasOverlay.addEventListener("click", closeIdeas);

    // Form Navigation
    formStep1.addEventListener("submit", handleStep1Submit);
    btnBack1.addEventListener("click", () => goToStep(1));
    btnGenerateIdea.addEventListener("click", startPipeline);
    btnStartOver.addEventListener("click", resetApp);
});

function updateThemeIcon(theme) {
    const icon = themeToggle.querySelector("i");
    if (theme === "dark") {
        icon.className = "fas fa-sun";
    } else {
        icon.className = "fas fa-moon";
    }
}

// ── Step Navigation ──
function goToStep(stepNum) {
    state.step = stepNum;
    
    // Update panels
    steps.forEach((s, idx) => {
        if (idx + 1 === stepNum) s.classList.add("active");
        else s.classList.remove("active");
    });

    // Update indicators
    indicators.forEach((ind, idx) => {
        if (idx + 1 < stepNum) {
            ind.classList.add("completed");
            ind.classList.remove("active");
        } else if (idx + 1 === stepNum) {
            ind.classList.add("active");
            ind.classList.remove("completed");
        } else {
            ind.classList.remove("active", "completed");
        }
    });

    // Update connectors
    connectors.forEach((conn, idx) => {
        if (idx + 1 < stepNum) conn.classList.add("active");
        else conn.classList.remove("active");
    });
}

// ── Step 1: Gather Pain Points ──
async function handleStep1Submit(e) {
    e.preventDefault();
    
    state.market = document.getElementById("input-market").value;
    state.sector = document.getElementById("input-sector").value;
    state.team_size = document.getElementById("input-team").value;
    state.budget = document.getElementById("input-budget").value;
    state.sessionId = crypto.randomUUID(); // new session

    btnFindPain.disabled = true;
    btnFindPain.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Scraping Web...';

    try {
        const response = await fetch(`${API_BASE}/pain-points`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                market: state.market,
                sector: state.sector,
                session_id: state.sessionId
            })
        });
        
        if (response.ok) {
            // Open SSE connection to listen for updates
            listenToSSE(state.sessionId, handlePainPointEvents);
        } else {
            throw new Error("Failed to start pain point discovery");
        }
    } catch (err) {
        alert(err.message);
        btnFindPain.disabled = false;
        btnFindPain.innerHTML = '<i class="fas fa-search"></i> Find Pain Points';
    }
}

function handlePainPointEvents(event) {
    const data = JSON.parse(event.data);
    
    if (event.type === "status") {
        btnFindPain.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${data.message}`;
    }
    else if (event.type === "pain_points_raw") {
        rawPainPoints.innerHTML = marked.parse(data.content || "No raw data");
    }
    else if (event.type === "pain_points_top") {
        state.pain_points = data.pain_points;
        renderPainPointCards();
        goToStep(2);
        
        // Reset button
        btnFindPain.disabled = false;
        btnFindPain.innerHTML = '<i class="fas fa-search"></i> Find Pain Points';
    }
    else if (event.type === "error") {
        alert("Error: " + data.message);
        btnFindPain.disabled = false;
        btnFindPain.innerHTML = '<i class="fas fa-search"></i> Find Pain Points';
        return true; // close SSE
    }
    else if (event.type === "done") {
        return true; // close SSE
    }
    return false;
}

function renderPainPointCards() {
    painPointCards.innerHTML = "";
    btnGenerateIdea.disabled = true;
    state.selected_pain_point = null;

    state.pain_points.forEach((pp, idx) => {
        const card = document.createElement("div");
        card.className = "pain-point-card";
        card.innerHTML = `
            <div class="card-number">0${idx + 1}</div>
            <p>${pp}</p>
        `;
        
        card.addEventListener("click", () => {
            // Deselect all
            document.querySelectorAll(".pain-point-card").forEach(c => c.classList.remove("selected"));
            // Select this
            card.classList.add("selected");
            state.selected_pain_point = pp;
            btnGenerateIdea.disabled = false;
        });

        painPointCards.appendChild(card);
    });
}

// ── Step 3: Run Full Pipeline ──
async function startPipeline() {
    goToStep(3);
    
    // Reset pipeline UI
    logEntries.innerHTML = "";
    resultStream.innerHTML = "";
    finalDashboard.classList.add("hidden");
    document.querySelectorAll(".pipeline-node").forEach(n => {
        n.classList.remove("active", "completed", "error");
    });
    
    // Reset SVG Path
    const path = document.getElementById("path-progress");
    if (path) {
        const len = path.getTotalLength();
        path.style.strokeDasharray = len;
        path.style.strokeDashoffset = len; // completely hidden
    }
    
    // Start backend pipeline
    try {
        const response = await fetch(`${API_BASE}/generate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                market: state.market,
                sector: state.sector,
                team_size: state.team_size,
                budget: state.budget,
                pain_point: state.selected_pain_point,
                session_id: state.sessionId
            })
        });
        
        if (response.ok) {
            listenToSSE(state.sessionId, handlePipelineEvents);
        } else {
            throw new Error("Failed to start pipeline");
        }
    } catch (err) {
        addLog(`Error: ${err.message}`);
    }
}

function handlePipelineEvents(event) {
    const data = JSON.parse(event.data);
    
    if (event.type === "status") {
        addLog(data.message);
        updatePipelineNode(data.stage);
    }
    else if (event.type === "idea_generated") {
        addStreamCard("idea", `💡 Idea: ${data.idea_name}`, `**STARTUP NAME:** ${data.idea_name}\n\n${data.idea_content}`);
        setNodeComplete("idea");
    }
    else if (event.type === "web_research_done") {
        addStreamCard("research", "🌐 Web Research Found", data.research_report);
    }
    else if (event.type === "judge_originality_result") {
        addStreamCard("judge", `🧑‍⚖️ Originality: ${data.approved ? 'APPROVED' : 'REJECTED'}`, data.reason);
        setNodeComplete("judge", !data.approved); // pass true for error if rejected
    }
    else if (event.type === "analysis_done") {
        addStreamCard("analysis", "📊 Market Analysis", data.analysis);
        setNodeComplete("analysis");
    }
    else if (event.type === "debate_round") {
        const title = data.role === "bull" ? `🐂 Bull (Round ${data.round})` : `🐻 Bear (Round ${data.round})`;
        addStreamCard(data.role, title, data.content);
        if (data.role === "bear" && data.round === 2) {
            setNodeComplete("debate");
        }
    }
    else if (event.type === "verdict") {
        setNodeComplete("verdict");
        renderFinalDashboard(data);
    }
    else if (event.type === "vc_research") {
        addStreamCard("vc", "💰 VC Matchmaking Results", data.vc_report);
        const vcDashboard = document.getElementById("vc-results-container");
        const vcContent = document.getElementById("vc-results-content");
        if (vcDashboard && vcContent) {
            vcDashboard.classList.remove("hidden");
            vcContent.innerHTML = marked.parse(data.vc_report);
        }
    }
    else if (event.type === "error") {
        addLog(`❌ Error: ${data.message}`);
        return true; // close
    }
    else if (event.type === "done") {
        return true; // close
    }
    return false;
}

// ── UI Helpers ──

function listenToSSE(sessionId, callback) {
    const evtSource = new EventSource(`${API_BASE}/stream/${sessionId}`);
    
    // Bind all generic events
    const handle = (e) => {
        const shouldClose = callback(e);
        if (shouldClose) {
            evtSource.close();
        }
    };
    
    evtSource.addEventListener("status", handle);
    evtSource.addEventListener("pain_points_raw", handle);
    evtSource.addEventListener("pain_points_top", handle);
    evtSource.addEventListener("idea_generated", handle);
    evtSource.addEventListener("web_research_done", handle);
    evtSource.addEventListener("judge_originality_result", handle);
    evtSource.addEventListener("analysis_done", handle);
    evtSource.addEventListener("debate_round", handle);
    evtSource.addEventListener("verdict", handle);
    evtSource.addEventListener("vc_research", handle);
    evtSource.addEventListener("saved", handle);
    evtSource.addEventListener("error", handle);
    evtSource.addEventListener("done", handle);
    
    evtSource.onerror = () => evtSource.close();
}

function addLog(msg) {
    const entry = document.createElement("div");
    entry.className = "log-entry";
    entry.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
    logEntries.appendChild(entry);
    // Auto-scroll
    logEntries.parentElement.scrollTop = logEntries.parentElement.scrollHeight;
}

function updatePipelineNode(stage) {
    // Mapping internal stage names to UI nodes
    const map = {
        "idea_generation": "idea",
        "judge_originality": "judge",
        "analysis": "analysis",
        "dialectic_start": "debate",
        "bull_r1": "debate",
        "bear_r1": "debate",
        "bull_r2": "debate",
        "bear_r2": "debate",
        "investment_judge": "verdict"
    };
    
    const nodeId = map[stage];
    if (nodeId) {
        document.querySelectorAll(".pipeline-node").forEach(n => n.classList.remove("active"));
        const node = document.getElementById(`node-${nodeId}`);
        if (node && !node.classList.contains("completed")) {
            node.classList.add("active");
        }
    }
}

function setNodeComplete(nodeId, isError = false) {
    const node = document.getElementById(`node-${nodeId}`);
    if (node) {
        node.classList.remove("active");
        node.classList.add(isError ? "error" : "completed");
        
        if (!isError) {
            updatePathProgress(nodeId);
        }
    }
}

function updatePathProgress(completedNodeId) {
    const path = document.getElementById("path-progress");
    if (!path) return;
    
    const length = path.getTotalLength();
    if (!path.style.strokeDasharray) {
        path.style.strokeDasharray = length;
    }
    
    const progressMap = {
        "idea": 0.25,
        "judge": 0.50,
        "analysis": 0.75,
        "debate": 1.0,
        "verdict": 1.0
    };
    
    const percent = progressMap[completedNodeId] || 0;
    const offset = length - (length * percent);
    path.style.strokeDashoffset = offset;
}

function getNextNode(curr) {
    const flow = ["idea", "judge", "analysis", "debate", "verdict"];
    return flow[flow.indexOf(curr) + 1] || "";
}

function addStreamCard(type, title, mdContent) {
    const card = document.createElement("div");
    card.className = `stream-card ${type}`;
    
    // Default collapsed unless it's an idea or short judge reason
    const isCollapsed = ["research", "analysis", "bull", "bear"].includes(type);
    
    card.innerHTML = `
        <div class="stream-card-header ${isCollapsed ? 'collapsed' : ''}" onclick="this.classList.toggle('collapsed'); this.nextElementSibling.classList.toggle('collapsed');">
            <span>${title}</span>
            <i class="fas fa-chevron-down chevron"></i>
        </div>
        <div class="stream-card-body md-content ${isCollapsed ? 'collapsed' : ''}">
            ${marked.parse(mdContent)}
        </div>
    `;
    
    resultStream.appendChild(card);
}

function renderFinalDashboard(data) {
    finalDashboard.classList.remove("hidden");
    
    const banner = document.getElementById("verdict-banner");
    const badge = document.getElementById("verdict-badge");
    const score = document.getElementById("verdict-score");
    const exp = document.getElementById("verdict-explanation");
    
    if (data.investable) {
        banner.className = "verdict-banner investable";
        badge.className = "verdict-badge investable";
        badge.innerHTML = "✅ INVESTABLE";
        triggerConfetti();
    } else {
        banner.className = "verdict-banner not-investable";
        badge.className = "verdict-badge not-investable";
        badge.innerHTML = "❌ NOT INVESTABLE";
    }
    
    score.textContent = data.score.toFixed(1);
    exp.innerHTML = `<strong>Explanation:</strong><br>${marked.parse(data.explanation)}`;
}

function resetApp() {
    state.sessionId = crypto.randomUUID();
    goToStep(1);
    finalDashboard.classList.add("hidden");
    const vcContainer = document.getElementById("vc-results-container");
    if (vcContainer) vcContainer.classList.add("hidden");
    resultStream.innerHTML = "";
    logEntries.innerHTML = "";
}

// ── Saved Ideas Logic ──
async function loadSavedIdeas() {
    ideasList.innerHTML = '<div class="text-center mt-32"><i class="fas fa-spinner fa-spin fa-2x"></i></div>';
    
    try {
        const res = await fetch(`${API_BASE}/ideas`);
        const ideas = await res.json();
        
        if (ideas.length === 0) {
            ideasList.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📂</div>
                    <p>No saved ideas yet.</p>
                </div>
            `;
            return;
        }
        
        ideasList.innerHTML = "";
        ideas.forEach(idea => {
            const card = document.createElement("div");
            card.className = "idea-card";
            card.innerHTML = `
                <div class="idea-card-title">
                    🚀 ${idea.idea_name}
                </div>
                <div class="idea-card-meta">
                    Topic: ${idea.topic} • ${idea.timestamp.split(' ')[0]}
                </div>
                <div class="idea-card-score">Score: ${idea.score?.toFixed(1) || '-'}</div>
                
                <div class="idea-card-content md-content">
                    ${marked.parse(idea.idea_description)}
                    <h4 class="mt-16">Verdict</h4>
                    <p>${idea.explanation}</p>
                    ${idea.vc_report ? `<h4 class="mt-16"><i class="fas fa-handshake"></i> Matched VCs</h4><div style="background: var(--bg-alt); padding: 12px; border-radius: var(--radius-sm); border: 1px solid var(--border); margin-top: 8px;">${marked.parse(idea.vc_report)}</div>` : ''}
                </div>
                
                <div class="idea-card-actions">
                    <button class="btn btn-primary btn-sm btn-expand"><i class="fas fa-expand"></i> View</button>
                    <button class="btn btn-danger btn-sm btn-delete"><i class="fas fa-trash"></i> Delete</button>
                </div>
            `;
            
            card.querySelector(".btn-expand").addEventListener("click", () => {
                card.classList.toggle("expanded");
            });
            
            card.querySelector(".btn-delete").addEventListener("click", async () => {
                if(confirm("Delete this idea?")) {
                    await fetch(`${API_BASE}/ideas/${idea.id}`, { method: "DELETE" });
                    loadSavedIdeas();
                }
            });
            
            ideasList.appendChild(card);
        });
        
    } catch (e) {
        ideasList.innerHTML = `<p style="color:red">Failed to load ideas: ${e.message}</p>`;
    }
}

// ── Confetti ──
function triggerConfetti() {
    const container = document.getElementById("confetti");
    const colors = ["#FFE156", "#FF6B9D", "#7BF178", "#56CFFF", "#B388FF"];
    
    for (let i = 0; i < 100; i++) {
        const piece = document.createElement("div");
        piece.className = "confetti-piece";
        piece.style.left = Math.random() * 100 + "vw";
        piece.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
        piece.style.animationDuration = (Math.random() * 2 + 2) + "s";
        piece.style.animationDelay = (Math.random() * 0.5) + "s";
        container.appendChild(piece);
        
        setTimeout(() => piece.remove(), 4000);
    }
}
