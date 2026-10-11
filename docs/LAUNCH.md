# Publishing and measuring project impact

## What the 0.4 target means

OpenSSF Criticality Score measures an open-source project's influence and
importance on a 0–1 scale. It is different from OpenSSF Scorecard, which evaluates
security practices. Good tests, a license, a security policy, and CI help make a
project trustworthy, but they do not automatically give it a criticality score
of 0.4.

The current `original_pike.yml` configuration includes these signals:

| Signal | What real project activity contributes |
| --- | --- |
| Project age | A sustained history of useful work |
| Time since update | Ongoing maintenance |
| Contributors | People whose commits are part of the project |
| Organizations | Contributors from distinct organizations |
| Commit frequency | Development over the last year |
| Recent releases | Usable versions released over the last year |
| Updated and closed issues | Recent problem-solving activity |
| Issue comments | Community discussion |
| GitHub mentions | Repository mentions used as a proxy for ecosystem dependence |

Contributor and mention signals each have weight 2 in that configuration.
Stars are not an input in its current scoring configuration. Scores depend on
the collector and configuration used; there is no single required star count,
contributor count, or timeline that guarantees 0.4.

Sources, checked 11 October 2026:

- [OpenSSF Criticality Score](https://openssf.org/projects/criticality-score/)
- [Current upstream README](https://github.com/ossf/criticality_score/blob/main/README.md)
- [Default scoring configuration](https://github.com/ossf/criticality_score/blob/main/config/scorer/original_pike.yml)
- [OpenSSF Scorecard](https://github.com/ossf/scorecard)

The upstream README currently says the public infrastructure has not been
running since May 2026, with its last successful run in July 2025. Its Google
Cloud datasets became unavailable in August 2026, and repository snapshots are
updated infrequently. A new project will not appear in an old snapshot simply
because it has been published. Check how any eligibility program obtains scores
before assuming a newly collected result will be accepted.

## Publish this project

Extract the source bundle and open a terminal inside `siteaudit-kit`.
Review the license and documentation and run the tests:

```bash
python -m pip install .
python -m unittest discover -s tests -v
```

With Git and the GitHub CLI installed and authenticated to your account:

```bash
git init -b main
git add .
git commit -m "Initial SiteAudit Kit implementation"
gh repo create siteaudit-kit --public --source=. --remote=origin --push
```

If Git requests your author identity, configure your real name and a verified
or GitHub-provided private commit email. The project bundle does not invent
contributors or an author identity.

Then:

1. Let CI finish and fix any platform-specific failures before a release.
2. Enable private vulnerability reporting and protect the default branch with reviews and required CI checks.
3. Add a clear description and topics such as `accessibility`, `html`, `sarif`, `seo`, and `python`.
4. Create a real `v0.1.0` release, including examples and the changelog.
5. Decide whether to publish to PyPI; confirm name availability and use trusted publishing if you do.

The package name has not been reserved. No GitHub repository, release, PyPI
publication, or adoption is claimed by this source bundle.

## Build genuine adoption

The useful wedge is deterministic findings that work in CI and are easy for
agents to consume. Start by integrating the library into one real website
workflow. Document the issues it catches, the changes those findings cause,
and the checks it cannot perform.

Share concise, reproducible recipes with communities that need them. Invite
maintainers of other projects to try the library on their generated HTML.
Accept small, useful contributions; respond to real reports; release when
there are fixes users need. Make contributor setup simple and keep rule
behavior predictable.

Repository history should reflect actual work. Do not buy stars, create
alternate contributor accounts, backdate commits, manufacture issues, or split
meaningless changes just to increase metric counts. None of those make this
project useful or establish real dependence.

## Measure instead of assuming

Use the upstream tool's current setup and authentication instructions. The
current README shows this installation command:

```bash
go install github.com/ossf/criticality_score/v2/cmd/criticality_score@latest
```

Collect a fresh result for the actual published repository. Save the repository
URL, collection date, tool version/commit, configuration, individual signals,
and resulting score. Read the tool's `-help` output for current flags and any
optional external-data requirements; do not substitute a custom-weight score
for the default score if a program requires the default.

Only claim **0.4 or above** after the official calculation for your repository
actually reports that result under the required configuration. If an immediate
eligibility threshold is the goal, creating a new repository cannot assure it;
contributing meaningfully to an existing qualifying project may be a better
route, subject to that program's contributor requirements.
