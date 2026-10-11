# SiteAudit Kit

**Small website checks with evidence you can act on.**

SiteAudit Kit is a Python library, command-line tool, and GitHub composite action
for auditing HTML. It turns common website mistakes into reproducible findings
with stable rule IDs, source lines, evidence, references, and suggested fixes.

Use it on a generated HTML file before deployment, on a live page during review,
or as the deterministic checking layer inside an AI website assistant. It runs
without API keys, LLM calls, telemetry, or runtime dependencies.

## Quick start

Requires Python 3.10 or newer. From this source repository:

```bash
python -m pip install .
siteaudit examples/clean.html
siteaudit examples/problematic.html --format html --output report.html --fail-on none
siteaudit https://example.org --format json --output report.json
```

The second command produces a readable, self-contained report with no external
fonts, assets, or JavaScript. The deliberately problematic fixture demonstrates
the findings. A public package name has not been reserved or published yet.

You can also run straight from source without installing:

```bash
PYTHONPATH=src python -m siteaudit_kit examples/clean.html
```

For Windows PowerShell, set `$env:PYTHONPATH = "src"` before running
`python -m siteaudit_kit examples/clean.html`.

## What it checks

| Area | Checks |
| --- | --- |
| Accessibility | Document language, image alt attributes, button/link names, form labels, heading jumps |
| SEO | Title, title-length advice, description, canonical URL, primary headings |
| HTML | Duplicate IDs, viewport metadata |
| Performance | Image dimensions, blocking head scripts, HTML size budget |
| Security | HTTP transport, mixed embedded resources, HTTP form submissions, CSP, nosniff, HSTS, framing headers |

Run `siteaudit --list-rules` for all **24 rules**, or see the [rule catalog](docs/RULES.md).
Advice such as title length, canonical URLs, or image dimensions is explicitly
heuristic. Empty `alt=""` is valid for decorative images. Module, async, and defer
scripts are excluded from the blocking-script check.

HTTP-header checks are skipped for local HTML unless you supply captured headers.
The report always lists the checks that ran and those that were skipped or ignored.

```bash
siteaudit examples/clean.html \
  --base-url https://example.org/garden \
  --headers examples/headers.json \
  --fail-on info
```

## Use it in a Python application

```python
from siteaudit_kit import audit_html, fetch_url

page = fetch_url("https://example.org", timeout=10, max_bytes=1_048_576)
report = audit_html(page.html, source=page.url, url=page.url, headers=page.headers)

for finding in report.findings:
    print(finding.rule_id, finding.line, finding.message, finding.fix)

payload = report.to_dict()  # JSON-serializable, schema_version 1
```

`audit_html()` itself performs no network operations. This makes it easy to use
with HTML your application already fetched or generated. See
[the agent adapter](examples/agent_adapter.py) and [API guide](docs/API.md).
Treat extracted markup as untrusted data when passing it to an LLM.

## Prevent new issues with baselines

Accept existing findings deliberately, then make CI fail only on new ones:

```bash
siteaudit examples/problematic.html --write-baseline baseline.json --fail-on none
siteaudit examples/problematic.html --baseline baseline.json --fail-on warning
```

Baselines preserve occurrence counts: introducing a second identical broken
button still counts as a new finding. Line-number changes do not invalidate
accepted findings. Source paths and evidence must remain consistent; changing
the path, source attributes, or evidence can create a new fingerprint.

An ordinary JSON report can also be used as a baseline. Updating a baseline is
an explicit maintenance decision, not an automatic step in the CI workflow.

| Exit status | Meaning |
| --- | --- |
| `0` | No new findings at or above the requested severity |
| `1` | New findings reached `--fail-on` (default: `error`) |
| `2` | Invalid input, file error, unsafe URL, failed fetch, or exceeded budget |

`--fail-on none` disables finding-based failure; operational errors still return `2`.
Use `--ignore SEO004,PERF001` when a rule does not fit your project.

## GitHub and CI

The included [CI workflow](.github/workflows/ci.yml) tests Python 3.10–3.14 on
Linux and Windows. Actions are pinned to commit hashes, and Dependabot is
configured to update those pins. These workflows have to run on GitHub after
you publish the repository; local verification covers Python 3.12.

This repository includes a composite action in [action.yml](action.yml). After
checkout, a workflow in this repository can run:

```yaml
- name: Audit generated HTML
  uses: ./
  with:
    target: examples/clean.html
    format: sarif
    output: siteaudit.sarif
    fail-on: warning
```

For another repository, reference the published repository at a reviewed commit
SHA. SARIF output can be uploaded with GitHub's CodeQL upload action if code
scanning is enabled. The composite action writes the report and gates the build;
it does not upload results or require security-events permissions.

JSON, SARIF, HTML, and text reports can also be generated directly with the CLI.
SARIF locations are most useful for local files checked into the repository;
live URL findings may not map to a GitHub source file.

## Fetching behavior

One page is requested, plus up to five redirects. Embedded assets are examined
as markup and are not fetched. Requests have a byte budget and time budget.
Private, loopback, link-local, reserved, multicast, mixed public/private DNS,
and supported IPv6 tunnel/translation destinations are blocked by default.
Each redirect is validated; connections use the validated IP with the original
hostname for TLS verification. HTTPS-to-HTTP redirects are blocked.

For your trusted local development server:

```bash
siteaudit http://127.0.0.1:8000 --allow-private
```

There are no cookies, authenticated sessions, retries, or proxy support. HTML
responses must declare an HTML Content-Type. Compression is not supported;
the client requests an identity response and rejects servers that ignore it.
OS DNS resolution can exceed the configured time budget before it returns.
See [SECURITY.md](SECURITY.md) before embedding the fetcher in a public service.

## Limits

This is a source-HTML linter, not a browser audit. It does not render JavaScript,
measure Core Web Vitals, inspect CSS contrast or layout, crawl a website, check
links, validate all HTML, or implement the full accessible-name computation.
Header presence does not establish a secure configuration. Browser-based and
manual accessibility tests remain necessary.

The parser recovers from some common unclosed tags but does not implement the
HTML5 tree-building algorithm. Findings describe the supplied source, not the
final rendered DOM. Local files must be UTF-8; fetched documents use a declared
HTTP charset or UTF-8. Node, nesting, and byte limits keep work bounded.

## Develop and contribute

```bash
python -m pip install .
python -m unittest discover -s tests -v
```

Tests use only the standard library and a local test server. They need no
external network access or API credentials. Good first contributions include
false-positive fixtures, static-generator integrations, additional documented
rules, and framework-specific usage examples. See [CONTRIBUTING.md](CONTRIBUTING.md).

The project is MIT licensed. Version 0.1.0 is an initial implementation;
the [roadmap](docs/ROADMAP.md) lists proposals rather than promised features.

## OpenSSF criticality

A newly created project has no verified OpenSSF Criticality Score. A score of
0.4 cannot be promised from source quality or repository setup alone. The
Criticality Score measures ecosystem influence using repository and community
signals; OpenSSF Scorecard separately evaluates security practices.

See [the launch and measurement guide](docs/LAUNCH.md) for publishing steps,
genuine adoption work, current official references, and score measurement.
There is intentionally no unverified score badge in this README.
