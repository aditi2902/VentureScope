"""
VC Research Tool
================
Searches for Venture Capital firms that have invested in similar startups
within a given market/domain. Uses Serper (Google Search) by default, with
optional Crunchbase Basic API integration when CRUNCHBASE_API_KEY is set.
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from dotenv import load_dotenv

from search_client import web_search

load_dotenv()

logger = logging.getLogger(__name__)

CRUNCHBASE_API_KEY = os.getenv("CRUNCHBASE_API_KEY", "")
CRUNCHBASE_API_URL = "https://api.crunchbase.com/api/v4"
REQUEST_TIMEOUT = 8

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fetch_page_text(url: str, max_chars: int = 500) -> str:
    """Download a URL and extract main text via trafilatura."""
    try:
        import trafilatura
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers=_HEADERS)
        if resp.status_code != 200:
            return ""
        text = trafilatura.extract(resp.text, include_comments=False, include_tables=False)
        return (text or "")[:max_chars]
    except Exception:
        return ""


def _serper_vc_query(query: str, max_results: int, deep: bool = False) -> list[dict]:
    """Run a Serper search and optionally deep-scrape result pages."""
    results = web_search(query, max_results=max_results)
    if not results:
        return []
    if deep:
        for r in results:
            url = r.get("href", "")
            if url:
                page_text = _fetch_page_text(url)
                if page_text:
                    r["page_text"] = page_text
    return results


def _crunchbase_search_vc_firms(market: str, limit: int = 5) -> list[dict]:
    """Search Crunchbase Basic API for investor organizations in the market."""
    if not CRUNCHBASE_API_KEY:
        return []

    try:
        headers = {
            "X-API-Key": CRUNCHBASE_API_KEY,
            "Content-Type": "application/json",
        }
        payload = {
            "field_ids": [
                "name",
                "short_description",
                "website_url",
                "location_identifiers",
            ],
            "query": [
                {
                    "type": "predicate",
                    "field_id": "facet_ids",
                    "operator_id": "includes",
                    "values": ["investor"],
                }
            ],
            "limit": limit,
        }
        resp = requests.post(
            f"{CRUNCHBASE_API_URL}/searches/organizations",
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        if resp.status_code != 200:
            logger.warning(f"Crunchbase API returned {resp.status_code}: {resp.text[:200]}")
            return []

        data = resp.json()
        results = []
        for entity in data.get("entities", []):
            props = entity.get("properties", {})
            locs = props.get("location_identifiers") or []
            results.append({
                "name": props.get("name", "Unknown"),
                "description": props.get("short_description", ""),
                "website": props.get("website_url", ""),
                "location": locs[0].get("value", "") if locs else "",
            })
        return results

    except Exception as e:
        logger.warning(f"Crunchbase API search failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_vcs(
    market: str,
    idea_name: str,
    idea_content: str,
    pain_point: str,
    max_results: int = 5,
    max_deep_scrape: int = 2,
) -> str:
    """
    Search for Venture Capital firms investing in the given market/domain.

    Runs multiple Serper queries in parallel. If the ``CRUNCHBASE_API_KEY``
    environment variable is set, also queries the Crunchbase Basic API for
    investor organizations.

    Args:
        market: The market/domain (e.g. 'Fitness Apps').
        idea_name: The generated startup name.
        idea_content: The startup idea description.
        pain_point: The selected pain point the idea addresses.
        max_results: Number of results per Serper query (configurable depth).
        max_deep_scrape: Number of queries whose results get deep-scraped.

    Returns:
        A structured markdown report of relevant VC firms.
    """
    # Build diverse queries to surface VC firms
    queries = [
        f'"venture capital" "{market}" investors funding portfolio',
        f'"{market}" startups raised "series A" OR seed investors funding',
        f'site:crunchbase.com "{market}" investors funding portfolio',
        f'site:angellist.com "{market}" venture capital investors',
        f'"{idea_name}" similar startups funded investors',
        f'"{market}" "pain point" startup funding investors venture',
    ]

    # -- Parallel Serper searches -------------------------------------------
    all_results: list[dict] = []
    seen_urls: set[str] = set()

    def _search(query: str, idx: int):
        results = _serper_vc_query(query, max_results=max_results, deep=idx < max_deep_scrape)
        for r in results:
            url = r.get("href", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append(r)

    with ThreadPoolExecutor(max_workers=len(queries)) as pool:
        futures = {pool.submit(_search, q, i): q for i, q in enumerate(queries)}
        for _ in as_completed(futures):
            pass

    # -- Optional Crunchbase search -----------------------------------------
    cb_firms = _crunchbase_search_vc_firms(market, limit=max_results)

    # -- Deduplicate Serper results by title --------------------------------
    seen_titles: set[str] = set()
    unique_results: list[dict] = []
    for r in all_results:
        title = r.get("title", "")
        if title and title not in seen_titles:
            seen_titles.add(title)
            unique_results.append(r)

    # -- Build the markdown report ------------------------------------------
    report = f"## VC Investment Landscape: {market}\n\n"

    if cb_firms:
        report += "### Crunchbase — VC Firms in this Space\n"
        for firm in cb_firms:
            name = firm["name"]
            desc = firm["description"]
            website = firm["website"]
            location = firm["location"]
            report += f"- **{name}**"
            if location:
                report += f" ({location})"
            report += "\n"
            if desc:
                report += f"  - {desc}\n"
            if website:
                report += f"  - [{website}]({website})\n"
        report += "\n"

    if unique_results:
        report += "### Web Search — Investors & Funding Activity\n"
        for i, r in enumerate(unique_results[: max_results * 2], 1):
            title = r.get("title", "")
            body = r.get("body", "")
            href = r.get("href", "")
            page_text = r.get("page_text", "")

            report += f"{i}. **[{title}]({href})**\n"
            if body:
                report += f"   {body}\n"
            if page_text:
                excerpt = page_text[:300]
                report += f"   > {excerpt}\n"
            report += "\n"
    else:
        report += "No VC-related results found via web search.\n"

    if len(report) > 3000:
        report = report[:2900] + "\n\n… (truncated for brevity)"

    return report


# ---------------------------------------------------------------------------
# CLI test entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test VC research for a startup idea.")
    parser.add_argument("--market", default="Fitness Apps", help="Market / domain")
    parser.add_argument("--name", default="FitProgress", help="Startup idea name")
    parser.add_argument("--desc", default="A fitness tracking app that accurately logs workouts, tracks progress over time, and provides personalized training recommendations.", help="Startup idea description")
    parser.add_argument("--pain-point", default="Users cannot accurately track their long-term fitness progress across different workout types.", help="Pain point being solved")
    parser.add_argument("--max-results", type=int, default=5, help="Results per query")
    parser.add_argument("--deep", type=int, default=2, help="Number of queries to deep-scrape")

    args = parser.parse_args()

    print(f"Searching VCs for: {args.market}\n")

    report = find_vcs(
        market=args.market,
        idea_name=args.name,
        idea_content=args.desc,
        pain_point=args.pain_point,
        max_results=args.max_results,
        max_deep_scrape=args.deep,
    )

    print(report)
