"""Web page crawler and link extraction logic."""
from typing import List, Set
import requests
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None
import urllib3

urllib3.disable_warnings()

class LinkCrawler:
    def __init__(self, timeout: int = 10) -> None:
        self.timeout = timeout
        self.session = requests.Session()

    def fetch_page(self, url: str) -> str:
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.text

    def extract_links(self, html: str) -> List[str]:
        if BeautifulSoup is None:
            return []
        soup = BeautifulSoup(html, "html.parser")
        links: Set[str] = set()
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith("http"):
                links.add(href)
        return sorted(list(links))
