# Tech Watch System — Claude Code Project Guide

## What This Project Does

An automated daily tech watch pipeline that:
1. Searches the web for fresh articles on Data & AI topics (last 24h)
2. Filters and ranks them by relevance using Gemini API
3. Stores articles + summaries in Supabase (deduplication included)
4. Sends a formatted daily digest email via Gmail

## Project Structure

```
data-technos/
├── src/tech_watch/
│   ├── main.py          # Entry point — orchestrates the full pipeline
│   ├── config.py        # Non-secret config: topics, RSS feeds, thresholds
│   ├── searcher.py      # Fetch articles via Brave News API + RSS feeds
│   ├── summarizer.py    # Summarize & score articles via Gemini API
│   ├── storage.py       # Supabase: store articles, check duplicates
│   └── email_sender.py  # Gmail API: format & send daily digest
├── tests/
│   ├── test_searcher.py
│   ├── test_summarizer.py
│   └── test_storage.py
├── logs/                # Cron log output (gitignored)
├── pyproject.toml
├── requirements.txt
├── .env                 # Secrets (never commit this)
├── .env.example         # Template for required secrets
├── README.md            # Full setup instructions
└── CLAUDE.md            # This file
```

## Tech Stack

| Component | Tool | Notes |
|-----------|------|-------|
| Search | Brave News API | 20 topic queries, last 24h |
| Search | RSS feeds (feedparser) | 28 sources |
| Language filter | langdetect | EN + FR only |
| Full text extraction | trafilatura | Falls back to snippet on 403 |
| Summarization | Google Gemini API (`gemini-2.5-flash`) | Scores 1-10, generates summaries |
| Storage | Supabase (PostgreSQL) | Deduplication by URL |
| Email | Gmail API (OAuth2) | HTML + plain text digest |

## Pipeline Flow

```
main.py
  └─> searcher.py      # search_articles() → raw article list (Brave + RSS, deduplicated)
  └─> summarizer.py    # filter_and_summarize() → enriched articles (score ≥ MIN_RELEVANCE_SCORE)
  └─> storage.py       # save_articles() → new articles only (URL deduplication)
  └─> email_sender.py  # send_digest() → top MAX_ARTICLES_IN_DIGEST articles by score
```

## Key Design Decisions

- **Deduplication**: Supabase is the source of truth. Before storing, each article URL is checked against existing records.
- **Relevance filtering**: Gemini scores each article 1–10. Only articles scoring ≥ `MIN_RELEVANCE_SCORE` (default 6) are stored.
- **24h window**: Brave appends a date filter to queries. RSS applies a strict 24h cutoff (articles with no date are dropped).
- **Full text fetching**: trafilatura fetches full article text before scoring. Falls back to Brave snippet on paywalled/blocked sites.
- **Batch size 20**: Gemini free tier allows 20 requests/day for `gemini-2.5-flash`. Batching 20 articles per call keeps usage at ~11 calls/day for ~200 articles.
- **No secrets in code**: All API keys live in `.env`.

## Topics Covered (configured in config.py)

Data Engineering, Analytics Engineering, dbt, BigQuery, Apache Airflow, GCP, Fivetran,
Snowflake, Databricks, Looker, Data Visualization, Business Intelligence,
AI applied to Data Engineering, LLM + SQL, AI Agents, RAG, MLOps,
Data Governance, Data Contracts.

## Running the Pipeline

```bash
# One-off full run
python -m tech_watch.main

# Dry run (search + summarize only, no Supabase write, no email)
python -m tech_watch.main --dry-run

# Debug mode (verbose logs)
python -m tech_watch.main --debug
```

## Scheduling

Runs daily via cron (set up on Maria's Mac):
```cron
0 8 * * * cd /path/to/data-technos && python -m tech_watch.main >> logs/tech_watch.log 2>&1
```

## Supabase Schema

Table name: `articles`

| Column | Type | Notes |
|--------|------|-------|
| `article_id` | uuid | Primary key |
| `title` | text | Truncated to 500 chars |
| `url` | text | Used for deduplication (normalized) |
| `source` | text | Domain/publication |
| `published_date` | text | When the article was published |
| `summary` | text | Gemini-generated summary |
| `relevance_score` | int2 | 1–10 score from Gemini |
| `topics` | text | Comma-separated topic tags |
| `sent` | bool | True once included in a digest email |
| `origin` | text | `"brave"` or `"rss"` |
| `created_at` | timestamptz | When we added this record |

## Gemini API Usage

- Model: `gemini-2.5-flash` (free tier: 20 requests/day)
- Batch size: 20 articles per call (~11 calls/day for ~200 articles)
- Task: Given article titles + full text (or snippet fallback), Gemini returns JSON with summaries, scores, and topic tags
- Prompt lives in `summarizer.py` — edit there to tune scoring behavior
- `GEMINI_MAX_TOKENS = 16384` to avoid truncated JSON with 20-article batches

## Common Issues & Fixes

- **429 RESOURCE_EXHAUSTED (daily quota)**: Free tier limit hit — wait until midnight Pacific for reset
- **429 RESOURCE_EXHAUSTED (per-minute)**: Rate limit — pipeline has 7s delay between batches + 20s retry
- **Unterminated JSON string**: `GEMINI_MAX_TOKENS` too low — currently set to 16384
- **Gmail auth expired**: Re-run the OAuth flow to get a new refresh token (see README)
- **Too few articles**: Lower `MIN_RELEVANCE_SCORE` in config.py or add more topics/RSS feeds
- **403 on article fetch**: Site blocks scrapers — trafilatura falls back to snippet automatically
