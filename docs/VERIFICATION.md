# Local verification

Verified on 11 October 2026 using Python 3.12.14 on Linux.

- All 66 standard-library tests passed.
- Every one of the 24 rule IDs is exercised by triggering fixtures.
- Fetch tests cover local HTTP, redirects, address restrictions, pinned TLS
  hostname handling, response size, encoding, truncation, and timeouts.
- Report tests cover deterministic JSON, HTML escaping, terminal control
  characters, SARIF structure, baselines, and duplicate occurrence counts.
- CLI tests cover report formats, output files, severity gates, baselines,
  local response headers, invalid inputs, version, and the rule catalog.
- Both a wheel and a source distribution built and installed successfully.
- Each distribution was imported and used to audit the clean example from
  a separate target directory, outside the source checkout.
- The installed console command passed the clean fixture at `--fail-on info`.
- The agent adapter produced valid JSON with a version-1 audit payload.
- GitHub workflow and composite-action YAML parsed successfully; CI's event
  configuration and read-only contents permission were checked.

GitHub-hosted CI, Windows, and other Python versions have not yet been executed
for this repository. The included CI matrix is configured to run those checks
after publication. SARIF has been structure-tested, not uploaded to GitHub
code scanning in this environment. Public live URLs were not used in tests.

No OpenSSF Criticality Score was collected: there is no published repository
URL for this bundle. No particular score or adoption is claimed.
