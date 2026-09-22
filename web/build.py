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


#: The head the artifact runtime supplies for us and a file on disk does not.
#:
#: This was a real bug, shipped: the artifact build drops index.html's <head>
#: because the host page owns it, so the same bytes saved as a file opened in
#: QUIRKS MODE (no doctype - height:100% and the fixed sheets stop behaving),
#: at desktop width on a phone (no viewport), and with every em-dash and block
#: character mangled (no charset, and a file:// page has no HTTP header to fall
#: back on). A standalone page needs a standalone document.
STANDALONE_HEAD = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#000000">
<meta name="description" content="CryptoWarz - buy low, sell high, ride the subway, dodge the SEC.">
"""


def standalone(text: str) -> str:
    """The same game as a complete document you can open from disk."""
    return f"{STANDALONE_HEAD}{text.split(chr(10), 1)[0]}\n" + \
           text.split(chr(10), 1)[1].replace("<style>", "<style>", 1) \
               .replace("</style>", "</style>\n</head>\n<body>", 1) + "\n</body>\n</html>\n"


def main() -> int:
    text = build()
    if "<script src=" in text:
        print("build failed: a relative script survived the inline step", file=sys.stderr)
        return 1
    out = HERE / "cryptowarz.artifact.html"
    out.write_text(text, encoding="utf-8")
    print(f"wrote {out} ({len(text) / 1024:.0f} KB)")

    # the same game as a page anyone can open: from disk, from a web host, from
    # GitHub Pages. Committed, unlike the artifact bundle, because it IS the
    # published site.
    page = HERE.parent / "docs" / "index.html"
    page.parent.mkdir(exist_ok=True)
    whole = standalone(text)
    for needed in ("<!doctype html>", "<meta charset=\"utf-8\">", "name=\"viewport\"",
                   "</body>", "</html>"):
        if needed not in whole:
            print(f"build failed: the standalone page has no {needed}", file=sys.stderr)
            return 1
    page.write_text(whole, encoding="utf-8")
    (page.parent / ".nojekyll").write_text("")
    print(f"wrote {page} ({len(whole) / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
