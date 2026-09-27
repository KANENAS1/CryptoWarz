"""The market moves as one, and what that did and did not buy.

The honest summary is in market.py: the tide prices the diversification free
lunch and makes the board read like crypto. It does NOT create a decision - a
bot handed tomorrow's regime does worse than one ignoring the weather, five
different ways. These tests hold the mechanism to what it actually is.
"""

import math
import random
import statistics
import unittest

from cryptowarz import market as M
from cryptowarz.coins import COINS
from cryptowarz.market import MarketState

RISKY = [c.symbol for c in COINS if c.symbol != "USDC"]


def walk(seed, days=25):
    rng = random.Random(seed)
    state = MarketState(rng)
    start = dict(state.levels)
    steps = {s: [] for s in RISKY}
    for _ in range(days):
        prev = dict(state.levels)
        state.drift(rng)
        for s in RISKY:
            steps[s].append(math.log(max(1e-12, state.levels[s]) / max(1e-12, prev[s])))
    return state, start, steps


class TestTheTideIsCarvedOutNotPiledOn(unittest.TestCase):
    """The single decision the whole design rests on.

    A first version drew the regime at full strength regardless of TIDE_SHARE,
    so it was added on top of every coin's volatility instead of taken out of
    it: single-coin swings grew 12% and the dial did not control the thing it
    was named after. Turning it to zero left the weather exactly where it was.
    """

    def test_the_two_shares_square_to_one(self):
        self.assertAlmostEqual(M.TIDE_SHARE ** 2 + M.IDIO_SHARE ** 2, 1.0)

    def test_the_tides_own_split_squares_to_one_as_well(self):
        rest = math.sqrt(max(0.0, 1.0 - M.TIDE_REGIME ** 2))
        self.assertAlmostEqual(M.TIDE_REGIME ** 2 + rest ** 2, 1.0)

    def test_turning_the_dial_to_zero_turns_the_weather_off(self):
        """A constant that does not control the thing it is named after is not
        a dial, it is a decoration."""
        share, idio = M.TIDE_SHARE, M.IDIO_SHARE
        try:
            M.TIDE_SHARE, M.IDIO_SHARE = 0.0, 1.0
            rng = random.Random(3)
            state = MarketState(rng)
            for _ in range(30):
                state.drift(rng)
                self.assertEqual(state.tide, 0.0)
                self.assertEqual(state.tide_trend, 0.0)
        finally:
            M.TIDE_SHARE, M.IDIO_SHARE = share, idio

    def test_a_single_coin_swings_about_as_hard_as_it_always_did(self):
        """The budget is fixed, so adding correlation must not add loudness."""
        share, idio = M.TIDE_SHARE, M.IDIO_SHARE
        try:
            def spread():
                return statistics.mean(
                    statistics.pstdev(walk(i)[2]["SHIB"]) for i in range(60))

            M.TIDE_SHARE, M.IDIO_SHARE = 0.0, 1.0
            without = spread()
            M.TIDE_SHARE, M.IDIO_SHARE = share, idio
            with_tide = spread()
        finally:
            M.TIDE_SHARE, M.IDIO_SHARE = share, idio
        self.assertLess(abs(with_tide - without) / without, 0.20,
                        f"the tide changed a coin's own volatility by "
                        f"{abs(with_tide - without) / without:.0%}")


class TestItActuallyCorrelates(unittest.TestCase):
    def test_coins_move_together_more_than_they_used_to(self):
        share, idio = M.TIDE_SHARE, M.IDIO_SHARE

        def correlation():
            out = []
            for i in range(120):
                steps = walk(i)[2]
                a, b = steps["SHIB"], steps["BTC"]
                sa, sb = statistics.pstdev(a), statistics.pstdev(b)
                if sa and sb:
                    ma, mb = statistics.mean(a), statistics.mean(b)
                    out.append(sum((x - ma) * (y - mb) for x, y in zip(a, b))
                               / len(a) / (sa * sb))
            return statistics.mean(out)

        try:
            M.TIDE_SHARE, M.IDIO_SHARE = 0.0, 1.0
            alone = correlation()
            M.TIDE_SHARE, M.IDIO_SHARE = share, idio
            together = correlation()
        finally:
            M.TIDE_SHARE, M.IDIO_SHARE = share, idio
        self.assertGreater(together, alone + 0.02,
                           f"coins are no more correlated than before "
                           f"({alone:+.2f} -> {together:+.2f})")

    def test_spreading_your_money_is_no_longer_free(self):
        """The flaw this was built for: holding everything used to give a
        HIGHER median return and a third of the variance, with nothing given
        up. It should still help. It should no longer be free."""
        share, idio = M.TIDE_SHARE, M.IDIO_SHARE

        def shelter():
            one, all_of_them = [], []
            for i in range(200):
                state, start, _ = walk(i)
                rets = {s: state.levels[s] / start[s] for s in RISKY}
                one.append(rets[RISKY[i % len(RISKY)]])
                all_of_them.append(statistics.mean(rets.values()))
            return 1.0 - statistics.pstdev(all_of_them) / statistics.pstdev(one)

        try:
            M.TIDE_SHARE, M.IDIO_SHARE = 0.0, 1.0
            before = shelter()
            M.TIDE_SHARE, M.IDIO_SHARE = share, idio
            after = shelter()
        finally:
            M.TIDE_SHARE, M.IDIO_SHARE = share, idio
        self.assertLess(after, before - 0.05,
                        f"diversifying still shelters {after:.0%} of the risk, "
                        f"against {before:.0%} before - the lunch is still free")
        self.assertGreater(after, 0.2, "diversifying stopped helping at all")


