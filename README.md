# Tech Watch

An automated daily pipeline that searches the web for fresh Data & AI articles, scores them by relevance, stores them in Supabase, and sends you a formatted email digest.

## What It Does

1. **Search** — Queries Brave News API + 28 RSS feeds for articles published in the last 24h
2. **Summarize & Score** — Fetches full article text with trafilatura, sends batches to Gemini API for 1–10 relevance scoring and 2-3 sentence summaries
3. **Store** — Saves new articles to Supabase (deduplication by URL)
4. **Email** — Sends a formatted HTML digest via Gmail

## Tech Stack

| Component | Tool |
|-----------|------|
| Search | Brave News API + RSS (feedparser) |
| Summarization | Google Gemini API (`gemini-2.5-flash`) |
| Storage | Supabase (PostgreSQL) |
| Email | Gmail API (OAuth2) |
| Language filter | langdetect (EN + FR) |
| Full text extraction | trafilatura |

---

## Setup

### 1. Clone and install

```bash
git clone <your-repo>
cd data-technos
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

### 2. Create your `.env` file

Copy the template and fill in your secrets:

```bash
cp .env.example .env
```

```env
GEMINI_API_KEY=...
BRAVE_API_KEY=...
SUPABASE_URL=...
SUPABASE_KEY=...
GMAIL_CLIENT_ID=...
GMAIL_CLIENT_SECRET=...
GMAIL_REFRESH_TOKEN=...
GMAIL_SENDER_EMAIL=your@gmail.com
```

### 3. Set up Supabase

Create a table called `articles` in your Supabase project with this schema:

| Column | Type | Notes |
|--------|------|-------|
| `article_id` | uuid | Primary key, default `gen_random_uuid()` |
| `title` | text | |
| `url` | text | Unique — used for deduplication |
| `source` | text | Domain/publication name |
| `published_date` | text | |
| `summary` | text | Gemini-generated summary |
| `relevance_score` | int2 | 1–10 |
| `topics` | text | Comma-separated topic tags |
| `sent` | bool | True once included in a digest |
| `origin` | text | `"brave"` or `"rss"` |
| `created_at` | timestamptz | |

### 4. Set up Gmail OAuth2

You need a Google Cloud project with the Gmail API enabled.

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project → Enable **Gmail API**
3. Create **OAuth 2.0 credentials** (Desktop app type)
4. Add your Gmail address as a test user (OAuth consent screen → Audience)
5. Run the one-time auth flow to get your refresh token:

```bash
python scripts/get_gmail_token.py
```

Copy the printed `refresh_token` into your `.env`.

### 5. Get API keys

- **Brave Search**: [brave.com/search/api](https://brave.com/search/api) — free tier, 2000 queries/month
- **Gemini**: [aistudio.google.com](https://aistudio.google.com) → Get API key — free tier, 20 requests/day for `gemini-2.5-flash`

---

## Running

```bash
# Full run (search + summarize + store + email)
python -m tech_watch.main

# Dry run (search + summarize only, no DB write, no email)
python -m tech_watch.main --dry-run

# Verbose logging
python -m tech_watch.main --debug
```

## Scheduling (daily at 8am)

```bash
crontab -e
```

Add:
```cron
0 8 * * * cd /path/to/data-technos && source .venv/bin/activate && python -m tech_watch.main >> logs/tech_watch.log 2>&1
```

Create the logs directory first: `mkdir -p logs`

---

## Configuration

All non-secret settings are in [src/tech_watch/config.py](src/tech_watch/config.py):

| Setting | Default | Description |
|---------|---------|-------------|
| `TOPICS` | 20 topics | Search queries sent to Brave |
| `RSS_FEEDS` | 28 feeds | RSS sources (Medium, TDS, Substacks, etc.) |
| `MIN_RELEVANCE_SCORE` | 6 | Minimum score (1–10) to keep an article |
| `MAX_ARTICLES_IN_DIGEST` | 20 | Max articles in the email |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model to use |
| `DIGEST_RECIPIENTS` | your email | Who receives the digest |

---

## Project Structure

```
data-technos/
├── src/tech_watch/
│   ├── main.py          # Pipeline entry point
│   ├── config.py        # Non-secret configuration
│   ├── searcher.py      # Brave + RSS article search
│   ├── summarizer.py    # Gemini summarization & scoring
│   ├── storage.py       # Supabase storage & deduplication
│   └── email_sender.py  # Gmail digest email
├── tests/
│   ├── test_searcher.py
│   ├── test_summarizer.py
│   └── test_storage.py
├── pyproject.toml
├── requirements.txt
├── .env                 # Secrets (never commit)
└── .env.example         # Template
```

## Running Tests

```bash
pytest tests/ -v
```

---

## Known Limitations

- **Gemini free tier**: 20 requests/day for `gemini-2.5-flash`. At batch size 20, this handles ~400 articles/day comfortably.
- **Paywalled sites**: Forbes, NYT, PCMag block scrapers. The pipeline falls back to the Brave snippet for scoring — these articles tend to score low anyway.
- **Medium redirect loops**: Some Medium subdomains loop on redirect. Trafilatura catches these and falls back to snippet.
