import logging
from google_play_scraper import search, reviews, Sort
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

def get_play_store_complaints(sector: str, max_apps: int = 3, max_reviews: int = 15) -> str:
    """
    Search for apps related to the sector and fetch negative reviews to extract pain points.
    """
    try:
        # Search for apps related to the sector
        app_results = search(sector, n_hits=max_apps)
        if not app_results:
            return "No relevant apps found on the Play Store."

        complaints = []
        for app_info in app_results:
            app_id = app_info['appId']
            app_title = app_info['title']
            try:
                # Fetch recent negative reviews (score 1-3)
                result, _ = reviews(
                    app_id,
                    lang='en',
                    country='us',
                    sort=Sort.MOST_RELEVANT,
                    count=max_reviews * 2 # Fetch more, filter later
                )
                
                app_complaints = [r['content'] for r in result if r['score'] <= 3]
                
                if app_complaints:
                    complaints.append(f"### App: {app_title}")
                    for complaint in app_complaints[:max_reviews]:
                        # clean up newlines for formatting
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

def get_reddit_complaints(sector: str, max_results: int = 5) -> str:
    """
    Search Reddit for discussions and complaints about the given sector using DuckDuckGo.
    """
    try:
        ddgs = DDGS()
        query = f"site:reddit.com/r/startups OR site:reddit.com/r/Entrepreneur {sector} problems OR complaints OR pain points"
        results = list(ddgs.text(query, max_results=max_results))
        
        if not results:
            # Fallback to broader reddit search
            query = f"site:reddit.com {sector} problems OR complaints"
            results = list(ddgs.text(query, max_results=max_results))

        if not results:
            return "No relevant Reddit discussions found."

        reddit_data = []
        for r in results:
            title = r.get('title', '')
            body = r.get('body', '')
            reddit_data.append(f"- **{title}**: {body}")

        return "\n".join(reddit_data)
    except Exception as e:
        logger.error(f"Reddit search failed: {e}")
        return "Failed to fetch Reddit data."

def gather_pain_points(sector: str) -> str:
    """
    Combines Play Store and Reddit complaints into a single report.
    """
    play_store = get_play_store_complaints(sector)
    reddit = get_reddit_complaints(sector)

    report = f"## User Pain Points for '{sector}'\n\n"
    report += "### Google Play Store Complaints\n"
    report += play_store + "\n\n"
    report += "### Reddit Discussions & Complaints\n"
    report += reddit + "\n"

    return report

if __name__ == "__main__":
    # Test script locally
    sector = "fitness app"
    print(gather_pain_points(sector))
