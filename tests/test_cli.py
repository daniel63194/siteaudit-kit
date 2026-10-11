import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CLITests(unittest.TestCase):
    def call(self, *args):
               env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONIOENCODING="utf-8")
        return subprocess.run([sys.executable, "-m", "siteaudit_kit", *map(str, args)],
                              cwd=ROOT, env=env, text=True, encoding="utf-8", capture_output=True, timeout=10)

    def test_clean_cli(self):
        result = self.call("examples/clean.html")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No findings", result.stdout)

    def test_error_exit_and_json(self):
        result = self.call("examples/problematic.html", "--format", "json")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertGreater(json.loads(result.stdout)["summary"]["error"], 0)

    def test_none_gate(self):
        self.assertEqual(self.call("examples/problematic.html", "--fail-on", "none").returncode, 0)

    def test_output_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "report.html"
            result = self.call("examples/clean.html", "--format", "html", "--output", path)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertIn("<!doctype html>", path.read_text(encoding="utf-8"))

    def test_baseline_end_to_end(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baseline.json"
            initial = self.call("examples/problematic.html", "--write-baseline", path)
            self.assertEqual(initial.returncode, 1)  # Saving is not silently accepting this run.
            accepted = self.call("examples/problematic.html", "--baseline", path, "--fail-on", "info")
            self.assertEqual(accepted.returncode, 0, accepted.stderr)
            self.assertIn("0 new", accepted.stdout)

    def test_local_file_with_headers_and_url(self):
        result = self.call("examples/clean.html", "--base-url", "https://example.org/garden",
                           "--headers", "examples/headers.json", "--fail-on", "info")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("24 checks", result.stdout)

    def test_input_errors(self):
        for args in (("missing.html",), ("examples/clean.html", "--ignore", "BAD"),
                     ("examples/clean.html", "--max-bytes", "1"),
                     ("examples/clean.html", "--base-url", "file:///etc/passwd"),
                     ("https://example.org", "--base-url", "https://example.org")):
            with self.subTest(args=args):
                result = self.call(*args)
                self.assertEqual(result.returncode, 2)
                self.assertIn("siteaudit:", result.stderr)

    def test_bad_json_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baseline.json"
            path.write_text("not json", encoding="utf-8")
            self.assertEqual(self.call("examples/clean.html", "--baseline", path).returncode, 2)

    def test_version_and_rules(self):
        self.assertIn("0.1.0", self.call("--version").stdout)
        rules = self.call("--list-rules")
        self.assertEqual(rules.returncode, 0)
        self.assertEqual(len(rules.stdout.splitlines()), 24)

    def test_sarif_cli(self):
        result = self.call("examples/clean.html", "--format", "sarif")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["runs"][0]["results"], [])
