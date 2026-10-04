"""Custom exception hierarchy."""


class CrawlerError(Exception):
    """Base class for all crawler errors."""


class ConfigError(CrawlerError):
    """Invalid configuration."""


class FetchError(CrawlerError):
    """A page could not be downloaded (after retries)."""


class SkippedContent(CrawlerError):
    """The response is not something we want to parse (e.g. PDF, too large)."""


class ParseError(CrawlerError):
    """HTML could not be parsed."""


class ExportError(CrawlerError):
    """Exporting results failed."""
