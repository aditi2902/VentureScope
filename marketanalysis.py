import logging
import streamlit as st
from langchain.agents import create_agent
from langchain_ollama import ChatOllama
from opportunity_analysis import analyze_market, analyze_opportunity, analyze_competitors
from database import init_db, save_idea, get_all_ideas, delete_idea
from judge import judge_idea
from pain_points import gather_pain_points

# =====================================
# DATABASE INIT
# =====================================
init_db()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@st.cache_resource
def create_market_agent():
    return create_agent(
        model="ollama:llama3.2:1b",
        tools=[analyze_market, analyze_opportunity, analyze_competitors],
        system_prompt=(
            "You are a market, opportunity, and competitor analysis chatbot. Respond like a business analyst. "
            "Use all three tools — analyze_market, analyze_opportunity, and analyze_competitors — to research "
            "the startup idea. Cover market structure, CAGR, growth drivers, risks, market need, value proposition, "
            "competitor landscape, strengths/weaknesses, and whitespace opportunities."
        ),
    )


@st.cache_resource
def load_idea_llm():
    return ChatOllama(
        model="qwen3:8b",
        temperature=0.7,
    )


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
    "Enter a market topic. I will find the top 3 user pain points and ask you to pick one. "
    "Then I will generate a targeted startup idea based on your choice!"
)

agent = create_market_agent()
idea_llm = load_idea_llm()

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
            
            with st.spinner("🔍 Scraping Play Store & Reddit for user pain points..."):
                pain_points_text = gather_pain_points(user_text)

                extraction_prompt = f"""/no_think
Analyze the following user pain points and complaints. Identify the top 3 most distinct, 
significant, and actionable pain points that could form the basis of a startup.

## Raw Pain Points
{pain_points_text}

## Output Format
Return exactly 3 lines, each starting with "- ". Keep each line under 30 words describing the specific problem. Do not add any other text.
"""
                extraction_response = idea_llm.invoke(extraction_prompt)
                lines = [line.strip().lstrip('-').strip() for line in extraction_response.content.strip().split('\n') if line.strip().startswith('-')]
                
                if len(lines) >= 3:
                    st.session_state.current_options = lines[:3]
                else:
                    st.session_state.current_options = [
                        "General UX/UI issues and bugs",
                        "Lack of specific features requested by users",
                        "Customer service and subscription problems"
                    ]

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

            idea_prompt = f"""/no_think
You are an expert startup founder. You have identified the following specific user pain point in the {market} market:
"{selected_pain_point}"

Generate ONE unique startup idea that solves this exact problem.

{existing_ideas_text}

## Output Format
STARTUP NAME: <catchy name>
---
<Detailed description (200-400 words) covering: problem, target customers,
product/service, revenue model, differentiators, timing advantage, go-to-market>
"""
            log_debug("Generating startup idea...")
            with st.spinner("💡 Generating startup idea from selected pain point..."):
                idea_response = idea_llm.invoke(idea_prompt)
                idea_raw = idea_response.content.strip()

            idea_name = "Unnamed Startup"
            idea_content = idea_raw
            if "STARTUP NAME:" in idea_raw:
                parts = idea_raw.split("---", 1)
                idea_name = parts[0].replace("STARTUP NAME:", "").strip()
                if len(parts) > 1:
                    idea_content = parts[1].strip()

            # STEP 3: LLM Judge
            log_debug("Running judge...")
            with st.spinner("🧑‍⚖️ Judge is reviewing for originality..."):
                verdict = judge_idea(market, idea_name, idea_content)

            if verdict["approved"]:
                log_debug(f"Judge APPROVED: {verdict['reason']}")
                
                # STEP 4: Market Analysis
                log_debug("Running market and opportunity analysis...")
                with st.spinner("📊 Analyzing market, opportunity, and competitors..."):
                    analysis_inputs = {
                        "messages": [
                            {
                                "role": "user",
                                "content": f"Analyze the market and competitors for this idea:\nName: {idea_name}\nDescription: {idea_content}"
                            }
                        ]
                    }
                    analysis_response = agent.invoke(analysis_inputs)
                    analysis_text = ""
                    if "messages" in analysis_response and analysis_response["messages"]:
                        analysis_text = analysis_response["messages"][-1].content
                
                full_idea_content = f"{idea_content}\n\n### Comprehensive Analysis\n{analysis_text}"
                save_idea(market, idea_name, full_idea_content)
                
                reply = (
                    f"## 🚀 {idea_name}\n\n{idea_content}\n\n"
                    f"✅ **Approved & Saved** — {verdict['reason']}\n\n"
                    f"--- \n\n## 📊 Comprehensive Analysis\n{analysis_text}"
                )
            else:
                log_debug(f"Judge REJECTED: {verdict['reason']}")
                reply = (
                    f"## ❌ {idea_name} (Rejected)\n\n{idea_content}\n\n"
                    f"⚠️ **Rejected** — {verdict['reason']}\n\n"
                    f"*This idea was not saved. Try a different angle.*"
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
