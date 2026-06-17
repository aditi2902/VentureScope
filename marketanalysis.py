import logging
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

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)





@st.cache_resource
def load_idea_llm():
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


if "history" not in st.session_state:
    st.session_state.history = []
if "debug_logs" not in st.session_state:
    st.session_state.debug_logs = []
if "chat_state" not in st.session_state:
    st.session_state.chat_state = "WAITING_FOR_TOPIC"
if "current_topic" not in st.session_state:
    st.session_state.current_topic = ""
if "current_options" not in st.session_state:
    st.session_state.current_options = []


def log_debug(message: str) -> None:
    logger.debug(message)
    st.session_state.debug_logs.append(message)


st.set_page_config(page_title="Startup Idea Chatbot", page_icon="🚀")

# =====================================
# SIDEBAR — Approved Startup Ideas
# =====================================
st.sidebar.title("💡 Approved Startup Ideas")
saved_ideas = get_all_ideas()

if not saved_ideas:
    st.sidebar.info("No approved ideas yet.")
else:
    for idea in saved_ideas:
        with st.sidebar.expander(f"🚀 {idea['idea_name']}"):
            st.caption(f"Topic: {idea['topic']}  •  {idea['timestamp']}")
            st.markdown(idea["idea_content"])
            if st.button("🗑️ Delete", key=f"del_{idea['id']}"):
                delete_idea(idea["id"])
                st.rerun()

st.title("🚀 Startup Idea Chatbot")
st.write(
    "Enter a market topic. I will find the  3 user pain points and ask you to pick one. "
    "Then I will generate a targeted startup idea based on your choice!"
)


idea_llm = load_idea_llm()
gemini_llm = load_gemini_llm()

with st.form(key="chat_form", clear_on_submit=True):
    if st.session_state.chat_state == "WAITING_FOR_TOPIC":
        user_input = st.text_input("Your market topic", "Fitness Apps")
    else:
        user_input = st.text_input("Select an option (1, 2, or 3)", "1")
    submit_button = st.form_submit_button("Send")

