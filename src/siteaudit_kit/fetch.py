"""Bounded HTTP(S) fetching with address validation and pinned connections.

No cookies, authentication, proxy environment variables, or asset requests.
"""

from dataclasses import dataclass
import http.client
import ipaddress
import math
import re
import socket
import ssl
import threading
import time
from urllib.parse import quote, urljoin, urlsplit, urlunsplit


class FetchError(ValueError):
    """A URL was unsafe, unavailable, non-HTML, or exceeded a budget."""


@dataclass(frozen=True)
class FetchedPage:
    url: str
    html: str
    headers: dict[str, str]
    status: int
    size_bytes: int


def validate_url(url: str):
    if not isinstance(url, str) or len(url) > 8192:
        raise FetchError("URL must be a string of at most 8192 characters")
    if any(ord(c) < 33 or ord(c) == 127 for c in url) or "\\" in url:
        raise FetchError("URL contains whitespace, control characters, or backslashes")
    try:
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise FetchError("only absolute HTTP and HTTPS URLs are supported")
        if parts.username is not None or parts.password is not None:
            raise FetchError("URLs with embedded credentials are not supported")
        if "%" in parts.hostname:
            raise FetchError("encoded hostnames and IPv6 zone identifiers are not supported")
        port = parts.port if parts.port is not None else (443 if parts.scheme == "https" else 80)
        if not 1 <= port <= 65535:
            raise FetchError("invalid URL port")
        host = parts.hostname.encode("idna").decode("ascii")
        if not host or len(host) > 253:
            raise FetchError("invalid hostname")
        return parts, host, port
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, FetchError):
            raise
        raise FetchError("invalid URL") from exc


