import logging
import streamlit as st
from langchain.agents import create_agent
from langchain.tools import tool

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@tool
def analyze_market(topic: str) -> str:
    """Return a market analysis summary for the specified topic."""
    return (
        f"Market analysis for {topic}:\n"
        "- Market structure: define the key segments, value chain, and competitive landscape.\n"
        "- CAGR estimate: provide an illustrative compound annual growth rate based on market dynamics.\n"
        "- Growth drivers: identify the main demand drivers and opportunities.\n"
        "- Risks and challenges: summarize the key barriers and headwinds.\n"
        "- Outlook: describe the expected direction and strategic focus areas."
    )


@st.cache_resource
def create_market_agent():
    return create_agent(
        model="ollama:llama3.2:1b",
        tools=[analyze_market],
        system_prompt=(
            "You are a market analysis chatbot. Respond like a business analyst, "
            "focus on market structure, competitive segments, growth drivers, risks, "
            "and an estimated CAGR outlook for the topic provided."
        ),
    )


if "history" not in st.session_state:
    st.session_state.history = []
if "debug_logs" not in st.session_state:
    st.session_state.debug_logs = []


def log_debug(message: str) -> None:
    logger.debug(message)
    st.session_state.debug_logs.append(message)


st.set_page_config(page_title="Market Analysis Chatbot", page_icon="💬")
st.title("Market Analysis Chatbot")
st.write(
    "Ask about any market topic and get a structured market analysis response. "
    "The bot will answer with market structure, growth outlook, CAGR, risks, "
    "and strategic observations."
)

agent = create_market_agent()

with st.form(key="chat_form", clear_on_submit=True):
    user_input = st.text_input("Your message", "Analyze the electric vehicle market structure and CAGR.")
    submit_button = st.form_submit_button("Send")

if submit_button and user_input.strip():
    user_text = user_input.strip()
    st.session_state.history.append({"role": "user", "content": user_text})
    log_debug(f"User submitted: {user_text}")
    inputs = {
    "messages": [
        {
            "role": "user",
            "content": f"Create a detailed market analysis report for: {user_text}"
        }
    ]
}
    log_debug(f"Agent input messages: {inputs}")
    try:
        response = agent.invoke(inputs)
        final_answer = ""

        if "messages" in response and response["messages"]:
            final_answer = response["messages"][-1].content

        if final_answer:
            log_debug(f"Assistant final reply: {final_answer}")
            st.session_state.history.append({"role": "assistant", "content": final_answer})
        else:
            log_debug("Agent returned no reply text.")
            st.warning("The agent did not return a response.")
    except Exception as e:
        error_message = f"Agent invocation error: {e}"
        log_debug(error_message)
        st.error("An error occurred while generating the reply. See debug logs.")

for message in st.session_state.history:
    with st.chat_message(message["role"]):
        st.write(message["content"])

with st.sidebar.expander("Debug logs", expanded=True):
    if st.session_state.debug_logs:
        st.write("---")
        for index, log_line in enumerate(st.session_state.debug_logs, start=1):
            st.text(f"{index}. {log_line}")
    else:
        st.write("No debug logs yet.")

st.markdown("---")
st.caption("Powered by LangChain and Ollama model via Streamlit.")
