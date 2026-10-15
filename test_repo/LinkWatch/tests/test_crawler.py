"""Unit tests for link crawler."""
import pytest
from linkwatch.crawler import LinkCrawler

def test_extract_links_basic():
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        pytest.skip("beautifulsoup4 not installed in test environment")
    html = '<html><body><a href="https://example.com/one">1</a><a href="https://example.com/two">2</a></body></html>'
    crawler = LinkCrawler()
    links = crawler.extract_links(html)
    assert links == ["https://example.com/one", "https://example.com/two"]

def test_extract_links_skips_internal_anchors():
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        pytest.skip("beautifulsoup4 not installed in test environment")
    html = '<html><body><a href="#section">anchor</a><a href="http://external.org">ext</a></body></html>'
    crawler = LinkCrawler()
    links = crawler.extract_links(html)
    assert links == ["http://external.org"]
