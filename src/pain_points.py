import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from google_play_scraper import search, reviews, Sort
from ddgs import DDGS
import requests
import trafilatura

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

REQUEST_TIMEOUT = 8  # seconds – strict cap per HTTP request

def _fetch_page_text(url: str, max_chars: int = 1500) -> str:
    """Download a URL and extract its main text content via trafilatura.
    Returns at most *max_chars* characters. Returns '' on any failure."""
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        if resp.status_code != 200:
            return ""
        text = trafilatura.extract(resp.text, include_comments=False, include_tables=False)
        return (text or "")[:max_chars]
    except Exception:
        return ""


def _ddg_search_snippets(query: str, max_results: int = 5) -> list[dict]:
    """Run a DuckDuckGo text search and return result dicts."""
    try:
        ddgs = DDGS()
        return list(ddgs.text(query, max_results=max_results))
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed for '{query}': {e}")
        return []


def _format_results(results: list[dict], deep_scrape: bool = False) -> str:
    """Turn DDG result dicts into markdown bullet points.
    If *deep_scrape* is True, also fetch the page text for richer content."""
    lines = []
    for r in results:
        title = r.get("title", "")
        body = r.get("body", "")
        href = r.get("href", "")

        extra = ""
        if deep_scrape and href:
            page_text = _fetch_page_text(href, max_chars=800)
            if page_text:
                # Take a meaningful excerpt
                extra = f"\n  > {page_text[:400]}…" if len(page_text) > 400 else f"\n  > {page_text}"

        lines.append(f"- **{title}**: {body}{extra}")
    return "\n".join(lines) if lines else ""

# ---------------------------------------------------------------------------
# Source 1: Google Play Store (existing, refined)
# ---------------------------------------------------------------------------

def get_play_store_complaints(sector: str, max_apps: int = 2, max_reviews: int = 3) -> str:
    """
    Search for apps related to the sector and fetch negative reviews to extract pain points.
    """
    try:
        app_results = search(sector, n_hits=max_apps)
        if not app_results:
            return "No relevant apps found on the Play Store."

        complaints = []
        for app_info in app_results:
            app_id = app_info['appId']
            app_title = app_info['title']
            try:
                result, _ = reviews(
                    app_id,
                    lang='en',
                    country='us',
                    sort=Sort.MOST_RELEVANT,
                    count=max_reviews * 2
                )

                app_complaints = [r['content'] for r in result if r['score'] <= 3]

                if app_complaints:
                    complaints.append(f"#### App: {app_title}")
                    for complaint in app_complaints[:max_reviews]:
                        clean_complaint = complaint.replace('\n', ' ').strip()
                        complaints.append(f"- {clean_complaint}")
            except Exception as e:
                logger.warning(f"Failed to fetch reviews for {app_id}: {e}")
                continue

        if not complaints:
            return "No negative reviews found for apps in this sector."

        return "\n".join(complaints)
    except Exception as e:
        logger.error(f"Play Store scraping failed: {e}")
        return "Failed to fetch Play Store data."

# ---------------------------------------------------------------------------
# Source 2: Reddit (existing, improved queries)
# ---------------------------------------------------------------------------

def get_reddit_complaints(sector: str, max_results: int = 2) -> str:
    """Search Reddit for complaints and pain points via DuckDuckGo."""
    queries = [
        f'site:reddit.com "{sector}" problems OR complaints OR frustrating OR "pain points"',
        f'site:reddit.com "{sector}" worst OR terrible OR broken OR "wish it had"',
    ]
    all_results = []
    for q in queries:
        all_results.extend(_ddg_search_snippets(q, max_results=max_results))
        if len(all_results) >= max_results:
            break

    if not all_results:
        return "No relevant Reddit discussions found."

    # De-duplicate by title
    seen_titles = set()
    unique = []
    for r in all_results:
        t = r.get("title", "")
        if t not in seen_titles:
            seen_titles.add(t)
            unique.append(r)

    return _format_results(unique[:max_results], deep_scrape=False)

# ---------------------------------------------------------------------------
# Source 3: Hacker News
# ---------------------------------------------------------------------------

def get_hackernews_complaints(sector: str, max_results: int = 2) -> str:
    """Search Hacker News for developer/startup community pain points."""
    query = f'site:news.ycombinator.com "{sector}" problems OR challenges OR frustrations'
    results = _ddg_search_snippets(query, max_results=max_results)
    if not results:
        return "No relevant Hacker News discussions found."
    return _format_results(results, deep_scrape=False)

# ---------------------------------------------------------------------------
# Source 4: Product Hunt
# ---------------------------------------------------------------------------

