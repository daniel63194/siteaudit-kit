import json
import unittest

from siteaudit_kit import audit_html
from siteaudit_kit.reporting import html_report, render, sarif_report, text_report


class ReportingTests(unittest.TestCase):
    def test_json_is_deterministic_and_has_schema(self):
        report = audit_html('<img src="x">', source="index.html")
        output = render(report, "json")
        self.assertEqual(output, render(audit_html('<img src="x">', source="index.html"), "json"))
        self.assertEqual(json.loads(output)["schema_version"], 1)

    def test_html_report_escapes_untrusted_source_and_evidence(self):
        report = audit_html('<img src="x&quot;&gt;&lt;script&gt;alert(1)&lt;/script&gt;">',
                            source='<script>alert("source")</script>')
        output = html_report(report)
        self.assertNotIn("<script>", output)
        self.assertIn("&lt;script&gt;", output)
        self.assertIn('default-src', output)

    def test_terminal_report_removes_control_characters(self):
        report = audit_html('<img src="\x1b[2J">', source="\x1b[2Jfile.html")
        self.assertNotIn("\x1b", text_report(report))

    def test_sarif_rule_indices_locations_and_fingerprints(self):
        report = audit_html('\n<img>', source="build/my file.html")
        sarif = sarif_report(report)
        self.assertEqual(sarif["version"], "2.1.0")
        run = sarif["runs"][0]
        for result in run["results"]:
            self.assertEqual(run["tool"]["driver"]["rules"][result["ruleIndex"]]["id"], result["ruleId"])
            self.assertEqual(result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"], "build/my%20file.html")
            self.assertEqual(len(result["partialFingerprints"]["siteaudit/v1"]), 64)

    def test_baseline_suppression_in_sarif(self):
        report = audit_html("<img>")
        report.apply_baseline(report.baseline())
        for result in sarif_report(report)["runs"][0]["results"]:
            self.assertEqual(result["baselineState"], "unchanged")
            self.assertEqual(result["suppressions"][0]["status"], "accepted")

    def test_baseline_survives_line_insertions(self):
        before = audit_html("<img>")
        after = audit_html("\n\n<img>")
        after.apply_baseline(before.baseline())
        self.assertFalse(after.fails("info"))

    def test_baseline_counts_duplicate_occurrences(self):
        before = audit_html("<button></button>")
        after = audit_html("<button></button><button></button>")
        after.apply_baseline(before.baseline())
        self.assertTrue(after.fails())
        self.assertEqual(sum(f.rule_id == "A11Y003" and f.is_new for f in after.findings), 1)

    def test_full_json_report_as_baseline(self):
        report = audit_html("<img>")
        report.apply_baseline(report.to_dict())
        self.assertFalse(report.fails("info"))

    def test_baseline_validation(self):
        for payload in ([], {"schema_version": 2}, {"schema_version": 1, "fingerprints": ["bad"]},
                        {"schema_version": 1, "findings": [None]}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                audit_html("").apply_baseline(payload)

    def test_severity_gate(self):
        report = audit_html('<html lang="en"><head><title>A descriptive page title</title></head><body><h1>Hi</h1></body></html>')
        self.assertFalse(report.fails("error"))
        self.assertTrue(report.fails("warning"))
        self.assertFalse(report.fails("none"))
        with self.assertRaises(ValueError):
            report.fails("unknown")

    def test_unknown_format(self):
        with self.assertRaises(ValueError):
            render(audit_html(""), "unknown")
