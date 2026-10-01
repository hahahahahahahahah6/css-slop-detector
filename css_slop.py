#!/usr/bin/env python3
"""css-slop-detector: score CSS/HTML for AI-generated design cliches.

Detects the visual fingerprints of AI-generated web design: oversized
border radii, glassmorphism-everywhere, purple gradients, neon glows,
pure-black dark mode with no light toggle, and giant centered hero titles.

Standard library only. No dependencies.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field


VERSION = "0.1.0"

# ---------------------------------------------------------------- checks

@dataclass
class Finding:
    rule: str
    line: int
    message: str
    weight: int
    snippet: str = ""


@dataclass
class FileReport:
    path: str
    findings: list = field(default_factory=list)

    @property
    def score(self) -> int:
        # weights are severity points; scale to a 0-100 slop score
        return min(100, sum(f.weight for f in self.findings) * 4)

    @property
    def label(self) -> str:
        s = self.score
        if s <= 20:
            return "clean"
        if s <= 50:
            return "mild slop"
        if s <= 80:
            return "slop"
        return "peak slop"


_PURPLE_RE = re.compile(
    r"purple|violet|indigo|fuchsia|magenta|rebeccapurple"
    r"|#8b5cf6|#a855f7|#7c3aed|#6d28d9|#d946ef|#c026d3",
    re.IGNORECASE,
)
_RADIUS_RE = re.compile(r"border-radius\s*:\s*(\d+(?:\.\d+)?)\s*(px|rem|em)?", re.IGNORECASE)
_GLASS_RE = re.compile(r"backdrop-filter\s*:[^;]*blur", re.IGNORECASE)
_GRADIENT_RE = re.compile(r"(linear|radial|conic)-gradient\s*\(([^;{}]*)\)", re.IGNORECASE)
_GLOW_RE = re.compile(
    r"box-shadow\s*:[^;]*?(\d+(?:\.\d+)?)\s*(?:px)?\s+"
    r"(\d+(?:\.\d+)?)\s*(?:px)?\s+(\d+(?:\.\d+)?)\s*px", re.IGNORECASE
)
_GLOW_COLOR_RE = re.compile(
    r"box-shadow\s*:[^;]*(rgba?\s*\([^)]*\)|#[0-9a-f]{3,8})", re.IGNORECASE
)
_BLACK_BG_RE = re.compile(
    r"background(?:-color)?\s*:\s*(#000(?:000)?|#0[0-9a-f]{5}|#111(?:111)?|black)\b",
    re.IGNORECASE,
)
_CENTER_RE = re.compile(r"text-align\s*:\s*center", re.IGNORECASE)
_BIG_TEXT_RE = re.compile(r"font-size\s*:\s*(\d+(?:\.\d+)?)\s*(px|rem|em)?", re.IGNORECASE)
_LIGHT_MODE_RE = re.compile(
    r"prefers-color-scheme\s*:\s*light|data-theme\s*=\s*[\"']light[\"']"
    r"|\.light-theme|theme-toggle|color-scheme\s*:\s*light",
    re.IGNORECASE,
)
_RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}")


def _px(value: float, unit: str | None) -> float:
    if (unit or "px").lower() == "px":
        return value
    return value * 16  # rem/em -> px approximation


def check_rule_block(selector: str, block: str, line: int) -> list[Finding]:
    out: list[Finding] = []

    for m in _RADIUS_RE.finditer(block):
        if _px(float(m.group(1)), m.group(2)) >= 20:
            out.append(Finding(
                "big-radius", line,
                f"oversized border-radius ({m.group(1)}{m.group(2) or 'px'}) "
                f"on '{selector.strip()}'",
                2, m.group(0)))

    if _GLASS_RE.search(block):
        out.append(Finding(
            "glass", line,
            f"backdrop-filter blur on '{selector.strip()}' (glassmorphism)",
            2, "backdrop-filter: blur(...)"))

    for m in _GRADIENT_RE.finditer(block):
        if _PURPLE_RE.search(m.group(2)):
            out.append(Finding(
                "purple-gradient", line,
                f"purple/violet gradient on '{selector.strip()}'",
                3, m.group(0)[:80]))

    for m in _GLOW_RE.finditer(block):
        if float(m.group(3)) >= 24 and _GLOW_COLOR_RE.search(block):
            out.append(Finding(
                "glow-shadow", line,
                f"neon glow box-shadow (blur {m.group(3)}px) "
                f"on '{selector.strip()}'",
                2, m.group(0)[:80]))

    if _BLACK_BG_RE.search(block):
        out.append(Finding(
            "pure-black", line,
            f"pure/near-black background on '{selector.strip()}'",
            2, "background: ...black"))

    big_text = None
    for m in _BIG_TEXT_RE.finditer(block):
        if _px(float(m.group(1)), m.group(2)) >= 40:
            big_text = m.group(0)
    if big_text and _CENTER_RE.search(block):
        out.append(Finding(
            "hero-center", line,
            f"giant centered title ({big_text}) on '{selector.strip()}'",
            3, big_text))

    return out


def scan_css_text(css: str, path: str, base_line: int = 0) -> FileReport:
    report = FileReport(path)
    for m in _RULE_RE.finditer(css):
        selector, block = m.group(1), m.group(2)
        line = base_line + css.count("\n", 0, m.start()) + 1
        report.findings.extend(check_rule_block(selector, block, line))
    if not _LIGHT_MODE_RE.search(css) and _BLACK_BG_RE.search(css):
        report.findings.append(Finding(
            "no-light-mode", 1,
            "dark-only design: near-black backgrounds with no light-mode "
            "toggle or prefers-color-scheme: light found",
            5, ""))
    return report


_STYLE_TAG_RE = re.compile(r"<style[^>]*>(.*?)</style>", re.IGNORECASE | re.DOTALL)
_INLINE_STYLE_RE = re.compile(r'style\s*=\s*"([^"]*)"', re.IGNORECASE)


def scan_html_text(html: str, path: str) -> FileReport:
    report = FileReport(path)
    for m in _STYLE_TAG_RE.finditer(html):
        base_line = html.count("\n", 0, m.start(1))
        sub = scan_css_text(m.group(1), path, base_line)
        report.findings.extend(sub.findings)
    # inline styles: wrap as a synthetic rule so block checks apply
    for m in _INLINE_STYLE_RE.finditer(html):
        line = html.count("\n", 0, m.start()) + 1
        fake = f".inline{{{m.group(1)}}}"
        sub = scan_css_text(fake, path, line - 1)
        for f in sub.findings:
            f.snippet = (f.snippet or "")[:60]
        report.findings.extend(sub.findings)
    if not _LIGHT_MODE_RE.search(html) and _BLACK_BG_RE.search(html):
        report.findings.append(Finding(
            "no-light-mode", 1,
            "dark-only design: near-black backgrounds with no light-mode "
            "toggle found",
            5, ""))
    return report


def scan_path(path: str) -> FileReport:
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    if path.lower().endswith((".html", ".htm")):
        return scan_html_text(text, path)
    return scan_css_text(text, path)


# ---------------------------------------------------------------- cli

def fmt_human(report: FileReport) -> str:
    lines = [f"{report.path}: score {report.score}/100 ({report.label})"]
    for f in report.findings:
        lines.append(f"  L{f.line} [{f.rule}] {f.message}")
    if not report.findings:
        lines.append("  no slop detected")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="css-slop",
        description="Score CSS/HTML for AI-generated design cliches.")
    ap.add_argument("paths", nargs="+", help="CSS or HTML files to scan")
    ap.add_argument("--json", action="store_true", help="emit JSON report")
    ap.add_argument("--fail-under", type=int, default=None, metavar="N",
                    help="exit 1 if any file scores >= N")
    args = ap.parse_args(argv)

    reports = []
    for p in args.paths:
        try:
            reports.append(scan_path(p))
        except OSError as e:
            print(f"error: {p}: {e}", file=sys.stderr)
            return 2

    if args.json:
        print(json.dumps([
            {"path": r.path, "score": r.score, "label": r.label,
             "findings": [{"rule": f.rule, "line": f.line,
                           "message": f.message, "weight": f.weight}
                          for f in r.findings]}
            for r in reports], indent=2))
    else:
        print("\n\n".join(fmt_human(r) for r in reports))

    if args.fail_under is not None and any(r.score >= args.fail_under for r in reports):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
