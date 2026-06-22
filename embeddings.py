"""
Embeddings module using Hugging Face's SentenceTransformers.
Runs locally on CPU. Provides memory store comparisons to ensure unique pain points.
"""

import numpy as np
from sentence_transformers import SentenceTransformer

# Lazy load the model to avoid loading it on module import
_model = None

def get_model():
    """Load and cache the SentenceTransformer model."""
    global _model
    if _model is None:
        # Using a fast, lightweight 384-dimensional model
        _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _model

def embed_texts(texts: list[str]) -> np.ndarray:
    """Batch embed a list of texts. Returns a numpy array of shape (n_texts, 384)."""
    if not texts:
        return np.empty((0, 384))
    model = get_model()
    return model.encode(texts, convert_to_numpy=True)

def embed_text(text: str) -> np.ndarray:
    """Embed a single text string. Returns a 1D numpy array of shape (384,)."""
    model = get_model()
    return model.encode(text, convert_to_numpy=True)

def cosine_similarity(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
    """Compute the cosine similarity between two embedding vectors."""
    a = np.array(embedding1)
    b = np.array(embedding2)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))

def filter_and_ensure_unique_pain_points(new_candidates: list[str], market: str, llm) -> list[str]:
    """
    Compare new candidate pain points against all stored pain points in memory.
    If a candidate has > 0.70 similarity to any memory record, it is flagged as a repeat.
    If repeats exist, the LLM is prompted to rewrite them into brand new, distinct ideas.
    Saves the final pain points to database memory and returns them.
    """
    from database import get_all_generated_pain_points, save_generated_pain_point

    # Fetch existing pain points from memory
    stored = get_all_generated_pain_points()
    
    stored_embs = []
    stored_texts = []
    for s in stored:
        if s["embedding"] is not None:
            try:
                stored_embs.append(np.frombuffer(s["embedding"], dtype=np.float32))
                stored_texts.append(s["pain_point"])
            except Exception:
                pass

    final_unique_needs = []
    candidates_to_process = list(new_candidates)

    # We do up to 3 refinement attempts
    for attempt in range(3):
        if not candidates_to_process:
            break
            
        candidate_embs = embed_texts(candidates_to_process)
        repeating_indices = []
        
        for idx, cand_emb in enumerate(candidate_embs):
            is_repeat = False
            # Check against memory database
            for s_idx, s_emb in enumerate(stored_embs):
                sim = cosine_similarity(cand_emb, s_emb)
                if sim > 0.70:
                    is_repeat = True
                    break
                    
            # Check against already accepted needs in this batch to prevent self-duplication
            if not is_repeat:
                for approved_need in final_unique_needs:
                    approved_emb = embed_text(approved_need)
                    sim = cosine_similarity(cand_emb, approved_emb)
                    if sim > 0.70:
                        is_repeat = True
                        break
                        
            if is_repeat:
                repeating_indices.append(idx)
            else:
                final_unique_needs.append(candidates_to_process[idx])
                
        # If we have enough unique needs, we can stop
        if len(final_unique_needs) >= 3 or not repeating_indices:
            break
            
        # We need more unique needs. Ask LLM to generate replacements.
        needed = 3 - len(final_unique_needs)
        avoid_str = "\n".join([f"- {text}" for text in (stored_texts + final_unique_needs)[:30]])
        
        refinement_prompt = f"""/no_think
You are an expert startup researcher. We need to identify {needed} new, distinct industry-wide pain points for the {market} sector.
You MUST NOT generate any pain point that is semantically similar to the following list of already existing/generated pain points:

Already Generated Pain Points (DO NOT REPEAT):
{avoid_str}

Please generate {needed} brand new, distinct pain points for {market}.

RULES:
- Each pain point must follow this format: "In {market}, [who] cannot [do what] because [structural reason], costing them [impact]."
- Keep each under 65 words.
- They must be completely different from each other and the avoided list.
- Do NOT name specific companies.
- Output each pain point on a new line starting with "- ". Do not add any other text.
"""
        try:
            from dialectic import invoke_with_retry
            response_content = invoke_with_retry(llm, refinement_prompt)
            new_lines = [l.strip().lstrip('-').strip() for l in response_content.split('\n') if l.strip().startswith('-')]
            candidates_to_process = new_lines[:needed]
        except Exception as e:
            print(f"[embeddings] Uniqueness check refinement failed: {e}")
            break

    # Fill fallback defaults if we don't have enough
    while len(final_unique_needs) < 3:
        fallback = f"In {market}, customer demands are unmet due to a lack of integrated digital solutions, costing them efficiency."
        final_unique_needs.append(fallback)

    # Save final 3 pain points to memory so they are remembered next time
    for need in final_unique_needs[:3]:
        if need not in stored_texts:
            try:
                emb = embed_text(need).tobytes()
                save_generated_pain_point(market, need, emb)
            except Exception:
                save_generated_pain_point(market, need)

    return final_unique_needs[:3]


