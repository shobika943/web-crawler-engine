"""Convenience entry point:  python main.py crawl <url>"""
import sys

from crawler_engine.cli import main

if __name__ == "__main__":
    sys.exit(main())
