import asyncio

import pytest

from crawler_engine.config import CrawlConfig
from crawler_engine.crawler import Crawler
from crawler_engine.exceptions import CrawlerError


def cfg(site, **kw):
    base = dict(seeds=(site + "/",), max_depth=3, delay=0, retries=1, backoff=0.01,
                timeout=3, log_file=None)
    base.update(kw)
    return CrawlConfig(**base)


def test_full_crawl_respects_robots_depth_and_dedupes(site):
    res = asyncio.run(Crawler(cfg(site)).crawl())
    urls = {p.url.replace(site, "") for p in res.pages}
    assert urls == {"/", "/about", "/blog/", "/blog/post1"}
    assert len(res.pages) == len(urls)                    # no duplicates
    assert res.stats.skipped_robots == 1                  # /private/secret
    assert [f.url.replace(site, "") for f in res.failed] == ["/broken"]  # 404
    assert res.stats.duplicates_skipped > 0
    assert not any("external.example.org" in p.url for p in res.pages)


def test_depth_limit(site):
    res = asyncio.run(Crawler(cfg(site, max_depth=0)).crawl())
    assert len(res.pages) == 1 and res.pages[0].depth == 0


def test_max_pages(site):
    res = asyncio.run(Crawler(cfg(site, max_pages=2)).crawl())
    assert len(res.pages) == 2


def test_ignore_robots(site):
    res = asyncio.run(Crawler(cfg(site, respect_robots=False)).crawl())
    assert any(p.url.endswith("/private/secret") for p in res.pages)


def test_unreachable_host_is_reported_not_raised():
    res = asyncio.run(Crawler(CrawlConfig(seeds=("http://127.0.0.1:1/",), delay=0, retries=1,
                                          backoff=0.01, timeout=1, log_file=None)).crawl())
    assert res.stats.failures == 1 and not res.pages


def test_no_valid_seeds():
    with pytest.raises(CrawlerError):
        asyncio.run(Crawler(CrawlConfig(seeds=("not a url",), log_file=None)).crawl())
