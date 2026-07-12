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

// VCs Panel
const btnOpenVcs = document.getElementById("btn-open-vcs");
const btnCloseVcs = document.getElementById("btn-close-vcs");
const vcsOverlay = document.getElementById("vcs-overlay");
const vcsPanel = document.getElementById("vcs-panel");
const vcsList = document.getElementById("vcs-list");

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
        closeVcs();
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

    // VCs Panel
    if (btnOpenVcs) {
        btnOpenVcs.addEventListener("click", () => {
            closeIdeas();
            vcsOverlay.classList.add("open");
            vcsPanel.classList.add("open");
            loadVCMatchmaker();
        });
    }
    
    const closeVcs = () => {
        vcsOverlay.classList.remove("open");
        vcsPanel.classList.remove("open");
    };
    if (btnCloseVcs) btnCloseVcs.addEventListener("click", closeVcs);
    if (vcsOverlay) vcsOverlay.addEventListener("click", closeVcs);

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

function parseVCsFromReport(reportText) {
    const vcs = [];
    const lines = reportText.split('\n');
    let currentVC = null;
    
    for (let line of lines) {
        line = line.trim();
        // Check for new VC item: starts with - ** or * **
        const headerMatch = line.match(/^[-*]\s+\*\*([^*]+)\*\*(?:\s+\(([^)]+)\))?/);
        if (headerMatch) {
            if (currentVC) {
                vcs.push(currentVC);
            }
            currentVC = {
                name: headerMatch[1].trim(),
                location: headerMatch[2] ? headerMatch[2].trim() : "",
                email: "",
                website: ""
            };
        } else if (currentVC) {
            // Check for fields under current VC
            const emailMatch = line.match(/[-*]\s+\*?Email:\*?\s*(\S+@\S+)/i) || line.match(/Found Emails:\s*(\S+@\S+)/i);
            const webMatch = line.match(/[-*]\s+\*?Website:\*?\s*\[([^\]]+)\]/i) || line.match(/Website:\s*(\S+)/i);
            
            if (emailMatch) {
                // Strip trailing commas, periods or brackets if any
                currentVC.email = emailMatch[1].trim().replace(/[.,()<>]/g, "");
            }
            if (webMatch) {
                currentVC.website = webMatch[1].trim();
            }
        }
    }
    if (currentVC) {
        vcs.push(currentVC);
    }
    
    // Add default fallbacks if parsing fails to find anything
    if (vcs.length === 0) {
        return [
            { name: "Sequoia Capital", email: "info@sequoiacap.com", location: "Menlo Park, CA" },
            { name: "Andreessen Horowitz", email: "info@a16z.com", location: "Menlo Park, CA" },
            { name: "Y Combinator", email: "apply@ycombinator.com", location: "Mountain View, CA" }
        ];
    }
    return vcs;
}

