"""
VC Research Tool
================
Searches for Venture Capital firms that have invested in similar startups
within a given market/domain. Uses Serper (Google Search) by default, with
optional Crunchbase Basic API integration when CRUNCHBASE_API_KEY is set.
"""

import logging
import os
import re
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

# Patterns that strongly suggest a VC firm name
_VC_NAME_PATTERNS = [
    re.compile(r'\b([A-Z][A-Za-z0-9\'&.\s]+?(?:Capital|Ventures|Partners|Equity|Group|Fund|Investments|Associates|Advisors|Global|Growth))\b'),
    re.compile(r'led\s+by\s+([A-Z][A-Za-z0-9\s&.]+?)(?:[,]|\s+invested|\s+participated|\s+and|\s+at\s+|$)'),
    re.compile(r'raised\s+\$[\d.,]+\s*(?:million|billion|M|B|Mn|Bn)?\s*(?:in\s+)?(?:funding|Series|Seed|Round|from).*?(?:from\s+|led\s+by\s+)([A-Z][A-Za-z0-9\s&.\']+?)(?:[,]|\s+and|\s+\.|$)'),
]

# Known notable VC firms to catch even without pattern matches
_KNOWN_VC = [
    "Andreessen Horowitz", "a16z", "Sequoia Capital", "Accel", "Benchmark",
    "Greylock Partners", "Kleiner Perkins", "Bessemer Venture Partners",
    "Index Ventures", "Lightspeed Venture Partners", "Insight Partners",
    "General Catalyst", "Founders Fund", "Y Combinator", "First Round Capital",
    "Union Square Ventures", "Tiger Global", "SoftBank", "Coatue",
    "Menlo Ventures", "Redpoint Ventures", "NEA", "Battery Ventures",
    "Felicis Ventures", "GV", "Khosla Ventures", "Matrix Partners",
    "Mayfield Fund", "Spark Capital", "Venrock", "8VC",
]


_SECTOR_MAPPING = [
    {
        "keywords": ["health", "medical", "biotech", "clinical", "fitness", "wellness", "doctor", "hospital", "patient", "care"],
        "category": "HealthTech & Wellness",
        "vcs": [
            {"name": "F-Prime Capital", "location": "Cambridge, MA", "desc": "Global venture capital firm investing in healthcare and life sciences.", "web": "fprimecapital.com"},
            {"name": "Oak HC/FT", "location": "Greenwich, CT", "desc": "Investing in early to growth-stage healthcare and financial technology.", "web": "oakhcft.com"},
            {"name": "Venrock", "location": "Palo Alto, CA", "desc": "Rockefeller family venture arm focusing on healthcare tech and IT.", "web": "venrock.com"},
            {"name": "Rock Health", "location": "San Francisco, CA", "desc": "Seed fund and advisory firm dedicated entirely to digital health.", "web": "rockhealth.com"},
            {"name": "Frazier Healthcare Partners", "location": "Seattle, WA", "desc": "Providing growth equity and venture capital to healthcare leaders.", "web": "frazierhealthcare.com"}
        ]
    },
    {
        "keywords": ["finance", "payment", "fintech", "banking", "crypto", "blockchain", "lending", "insurance", "insurtech", "wealth"],
        "category": "FinTech & Web3",
        "vcs": [
            {"name": "Ribbit Capital", "location": "Palo Alto, CA", "desc": "Venture capital firm focused on financial services technology.", "web": "ribbitcap.com"},
            {"name": "Valar Ventures", "location": "New York, NY", "desc": "Venture fund backing high-growth fintech startups globally.", "web": "valar.com"},
            {"name": "QED Investors", "location": "Alexandria, VA", "desc": "Leading fintech venture firm supporting financial disruptors.", "web": "qedinvestors.com"},
            {"name": "Canapi Ventures", "location": "Washington, DC", "desc": "Venture capital firm investing in banking and fintech innovation.", "web": "canapi.com"},
            {"name": "Point72 Ventures", "location": "New York, NY", "desc": "Investing in early-stage fintech, software, and AI.", "web": "p72.vc"}
        ]
    },
    {
        "keywords": ["deeptech", "ai", "artificial intelligence", "ml", "machine learning", "robot", "quantum", "space", "hardware", "hard tech", "sensor", "automotive", "physics"],
        "category": "DeepTech & AI",
        "vcs": [
            {"name": "Khosla Ventures", "location": "Menlo Park, CA", "desc": "Venture capital firm focusing on early-stage deeptech, clean energy, and AI.", "web": "khoslaventures.com"},
            {"name": "Founders Fund", "location": "San Francisco, CA", "desc": "Stage-agnostic firm investing in science and engineering breakthroughs.", "web": "foundersfund.com"},
            {"name": "Lux Capital", "location": "New York / Menlo Park", "desc": "Investing in counter-conventional deeptech and science ventures.", "web": "luxcapital.com"},
            {"name": "DCVC (Data Collective)", "location": "Palo Alto, CA", "desc": "Venture capital firm investing in AI, compute, and physical science.", "web": "dcvc.com"},
            {"name": "Fifty Years", "location": "San Francisco, CA", "desc": "Seed-stage venture fund backing deeptech solving key global challenges.", "web": "fiftyyears.com"}
        ]
    },
    {
        "keywords": ["saas", "b2b", "enterprise", "cloud", "software", "infrastructure", "devops", "security", "database", "crm", "workflow"],
        "category": "Enterprise SaaS",
        "vcs": [
            {"name": "Sequoia Capital", "location": "Menlo Park, CA", "desc": "Legendary venture firm investing in early to late-stage enterprise leaders.", "web": "sequoiacap.com"},
            {"name": "Bessemer Venture Partners", "location": "San Francisco, CA", "desc": "Top-tier VC firm known for cloud computing and SaaS research.", "web": "bvp.com"},
            {"name": "Accel", "location": "Palo Alto, CA", "desc": "Early and growth-stage venture capital firm investing in software leaders.", "web": "accel.com"},
            {"name": "Index Ventures", "location": "London / San Francisco", "desc": "Supporting SaaS founders from seed to IPO.", "web": "indexventures.com"},
            {"name": "Battery Ventures", "location": "Boston, MA", "desc": "Technology-focused investment firm focusing on enterprise software.", "web": "battery.com"}
        ]
    },
    {
        "keywords": ["app", "b2c", "consumer", "social", "e-commerce", "marketplace", "game", "gaming", "media", "entertainment", "retail", "shop"],
        "category": "Consumer & Mobile App",
        "vcs": [
            {"name": "Andreessen Horowitz", "location": "Menlo Park, CA", "desc": "Stage-agnostic venture firm backing bold consumer tech founders.", "web": "a16z.com"},
            {"name": "Benchmark", "location": "San Francisco, CA", "desc": "Early-stage venture capital firm focused on social, mobile, and consumer.", "web": "benchmark.com"},
            {"name": "Greycroft", "location": "New York / LA", "desc": "Venture capital firm focused on mobile and consumer internet startup opportunities.", "web": "greycroft.com"},
            {"name": "General Catalyst", "location": "Cambridge, MA", "desc": "Supporting early-stage and transformational consumer app businesses.", "web": "generalcatalyst.com"},
            {"name": "First Round Capital", "location": "Philadelphia, PA", "desc": "Helping seed-stage startups get their first consumer users.", "web": "firstround.com"}
        ]
    }
]

