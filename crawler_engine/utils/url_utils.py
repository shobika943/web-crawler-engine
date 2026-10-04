"""URL normalisation and filtering helpers."""
from __future__ import annotations

from urllib.parse import urldefrag, urlsplit, urlunsplit

_SKIP_EXT = {
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico", ".bmp",
    ".pdf", ".zip", ".gz", ".tar", ".rar", ".7z", ".exe", ".dmg",
    ".mp3", ".mp4", ".avi", ".mov", ".wav", ".css", ".js", ".json", ".xml",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
}
_DEFAULT_PORTS = {"http": 80, "https": 443}


def normalize_url(url: str) -> str:
    """Canonical form used for duplicate detection (no fragment, lowercase host)."""
    url, _ = urldefrag(url.strip())
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    port = parts.port
    netloc = host if port in (None, _DEFAULT_PORTS.get(scheme)) else f"{host}:{port}"
    path = parts.path or "/"
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def is_crawlable(url: str) -> bool:
    """True for http(s) URLs that don't look like binary assets."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return False
    return not any(parts.path.lower().endswith(ext) for ext in _SKIP_EXT)


def _site(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def same_site(url: str, other: str) -> bool:
    """Same host, ignoring a leading ``www.``."""
    return _site(url) == _site(other)
