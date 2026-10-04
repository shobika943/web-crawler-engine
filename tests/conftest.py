"""Local demo website used by unit/integration tests (no internet needed)."""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

PAGES = {
    "/": '<html lang="en"><head><title>Home</title><meta name="description" content="Welcome page">'
         '</head><body><h1>Python Crawler Demo</h1><p>Learn web crawling with Python.</p>'
         '<a href="/about">About</a> <a href="/blog/">Blog</a> <a href="/about#team">Team</a> '
         '<a href="/private/secret">Secret</a> <a href="/broken">Broken</a> <a href="/file.pdf">PDF</a>'
         '<a href="https://external.example.org/">Ext</a><img src="/logo.png" alt="Logo"></body></html>',
    "/about": '<html><head><title>About Us</title></head><body><h1>About</h1>'
              '<p>We build crawlers in Python.</p><a href="/">Home</a><a href="/blog/post1">P1</a></body></html>',
    "/blog/": '<html><head><title>Blog</title></head><body><h2>Posts</h2><p>Async IO rocks.</p>'
              '<a href="/blog/post1">Post 1</a><a href="/">Home</a></body></html>',
    "/blog/post1": '<html><head><title>Post One</title></head><body><h1>Async crawling</h1>'
                   '<p>asyncio makes crawling fast. Crawling crawling.</p></body></html>',
    "/private/secret": "<html><title>Secret</title><body>hidden</body></html>",
}
ROBOTS = "User-agent: *\nDisallow: /private/\n"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        path = self.path.split("?")[0]
        if path == "/robots.txt":
            return self._send(200, ROBOTS, "text/plain")
        if path == "/file.pdf":
            return self._send(200, "%PDF", "application/pdf")
        if path in PAGES:
            return self._send(200, PAGES[path], "text/html; charset=utf-8")
        self._send(404, "nope", "text/plain")

    def _send(self, code, body, ctype):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):  # silence
        pass


@pytest.fixture(scope="session")
def site():
    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