async function loadVCMatchmaker() {
    vcsList.innerHTML = '<div class="text-center mt-32"><i class="fas fa-spinner fa-spin fa-2x"></i></div>';
    
    try {
        const res = await fetch(`${API_BASE}/ideas`);
        const ideas = await res.json();
        
        // Filter ideas that have a vc_report
        const matchedIdeas = ideas.filter(idea => idea.vc_report);
        
        if (matchedIdeas.length === 0) {
            vcsList.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">💰</div>
                    <p>No VC matchings generated yet. Run a startup generation pipeline to discover matched VCs.</p>
                </div>
            `;
            return;
        }
        
        vcsList.innerHTML = "";
        matchedIdeas.forEach(idea => {
            const vcs = parseVCsFromReport(idea.vc_report);
            
            const card = document.createElement("div");
            card.className = "idea-card"; // Re-use the existing card styling
            
            // Build options for selector
            let selectorOptions = "";
            vcs.forEach(vc => {
                const display = `${vc.name} ${vc.location ? `(${vc.location})` : ''} - ${vc.email || 'No email'}`;
                selectorOptions += `<option value="${vc.email || 'info@' + (vc.website || 'firm.com')}" data-name="${vc.name}">${display}</option>`;
            });

            card.innerHTML = `
                <div class="idea-card-title flex-between" style="border-bottom: 2px solid var(--border); padding-bottom: 12px; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between;">
                    <span>🚀 ${idea.idea_name}</span>
                    <span style="font-size: 0.75rem; background: var(--green); padding: 4px 8px; border-radius: var(--radius-sm); border: 2px solid var(--border); font-weight: bold;">
                        ${idea.sector || 'General'}
                    </span>
                </div>
                <div class="idea-card-meta mb-16" style="margin-bottom: 16px;">
                    <strong>Market Focus:</strong> ${idea.topic}
                </div>
                <div class="vc-report-container md-content" style="max-height: 300px; overflow-y: auto; background: var(--bg-alt); padding: 16px; border-radius: var(--radius-sm); border: 2px solid var(--border); margin-bottom: 16px;">
                    ${marked.parse(idea.vc_report)}
                </div>
                
                <div class="pitch-setup-section" style="border-top: 2px dashed var(--border); padding-top: 16px;">
                    <label style="display:block; font-weight:bold; font-size:0.85rem; margin-bottom: 6px; font-family: var(--font-heading);">Select Match VC for Direct Pitch:</label>
                    <div style="display:flex; gap: 8px;">
                        <select class="form-select vc-selector" style="flex: 1; padding: 8px 12px; border: var(--border-w) solid var(--border); border-radius: var(--radius-sm); font-size: 0.85rem; background: var(--surface); color: var(--text);">
                            ${selectorOptions}
                        </select>
                        <button class="btn btn-primary btn-sm btn-initiate-pitch" style="white-space: nowrap;"><i class="fas fa-edit"></i> Draft Pitch</button>
                    </div>
                </div>
                <div class="pitch-draft-area-container"></div>
            `;
            
            // Add handler for draft cold email pitch
            const btnInitiate = card.querySelector(".btn-initiate-pitch");
            const vcSelector = card.querySelector(".vc-selector");
            const draftContainer = card.querySelector(".pitch-draft-area-container");
            
            btnInitiate.addEventListener("click", () => {
                let pitchDiv = draftContainer.querySelector(".pitch-draft-area");
                if (pitchDiv) {
                    pitchDiv.remove();
                    btnInitiate.innerHTML = '<i class="fas fa-edit"></i> Draft Pitch';
                } else {
                    const selectedOption = vcSelector.options[vcSelector.selectedIndex];
                    const vcName = selectedOption.getAttribute("data-name");
                    const vcEmail = vcSelector.value;
                    
                    pitchDiv = document.createElement("div");
                    pitchDiv.className = "pitch-draft-area mt-16";
                    pitchDiv.style = "background: var(--surface); padding: 16px; border: var(--border-w) solid var(--border); border-radius: var(--radius-sm); font-family: var(--font-body); font-size: 0.85rem; margin-top: 16px;";
                    
                    const defaultSubject = `Intro: ${idea.idea_name} - Solving ${idea.topic} pain points`;
                    const defaultBody = `Hi,\n\nI saw your investments in the ${idea.topic} sector. We're launching ${idea.idea_name} to solve user pain points like:\n\n"${idea.pain_point || 'general market gaps'}".\n\nGiven your focus, I thought this would align with your portfolio. Let me know if you'd like to see our pitch deck!\n\nBest,\n[Your Name]`;
                    
                    pitchDiv.innerHTML = `
                        <div style="font-weight: bold; margin-bottom: 12px; border-bottom: 2px solid var(--border); padding-bottom: 6px; display: flex; justify-content: space-between; align-items: center; font-family: var(--font-heading);">
                            <span>📧 Pitch Email to ${vcName}</span>
                            <button class="btn btn-secondary btn-sm btn-copy-pitch" style="padding: 2px 8px; font-size: 0.75rem;"><i class="fas fa-copy"></i> Copy</button>
                        </div>
                        
                        <div class="form-group" style="margin-bottom: 12px;">
                            <label style="display:block; font-weight:bold; margin-bottom:4px;">To:</label>
                            <input type="email" class="form-input pitch-email-to" value="${vcEmail}" style="padding: 6px 10px; font-size: 0.85rem; font-family: var(--font-mono);">
                        </div>
                        
                        <div class="form-group" style="margin-bottom: 12px;">
                            <label style="display:block; font-weight:bold; margin-bottom:4px;">Subject:</label>
                            <input type="text" class="form-input pitch-email-subject" value="${defaultSubject}" style="padding: 6px 10px; font-size: 0.85rem;">
                        </div>
                        
                        <div class="form-group" style="margin-bottom: 16px;">
                            <label style="display:block; font-weight:bold; margin-bottom:4px;">Body:</label>
                            <textarea class="form-input pitch-email-body" rows="8" style="padding: 10px; font-size: 0.85rem; font-family: var(--font-body); resize: vertical; height: 150px; line-height: 1.5;">${defaultBody}</textarea>
                        </div>
                        
                        <div style="display: flex; gap: 8px;">
                            <a href="" target="_blank" class="btn btn-success btn-sm btn-send-email" style="flex: 1; text-align: center; display: inline-flex; align-items: center; justify-content: center; gap: 6px; background: var(--green); color: var(--text);">
                                <i class="fas fa-paper-plane"></i> Send Email Directly
                            </a>
                        </div>
                    `;
                    
                    const toInput = pitchDiv.querySelector(".pitch-email-to");
                    const subjectInput = pitchDiv.querySelector(".pitch-email-subject");
                    const bodyInput = pitchDiv.querySelector(".pitch-email-body");
                    const sendBtn = pitchDiv.querySelector(".btn-send-email");
                    
                    const refreshMailto = () => {
                        const to = toInput.value;
                        const subject = subjectInput.value;
                        const body = bodyInput.value;
                        sendBtn.href = `mailto:${encodeURIComponent(to)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
                    };
                    
                    // Bind change handlers
                    toInput.addEventListener("input", refreshMailto);
                    subjectInput.addEventListener("input", refreshMailto);
                    bodyInput.addEventListener("input", refreshMailto);
                    
                    // Initial load
                    refreshMailto();
                    
                    // Add copy handler
                    pitchDiv.querySelector(".btn-copy-pitch").addEventListener("click", () => {
                        navigator.clipboard.writeText(`To: ${toInput.value}\nSubject: ${subjectInput.value}\n\n${bodyInput.value}`);
                        alert('Copied draft details to clipboard!');
                    });
                    
                    draftContainer.appendChild(pitchDiv);
                    btnInitiate.innerHTML = '<i class="fas fa-times"></i> Close Pitch';
                }
            });
            
            vcsList.appendChild(card);
        });
        
    } catch (e) {
        vcsList.innerHTML = `<p style="color:red">Failed to load VC matchings: ${e.message}</p>`;
    }
}