_DEFAULT_VCS = [
    {"name": "Y Combinator", "location": "Mountain View, CA", "desc": "World's leading startup accelerator backing early-stage tech teams.", "web": "ycombinator.com"},
    {"name": "Techstars", "location": "Boulder, CO", "desc": "Global accelerator network providing investment and mentorship.", "web": "techstars.com"},
    {"name": "Sequoia Capital", "location": "Menlo Park, CA", "desc": "Legendary venture firm investing in legendary companies.", "web": "sequoiacap.com"},
    {"name": "SV Angel", "location": "San Francisco, CA", "desc": "Super angel fund investing in early-stage consumer and enterprise software.", "web": "svangel.com"},
    {"name": "500 Global", "location": "San Francisco, CA", "desc": "Venture capital firm on a mission to discover and back tech founders.", "web": "500.co"}
]


def _get_dummy_vcs(market: str) -> tuple[str, list[dict]]:
    """Determine sector and return relevant fallback VC list."""
    market_lower = market.lower()
    best_cat = "General Tech & Internet"
    best_vcs = _DEFAULT_VCS
    max_matches = 0
    
    for mapping in _SECTOR_MAPPING:
        matches = sum(1 for kw in mapping["keywords"] if kw in market_lower)
        if matches > max_matches:
            max_matches = matches
            best_cat = mapping["category"]
            best_vcs = mapping["vcs"]
            
    return best_cat, best_vcs


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fetch_page_text(url: str, max_chars: int = 800) -> str:
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


def _search_vc(query: str, max_results: int, deep: bool = False) -> list[dict]:
    """Run a web search and optionally deep-scrape result pages."""
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


