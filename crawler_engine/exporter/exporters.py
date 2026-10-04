"""Exporters: JSON, CSV, SQLite and XML sitemap."""
from __future__ import annotations

import csv
import json
import logging
import sqlite3
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Sequence

from crawler_engine.exceptions import ExportError
from crawler_engine.models import CrawlResult, CrawlStats, FailedPage, PageData

log = logging.getLogger(__name__)


class Exporter(ABC):
    """Strategy interface: write a crawl result to ``path``."""

    @abstractmethod
    def export(self, result: CrawlResult, path: Path) -> Path: ...

    @staticmethod
    def _prepare(path: Path) -> Path:
        path = Path(path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ExportError(f"Cannot create {path.parent}: {exc}") from exc
        return path


class JsonExporter(Exporter):
    def export(self, result: CrawlResult, path: Path) -> Path:
        path = self._prepare(path)
        payload = {
            "stats": result.stats.to_dict(),
            "failed": [vars(f) for f in result.failed],
            "pages": [p.to_dict() for p in result.pages],
        }
        try:
            path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:
            raise ExportError(f"Cannot write {path}: {exc}") from exc
        log.info("Wrote JSON: %s", path)
        return path


class CsvExporter(Exporter):
    FIELDS = ["url", "depth", "status_code", "title", "description", "language", "h1",
              "word_count", "num_links", "num_images", "text_preview", "fetched_at"]

    def export(self, result: CrawlResult, path: Path) -> Path:
        path = self._prepare(path)
        try:
            with path.open("w", newline="", encoding="utf-8-sig") as fh:
                writer = csv.DictWriter(fh, fieldnames=self.FIELDS)
                writer.writeheader()
                for p in result.pages:
                    writer.writerow({
                        "url": p.url, "depth": p.depth, "status_code": p.status_code,
                        "title": p.title, "description": p.description, "language": p.language,
                        "h1": " | ".join(p.headings.get("h1", [])),
                        "word_count": p.word_count, "num_links": len(p.links),
                        "num_images": len(p.images), "text_preview": p.text[:300],
                        "fetched_at": p.fetched_at,
                    })
        except OSError as exc:
            raise ExportError(f"Cannot write {path}: {exc}") from exc
        log.info("Wrote CSV: %s", path)
        return path


class SqliteExporter(Exporter):
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS pages(url TEXT PRIMARY KEY, depth INT, status_code INT, title TEXT,
        description TEXT, language TEXT, text TEXT, word_count INT, fetched_at TEXT);
    CREATE TABLE IF NOT EXISTS links(source TEXT, target TEXT, anchor_text TEXT);
    CREATE TABLE IF NOT EXISTS images(page TEXT, src TEXT, alt TEXT);
    CREATE TABLE IF NOT EXISTS headings(page TEXT, level TEXT, text TEXT);
    """

    def export(self, result: CrawlResult, path: Path) -> Path:
        path = self._prepare(path)
        try:
            with sqlite3.connect(path) as con:
                con.executescript(self.SCHEMA)
                for p in result.pages:
                    for table, col in (("links", "source"), ("images", "page"), ("headings", "page")):
                        con.execute(f"DELETE FROM {table} WHERE {col}=?", (p.url,))
                    con.execute("INSERT OR REPLACE INTO pages VALUES(?,?,?,?,?,?,?,?,?)",
                                (p.url, p.depth, p.status_code, p.title, p.description,
                                 p.language, p.text, p.word_count, p.fetched_at))
                    con.executemany("INSERT INTO links VALUES(?,?,?)",
                                    [(p.url, l["url"], l["text"]) for l in p.links])
                    con.executemany("INSERT INTO images VALUES(?,?,?)",
                                    [(p.url, i["src"], i["alt"]) for i in p.images])
                    con.executemany("INSERT INTO headings VALUES(?,?,?)",
                                    [(p.url, lvl, t) for lvl, ts in p.headings.items() for t in ts])
        except sqlite3.Error as exc:
            raise ExportError(f"SQLite export failed: {exc}") from exc
        log.info("Wrote SQLite DB: %s", path)
        return path


class SitemapExporter(Exporter):
    """Standard sitemaps.org XML of all successfully crawled URLs."""

    def export(self, result: CrawlResult, path: Path) -> Path:
        path = self._prepare(path)
        root = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
        for p in result.pages:
            node = ET.SubElement(root, "url")
            ET.SubElement(node, "loc").text = p.url
            ET.SubElement(node, "lastmod").text = p.fetched_at[:10]
        ET.indent(root)
        try:
            ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
        except OSError as exc:
            raise ExportError(f"Cannot write {path}: {exc}") from exc
        log.info("Wrote sitemap: %s", path)
        return path


def load_pages_json(path: Path) -> list[PageData]:
    """Read pages back from a JSON export."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return [PageData.from_dict(p) for p in data["pages"]]
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        raise ExportError(f"Cannot load crawl data from {path}: {exc}") from exc


def load_result_json(path: Path) -> CrawlResult:
    """Read a full crawl result (pages, failures, stats) from a JSON export."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return CrawlResult(
            pages=[PageData.from_dict(p) for p in data["pages"]],
            failed=[FailedPage(**f) for f in data.get("failed", [])],
            stats=CrawlStats(**data.get("stats", {})),
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ExportError(f"Cannot load crawl data from {path}: {exc}") from exc
