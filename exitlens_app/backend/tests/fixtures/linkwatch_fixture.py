"""Realistic LinkWatch-style Python service repository fixture.

Simulates a real-world repository layout matching LinkWatch:
- Multiple manifests: requirements.txt, pyproject.toml, and setup.cfg
- Layered Python packages: linkwatch/cli.py, linkwatch/crawler.py, linkwatch/db.py
- Discovered and unmapped imports
- Deterministic risk patterns (wide constraints, missing lockfile, lock drift)
- Unit and integration tests configured with pytest.ini
"""

from pathlib import Path


def create_linkwatch_fixture_repo(base_dir: Path) -> Path:
    """Construct a full-featured LinkWatch-style repository fixture."""
    repo = base_dir / "LinkWatch"
    repo.mkdir(parents=True, exist_ok=True)

    # 1. Manifests
    (repo / "requirements.txt").write_text(
        "# Core production dependencies\n"
        "requests>=2.20.0\n"
        "beautifulsoup4>=4.9.0\n"
        "urllib3==1.26.15\n"
        "colorama>=0.4.4\n"
        "click>=8.0.0\n",
        encoding="utf-8",
    )

    (repo / "pyproject.toml").write_text(
        '[build-system]\n'
        'requires = ["setuptools>=61.0", "wheel"]\n'
        'build-backend = "setuptools.build_meta"\n\n'
        '[project]\n'
        'name = "linkwatch"\n'
        'version = "0.2.1"\n'
        'description = "Continuous link health verification and dead link monitor."\n'
        'readme = "README.md"\n'
        'requires-python = ">=3.10"\n'
        'dependencies = [\n'
        '    "requests>=2.20.0",\n'
        '    "beautifulsoup4>=4.9.0",\n'
        ']\n\n'
        '[tool.pytest.ini_options]\n'
        'testpaths = ["tests"]\n'
        'python_files = ["test_*.py"]\n',
        encoding="utf-8",
    )

    (repo / "pytest.ini").write_text(
        "[pytest]\n"
        "testpaths = tests\n"
        "python_files = test_*.py\n",
        encoding="utf-8",
    )

    (repo / "README.md").write_text(
        "# LinkWatch\n"
        "Continuous link health monitor and dead link detector.\n",
        encoding="utf-8",
    )

    # 2. Source Tree (linkwatch/)
    pkg_dir = repo / "linkwatch"
    pkg_dir.mkdir(parents=True, exist_ok=True)

    (pkg_dir / "__init__.py").write_text(
        '"""LinkWatch core package."""\n__version__ = "0.2.1"\n',
        encoding="utf-8",
    )

    (pkg_dir / "crawler.py").write_text(
        '"""Web page crawler and link extraction logic."""\n'
        'from typing import List, Set\n'
        'import requests\n'
        'try:\n'
        '    from bs4 import BeautifulSoup\n'
        'except ImportError:\n'
        '    BeautifulSoup = None\n'
        'import urllib3\n\n'
        'urllib3.disable_warnings()\n\n'
        'class LinkCrawler:\n'
        '    def __init__(self, timeout: int = 10) -> None:\n'
        '        self.timeout = timeout\n'
        '        self.session = requests.Session()\n\n'
        '    def fetch_page(self, url: str) -> str:\n'
        '        response = self.session.get(url, timeout=self.timeout)\n'
        '        response.raise_for_status()\n'
        '        return response.text\n\n'
        '    def extract_links(self, html: str) -> List[str]:\n'
        '        if BeautifulSoup is None:\n'
        '            return []\n'
        '        soup = BeautifulSoup(html, "html.parser")\n'
        '        links: Set[str] = set()\n'
        '        for a in soup.find_all("a", href=True):\n'
        '            href = a["href"].strip()\n'
        '            if href.startswith("http"):\n'
        '                links.add(href)\n'
        '        return sorted(list(links))\n',
        encoding="utf-8",
    )

    (pkg_dir / "cli.py").write_text(
        '"""Command line entry point for LinkWatch."""\n'
        'import sys\n'
        'import click\n'
        'from colorama import Fore, Style, init as colorama_init\n'
        'from linkwatch.crawler import LinkCrawler\n\n'
        'colorama_init(autoreset=True)\n\n'
        '@click.command()\n'
        '@click.argument("target_url")\n'
        'def main(target_url: str) -> None:\n'
        '    crawler = LinkCrawler()\n'
        '    try:\n'
        '        html = crawler.fetch_page(target_url)\n'
        '        links = crawler.extract_links(html)\n'
        '        print(f"{Fore.GREEN}Discovered {len(links)} links on {target_url}{Style.RESET_ALL}")\n'
        '    except Exception as exc:\n'
        '        print(f"{Fore.RED}Error crawling {target_url}: {exc}{Style.RESET_ALL}", file=sys.stderr)\n'
        '        sys.exit(1)\n\n'
        'if __name__ == "__main__":\n'
        '    main()\n',
        encoding="utf-8",
    )

    # 3. Test Suite (tests/)
    tests_dir = repo / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)

    (tests_dir / "__init__.py").write_text("", encoding="utf-8")

    (tests_dir / "test_crawler.py").write_text(
        '"""Unit tests for link crawler."""\n'
        'import pytest\n'
        'from linkwatch.crawler import LinkCrawler\n\n'
        'def test_extract_links_basic():\n'
        '    try:\n'
        '        from bs4 import BeautifulSoup\n'
        '    except ImportError:\n'
        '        pytest.skip("beautifulsoup4 not installed in test environment")\n'
        '    html = \'<html><body><a href="https://example.com/one">1</a><a href="https://example.com/two">2</a></body></html>\'\n'
        '    crawler = LinkCrawler()\n'
        '    links = crawler.extract_links(html)\n'
        '    assert links == ["https://example.com/one", "https://example.com/two"]\n\n'
        'def test_extract_links_skips_internal_anchors():\n'
        '    try:\n'
        '        from bs4 import BeautifulSoup\n'
        '    except ImportError:\n'
        '        pytest.skip("beautifulsoup4 not installed in test environment")\n'
        '    html = \'<html><body><a href="#section">anchor</a><a href="http://external.org">ext</a></body></html>\'\n'
        '    crawler = LinkCrawler()\n'
        '    links = crawler.extract_links(html)\n'
        '    assert links == ["http://external.org"]\n',
        encoding="utf-8",
    )

    (tests_dir / "test_cli.py").write_text(
        '"""CLI sanity tests."""\n'
        'from click.testing import CliRunner\n'
        'from linkwatch.cli import main\n\n'
        'def test_cli_help():\n'
        '    runner = CliRunner()\n'
        '    res = runner.invoke(main, ["--help"])\n'
        '    assert res.exit_code == 0\n'
        '    assert "TARGET_URL" in res.output\n',
        encoding="utf-8",
    )

    # 4. Git and venv dummy dirs to verify ignore behavior
    git_dir = repo / ".git" / "refs"
    git_dir.mkdir(parents=True, exist_ok=True)
    (git_dir / "head").write_text("dummy", encoding="utf-8")

    venv_dir = repo / ".venv" / "lib"
    venv_dir.mkdir(parents=True, exist_ok=True)
    (venv_dir / "site_package.py").write_text("import ignored_in_venv", encoding="utf-8")

    return repo
