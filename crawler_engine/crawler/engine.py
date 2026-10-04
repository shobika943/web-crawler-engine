"""Breadth-first, depth-limited asynchronous crawler."""
from __future__ import annotations

import asyncio
import logging
import time

from crawler_engine.config import CrawlConfig
from crawler_engine.crawler.fetcher import Fetcher
from crawler_engine.exceptions import CrawlerError, FetchError, SkippedContent
from crawler_engine.models import CrawlResult, FailedPage, PageData
from crawler_engine.parser.html_parser import HtmlParser
from crawler_engine.utils.url_utils import is_crawlable, normalize_url, same_site

log = logging.getLogger(__name__)


class Crawler:
    """Crawl internal links from seed URLs up to ``config.max_depth``.

    Level-by-level BFS: every URL at depth *d* is fetched concurrently (bounded by a
    semaphore), then newly discovered internal URLs form depth *d+1*.
    """

    def __init__(self, config: CrawlConfig, parser: HtmlParser | None = None) -> None:
        self._cfg = config
        self._parser = parser or HtmlParser()
        self._sem = asyncio.Semaphore(config.concurrency)
        self._result = CrawlResult()
        self._visited: set[str] = set()

    async def crawl(self) -> CrawlResult:
        seeds = [normalize_url(s) for s in self._cfg.seeds if is_crawlable(s)]
        if not seeds:
            raise CrawlerError("No valid http(s) seed URLs supplied")
        start = time.perf_counter()
        frontier = list(dict.fromkeys(seeds))
        self._visited.update(frontier)
        stats = self._result.stats

        async with Fetcher(self._cfg) as fetcher:
            for depth in range(self._cfg.max_depth + 1):
                remaining = self._cfg.max_pages - len(self._result.pages)
                if not frontier or remaining <= 0:
                    break
                batch = frontier[:remaining]
                log.info("Depth %d: crawling %d URL(s)", depth, len(batch))
                pages = await asyncio.gather(*(self._process(fetcher, u, depth) for u in batch))
                frontier = self._next_frontier([p for p in pages if p], depth, seeds)

        stats.duration_seconds = time.perf_counter() - start
        stats.pages_visited = len(self._result.pages)
        stats.failures = len(self._result.failed)
        log.info("Crawl finished: %d pages, %d failures", stats.pages_visited, stats.failures)
        return self._result

    def _next_frontier(self, pages: list[PageData], depth: int, seeds: list[str]) -> list[str]:
        if depth >= self._cfg.max_depth:
            return []
        nxt: list[str] = []
        for page in pages:
            for link in page.links:
                url = link["url"]
                if not any(same_site(url, s) for s in seeds):
                    continue
                if url in self._visited:
                    self._result.stats.duplicates_skipped += 1
                    continue
                self._visited.add(url)
                self._result.stats.urls_discovered += 1
                nxt.append(url)
        return nxt

    async def _process(self, fetcher: Fetcher, url: str, depth: int) -> PageData | None:
        stats = self._result.stats
        async with self._sem:
            try:
                assert fetcher.robots is not None
                if not await fetcher.robots.can_fetch(url):
                    stats.skipped_robots += 1
                    log.info("Blocked by robots.txt: %s", url)
                    return None
                fetched = await fetcher.fetch(url)
                stats.bytes_downloaded += fetched.size
                page = self._parser.parse(fetched.html, fetched.url, depth, fetched.status_code)
                self._result.pages.append(page)
                log.info("[d=%d] OK %s (%s)", depth, url, page.title[:50])
                return page
            except SkippedContent as exc:
                stats.skipped_non_html += 1
                log.info("Skipped %s: %s", url, exc)
            except (FetchError, CrawlerError) as exc:
                self._result.failed.append(FailedPage(url, depth, str(exc)))
                log.error("Failed %s: %s", url, exc)
            except Exception as exc:  # never let one page kill the crawl
                self._result.failed.append(FailedPage(url, depth, f"Unexpected: {exc!r}"))
                log.exception("Unexpected error on %s", url)
        return None