def _extract_vc_names(text: str) -> set[str]:
    """Extract likely VC firm names from a text string."""
    found = set()

    # Pattern-based extraction
    for pattern in _VC_NAME_PATTERNS:
        for match in pattern.finditer(text):
            name = match.group(1).strip().rstrip(",").rstrip(".")
            # Filter out false positives
            if len(name) > 3 and not name.lower().startswith(("the ", "this ", "that ")):
                found.add(name)

    # Known VC check (catch names that don't match patterns)
    text_lower = text.lower()
    for name in _KNOWN_VC:
        if name.lower() in text_lower:
            found.add(name)

    return found


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
    max_chars: int = 3000,
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
        max_chars: Maximum report length (0 = no limit).

    Returns:
        A structured markdown report of relevant VC firms.
    """
    # -- Queries that surface VC firm names ---------------------------------
    vc_queries = [
        f'"top venture capital" "{market}" list firms',
        f'"{market}" startup "raised" "led by" OR "from" funding',
        f'"{market}" "series" funding investor venture capital',
    ]

    # -- General queries (original) -----------------------------------------
    general_queries = [
        f'"venture capital" "{market}" investors funding portfolio',
        f'"{market}" startups raised "series A" OR seed investors funding',
        f'crunchbase "{market}" investors funding',
        f'angellist "{market}" venture capital investors',
        f'"{idea_name}" similar startups funded investors',
        f'"{market}" "pain point" startup funding investors venture',
    ]

    all_queries = vc_queries + general_queries
    num_vc_queries = len(vc_queries)

    # -- Parallel search ----------------------------------------------------
    all_results: list[dict] = []
    seen_urls: set[str] = set()
    all_vc_names: set[str] = set()

    def _search(query: str, idx: int):
        deep = idx < max_deep_scrape
        results = _search_vc(query, max_results=max_results, deep=deep)
        for r in results:
            # Extract VC names from every result
            text = f"{r.get('title', '')} {r.get('body', '')} {r.get('page_text', '')}"
            all_vc_names.update(_extract_vc_names(text))

            url = r.get("href", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_results.append(r)

    with ThreadPoolExecutor(max_workers=len(all_queries)) as pool:
        futures = {pool.submit(_search, q, i): q for i, q in enumerate(all_queries)}
        for _ in as_completed(futures):
            pass

    # -- Optional Crunchbase search -----------------------------------------
    cb_firms = _crunchbase_search_vc_firms(market, limit=max_results)
    for firm in cb_firms:
        if firm["name"]:
            all_vc_names.add(firm["name"])

    # -- Deduplicate by title -----------------------------------------------
    seen_titles: set[str] = set()
    unique_results: list[dict] = []
    for r in all_results:
        title = r.get("title", "")
        if title and title not in seen_titles:
            seen_titles.add(title)
            unique_results.append(r)

    # -- Build the markdown report ------------------------------------------
    category, matched_vcs = _get_dummy_vcs(market)
    report = f"## VC Investment Landscape: {market}\n\n"
    report += f"### Target VC Recommendations ({category})\n"
    report += f"The following top-tier and sector-specific venture firms are highly aligned with the **{market}** domain and **{idea_name}**:\n\n"
    for vc in matched_vcs:
        report += f"- **{vc['name']}** ({vc['location']})\n"
        report += f"  - *Focus:* {vc['desc']}\n"
        report += f"  - *Website:* [{vc['web']}](https://{vc['web']})\n"
    report += "\n"

    # VC Firms section (new)
    if all_vc_names:
        _VC_SUFFIXES = ("Capital", "Ventures", "Partners", "Equity", "Fund", "Group", "Investments", "Global", "Growth", "Associates", "Advisors")

        clean_names = set()
        for name in sorted(all_vc_names, key=lambda x: -len(x)):
            lower = name.lower()
            if len(name) < 4:
                continue
            # Skip obviously generic phrases
            if any(lower.startswith(skip) for skip in [
                "top ", "list ", "best ", "series ", "how to ", "guide ",
            ]):
                continue
            if lower in ("top 13 global",):
                continue
            # Strip leading noise words
            for prefix in ("Crunchbase ", "AngelList ", "Site:"):
                if name.startswith(prefix):
                    name = name[len(prefix):]
                    break
            # Skip sentences / long phrases (VC names are 1ΓÇô5 words)
            if len(name.split()) > 5:
                continue
            # Skip phrases that contain "has" / "including" / "today" etc.
            if any(w in name.lower().split() for w in ("has", "including", "today", "get", "find", "with", "their")):
                continue
            # Must look like a firm name: ends with a VC suffix OR is a known VC
            if not (name.endswith(_VC_SUFFIXES) or name in _KNOWN_VC):
                continue
            clean_names.add(name)

        if clean_names:
            report += "### VC Firms\n"
            for name in sorted(clean_names)[:15]:
                report += f"- **{name}**\n"
            report += "\n"

    # Crunchbase section (kept as-is)
    if cb_firms:
        report += "### Crunchbase ΓÇö VC Firms in this Space\n"
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

    # Web search results (kept as-is)
    if unique_results:
        report += "### Web Search ΓÇö Investors & Funding Activity\n"
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

    if max_chars and len(report) > max_chars:
        report = report[: max_chars - 60] + "\n\nΓÇª (truncated for brevity)"

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
    parser.add_argument("--no-truncate", action="store_true", help="Disable output truncation")

    args = parser.parse_args()

    print(f"Searching VCs for: {args.market}\n")

    report = find_vcs(
        market=args.market,
        idea_name=args.name,
        idea_content=args.desc,
        pain_point=args.pain_point,
        max_results=args.max_results,
        max_deep_scrape=args.deep,
        max_chars=0 if args.no_truncate else 3000,
    )

    print(report)
