"""Configuration loaded from environment / .env file."""
from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

from dotenv import load_dotenv

from crawler_engine.exceptions import ConfigError


def _bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class CrawlConfig:
    """All tunables of a crawl. Immutable; use :meth:`with_overrides`."""

    seeds: tuple[str, ...] = ()
    max_depth: int = 2
    max_pages: int = 50
    concurrency: int = 5
    delay: float = 1.0
    timeout: float = 10.0
    retries: int = 3
    backoff: float = 1.5
    user_agent: str = "PyCrawlerBot/1.0"
    respect_robots: bool = True
    max_bytes: int = 5_000_000
    output_dir: Path = field(default_factory=lambda: Path("output"))
    log_level: str = "INFO"
    log_file: Path | None = Path("logs/crawler.log")

    @classmethod
    def from_env(cls, env_file: str | None = ".env") -> "CrawlConfig":
        """Build a config from environment variables (``CRAWLER_*``)."""
        if env_file:
            load_dotenv(env_file)
        g = os.environ.get
        try:
            seeds = tuple(s.strip() for s in g("CRAWLER_SEEDS", "").split(",") if s.strip())
            log_file = g("CRAWLER_LOG_FILE", "logs/crawler.log")
            cfg = cls(
                seeds=seeds,
                max_depth=int(g("CRAWLER_MAX_DEPTH", "2")),
                max_pages=int(g("CRAWLER_MAX_PAGES", "50")),
                concurrency=int(g("CRAWLER_CONCURRENCY", "5")),
                delay=float(g("CRAWLER_DELAY", "1.0")),
                timeout=float(g("CRAWLER_TIMEOUT", "10")),
                retries=int(g("CRAWLER_RETRIES", "3")),
                backoff=float(g("CRAWLER_BACKOFF", "1.5")),
                user_agent=g("CRAWLER_USER_AGENT", "PyCrawlerBot/1.0"),
                respect_robots=_bool(g("CRAWLER_RESPECT_ROBOTS", "true")),
                output_dir=Path(g("CRAWLER_OUTPUT_DIR", "output")),
                log_level=g("CRAWLER_LOG_LEVEL", "INFO").upper(),
                log_file=Path(log_file) if log_file else None,
            )
        except ValueError as exc:
            raise ConfigError(f"Invalid numeric value in environment: {exc}") from exc
        cfg.validate()
        return cfg

    def with_overrides(self, **kwargs: object) -> "CrawlConfig":
        """Return a copy with non-None overrides applied (CLI flags)."""
        clean = {k: v for k, v in kwargs.items() if v is not None}
        cfg = replace(self, **clean)  # type: ignore[arg-type]
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if self.max_depth < 0:
            raise ConfigError("max_depth must be >= 0")
        if self.max_pages < 1:
            raise ConfigError("max_pages must be >= 1")
        if self.concurrency < 1:
            raise ConfigError("concurrency must be >= 1")
        if self.delay < 0 or self.timeout <= 0 or self.retries < 0:
            raise ConfigError("delay/timeout/retries have invalid values")