// ═══════════════════════════════════════════════════════
// PITCH MY IDEA — Panel, Form, SSE, UI Rendering
// ═══════════════════════════════════════════════════════

const btnOpenPitch  = document.getElementById("btn-open-pitch");
const btnClosePitch = document.getElementById("btn-close-pitch");
const pitchOverlay  = document.getElementById("pitch-overlay");
const pitchPanel    = document.getElementById("pitch-panel");

const pitchStep1    = document.getElementById("pitch-step-1");
const pitchStep2    = document.getElementById("pitch-step-2");
const pitchTab1     = document.getElementById("pitch-tab-1");
const pitchTab2     = document.getElementById("pitch-tab-2");

const pitchForm     = document.getElementById("pitch-form");
const btnPitchRedo  = document.getElementById("btn-pitch-redo");

const pitchLogEntries       = document.getElementById("pitch-log-entries");
const readinessGaugeSection = document.getElementById("readiness-gauge-section");
const gaugeFill             = document.getElementById("gauge-fill");
const gaugeScoreText        = document.getElementById("gauge-score-text");
const readinessLabel        = document.getElementById("readiness-label");
const dimensionGrid         = document.getElementById("dimension-grid");
const suggestionsBlock      = document.getElementById("suggestions-block");
const suggestionsList       = document.getElementById("suggestions-list");
const pitchVcSection        = document.getElementById("pitch-vc-section");
const pitchVcContent        = document.getElementById("pitch-vc-content");
const pitchRedo             = document.getElementById("pitch-redo");

let pitchSessionId = crypto.randomUUID();

// ── Open / Close ──
function closePitchPanel() {
    pitchOverlay.classList.remove("open");
    pitchPanel.classList.remove("open");
}

function openPitchPanel() {
    // Close other panels first
    document.getElementById("ideas-overlay").classList.remove("open");
    document.getElementById("ideas-panel").classList.remove("open");
    document.getElementById("vcs-overlay").classList.remove("open");
    document.getElementById("vcs-panel").classList.remove("open");
    pitchOverlay.classList.add("open");
    pitchPanel.classList.add("open");
}

