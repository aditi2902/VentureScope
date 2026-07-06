# Migrate from Streamlit to Neobrutalist Web App

Replace the Streamlit-based UI (`agent.py`) with a **Flask backend + vanilla HTML/CSS/JS frontend** featuring a stunning **neobrutalism** design with 3D elements, interactive animations, and a multi-step pipeline flow inspired by [ideaproof.io](https://ideaproof.io).

## User Review Required

> [!IMPORTANT]
> **This is a major UI rewrite.** The backend Python logic (LLM calls, web research, dialectic debate, judge, embeddings) stays **100% untouched**. Only the UI layer and its API bridge change.

> [!WARNING]
> The current `agent.py` (Streamlit) will be replaced by `app.py` (Flask). You can still keep `agent.py` as a backup if needed.

## Open Questions

> [!IMPORTANT]
> **Port**: The Flask app will run on `http://localhost:5000`. Is that OK, or do you prefer a different port?

## Proposed Changes

### Backend — Flask API Server

#### [NEW] [app.py](file:///c:/Users/Shloka%20Pol/OneDrive/Desktop/ai_startup_agent/app.py)
Flask server that exposes REST API endpoints. All the existing Python modules (`database.py`, `dialectic.py`, `judge.py`, `pain_points.py`, `web_research.py`, `embeddings.py`, `search_client.py`) are imported and used **as-is** — no changes to business logic.

**API Endpoints:**
| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/` | Serve the main HTML page |
| `GET` | `/api/ideas` | Fetch all saved ideas from DB |
| `DELETE` | `/api/ideas/<id>` | Delete a saved idea |
| `POST` | `/api/pain-points` | Run pain point discovery pipeline (market, sector) |
| `POST` | `/api/generate` | Run the full pipeline: idea generation → judge → analysis → dialectic debate → save |
| `GET` | `/api/status` | SSE (Server-Sent Events) endpoint for real-time progress updates |

Key design decisions:
- **SSE (Server-Sent Events)** for streaming live progress to the frontend (e.g., "🌐 Scraping Play Store...", "🐂 Bull Case Round 1...", "⚖️ Judge deliberating...") — no WebSocket complexity needed
- Long-running pipeline runs in a background thread, pushes status updates via SSE
- CORS enabled for local development

---

### Frontend — Neobrutalism UI

#### [NEW] [static/index.html](file:///c:/Users/Shloka%20Pol/OneDrive/Desktop/ai_startup_agent/static/index.html)
Single-page application with these sections/views:

**1. Hero / Landing Section**
- Bold neobrutalist hero with thick black borders, offset shadows, and vibrant color blocks
- Animated 3D floating rocket/lightbulb icons using CSS transforms
- Punchy headline: "Turn Market Pain Into Startup Gold 🚀"
- Smooth scroll to the input wizard

**2. Multi-Step Input Wizard (Inspired by ideaproof.io "How It Works")**
- **Step 01**: Enter Market/Domain (big input with neobrutalist thick border)
- **Step 02**: Select Sector, Team Size, Budget (card-based selection with hover lift effects)
- **Step 03**: Pain Point Discovery → Select from top 3 (radio cards with 3D press effect)
- Numbered step indicators with connecting lines (like ideaproof.io's `01 → 02 → 03` flow)
- Each step slides in with CSS animations

**3. Pipeline Progress View ("Watch It Work" — inspired by ideaproof.io's flow map)**
- Horizontal pipeline visualization showing each stage as a connected node:
  `💡 Idea Gen → 🧑‍⚖️ Judge → 📊 Analysis → 🐂 Bull Case → 🐻 Bear Case → ⚖️ Verdict`
- Each node lights up / animates when active (pulsing glow, checkmark on complete)
- Live log stream below showing real-time LLM progress messages
- 3D rotating loading spinner during processing

**4. Results Dashboard**
- **Startup Card**: Big neobrutalist card with startup name, description, score badge
- **Analysis Panel**: Expandable/collapsible sections for market analysis
- **Dialectic Debate**: Side-by-side Bull 🐂 vs Bear 🐻 columns with colored backgrounds
- **Verdict Badge**: Large animated INVESTABLE/NOT INVESTABLE badge with score ring
- **Save confirmation** with confetti animation on success

**5. Sidebar → Saved Ideas Gallery**
- Grid of neobrutalist cards showing all approved ideas
- Each card: name, topic, score, timestamp, delete button
- Click to expand full details in a modal

#### [NEW] [static/styles.css](file:///c:/Users/Shloka%20Pol/OneDrive/Desktop/ai_startup_agent/static/styles.css)
Complete neobrutalism design system:

**Design Tokens:**
- **Colors**: Vibrant primaries — Electric Yellow `#FFE156`, Hot Pink `#FF6B9D`, Acid Green `#7BF178`, Sky Blue `#56CFFF`, Soft Cream `#FFF8E7` background
- **Borders**: 3-4px solid black everywhere (signature neobrutalism)
- **Shadows**: Hard offset box-shadows (`4px 4px 0px #000`, `8px 8px 0px #000`)
- **Typography**: `Space Grotesk` (headings) + `Inter` (body) from Google Fonts
- **Border-radius**: 0px-12px (sharp or slightly rounded — neobrutalist signature)

**Animations & Effects:**
- Button hover: translate up + shadow grows (3D lift effect)
- Button active/press: translate down + shadow shrinks (3D press effect)
- Card hover: subtle rotate + scale with perspective transform
- Pipeline nodes: pulse animation when active, checkmark slide-in on complete
- Step transitions: slide-in from right with opacity fade
- Confetti burst on idea approval
- Floating background shapes (circles, squares) with slow CSS animation
- Smooth scroll behavior
- Dark/light theme toggle (neobrutalism works beautifully in both)

#### [NEW] [static/app.js](file:///c:/Users/Shloka%20Pol/OneDrive/Desktop/ai_startup_agent/static/app.js)
Vanilla JavaScript SPA logic:
- State management (current step, form data, results)
- Fetch API calls to Flask endpoints
- SSE listener for real-time pipeline progress
- DOM manipulation for step transitions
- Pipeline visualization controller
- Saved ideas gallery (fetch + render + delete)
- Confetti animation on approval
- Theme toggle (dark/light)

---

### Dependency Updates

#### [MODIFY] [requirements.txt](file:///c:/Users/Shloka%20Pol/OneDrive/Desktop/ai_startup_agent/requirements.txt)
Add `flask` and `flask-cors`. Remove `streamlit` since we're migrating away from it.

```diff
-streamlit>=1.30.0
+flask>=3.0.0
+flask-cors>=4.0.0
```

---

## Architecture Summary

```
┌─────────────────────────────────────────────────────────┐
│  BROWSER (localhost:5000)                               │
│  ┌───────────────┐  ┌──────────────┐  ┌─────────────┐  │
│  │  index.html   │  │  styles.css  │  │   app.js    │  │
│  │  (Structure)  │  │  (Neobrutal) │  │  (Logic)    │  │
│  └───────┬───────┘  └──────────────┘  └──────┬──────┘  │
│          │              Fetch API + SSE       │         │
└──────────┼────────────────────────────────────┼─────────┘
           │                                    │
           ▼                                    ▼
┌──────────────────────────────────────────────────────────┐
│  FLASK SERVER (app.py)                                   │
│  ┌──────────┐  ┌─────────┐  ┌───────────┐  ┌─────────┐ │
│  │ /api/    │  │ pain_   │  │ dialectic │  │ judge   │ │
│  │ routes   │→ │ points  │→ │ .py       │→ │ .py     │ │
│  └──────────┘  └─────────┘  └───────────┘  └─────────┘ │
│  ┌──────────┐  ┌─────────────┐  ┌───────────────────┐  │
│  │ database │  │ web_research│  │ embeddings /      │  │
│  │ .py      │  │ .py         │  │ search_client.py  │  │
│  └──────────┘  └─────────────┘  └───────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

## Verification Plan

### Automated Tests
```bash
# Start the Flask server
python app.py

# In another terminal, test API endpoints
curl http://localhost:5000/api/ideas
curl -X POST http://localhost:5000/api/pain-points -H "Content-Type: application/json" -d "{\"market\": \"fitness apps\", \"sector\": \"B2C Mobile App\"}"
```

### Manual Verification
- Open `http://localhost:5000` in browser
- Walk through the full flow: enter market → select pain point → generate idea → view results
- Verify ideas appear in saved gallery
- Verify delete works
- Check neobrutalism styling, animations, and responsiveness
- Test SSE progress updates during pipeline execution
