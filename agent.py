import os
import streamlit as st
from langchain_openai import ChatOpenAI
from web_research import deep_web_research
from database import init_db, save_idea, get_all_ideas, delete_idea
from judge import judge_idea
from pain_points import gather_pain_points
from dialectic import run_dialectic, invoke_with_retry
from vc_research import find_vcs
from dotenv import load_dotenv

load_dotenv(override=True)

# =====================================
# DATABASE INIT
# =====================================
_db_error = None
try:
    init_db()
except Exception as _e:
    _db_error = _e  # Store error, show it in UI after page config

# =====================================
# PAGE CONFIG
# =====================================

st.set_page_config(
    page_title="AI Startup Idea Generator",
    page_icon="🚀",
    layout="wide"
)

# Show DB connection error as a banner (doesn't crash the app)
if _db_error:
    st.warning(
        f"⚠️ **Neon DB unreachable** — using local SQLite instead. Your ideas are saved locally.\n\n"
        f"**Details:** `{_db_error}`"
    )

# =====================================
# SESSION STATE INIT
# =====================================
if "step" not in st.session_state:
    st.session_state.step = 0
if "market" not in st.session_state:
    st.session_state.market = ""
if "sector" not in st.session_state:
    st.session_state.sector = "B2B SaaS"
if "team_size" not in st.session_state:
    st.session_state.team_size = "1-2 (Solo/Co-founders)"
if "budget" not in st.session_state:
    st.session_state.budget = "$10k-$50k (Pre-seed)"
if "top_pain_points" not in st.session_state:
    st.session_state.top_pain_points = []
if "raw_pain_points" not in st.session_state:
    st.session_state.raw_pain_points = ""

def reset_state():
    st.session_state.step = 0
    st.session_state.top_pain_points = []
    st.session_state.raw_pain_points = ""
    if "idea_name" in st.session_state:
        del st.session_state.idea_name
    if "idea_content" in st.session_state:
        del st.session_state.idea_content
    if "analysis_text" in st.session_state:
        del st.session_state.analysis_text
    if "dialectic_result" in st.session_state:
        del st.session_state.dialectic_result

# =====================================
# SIDEBAR — Approved Startup Ideas
# =====================================

st.sidebar.title("💡 Approved Startup Ideas")
saved_ideas = get_all_ideas()

if not saved_ideas:
    st.sidebar.info("No approved ideas yet. Generate your first one!")
else:
    for idea in saved_ideas:
        with st.sidebar.expander(f"🚀 {idea['idea_name']}"):
            st.caption(f"Topic: {idea['topic']}  •  {idea['timestamp']}")
            st.markdown(idea["idea_content"])
            if st.button("🗑️ Delete", key=f"del_{idea['id']}"):
                delete_idea(idea["id"])
                st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ LLM Configuration")
model_provider = st.sidebar.selectbox(
    "Preferred LLM Provider",
    options=["Nvidia DeepSeek (Cloud)", "Ollama Qwen2.5:3b (Local)"],
    index=0,
    help="Nvidia DeepSeek uses a cloud API. Ollama runs locally on port 11434."
)

use_ollama = (model_provider == "Ollama Qwen2.5:3b (Local)")

# =====================================
# HEADER
# =====================================

st.title("🚀 AI Startup Idea Generator")
st.write(
    "Enter a market or domain. The agent will find user pain points and present the top 3. "
    "Select one, and it will generate a targeted idea, judge it, and run a full market/opportunity analysis."
)

# =====================================
# LOAD AGENTS — Llama 3.1 70B Only
# =====================================

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

# ── Llama 3.1 70B: Used for Generative tasks ──
@st.cache_resource
def load_llama_llm():
    return _make_nvidia_llm("meta/llama-3.1-70b-instruct", temperature=0.7)

@st.cache_resource
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

@st.cache_resource
def load_ollama_llm(model_name: str = "qwen2.5:3b", temperature: float = 0.7):
    try:
        from langchain_ollama import ChatOllama
        llm = ChatOllama(model=model_name, temperature=temperature)
        original_invoke = llm.invoke
        def tracked_invoke(*args, **kwargs):
            print(f"🤖 [LLM CALL] -> Model: {model_name} (Ollama Local)")
            return original_invoke(*args, **kwargs)
        object.__setattr__(llm, "invoke", tracked_invoke)
        return llm
    except Exception as e:
        st.warning(f"⚠️ Failed to initialize Ollama: {e}")
        return None