def _public_address(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return _public_address(str(ip.ipv4_mapped))
        # Avoid translation/tunnelling ranges which can encode a private IPv4 target.
        if ip.sixtofour is not None or ip.teredo is not None:
            return False
        if ip in ipaddress.ip_network("64:ff9b::/96") or ip in ipaddress.ip_network("64:ff9b:1::/48"):
            return False
    return ip.is_global and not ip.is_multicast and not ip.is_unspecified


def _resolve(host: str, port: int, allow_private: bool) -> str:
    try:
        answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise FetchError("hostname resolution failed") from exc
    addresses = list(dict.fromkeys(answer[4][0] for answer in answers))
    if not addresses:
        raise FetchError("hostname has no addresses")
    if not allow_private and any(not _public_address(ip) for ip in addresses):
        raise FetchError("private, local, reserved, or mixed public/private destinations are blocked; "
                         "use --allow-private only for trusted development targets")
    return addresses[0]


class _PinnedConnection(http.client.HTTPConnection):
    def __init__(self, host, port, address, timeout, tls):
        super().__init__(host, port=port, timeout=timeout)
        self.address = address
        self.tls = tls

    def connect(self):
        # Connect to the previously validated literal IP, never re-resolve the hostname.
        self.sock = socket.create_connection((self.address, self.port), timeout=self.timeout)
        if self.tls:
            try:
                self.sock = ssl.create_default_context().wrap_socket(self.sock, server_hostname=self.host)
            except Exception:
                self.sock.close()
                self.sock = None
                raise


def _remaining(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise FetchError("request time budget exceeded")
    return remaining


def _interrupt_socket(sock):
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass


def fetch_url(url: str, *, timeout: float = 15.0, max_bytes: int = 2 * 1024 * 1024,
              max_redirects: int = 5, allow_private: bool = False) -> FetchedPage:
    """Fetch one HTML document, validating and pinning each redirect destination.

    The time budget covers HTTP/TLS and reads; OS DNS resolution is synchronous
    and may exceed it before returning. A network firewall is still recommended
    if an embedding service accepts arbitrary untrusted user URLs.
    """
    if not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 120:
        raise FetchError("timeout must be finite, positive, and at most 120 seconds")
    if not isinstance(max_bytes, int) or not 1 <= max_bytes <= 8 * 1024 * 1024:
        raise FetchError("max_bytes must be an integer between 1 and 8 MiB")
    if not isinstance(max_redirects, int) or not 0 <= max_redirects <= 10:
        raise FetchError("max_redirects must be between 0 and 10")
    current = url
    deadline = time.monotonic() + timeout
    seen = set()
    for hop in range(max_redirects + 1):
        parts, host, port = validate_url(current)
        current = urlunsplit((parts.scheme, parts.netloc, parts.path or "/", parts.query, ""))
        if current in seen:
            raise FetchError("redirect loop detected")
        seen.add(current)
        address = _resolve(host, port, allow_private)
        connection = _PinnedConnection(host, port, address, _remaining(deadline), parts.scheme == "https")
        response = None
        watchdog = None
        try:
            target = quote(parts.path or "/", safe="/%:@!$&'()*+,;=-._~")
            if parts.query:
                target += "?" + quote(parts.query, safe="%/:@!$&'()*+,;=?-._~")
            connection.request("GET", target, headers={
                "User-Agent": "SiteAudit-Kit/0.1.0",
                "Accept": "text/html, application/xhtml+xml",
                "Accept-Encoding": "identity",
                "Connection": "close",
            })
            active_socket = connection.sock
            active_socket.settimeout(_remaining(deadline))
            watchdog = threading.Timer(_remaining(deadline), _interrupt_socket, args=(active_socket,))
            watchdog.daemon = True
            watchdog.start()
            response = connection.getresponse()
            headers = {}
            for key, value in response.getheaders():
                key = key.lower()
                headers[key] = headers[key] + ", " + value if key in headers else value
            if response.status in {301, 302, 303, 307, 308}:
                if hop == max_redirects:
                    raise FetchError("redirect limit exceeded")
                location = headers.get("location", "")
                if not location:
                    raise FetchError("redirect has no Location header")
                destination = urljoin(current, location)
                next_parts, _, _ = validate_url(destination)
                if parts.scheme == "https" and next_parts.scheme == "http":
                    raise FetchError("HTTPS-to-HTTP redirects are blocked")
                current = destination
                continue
            if not 200 <= response.status < 300:
                raise FetchError(f"HTTP status {response.status}")
            content_type = headers.get("content-type", "")
            if content_type.partition(";")[0].strip().lower() not in {"text/html", "application/xhtml+xml"}:
                raise FetchError("response must declare an HTML Content-Type")
            if headers.get("content-encoding", "identity").strip().lower() not in {"", "identity"}:
                raise FetchError("server returned compressed content despite Accept-Encoding: identity")
            length = headers.get("content-length")
            if length:
                try:
                    declared = int(length)
                except ValueError as exc:
                    raise FetchError("invalid Content-Length header") from exc
                if declared < 0 or declared > max_bytes:
                    raise FetchError("response exceeds byte budget or has invalid length")
            data = bytearray()
            while not response.isclosed():
                active_socket.settimeout(_remaining(deadline))
                chunk = response.read1(min(65536, max_bytes + 1 - len(data)))
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > max_bytes:
                    raise FetchError("response exceeds byte budget")
            _remaining(deadline)
            if length and len(data) != int(length):
                raise FetchError("response ended before Content-Length bytes were received")
            match = re.search(r"charset\s*=\s*[\"']?([^;\s\"']+)", content_type, re.I)
            charset = match.group(1) if match else "utf-8-sig"
            try:
                html = data.decode(charset, errors="replace")
            except LookupError as exc:
                raise FetchError("unsupported response character encoding") from exc
            return FetchedPage(current, html, headers, response.status, len(data))
        except FetchError:
            raise
        except (OSError, http.client.HTTPException) as exc:
            raise FetchError(f"request failed: {type(exc).__name__}") from exc
        finally:
            # response may own the socket when the server closes each connection.
            if watchdog is not None:
                watchdog.cancel()
            if response is not None:
                response.close()
            connection.close()
    raise FetchError("redirect limit exceeded")