if (btnOpenPitch)  btnOpenPitch.addEventListener("click", openPitchPanel);
if (btnClosePitch) btnClosePitch.addEventListener("click", closePitchPanel);
if (pitchOverlay)  pitchOverlay.addEventListener("click", closePitchPanel);

// ── Step navigation ──
function showPitchStep(num) {
    if (num === 1) {
        pitchStep1.classList.remove("hidden");
        pitchStep2.classList.add("hidden");
        pitchTab1.classList.add("active");
        pitchTab2.classList.remove("active");
    } else {
        pitchStep1.classList.add("hidden");
        pitchStep2.classList.remove("hidden");
        pitchTab1.classList.remove("active");
        pitchTab2.classList.add("active");
    }
}

// ── Form submit ──
if (pitchForm) {
    pitchForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        pitchSessionId = crypto.randomUUID();

        const payload = {
            session_id:       pitchSessionId,
            startup_name:     document.getElementById("pitch-name").value.trim(),
            domain:           document.getElementById("pitch-domain").value.trim(),
            sector:           document.getElementById("pitch-sector").value,
            stage:            document.getElementById("pitch-stage").value,
            monthly_revenue:  document.getElementById("pitch-monthly-revenue").value.trim(),
            annual_turnover:  document.getElementById("pitch-annual-turnover").value.trim(),
            team_size:        document.getElementById("pitch-team-size").value,
            description:      document.getElementById("pitch-description").value.trim(),
            problem_solved:   document.getElementById("pitch-problem").value.trim(),
            target_customer:  document.getElementById("pitch-customer").value.trim(),
            competitors:      document.getElementById("pitch-competitors").value.trim(),
            funding_sought:   document.getElementById("pitch-funding").value,
        };

        if (!payload.startup_name || !payload.domain || !payload.description || !payload.problem_solved) {
            alert("Please fill in all required fields (marked with *).");
            return;
        }

        // Reset step 2 UI
        pitchLogEntries.innerHTML = "";
        readinessGaugeSection.classList.add("hidden");
        dimensionGrid.classList.add("hidden");
        dimensionGrid.innerHTML = "";
        suggestionsBlock.classList.add("hidden");
        suggestionsList.innerHTML = "";
        pitchVcSection.classList.add("hidden");
        pitchVcContent.innerHTML = "";
        pitchRedo.classList.add("hidden");

        // Reset gauge
        gaugeFill.style.strokeDashoffset = "502.65";
        gaugeFill.className = "gauge-fill";
        gaugeScoreText.textContent = "0.0";
        readinessLabel.textContent = "Calculating...";
        readinessLabel.className = "readiness-title";

        showPitchStep(2);

        const submitBtn = document.getElementById("btn-pitch-submit");
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Evaluating...';

        try {
            const res = await fetch(`${API_BASE}/evaluate-idea`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                listenToPitchSSE(pitchSessionId);
            } else {
                throw new Error("Failed to start evaluation");
            }
        } catch (err) {
            addPitchLog(`❌ Error: ${err.message}`);
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-magic"></i> Evaluate My Startup';
        }
    });
}

if (btnPitchRedo) {
    btnPitchRedo.addEventListener("click", () => {
        showPitchStep(1);
        const submitBtn = document.getElementById("btn-pitch-submit");
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-magic"></i> Evaluate My Startup';
        }
    });
}

// ── SSE for pitch ──
function listenToPitchSSE(sessionId) {
    const evtSource = new EventSource(`${API_BASE}/stream/${sessionId}`);

    const events = ["status", "eval_result", "vc_research", "saved", "error", "done"];
    events.forEach(evt => {
        evtSource.addEventListener(evt, (e) => {
            const shouldClose = handlePitchEvent(e);
            if (shouldClose) evtSource.close();
        });
    });

    evtSource.onerror = () => evtSource.close();
}

