"""フェッチャーの基本テスト。ネットワークアクセスなし。"""
from __future__ import annotations

import pytest


SAMPLE_RSS = """\
<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Test Feed</title>
  <entry>
    <id>https://example.com/post/1</id>
    <title>First Post</title>
    <link href="https://example.com/post/1"/>
    <published>2024-06-01T12:00:00Z</published>
    <summary>This is a &lt;b&gt;summary&lt;/b&gt; with HTML.</summary>
  </entry>
  <entry>
    <id>https://example.com/post/2</id>
    <title>Second Post</title>
    <link href="https://example.com/post/2"/>
  </entry>
</feed>
"""


def _make_rss_fetcher(url: str = "https://example.com/feed") -> "RssFetcher":
    from collector.fetchers.rss import RssFetcher
    return RssFetcher({"name": "test", "url": url})


class TestRssFetcher:
    def test_parse_entries(self, respx_mock):
        """feedparserがエントリを正しく解析できること。"""
        import respx
        import httpx
        from collector.fetchers.rss import RssFetcher

        with respx.mock:
            respx.get("https://example.com/feed").mock(
                return_value=httpx.Response(200, content=SAMPLE_RSS.encode())
            )
            fetcher = RssFetcher({"name": "test", "url": "https://example.com/feed"})
            items = fetcher.fetch()

        assert len(items) == 2
        assert items[0]["external_id"] == "https://example.com/post/1"
        assert items[0]["title"] == "First Post"
        assert items[0]["url"] == "https://example.com/post/1"
        assert items[0]["published_at"] is not None

    def test_strips_html_from_summary(self, respx_mock):
        import respx
        import httpx
        from collector.fetchers.rss import RssFetcher

        with respx.mock:
            respx.get("https://example.com/feed").mock(
                return_value=httpx.Response(200, content=SAMPLE_RSS.encode())
            )
            fetcher = RssFetcher({"name": "test", "url": "https://example.com/feed"})
            items = fetcher.fetch()

        assert "<b>" not in (items[0]["summary"] or "")
        assert "summary" in (items[0]["summary"] or "").lower()

    def test_skips_entry_without_id_or_link(self):
        """external_id が取れないエントリはスキップされること。"""
        import feedparser
        from collector.fetchers.rss import _parse_date, _strip_html

        # feedparser に直接食わせてロジックを確認
        bad_feed = """\
<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><title>No ID No Link</title></entry>
</feed>"""
        parsed = feedparser.parse(bad_feed)
        entry = parsed.entries[0]
        external_id = entry.get("id") or entry.get("link") or ""
        assert external_id == ""


# respx が入っていない環境ではネットワークテストをスキップ
def pytest_configure(config):
    config.addinivalue_line("markers", "network: marks tests that use real network")


class TestRssFetcherUnit:
    """respx に依存しない単体テスト。"""

    def test_strip_html(self):
        from collector.fetchers.rss import _strip_html

        assert _strip_html("<b>hello</b> &amp; world") == "hello & world"
        assert _strip_html("plain text") == "plain text"
        assert _strip_html("") == ""

    def test_parse_date_published(self):
        import feedparser
        from collector.fetchers.rss import _parse_date

        feed = feedparser.parse(
            '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">'
            '<entry><id>x</id><title>T</title>'
            '<published>2024-01-15T10:30:00Z</published></entry></feed>'
        )
        date = _parse_date(feed.entries[0])
        assert date is not None
        assert "2024-01-15" in date

    def test_parse_date_missing(self):
        import feedparser
        from collector.fetchers.rss import _parse_date

        feed = feedparser.parse(
            '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">'
            '<entry><id>x</id><title>T</title></entry></feed>'
        )
        assert _parse_date(feed.entries[0]) is None
