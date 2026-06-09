from langchain.tools import tool

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

@tool
def analyze_opportunity(topic: str) -> str:
    """Return an opportunity analysis summary for the specified business opportunity or market topic."""
    return (
        f"Opportunity analysis for {topic}:\n"
        "- Market Need: Describe the core customer pain point and target audience.\n"
        "- Value Proposition: Detail the unique solution and key benefits to the customer.\n"
        "- Revenue Streams: Outline potential business models, pricing, and monetization strategy.\n"
        "- Competitive Edge: Highlight key differentiators and defensibility against competitors.\n"
        "- Execution Complexity: Note the key challenges, dependencies, and initial steps for implementation."
    )