try:
    llama_llm = load_llama_llm()
    judge_llm = load_qwen_judge_llm()
except Exception as e:
    st.error(f"❌ Failed to load Nvidia/Cloud models (Check your .env settings):\n\n{e}")
    st.stop()


# =====================================
# STEP 1: USER INPUT & PAIN POINT GATHERING
# =====================================

col_market, col_sector = st.columns(2)
with col_market:
    market_input = st.text_input(
        "Market / Domain",
        value=st.session_state.market,
        placeholder="e.g. Fitness Apps, AI Education, HealthTech"
    )

sectors = ["B2B SaaS", "B2C Mobile App", "FinTech", "HealthTech", "DeepTech", "Hardware", "E-commerce", "Marketplace"]
default_sector_idx = sectors.index(st.session_state.sector) if st.session_state.sector in sectors else 0
with col_sector:
    sector_input = st.selectbox(
        "Sector",
        options=sectors,
        index=default_sector_idx
    )

col_team, col_budget = st.columns(2)
team_sizes = ["1-2 (Solo/Co-founders)", "3-5 (Small Team)", "6-10 (Growing Startup)", "10+ (Established)"]
default_team_idx = team_sizes.index(st.session_state.team_size) if st.session_state.team_size in team_sizes else 0
with col_team:
    team_size_input = st.selectbox(
        "Team Size",
        options=team_sizes,
        index=default_team_idx
    )

budgets = ["<$10k (Lean/Bootstrapped)", "$10k-$50k (Pre-seed)", "$50k-$200k (Seed)", "$200k+ (Ventured)"]
default_budget_idx = budgets.index(st.session_state.budget) if st.session_state.budget in budgets else 1
with col_budget:
    budget_input = st.selectbox(
        "Available Budget",
        options=budgets,
        index=default_budget_idx
    )

if (market_input != st.session_state.market or 
    sector_input != st.session_state.sector or 
    team_size_input != st.session_state.team_size or 
    budget_input != st.session_state.budget):
    st.session_state.market = market_input
    st.session_state.sector = sector_input
    st.session_state.team_size = team_size_input
    st.session_state.budget = budget_input
    reset_state()

if st.session_state.step == 0:
    if st.button("🔍 Find Pain Points"):
        if not st.session_state.market.strip():
            st.warning("Please enter a market or domain.")
            st.stop()

        with st.spinner("🌐 Deep-scraping 8 sources for domain pain points (Play Store, Reddit, HN, Product Hunt, G2, Trustpilot, StackOverflow, blogs)..."):
            pain_points_text = gather_pain_points(st.session_state.market)
            st.session_state.raw_pain_points = pain_points_text
            
        with st.spinner("🧠 Extracting candidate pain points and checking against memory..."):
            extraction_prompt = f"""/no_think
You are a venture analyst scanning raw complaints about {st.session_state.market} for STRUCTURAL
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
in {st.session_state.market} that pass the WHO/WHAT/WHY/IMPACT test above.

Format: "In {st.session_state.market}, [who] cannot [do what] because [structural reason], costing
them [quantified impact]."
Keep each line under 70 words. Output EXACTLY 5 lines, each starting with "- ".
No other text.

## Raw Complaints
{pain_points_text}
"""
            candidates = []
            try:
                from dialectic import invoke_with_retry
                response_content = invoke_with_retry(llama_llm, extraction_prompt)
                candidates = [l.strip().lstrip('-').strip() for l in response_content.split('\n') if l.strip().startswith('-')]
            except Exception as e:
                pass

            if len(candidates) < 3:
                candidates = [
                    f"In {st.session_state.market}, customers cannot access reliable services because of fragmented providers, costing them extra search time.",
                    f"In {st.session_state.market}, small businesses cannot scale operationally due to high overhead software costs, limiting their profit margins.",
                    f"In {st.session_state.market}, users cannot verify provider credentials quickly, resulting in security vulnerabilities and loss of trust."
                ]

            try:
                from embeddings import filter_and_ensure_unique_pain_points
                synthesized_needs = filter_and_ensure_unique_pain_points(candidates, st.session_state.market, llama_llm)
            except Exception as e:
                synthesized_needs = candidates[:3]

            st.session_state.top_pain_points = synthesized_needs[:3]
            st.session_state.step = 1
            st.rerun()



