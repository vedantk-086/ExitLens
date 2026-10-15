"""Command line entry point for LinkWatch."""
import sys
import click
from colorama import Fore, Style, init as colorama_init
from linkwatch.crawler import LinkCrawler

colorama_init(autoreset=True)

@click.command()
@click.argument("target_url")
def main(target_url: str) -> None:
    crawler = LinkCrawler()
    try:
        html = crawler.fetch_page(target_url)
        links = crawler.extract_links(html)
        print(f"{Fore.GREEN}Discovered {len(links)} links on {target_url}{Style.RESET_ALL}")
    except Exception as exc:
        print(f"{Fore.RED}Error crawling {target_url}: {exc}{Style.RESET_ALL}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
