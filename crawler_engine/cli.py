"""Command-line interface: crawl / search / keywords."""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import webbrowser
from pathlib import Path

from crawler_engine.analysis import KeywordAnalyzer, SearchEngine
from crawler_engine.config import CrawlConfig
from crawler_engine.crawler import Crawler
from crawler_engine.exceptions import CrawlerError
from crawler_engine.exporter import (
    CsvExporter, HtmlReportExporter, JsonExporter, SitemapExporter, SqliteExporter,
    load_pages_json, load_result_json,
)
from crawler_engine.utils import setup_logging

log = logging.getLogger("crawler_engine.cli")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="crawler", description="Async web crawler & data extractor")
    p.add_argument("--env-file", default=".env", help="path to .env (default: .env)")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("crawl", help="crawl websites and export datasets")
    c.add_argument("urls", nargs="*", help="seed URLs (falls back to CRAWLER_SEEDS)")
    c.add_argument("-d", "--depth", type=int, dest="max_depth")
    c.add_argument("-m", "--max-pages", type=int)
    c.add_argument("-c", "--concurrency", type=int)
    c.add_argument("--delay", type=float, help="seconds between requests to one host")
    c.add_argument("--timeout", type=float)
    c.add_argument("--retries", type=int)
    c.add_argument("-o", "--output-dir", type=Path)
    c.add_argument("--ignore-robots", action="store_true", help="do not obey robots.txt")
    c.add_argument("--log-level")
    c.add_argument("--open", action="store_true", dest="open_report",
                   help="open the HTML report in your browser when finished")
    c.add_argument("-q", "--query", help="run a keyword search on results right after crawling")

    r = sub.add_parser("report", help="build the HTML report from a saved JSON export")
    r.add_argument("--data", type=Path, default=Path("output/pages.json"))
    r.add_argument("--no-open", action="store_true", help="do not open the browser")

    s = sub.add_parser("search", help="keyword search over a saved JSON export")
    s.add_argument("query")
    s.add_argument("--data", type=Path, default=Path("output/pages.json"))
    s.add_argument("-n", "--limit", type=int, default=10)

    k = sub.add_parser("keywords", help="keyword frequency analysis of a saved JSON export")
    k.add_argument("--data", type=Path, default=Path("output/pages.json"))
    k.add_argument("-n", "--top", type=int, default=20)
    return p


def _print_hits(hits: list) -> None:
    if not hits:
        print("No results.")
    for i, h in enumerate(hits, 1):
        print(f"{i:>2}. [{h.score:>5.0f}] {h.title or '(no title)'}\n    {h.url}\n    {h.snippet}\n")


async def _run_crawl(args: argparse.Namespace, cfg: CrawlConfig) -> int:
    result = await Crawler(cfg).crawl()
    out = cfg.output_dir
    JsonExporter().export(result, out / "pages.json")
    CsvExporter().export(result, out / "pages.csv")
    SqliteExporter().export(result, out / "crawl.db")
    SitemapExporter().export(result, out / "sitemap.xml")
    report = HtmlReportExporter().export(result, out / "report.html")
    print(result.stats.summary())
    print(f" Exports written to: {out.resolve()}")
    print(f" HTML report       : {report.resolve()}")
    if args.open_report:
        webbrowser.open(report.resolve().as_uri())
    if result.failed:
        print("\nFailed URLs:")
        for f in result.failed[:10]:
            print(f"  - {f.url} ({f.reason})")
    if args.query:
        print(f"\nSearch results for '{args.query}':\n")
        _print_hits(SearchEngine(result.pages).search(args.query))
    return 0 if result.pages else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "crawl":
            cfg = CrawlConfig.from_env(args.env_file).with_overrides(
                seeds=tuple(args.urls) or None, max_depth=args.max_depth,
                max_pages=args.max_pages, concurrency=args.concurrency, delay=args.delay,
                timeout=args.timeout, retries=args.retries, output_dir=args.output_dir,
                respect_robots=False if args.ignore_robots else None,
                log_level=args.log_level.upper() if args.log_level else None,
            )
            setup_logging(cfg.log_level, cfg.log_file)
            if not cfg.seeds:
                print("error: provide seed URLs or set CRAWLER_SEEDS", file=sys.stderr)
                return 2
            return asyncio.run(_run_crawl(args, cfg))
        setup_logging("WARNING")
        if args.command == "report":
            report = HtmlReportExporter().export(load_result_json(args.data),
                                                 args.data.parent / "report.html")
            print(f"HTML report: {report.resolve()}")
            if not args.no_open:
                webbrowser.open(report.resolve().as_uri())
            return 0
        pages = load_pages_json(args.data)
        if args.command == "search":
            _print_hits(SearchEngine(pages).search(args.query, args.limit))
        else:
            for word, count in KeywordAnalyzer(pages).top_keywords(args.top):
                print(f"{word:<20}{count:>6}  {'#' * min(count, 40)}")
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except CrawlerError as exc:
        log.error("%s", exc)
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