function handlePitchEvent(event) {
    const data = JSON.parse(event.data);

    if (event.type === "status") {
        addPitchLog(data.message);
    }
    else if (event.type === "eval_result") {
        addPitchLog(data.message);
        renderReadinessGauge(data.overall_score);
        renderDimensionCards(data.dimensions);
        renderSuggestions(data.dimensions);
    }
    else if (event.type === "vc_research") {
        addPitchLog(data.message);
        pitchVcSection.classList.remove("hidden");
        pitchVcContent.innerHTML = marked.parse(data.vc_report || "No VC data.");
    }
    else if (event.type === "saved") {
        addPitchLog("💾 Evaluation saved to database.");
        pitchRedo.classList.remove("hidden");
    }
    else if (event.type === "error") {
        addPitchLog(`❌ Error: ${data.message}`);
        pitchRedo.classList.remove("hidden");
        return true;
    }
    else if (event.type === "done") {
        pitchRedo.classList.remove("hidden");
        return true;
    }
    return false;
}

// ── UI helpers ──
function addPitchLog(msg) {
    const el = document.createElement("div");
    el.className = "log-entry";
    el.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
    pitchLogEntries.appendChild(el);
    pitchLogEntries.parentElement.scrollTop = pitchLogEntries.parentElement.scrollHeight;
}

function getScoreClass(score) {
    if (score >= 7) return "high";
    if (score >= 4.5) return "mid";
    return "low";
}

function getReadinessLabel(score) {
    if (score >= 8.5) return "🚀 Investor-Ready!";
    if (score >= 7)   return "✅ Strong Startup";
    if (score >= 5.5) return "📈 Promising, Needs Work";
    if (score >= 4)   return "⚠️ Early Stage";
    return "🛠 Needs Major Work";
}

function renderReadinessGauge(score) {
    readinessGaugeSection.classList.remove("hidden");

    const circumference = 502.65;
    const fraction = Math.min(Math.max(score / 10, 0), 1);
    const offset = circumference - fraction * circumference;

    const cls = getScoreClass(score);
    gaugeFill.className = `gauge-fill score-${cls}`;
    readinessLabel.className = `readiness-title score-${cls}`;

    // Animate number counter
    let current = 0;
    const target = score;
    const steps = 40;
    const increment = target / steps;
    const interval = setInterval(() => {
        current = Math.min(current + increment, target);
        gaugeScoreText.textContent = current.toFixed(1);
        if (current >= target) clearInterval(interval);
    }, 30);

    // Animate SVG ring
    setTimeout(() => {
        gaugeFill.style.strokeDashoffset = offset;
    }, 50);

    readinessLabel.textContent = getReadinessLabel(score);
}

function renderDimensionCards(dimensions) {
    if (!dimensions || !dimensions.length) return;
    dimensionGrid.classList.remove("hidden");
    dimensionGrid.innerHTML = "";

    dimensions.forEach(dim => {
        const cls = getScoreClass(dim.score);
        const barPct = (dim.score / 10 * 100).toFixed(1);

        const card = document.createElement("div");
        card.className = "dimension-card";
        card.innerHTML = `
            <div class="dimension-card-header">
                <span class="dimension-name">${dim.name}</span>
                <span class="dimension-score-badge ${cls}">${dim.score.toFixed(1)}</span>
            </div>
            <div class="dimension-bar-track">
                <div class="dimension-bar-fill ${cls}" style="width:0%" data-target="${barPct}"></div>
            </div>
            <div class="dimension-feedback">${dim.feedback || ""}</div>
        `;
        dimensionGrid.appendChild(card);

        // Animate bar after render
        requestAnimationFrame(() => {
            setTimeout(() => {
                const fill = card.querySelector(".dimension-bar-fill");
                if (fill) fill.style.width = `${barPct}%`;
            }, 80);
        });
    });
}

function renderSuggestions(dimensions) {
    const hasSuggestions = dimensions.some(d => d.suggestion && d.suggestion.trim());
    if (!hasSuggestions) return;

    suggestionsBlock.classList.remove("hidden");
    suggestionsList.innerHTML = "";

    let idx = 1;
    dimensions.forEach(dim => {
        if (!dim.suggestion || !dim.suggestion.trim()) return;
        const item = document.createElement("div");
        item.className = "suggestion-item";
        item.innerHTML = `
            <div class="suggestion-bullet">${idx}</div>
            <div>
                <div class="suggestion-dim-label">${dim.name}</div>
                <div class="suggestion-text">${dim.suggestion}</div>
            </div>
        `;
        suggestionsList.appendChild(item);
        idx++;
    });
}
