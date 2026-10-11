# Contributing

SiteAudit Kit welcomes useful changes supported by real examples. An especially
valuable contribution is a small HTML fixture showing a false positive or
missing check, with the expected behavior explained.

## Setup

```bash
python -m venv .venv
```

Activate with `source .venv/bin/activate` on Linux/macOS or
`.venv\Scripts\Activate.ps1` in Windows PowerShell, then:

```bash
python -m pip install .
python -m unittest discover -s tests -v
```

After editing source, install again before testing, or set `PYTHONPATH=src`
(`$env:PYTHONPATH = "src"` in PowerShell). All tests use the standard library.
The fetch tests bind a local test server and never contact a public website.

## Submit a change

1. Open an issue with a reproducible example for a substantial feature or behavior change.
2. Keep each pull request focused on one problem.
3. Add a regression test when changing detection, reporting, or fetching behavior.
4. Run the test suite and exercise the relevant CLI behavior.
5. Describe the trigger, resulting behavior, and validation in the pull request.

Documentation improvements and small fixes do not need an issue first.
Do not include secrets, customer HTML, or personally identifying fixture data.

## Rules and compatibility

Rule IDs are part of the public API. Preserve them when improving detection;
use a new ID for a substantially different check. Each rule must have a specific
fix, a primary reference, an appropriate severity, and tests for both triggering
and non-triggering cases. Advisory checks should say what cannot be inferred.

Prefer zero runtime dependencies and deterministic behavior. Do not make
`audit_html()` fetch URLs or execute JavaScript. Changes to the fetcher's safety
boundaries need explicit tests. JSON consumers depend on `schema_version`;
incompatible schema changes must increment it. Baseline fingerprints omit line
numbers by design and preserve duplicate counts.

Update the rule catalog with:

```bash
python scripts/update_rule_docs.py
```

Tests, docs, and examples are welcome from beginners. Proposed starting tasks
are listed in [docs/ROADMAP.md](docs/ROADMAP.md); these are proposals, not open
issues or claims that contributors are already working on them.

By submitting a contribution, you agree to license it under this project's MIT
license. Follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Report security issues
using [SECURITY.md](SECURITY.md).
