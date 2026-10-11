"""Portable terminal, JSON, HTML and SARIF 2.1.0 output."""

from html import escape
import json
import re
from urllib.parse import quote

from .models import Report
from .rules import RULES


def _plain(value: str) -> str:
    # Prevent terminal escape/control injection from untrusted source markup.
    return re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", value)


def text_report(report: Report) -> str:
    data = report.to_dict()
    lines = [f"SiteAudit Kit — {_plain(report.source)}",
             f"{len(report.checks_run)} checks; "
             + ", ".join(f"{n} {s}" for s, n in data["summary"].items())
             + f"; {data['new_findings']} new"]
    for finding in report.findings:
        status = "new" if finding.is_new else "baseline"
        lines.extend([f"\n[{finding.severity.upper()}] {finding.rule_id} ({status}) "
                      f"line {finding.line}: {finding.title}",
                      "  " + _plain(finding.message), "  Fix: " + _plain(finding.fix)])
    if not report.findings:
        lines.append("No findings in the checks that ran.")
    if report.checks_skipped:
        lines.append("\nSkipped/ignored: " + ", ".join(report.checks_skipped))
    lines.append("\nStatic heuristics only; no JavaScript, browser measurements, or WCAG certification.")
    return "\n".join(lines) + "\n"


def sarif_report(report: Report) -> dict:
    rule_ids = sorted({f.rule_id for f in report.findings})
    indices = {rule_id: i for i, rule_id in enumerate(rule_ids)}
    source = report.source.replace("\\", "/")
    if not source.lower().startswith(("http://", "https://", "file://")):
        source = quote(source, safe="/:@-._~")
    results = []
    for finding in report.findings:
        result = {
            "ruleId": finding.rule_id, "ruleIndex": indices[finding.rule_id],
            "level": {"info": "note", "warning": "warning", "error": "error"}[finding.severity],
            "message": {"text": finding.message + " Fix: " + finding.fix},
            "locations": [{"physicalLocation": {
                "artifactLocation": {"uri": source},
                "region": {"startLine": finding.line},
            }}],
            "partialFingerprints": {"siteaudit/v1": finding.fingerprint},
            "baselineState": "new" if finding.is_new else "unchanged",
            "properties": {"category": finding.category, "evidence": finding.evidence},
        }
        if not finding.is_new:
            result["suppressions"] = [{"kind": "external", "status": "accepted", "justification": "Accepted baseline finding"}]
        results.append(result)
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {
            "name": "SiteAudit Kit", "version": "0.1.0",
            "rules": [{"id": ident, "shortDescription": {"text": RULES[ident].title},
                       "helpUri": RULES[ident].reference,
                       "help": {"text": RULES[ident].fix},
                       "properties": {"tags": [RULES[ident].category]}} for ident in rule_ids],
        }}, "results": results}],
    }


def html_report(report: Report) -> str:
    summary = report.to_dict()["summary"]
    rows = []
    for finding in report.findings:
        rows.append(f'''<article class="finding {finding.severity}">
<div class="meta"><span>{escape(finding.rule_id)} · {escape(finding.category)}</span>
<span>{finding.severity.upper()} · {"NEW" if finding.is_new else "BASELINE"} · line {finding.line}</span></div>
<h2>{escape(finding.title)}</h2><p>{escape(finding.message)}</p>
<pre><code>{escape(finding.evidence)}</code></pre>
<p class="fix"><strong>Suggested fix</strong><br>{escape(finding.fix)}</p>
<a href="{escape(finding.reference, quote=True)}" rel="noreferrer">Read the reference ↗</a></article>''')
    stats = "".join(f'<div><b>{n}</b><span>{severity}</span></div>' for severity, n in summary.items())
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>SiteAudit Kit report</title><style>
:root{{font-family:system-ui,sans-serif;color:#18261f;background:#f4f5ef;line-height:1.55}}
body{{margin:0}}main{{max-width:920px;margin:auto;padding:48px 24px}}
.label{{font-size:12px;letter-spacing:2px;font-weight:700;color:#3d6651}}
h1{{font-size:clamp(32px,5vw,48px);line-height:1.15;letter-spacing:-1.5px;margin:16px 0}}
.source{{overflow-wrap:anywhere;color:#46584b}}.stats{{display:flex;gap:32px;padding:24px 0;border-top:1px solid #cfd6cb;border-bottom:1px solid #cfd6cb;margin:28px 0}}
.stats b{{display:block;font-size:32px;line-height:1.1}}.stats span{{font-size:13px}}
.finding{{background:#fff;padding:24px;margin:16px 0;border:1px solid #d9dfd5;border-left:4px solid #9baf9f}}
.error{{border-left-color:#bc3b2a}}.warning{{border-left-color:#ad791b}}
.meta{{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;font-size:12px;color:#59645b}}
h2{{font-size:21px;line-height:1.3}}p{{margin:12px 0}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f5ef;padding:12px;font-size:13px}}
a{{color:#215d3c}}.fix{{color:#344f3d}}footer{{font-size:13px;color:#5c675d;margin-top:32px}}
</style></head><body><main><div class="label">SITEAUDIT KIT / STATIC AUDIT</div>
<h1>Small checks.<br>Actionable findings.</h1><p class="source">{escape(report.source)}</p>
<div class="stats">{stats}<div><b>{sum(f.is_new for f in report.findings)}</b><span>new findings</span></div></div>
{''.join(rows) or '<p>No findings in the checks that ran.</p>'}
<footer>{len(report.checks_run)} checks ran. Skipped/ignored: {escape(', '.join(report.checks_skipped)) or 'none'}.<br>
Static heuristics only. This report does not execute JavaScript, measure page speed, prove security, or certify WCAG compliance.</footer>
</main></body></html>'''


def render(report: Report, format: str) -> str:
    if format == "text":
        return text_report(report)
    if format == "html":
        return html_report(report)
    if format == "json":
        return json.dumps(report.to_dict(), ensure_ascii=True, indent=2) + "\n"
    if format == "sarif":
        return json.dumps(sarif_report(report), ensure_ascii=True, indent=2) + "\n"
    raise ValueError("unknown report format")
