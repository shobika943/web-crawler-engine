"""Async HTTP downloader with retries, timeouts and per-host politeness delay."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from types import TracebackType
from urllib.parse import urlsplit

import httpx

from crawler_engine.config import CrawlConfig
from crawler_engine.crawler.robots import RobotsPolicy
from crawler_engine.exceptions import FetchError, SkippedContent

log = logging.getLogger(__name__)
_RETRY_STATUS = {429, 500, 502, 503, 504}


@dataclass
class FetchResult:
    url: str          # final URL after redirects
    status_code: int
    html: str
    size: int


class Fetcher:
    """Use as ``async with Fetcher(config) as f``."""

    def __init__(self, config: CrawlConfig) -> None:
        self._cfg = config
        self._client: httpx.AsyncClient | None = None
        self.robots: RobotsPolicy | None = None
        self._host_locks: dict[str, asyncio.Lock] = {}
        self._last_hit: dict[str, float] = {}

    async def __aenter__(self) -> "Fetcher":
        self._client = httpx.AsyncClient(
            headers={"User-Agent": self._cfg.user_agent, "Accept": "text/html,*/*;q=0.8"},
            timeout=httpx.Timeout(self._cfg.timeout),
            follow_redirects=True,
            limits=httpx.Limits(max_connections=self._cfg.concurrency * 2),
        )
        self.robots = RobotsPolicy(self._client, self._cfg.user_agent, self._cfg.respect_robots)
        return self

    async def __aexit__(self, et: type[BaseException] | None, ev: BaseException | None,
                        tb: TracebackType | None) -> None:
        if self._client:
            await self._client.aclose()

    async def _throttle(self, url: str) -> None:
        """Ensure at least `delay` seconds between requests to the same host."""
        host = urlsplit(url).netloc
        delay = self._cfg.delay
        if self.robots:
            delay = max(delay, await self.robots.crawl_delay(url))
        lock = self._host_locks.setdefault(host, asyncio.Lock())
        async with lock:
            wait = delay - (time.monotonic() - self._last_hit.get(host, 0.0))
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_hit[host] = time.monotonic()

    async def fetch(self, url: str) -> FetchResult:
        """Download `url`; retries transient failures with exponential backoff."""
        assert self._client is not None, "Fetcher must be used as an async context manager"
        last_error: Exception | None = None
        for attempt in range(self._cfg.retries + 1):
            try:
                await self._throttle(url)
                resp = await self._client.get(url)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                log.warning("Attempt %d/%d failed for %s: %s", attempt + 1,
                            self._cfg.retries + 1, url, type(exc).__name__)
            except httpx.InvalidURL as exc:
                raise FetchError(f"Invalid URL {url}: {exc}") from exc
            else:
                if resp.status_code in _RETRY_STATUS and attempt < self._cfg.retries:
                    last_error = FetchError(f"HTTP {resp.status_code}")
                    log.warning("HTTP %d for %s (attempt %d)", resp.status_code, url, attempt + 1)
                elif resp.status_code >= 400:
                    raise FetchError(f"HTTP {resp.status_code}")
                else:
                    return self._to_result(resp)
            await asyncio.sleep(self._cfg.backoff ** attempt)
        raise FetchError(f"Gave up after {self._cfg.retries + 1} attempts: {last_error!r}")

    def _to_result(self, resp: httpx.Response) -> FetchResult:
        ctype = resp.headers.get("content-type", "").lower()
        if "html" not in ctype and "xml" not in ctype:
            raise SkippedContent(f"Non-HTML content-type: {ctype or 'unknown'}")
        size = len(resp.content)
        if size > self._cfg.max_bytes:
            raise SkippedContent(f"Response too large ({size} bytes)")
        return FetchResult(url=str(resp.url), status_code=resp.status_code, html=resp.text, size=size)
