# Proposed roadmap

The initial release is deliberately narrow: one document, static markup,
reproducible findings, no runtime dependencies. These are directions for
discussion, not completed functionality or promises of delivery dates.

## Validate usefulness first

- Collect anonymized fixtures from real static sites and WordPress templates.
- Publish short recipes for Astro, Hugo, Jekyll, Django, and CI-generated HTML.
- Improve false-positive handling for static accessible names and unusual markup.
- Add evidence-focused regression cases before expanding rule count.

## Candidate extensions

- Audit directories of generated HTML while keeping per-file baselines.
- Provide a versioned JSON Schema and machine-readable rule export.
- Allow project-specific rule configuration and severity overrides.
- Add an optional browser adapter for rendered DOM; keep the core dependency-free.
- Add a thin MCP adapter once the core API has real consumers and feedback.

## Contributor-friendly starting work

| Proposal | Useful deliverable |
| --- | --- |
| Static generator recipe | Tested instructions and a small public fixture |
| False-positive investigation | Minimal reproducer and expected result |
| Report portability | SARIF tests using Windows and absolute-path inputs |
| Rule reference upkeep | Updated primary links and accurately scoped descriptions |
| Real integration | A separate project using the library with a reproducible example |

Keep scope tied to real user needs. Additional dependencies, crawling, and
browser rendering deserve a design discussion because they change the security
and execution boundaries.
