"""
app.py — Flask backend for AI Startup Agent.

Replaces the Streamlit UI with a REST API + SSE streaming server.
All existing Python modules (database, dialectic, judge, pain_points,
web_research, embeddings, search_client) are imported and used as-is.
"""

import os
import json
import time
import uuid
import threading
from queue import Queue, Empty
from flask import Flask, request, jsonify, Response, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv(override=True)

# ── App Setup ──
app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app)

# ── Database Init ──
from database import init_db, save_idea, get_all_ideas, delete_idea

_db_error = None
try:
    init_db()
except Exception as e:
    _db_error = str(e)
    print(f"[app] DB init error (will use SQLite fallback): {e}")

# ── LLM Loading ──
from langchain_openai import ChatOpenAI

def _make_nvidia_llm(model: str, temperature: float):
    """Helper to create a tracked Nvidia NIM LLM."""
    llm = ChatOpenAI(
        model=model,
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=os.environ.get("NVIDIA_API_KEY"),
        temperature=temperature,
    )
    original_invoke = llm.invoke
    def tracked_invoke(*args, **kwargs):
        print(f"🤖 [LLM CALL] -> Model: {model} (Nvidia NIM)")
        return original_invoke(*args, **kwargs)
    object.__setattr__(llm, "invoke", tracked_invoke)
    return llm

def load_llama_llm():
    return _make_nvidia_llm("meta/llama-3.1-70b-instruct", temperature=0.7)

def load_qwen_judge_llm():
    """Separate instance using local Qwen for structured evaluation tasks."""
    from langchain_ollama import ChatOllama
    llm = ChatOllama(model="qwen3:8b", temperature=0.2)
    original_invoke = llm.invoke
    def tracked_invoke(*args, **kwargs):
        print(f"🤖 [LLM CALL] -> Model: qwen3:8b (Ollama Judge)")
        return original_invoke(*args, **kwargs)
    object.__setattr__(llm, "invoke", tracked_invoke)
    return llm

try:
    llama_llm = load_llama_llm()
    judge_llm = load_qwen_judge_llm()
    print("✅ LLMs loaded successfully.")
except Exception as e:
    print(f"❌ Failed to load LLMs: {e}")
    llama_llm = None
    judge_llm = None

# ── SSE Event Queues (keyed by session_id) ──
_sse_queues: dict[str, Queue] = {}
_sse_lock = threading.Lock()

def _get_queue(session_id: str) -> Queue:
    with _sse_lock:
        if session_id not in _sse_queues:
            _sse_queues[session_id] = Queue()
        return _sse_queues[session_id]

def _push_event(session_id: str, event_type: str, data: dict):
    """Push an SSE event to the session's queue."""
    q = _get_queue(session_id)
    q.put({"event": event_type, "data": data})

def _cleanup_queue(session_id: str):
    with _sse_lock:
        _sse_queues.pop(session_id, None)


# ═══════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/ideas", methods=["GET"])
def api_get_ideas():
    """Return all saved ideas (without embeddings)."""
    ideas = get_all_ideas()
    # Strip binary embedding from JSON response
    for idea in ideas:
        idea.pop("embedding", None)
    return jsonify(ideas)


@app.route("/api/ideas/<int:idea_id>", methods=["DELETE"])
def api_delete_idea(idea_id):
    delete_idea(idea_id)
    return jsonify({"status": "deleted", "id": idea_id})


@app.route("/api/stream/<session_id>", methods=["GET"])
def api_stream(session_id):
    """SSE endpoint — streams real-time progress events to the frontend."""
    def generate():
        q = _get_queue(session_id)
        while True:
            try:
                msg = q.get(timeout=120)  # 2 min timeout
                event_type = msg.get("event", "status")
                data_json = json.dumps(msg.get("data", {}))
                yield f"event: {event_type}\ndata: {data_json}\n\n"
                if event_type in ("done", "error"):
                    break
            except Empty:
                # Send keepalive
                yield ":keepalive\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.route("/api/pain-points", methods=["POST"])
