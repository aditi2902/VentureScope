import streamlit as st
from langchain_ollama import ChatOllama

# =====================================
# PAGE CONFIG
# =====================================

st.set_page_config(
    page_title="Market Analysis Agent",
    page_icon="📊",
    layout="wide"
)

# =====================================
# HEADER
# =====================================

st.title("📊 Market Analysis Agent")
st.write("Enter a market and generate a market analysis report.")

# =====================================
# LOAD MODEL
# =====================================

@st.cache_resource
def load_model():
    return ChatOllama(
        model="qwen3:4b",
        temperature=0.3
    )

# =====================================
# MODEL INIT
# =====================================

try:
    llm = load_model()
    st.success("✅ Qwen3:4B Loaded Successfully")
except Exception as e:
    st.error(f"❌ Failed to load Ollama model:\n\n{e}")
    st.stop()

# =====================================
# USER INPUT
# =====================================

market = st.text_input(
    "Market Topic",
    placeholder="Electric Vehicle Market"
)

# =====================================
# ANALYZE BUTTON
# =====================================

if st.button("Analyze Market"):

    if not market.strip():
        st.warning("Please enter a market topic.")
        st.stop()

    prompt = f"""
    Analyze the {market} market.

    Include:
    - Overview
    - Estimated CAGR
    - Major Players
    - Growth Drivers
    - Risks
    - Future Outlook

    Keep the report under 300 words.
    """
    try:

        with st.spinner("Analyzing Market..."):

            response = llm.invoke(prompt)

        st.markdown("---")
        st.markdown(response.content)

    except Exception as e:

        st.error(f"Analysis Error:\n\n{e}")