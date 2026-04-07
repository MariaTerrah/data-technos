"""
Non-secret configuration for the Tech Watch pipeline.
Edit this file to tune topics, thresholds, and preferences.
Secrets (API keys, tokens) go in .env — never here.
"""

# ---------------------------------------------------------------------------
# Search topics
# Each entry becomes a distinct search query (appended with a recency filter).
# ---------------------------------------------------------------------------
TOPICS = [
    # Broad fields (your core domain)
    "data engineering",
    "data analytics",
    "analytics engineering",

    # Your daily stack
    "dbt data build tool",
    "BigQuery",
    "Apache Airflow",
    "Google Cloud Platform data",
    "Fivetran",

    # Industry awareness
    "Snowflake",
    "Databricks",

    # BI & Visualization
    "Looker",
    "data visualization",
    "business intelligence",

    # AI applied to data (your interest)
    "AI data engineering",
    "LLM SQL analytics",
    "AI agents data",
    "RAG vector database",
    "MLOps",

    # Practices
    "data governance",
    "data contracts",
]

# Max articles to fetch per topic query (Brave only)
MAX_ARTICLES_PER_TOPIC = 5

# ---------------------------------------------------------------------------
# RSS feed sources
# Add or remove feeds here — no need to touch searcher.py
# ---------------------------------------------------------------------------
RSS_FEEDS = [
    # --- Data Engineering & Analytics ---
    "https://medium.com/feed/tag/data-engineering",
    "https://medium.com/feed/tag/analytics-engineering",
    "https://medium.com/feed/tag/dataengineering",
    "https://towardsdatascience.com/feed",
    "https://dev.to/feed/tag/dataengineering",
    "https://dev.to/feed/tag/analytics",
    "https://blog.getdbt.com/rss/",
    "https://dataengineeringweekly.substack.com/feed",
    "https://seattledataguy.substack.com/feed",
    "https://benn.substack.com/feed",

    # --- Your Stack (GCP, Airflow, BigQuery, Fivetran) ---
    "https://www.astronomer.io/blog/rss.xml",
    "https://cloud.google.com/blog/rss/",
    "https://www.fivetran.com/blog/rss.xml",

    # --- AI & LLMs ---
    "https://medium.com/feed/tag/llm",
    "https://medium.com/feed/tag/large-language-models",
    "https://medium.com/feed/tag/artificial-intelligence",
    "https://dev.to/feed/tag/ai",
    "https://dev.to/feed/tag/machinelearning",
    "https://thesequence.substack.com/feed",
    "https://magazine.sebastianraschka.com/feed",
    "https://lastweekinai.substack.com/feed",
    "https://aitidbits.substack.com/feed",

    # --- AI applied to Data ---
    "https://medium.com/feed/tag/mlops",
    "https://medium.com/feed/tag/ai-agents",
    "https://thedataexchange.media/feed",
    "https://mlops.community/feed",

    # --- BI & Visualization ---
    "https://medium.com/feed/tag/data-visualization",
    "https://medium.com/feed/tag/business-intelligence",
]

# ---------------------------------------------------------------------------
# Relevance filtering
# Claude scores each article 1–10. Only articles at or above this threshold
# are kept and stored.
# ---------------------------------------------------------------------------
MIN_RELEVANCE_SCORE = 6

# Max articles to include in the daily email digest
MAX_ARTICLES_IN_DIGEST = 20

# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------
SUPABASE_TABLE_NAME = "articles"

# ---------------------------------------------------------------------------
# Gemini API
# ---------------------------------------------------------------------------
GEMINI_MODEL = "gemini-2.5-flash"

# Max tokens Gemini can use in its response (16384 for batches of 20 articles with gemini-2.5-flash)
GEMINI_MAX_TOKENS = 16384

# ---------------------------------------------------------------------------
# Email digest
# ---------------------------------------------------------------------------
# Recipient(s) of the daily digest — loaded from .env
import os as _os
DIGEST_RECIPIENTS = [r.strip() for r in _os.getenv("DIGEST_RECIPIENTS", "").split(",") if r.strip()]

# Email subject line (date will be appended automatically)
DIGEST_SUBJECT_PREFIX = "Daily Tech Watch"

# Sender display name
DIGEST_SENDER_NAME = "Tech Watch Bot"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = "INFO"  # DEBUG | INFO | WARNING | ERROR