def api_pain_points():
    """
    Discover pain points for a market.
    Streams intermediate results via SSE.
    Body: { market, sector, session_id }
    """
    body = request.json or {}
    market = body.get("market", "").strip()
    session_id = body.get("session_id", str(uuid.uuid4()))

    if not market:
        return jsonify({"error": "Market is required"}), 400

    def run():
        try:
            # Stage 1: Gather raw pain points
            _push_event(session_id, "status", {
                "stage": "pain_points_scraping",
                "message": "🌐 Deep-scraping 9 sources for domain pain points (Play Store, Reddit, HN, Product Hunt, G2, Trustpilot, StackOverflow, Quora, blogs)..."
            })

            from pain_points import gather_pain_points
            pain_points_text = gather_pain_points(market)

            _push_event(session_id, "pain_points_raw", {
                "stage": "pain_points_raw",
                "message": "✅ Raw pain points gathered from 9 sources",
                "content": pain_points_text
            })

            # Stage 2: Extract & deduplicate top 3
            _push_event(session_id, "status", {
                "stage": "pain_points_extracting",
                "message": "🧠 Extracting candidate pain points and checking against memory..."
            })

            from dialectic import invoke_with_retry
            extraction_prompt = f"""/no_think
You are a venture analyst scanning raw complaints about {market} for STRUCTURAL
market gaps an investor would fund — not product feedback a PM would put in a backlog.

A valid pain point names all four of:
1. WHO loses money or time (a specific economic actor, not "users")
2. WHAT they cannot do
3. The STRUCTURAL reason incumbents can't easily fix it (regulation, fragmented
   supply, data silo, switching cost, geography, capital intensity — not "no one
   has built this yet")
4. The IMPACT in a unit an investor recognizes (hours/week, % revenue, churn, CAC)

GOOD EXAMPLE:
"In freight logistics, regional trucking brokers cannot price spot loads in real
time because rate data is siloed across competing load boards, costing them
8-12% margin on every booking."

BAD EXAMPLES — do not produce anything shaped like these:
- "Users are annoyed the app crashes on Android." (bug, not a market gap)
- "People wish there was a cheaper subscription." (pricing gripe, not structural)
- "Customer support is slow." (support quality, not a market gap)

Explicitly ban: UI/UX bugs, app crashes, customer support quality, subscription
pricing complaints, and one-off edge cases that only affect a single company.

From the raw complaints below, extract the 5 most distinct STRUCTURAL pain points
in {market} that pass the WHO/WHAT/WHY/IMPACT test above.

Format: "In {market}, [who] cannot [do what] because [structural reason], costing
them [quantified impact]."
Keep each line under 70 words. Output EXACTLY 5 lines, each starting with "- ".
No other text.

## Raw Complaints
{pain_points_text}
"""
            candidates = []
            try:
                response_content = invoke_with_retry(llama_llm, extraction_prompt)
                candidates = [l.strip().lstrip('-').strip() for l in response_content.split('\n') if l.strip().startswith('-')]
            except Exception:
                pass

            if len(candidates) < 3:
                candidates = [
                    f"In {market}, customers cannot access reliable services because of fragmented providers, costing them extra search time.",
                    f"In {market}, small businesses cannot scale operationally due to high overhead software costs, limiting their profit margins.",
                    f"In {market}, users cannot verify provider credentials quickly, resulting in security vulnerabilities and loss of trust."
                ]

            try:
                from embeddings import filter_and_ensure_unique_pain_points
                synthesized_needs = filter_and_ensure_unique_pain_points(candidates, market, llama_llm)
            except Exception:
                synthesized_needs = candidates[:3]

            top_pain_points = synthesized_needs[:3]

            _push_event(session_id, "pain_points_top", {
                "stage": "pain_points_done",
                "message": "✅ Top 3 structural pain points identified",
                "pain_points": top_pain_points,
                "raw_text": pain_points_text
            })

            _push_event(session_id, "done", {"message": "Pain point discovery complete"})

        except Exception as e:
            _push_event(session_id, "error", {"message": str(e)})

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return jsonify({"session_id": session_id, "status": "started"})