def get_producthunt_complaints(sector: str, max_results: int = 2) -> str:
    """Search Product Hunt for product feedback and feature requests."""
    query = f'site:producthunt.com "{sector}" OR alternatives OR review'
    results = _ddg_search_snippets(query, max_results=max_results)
    if not results:
        return "No relevant Product Hunt discussions found."
    return _format_results(results, deep_scrape=False)

# ---------------------------------------------------------------------------
# Source 5: G2 / Capterra Reviews
# ---------------------------------------------------------------------------

def get_g2_capterra_complaints(sector: str, max_results: int = 2) -> str:
    """Search G2 and Capterra for enterprise/SaaS software review pain points."""
    query = f'(site:g2.com OR site:capterra.com) "{sector}" reviews OR complaints OR cons'
    results = _ddg_search_snippets(query, max_results=max_results)
    if not results:
        # Fallback broader query
        query = f'(site:g2.com OR site:capterra.com) {sector}'
        results = _ddg_search_snippets(query, max_results=max_results)
    if not results:
        return "No relevant G2/Capterra reviews found."
    return _format_results(results, deep_scrape=False)

# ---------------------------------------------------------------------------
# Source 6: Trustpilot
# ---------------------------------------------------------------------------

def get_trustpilot_complaints(sector: str, max_results: int = 2) -> str:
    """Search Trustpilot for consumer-facing service complaints."""
    query = f'site:trustpilot.com "{sector}" reviews'
    results = _ddg_search_snippets(query, max_results=max_results)
    if not results:
        return "No relevant Trustpilot reviews found."
    return _format_results(results, deep_scrape=False)

# ---------------------------------------------------------------------------
# Source 7: Stack Overflow / Dev Forums
# ---------------------------------------------------------------------------

def get_stackoverflow_complaints(sector: str, max_results: int = 2) -> str:
    """Search Stack Overflow for technical pain points and tooling gaps."""
    query = f'site:stackoverflow.com "{sector}" issues OR problems OR error OR alternative'
    results = _ddg_search_snippets(query, max_results=max_results)
    if not results:
        return "No relevant Stack Overflow discussions found."
    return _format_results(results, deep_scrape=False)

# ---------------------------------------------------------------------------
# Source 8: Industry Blogs & News (deep scrape)
# ---------------------------------------------------------------------------

def get_industry_blog_complaints(sector: str, max_results: int = 2) -> str:
    """Search industry blogs and news for market-level pain points and expert opinions.
    This source uses deep scraping to extract article content."""
    query = f'"{sector}" challenges OR problems OR "pain points" OR "biggest issues" 2025 OR 2026'
    results = _ddg_search_snippets(query, max_results=max_results)
    if not results:
        return "No relevant industry articles found."
    # Deep-scrape article content for richer insight
    return _format_results(results, deep_scrape=True)

# ---------------------------------------------------------------------------
# Aggregator: gather_pain_points (runs all sources concurrently)
# ---------------------------------------------------------------------------

# Each entry: (section_title, callable, args)
_SOURCES = [
    ("Google Play Store Complaints",   get_play_store_complaints,   {}),
    ("Reddit Discussions & Complaints", get_reddit_complaints,       {}),
    ("Hacker News Discussions",         get_hackernews_complaints,   {}),
    ("Product Hunt Feedback",           get_producthunt_complaints,  {}),
    ("G2 / Capterra Reviews",           get_g2_capterra_complaints,  {}),
    ("Trustpilot Reviews",              get_trustpilot_complaints,   {}),
    ("Stack Overflow / Dev Forums",     get_stackoverflow_complaints,{}),
    ("Industry Blogs & News",           get_industry_blog_complaints,{}),
]


def gather_pain_points(sector: str) -> str:
    """
    Scrape ALL sources concurrently and return a combined pain-points report.
    Uses ThreadPoolExecutor so total wall-clock time ≈ slowest single source
    (~10-15 s) instead of the sum of all sources.
    """
    results: dict[str, str] = {}

    def _run(title: str, func, kwargs):
        try:
            return title, func(sector, **kwargs)
        except Exception as e:
            logger.error(f"Source '{title}' failed: {e}")
            return title, f"Failed to fetch data from {title}."

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            pool.submit(_run, title, func, kwargs): title
            for title, func, kwargs in _SOURCES
        }
        for future in as_completed(futures):
            title, data = future.result()
            results[title] = data

    # Build the report in source-order (not completion-order)
    report = f"## User Pain Points for '{sector}'\n\n"
    for title, _, _ in _SOURCES:
        report += f"### {title}\n"
        report += results.get(title, "No data.") + "\n\n"

    return report


if __name__ == "__main__":
    # Quick local test
    import time
    sector = "fitness app"
    start = time.time()
    print(gather_pain_points(sector))
    print(f"\n⏱ Completed in {time.time() - start:.1f}s")
