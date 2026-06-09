import streamlit as st
from langchain.agents import create_agent
from opportunity_analysis import analyze_market, analyze_opportunity

# =====================================
# PAGE CONFIG
# =====================================

st.set_page_config(
    page_title="Market & Opportunity Analysis Agent",
    page_icon="📊",
    layout="wide"
)

# =====================================
# HEADER
# =====================================

st.title("📊 Market & Opportunity Analysis Agent")
st.write("Enter a business idea or market topic to generate a comprehensive market and opportunity analysis report.")

# =====================================
# LOAD AGENT
# =====================================

@st.cache_resource
def load_agent():
    return create_agent(
        model="ollama:qwen3:8b",
        tools=[analyze_market, analyze_opportunity],
        system_prompt=(
            "You are an expert business and market analyst. Use BOTH the analyze_market and "
            "analyze_opportunity tools to evaluate the user's topic. Then, compile a comprehensive "
            "report (under 500 words) containing two distinct sections:\n"
            "1. Market Analysis (Structure, CAGR, Drivers, Risks, Outlook)\n"
            "2. Opportunity Analysis (Market Need, Value Proposition, Revenue Streams, Competitive Edge, Complexity)\n"
            "Ensure the output is clean, professional, and well-formatted."
        ),
    )

# =====================================
# MODEL INIT
# =====================================

try:
    agent = load_agent()
    st.success("✅ Qwen3:8B Agent Loaded Successfully")
except Exception as e:
    st.error(f"❌ Failed to load Ollama agent:\n\n{e}")
    st.stop()

# =====================================
# USER INPUT
# =====================================

market = st.text_input(
    "Opportunity/Market Topic",
    placeholder="Electric Vehicle Charging Network"
)

# =====================================
# ANALYZE BUTTON
# =====================================

if st.button("Run Comprehensive Analysis"):

    if not market.strip():
        st.warning("Please enter a topic.")
        st.stop()

    inputs = {
        "messages": [
            {
                "role": "user",
                "content": f"Provide both a market analysis and an opportunity analysis for: {market}"
            }
        ]
    }
    
    try:
        with st.spinner("Analyzing Market & Opportunity..."):
            response = agent.invoke(inputs)
            
            final_answer = ""
            if "messages" in response and response["messages"]:
                final_answer = response["messages"][-1].content

        st.markdown("---")
        if final_answer:
            st.markdown(final_answer)
        else:
            st.warning("The agent did not return a response.")

    except Exception as e:
        st.error(f"Analysis Error:\n\n{e}")