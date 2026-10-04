"""robots.txt handling with a per-host cache."""
from __future__ import annotations

import asyncio
import logging
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx

log = logging.getLogger(__name__)


class RobotsPolicy:
    """Fetches and caches robots.txt; answers ``can_fetch`` / ``crawl_delay``."""

    def __init__(self, client: httpx.AsyncClient, user_agent: str, enabled: bool = True) -> None:
        self._client = client
        self._ua = user_agent
        self._enabled = enabled
        self._cache: dict[str, RobotFileParser | None] = {}
        self._lock = asyncio.Lock()

    async def _load(self, url: str) -> RobotFileParser | None:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        async with self._lock:
            if origin in self._cache:
                return self._cache[origin]
            parser: RobotFileParser | None = None
            try:
                resp = await self._client.get(f"{origin}/robots.txt")
                if resp.status_code == 200:
                    parser = RobotFileParser()
                    parser.parse(resp.text.splitlines())
                elif resp.status_code in (401, 403):
                    parser = RobotFileParser()
                    parser.parse(["User-agent: *", "Disallow: /"])
                # 404 & others => no restrictions
            except httpx.HTTPError as exc:
                log.warning("Could not fetch robots.txt for %s (%s); assuming allowed", origin, exc)
            self._cache[origin] = parser
            return parser

    async def can_fetch(self, url: str) -> bool:
        if not self._enabled:
            return True
        parser = await self._load(url)
        return True if parser is None else parser.can_fetch(self._ua, url)

    async def crawl_delay(self, url: str) -> float:
        if not self._enabled:
            return 0.0
        parser = await self._load(url)
        if parser is None:
            return 0.0
        return float(parser.crawl_delay(self._ua) or 0.0)
