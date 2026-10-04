import json

from crawler_engine.analysis import KeywordAnalyzer, SearchEngine
from crawler_engine.config import CrawlConfig
from crawler_engine.exceptions import ConfigError
from crawler_engine.exporter import CsvExporter, JsonExporter, SitemapExporter, SqliteExporter, load_pages_json
from crawler_engine.models import CrawlResult
from crawler_engine.parser import HtmlParser
from crawler_engine.utils.url_utils import is_crawlable, normalize_url, same_site
import pytest, sqlite3

HTML = """<html lang="en"><head><title> Hello  World </title>
<meta name="description" content="A test"><meta property="og:title" content="OG"></head>
<body><script>var x=1;</script><h1>Main</h1><h2>Sub</h2><p>First para.</p><p>Second para.</p>
<a href="/a#frag">A</a><a href="/a">A again</a><a href="mailto:x@y.z">mail</a>
<a href="http://other.com/x.jpg">img</a><img src="i.png" alt="pic"></body></html>"""


def test_normalize_and_filters():
    assert normalize_url("HTTP://Example.com:80/a#x") == "http://example.com/a"
    assert normalize_url("https://example.com") == "https://example.com/"
    assert is_crawlable("https://a.com/page") and not is_crawlable("https://a.com/x.pdf")
    assert not is_crawlable("ftp://a.com/")
    assert same_site("https://www.a.com/x", "https://a.com/y")
    assert not same_site("https://a.com", "https://b.com")


def test_parser_extracts_everything():
    p = HtmlParser().parse(HTML, "http://site.test/dir/", depth=1)
    assert p.title == "Hello World" and p.language == "en" and p.description == "A test"
    assert p.headings == {"h1": ["Main"], "h2": ["Sub"]}
    assert p.paragraphs == ["First para.", "Second para."]
    assert [l["url"] for l in p.links] == ["http://site.test/a"]  # dedup, no mailto, no .jpg
    assert p.images == [{"src": "http://site.test/dir/i.png", "alt": "pic"}]
    assert "var x" not in p.text and p.word_count > 0


def _pages():
    a = HtmlParser().parse("<title>Python guide</title><h1>Python</h1><p>python python code</p>", "http://x/a")
    b = HtmlParser().parse("<title>Cooking</title><p>pasta and python once</p>", "http://x/b")
    return [a, b]


def test_search_ranking_and_keywords():
    hits = SearchEngine(_pages()).search("python")
    assert [h.url for h in hits] == ["http://x/a", "http://x/b"]
    assert SearchEngine(_pages()).search("nonexistentword") == []
    assert KeywordAnalyzer(_pages()).top_keywords(1)[0][0] == "python"


def test_exporters(tmp_path):
    res = CrawlResult(pages=_pages())
    JsonExporter().export(res, tmp_path / "o.json")
    CsvExporter().export(res, tmp_path / "o.csv")
    SqliteExporter().export(res, tmp_path / "o.db")
    SitemapExporter().export(res, tmp_path / "s.xml")
    assert len(json.loads((tmp_path / "o.json").read_text())["pages"]) == 2
    assert len(load_pages_json(tmp_path / "o.json")) == 2
    assert (tmp_path / "o.csv").read_text(encoding="utf-8-sig").count("\n") == 3
    assert sqlite3.connect(tmp_path / "o.db").execute("select count(*) from pages").fetchone()[0] == 2
    assert "<loc>http://x/a</loc>" in (tmp_path / "s.xml").read_text()


def test_config_validation(monkeypatch):
    with pytest.raises(ConfigError):
        CrawlConfig(max_depth=-1).validate()
    monkeypatch.setenv("CRAWLER_MAX_DEPTH", "abc")
    with pytest.raises(ConfigError):
        CrawlConfig.from_env(None)


def test_html_report_and_roundtrip(tmp_path):
    from crawler_engine.exporter import HtmlReportExporter, load_result_json
    res = CrawlResult(pages=_pages())
    JsonExporter().export(res, tmp_path / "o.json")
    loaded = load_result_json(tmp_path / "o.json")
    out = HtmlReportExporter().export(loaded, tmp_path / "report.html")
    html = out.read_text(encoding="utf-8")
    assert "Web Crawl Report" in html and "http://x/a" in html and "__DATA__" not in html
