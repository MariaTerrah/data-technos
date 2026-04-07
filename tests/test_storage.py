"""
Unit tests for storage.py

Tests pure logic functions — no real Supabase connection made.
"""

from tech_watch.storage import _build_row, _normalize_url


class TestNormalizeUrl:
    def test_strips_trailing_slash(self):
        assert _normalize_url("https://example.com/article/") == "https://example.com/article"

    def test_strips_whitespace(self):
        assert _normalize_url("  https://example.com  ") == "https://example.com"

    def test_empty_string(self):
        assert _normalize_url("") == ""


class TestBuildRow:
    def _sample_article(self, **overrides):
        article = {
            "title": "How dbt 2.0 changes everything",
            "url": "https://blog.getdbt.com/dbt-2-0/",
            "source": "getdbt.com",
            "published": "2026-04-01",
            "summary": "dbt 2.0 introduces major changes.",
            "relevance_score": 9,
            "topics": ["dbt", "analytics engineering"],
            "origin": "rss",
        }
        article.update(overrides)
        return article

    def test_returns_dict(self):
        row = _build_row(self._sample_article())
        assert isinstance(row, dict)

    def test_url_normalized(self):
        row = _build_row(self._sample_article(url="https://blog.getdbt.com/dbt-2-0/"))
        assert row["url"] == "https://blog.getdbt.com/dbt-2-0"

    def test_topics_list_converted_to_string(self):
        row = _build_row(self._sample_article(topics=["dbt", "BigQuery", "GCP"]))
        assert row["topics"] == "dbt, BigQuery, GCP"

    def test_empty_topics(self):
        row = _build_row(self._sample_article(topics=[]))
        assert row["topics"] == ""

    def test_sent_defaults_to_false(self):
        row = _build_row(self._sample_article())
        assert row["sent"] is False

    def test_title_truncated_to_500_chars(self):
        long_title = "A" * 600
        row = _build_row(self._sample_article(title=long_title))
        assert len(row["title"]) == 500

    def test_published_date_mapped_correctly(self):
        row = _build_row(self._sample_article(published="2026-04-01"))
        assert row["published_date"] == "2026-04-01"

    def test_missing_fields_use_defaults(self):
        row = _build_row({"url": "https://example.com"})
        assert row["title"] == ""
        assert row["summary"] == ""
        assert row["relevance_score"] == 0
        assert row["topics"] == ""
        assert row["origin"] == ""

    def test_created_at_is_set(self):
        row = _build_row(self._sample_article())
        assert row["created_at"] is not None
        assert "2026" in row["created_at"]
