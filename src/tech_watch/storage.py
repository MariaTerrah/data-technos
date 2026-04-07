"""
storage.py — Save articles to Supabase and check for duplicates.

Responsibilities:
  - Filter out articles whose URL already exists in the database (deduplication)
  - Insert new articles into the `articles` table
  - Mark articles as sent after the email digest is dispatched
"""

import logging
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
logger = logging.getLogger(__name__)


def get_client() -> Client:
    """Create and return a Supabase client."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL or SUPABASE_KEY missing from .env")
    return create_client(url, key)


def save_articles(articles: list[dict]) -> list[dict]:
    """
    Save a list of enriched articles to Supabase.

    - Skips articles whose URL already exists (deduplication)
    - Returns only the newly inserted articles

    Each article must have: title, url, source, summary, relevance_score, topics, origin
    """
    if not articles:
        return []

    client = get_client()

    # Fetch all existing URLs in one query
    existing_urls = _get_existing_urls(client)
    logger.info(f"Found {len(existing_urls)} existing URLs in database")

    # Filter out duplicates
    new_articles = [a for a in articles if _normalize_url(a.get("url", "")) not in existing_urls]
    logger.info(f"{len(new_articles)} new articles to insert (skipping {len(articles) - len(new_articles)} duplicates)")

    if not new_articles:
        return []

    # Insert new articles
    rows = [_build_row(article) for article in new_articles]
    try:
        client.table("articles").insert(rows).execute()
        logger.info(f"Inserted {len(rows)} articles into Supabase")
    except Exception as e:
        logger.error(f"Failed to insert articles: {e}")
        raise

    return new_articles


def mark_as_sent(articles: list[dict]) -> None:
    """
    Mark articles as sent in the database after the email digest is dispatched.
    Updates the `sent` field to True for each article URL.
    """
    if not articles:
        return

    client = get_client()
    urls = [_normalize_url(a["url"]) for a in articles]

    try:
        client.table("articles").update({"sent": True}).in_("url", urls).execute()
        logger.info(f"Marked {len(urls)} articles as sent")
    except Exception as e:
        logger.error(f"Failed to mark articles as sent: {e}")
        raise


def _get_existing_urls(client: Client) -> set[str]:
    """Fetch all article URLs already stored in the database."""
    try:
        response = client.table("articles").select("url").execute()
        return {_normalize_url(row["url"]) for row in response.data}
    except Exception as e:
        logger.error(f"Failed to fetch existing URLs: {e}")
        raise


def _build_row(article: dict) -> dict:
    """Convert an article dict into a Supabase table row."""
    return {
        "title":           article.get("title", "")[:500],  # safety truncation
        "url":             _normalize_url(article.get("url", "")),
        "source":          article.get("source", ""),
        "published_date":  article.get("published", None),
        "summary":         article.get("summary", ""),
        "relevance_score": article.get("relevance_score", 0),
        "topics":          ", ".join(article.get("topics", [])),  # list → comma-separated string
        "sent":            False,
        "origin":          article.get("origin", ""),
        "created_at":      datetime.now(timezone.utc).isoformat(),
    }


def _normalize_url(url: str) -> str:
    """Strip trailing slashes for consistent deduplication."""
    return url.rstrip("/").strip()