if submit_button and user_input.strip():
    user_text = user_input.strip()
    st.session_state.history.append({"role": "user", "content": user_text})
    log_debug(f"User submitted: {user_text} (State: {st.session_state.chat_state})")

    try:
        if st.session_state.chat_state == "WAITING_FOR_TOPIC":
            st.session_state.current_topic = user_text
            log_debug(f"Scraping pain points for {user_text}...")
            
            with st.spinner("🌐 Deep-scraping 8 sources for domain pain points..."):
                pain_points_text = gather_pain_points(user_text)

            with st.spinner("🧠 Extracting candidate pain points and checking against memory..."):
                extraction_prompt = f"""/no_think
You are a venture analyst scanning raw complaints about {user_text} for STRUCTURAL
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
in {user_text} that pass the WHO/WHAT/WHY/IMPACT test above.

Format: "In {user_text}, [who] cannot [do what] because [structural reason], costing
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
                        f"In {user_text}, customers cannot access reliable services because of fragmented providers, costing them extra search time.",
                        f"In {user_text}, small businesses cannot scale operationally due to high overhead software costs, limiting their profit margins.",
                        f"In {user_text}, users cannot verify provider credentials quickly, resulting in security vulnerabilities and loss of trust."
                    ]

                try:
                    from embeddings import filter_and_ensure_unique_pain_points
                    synthesized_needs = filter_and_ensure_unique_pain_points(candidates, user_text, gemini_llm)
                except Exception as e:
                    synthesized_needs = candidates[:3]

                st.session_state.current_options = synthesized_needs[:3]



            reply = "Here are the Top 3 user complaints I found for that market. **Reply with 1, 2, or 3** to build an idea around it:\n\n"
            for i, opt in enumerate(st.session_state.current_options, 1):
                reply += f"{i}. {opt}\n"
            
            st.session_state.history.append({"role": "assistant", "content": reply})
            st.session_state.chat_state = "WAITING_FOR_SELECTION"
            st.rerun()

        elif st.session_state.chat_state == "WAITING_FOR_SELECTION":
            # Parse user selection (1, 2, or 3)
            selection_idx = -1
            if user_text.isdigit() and 1 <= int(user_text) <= len(st.session_state.current_options):
                selection_idx = int(user_text) - 1
            else:
                # If they didn't just type a number, try to find it in their text
                for i in range(1, len(st.session_state.current_options) + 1):
                    if str(i) in user_text:
                        selection_idx = i - 1
                        break
            
            if selection_idx == -1:
                reply = "I didn't catch that. Please reply with 1, 2, or 3."
                st.session_state.history.append({"role": "assistant", "content": reply})
                st.rerun()

            selected_pain_point = st.session_state.current_options[selection_idx]
            market = st.session_state.current_topic
            
            reply_ack = f"Great choice: *\"{selected_pain_point}\"*. Generating an idea now..."
            st.session_state.history.append({"role": "assistant", "content": reply_ack})

            # STEP 2: Generate Startup Idea
            existing_ideas = get_all_ideas()
            existing_ideas_text = ""
            if existing_ideas:
                existing_ideas_text = "\n\n## IMPORTANT — These ideas already exist. Do NOT repeat them:\n"
                for i, idea in enumerate(existing_ideas[:10], 1):
                    existing_ideas_text += f"\n{i}. **{idea['idea_name']}**: {idea['idea_content'][:200]}...\n"

            # Generate and judge loop
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
You are an expert startup founder. You have identified the following specific user pain point in the {market} market:
"{selected_pain_point}"

Generate ONE unique startup idea that solves this exact problem.

{existing_ideas_text}
{rejected_ideas_text}

## Originality Requirement
You must generate a concept that is completely different in name, approach, and features from the existing ideas and the rejected ideas listed above. Be creative!

## Output Format
STARTUP NAME: <catchy name>
---
<Detailed description (200-400 words) covering: problem, target customers,
product/service, revenue model, differentiators, timing advantage, go-to-market>
"""
                log_debug(f"Generating startup idea (Attempt {attempt})...")
                with st.spinner(f"💡 Generating startup idea (Attempt {attempt})..."):
                    temp_llm = ChatOllama(
                        model="qwen2.5:3b",
                        temperature=min(0.7 + (attempt - 1) * 0.1, 1.2)
                    )
                    idea_response = temp_llm.invoke(idea_prompt)
                    idea_raw = idea_response.content.strip()

                temp_name = "Unnamed Startup"
                temp_content = idea_raw
                if "STARTUP NAME:" in idea_raw:
                    parts = idea_raw.split("---", 1)
                    temp_name = parts[0].replace("STARTUP NAME:", "").strip()
                    if len(parts) > 1:
                        temp_content = parts[1].strip()

                log_debug(f"Running judge on Attempt {attempt}...")
                with st.spinner(f"🧑‍⚖️ Judge is reviewing Attempt {attempt} for originality..."):
                    verdict = judge_idea(market, temp_name, temp_content)

                if verdict["approved"]:
                    approved = True
                    idea_name = temp_name
                    idea_content = temp_content
                else:
                    rejected_list.append({"name": temp_name, "content": temp_content})
                    log_debug(f"Attempt {attempt} rejected: {verdict['reason']}")

            log_debug(f"Judge APPROVED after {attempt} attempts: {verdict['reason']}")
            
            # STEP 4: Market Analysis
            log_debug("Running market and opportunity analysis...")
            with st.spinner("📊 Running live web research & analysis..."):
                # Run the single deep web research query directly
                research_report = deep_web_research.run(market)
                
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
            
            full_idea_content = f"{idea_content}\n\n### Comprehensive Analysis\n{analysis_text}"
            save_idea(market, idea_name, full_idea_content)
            
            reply = (
                f"## 🚀 {idea_name}\n\n{idea_content}\n\n"
                f"✅ **Approved & Saved** — {verdict['reason']}\n\n"
                f"--- \n\n## 📊 Comprehensive Analysis\n{analysis_text}"
            )

            st.session_state.history.append({"role": "assistant", "content": reply})
            
            # Reset state for next topic
            st.session_state.chat_state = "WAITING_FOR_TOPIC"
            st.session_state.current_topic = ""
            st.session_state.current_options = []
            
            st.rerun()

    except Exception as e:
        error_message = f"Error: {e}"
        log_debug(error_message)
        st.error("An error occurred. See debug logs.")

for message in st.session_state.history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

with st.sidebar.expander("Debug logs", expanded=False):
    if st.session_state.debug_logs:
        for index, log_line in enumerate(st.session_state.debug_logs, start=1):
            st.text(f"{index}. {log_line}")
    else:
        st.write("No debug logs yet.")

st.markdown("---")
st.caption("Powered by LangChain, Ollama & LLM-as-a-Judge via Streamlit.")
