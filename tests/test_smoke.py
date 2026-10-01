"""Smoke tests for css-slop-detector. Run: python3 -m unittest tests.test_smoke -v"""

import os
import subprocess
import sys
import tempfile
import unittest

TOOL = os.path.join(os.path.dirname(__file__), "..", "css_slop.py")

SLOPPY_CSS = """
.hero {
  background: #000;
  border-radius: 32px;
  backdrop-filter: blur(20px);
  background: linear-gradient(135deg, #8b5cf6, #d946ef);
  box-shadow: 0 0 60px rgba(139, 92, 246, 0.6);
}
.hero h1 {
  font-size: 72px;
  text-align: center;
}
"""

CLEAN_CSS = """
.card {
  background: #ffffff;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}
.card h2 {
  font-size: 20px;
  text-align: left;
}
@media (prefers-color-scheme: light) {
  :root { color-scheme: light; }
}
"""


def run_tool(*args):
    return subprocess.run(
        [sys.executable, TOOL, *args],
        capture_output=True, text=True, timeout=30)


class TestSlopDetector(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sloppy = os.path.join(self.tmp.name, "sloppy.css")
        self.clean = os.path.join(self.tmp.name, "clean.css")
        with open(self.sloppy, "w") as f:
            f.write(SLOPPY_CSS)
        with open(self.clean, "w") as f:
            f.write(CLEAN_CSS)

    def tearDown(self):
        self.tmp.cleanup()

    def test_sloppy_scores_high(self):
        r = run_tool(self.sloppy, "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        import json
        report = json.loads(r.stdout)[0]
        self.assertGreaterEqual(report["score"], 50, report)
        rules = {f["rule"] for f in report["findings"]}
        self.assertTrue(
            {"big-radius", "glass", "purple-gradient", "glow-shadow",
             "pure-black", "hero-center", "no-light-mode"} & rules,
            f"expected slop rules, got {rules}")

    def test_clean_scores_low(self):
        r = run_tool(self.clean, "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        import json
        report = json.loads(r.stdout)[0]
        self.assertLessEqual(report["score"], 20, report)

    def test_html_inline_styles(self):
        html = os.path.join(self.tmp.name, "page.html")
        with open(html, "w") as f:
            f.write('<div style="border-radius: 28px; '
                    'background: linear-gradient(90deg, violet, fuchsia)">x</div>')
        r = run_tool(html, "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        import json
        report = json.loads(r.stdout)[0]
        rules = {f["rule"] for f in report["findings"]}
        self.assertIn("big-radius", rules)
        self.assertIn("purple-gradient", rules)

    def test_fail_under_flag(self):
        # --fail-under N fails when the score is UNDER N (matches plain-speak).
        r = run_tool(self.sloppy, "--fail-under", "50")
        self.assertEqual(r.returncode, 0, r.stderr)  # sloppy scores >= 50
        r = run_tool(self.clean, "--fail-under", "50")
        self.assertEqual(r.returncode, 1)  # clean scores < 50

    def test_near_black_ignores_blue_green(self):
        p = os.path.join(self.tmp.name, "colors.css")
        with open(p, "w") as f:
            f.write(".a{background:#0066cc}\n.b{background:#00ff00}\n"
                    ".c{background:#0a0a0a}\n.d{background:#000}\n")
        r = run_tool(p, "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        import json
        report = json.loads(r.stdout)[0]
        black_lines = sorted(f["line"] for f in report["findings"]
                             if f["rule"] == "pure-black")
        self.assertEqual(black_lines, [3, 4], report["findings"])

    def test_tailwind_shadow_not_neon(self):
        p = os.path.join(self.tmp.name, "shadow.css")
        with open(p, "w") as f:
            f.write(".a{box-shadow: 0 25px 50px -12px rgba(0,0,0,.25)}\n"
                    ".b{box-shadow: 0 0 60px rgba(139,92,246,.6)}\n")
        r = run_tool(p, "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        import json
        report = json.loads(r.stdout)[0]
        glow_lines = sorted(f["line"] for f in report["findings"]
                            if f["rule"] == "glow-shadow")
        self.assertEqual(glow_lines, [2], report["findings"])

    def test_rule_line_numbers(self):
        p = os.path.join(self.tmp.name, "lines.css")
        with open(p, "w") as f:
            f.write(".a {\n  background: #000;\n}\n"
                    ".b {\n  background: #000;\n}\n")
        r = run_tool(p, "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        import json
        report = json.loads(r.stdout)[0]
        black_lines = sorted(f["line"] for f in report["findings"]
                             if f["rule"] == "pure-black")
        self.assertEqual(black_lines, [1, 4], report["findings"])  # was [1, 3]

    def test_missing_file_errors(self):
        r = run_tool(os.path.join(self.tmp.name, "nope.css"))
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
