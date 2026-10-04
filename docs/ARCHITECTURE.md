# Architecture

```
                 ┌────────────┐
   CLI / .env ──▶│ CrawlConfig│
                 └─────┬──────┘
                       ▼
┌───────────────────────────────────────────┐
│ Crawler (engine.py)  – BFS by depth        │
│  visited-set · semaphore · stats           │
│      │ uses                │ uses          │
│      ▼                     ▼               │
│  Fetcher (httpx async)   HtmlParser (bs4)  │
│  retries · backoff       title/headings/   │
│  per-host delay          p/links/img/meta  │
│  RobotsPolicy (cache)                      │
└──────────────┬────────────────────────────┘
               ▼  CrawlResult (PageData[], FailedPage[], CrawlStats)
   ┌───────────┴─────────────┐
   ▼                         ▼
Exporters (strategy)     Analysis
JSON · CSV · SQLite ·    SearchEngine (ranked keyword search)
Sitemap XML              KeywordAnalyzer (frequency)
```

## Packages
| Package | Responsibility |
|---|---|
| `crawler_engine.crawler` | `Crawler` orchestration, `Fetcher` (network), `RobotsPolicy` |
| `crawler_engine.parser` | HTML → `PageData` |
| `crawler_engine.exporter` | `Exporter` ABC + JSON/CSV/SQLite/Sitemap implementations |
| `crawler_engine.analysis` | Keyword search & frequency analysis |
| `crawler_engine.utils` | URL normalisation, logging setup |
| `crawler_engine.config / models / exceptions / cli` | Settings, dataclasses, error hierarchy, CLI |

## Key design decisions
* **Async I/O (httpx + asyncio)** – many pages downloaded concurrently; a semaphore bounds concurrency.
* **Level-by-level BFS** – deterministic depth accounting; `max_depth` and `max_pages` are enforced per level.
* **Duplicate avoidance** – URLs are normalised (fragment removed, host lowercased, default ports dropped) and kept in a `visited` set *before* being queued.
* **Politeness** – robots.txt is fetched once per host and cached; a per-host lock enforces `max(CRAWLER_DELAY, robots Crawl-delay)` between requests.
* **Resilience** – timeouts, retries with exponential backoff for network errors and 429/5xx; 4xx fail fast. Any exception on one page is logged and recorded in `failed`, never aborting the crawl.
* **Open/closed exporters** – new formats only need a new `Exporter` subclass.
* **Dependency direction** – parser/exporter/analysis depend only on `models`; the engine depends on fetcher + parser; the CLI wires everything.

## Error hierarchy
`CrawlerError` → `ConfigError`, `FetchError`, `SkippedContent`, `ParseError`, `ExportError`.

## Extending
Different parser (e.g. CSS selectors per site): pass a custom object with `.parse(html, url, depth, status_code)` to `Crawler(config, parser=...)`.
