"""
Unit tests for summarizer.py

Tests pure logic functions — no real Gemini API calls made.
"""

import json
from tech_watch.summarizer import _process_batch


class TestProcessBatch:
    """Tests the JSON parsing and merging logic inside _process_batch."""

    def _make_client(self, json_response: str):
        """Create a fake Gemini client that returns a fixed response."""
        from unittest.mock import MagicMock
        client = MagicMock()
        response = MagicMock()
        response.text = json_response
        client.models.generate_content.return_value = response
        return client

    def test_merges_gemini_output_into_articles(self):
        batch = [
            {"title": "dbt 2.0 released", "source": "getdbt.com", "content": "...", "full_text_fetched": True},
            {"title": "Dallas AI leader", "source": "dallasnews.com", "content": "...", "full_text_fetched": False},
        ]
        gemini_response = json.dumps([
            {"index": 0, "relevance_score": 9, "summary": "dbt 2.0 changes everything.", "topics": ["dbt"]},
            {"index": 1, "relevance_score": 2, "summary": "Local business news.", "topics": []},
        ])
        model = self._make_client(gemini_response)
        result = _process_batch(model, batch)

        assert len(result) == 2
        assert result[0]["relevance_score"] == 9
        assert result[0]["summary"] == "dbt 2.0 changes everything."
        assert result[0]["topics"] == ["dbt"]
        assert result[1]["relevance_score"] == 2

    def test_strips_markdown_code_fences(self):
        batch = [
            {"title": "BigQuery update", "source": "google.com", "content": "...", "full_text_fetched": True},
        ]
        gemini_response = "```json\n" + json.dumps([
            {"index": 0, "relevance_score": 8, "summary": "BigQuery gets new features.", "topics": ["BigQuery"]}
        ]) + "\n```"
        model = self._make_client(gemini_response)
        result = _process_batch(model, batch)

        assert len(result) == 1
        assert result[0]["relevance_score"] == 8

    def test_skips_invalid_index(self):
        batch = [
            {"title": "Article A", "source": "source.com", "content": "...", "full_text_fetched": True},
        ]
        gemini_response = json.dumps([
            {"index": 99, "relevance_score": 9, "summary": "Should be skipped.", "topics": []},
        ])
        model = self._make_client(gemini_response)
        result = _process_batch(model, batch)
        assert result == []

    def test_original_article_fields_preserved(self):
        batch = [
            {"title": "Airflow 3.0", "url": "https://airflow.apache.org", "source": "apache.org",
             "content": "...", "full_text_fetched": True, "origin": "rss"},
        ]
        gemini_response = json.dumps([
            {"index": 0, "relevance_score": 7, "summary": "Airflow 3.0 released.", "topics": ["Airflow"]},
        ])
        model = self._make_client(gemini_response)
        result = _process_batch(model, batch)

        assert result[0]["url"] == "https://airflow.apache.org"
        assert result[0]["origin"] == "rss"
        assert result[0]["title"] == "Airflow 3.0"
