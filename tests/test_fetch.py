from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
import threading
import time
import unittest
from unittest.mock import patch

from siteaudit_kit.fetch import FetchError, _PinnedConnection, _public_address, _resolve, fetch_url, validate_url


class QuietServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass  # Clients intentionally interrupt oversized/timed-out test responses.


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        path = self.path.partition("?")[0]
        if path == "/timeout":
            time.sleep(0.4)
        redirects = {"/relative": "/html", "/loop": "/loop", "/private": "http://127.0.0.1:1/",
                     "/downgrade": "http://example.org/"}
        if path in redirects or path == "/missing-location":
            self.send_response(302)
            if path in redirects:
                self.send_header("Location", redirects[path])
            self.end_headers()
            return
        if path == "/status":
            self.send_response(404)
            self.end_headers()
            return
        body = b'<html lang="en"><head><title>Example HTML page</title></head><body><h1>Hello</h1></body></html>'
        if path == "/large":
            body = b"x" * 4096
        if path == "/latin":
            body = "<h1>café</h1>".encode("latin-1")
        self.send_response(200)
        content_type = "text/html; charset=utf-8"
        if path == "/json":
            content_type = "application/json"
        elif path == "/latin":
            content_type = "text/html; charset=iso-8859-1"
        elif path == "/bad-charset":
            content_type = "text/html; charset=unknown-character-set"
        self.send_header("Content-Type", content_type)
        if path == "/compressed":
            self.send_header("Content-Encoding", "gzip")
        if path != "/stream":
            self.send_header("Content-Length", str(len(body) + (10 if path == "/truncated" else 0)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass


class FetchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = QuietServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def get(self, path, **kwargs):
        return fetch_url(self.base + path, allow_private=True, **kwargs)

    def test_fetch_html(self):
        page = self.get("/html#fragment")
        self.assertEqual(page.url, self.base + "/html")
        self.assertEqual(page.status, 200)
        self.assertIn("<h1>Hello", page.html)
        self.assertEqual(page.size_bytes, len(page.html.encode()))

    def test_private_target_blocked_by_default(self):
        with self.assertRaisesRegex(FetchError, "blocked"):
            fetch_url(self.base + "/html")

    def test_relative_redirect(self):
        self.assertEqual(self.get("/relative").url, self.base + "/html")

    def test_redirect_loop(self):
        with self.assertRaisesRegex(FetchError, "loop"):
            self.get("/loop")

    def test_redirect_budget(self):
        with self.assertRaisesRegex(FetchError, "limit"):
            self.get("/relative", max_redirects=0)

    def test_redirect_missing_location(self):
        with self.assertRaisesRegex(FetchError, "Location"):
            self.get("/missing-location")

    def test_every_redirect_is_resolved(self):
        calls = []
        original = _resolve

        def resolve(host, port, allow_private):
            calls.append((host, port))
            if len(calls) == 2:
                raise FetchError("private redirect blocked")
            return original(host, port, True)

        with patch("siteaudit_kit.fetch._resolve", side_effect=resolve):
            with self.assertRaisesRegex(FetchError, "private redirect"):
                fetch_url(self.base + "/private")
        self.assertEqual(len(calls), 2)

    def test_non_html_response(self):
        with self.assertRaisesRegex(FetchError, "Content-Type"):
            self.get("/json")

    def test_http_error_status(self):
        with self.assertRaisesRegex(FetchError, "404"):
            self.get("/status")

    def test_declared_size_budget(self):
        with self.assertRaisesRegex(FetchError, "budget"):
            self.get("/large", max_bytes=100)

    def test_streamed_size_budget(self):
        with self.assertRaisesRegex(FetchError, "budget"):
            self.get("/stream", max_bytes=10)

    def test_truncated_response_rejected(self):
        with self.assertRaisesRegex(FetchError, "Content-Length"):
            self.get("/truncated")

    def test_compression_is_explicitly_rejected(self):
        with self.assertRaisesRegex(FetchError, "compressed"):
            self.get("/compressed")

    def test_declared_character_encoding(self):
        self.assertIn("café", self.get("/latin").html)

    def test_unknown_character_encoding(self):
        with self.assertRaisesRegex(FetchError, "encoding"):
            self.get("/bad-charset")

    def test_timeout_interrupts_request(self):
        start = time.monotonic()
        with self.assertRaises(FetchError):
            self.get("/timeout", timeout=0.08)
        self.assertLess(time.monotonic() - start, 0.35)

    def test_invalid_budgets(self):
        for kwargs in ({"timeout": float("nan")}, {"timeout": float("inf")}, {"timeout": 0},
                       {"max_bytes": 0}, {"max_bytes": 9 * 1024 * 1024}, {"max_redirects": 11}):
            with self.subTest(kwargs=kwargs), self.assertRaises(FetchError):
                self.get("/html", **kwargs)

    def test_url_validation(self):
        for url in ("file:///etc/passwd", "ftp://example.org", "https://user:pass@example.org",
                    "https://example.org\nInjected", "https://example.org\\path",
                    "https://example.org:0", "https://example.org:99999",
                    "https://[fe80::1%25eth0]/", "https://exa%mple.org", "https://"):
            with self.subTest(url=url), self.assertRaises(FetchError):
                validate_url(url)

    def test_idna_hostname(self):
        _, host, _ = validate_url("https://bücher.example/")
        self.assertEqual(host, "xn--bcher-kva.example")

    def test_public_private_and_tunnel_addresses(self):
        for address in ("127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "fc00::1",
                        "::ffff:127.0.0.1", "224.0.0.1", "2002:7f00:1::", "64:ff9b::7f00:1", "192.0.2.1"):
            with self.subTest(address=address):
                self.assertFalse(_public_address(address))
        self.assertTrue(_public_address("8.8.8.8"))
        self.assertTrue(_public_address("2606:4700:4700::1111"))

    def test_mixed_dns_answers_blocked(self):
        answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 443)),
                   (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
        with patch("socket.getaddrinfo", return_value=answers):
            with self.assertRaisesRegex(FetchError, "blocked"):
                _resolve("example.org", 443, False)

    def test_connection_uses_pinned_ip_and_original_tls_hostname(self):
        with patch("socket.create_connection") as connect, patch("ssl.create_default_context") as context:
            connection = _PinnedConnection("example.org", 443, "8.8.8.8", 2, True)
            connection.connect()
            connect.assert_called_once_with(("8.8.8.8", 443), timeout=2)
            context.return_value.wrap_socket.assert_called_once_with(connect.return_value, server_hostname="example.org")
            connection.close()

    def test_https_downgrade_blocked(self):
        response = unittest.mock.MagicMock()
        response.status = 302
        response.getheaders.return_value = [("Location", "http://example.org/")]
        with patch("siteaudit_kit.fetch._resolve", return_value="8.8.8.8"), patch("siteaudit_kit.fetch._PinnedConnection") as cls:
            cls.return_value.getresponse.return_value = response
            with self.assertRaisesRegex(FetchError, "HTTPS-to-HTTP"):
                fetch_url("https://example.org")


if __name__ == "__main__":
    unittest.main()
