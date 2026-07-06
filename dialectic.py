"""
Dialectic Debate Engine for Startup Ideas.
Uses a Bull Investor Agent, a Bear Investor Agent, and an Investment Judge
to evaluate the viability of a startup idea based on market analysis.
"""

import os
import time
import random
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv(override=True)

def _load_fallback_llm():
    """Primary fallback: Llama 3.1 70B (stable Nvidia endpoint)."""
    llm = ChatOpenAI(
        model="meta/llama-3.1-70b-instruct",
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=os.environ.get("NVIDIA_API_KEY"),
        temperature=0.7,
    )
    original_invoke = llm.invoke
    def tracked_invoke(*args, **kwargs):
        print(f"🤖 [LLM CALL] -> Model: meta/llama-3.1-70b-instruct (Nvidia NIM Fallback)")
        return original_invoke(*args, **kwargs)
    object.__setattr__(llm, "invoke", tracked_invoke)
    return llm

def invoke_with_retry(llm, prompt, max_retries=5, initial_delay=3.0) -> str:
    """
    Invokes the LLM with exponential backoff for transient RPM rate limits (429).
    Falls back to Llama 3.1 70B on quota exhaustion or hard errors.
    """
    # Preventative delay between NVIDIA NIM calls to respect the free-tier rate limit
    if "ChatOpenAI" in str(type(llm)):
        time.sleep(2)

    delay = initial_delay
    for attempt in range(max_retries):
        try:
            response = llm.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            err_str = str(e)
            is_daily_quota = "RESOURCE_EXHAUSTED" in err_str or "exceeded your current quota" in err_str.lower()
            is_rpm_limit = "429" in err_str and not is_daily_quota
            is_not_found = "404" in err_str or "NOT_FOUND" in err_str

            # Daily quota or model not found → jump to fallback immediately
            if is_daily_quota or is_not_found:
                print(f"[dialectic] Hard quota/404 error — skipping retries, falling back immediately: {e}")
                break

            # Transient RPM rate limit → wait and retry
            if is_rpm_limit and attempt < max_retries - 1:
                sleep_time = delay + random.uniform(0, 1.0)
                print(f"[dialectic] Rate limit hit (429). Retrying in {sleep_time:.2f}s... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(sleep_time)
                delay *= 2.0
                continue

            # Any other non-retriable error → fall back
            print(f"[dialectic] LLM invoke failed with error: {e}. Falling back...")
            break

    # Fallback: Llama 3.1 70B
    print("[dialectic] Falling back to Llama 3.1 70B (Nvidia NIM)...")
    try:
        fallback_llm = _load_fallback_llm()
        fallback_response = fallback_llm.invoke(prompt)
        return fallback_response.content.strip()
    except Exception as llama_err:
        print(f"[dialectic] Llama fallback failed: {llama_err}")
        raise

def bull_case(idea_name: str, idea_content: str, market: str, analysis_text: str, round_num: int, history: str, llm, sector: str = "", team_size: str = "", budget: str = "") -> str:
    """
    Plays the role of an optimistic VC partner championing the startup.
    Generates strong pro-investment arguments with evidence from analysis.
    """
    if llm is None:
        llm = _load_fallback_llm()

    constraints_text = ""
    if sector or team_size or budget:
        constraints_text = f"\n## Constraints & Execution Context:\n- Sector: {sector}\n- Team Size: {team_size}\n- Available Budget: {budget}\n"

    if round_num == 1:
        prompt = f"""/no_think
You are an optimistic VC partner championing this startup. Your goal is to argue why the following startup idea is highly investable and has massive potential.

## Startup Under Evaluation
**Name:** {idea_name}
**Market/Domain:** {market}
**Description:** {idea_content}

## Market Research & Analysis
{analysis_text}
{constraints_text}
Use the market research and analysis to back up your points with specific facts, CAGR, market size, and customer pain points.
Explain why {idea_name} is highly realistic, feasible, and scalable within these specific team size and budget constraints.
CRITICAL INSTRUCTION: Base your entire debate ONLY on the startup description provided above. Do NOT hallucinate features, products, or business models that are not explicitly mentioned in the description. Focus your arguments strictly on the market potential and feasibility of what is actually described.
Provide 3-5 structured, strong arguments for investing in {idea_name}. Be professional, persuasive, and quantitative where possible.
Do not write any pleasantries or introductory meta-text. Jump straight into the pro-arguments.
"""
    else:
        prompt = f"""/no_think
You are an optimistic VC partner championing this startup. Rebut the Bear investor's counter-arguments. Defend the startup's viability, show why the Bear's risks are manageable or mitigated, and reinforce why this is a massive investment opportunity.

## Startup Under Evaluation
**Name:** {idea_name}
**Market/Domain:** {market}
**Description:** {idea_content}
{constraints_text}
Address how the team can execute and build a solid competitive moat even with the given team size and budget constraints.
Here is the debate transcript so far:
{history}

Provide your final rebuttal. Address the Bear's specific concerns about {idea_name} directly and summarize why we must invest now.
Do not write any pleasantries or introductory meta-text. Jump straight into the rebuttal.
"""

    return invoke_with_retry(llm, prompt)

def bear_case(idea_name: str, idea_content: str, market: str, analysis_text: str, round_num: int, history: str, llm, sector: str = "", team_size: str = "", budget: str = "") -> str:
    """
    Plays the role of a skeptical risk-focused investor.
    Generates contra-investment arguments and rebuts the Bull investor.
    """
    if llm is None:
        llm = _load_fallback_llm()

    constraints_text = ""
    if sector or team_size or budget:
        constraints_text = f"\n## Constraints & Execution Context:\n- Sector: {sector}\n- Team Size: {team_size}\n- Available Budget: {budget}\n"

    if round_num == 1:
        prompt = f"""/no_think
You are a skeptical, risk-focused venture investor. Your goal is to argue why the following startup idea is NOT investable. Highlight risks like market size limitations, execution challenges, intense competition, lack of defensive moats, regulatory issues, and cash flow constraints.

## Startup Under Evaluation
**Name:** {idea_name}
**Market/Domain:** {market}
**Description:** {idea_content}

## Market Research & Analysis
{analysis_text}
{constraints_text}
Particularly scrutinize if {idea_name} is actually realistic and executable under these team size and budget constraints. Highlight resource bottlenecks.
CRITICAL INSTRUCTION: Base your entire debate ONLY on the startup description provided above. Do NOT hallucinate flaws in features or products that the startup never claimed to build. Attack the actual concept described.
Here is the Bull investor's argument:
{history}

Provide 3-5 structured, strong arguments AGAINST investing in {idea_name}. Be highly critical, analytical, and point out flaws in the Bull's assumptions.
Do not write any pleasantries or introductory meta-text. Jump straight into the contra-arguments.
"""
    else:
        prompt = f"""/no_think
You are a skeptical, risk-focused venture investor. Counter the Bull investor's rebuttal. Show why their mitigations are unrealistic, why the risks remain critical barriers, and why this business is highly likely to fail or underperform.

## Startup Under Evaluation
**Name:** {idea_name}
**Market/Domain:** {market}
**Description:** {idea_content}
{constraints_text}
Dismantle the Bull's claims about {idea_name}'s execution feasibility given the strict limits of the team size and budget.
Here is the debate transcript so far:
{history}

Provide your final counter-rebuttal. Dismantle the Bull's rebuttal and summarize why we must pass on investing in {idea_name}.
Do not write any pleasantries or introductory meta-text. Jump straight into the counter-rebuttal.
"""

    return invoke_with_retry(llm, prompt)

def investment_judge(idea_name: str, idea_content: str, market: str, analysis_text: str, history: str, llm, sector: str = "", team_size: str = "", budget: str = "") -> dict:
    """
    Receives the debate history and decides the final investment verdict.
    """
    if llm is None:
        llm = _load_fallback_llm()

    constraints_text = ""
    if sector or team_size or budget:
        constraints_text = f"\n## Constraints & Execution Context:\n- Sector: {sector}\n- Team Size: {team_size}\n- Available Budget: {budget}\n"

    prompt = f"""/no_think
You are the Lead Investment Partner at a top venture capital firm. You are judging a structured dialectic debate between two investors about ONE specific startup idea. Read the idea description carefully — this is the ONLY thing being evaluated.

## The Startup Being Evaluated
**Name:** {idea_name}
**Market/Domain:** {market}
**Description:** {idea_content}

## Market & Feasibility Context
{analysis_text}
{constraints_text}

## Debate Transcript (Bull vs Bear, both arguing exclusively about {idea_name})
{history}

## Your Task
Evaluate the quality of BOTH sides' arguments about **{idea_name}** specifically. Do NOT evaluate a different idea or introduce your own startup concept.

Focus your evaluation on:
1. **Argument strength**: Which side made stronger, more evidence-backed points about {idea_name}?
2. **Feasibility**: Is the proposed solution realistic given the team size ({team_size}) and budget ({budget})?
3. **Market opportunity**: Does {idea_name} address a real, large enough market to generate investor-grade returns?
4. **Execution risk**: Are the Bear's risk concerns about {idea_name} credible and unmitigated?
5. **Moat & defensibility**: Does {idea_name} have a sustainable competitive advantage?

CRITICAL INSTRUCTION: Remember this is a startup concept operating with a budget/stage of "{budget}". Every new startup at this stage has massive risks, unproven moats, and fierce competition. Do NOT reject an idea simply because it has risks. You should rate it INVESTABLE if the core problem is real, the solution is plausible under the {budget} constraints, and the market opportunity is large enough to justify the risk. Be an optimistic venture capitalist looking for reasons to invest, rather than a pessimistic analyst looking for reasons to pass.
DO NOT conduct an originality/novelty check — that has already been done. Focus purely on investment viability and debate quality.

Decide whether **{idea_name}** is INVESTABLE or NOT INVESTABLE based on the debate and context above. We invest in ideas with a clear moat, high growth potential, realistic feasibility under the given constraints, and manageable risks.

You MUST respond in the following format:

VERDICT: <INVESTABLE or NOT INVESTABLE>
SCORE: <an investment score from 1.0 to 10.0>
EXPLANATION: <a detailed, objective explanation of your decision about {idea_name}, summarizing the key arguments from both sides and why one won, specifically referencing the feasibility given the team size and budget constraints>
BULL SUMMARY: <a brief summary of the Bull's key points about {idea_name}>
BEAR SUMMARY: <a brief summary of the Bear's key points about {idea_name}>

Do not include any thinking block in your output. Start your response with "/no_think".
"""

    raw = invoke_with_retry(llm, prompt)

    # Parse response
    lines = raw.split("\n")
    verdict_val = "NOT INVESTABLE"
    score_val = 5.0
    explanation_val = ""
    bull_summary_val = ""
    bear_summary_val = ""

    current_field = None
    field_content = []

    for line in lines:
        upper_line = line.strip().upper()
        if upper_line.startswith("VERDICT:"):
            if current_field:
                content_str = "\n".join(field_content).strip()
                if current_field == "EXPLANATION":
                    explanation_val = content_str
                elif current_field == "BULL SUMMARY":
                    bull_summary_val = content_str
                elif current_field == "BEAR SUMMARY":
                    bear_summary_val = content_str
            verdict_val = line.split(":", 1)[1].strip()
            current_field = None
            field_content = []
        elif upper_line.startswith("SCORE:"):
            if current_field:
                content_str = "\n".join(field_content).strip()
                if current_field == "EXPLANATION":
                    explanation_val = content_str
                elif current_field == "BULL SUMMARY":
                    bull_summary_val = content_str
                elif current_field == "BEAR SUMMARY":
                    bear_summary_val = content_str
            try:
                score_val = float(line.split(":", 1)[1].strip())
            except ValueError:
                score_val = 5.0
            current_field = None
            field_content = []
        elif upper_line.startswith("EXPLANATION:"):
            if current_field:
                content_str = "\n".join(field_content).strip()
                if current_field == "EXPLANATION":
                    explanation_val = content_str
                elif current_field == "BULL SUMMARY":
                    bull_summary_val = content_str
                elif current_field == "BEAR SUMMARY":
                    bear_summary_val = content_str
            current_field = "EXPLANATION"
            field_content = [line.split(":", 1)[1].strip()]
        elif upper_line.startswith("BULL SUMMARY:"):
            if current_field:
                content_str = "\n".join(field_content).strip()
                if current_field == "EXPLANATION":
                    explanation_val = content_str
                elif current_field == "BULL SUMMARY":
                    bull_summary_val = content_str
                elif current_field == "BEAR SUMMARY":
                    bear_summary_val = content_str
            current_field = "BULL SUMMARY"
            field_content = [line.split(":", 1)[1].strip()]
        elif upper_line.startswith("BEAR SUMMARY:"):
            if current_field:
                content_str = "\n".join(field_content).strip()
                if current_field == "EXPLANATION":
                    explanation_val = content_str
                elif current_field == "BULL SUMMARY":
                    bull_summary_val = content_str
                elif current_field == "BEAR SUMMARY":
                    bear_summary_val = content_str
            current_field = "BEAR SUMMARY"
            field_content = [line.split(":", 1)[1].strip()]
        else:
            if current_field:
                field_content.append(line)

    if current_field:
        content_str = "\n".join(field_content).strip()
        if current_field == "EXPLANATION":
            explanation_val = content_str
        elif current_field == "BULL SUMMARY":
            bull_summary_val = content_str
        elif current_field == "BEAR SUMMARY":
            bear_summary_val = content_str

    investable = "INVESTABLE" in verdict_val.upper() and "NOT INVESTABLE" not in verdict_val.upper()
    return {
        "investable": investable,
        "verdict": verdict_val,
        "score": score_val,
        "explanation": explanation_val if explanation_val else raw,
        "bull_summary": bull_summary_val,
        "bear_summary": bear_summary_val
    }

def run_dialectic(
    idea_name: str,
    idea_content: str,
    market: str,
    analysis_text: str,
    debate_llm=None,
    judge_llm=None,
    sector: str = "",
    team_size: str = "",
    budget: str = "",
) -> dict:
    """
    Orchestrates the 2-round Bull vs Bear debate and invokes the Judge for final decision.

    Args:
        debate_llm: LLM for Bull and Bear agents.
        judge_llm:  LLM for the Investment Judge.
                    Falls back to debate_llm if not provided.
    """
    if debate_llm is None:
        debate_llm = _load_fallback_llm()
    if judge_llm is None:
        judge_llm = debate_llm

    transcript = []

    # Round 1: Bull Initial Case
    bull_r1 = bull_case(idea_name, idea_content, market, analysis_text, 1, "", debate_llm, sector, team_size, budget)
    transcript.append({"role": "Bull (Round 1)", "content": bull_r1})

    # Round 1: Bear Counter (with history of Bull R1)
    history_for_bear_r1 = f"Bull (Round 1):\n{bull_r1}"
    bear_r1 = bear_case(idea_name, idea_content, market, analysis_text, 1, history_for_bear_r1, debate_llm, sector, team_size, budget)
    transcript.append({"role": "Bear (Round 1)", "content": bear_r1})

    # Round 2: Bull Rebuttal
    history_for_bull_r2 = (
        f"--- Round 1: Bull Case ---\n{bull_r1}\n\n"
        f"--- Round 1: Bear Case ---\n{bear_r1}"
    )
    bull_r2 = bull_case(idea_name, idea_content, market, analysis_text, 2, history_for_bull_r2, debate_llm, sector, team_size, budget)
    transcript.append({"role": "Bull (Round 2)", "content": bull_r2})

    # Round 2: Bear Counter-Rebuttal
    history_for_bear_r2 = (
        f"--- Round 1: Bull Case ---\n{bull_r1}\n\n"
        f"--- Round 1: Bear Case ---\n{bear_r1}\n\n"
        f"--- Round 2: Bull Rebuttal ---\n{bull_r2}"
    )
    bear_r2 = bear_case(idea_name, idea_content, market, analysis_text, 2, history_for_bear_r2, debate_llm, sector, team_size, budget)
    transcript.append({"role": "Bear (Round 2)", "content": bear_r2})

    # Full history for judge
    full_history = (
        f"--- Round 1: Bull Case ---\n{bull_r1}\n\n"
        f"--- Round 1: Bear Case ---\n{bear_r1}\n\n"
        f"--- Round 2: Bull Rebuttal ---\n{bull_r2}\n\n"
        f"--- Round 2: Bear Counter-Rebuttal ---\n{bear_r2}"
    )

    verdict = investment_judge(idea_name, idea_content, market, analysis_text, full_history, judge_llm, sector, team_size, budget)
    verdict["transcript"] = transcript
    return verdict
