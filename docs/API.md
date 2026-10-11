# API and output

## Audit supplied HTML

```python
from siteaudit_kit import audit_html

report = audit_html(
    "<html><head></head><body><img src='photo.jpg'></body></html>",
    source="public/index.html",
    url="https://example.org/",
    headers={"X-Content-Type-Options": "nosniff"},
    ignore=["SEO004"],
)
```

`source` identifies the input in reports and fingerprints. It defaults to
`document.html`. Keep it consistent between baseline creation and CI runs.
`url` enables transport, form-action, and embedded-resource URL checks.
`headers=None` skips checks requiring HTTP headers; an empty dict means headers
were inspected and none were present. `ignore` accepts known rule IDs only.

The result is a `Report` with `findings`, `checks_run`, and `checks_skipped`.
Each `Finding` contains `rule_id`, `category`, `severity`, `title`, `message`,
`fix`, `reference`, `source`, `line`, `evidence`, `fingerprint`, and `is_new`.
Lines are one-based; document-level and header findings use line 1.

The parser accepts at most 8 MiB of UTF-8-equivalent HTML, 100,000 elements,
and approximately 512 levels of nesting. Exceeding a limit raises `ValueError`.
The default CLI input/download limit is lower, at 2 MiB.

## Fetch HTML explicitly

```python
from siteaudit_kit import fetch_url

page = fetch_url(
    "https://example.org/",
    timeout=15,
    max_bytes=2_097_152,
    max_redirects=5,
    allow_private=False,
)
```

Returns a `FetchedPage` with final `url`, decoded `html`, lowercase `headers`,
HTTP `status`, and downloaded `size_bytes`. Fetch failures raise `FetchError`,
a subclass of `ValueError`. Redirects are limited to ten if explicitly
configured; timeout must be positive, finite, and at most 120 seconds.

The byte limit counts the identity-encoded response body. The HTML size advisory
counts bytes after decoding and re-encoding as UTF-8, so these values can differ.
No browser encoding-sniffing algorithm is implemented. UTF-8 is the fallback.

## Format reports

```python
from siteaudit_kit.reporting import render

json_text = render(report, "json")
html_text = render(report, "html")
sarif_text = render(report, "sarif")
terminal_text = render(report, "text")
```

JSON has `schema_version: 1`, `source`, `summary`, `new_findings`, `checks_run`,
`checks_skipped`, and `findings`. Summary counts include accepted baseline
findings. `new_findings` counts only those not accepted by the baseline.
No audit percentage or OpenSSF score is computed.

SARIF uses stable rule IDs and `siteaudit/v1` partial fingerprints. Accepted
findings have `baselineState: unchanged` and an external accepted suppression.
Otherwise findings are marked new. The tool reports one document per run.

## Baselines and gates

```python
accepted = report.baseline()
next_report = audit_html("<html></html>", source="public/index.html")
next_report.apply_baseline(accepted)
should_fail = next_report.fails("warning")
```

A baseline is `{"schema_version": 1, "fingerprints": [...]}`. Full version-1
JSON reports can also be loaded. The fingerprint is SHA-256 of the rule ID,
source identifier, and a bounded evidence string; line numbers are excluded.
Fingerprints match by occurrence count, not just set membership.

Evidence changes or source-path changes can create new findings. For document
and header checks, stable evidence keys deliberately allow updated wording to
remain accepted. This is an acceptance mechanism, not a semantic source diff.
Changing the evidence or rule semantics in a future release may require review
and regeneration of a baseline.