@app.route("/api/generate", methods=["POST"])
def api_generate():
    """
    Run the full pipeline: idea gen → judge → analysis → dialectic → save.
    Streams ALL intermediate results via SSE so the user sees everything live.
    Body: { market, sector, team_size, budget, pain_point, session_id }
    """
    body = request.json or {}
    market = body.get("market", "").strip()
    sector = body.get("sector", "")
    team_size = body.get("team_size", "")
    budget = body.get("budget", "")
    pain_point = body.get("pain_point", "")
    session_id = body.get("session_id", str(uuid.uuid4()))

    if not market or not pain_point:
        return jsonify({"error": "Market and pain_point are required"}), 400

    def run():
        try:
            from concurrent.futures import ThreadPoolExecutor
            from dialectic import invoke_with_retry, run_dialectic
            from judge import judge_idea
            from web_research import deep_web_research

            existing_ideas = get_all_ideas()
            existing_ideas_text = ""
            if existing_ideas:
                existing_ideas_text = "\n\n## IMPORTANT — These startup ideas already exist. You MUST NOT repeat them:\n"
                for i, idea in enumerate(existing_ideas[:10], 1):
                    existing_ideas_text += f"\n{i}. **{idea['idea_name']}**: {idea['idea_content'][:200]}...\n"

            rejected_list = []
            idea_approved = False
            attempt = 0
            max_attempts = 2
            research_report = None

            while not idea_approved and attempt < max_attempts:
                attempt += 1

                rejected_ideas_text = ""
                if rejected_list:
                    rejected_ideas_text = "\n\n## CRITICAL: DO NOT REPEAT THESE REJECTED IDEAS\n"
                    for idx, rej in enumerate(rejected_list, 1):
                        rejected_ideas_text += f"- **{rej['name']}**: {rej['content'][:150]}...\n"

                idea_prompt = f"""/no_think
You are an expert startup founder. You have identified the following specific user pain point in the {market} market:
"{pain_point}"

Generate ONE unique and detailed startup idea that directly solves this exact problem.

## Constraints & Context:
- Sector: {sector}
- Team Size: {team_size}
- Available Budget: {budget}

The proposed startup idea must be realistic and executable within these team size and budget constraints for the selected sector.

{existing_ideas_text}
{rejected_ideas_text}

## Originality Requirement
You must generate a concept that is completely different in name, approach, and features from the existing ideas and the rejected ideas listed above. Be creative!

## Output Format (follow exactly)
STARTUP NAME: <catchy startup name>
---
<Detailed startup idea description covering:
- Problem being solved (reference the pain point above)
- Target customers
- Core product/service
- Revenue model
- Key differentiators
- Why now (timing advantage)
- Initial go-to-market strategy
Keep it between 200-400 words.>
"""

                # On first attempt, kick off web research in parallel
                if attempt == 1 and research_report is None:
                    _push_event(session_id, "status", {
                        "stage": "idea_generation",
                        "message": f"💡 Generating startup idea + 🌐 Running web research in parallel (Attempt {attempt})..."
                    })
                    with ThreadPoolExecutor(max_workers=2) as parallel_pool:
                        future_idea = parallel_pool.submit(invoke_with_retry, llama_llm, idea_prompt)
                        future_research = parallel_pool.submit(deep_web_research.run, market)
                        idea_raw = future_idea.result().strip()
                        research_report = future_research.result()
                else:
                    if research_report is None:
                        _push_event(session_id, "status", {
                            "stage": "web_research",
                            "message": "🌐 Running live web research for market analysis..."
                        })
                        research_report = deep_web_research.run(market)

                    _push_event(session_id, "status", {
                        "stage": "idea_generation",
                        "message": f"💡 Generating startup idea (Attempt {attempt})..."
                    })
                    idea_raw = invoke_with_retry(llama_llm, idea_prompt).strip()

                # Parse startup name and description
                if "STARTUP NAME:" in idea_raw:
                    parts = idea_raw.split("---", 1)
                    name_line = parts[0].strip()
                    idea_name = name_line.replace("STARTUP NAME:", "").strip()
                    idea_content = parts[1].strip() if len(parts) > 1 else idea_raw
                else:
                    idea_name = "Unnamed Startup"
                    idea_content = idea_raw

                # Stream the idea immediately to the user
                _push_event(session_id, "idea_generated", {
                    "stage": "idea_generated",
                    "message": f"💡 Startup Idea Generated: {idea_name}",
                    "idea_name": idea_name,
                    "idea_content": idea_content,
                    "attempt": attempt
                })

                # Stream web research to the user
                _push_event(session_id, "web_research_done", {
                    "stage": "web_research_done",
                    "message": "🌐 Web research complete",
                    "research_report": research_report
                })

                # ── JUDGE: Originality check ──
                _push_event(session_id, "status", {
                    "stage": "judge_originality",
                    "message": f"🧑‍⚖️ Judge is reviewing Attempt {attempt} for originality..."
                })

                orig_verdict = judge_idea(market, idea_name, idea_content, llm=judge_llm)

                _push_event(session_id, "judge_originality_result", {
                    "stage": "judge_originality_done",
                    "message": f"🧑‍⚖️ Originality Verdict: {'✅ APPROVED' if orig_verdict['approved'] else '❌ REJECTED'}",
                    "approved": orig_verdict["approved"],
                    "reason": orig_verdict["reason"],
                    "attempt": attempt
                })

                if not orig_verdict["approved"]:
                    rejected_list.append({"name": idea_name, "content": idea_content})
                    continue

                # ── ANALYSIS ──
                _push_event(session_id, "status", {
                    "stage": "analysis",
                    "message": f"📊 Analyzing '{idea_name}' against market research..."
                })

                analysis_prompt = f"""/no_think
You are an expert business analyst. Analyze the following startup idea in the context of the provided web research report.

Startup Idea Name: {idea_name}
Startup Idea Description: {idea_content}

Web Research Report:
{research_report}

Based on this research report, provide a structured, detailed analysis covering:
1. Market: Market size, CAGR, growth drivers, and trends.
2. Competitors: Competitor landscape, strengths/weaknesses of existing players, and funding/traction.
3. Opportunity: Specific customer pain points, value proposition, revenue model, and whitespace opportunities.
4. Risks: Execution challenges, barriers to entry, and potential risks.

Ensure your analysis is grounded in the facts and data cited in the research report. Cite specific data points. Keep the analysis under 600 words.
"""
                analysis_text = invoke_with_retry(llama_llm, analysis_prompt).strip()

                _push_event(session_id, "analysis_done", {
                    "stage": "analysis_done",
                    "message": "📊 Market analysis complete",
                    "analysis": analysis_text
                })

                # ── DIALECTIC DEBATE (stream each round) ──
                _push_event(session_id, "status", {
                    "stage": "dialectic_start",
                    "message": f"🐂🐻 Starting 2-Round Dialectic Investment Debate for '{idea_name}'..."
                })

                from dialectic import bull_case, bear_case, investment_judge

                # Round 1: Bull
                _push_event(session_id, "status", {
                    "stage": "bull_r1",
                    "message": "🐂 Bull Investor presenting Round 1 arguments..."
                })
                bull_r1 = bull_case(idea_name, idea_content, market, analysis_text, 1, "", llama_llm, sector, team_size, budget)
                _push_event(session_id, "debate_round", {
                    "stage": "bull_r1_done",
                    "message": "🐂 Bull Round 1 complete",
                    "role": "bull",
                    "round": 1,
                    "content": bull_r1
                })

                # Round 1: Bear
                _push_event(session_id, "status", {
                    "stage": "bear_r1",
                    "message": "🐻 Bear Investor presenting Round 1 counter-arguments..."
                })
                history_for_bear_r1 = f"Bull (Round 1):\n{bull_r1}"
                bear_r1 = bear_case(idea_name, idea_content, market, analysis_text, 1, history_for_bear_r1, llama_llm, sector, team_size, budget)
                _push_event(session_id, "debate_round", {
                    "stage": "bear_r1_done",
                    "message": "🐻 Bear Round 1 complete",
                    "role": "bear",
                    "round": 1,
                    "content": bear_r1
                })

                # Round 2: Bull Rebuttal
                _push_event(session_id, "status", {
                    "stage": "bull_r2",
                    "message": "🐂 Bull Investor presenting Round 2 rebuttal..."
                })
                history_for_bull_r2 = (
                    f"--- Round 1: Bull Case ---\n{bull_r1}\n\n"
                    f"--- Round 1: Bear Case ---\n{bear_r1}"
                )
                bull_r2 = bull_case(idea_name, idea_content, market, analysis_text, 2, history_for_bull_r2, llama_llm, sector, team_size, budget)
                _push_event(session_id, "debate_round", {
                    "stage": "bull_r2_done",
                    "message": "🐂 Bull Round 2 rebuttal complete",
                    "role": "bull",
                    "round": 2,
                    "content": bull_r2
                })

                # Round 2: Bear Counter-Rebuttal
                _push_event(session_id, "status", {
                    "stage": "bear_r2",
                    "message": "🐻 Bear Investor presenting Round 2 counter-rebuttal..."
                })
                history_for_bear_r2 = (
                    f"--- Round 1: Bull Case ---\n{bull_r1}\n\n"
                    f"--- Round 1: Bear Case ---\n{bear_r1}\n\n"
                    f"--- Round 2: Bull Rebuttal ---\n{bull_r2}"
                )
                bear_r2 = bear_case(idea_name, idea_content, market, analysis_text, 2, history_for_bear_r2, llama_llm, sector, team_size, budget)
                _push_event(session_id, "debate_round", {
                    "stage": "bear_r2_done",
                    "message": "🐻 Bear Round 2 counter-rebuttal complete",
                    "role": "bear",
                    "round": 2,
                    "content": bear_r2
                })

                # ── INVESTMENT JUDGE ──
                _push_event(session_id, "status", {
                    "stage": "investment_judge",
                    "message": "⚖️ Investment Judge deliberating final verdict..."
                })

                full_history = (
                    f"--- Round 1: Bull Case ---\n{bull_r1}\n\n"
                    f"--- Round 1: Bear Case ---\n{bear_r1}\n\n"
                    f"--- Round 2: Bull Rebuttal ---\n{bull_r2}\n\n"
                    f"--- Round 2: Bear Counter-Rebuttal ---\n{bear_r2}"
                )
                dialectic_result = investment_judge(
                    idea_name, idea_content, market, analysis_text,
                    full_history, judge_llm, sector, team_size, budget
                )

                _push_event(session_id, "verdict", {
                    "stage": "verdict",
                    "message": f"⚖️ Verdict: {'✅ INVESTABLE' if dialectic_result['investable'] else '❌ NOT INVESTABLE'}",
                    "investable": dialectic_result["investable"],
                    "verdict": dialectic_result.get("verdict", ""),
                    "score": dialectic_result.get("score"),
                    "explanation": dialectic_result.get("explanation", ""),
                    "bull_summary": dialectic_result.get("bull_summary", ""),
                    "bear_summary": dialectic_result.get("bear_summary", "")
                })

                if dialectic_result["investable"]:
                    idea_approved = True

                    # Save to DB
                    save_idea(
                        topic=market,
                        idea_name=idea_name,
                        idea_description=idea_content,
                        analysis=analysis_text,
                        verdict=dialectic_result.get("verdict", ""),
                        score=dialectic_result.get("score"),
                        explanation=dialectic_result.get("explanation", ""),
                        bull_summary=dialectic_result.get("bull_summary", ""),
                        bear_summary=dialectic_result.get("bear_summary", ""),
                        pain_point=pain_point,
                        sector=sector,
                        team_size=team_size,
                        budget=budget,
                    )

                    _push_event(session_id, "saved", {
                        "stage": "saved",
                        "message": "💾 Startup idea saved to database!",
                        "idea_name": idea_name,
                        "idea_content": idea_content,
                        "analysis": analysis_text,
                        "dialectic_result": {
                            "investable": dialectic_result["investable"],
                            "verdict": dialectic_result.get("verdict", ""),
                            "score": dialectic_result.get("score"),
                            "explanation": dialectic_result.get("explanation", ""),
                            "bull_summary": dialectic_result.get("bull_summary", ""),
                            "bear_summary": dialectic_result.get("bear_summary", ""),
                        }
                    })
                else:
                    rejected_list.append({"name": idea_name, "content": idea_content})

            if not idea_approved:
                _push_event(session_id, "error", {
                    "message": "❌ Failed to generate an original and investable idea after 2 attempts. Please try again with different criteria."
                })
            else:
                _push_event(session_id, "done", {"message": "✅ Pipeline complete!"})

        except Exception as e:
            import traceback
            traceback.print_exc()
            _push_event(session_id, "error", {"message": f"Pipeline error: {str(e)}"})

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return jsonify({"session_id": session_id, "status": "started"})


# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════

if __name__ == "__main__":
    print("\n🚀 AI Startup Agent running at http://localhost:5000\n")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
