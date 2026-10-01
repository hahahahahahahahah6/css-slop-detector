# css-slop-detector

Score your CSS/HTML for **AI-generated design cliches** — the "AI slop" look:
oversized border radii, glassmorphism on everything, purple gradients, neon
glows, pure-black dark mode with no light toggle, and giant centered hero
titles.

If AI built your site, this tells you in one number how obvious it is.

Zero dependencies. Python standard library only.

## Install

```bash
pip install css-slop-detector
# or just run it — it's one file:
python3 css_slop.py scan style.css
```

Requires Python 3.9+.

## Usage

```bash
$ css-slop scan styles.css
styles.css: score 68/100 (slop)
  L12 [big-radius] oversized border-radius (32px) on '.card'
  L12 [glass] backdrop-filter blur on '.card' (glassmorphism)
  L15 [purple-gradient] purple/violet gradient on '.hero'
  L22 [hero-center] giant centered title (font-size: 72px) on '.hero h1'
  L1 [no-light-mode] dark-only design: near-black backgrounds with no
     light-mode toggle or prefers-color-scheme: light found
```

Works on `.css` files and `.html` files (scans `<style>` blocks and inline
`style="..."` attributes). Machine-readable output with `--json`; fail CI
with `--fail-under 50`.

## Rules

| rule | what it flags |
|---|---|
| `big-radius` | `border-radius` ≥ 20px |
| `glass` | `backdrop-filter: blur` |
| `purple-gradient` | purple/violet/indigo/fuchsia gradients |
| `glow-shadow` | colored `box-shadow` with blur ≥ 24px |
| `pure-black` | `#000`-style backgrounds |
| `hero-center` | `text-align: center` + `font-size` ≥ 40px in one rule |
| `no-light-mode` | dark-only design, no light-mode toggle found |

Scores: 0–20 clean, 21–50 mild slop, 51–80 slop, 81–100 peak slop.

## Differentiation

Design-skill collections (impeccable, ui-skills, hallmark) teach AI to
*generate* better design. This does the opposite: it *detects* the finished
product's AI fingerprints and scores them, so you can de-slop before
shipping. One file, no dependencies, runs in CI.

## License

MIT
