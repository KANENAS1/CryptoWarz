#!/usr/bin/env python3
"""Fold web/ into one self-contained file for publishing.

The Artifact host wraps whatever it is given in its own document skeleton and
enforces a CSP that blocks most external loads, so the published page has to be
a single file with no relative <script src>. This strips the standalone
document wrapper and inlines game.js - the repo keeps the readable two-file
version, the published page gets the flattened one, and neither is edited by
hand.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build() -> str:
    html = (HERE / "index.html").read_text(encoding="utf-8")
    game = (HERE / "game.js").read_text(encoding="utf-8")

    # node's CommonJS export has no meaning in a browser and would throw
    game = game.replace('if (typeof module !== "undefined") {', "if (false) {")

    title = "<title>CryptoWarz</title>"
    style = html[html.index("<style>"):html.index("</style>") + len("</style>")]
    body = html[html.index("<body>") + len("<body>"):html.index("</body>")]
    body = body.replace('<script src="game.js"></script>', f"<script>\n{game}\n</script>")
    return f"{title}\n{style}\n{body.strip()}\n"


def main() -> int:
    out = HERE / "cryptowarz.artifact.html"
    text = build()
    if "<script src=" in text:
        print("build failed: a relative script survived the inline step", file=sys.stderr)
        return 1
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out} ({len(text) / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
