"""Deterministic, evidence-based checks on a single HTML document."""

import re
from urllib.parse import urljoin, urlsplit

from .dom import Document, Node
from .models import Finding, Report
from .rules import HEADER_RULES, RULES, URL_RULES


def audit_html(html: str, *, source: str = "document.html", url: str | None = None,
               headers: dict[str, str] | None = None, ignore=()) -> Report:
    """Audit source HTML. HTTP checks are skipped unless headers/url are supplied.

    No JavaScript execution, crawling, or network requests occur in this function.
    Names and labels are static heuristics, not a full accessible-name algorithm.
    """
    ignored = set(ignore)
    unknown = ignored - RULES.keys()
    if unknown:
        raise ValueError("unknown ignored rule IDs: " + ", ".join(sorted(unknown)))
    if len(html.encode("utf-8")) > 8 * 1024 * 1024:
        raise ValueError("HTML exceeds the library's 8 MiB parser budget")
    if headers is not None and (not isinstance(headers, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in headers.items()
    )):
        raise ValueError("headers must be a mapping of string names to string values")
    document = Document(html)
    report = Report(source)
    scheme = urlsplit(url).scheme.lower() if url else ""
    if url and (scheme not in {"http", "https"} or not urlsplit(url).hostname):
        raise ValueError("url must be an absolute HTTP or HTTPS URL")
    available = set(RULES) - ignored
    if headers is None:
        available -= HEADER_RULES
    if not url:
        available -= URL_RULES
    if scheme != "https":
        available.discard("SEC006")
    report.checks_run = sorted(available)
    report.checks_skipped = sorted(set(RULES) - available)
    nodes = document.nodes

    def find(tag):
        return [n for n in nodes if n.tag == tag]

    def emit(rule_id, message, node: Node | None = None, evidence=None):
        if rule_id in available:
            report.findings.append(Finding.from_rule(
                RULES[rule_id], source=source, message=message,
                line=node.line if node else 1,
                evidence=evidence if evidence is not None else node.evidence() if node else "document",
            ))

    head_nodes = [n for n in nodes if n.has_ancestor("head")]
    titles = [n for n in head_nodes if n.tag == "title"]
    if not titles or not titles[0].text():
        emit("SEO001", "The document head has no non-empty title.")
    elif not 15 <= len(titles[0].text()) <= 70:
        emit("SEO002", f"The title contains {len(titles[0].text())} characters.", titles[0])
    meta = {n.attrs.get("name", "").lower(): n for n in head_nodes if n.tag == "meta"}
    if "description" not in meta or not meta["description"].attrs.get("content", "").strip():
        emit("SEO003", "No non-empty meta description was found in the head.")
    if not any(n.tag == "link" and "canonical" in n.attrs.get("rel", "").lower().split()
               and n.attrs.get("href", "").strip() for n in head_nodes):
        emit("SEO004", "The document has no canonical link in the head.")
    h1 = [n for n in find("h1") if not n.is_hidden()]
    if not h1:
        emit("SEO005", "No visible primary heading was found.")
    elif len(h1) > 1:
        emit("SEO006", f"Found {len(h1)} primary headings.", h1[1])
    roots = find("html")
    if not roots or not roots[0].attrs.get("lang", "").strip():
        emit("A11Y001", "The html element has no non-empty lang attribute.", roots[0] if roots else None)
    viewport = meta.get("viewport")
    if not viewport or not viewport.attrs.get("content", "").strip():
        emit("HTML002", "No non-empty viewport meta tag was found in the head.")
    counts = {}
    previous_heading = 0
    for node in nodes:
        if node.attrs.get("id"):
            ident = node.attrs["id"]
            counts[ident] = counts.get(ident, 0) + 1
            if counts[ident] > 1:
                emit("HTML001", f"The ID {ident!r} appears more than once.", node)
        if node.is_hidden():
            continue
        if node.tag == "img":
            if "alt" not in node.attrs and node.attrs.get("role", "").lower() not in {"presentation", "none"}:
                emit("A11Y002", "The image has no alt attribute.", node)
            if not all(re.fullmatch(r"[1-9][0-9]*", node.attrs.get(a, "")) for a in ("width", "height")):
                emit("PERF001", "No positive integer width/height pair was found in the source.", node)
        if node.tag == "button" or (node.tag == "input" and node.attrs.get("type", "").lower()
                                    in {"button", "submit", "reset", "image"}):
            if not document.named(node):
                emit("A11Y003", "The static markup provides no detected name for this button.", node)
        elif node.tag in {"input", "select", "textarea"}:
            if node.attrs.get("type", "").lower() != "hidden" and not document.labelled_control(node):
                emit("A11Y005", "No non-empty associated label or name was found.", node)
        if node.tag == "a" and "href" in node.attrs and not document.named(node):
            emit("A11Y004", "The link contains no detected descriptive text or name.", node)
        if re.fullmatch(r"h[1-6]", node.tag):
            level = int(node.tag[1])
            if previous_heading and level > previous_heading + 1:
                emit("A11Y006", f"Heading level jumps from h{previous_heading} to h{level}.", node)
            previous_heading = level
        if (node.tag == "script" and node.attrs.get("src") and node.has_ancestor("head")
            and not any(a in node.attrs for a in ("defer", "async"))
            and node.attrs.get("type", "").strip().lower() in {"", "text/javascript", "application/javascript"}):
            emit("PERF002", "A classic external script in head has neither defer nor async.", node)
    byte_count = len(html.encode("utf-8"))
    if byte_count > 200 * 1024:
        emit("PERF003", f"Decoded HTML is {byte_count:,} UTF-8 bytes.")
    if scheme == "http":
        emit("SEC001", "The page URL uses HTTP.", evidence="transport:http")
    bases = [n.attrs["href"] for n in head_nodes if n.tag == "base" and n.attrs.get("href")]
    resource_base = urljoin(url, bases[0]) if url and bases else url
    for node in nodes:
        # A form action is checked even if the form is hidden.
        if node.tag == "form" and url:
            # Empty/missing action submits to the document URL, not the base element.
            action = node.attrs.get("action", "").strip()
            target = urljoin(resource_base, action) if action else url
            if urlsplit(target).scheme.lower() == "http":
                emit("SEC003", "The form's resolved action uses HTTP.", node)
        if scheme != "https":
            continue
        resources = []
        if node.tag in {"script", "img", "iframe", "audio", "video", "source", "embed", "track", "input"}:
            if node.attrs.get("src"):
                resources.append(node.attrs["src"])
        if node.tag == "object" and node.attrs.get("data"):
            resources.append(node.attrs["data"])
        if node.tag == "video" and node.attrs.get("poster"):
            resources.append(node.attrs["poster"])
        if node.tag == "link" and set(node.attrs.get("rel", "").lower().split()) & {"stylesheet", "preload", "modulepreload"}:
            resources.append(node.attrs.get("href", ""))
        if node.tag in {"img", "source"} and node.attrs.get("srcset"):
            # Extract HTTP candidates without splitting commas inside a data URI.
            resources.extend(re.findall(r"(?:^|[\s,])(https?://[^\s,]+)", node.attrs["srcset"], re.I))
        for resource in dict.fromkeys(resources):
            if resource and urlsplit(urljoin(resource_base, resource)).scheme.lower() == "http":
                emit("SEC002", "The page embeds an HTTP resource.", node,
                     evidence=node.evidence() + " resource=" + resource[:240])
    if headers is not None:
        normalized = {k.lower(): v.strip() for k, v in headers.items()}
        csp = normalized.get("content-security-policy", "")
        meta_csp = any(n.tag == "meta" and n.attrs.get("http-equiv", "").lower() == "content-security-policy"
                       and n.attrs.get("content", "").strip() for n in head_nodes)
        if not csp and not meta_csp:
            emit("SEC004", "No enforced CSP HTTP header or CSP meta tag was found.", evidence="header:csp")
        if normalized.get("x-content-type-options", "").lower() != "nosniff":
            emit("SEC005", "X-Content-Type-Options is absent or not nosniff.", evidence="header:nosniff")
        hsts = normalized.get("strict-transport-security", "")
        max_age = re.search(r"(?:^|;)\s*max-age\s*=\s*([0-9]+)\s*(?:;|$)", hsts, re.I)
        if not max_age or not max_age.group(1).lstrip("0"):
            emit("SEC006", "No positive HSTS max-age was found.", evidence="header:hsts")
        framing = re.search(r"(?:^|[;,])\s*frame-ancestors\s+[^;,]+", csp, re.I)
        xfo = normalized.get("x-frame-options", "").upper()
        if not framing and xfo not in {"DENY", "SAMEORIGIN"}:
            emit("SEC007", "No frame-ancestors directive or recognized X-Frame-Options value was found.",
                 evidence="header:framing")
    report.findings.sort(key=lambda f: (f.rule_id, f.line, f.evidence))
    return report
