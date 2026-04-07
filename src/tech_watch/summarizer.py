"""
summarizer.py — Fetch full article text, then score and summarize using Gemini.

Pipeline per article:
  1. Fetch the full page with trafilatura (free article text extractor)
  2. If blocked / paywalled, fall back to the snippet from Brave
  3. Send batches of articles to Gemini for scoring + summarization
  4. Return only articles scoring >= MIN_RELEVANCE_SCORE
"""

import json
import logging
import os
import time
import trafilatura
from google import genai
from google.genai import types
from dotenv import load_dotenv
from tech_watch.config import MIN_RELEVANCE_SCORE, GEMINI_MAX_TOKENS, GEMINI_MODEL

load_dotenv()
logger = logging.getLogger(__name__)

# How many articles to send to Gemini in one API call
BATCH_SIZE = 20

# Max characters of article text to send to Gemini (to stay within token limits)
MAX_ARTICLE_CHARS = 3000

# Seconds to wait between batches — free tier allows 10 RPM, so 7s gives ~8.5 RPM
BATCH_DELAY_SECONDS = 7


def filter_and_summarize(articles: list[dict]) -> list[dict]:
    """
    Fetch full text, score and summarize a list of raw articles.

    Returns a filtered list (score >= MIN_RELEVANCE_SCORE), each enriched with:
        - summary          (str)   2-3 sentence summary
        - relevance_score  (int)   1–10
        - topics           (list)  matched topic tags
        - full_text_fetched (bool) whether full text was successfully retrieved
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing from .env")

    client = genai.Client(api_key=api_key)

    # Step 1: fetch full text for every article
    logger.info(f"Fetching full text for {len(articles)} articles...")
    for article in articles:
        article["content"], article["full_text_fetched"] = _fetch_full_text(article)

    # Step 2: send to Gemini in batches
    enriched: list[dict] = []
    for i in range(0, len(articles), BATCH_SIZE):
        batch = articles[i: i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        logger.info(f"Summarizing batch {batch_num} ({len(batch)} articles)")
        try:
            results = _process_batch(client, batch)
            enriched.extend(results)
        except Exception as e:
            logger.warning(f"Batch {batch_num} failed: {e}")
            continue
        # Respect the free-tier rate limit (15 RPM) between batches
        if i + BATCH_SIZE < len(articles):
            time.sleep(BATCH_DELAY_SECONDS)

    # Step 3: filter by relevance score and sort best first
    filtered = [a for a in enriched if a.get("relevance_score", 0) >= MIN_RELEVANCE_SCORE]
    filtered.sort(key=lambda a: a["relevance_score"], reverse=True)

    logger.info(f"{len(filtered)} articles passed the relevance filter (score >= {MIN_RELEVANCE_SCORE})")
    return filtered


def _fetch_full_text(article: dict) -> tuple[str, bool]:
    """
    Attempt to fetch the full article text from its URL using trafilatura.

    Returns:
        (text, True)  if full text was successfully extracted
        (snippet, False) if blocked / paywalled / failed — falls back to snippet
    """
    try:
        downloaded = trafilatura.fetch_url(
            article["url"],
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
        )
        if downloaded:
            text = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=False,
                no_fallback=False,
            )
            if text and len(text) > 200:  # sanity check: at least 200 chars
                logger.debug(f"Full text fetched: {article['url']}")
                # Truncate to avoid sending too many tokens to Gemini
                return text[:MAX_ARTICLE_CHARS], True

    except Exception as e:
        logger.debug(f"Could not fetch full text for {article['url']}: {e}")

    # Fall back to snippet from Brave
    logger.debug(f"Using snippet fallback for: {article['url']}")
    return article.get("snippet", ""), False


def _process_batch(client: genai.Client, batch: list[dict]) -> list[dict]:
    """Send a batch of articles to Gemini and return enriched results.

    Retries once on 429 (rate limit) after the suggested retry delay.
    """
    prompt = _build_prompt(batch)
    for attempt in range(2):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=GEMINI_MAX_TOKENS,
                    temperature=0.2,
                ),
            )
            break
        except Exception as e:
            if attempt == 0 and "429" in str(e):
                logger.warning("Rate limit hit — waiting 20s before retry")
                time.sleep(20)
            else:
                raise
    raw = response.text.strip()

    # Gemini sometimes wraps JSON in markdown code blocks — strip them
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    parsed = json.loads(raw)

    # Merge Gemini output back into original article dicts
    enriched = []
    for item in parsed:
        idx = item.get("index")
        if idx is None or idx >= len(batch):
            continue
        article = batch[idx].copy()
        article["summary"] = item.get("summary", "")
        article["relevance_score"] = int(item.get("relevance_score", 0))
        article["topics"] = item.get("topics", [])
        enriched.append(article)

    return enriched


def _build_prompt(batch: list[dict]) -> str:
    """Build the Gemini prompt for a batch of articles."""
    articles_text = ""
    for i, article in enumerate(batch):
        source_quality = "FULL ARTICLE TEXT" if article.get("full_text_fetched") else "SNIPPET ONLY"
        articles_text += f"""
[{i}] ({source_quality})
Title: {article['title']}
Source: {article['source']}
Content: {article['content']}
---"""

    return f"""You are a tech news curator for a Data Engineer / Analytics Engineer working with:
BigQuery, dbt, Apache Airflow, Google Cloud Platform, Fivetran, Looker, Python, SQL.
They are also interested in: data analytics broadly, AI applied to data engineering,data analytics, LLMs, AI based skills and BI tools.

For each article below, evaluate its relevance and return a JSON array.

Scoring rules:
- 9-10: Directly about their daily stack (dbt, BigQuery, Airflow, GCP, Fivetran, Looker) or AI applied to data
- 7-8: Closely related field (data engineering practices, analytics engineering, LLMs, MLOps)
- 5-6: Broadly interesting (data governance, BI trends, cloud data platforms)
- 1-4: Not relevant (generic tech news, unrelated domains, marketing fluff)
- Articles marked SNIPPET ONLY may have lower confidence scores — reflect that uncertainty

Return ONLY a valid JSON array, no explanation, no markdown. Format:
[
  {{
    "index": 0,
    "relevance_score": 8,
    "summary": "2-3 sentences in the same language as the article (English or French)",
    "topics": ["dbt", "data engineering"]
  }},
  ...
]

Valid topic tags: [dbt, BigQuery, Snowflake, Databricks, Airflow, Fivetran, Looker, GCP, SQL, Python, data engineering, analytics engineering, data analytics, LLMs, AI agents, RAG, MLOps, data governance, data contracts, BI, data visualization, streaming]

Articles:
{articles_text}"""
