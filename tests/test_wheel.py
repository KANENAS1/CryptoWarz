"""The prize wheel, and the one rule that makes a bigger map worth having.

The wheel pays for going somewhere NEW: one spin per stop, per run. Without
that it is a lever you pull rather than a map you explore, and six extra
stations earn nothing. Most of what follows guards that rule, and the rarity of
the wedge that hands out gear - a common gear wedge would turn a progression
built on winning runs into a progression built on riding trains.
"""

import collections
import unittest

from cryptowarz import gear as G
from cryptowarz import progress as P
from cryptowarz import save as S
from cryptowarz.game import WHEEL, Game
from cryptowarz.stations import STATIONS

WHEEL_STOPS = [s for s in STATIONS if s.has_wheel]
BARE = next(s for s in STATIONS if not s.has_wheel)


def at_a_wheel(seed=5, stop=None, gear=None):
    game = Game(seed=seed, gear=gear or {})
    game.station = stop or WHEEL_STOPS[0]
    game.player.capacity = 1e9          # so no prize is clipped by the wallet
    return game


class TestTheMap(unittest.TestCase):
    def test_there_are_wheels_worth_travelling_for(self):
        self.assertGreaterEqual(len(WHEEL_STOPS), 4)
        self.assertLess(len(WHEEL_STOPS), len(STATIONS),
                        "a wheel at every stop is not a reason to go anywhere")

    def test_the_new_stops_did_not_widen_the_arbitrage(self):
        """A bigger map must add places to go, not a bigger edge."""
        from cryptowarz.coins import COINS
        from cryptowarz.market import station_markup
        for coin in COINS:
            if coin.symbol == "USDC":
                continue
            marks = [station_markup(s, coin.symbol) for s in STATIONS]
            self.assertLess(max(marks) / min(marks), 2.6, coin.symbol)

    def test_every_station_name_is_unique(self):
        names = [s.name for s in STATIONS]
        self.assertEqual(len(names), len(set(names)))

    def test_the_services_did_not_all_land_in_one_borough(self):
        boroughs = {s.borough for s in STATIONS if s.has_wheel}
        self.assertGreaterEqual(len(boroughs), 3, "the wheels are all in one place")


class TestOneSpinPerStop(unittest.TestCase):
    def test_a_wheel_stop_offers_a_spin(self):
        self.assertTrue(at_a_wheel().wheel_ready)

    def test_a_stop_without_one_does_not(self):
        self.assertFalse(at_a_wheel(stop=BARE).wheel_ready)

    def test_the_second_spin_at_the_same_stop_is_refused(self):
        game = at_a_wheel()
        game.spin_wheel()
        self.assertFalse(game.wheel_ready)
        with self.assertRaises(ValueError):
            game.spin_wheel()

    def test_another_stop_is_a_fresh_spin(self):
        game = at_a_wheel()
        game.spin_wheel()
        game.station = WHEEL_STOPS[1]
        self.assertTrue(game.wheel_ready)

    def test_coming_back_later_does_not_reset_it(self):
        """The rule is per run, not per visit, or it is farmable."""
        game = at_a_wheel()
        game.spin_wheel()
        game.station = WHEEL_STOPS[1]
        game.spin_wheel()
        game.station = WHEEL_STOPS[0]
        self.assertFalse(game.wheel_ready)

    def test_a_reload_remembers_where_you_have_spun(self):
        game = at_a_wheel()
        game.spin_wheel()
        back = S.from_dict(S.to_dict(game))
        back.station = WHEEL_STOPS[0]
        self.assertFalse(back.wheel_ready, "a reload handed out a second spin")


class TestWhatItPays(unittest.TestCase):
    def spins(self, n=4_000, gear=None):
        out = collections.Counter()
        for seed in range(n):
            game = at_a_wheel(seed=seed, gear=gear)
            if gear:
                game.player.holding("DOGE").qty = 1_000.0
            before = game.player.used_capacity
            game.spin_wheel()
            out["cash"] += game.player.used_capacity - before
            out["gear"] += 1 if game.wheel_award else 0
            out["spins"] += 1
        return out

    def test_every_wedge_is_reachable(self):
        seen = set()
        for seed in range(4_000):
            game = at_a_wheel(seed=seed)
            said = " ".join(game.spin_wheel())
            from cryptowarz.game import WHEEL_LINES
            seen.update(label for label, line in WHEEL_LINES.items() if line in said)
        self.assertEqual(seen, {w[0] for w in WHEEL}, "a wedge can never come up")

    def test_gear_is_rare(self):
        got = self.spins()
        expected = sum(w[1] for w in WHEEL if w[3]) / sum(w[1] for w in WHEEL)
        self.assertAlmostEqual(got["gear"] / got["spins"], expected, delta=0.015)
        self.assertLess(got["gear"] / got["spins"], 0.08)

    def test_a_spin_can_pay_nothing_at_all(self):
        self.assertTrue(any(w[0] == "BUST" and w[2] == 0 for w in WHEEL))

    def test_gear_you_hold_for_lifts_the_cash_prizes(self):
        bare = self.spins(n=1_500)
        geared = self.spins(n=1_500, gear={"meme": G.MAX_LEVEL})
        self.assertGreater(geared["cash"], bare["cash"] * 1.05)

    def test_it_never_costs_you_anything(self):
        game = at_a_wheel()
        cash, debt = game.player.cash, game.player.debt
        game.spin_wheel()
        self.assertAlmostEqual(game.player.cash, cash)
        self.assertAlmostEqual(game.player.debt, debt)


class TestTheGearWedge(unittest.TestCase):
    def award(self, seed_from=0, holding=None, **kw):
        for seed in range(seed_from, seed_from + 6_000):
            game = at_a_wheel(seed=seed, **kw)
            if holding:
                game.player.holding(holding).qty = 1_000.0
            game.spin_wheel()
            if game.wheel_award:
                return game
        self.fail("never hit the gear wedge")

    def test_it_banks_a_win_toward_the_class_you_are_carrying(self):
        game = self.award(holding="BTC")
        self.assertEqual(game.wheel_award, "major")

    def test_a_banked_wheel_win_is_the_same_currency_as_a_real_one(self):
        profile = P.Profile()
        piece, before, after = G.credit_wheel(profile, "meme")
        self.assertEqual((piece.key, before, after), ("meme", 0, 1))
        self.assertEqual(profile.gear_wins, {"meme": 1})

    def test_it_hands_out_nothing_on_a_run_the_board_will_not_rank(self):
        """Whatever hands a run free money must not hand it progression."""
        for seed in range(6_000):
            game = at_a_wheel(seed=seed)
            game.hot_hand = True
            game.stats["hot_hand"] = True
            said = " ".join(game.spin_wheel())
            if "would have been" in said:
                self.assertIsNone(game.wheel_award)
                return
        self.fail("never hit the gear wedge")

    def test_junk_never_banks_anything(self):
        profile = P.Profile()
        self.assertIsNone(G.credit_wheel(profile, "wizard"))
        self.assertEqual(profile.gear_wins, {})


if __name__ == "__main__":
    unittest.main()
