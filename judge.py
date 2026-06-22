"""
LLM-as-a-Judge module for startup ideas.

Compares a newly generated startup idea against all previously approved
ideas stored in the database. If the new idea is too similar to any
existing one, it is rejected so the agent can try again.
"""

import os
from langchain_openai import ChatOpenAI
from database import get_all_ideas
from dotenv import load_dotenv

load_dotenv(override=True)


import gemini_tracker

def _load_judge_llm():
    """Load a Nvidia NIM DeepSeek V4 Pro model used exclusively for judging."""
    llm = ChatOpenAI(
        model="deepseek-ai/deepseek-v4-pro",
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=os.environ.get("NVIDIA_API_KEY"),
        temperature=0.2,
    )
    original_invoke = llm.invoke
    def tracked_invoke(*args, **kwargs):
        gemini_tracker.track_call()
        return original_invoke(*args, **kwargs)
    object.__setattr__(llm, "invoke", tracked_invoke)
    return llm


def judge_idea(topic: str, idea_name: str, idea_content: str) -> dict:
    """
    Use a two-stage approach to judge whether a new startup idea is too similar
    to any previously approved ideas in the database.

    Stage 1: Vector cosine similarity on HuggingFace embeddings. If > 0.85, reject.
    Stage 2: LLM-as-a-Judge for finer nuance / semantic difference.
    """
    all_ideas = get_all_ideas()

    # No prior ideas at all → auto-approve
    if not all_ideas:
        return {
            "approved": True,
            "reason": "No previous startup ideas in the database. This is the first one.",
            "similar_ids": [],
        }

    # --- STAGE 1: Cosine Similarity Check on Embeddings ---
    new_text = f"{idea_name}\n\n{idea_content}"
    try:
        from embeddings import embed_text, cosine_similarity
        import numpy as np
        new_emb = embed_text(new_text)
        
        for idea in all_ideas:
            if idea.get("embedding") is not None:
                existing_emb = np.frombuffer(idea["embedding"], dtype=np.float32)
                sim = cosine_similarity(new_emb, existing_emb)
                if sim > 0.85:
                    return {
                        "approved": False,
                        "reason": f"Too similar to the existing idea '{idea['idea_name']}' (semantic similarity: {sim:.2f}).",
                        "similar_ids": [idea["id"]],
                    }
    except Exception as e:
        # Fallback if embeddings/similarity fails
        pass

    # --- STAGE 2: LLM-as-a-Judge fallback / nuance check ---
    # Build a digest of every existing idea for the judge
    existing_digest = ""
    all_ids = []
    for i, idea in enumerate(all_ideas[:15], 1):  # cap at 15 to stay within context
        existing_digest += (
            f"\n--- Existing Idea #{i} (ID: {idea['id']}) ---\n"
            f"Name: {idea['idea_name']}\n"
            f"Topic: {idea['topic']}\n"
            f"Description: {idea['idea_content'][:600]}\n"
        )
        all_ids.append(idea["id"])

    judge_prompt = f"""You are a startup idea originality judge.

Your task: Decide whether a NEW startup idea is sufficiently unique compared to 
ALL previously approved ideas listed below. An idea is "too similar" if it targets 
the same problem, proposes essentially the same solution, or would compete in 
the exact same niche with no meaningful differentiation.

## ALL Previously Approved Startup Ideas
{existing_digest}

## New Startup Idea (to evaluate)
Name: {idea_name}
Topic: {topic}
Description: {idea_content[:1200]}

## Instructions
1. Compare the NEW idea against EVERY existing idea above (not just same-topic ones).
2. If ANY existing idea is essentially the same concept, REJECT.
3. If the new idea is meaningfully different from all existing ideas, APPROVE.
4. Respond with EXACTLY this format:

VERDICT: APPROVED
REASON: <one-sentence explanation>

OR

VERDICT: REJECTED
REASON: <one-sentence explaining which existing idea it duplicates and why>

/no_think"""

    from dialectic import invoke_with_retry
    llm = _load_judge_llm()
    raw = invoke_with_retry(llm, judge_prompt)

    # Parse the verdict
    approved = True
    reason = raw
    similar_ids = []

    for line in raw.split("\n"):
        line_stripped = line.strip()
        if line_stripped.upper().startswith("VERDICT:"):
            verdict_text = line_stripped.upper().replace("VERDICT:", "").strip()
            approved = "APPROVED" in verdict_text
        if line_stripped.upper().startswith("REASON:"):
            reason = line_stripped[len("REASON:"):].strip()

    if not approved:
        similar_ids = all_ids  # all were compared

    return {
        "approved": approved,
        "reason": reason,
        "similar_ids": similar_ids,
    }

