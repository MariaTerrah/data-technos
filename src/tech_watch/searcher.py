"""
searcher.py — Fetch recent articles from two sources:
  1. Brave News API     → industry news (announcements, releases, company news)
  2. RSS feeds          → blogs & communities (Medium, TDS, dev.to, Substacks...)

Both sources are merged, deduplicated by URL, and language-filtered (EN + FR).
"""

import logging
import os
import time
import feedparser
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional
from dotenv import load_dotenv
from langdetect import detect, LangDetectException
from tech_watch.config import TOPICS, MAX_ARTICLES_PER_TOPIC, RSS_FEEDS

load_dotenv()
logger = logging.getLogger(__name__)

BRAVE_API_URL = "https://api.search.brave.com/res/v1/news/search"
ALLOWED_LANGUAGES = {"en", "fr"}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def search_articles(topics: list[str] = TOPICS) -> list[dict]:
    """
    Fetch articles from Brave News API + RSS feeds.
    Returns a combined, deduplicated, language-filtered list.
    """
    seen_urls: set[str] = set()
    all_articles: list[dict] = []

    # --- Source 1: Brave News API ---
    brave_articles = _search_brave(topics, seen_urls)
    all_articles.extend(brave_articles)
    logger.info(f"Brave: {len(brave_articles)} articles")

    # --- Source 2: RSS feeds ---
    rss_articles = _search_rss(seen_urls)
    all_articles.extend(rss_articles)
    logger.info(f"RSS: {len(rss_articles)} articles")

    logger.info(f"Total: {len(all_articles)} unique articles")
    return all_articles


# ---------------------------------------------------------------------------
# Source 1: Brave News API
# ---------------------------------------------------------------------------

def _search_brave(topics: list[str], seen_urls: set[str]) -> list[dict]:
    """Search Brave News API for each topic."""
    api_key = os.getenv("BRAVE_API_KEY")
    if not api_key:
        logger.warning("BRAVE_API_KEY missing — skipping Brave search")
        return []

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    }

    articles = []
    for topic in topics:
        logger.info(f"Brave search: {topic}")
        try:
            params = {
                "q": topic,
                "count": MAX_ARTICLES_PER_TOPIC,
                "freshness": "pd",       # past day (24h)
                "text_decorations": 0,
                "country": "all",
            }
            response = requests.get(BRAVE_API_URL, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            for r in data.get("results", []):
                url = _normalize_url(r.get("url", ""))
                if not url or url in seen_urls:
                    continue
                text = f"{r.get('title', '')} {r.get('description', '')}".strip()
                if not _is_allowed_language(text):
                    continue
                seen_urls.add(url)
                articles.append({
                    "title":    r.get("title", "").strip(),
                    "url":      url,
                    "snippet":  r.get("description", "").strip(),
                    "source":   r.get("meta_url", {}).get("hostname", "").strip(),
                    "published": r.get("age", None),
                    "topic":    topic,
                    "origin":   "brave",
                })

            time.sleep(0.5)  # stay within Brave's 1 req/sec rate limit

        except requests.HTTPError as e:
            logger.warning(f"Brave API error for '{topic}': {e.response.status_code}")
        except Exception as e:
            logger.warning(f"Brave search failed for '{topic}': {e}")

    return articles


# ---------------------------------------------------------------------------
# Source 2: RSS feeds
# ---------------------------------------------------------------------------

def _search_rss(seen_urls: set[str]) -> list[dict]:
    """Read all RSS feeds and return articles published in the last 24 hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    articles = []

    for feed_url in RSS_FEEDS:
        logger.info(f"RSS: {feed_url}")
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                url = _normalize_url(entry.get("link", ""))
                if not url or url in seen_urls:
                    continue

                # Strict date filter — skip if no date or older than 24h
                published = _parse_rss_date(entry)
                if not published or published < cutoff:
                    continue

                # Language filter
                title = entry.get("title", "").strip()
                snippet = _extract_rss_snippet(entry)
                text = f"{title} {snippet}".strip()
                if not _is_allowed_language(text):
                    continue

                seen_urls.add(url)
                articles.append({
                    "title":    title,
                    "url":      url,
                    "snippet":  snippet,
                    "source":   feed.feed.get("title", feed_url),
                    "published": str(published) if published else None,
                    "topic":    "rss",
                    "origin":   "rss",
                })

        except Exception as e:
            logger.warning(f"RSS feed failed ({feed_url}): {e}")

    return articles


def _parse_rss_date(entry) -> Optional[datetime]:
    """Parse the published date from an RSS entry."""
    try:
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
            return datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
    except Exception:
        pass
    return None


def _extract_rss_snippet(entry) -> str:
    """Extract a clean short snippet from an RSS entry."""
    # Try summary first, then content
    text = entry.get("summary", "") or ""
    if not text and hasattr(entry, "content"):
        text = entry.content[0].get("value", "")
    # Strip HTML tags simply
    import re
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:300]  # keep it short — trafilatura will fetch the full text later


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_url(url: str) -> str:
    """Strip trailing slashes for consistent deduplication."""
    return url.rstrip("/").strip()


def _is_allowed_language(text: str) -> bool:
    """Return True if the text is detected as English or French."""
    if not text:
        return True
    try:
        return detect(text) in ALLOWED_LANGUAGES
    except LangDetectException:
        return True


# ---------------------------------------------------------------------------
# Run directly for testing: python searcher.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s — %(message)s")
    articles = search_articles(["dbt data build tool", "BigQuery"])
    brave = [a for a in articles if a["origin"] == "brave"]
    rss   = [a for a in articles if a["origin"] == "rss"]
    print(f"\nTotal: {len(articles)} articles  (Brave: {len(brave)}, RSS: {len(rss)})\n")
    for a in articles[:10]:
        print(f"[{a['origin']}] {a['title'][:70]}")
        print(f"         {a['source']}\n")
