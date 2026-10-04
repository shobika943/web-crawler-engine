"""HTML -> :class:`PageData` extraction using BeautifulSoup (lxml backend)."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from crawler_engine.exceptions import ParseError
from crawler_engine.models import PageData
from crawler_engine.utils.url_utils import is_crawlable, normalize_url

log = logging.getLogger(__name__)
_WS = re.compile(r"\s+")


def _clean(text: str) -> str:
    return _WS.sub(" ", text).strip()


class HtmlParser:
    """Turns raw HTML into structured data."""

    def parse(self, html: str, url: str, depth: int = 0, status_code: int = 200) -> PageData:
        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception as exc:  # parser backend failures are rare but possible
            raise ParseError(f"Cannot parse {url}: {exc}") from exc

        for tag in soup(["script", "style", "noscript", "template"]):
            tag.decompose()

        metadata = self._metadata(soup)
        title = _clean(soup.title.get_text()) if soup.title else metadata.get("og:title", "")
        body_text = _clean(soup.get_text(" "))
        page = PageData(
            url=url,
            depth=depth,
            status_code=status_code,
            title=title,
            description=metadata.get("description", metadata.get("og:description", "")),
            language=(soup.html.get("lang", "") if soup.html else ""),
            headings=self._headings(soup),
            paragraphs=[t for p in soup.find_all("p") if (t := _clean(p.get_text()))],
            links=self._links(soup, url),
            images=self._images(soup, url),
            metadata=metadata,
            text=body_text,
            word_count=len(body_text.split()),
            fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        return page

    @staticmethod
    def _headings(soup: BeautifulSoup) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for level in range(1, 7):
            items = [t for h in soup.find_all(f"h{level}") if (t := _clean(h.get_text()))]
            if items:
                out[f"h{level}"] = items
        return out

    @staticmethod
    def _links(soup: BeautifulSoup, base: str) -> list[dict[str, str]]:
        seen: set[str] = set()
        links: list[dict[str, str]] = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if href.startswith(("mailto:", "tel:", "javascript:", "#")):
                continue
            try:
                absolute = normalize_url(urljoin(base, href))
            except ValueError:  # malformed URL such as bad port
                continue
            if absolute in seen or not is_crawlable(absolute):
                continue
            seen.add(absolute)
            links.append({"url": absolute, "text": _clean(a.get_text())})
        return links

    @staticmethod
    def _images(soup: BeautifulSoup, base: str) -> list[dict[str, str]]:
        imgs = []
        for img in soup.find_all("img", src=True):
            imgs.append({"src": urljoin(base, img["src"]), "alt": _clean(img.get("alt", ""))})
        return imgs

    @staticmethod
    def _metadata(soup: BeautifulSoup) -> dict[str, str]:
        meta: dict[str, str] = {}
        for tag in soup.find_all("meta"):
            key = tag.get("name") or tag.get("property")
            content = tag.get("content")
            if key and content:
                meta[key.lower()] = _clean(content)
        canonical = soup.find("link", rel="canonical")
        if canonical and canonical.get("href"):
            meta["canonical"] = canonical["href"]
        return meta
