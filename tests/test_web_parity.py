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
class TestSaveFormatParity(unittest.TestCase):
    """Both front ends must agree on what a save looks like.

    They store in different places - a JSON file versus localStorage - but the
    shape and the version are shared, so a save format change on one side is a
    visible break rather than a quiet divergence.
    """

    @classmethod
    def setUpClass(cls):
        cls.js = run_node("dump.js", "--save")

    def python_save(self):
        import tempfile
        from cryptowarz import save as S
        from cryptowarz.game import Game
        from cryptowarz.stations import STATIONS
        g = Game(seed=21)
        qty = g.max_buyable("DOGE") * 0.3
        if qty > 0:
            g.buy("DOGE", qty)
        try:
            g.travel(next(s.name for s in STATIONS if s.name != g.station.name))
        except ValueError:
            pass
        return S.to_dict(g)

    def test_the_save_version_matches(self):
        from cryptowarz.save import SAVE_VERSION
        self.assertEqual(self.js["save_version"], SAVE_VERSION)

    def test_the_top_level_shape_matches(self):
        py = self.python_save()
        self.assertEqual(sorted(self.js["save"]), sorted(py),
                         "the two save formats have drifted apart")

    def test_the_player_shape_matches(self):
        py = self.python_save()
        self.assertEqual(sorted(self.js["save"]["player"]), sorted(py["player"]))

    def test_both_record_prices_and_the_pending_shock(self):
        for save in (self.js["save"], self.python_save()):
            self.assertIn("prices", save["market"])
            self.assertIn("shock", save["market"])
            self.assertIn("levels", save)
            self.assertIn("rng", save)     # the anti-savescum guarantee


@requires_node
class TestProgressParity(unittest.TestCase):
    """The ladder, the grades and the ranked slate must be one rule set.

    This is the part a leaderboard cannot survive drifting on: if the phone
    version grades a run differently, or deals a different market for today's
    second ranked run, the two front ends are posting incomparable numbers to
    the same board.
    """

    @classmethod
    def setUpClass(cls):
        cls.js = run_node("dump.js")["progress"]

    def test_the_profile_format_version_matches(self):
        from cryptowarz.progress import PROGRESS_VERSION
        self.assertEqual(self.js["version"], PROGRESS_VERSION)

    def test_the_number_of_ranked_runs_a_day_matches(self):
        from cryptowarz.progress import RUNS_PER_DAY
        self.assertEqual(self.js["runs_per_day"], RUNS_PER_DAY)

    def test_the_grade_ladder_matches(self):
        from cryptowarz.progress import GRADES
        self.assertEqual(len(self.js["grades"]), len(GRADES))
        for js, (threshold, letter, blurb) in zip(self.js["grades"], GRADES):
            self.assertAlmostEqual(js["threshold"], threshold, msg=letter)
            self.assertEqual(js["letter"], letter)
            self.assertEqual(js["blurb"], blurb, letter)

    def test_every_tier_matches_including_its_score_weight(self):
        from cryptowarz.progress import TIERS
        self.assertEqual([t["level"] for t in self.js["tiers"]], [t.level for t in TIERS])
        for js, py in zip(self.js["tiers"], TIERS):
            self.assertEqual(js["name"], py.name, py.name)
            self.assertAlmostEqual(js["debt"], py.debt, msg=py.name)
            self.assertAlmostEqual(js["capacity"], py.capacity, msg=py.name)
            self.assertAlmostEqual(js["heat"], py.heat_mult, msg=py.name)
            self.assertEqual(js["days"], py.days, py.name)
        self.assertEqual(self.js["tier_mults"], [t.score_mult for t in TIERS])

    def test_todays_slate_is_the_same_three_markets_on_both_sides(self):
        from cryptowarz.progress import daily_seeds
        self.assertEqual(self.js["daily_seeds"], daily_seeds(1_700_000_000))

    def test_the_goals_and_their_unlocks_match(self):
        from cryptowarz.progress import ACHIEVEMENTS, PERKS
        self.assertEqual(self.js["achievements"], [a.key for a in ACHIEVEMENTS])
        self.assertEqual(self.js["perks"],
                         [{"key": p.key, "by": p.unlocked_by} for p in PERKS])


@requires_node
class TestDiceParity(unittest.TestCase):
    """Both front ends must run the dice, and gate them, identically.

    The behavioural half matters more than the constants: a port that quietly
    stopped gating would keep passing every other test while handing the
    leaderboard to a run that is not supposed to reach it.
    """

    @classmethod
    def setUpClass(cls):
        cls.js = run_node("dump.js")["dice"]

    def test_the_dice_constants_match(self):
        from cryptowarz import game as gm
        self.assertEqual(self.js["every"], gm.DICE_EVERY)
        self.assertEqual(self.js["sides"], gm.DICE_SIDES)
        self.assertAlmostEqual(self.js["near_prize"], gm.DICE_NEAR_PRIZE)
        self.assertAlmostEqual(self.js["exact_prize"], gm.DICE_EXACT_PRIZE)
        self.assertEqual(self.js["streak_calls"], list(gm.HOT_HAND))
        self.assertAlmostEqual(self.js["streak_chance"], gm.HOT_HAND_CHANCE)
        self.assertAlmostEqual(self.js["streak_min"], gm.HOT_HAND_MIN)
        self.assertAlmostEqual(self.js["streak_max"], gm.HOT_HAND_MAX)

    def test_the_unranked_grade_matches(self):
        from cryptowarz.progress import UNRANKED_GRADE
        self.assertEqual(self.js["unranked_grade"], UNRANKED_GRADE)
        self.assertEqual(self.js["grade_shown"], UNRANKED_GRADE)

    def test_the_port_hides_it_the_same_way(self):
        self.assertFalse(self.js["ready_on_day_one"])
        self.assertTrue(self.js["calls_start_it"])
        self.assertFalse(self.js["reversed_does_not"])

    def test_the_payout_has_the_same_shape_on_both_sides(self):
        """Measured, not read off the constants.

        Two generators from one seed produce different streams, so the exact
        payouts cannot match. What must match is the behaviour the player
        feels: it skips some rides, the amounts vary widely, and nothing ever
        comes out above the ceiling.
        """
        from cryptowarz.game import HOT_HAND_CHANCE, HOT_HAND_MAX, HOT_HAND_MIN
        js = self.js["payouts"]
        self.assertAlmostEqual(js["paid_share"], HOT_HAND_CHANCE, delta=0.05)
        self.assertLessEqual(js["biggest"], HOT_HAND_MAX + 1e-6)
        self.assertGreaterEqual(js["smallest"], HOT_HAND_MIN - 1e-6)
        self.assertTrue(js["distinct_enough"], "the port pays a flat amount")

    def test_the_port_gates_it_the_same_way(self):
        self.assertTrue(self.js["unlocks_nothing"])
        self.assertTrue(self.js["spends_no_ranked_slot"])
        self.assertTrue(self.js["survives_reload"])


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
