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


graph = create_agent(
    model="ollama:llama3.2:1b",
    tools=[analyze_market],
    system_prompt=(
        "You are a market analysis assistant. For any topic given by the user, "
        "focus on market structure, competitive segments, growth drivers, risks, "
        "and an estimated CAGR outlook. Use the tool to generate a structured, "
        "business-oriented market analysis response."
    ),
)

inputs = {
    "messages": [
        {
            "role": "user",
            "content": "Please analyze the market structure and CAGR for the renewable energy industry."
        }
    ]
}

for chunk in graph.stream(inputs, stream_mode="updates"):
    print(chunk)
