import streamlit as st
from langchain_ollama import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI
from web_research import deep_web_research
from database import init_db, save_idea, get_all_ideas, delete_idea
from judge import judge_idea
from pain_points import gather_pain_points
from dotenv import load_dotenv

load_dotenv()

# =====================================
# DATABASE INIT
# =====================================
init_db()

# =====================================
# PAGE CONFIG
# =====================================

st.set_page_config(
    page_title="AI Startup Idea Generator",
    page_icon="🚀",
    layout="wide"
)

# =====================================
# SESSION STATE INIT
# =====================================
if "step" not in st.session_state:
    st.session_state.step = 0
if "market" not in st.session_state:
    st.session_state.market = ""
if "top_pain_points" not in st.session_state:
    st.session_state.top_pain_points = []
if "raw_pain_points" not in st.session_state:
    st.session_state.raw_pain_points = ""

def reset_state():
    st.session_state.step = 0
    st.session_state.top_pain_points = []
    st.session_state.raw_pain_points = ""

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

# =====================================
# HEADER
# =====================================

st.title("🚀 AI Startup Idea Generator")
st.write(
    "Enter a market or domain. The agent will find user pain points and present the top 3. "
    "Select one, and it will generate a targeted idea, judge it, and run a full market/opportunity analysis."
)

# =====================================
# LOAD AGENTS
# =====================================

@st.cache_resource
def load_llm():
    return ChatOllama(
        model="qwen2.5:3b",
        temperature=0.7,
    )

import gemini_tracker

@st.cache_resource
def load_gemini_llm():
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.7,
    )
    original_invoke = llm.invoke
    def tracked_invoke(*args, **kwargs):
        gemini_tracker.track_call()
        return original_invoke(*args, **kwargs)
    object.__setattr__(llm, "invoke", tracked_invoke)
    return llm

try:
    idea_llm = load_llm()
    gemini_llm = load_gemini_llm()
except Exception as e:
    st.error(f"❌ Failed to load models:\n\n{e}")
    st.stop()

# =====================================
# STEP 1: USER INPUT & PAIN POINT GATHERING
# =====================================

market_input = st.text_input(
    "Market / Domain",
    value=st.session_state.market,
    placeholder="e.g. Fitness Apps, AI Education, HealthTech"
)

if market_input != st.session_state.market:
    st.session_state.market = market_input
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
                response = gemini_llm.invoke(extraction_prompt)
                candidates = [l.strip().lstrip('-').strip() for l in response.content.strip().split('\n') if l.strip().startswith('-')]
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
                synthesized_needs = filter_and_ensure_unique_pain_points(candidates, st.session_state.market, gemini_llm)
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
# STEP 3: PIPELINE EXECUTION
# =====================================

if st.session_state.step == 2:
    selected_pain_point = st.session_state.selected_pain_point
    
    existing_ideas = get_all_ideas()
    existing_ideas_text = ""
    if existing_ideas:
        existing_ideas_text = "\n\n## IMPORTANT — These startup ideas already exist. You MUST NOT repeat them:\n"
        for i, idea in enumerate(existing_ideas[:10], 1):
            existing_ideas_text += f"\n{i}. **{idea['idea_name']}**: {idea['idea_content'][:200]}...\n"

    attempt = 0
    approved = False
    rejected_list = []
    
    idea_name = "Unnamed Startup"
    idea_content = ""
    verdict = {"approved": False, "reason": "No attempts made yet."}

    while not approved:
        attempt += 1
        
        rejected_ideas_text = ""
        if rejected_list:
            rejected_ideas_text = "\n\n## CRITICAL: DO NOT REPEAT THESE REJECTED IDEAS\nThe following startup ideas were just rejected for being too similar to existing work. You MUST NOT propose anything similar to these concepts:\n"
            for idx, rej in enumerate(rejected_list, 1):
                rejected_ideas_text += f"- **{rej['name']}**: {rej['content'][:150]}...\n"

        idea_prompt = f"""/no_think
You are an expert startup founder. You have identified the following specific user pain point in the {st.session_state.market} market:
"{selected_pain_point}"

Generate ONE unique and detailed startup idea that directly solves this exact problem.

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

        with st.spinner(f"💡 Generating startup idea (Attempt {attempt})..."):
            temp_llm = ChatOllama(
                model="qwen2.5:3b",
                temperature=min(0.7 + (attempt - 1) * 0.1, 1.2)
            )
            idea_response = temp_llm.invoke(idea_prompt)
            idea_raw = idea_response.content.strip()

        # Parse startup name and description
        temp_name = "Unnamed Startup"
        temp_content = idea_raw

        if "STARTUP NAME:" in idea_raw:
            parts = idea_raw.split("---", 1)
            name_line = parts[0].strip()
            temp_name = name_line.replace("STARTUP NAME:", "").strip()
            if len(parts) > 1:
                temp_content = parts[1].strip()

        with st.spinner(f"🧑‍⚖️ Judge is reviewing Attempt {attempt} for originality..."):
            verdict = judge_idea(st.session_state.market, temp_name, temp_content)

        if verdict["approved"]:
            approved = True
            idea_name = temp_name
            idea_content = temp_content
        else:
            rejected_list.append({"name": temp_name, "content": temp_content})
            st.warning(f"⚠️ Attempt {attempt} rejected: {verdict['reason']}")

    with st.spinner("📊 Running live web research & analysis..."):
        # Run the single deep web research query directly
        research_report = deep_web_research.run(st.session_state.market)
        
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
        analysis_response = idea_llm.invoke(analysis_prompt)
        analysis_text = analysis_response.content

    # Save and display
    st.markdown("---")
    save_idea(st.session_state.market, idea_name, f"{idea_content}\n\n### Comprehensive Analysis\n{analysis_text}")

    st.markdown(f"## 🚀 {idea_name}")
    st.markdown(idea_content)
    st.success(f"✅ **Judge APPROVED** — {verdict['reason']}")
    
    st.markdown("---")
    st.markdown("## 📊 Comprehensive Analysis")
    st.markdown(analysis_text)
    
    st.success("💾 Startup idea and analysis saved to database!")
    
    if st.button("🔄 Create Another Idea"):
        reset_state()
        st.rerun()