"""
Serper Search Client
====================
Shared module that wraps the Serper.dev Google Search API.
All other modules (pain_points, opportunity_analysis, web_research)
import from here instead of using ddgs directly.
"""

import os
import logging
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

logger = logging.getLogger(__name__)

SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
SERPER_URL = "https://google.serper.dev/search"


def serper_search(query: str, max_results: int = 5) -> list[dict]:
    """
    Run a Google search via Serper API and return results as a list of dicts.
    Each dict has: 'title', 'body' (snippet), 'href' (link).

    Falls back to an empty list on any error.
    """
    if not SERPER_API_KEY or SERPER_API_KEY == "your_api_key_here":
        logger.error("SERPER_API_KEY is not set. Add it to your .env file.")
        return []

    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "q": query,
        "num": max_results,
    }

    try:
        resp = requests.post(SERPER_URL, json=payload, headers=headers, timeout=8)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("organic", [])[:max_results]:
            results.append({
                "title": item.get("title", ""),
                "body": item.get("snippet", ""),
                "href": item.get("link", ""),
            })
        return results

    except Exception as e:
        logger.warning(f"Serper search failed for '{query}': {e}")
        return []
