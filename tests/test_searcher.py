"""
Unit tests for searcher.py

Tests pure logic functions — no real API calls made.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
from tech_watch.searcher import _normalize_url, _is_allowed_language, _parse_rss_date, _extract_rss_snippet


class TestNormalizeUrl:
    def test_strips_trailing_slash(self):
        assert _normalize_url("https://example.com/article/") == "https://example.com/article"

    def test_strips_whitespace(self):
        assert _normalize_url("  https://example.com  ") == "https://example.com"

    def test_no_change_when_clean(self):
        assert _normalize_url("https://example.com/article") == "https://example.com/article"

    def test_empty_string(self):
        assert _normalize_url("") == ""


class TestIsAllowedLanguage:
    def test_english_text_allowed(self):
        assert _is_allowed_language("This is an article about data engineering with dbt and BigQuery") is True

    def test_french_text_allowed(self):
        assert _is_allowed_language("Cet article parle de l'ingénierie des données et des outils modernes") is True

    def test_german_text_rejected(self):
        assert _is_allowed_language("Dies ist ein Artikel über Datentechnik und maschinelles Lernen") is False

    def test_empty_text_allowed(self):
        # Empty text → no detection possible → keep article (safe default)
        assert _is_allowed_language("") is True

    def test_very_short_text_allowed(self):
        # langdetect may or may not detect very short text — just verify it doesn't crash
        result = _is_allowed_language("ok")
        assert isinstance(result, bool)


class TestParseRssDate:
    def test_returns_datetime_from_published_parsed(self):
        entry = MagicMock()
        entry.published_parsed = (2026, 4, 1, 10, 0, 0, 0, 0, 0)
        entry.updated_parsed = None
        result = _parse_rss_date(entry)
        assert result == datetime(2026, 4, 1, 10, 0, 0, tzinfo=timezone.utc)

    def test_falls_back_to_updated_parsed(self):
        entry = MagicMock()
        entry.published_parsed = None
        entry.updated_parsed = (2026, 4, 1, 8, 30, 0, 0, 0, 0)
        result = _parse_rss_date(entry)
        assert result == datetime(2026, 4, 1, 8, 30, 0, tzinfo=timezone.utc)

    def test_returns_none_when_both_missing(self):
        entry = MagicMock()
        entry.published_parsed = None
        entry.updated_parsed = None
        result = _parse_rss_date(entry)
        assert result is None

    def test_prefers_published_over_updated(self):
        entry = MagicMock()
        entry.published_parsed = (2026, 4, 1, 10, 0, 0, 0, 0, 0)
        entry.updated_parsed  = (2026, 4, 2, 10, 0, 0, 0, 0, 0)  # newer but should be ignored
        result = _parse_rss_date(entry)
        assert result == datetime(2026, 4, 1, 10, 0, 0, tzinfo=timezone.utc)


class TestExtractRssSnippet:
    def test_extracts_plain_summary(self):
        entry = MagicMock()
        entry.get = lambda key, default="": "A great article about dbt." if key == "summary" else default
        result = _extract_rss_snippet(entry)
        assert result == "A great article about dbt."

    def test_strips_html_tags(self):
        entry = MagicMock()
        entry.get = lambda key, default="": "<p>A great article about <strong>dbt</strong>.</p>" if key == "summary" else default
        result = _extract_rss_snippet(entry)
        assert "<" not in result
        assert "dbt" in result

    def test_truncates_to_300_chars(self):
        entry = MagicMock()
        long_text = "word " * 200  # 1000 chars
        entry.get = lambda key, default="": long_text if key == "summary" else default
        result = _extract_rss_snippet(entry)
        assert len(result) <= 300

    def test_falls_back_to_content(self):
        entry = MagicMock()
        entry.get = lambda key, default="": default  # summary is empty
        entry.content = [{"value": "Fallback content about BigQuery."}]
        result = _extract_rss_snippet(entry)
        assert "BigQuery" in result