# =====================================
# STEP 2: USER SELECTION & IDEA GENERATION
# =====================================

if st.session_state.step == 1:
    with st.expander("📋 View Raw Discovered Pain Points", expanded=False):
        st.markdown(st.session_state.raw_pain_points)
        
    st.subheader("Top 3 User Complaints Discovered:")
    selected_pain_point = st.radio(
        "Select the problem you want your startup to solve:",
        st.session_state.top_pain_points
    )
    
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("🧠 Generate Idea"):
            st.session_state.selected_pain_point = selected_pain_point
            st.session_state.step = 2
            st.rerun()
    with col2:
        if st.button("🔄 Start Over"):
            reset_state()
            st.rerun()

# =====================================
# STEP 3: PIPELINE EXECUTION (Single run, guaranteed approval)
# =====================================

if st.session_state.step == 2:
    selected_pain_point = st.session_state.selected_pain_point
    
    existing_ideas = get_all_ideas()
    existing_ideas_text = ""
    if existing_ideas:
        existing_ideas_text = "\n\n## IMPORTANT — These startup ideas already exist. You MUST NOT repeat them:\n"
        for i, idea in enumerate(existing_ideas[:10], 1):
            existing_ideas_text += f"\n{i}. **{idea['idea_name']}**: {idea['idea_content'][:200]}...\n"

    if "idea_name" not in st.session_state:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        idea_name = "Unnamed Startup"
        idea_content = ""
        analysis_text = ""
        dialectic_result = {}
        research_report = None
        rejected_list = []

        idea_approved = False
        attempt = 0
        max_attempts = 2

        while not idea_approved and attempt < max_attempts:
            attempt += 1

            rejected_ideas_text = ""
            if rejected_list:
                rejected_ideas_text = "\n\n## CRITICAL: DO NOT REPEAT THESE REJECTED IDEAS\nThe following startup ideas were just rejected. You MUST NOT propose anything similar to these concepts:\n"
                for idx, rej in enumerate(rejected_list, 1):
                    rejected_ideas_text += f"- **{rej['name']}**: {rej['content'][:150]}...\n"

            idea_prompt = f"""/no_think
You are an expert startup founder. You have identified the following specific user pain point in the {st.session_state.market} market:
"{selected_pain_point}"

Generate ONE unique and detailed startup idea that directly solves this exact problem.

## Constraints & Context:
- Sector: {st.session_state.sector}
- Team Size: {st.session_state.team_size}
- Available Budget: {st.session_state.budget}

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
                with st.spinner(f"💡 Generating startup idea + 🌐 Running web research in parallel..."):
                    with ThreadPoolExecutor(max_workers=2) as parallel_pool:
                        future_idea = parallel_pool.submit(invoke_with_retry, llama_llm, idea_prompt)
                        future_research = parallel_pool.submit(deep_web_research.run, st.session_state.market)
                        idea_raw = future_idea.result().strip()
                        research_report = future_research.result()
            else:
                if research_report is None:
                    with st.spinner("🌐 Running live web research for market analysis..."):
                        research_report = deep_web_research.run(st.session_state.market)
                with st.spinner(f"💡 Generating startup idea (Attempt {attempt})..."):
                    idea_response = invoke_with_retry(llama_llm, idea_prompt)
                    idea_raw = idea_response.strip()

            # Parse startup name and description
            if "STARTUP NAME:" in idea_raw:
                parts = idea_raw.split("---", 1)
                name_line = parts[0].strip()
                temp_name = name_line.replace("STARTUP NAME:", "").strip()
                if len(parts) > 1:
                    temp_content = parts[1].strip()
                else:
                    temp_content = idea_raw
            else:
                temp_name = "Unnamed Startup"
                temp_content = idea_raw

            with st.spinner(f"🧑‍⚖️ Judge is reviewing Attempt {attempt} for originality..."):
                orig_verdict = judge_idea(st.session_state.market, temp_name, temp_content, llm=judge_llm)

            if not orig_verdict["approved"]:
                rejected_list.append({"name": temp_name, "content": temp_content})
                st.warning(f"⚠️ Attempt {attempt} rejected (Originality): {orig_verdict['reason']}")
                continue

            idea_name = temp_name
            idea_content = temp_content

            # --- STAGE 2: Run analysis (idea-specific, uses cached web research) ---
            with st.spinner(f"📊 Analyzing '{idea_name}' against market research..."):
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
                analysis_response = invoke_with_retry(llama_llm, analysis_prompt)
                analysis_text = analysis_response.strip()

            # --- STAGE 3: Run 2-round dialectic debate ---
            with st.status(f"🐂🐻⚖️ Running 2-Round Dialectic Investment Debate for '{idea_name}' (Attempt {attempt})...", expanded=True) as status:
                dialectic_result = run_dialectic(
                    idea_name=idea_name,
                    idea_content=idea_content,
                    market=st.session_state.market,
                    analysis_text=analysis_text,
                    debate_llm=llama_llm,
                    judge_llm=judge_llm,
                    sector=st.session_state.sector,
                    team_size=st.session_state.team_size,
                    budget=st.session_state.budget,
                )
                
                st.write("Debate completed. Analyzing verdict...")

                if dialectic_result["investable"]:
                    status.update(label=f"✅ Approved by Investment Judge", state="complete")
                    idea_approved = True
                else:
                    status.update(label=f"❌ Rejected by Investment Judge", state="complete")
                    rejected_list.append({"name": idea_name, "content": idea_content})
                    st.warning(f"⚠️ Attempt {attempt} rejected (Not Investable): {dialectic_result['explanation']}")

        if not idea_approved:
            st.error("❌ Failed to generate an original and investable idea after 2 attempts. Please start over or adjust your criteria.")
            st.stop()

        # Save to session state to prevent regeneration
        st.session_state.idea_name = idea_name
        st.session_state.idea_content = idea_content
        st.session_state.analysis_text = analysis_text
        st.session_state.dialectic_result = dialectic_result

        # Always save to DB
        save_idea(
            topic=st.session_state.market,
            idea_name=idea_name,
            idea_description=idea_content,
            analysis=analysis_text,
            verdict=dialectic_result.get("verdict", ""),
            score=dialectic_result.get("score"),
            explanation=dialectic_result.get("explanation", ""),
            bull_summary=dialectic_result.get("bull_summary", ""),
            bear_summary=dialectic_result.get("bear_summary", ""),
            pain_point=st.session_state.selected_pain_point,
            sector=st.session_state.sector,
            team_size=st.session_state.team_size,
            budget=st.session_state.budget,
        )

    # Retrieve from session state
    idea_name = st.session_state.idea_name
    idea_content = st.session_state.idea_content
    analysis_text = st.session_state.analysis_text
    dialectic_result = st.session_state.dialectic_result

    st.success(f"✅ **Dialectic Judge APPROVED** — Idea is investable")

    with st.spinner("💰 Searching for relevant VCs..."):
        vc_report = find_vcs(
            market=st.session_state.market,
            idea_name=idea_name,
            idea_content=idea_content,
            pain_point=st.session_state.selected_pain_point,
        )

    with st.spinner("💰 Searching for relevant VCs..."):
        vc_report = find_vcs(
            market=st.session_state.market,
            idea_name=idea_name,
            idea_content=idea_content,
            pain_point=st.session_state.selected_pain_point,
        )

    # Save and display
    st.markdown("---")

    st.markdown(f"## 🚀 {idea_name}")
    st.markdown(idea_content)
    
    st.markdown("---")
    st.markdown("## 📊 Comprehensive Analysis")
    st.markdown(analysis_text)

    st.markdown("---")
    st.markdown("## 💰 VC Investment Landscape")
    st.markdown(vc_report)
    
    st.markdown("---")
    st.markdown("## ⚖️ Dialectic Investment Debate Summary")
    st.info(f"**Explanation:** {dialectic_result.get('explanation', 'No explanation provided.')}")
    
    col_bull, col_bear = st.columns(2)
    with col_bull:
        st.markdown("### 🐂 Bull Case Summary")
        st.markdown(dialectic_result.get('bull_summary', 'No summary available.'))
    with col_bear:
        st.markdown("### 🐻 Bear Case Summary")
        st.markdown(dialectic_result.get('bear_summary', 'No summary available.'))

    combined_content = f"{idea_content}\n\n### Comprehensive Analysis\n{analysis_text}\n\n### VC Investment Landscape\n{vc_report}"
    save_idea(st.session_state.market, idea_name, combined_content)
    st.success("💾 Startup idea, analysis, dialectic debate, and VC research saved to database!")
    
    if st.button("🔄 Create Another Idea"):
        reset_state()
        st.rerun()
