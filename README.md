# Web Crawler & Data Extraction Engine

Async Python 3.11+ crawler that downloads pages, extracts titles, headings, paragraphs, links, images and metadata, follows internal links to a configurable depth, respects `robots.txt`, and exports JSON / CSV / SQLite / XML sitemap, with keyword search and keyword-frequency analysis.

## Features
- Multiple seed URLs · configurable depth, page limit, concurrency
- `httpx` + `asyncio` · retries with exponential backoff · timeouts
- robots.txt (cached, `Crawl-delay` aware) · per-host politeness delay
- Visited-URL tracking with URL normalisation
- Exports: `pages.json`, `pages.csv`, `crawl.db` (SQLite), `sitemap.xml`, and an interactive **`report.html`** dashboard
- Ranked keyword search and keyword frequency analysis
- Rotating log file · crawl statistics · CLI · Docker · 11 tests · GitHub Actions CI

## Setup
```bash
git clone https://github.com/<you>/web-crawler.git && cd web-crawler
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # Windows: copy .env.example .env
```

## Usage
```bash
# crawl (flags override .env)
python main.py crawl https://quotes.toscrape.com/ --depth 2 --max-pages 30 --delay 0.5

# several seeds + search straight after crawling
python main.py crawl https://quotes.toscrape.com/ https://books.toscrape.com/ -q "love"

# open the results as a web page (stats, live search, keyword chart, page table)
python main.py crawl https://quotes.toscrape.com/ -d 2 -m 30 --open
python main.py report                      # rebuild + open report from output/pages.json

# search / analyse saved data
python main.py search "life" --data output/pages.json
python main.py keywords --top 15
```
Outputs go to `output/` (change with `-o` or `CRAWLER_OUTPUT_DIR`); logs go to `logs/crawler.log`.

| Flag | Meaning |
|---|---|
| `-d/--depth` | link depth (0 = seeds only) |
| `-m/--max-pages` | stop after N pages |
| `-c/--concurrency` | parallel requests |
| `--delay` | seconds between requests per host |
| `--ignore-robots` | disable robots.txt (only on sites you own) |

## Docker
```bash
docker build -t web-crawler .
docker run --rm -v "$PWD/output:/app/output" web-crawler crawl https://quotes.toscrape.com/ -d 1
```

## Tests
```bash
python -m pytest -q
```
Tests run against a local HTTP server (no internet needed) and cover robots.txt, depth/page limits, duplicate handling, 404s, unreachable hosts, parsing, exporters, search and config validation.

## Project layout
See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Sample outputs are in `samples/` (generated from the local test site).

## Ethics
Crawl only sites you are allowed to crawl, keep delays polite and obey robots.txt.
