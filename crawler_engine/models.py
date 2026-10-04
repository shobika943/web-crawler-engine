"""Plain data containers shared across packages."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class PageData:
    """Everything extracted from one web page."""

    url: str
    depth: int
    status_code: int
    title: str = ""
    description: str = ""
    language: str = ""
    headings: dict[str, list[str]] = field(default_factory=dict)
    paragraphs: list[str] = field(default_factory=list)
    links: list[dict[str, str]] = field(default_factory=list)   # {"url", "text"}
    images: list[dict[str, str]] = field(default_factory=list)  # {"src", "alt"}
    metadata: dict[str, str] = field(default_factory=dict)
    text: str = ""
    word_count: int = 0
    fetched_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PageData":
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


@dataclass
class FailedPage:
    url: str
    depth: int
    reason: str


@dataclass
class CrawlStats:
    """Counters reported at the end of a crawl."""

    pages_visited: int = 0
    failures: int = 0
    skipped_robots: int = 0
    skipped_non_html: int = 0
    duplicates_skipped: int = 0
    urls_discovered: int = 0
    bytes_downloaded: int = 0
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def summary(self) -> str:
        rate = self.pages_visited / self.duration_seconds if self.duration_seconds else 0.0
        return (
            "\n=========== CRAWL STATISTICS ===========\n"
            f" Pages visited      : {self.pages_visited}\n"
            f" Failures           : {self.failures}\n"
            f" Blocked by robots  : {self.skipped_robots}\n"
            f" Non-HTML skipped   : {self.skipped_non_html}\n"
            f" Duplicates avoided : {self.duplicates_skipped}\n"
            f" URLs discovered    : {self.urls_discovered}\n"
            f" Data downloaded    : {self.bytes_downloaded / 1024:.1f} KiB\n"
            f" Execution time     : {self.duration_seconds:.2f}s ({rate:.2f} pages/s)\n"
            "========================================"
        )


@dataclass
class CrawlResult:
    pages: list[PageData] = field(default_factory=list)
    failed: list[FailedPage] = field(default_factory=list)
    stats: CrawlStats = field(default_factory=CrawlStats)
