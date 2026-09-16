"""Meta-progression: what a run leaves behind, and whether the ladder is real.

The point of all this is that a *lost* run still advances something. These
tests pin the rules; scripts/balance.py and the tuning notes in progress.py
cover whether the numbers are any good.
"""

import os
import statistics
import tempfile
import unittest

from cryptowarz import progress as P
from cryptowarz.coins import COINS
from cryptowarz.game import Game
from cryptowarz.stations import STATIONS


class ProfileTestCase(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self._prev = os.environ.get("CRYPTOWARZ_HOME")
        os.environ["CRYPTOWARZ_HOME"] = self._dir.name

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("CRYPTOWARZ_HOME", None)
        else:
            os.environ["CRYPTOWARZ_HOME"] = self._prev
        self._dir.cleanup()


def play(seed, tier=1, perk=None):
    g = Game(seed=seed, tier=tier, perk=perk)
    for _ in range(g.days):
        if g.finished:
            break
        try:
            for sym, h in list(g.player.wallet.items()):
                if h.qty > 0:
                    g.sell(sym, h.qty)
            best = min(((c.symbol, (g.market.price(c.symbol) - c.low) / (c.high - c.low))
                        for c in COINS if c.symbol != "USDC"), key=lambda x: x[1])[0]
            qty = g.max_buyable(best)
            if qty > 0:
                g.buy(best, qty * 0.95)
            g.travel(g.rng.choice([s.name for s in STATIONS if s.name != g.station.name]))
        except ValueError:
            break
    g.finalise()
    return g


class TestTiers(unittest.TestCase):
    def test_every_tier_is_distinct_and_ordered(self):
        self.assertEqual([t.level for t in P.TIERS], list(range(1, len(P.TIERS) + 1)))
        for a, b in zip(P.TIERS, P.TIERS[1:]):
            self.assertGreaterEqual(b.debt, a.debt, b.name)
            self.assertLessEqual(b.capacity, a.capacity, b.name)
            self.assertGreaterEqual(b.heat_mult, a.heat_mult, b.name)

    def test_a_tier_shapes_the_run(self):
        for tier in P.TIERS:
            g = Game(seed=1, tier=tier.level)
            self.assertAlmostEqual(g.player.debt, tier.debt, msg=tier.name)
            self.assertAlmostEqual(g.player.capacity, tier.capacity, msg=tier.name)
            self.assertEqual(g.days, tier.days, tier.name)

    def test_higher_tiers_really_are_harder(self):
        """A ladder that is not monotonic is not a ladder.

        Found the hard way: an early table gave tier 4 fewer days, and fewer
        days meant less debt compounding - so the 'harder' tier was easier.
        """
        rates = []
        for tier in (1, 3, 5):
            scores = [play(i, tier=tier).final_score() for i in range(60)]
            rates.append(sum(1 for s in scores if s > 0) / len(scores))
        self.assertGreater(rates[0], rates[1] + 0.05, "tier 3 is no harder than tier 1")
        self.assertGreater(rates[1], rates[2], "tier 5 is no harder than tier 3")

    def test_the_top_tier_is_still_beatable(self):
        """Unbeatable is not aspirational."""
        best = max(play(i, tier=5, perk="fixer").final_score() for i in range(60))
        self.assertGreater(best, 0, "nobody can ever clear the top tier")


class TestPerks(unittest.TestCase):
    def test_each_perk_changes_something(self):
        base = Game(seed=1)
        self.assertAlmostEqual(Game(seed=1, perk="seed_round").player.cash, base.player.cash + 2_000)
        self.assertAlmostEqual(Game(seed=1, perk="cold_storage").player.capacity,
                               base.player.capacity + 15_000)
        self.assertEqual(Game(seed=1, perk="metrocard").fare, 0.0)
        self.assertLess(Game(seed=1, perk="fixer").shark_rate, base.shark_rate)

    def test_an_unknown_perk_is_ignored_not_fatal(self):
        g = Game(seed=1, perk="nonsense")
        self.assertAlmostEqual(g.player.cash, 2_000)

    def test_every_perk_is_unlocked_by_a_real_achievement(self):
        keys = {a.key for a in P.ACHIEVEMENTS}
        for perk in P.PERKS:
            self.assertIn(perk.unlocked_by, keys, perk.key)

    def test_a_perk_helps(self):
        base = [play(i).final_score() for i in range(60)]
        helped = [play(i, perk="seed_round").final_score() for i in range(60)]
        self.assertGreater(statistics.median(helped), statistics.median(base))


class TestAchievements(ProfileTestCase):
    def test_finishing_any_run_earns_something(self):
        """A lost run must still pay out, or the thirtieth loss looks like the first."""
        profile = P.Profile()
        losing = play(3)
        losing.player.cash = 0.0
        losing.player.wallet = {}
        losing.player.debt = 90_000.0
        earned = P.award(profile, losing)
        self.assertTrue(earned)
        self.assertIn("first_run", profile.achievements)
        self.assertEqual(profile.runs, 1)

    def test_an_achievement_is_only_earned_once(self):
        profile = P.Profile()
        P.award(profile, play(3))
        first = list(profile.achievements)
        P.award(profile, play(4))
        self.assertEqual(len(set(profile.achievements)), len(profile.achievements))
        for key in first:
            self.assertIn(key, profile.achievements)

    def test_clearing_a_tier_unlocks_the_next(self):
        profile = P.Profile()
        self.assertEqual(profile.max_tier, 1)
        winner = play(1)
        winner.tier = 1
        winner.player.cash = 500_000.0
        winner.player.debt = 0.0
        P.award(profile, winner)
        self.assertEqual(profile.max_tier, 2)

    def test_losing_does_not_unlock_a_tier(self):
        profile = P.Profile()
        loser = play(1)
        loser.tier = 1
        loser.player.cash = 0.0
        loser.player.debt = 50_000.0
        loser.player.wallet = {}
        P.award(profile, loser)
        self.assertEqual(profile.max_tier, 1)

    def test_a_broken_check_cannot_end_a_run(self):
        profile = P.Profile()
        bad = P.Achievement("boom", "Boom", "", lambda g: 1 / 0)
        P.ACHIEVEMENTS.append(bad)
        try:
            P.award(profile, play(1))       # must not raise
        finally:
            P.ACHIEVEMENTS.remove(bad)

    def test_perks_appear_as_achievements_are_earned(self):
        profile = P.Profile()
        self.assertEqual(profile.unlocked_perks, [])
        profile.achievements.append("first_run")
        self.assertEqual([p.key for p in profile.unlocked_perks], ["metrocard"])


class TestProfilePersistence(ProfileTestCase):
    def test_round_trip(self):
        profile = P.Profile(runs=7, achievements=["first_run", "whale"],
                            best_net=123.0, best_tier_cleared=2)
        P.write_profile(profile)
        back = P.read_profile()
        self.assertEqual(back.runs, 7)
        self.assertEqual(sorted(back.achievements), ["first_run", "whale"])
        self.assertEqual(back.best_tier_cleared, 2)

    def test_a_missing_profile_is_a_blank_one(self):
        self.assertEqual(P.read_profile().runs, 0)

    def test_a_corrupt_profile_never_blocks_a_game(self):
        path = P.profile_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json")
        self.assertEqual(P.read_profile().runs, 0)

    def test_unknown_achievements_are_dropped_quietly(self):
        P.write_profile(P.Profile(achievements=["first_run", "from_a_future_version"]))
        self.assertEqual(P.read_profile().achievements, ["first_run"])


class TestDailyRun(unittest.TestCase):
    def test_the_same_day_deals_the_same_market(self):
        day = 1_700_000_000.0
        self.assertEqual(P.daily_seed(day), P.daily_seed(day + 3_600))

    def test_a_different_day_deals_a_different_one(self):
        day = 1_700_000_000.0
        self.assertNotEqual(P.daily_seed(day), P.daily_seed(day + 86_400 * 2))

    def test_the_daily_seed_reproduces_the_whole_run(self):
        seed = P.daily_seed(1_700_000_000.0)
        self.assertEqual([m.prices for m in [Game(seed=seed).market]],
                         [m.prices for m in [Game(seed=seed).market]])


if __name__ == "__main__":
    unittest.main()
