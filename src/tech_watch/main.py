"""
main.py — Entry point for the Tech Watch pipeline.

Run modes:
  python -m tech_watch.main           # full run
  python -m tech_watch.main --dry-run # search + summarize only, no DB write, no email
  python -m tech_watch.main --debug   # verbose logging
"""

import argparse
import logging
import sys
from tech_watch.searcher import search_articles
from tech_watch.summarizer import filter_and_summarize
from tech_watch.storage import save_articles, mark_as_sent
from tech_watch.config import LOG_LEVEL


def main():
    parser = argparse.ArgumentParser(description="Tech Watch daily pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Search + summarize only, no DB write, no email")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else getattr(logging, LOG_LEVEL)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s [%(module)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger(__name__)

    logger.info("=== Tech Watch pipeline starting ===")

    # Step 1 — Search
    logger.info("Step 1: Searching for articles...")
    articles = search_articles()
    logger.info(f"Found {len(articles)} articles total")

    if not articles:
        logger.warning("No articles found — exiting")
        sys.exit(0)

    # Step 2 — Summarize & score
    logger.info("Step 2: Summarizing and scoring articles...")
    enriched = filter_and_summarize(articles)
    logger.info(f"{len(enriched)} articles passed relevance filter")

    if not enriched:
        logger.warning("No relevant articles found — exiting")
        sys.exit(0)

    if args.dry_run:
        logger.info("Dry run — skipping storage and email")
        for a in enriched[:5]:
            logger.info(f"  [{a['relevance_score']}] {a['title']}")
        sys.exit(0)

    # Step 3 — Store
    logger.info("Step 3: Saving articles to Supabase...")
    new_articles = save_articles(enriched)
    logger.info(f"{len(new_articles)} new articles saved")

    if not new_articles:
        logger.info("No new articles to send — exiting")
        sys.exit(0)

    # Step 4 — Email
    logger.info("Step 4: Sending email digest...")
    from tech_watch.email_sender import send_digest
    send_digest(new_articles)
    mark_as_sent(new_articles)
    logger.info("Digest sent and articles marked as sent")

    logger.info("=== Pipeline complete ===")


if __name__ == "__main__":
    main()
