"""The web port must stay the same game as the Python one.

CryptoWarz now has two implementations of identical rules: the terminal version
in ``cryptowarz/`` and the phone version in ``web/game.js``. Two copies of a
rule set drift - a coin retuned on one side, a station bias edited on the
other - and the drift is silent, because each version works perfectly well on
its own while quietly being a different game.

So the data is compared exactly, and the behaviour is compared by shape. These
tests skip cleanly where node is unavailable, since the Python package itself
has no dependencies and must stay runnable anywhere.
"""

import json
import shutil
import subprocess
import unittest
from pathlib import Path

from cryptowarz.coins import COINS
from cryptowarz.game import DAYS, START_CAPACITY, START_CASH, START_DEBT, SUBWAY_FARE
from cryptowarz.stations import STATIONS

WEB = Path(__file__).resolve().parent.parent / "web"
NODE = shutil.which("node")
requires_node = unittest.skipUnless(NODE, "node is not installed; the web port cannot be checked")


def run_node(script, *args):
    out = subprocess.run([NODE, str(WEB / script), *args],
                         capture_output=True, text=True, timeout=300, check=True)
    return json.loads(out.stdout)


class TestWebSourcesExist(unittest.TestCase):
    def test_the_web_version_is_in_the_repo(self):
        for name in ("game.js", "index.html", "build.py", "balance.js", "dump.js"):
            self.assertTrue((WEB / name).exists(), f"web/{name} is missing")

    def test_the_standalone_page_loads_the_logic_it_does_not_inline_it(self):
        """index.html stays readable; only the published build is flattened."""
        html = (WEB / "index.html").read_text()
        self.assertIn('<script src="game.js"></script>', html)
        self.assertIn("viewport-fit=cover", html)   # iPhone safe areas

    def test_the_artifact_build_inlines_everything(self):
        import sys
        sys.path.insert(0, str(WEB))
        from build import build                     # noqa: E402
        page = build()
        self.assertNotIn("<script src=", page)      # the CSP blocks relative loads
        self.assertIn("function Game", page)
        self.assertIn("<title>CryptoWarz</title>", page)


@requires_node
class TestDataParity(unittest.TestCase):
    """Exact comparison - these are the same numbers or they are not."""

    @classmethod
    def setUpClass(cls):
        cls.js = run_node("dump.js")

    def test_constants_match(self):
        c = self.js["constants"]
        self.assertEqual(c["DAYS"], DAYS)
        self.assertAlmostEqual(c["SUBWAY_FARE"], SUBWAY_FARE)
        self.assertAlmostEqual(c["START_CASH"], START_CASH)
        self.assertAlmostEqual(c["START_DEBT"], START_DEBT)
        self.assertAlmostEqual(c["START_CAPACITY"], START_CAPACITY)

    def test_every_coin_matches(self):
        self.assertEqual([c["symbol"] for c in self.js["coins"]], [c.symbol for c in COINS])
        for js, py in zip(self.js["coins"], COINS):
            self.assertEqual(js["name"], py.name, py.symbol)
            self.assertAlmostEqual(js["low"], py.low, msg=py.symbol)
            self.assertAlmostEqual(js["high"], py.high, msg=py.symbol)
            self.assertEqual(js["meme"], py.meme, py.symbol)
            self.assertEqual(js["note"], py.note, py.symbol)

    def test_every_station_matches(self):
        self.assertEqual([s["name"] for s in self.js["stations"]], [s.name for s in STATIONS])
        for js, py in zip(self.js["stations"], STATIONS):
            self.assertAlmostEqual(js["heat"], py.heat, msg=py.name)
            self.assertEqual(js["shark"], py.has_shark, py.name)
            self.assertEqual(js["vault"], py.has_vault, py.name)
            self.assertEqual(js["shop"], py.has_upgrades, py.name)
            self.assertEqual(set(js["bias"]), set(py.bias), f"{py.name} biases differ")
            for symbol, value in py.bias.items():
                self.assertAlmostEqual(js["bias"][symbol], value, msg=f"{py.name}/{symbol}")


@requires_node
class TestBalanceParity(unittest.TestCase):
    """Shape comparison.

    Exact medians cannot match - mulberry32 and the Mersenne Twister produce
    different streams from the same seed - so what is asserted is every
    conclusion the balance table is supposed to support.
    """

    @classmethod
    def setUpClass(cls):
        cls.js = run_node("balance.js", "150", "--json")

    def test_doing_nothing_still_loses(self):
        r = self.js["do nothing"]
        self.assertLess(r["median"], 0)
        self.assertLessEqual(r["solvent"], 0.05)

    def test_random_play_still_loses_badly(self):
        r = self.js["buy at random"]
        self.assertLess(r["median"], self.js["do nothing"]["median"])
        self.assertLessEqual(r["solvent"], 0.15)

    def test_a_sensible_strategy_is_a_real_contest(self):
        r = self.js["buy the cheapest"]
        self.assertGreater(r["solvent"], 0.25, "punishing, not hard")
        self.assertLess(r["solvent"], 0.85, "a formula, not a game")
        self.assertGreater(r["best"], 100_000, "no upside worth chasing")

    def test_better_judgement_raises_the_ceiling(self):
        self.assertGreater(self.js["+ clear the debt"]["best"],
                           self.js["buy the cheapest"]["best"])
        self.assertGreater(self.js["+ clear the debt"]["p90"],
                           self.js["buy at random"]["p90"])


if __name__ == "__main__":
    unittest.main()
