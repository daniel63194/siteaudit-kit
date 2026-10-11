# Security

Version 0.1.x is the initial development series. Security reports should include
the affected version, a minimal reproduction, the expected boundary, and the
observed result. Avoid sensitive production data.

After this repository is published, enable GitHub private vulnerability reporting
under **Settings → Code security**. Use **Security → Advisories → Report a
vulnerability** when that route is available. If it is unavailable, open a public
issue titled **Request for private security contact**, without exploit details,
credentials, or sensitive URLs, so the maintainer can provide a private channel.

## Intended boundaries

- `audit_html()` analyzes supplied text without network or script execution.
- `fetch_url()` accepts HTTP/HTTPS only, rejects embedded credentials, validates
  all resolved addresses, and pins each connection to a validated literal IP.
- Every redirect is validated, and HTTPS-to-HTTP downgrades are blocked.
- Public fetching blocks non-global and selected tunnel/translation destinations.
- Body size, redirect count, node count, nesting, and HTTP time are bounded.
- TLS uses Python's default certificate verification and the original hostname.
- HTML reports escape source data and include a restrictive CSP. Reports do not
  execute scripts or load remote assets. Terminal reports remove control characters.

## Embedding in a service

The CLI is intended for developer-controlled targets. If you expose arbitrary
user URL fetching in a service, enforce network-level egress controls as well.
Host networking, NAT, internal routes, DNS configurations, or future address
allocations can undermine IP-based classifications. Deny access to metadata
endpoints, internal services, and networks your service should never contact.
Keep Python patched; address classifications come partly from `ipaddress`.

`--allow-private` disables address restrictions, including those for local and
metadata destinations. Use it only for trusted development targets. Do not let
an untrusted user choose it. Cookies, credentials, and proxies are not supported.

The HTTP/TLS/read budget shares a deadline and a socket watchdog during response
processing. OS DNS resolution is synchronous and cannot be interrupted by that
watchdog. Run the fetcher in a separately bounded worker if a strict wall-clock
limit is required. Responses with unsupported compression or non-HTML media
types are rejected rather than silently parsed.

## Reports and agents

Finding evidence can contain user-controlled strings. JSON and SARIF consumers
must escape strings when displaying them. If an LLM consumes evidence, treat it
as untrusted data and do not grant it authority to change instructions or tools.
Presence-based header checks are advice, not proof of a secure website.
