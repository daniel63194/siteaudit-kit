from pathlib import Path
import unittest

from siteaudit_kit import audit_html
from siteaudit_kit.rules import RULES

ROOT = Path(__file__).resolve().parents[1]
CLEAN = (ROOT / "examples/clean.html").read_text(encoding="utf-8")


def rule_ids(html, **kwargs):
    return {f.rule_id for f in audit_html(html, **kwargs).findings}


class AuditTests(unittest.TestCase):
    def test_clean_document(self):
        self.assertEqual(audit_html(CLEAN).findings, [])

    def test_problematic_document_has_actionable_locations(self):
        report = audit_html((ROOT / "examples/problematic.html").read_text(encoding="utf-8"),
                            url="https://example.org", headers={})
        expected = {"A11Y001", "A11Y002", "A11Y003", "A11Y004", "A11Y005", "A11Y006",
                    "HTML001", "HTML002", "SEO002", "SEO003", "SEO004", "PERF001", "PERF002",
                    "SEC002", "SEC003", "SEC004", "SEC005", "SEC006", "SEC007"}
        self.assertEqual({f.rule_id for f in report.findings}, expected)
        image = next(f for f in report.findings if f.rule_id == "A11Y002")
        self.assertEqual(image.line, 12)
        self.assertIn("<img", image.evidence)
        self.assertTrue(image.fix and image.reference)

    def test_every_rule_is_exercised(self):
        html = '<html><head></head><body><h1>x</h1><h1>y</h1><h3>z</h3><img><button></button><a href="/"></a><input><p id="a"></p><p id="a"></p><script></script></body></html>'
        reports = [audit_html(html + " " * 210_000, url="http://example.org", headers={}),
                   audit_html((ROOT / "examples/problematic.html").read_text(encoding="utf-8"),
                              url="https://example.org", headers={}), audit_html("", url="https://example.org")]
        self.assertEqual({f.rule_id for r in reports for f in r.findings}, set(RULES))

    def test_local_header_and_url_checks_are_skipped(self):
        report = audit_html(CLEAN)
        self.assertTrue({"SEC001", "SEC002", "SEC003", "SEC004", "SEC005", "SEC006", "SEC007"}
                        <= set(report.checks_skipped))

    def test_protective_headers_are_case_insensitive(self):
        headers = {"CONTENT-SECURITY-POLICY": "default-src 'self'; FRAME-ANCESTORS 'none'",
                   "X-Content-Type-Options": "NoSniff", "Strict-Transport-Security": "max-age = 300"}
        self.assertEqual(audit_html(CLEAN, url="https://example.org", headers=headers).findings, [])

    def test_hsts_zero_does_not_pass(self):
        self.assertIn("SEC006", rule_ids(CLEAN, url="https://example.org", headers={"strict-transport-security": "max-age=0"}))

    def test_report_only_csp_does_not_pass(self):
        self.assertIn("SEC004", rule_ids(CLEAN, headers={"Content-Security-Policy-Report-Only": "default-src 'self'"}))

    def test_meta_csp_does_not_provide_frame_ancestors(self):
        html = CLEAN.replace("</head>", '<meta http-equiv="Content-Security-Policy" content="default-src &apos;self&apos;; frame-ancestors &apos;none&apos;"></head>')
        ids = rule_ids(html, headers={})
        self.assertNotIn("SEC004", ids)
        self.assertIn("SEC007", ids)

    def test_decorative_and_presentation_images(self):
        self.assertNotIn("A11Y002", rule_ids('<img alt=""><img role="presentation"><img role="none">'))

    def test_button_names_from_text_aria_svg_image_and_title(self):
        html = '''<span id="name" hidden>Buy now</span>
        <button aria-labelledby="name"><span aria-hidden="true">+</span></button>
        <button aria-label="Save"></button><button><svg><title>Close</title></svg></button>
        <button><img alt="Help"></button><button title="Menu"></button><button>Next</button>
        <input type="submit"><input type="reset"><input type="button" value="Go"><input type="image" alt="Find">'''
        self.assertNotIn("A11Y003", rule_ids(html))

    def test_aria_hidden_content_does_not_name_button(self):
        self.assertIn("A11Y003", rule_ids('<button><span aria-hidden="true">x</span></button>'))

    def test_labels_explicit_implicit_and_aria(self):
        html = '''<label for="a">Email</label><input id="a">
        <label>Name <input></label><input aria-label="Phone"><span id="b">City</span>
        <select aria-labelledby="b"></select><textarea title="Message"></textarea>
        <input type="hidden">'''
        self.assertNotIn("A11Y005", rule_ids(html))

    def test_empty_and_broken_labels_do_not_pass(self):
        html = '<label for="a"></label><input id="a" placeholder="Name"><input aria-labelledby="missing">'
        self.assertEqual(sum(f.rule_id == "A11Y005" for f in audit_html(html).findings), 2)

    def test_hidden_and_inert_controls_do_not_raise_accessibility_findings(self):
        html = '<div hidden><button></button><input></div><template><img><input></template><noscript><img></noscript>'
        self.assertFalse({"A11Y002", "A11Y003", "A11Y005"} & rule_ids(html))

    def test_mixed_content_excludes_navigation_and_json(self):
        html = '<a href="http://example.org">Visit</a><script type="application/ld+json">{"url":"http://example.org"}</script>'
        self.assertNotIn("SEC002", rule_ids(html, url="https://example.org"))

    def test_mixed_content_resource_types(self):
        html = '<video poster="http://example.org/a"><source src="http://example.org/b"></video><object data="http://example.org/c"></object><link rel="stylesheet" href="http://example.org/d"><img srcset="https://example.org/e 1x, http://example.org/f 2x">'
        self.assertEqual(sum(f.rule_id == "SEC002" for f in audit_html(html, url="https://example.org").findings), 5)

    def test_http_base_makes_relative_resources_insecure(self):
        html = '<html><head><base href="http://example.org/"></head><body><img src="x"><form action="submit"></form><form></form></body></html>'
        report = audit_html(html, url="https://example.org")
        self.assertEqual(sum(f.rule_id == "SEC002" for f in report.findings), 1)
        self.assertEqual(sum(f.rule_id == "SEC003" for f in report.findings), 1)

    def test_module_async_and_defer_do_not_block(self):
        html = '<head><script src="a" type="module"></script><script src="b" async></script><script src="c" defer></script><script src="d" type="application/json"></script></head>'
        self.assertNotIn("PERF002", rule_ids(html))

    def test_title_in_body_does_not_pass(self):
        self.assertIn("SEO001", rule_ids('<html><head></head><body><title>Body title is invalid</title></body></html>'))

    def test_ignore_validation(self):
        self.assertNotIn("A11Y001", rule_ids("", ignore=["A11Y001"]))
        with self.assertRaises(ValueError):
            audit_html("", ignore=["UNKNOWN"])

    def test_resource_limits(self):
        with self.assertRaisesRegex(ValueError, "nesting"):
            audit_html("<div>" * 520)
        with self.assertRaisesRegex(ValueError, "8 MiB"):
            audit_html("a" * (8 * 1024 * 1024 + 1))

    def test_bad_url_and_header_types(self):
        with self.assertRaises(ValueError):
            audit_html(CLEAN, url="ftp://example.org")
        with self.assertRaises(ValueError):
            audit_html(CLEAN, headers={"content-type": 3})


if __name__ == "__main__":
    unittest.main()
