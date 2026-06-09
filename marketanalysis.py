import logging
import streamlit as st
from langchain.agents import create_agent
from opportunity_analysis import analyze_market, analyze_opportunity

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@st.cache_resource
def create_market_agent():
    return create_agent(
        model="ollama:llama3.2:1b",
        tools=[analyze_market, analyze_opportunity],
        system_prompt=(
            "You are a market and business opportunity analysis chatbot. Respond like a business analyst. "
            "Focus on market structure, competitive segments, growth drivers, risks, CAGR outlook, "
            "as well as business opportunity evaluation (market need, value proposition, revenue streams, "
            "competitive edge, and execution complexity) for the topic provided."
        ),
    )


if "history" not in st.session_state:
    st.session_state.history = []
if "debug_logs" not in st.session_state:
    st.session_state.debug_logs = []


def log_debug(message: str) -> None:
    logger.debug(message)
    st.session_state.debug_logs.append(message)


st.set_page_config(page_title="Market & Opportunity Analysis Chatbot", page_icon="💬")
st.title("Market & Opportunity Analysis Chatbot")
st.write(
    "Ask about any market topic or business opportunity and get a structured analysis response. "
    "The bot can provide market structure, growth outlook, CAGR, risks, or evaluate new business opportunities "
    "(market need, value proposition, revenue streams, competitive edge, and execution complexity)."
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
