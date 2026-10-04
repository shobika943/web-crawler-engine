"""Keyword search (TF-style scoring) and keyword-frequency analysis."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Sequence

from crawler_engine.models import PageData

_TOKEN = re.compile(r"[a-z0-9']+")
STOPWORDS = frozenset(
    "a an and are as at be but by for from has have he her his i in is it its of on or our she "
    "that the their them they this to was we were will with you your not no can all more one "
    "about into than so if what which who when there been also".split()
)


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


@dataclass
class SearchHit:
    url: str
    title: str
    score: float
    snippet: str


class SearchEngine:
    """Ranks pages: title matches x5, headings x3, body occurrences x1."""

    def __init__(self, pages: Sequence[PageData]) -> None:
        self._pages = pages

    def search(self, query: str, limit: int = 10) -> list[SearchHit]:
        terms = [t for t in tokenize(query) if t not in STOPWORDS] or tokenize(query)
        if not terms:
            return []
        hits: list[SearchHit] = []
        for page in self._pages:
            title = Counter(tokenize(page.title))
            heads = Counter(tokenize(" ".join(h for hs in page.headings.values() for h in hs)))
            body = Counter(tokenize(page.text))
            score = sum(5 * title[t] + 3 * heads[t] + body[t] for t in terms)
            if score and all(title[t] + heads[t] + body[t] for t in terms):
                hits.append(SearchHit(page.url, page.title, float(score), self._snippet(page, terms)))
        return sorted(hits, key=lambda h: h.score, reverse=True)[:limit]

    @staticmethod
    def _snippet(page: PageData, terms: list[str], width: int = 80) -> str:
        low = page.text.lower()
        idx = min((i for t in terms if (i := low.find(t)) >= 0), default=0)
        start = max(0, idx - width)
        end = min(len(page.text), idx + width)
        return ("..." if start else "") + page.text[start:end] + ("..." if end < len(page.text) else "")


class KeywordAnalyzer:
    """Corpus-level keyword frequency analysis."""

    def __init__(self, pages: Sequence[PageData]) -> None:
        self._pages = pages

    def top_keywords(self, n: int = 20, min_length: int = 3) -> list[tuple[str, int]]:
        counter: Counter[str] = Counter()
        for page in self._pages:
            counter.update(t for t in tokenize(page.text)
                           if len(t) >= min_length and t not in STOPWORDS and not t.isdigit())
        return counter.most_common(n)
