import streamlit as st
from langchain.agents import create_agent


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
            "You are a market analysis assistant. For any topic given by the user, "
            "focus on market structure, competitive segments, growth drivers, risks, "
            "and an estimated CAGR outlook. Use the tool to generate a structured, "
            "business-oriented market analysis response."
        ),
    )


st.title("Market Analysis Agent")
st.write(
    "Enter a market topic and the assistant will analyze market structure, CAGR, "
    "drivers, risks, and outlook for that topic."
)

topic = st.text_input("Market topic", "renewable energy industry")
run = st.button("Analyze market")

agent = create_market_agent()

if run:
    if not topic.strip():
        st.warning("Please enter a market topic.")
    else:
        result_box = st.empty()
        result_box.markdown("### Analysis in progress...")
        result_text = ""
        inputs = {
            "messages": [
                {
                    "role": "user",
                    "content": f"Please analyze the market structure and CAGR for the {topic}."
                }
            ]
        }
        for chunk in agent.stream(inputs, stream_mode="updates"):
            result_text += str(chunk)
            result_box.code(result_text)
        if not result_text:
            result_box.info("The agent did not return any analysis.")