class TestUSDCIsTheOneThingOutOfTheWater(unittest.TestCase):
    def test_the_stablecoin_has_no_beta(self):
        self.assertEqual(M.beta_of("USDC"), 0.0)

    def test_and_stays_pegged_through_any_weather(self):
        rng = random.Random(11)
        state = MarketState(rng)
        state.tide_trend = -0.4                  # a rout
        for _ in range(40):
            state.drift(rng)
            self.assertGreaterEqual(state.levels["USDC"], 0.97)
            self.assertLessEqual(state.levels["USDC"], 1.03)

    def test_memes_ride_harder_than_majors(self):
        self.assertGreater(M.beta_of("SHIB"), M.beta_of("BTC"))
        self.assertGreater(M.beta_of("SOL"), M.beta_of("BTC"))

    def test_the_average_risky_coin_has_a_beta_of_about_one(self):
        """A table averaging 1.23 quietly inflated every coin's volatility by
        12% - which is 'made it louder' rather than 'made it move together'."""
        betas = [M.beta_of(s) for s in RISKY]
        self.assertAlmostEqual(statistics.mean(betas), 1.0, delta=0.08)


class TestTheWeatherHasAName(unittest.TestCase):
    #: the scale the labels are read on, so these survive a retune
    def scale(self):
        return M.TYPICAL_VOL * M.TIDE_SHARE * M.TIDE_REGIME

    def test_every_level_is_reachable_and_ordered(self):
        one = self.scale()
        seen = [M.tide_level(t * one) for t in (1.2, 0.4, 0.0, -0.4, -1.2)]
        self.assertEqual(seen, ["EUPHORIA", "BULL", "CHOP", "BEAR", "CAPITULATION"])

    def test_the_labels_never_go_backwards(self):
        """Walking the dial from rout to euphoria must pass every level once,
        in order, or the thresholds have crossed over."""
        one = self.scale()
        names = [M.tide_level(t / 40.0 * one) for t in range(-80, 81)]
        order = [n for i, n in enumerate(names) if i == 0 or n != names[i - 1]]
        self.assertEqual(order, ["CAPITULATION", "BEAR", "CHOP", "BULL", "EUPHORIA"])

    def test_flat_water_reads_as_chop(self):
        self.assertEqual(M.tide_level(0.0), "CHOP")

    def test_the_name_comes_from_the_regime_not_todays_draw(self):
        """A label that flickered daily would be one nobody could act on."""
        rng = random.Random(5)
        state = MarketState(rng)
        state.tide_trend = 0.0
        state.tide = 0.9                       # a wild single day
        self.assertEqual(M.tide_level(state.tide_trend), "CHOP")

    def test_every_level_has_something_to_say(self):
        for _, name, blurb in M.TIDE_LEVELS:
            self.assertTrue(blurb.strip(), name)


class TestTheWeatherRidesTheSave(unittest.TestCase):
    def test_a_reload_does_not_reshuffle_the_regime(self):
        import json

        from cryptowarz import save as S
        from cryptowarz.game import Game

        game = Game(seed=17)
        for _ in range(6):
            game.state.drift(game.rng)
        game.state.tide_trend = -0.037
        game.state.tide = -0.041
        blob = json.loads(json.dumps(S.to_dict(game)))
        back = S.from_dict(blob)
        self.assertAlmostEqual(back.state.tide_trend, -0.037)
        self.assertAlmostEqual(back.state.tide, -0.041)

    def test_a_save_from_before_the_tide_still_loads(self):
        import json

        from cryptowarz import save as S
        from cryptowarz.game import Game

        blob = json.loads(json.dumps(S.to_dict(Game(seed=4))))
        del blob["tide"], blob["tide_trend"]
        back = S.from_dict(blob)
        self.assertEqual(back.state.tide, 0.0)
        self.assertEqual(back.state.tide_trend, 0.0)


if __name__ == "__main__":
    unittest.main()
