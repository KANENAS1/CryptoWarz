"""Word you go out and get, and why accuracy was the wrong lever.

The platform gave other players exactly one use - a coat to go through - and a
system whose only verb is violence is a thin system. Somebody standing at your
stop is now worth two entirely different things, and you get one of them.
"""

import random
import statistics
import unittest

from cryptowarz.game import (ASK_MAX, ASK_MIN, ASK_SHARE, LEAK_ACCURACY,
                             TIP_ACCURACY, TIP_FRESH_FOR, TOUT_ACCURACY,
                             TOUT_DISCOUNT, Game)


def warmed(seed, days=6):
    game = Game(seed=seed)
    for _ in range(days):
        game.state.drift(game.rng)
    return game


class TestKnowingTheRightThingBeatsBeingRight(unittest.TestCase):
    """The finding this feature turns on.

    Gossip picks the loudest coin. That sounds like good information and
    measurably is not: the loudest coin has travelled furthest from its middle,
    so the pull back is about to eat the run. Told right 95% of the time, that
    tip still only lands 56% - barely better than the tout's 52%.

    Raising accuracy does almost nothing. Asking the better question - what is
    moving hardest WITH ROOM LEFT - takes the same tip to 69%.
    """

    def felt(self, accuracy, shrewd, n=900, horizon=3):
        hits = total = 0
        for i in range(n):
            game = Game(seed=i)
            for _ in range(random.Random(i).randint(2, 12)):
                game.state.drift(game.rng)
            found = game._worth_gossiping_about(shrewd=shrewd)
            if not found:
                continue
            symbol, trend = found
            before = game.state.levels[symbol]
            up = game._write_tip(symbol, trend, accuracy, "test")
            for _ in range(horizon):
                game.state.drift(game.rng)
            after = game.state.levels[symbol]
            hits += (after > before) if up else (after < before)
            total += 1
        return hits / max(1, total)

    def test_a_leak_is_worth_more_than_a_tout(self):
        tout = self.felt(TOUT_ACCURACY, shrewd=False)
        leak = self.felt(LEAK_ACCURACY, shrewd=True)
        self.assertGreater(leak, tout + 0.08,
                           f"a leak lands {leak:.0%} against a tout's {tout:.0%} - "
                           f"not worth paying more for")

    def test_the_lever_is_the_question_not_the_accuracy(self):
        """Told right 95% of the time but asked the loud question, a tip is
        barely better than one told right 70% of the time. This is the test
        that stops somebody 'improving' the leak by raising a number."""
        loud_but_honest = self.felt(LEAK_ACCURACY, shrewd=False)
        shrewd = self.felt(LEAK_ACCURACY, shrewd=True)
        self.assertGreater(shrewd, loud_but_honest + 0.08,
                           "asking the better question bought nothing")

    def test_a_leak_is_still_wrong_often_enough_to_be_a_decision(self):
        """A tip you can bank is not information, it is an instruction."""
        leak = self.felt(LEAK_ACCURACY, shrewd=True)
        self.assertLess(leak, 0.85, f"a leak lands {leak:.0%} - that is an oracle")
        self.assertGreater(leak, 0.6, f"a leak lands {leak:.0%} - that is a coin flip")


class TestWhatAskingCosts(unittest.TestCase):
    def test_the_price_scales_with_the_run(self):
        """Flat prices stop mattering by day twenty."""
        poor, rich = warmed(1), warmed(2)
        poor.player.cash = 5_000.0
        rich.player.cash = 80_000.0
        self.assertLess(poor.ask_price(), rich.ask_price())

    def test_and_is_bounded_at_both_ends(self):
        game = warmed(3)
        game.player.cash = 0.0
        self.assertEqual(game.ask_price(), ASK_MIN)
        game.player.cash = 10_000_000.0
        self.assertEqual(game.ask_price(), ASK_MAX)

    def test_the_tout_charges_less(self):
        game = warmed(4)
        game.player.cash = 50_000.0
        self.assertAlmostEqual(game.ask_price(tout=True),
                               game.ask_price() * TOUT_DISCOUNT)

    def test_you_cannot_buy_what_you_cannot_afford(self):
        game = warmed(5)
        game.player.cash = 1.0
        with self.assertRaises(ValueError):
            game.ask_around()

    def test_asking_takes_the_money_and_leaves_a_tip(self):
        game = warmed(6)
        game.player.cash = 40_000.0
        before = game.player.cash
        try:
            game.ask_around()
        except ValueError:
            self.skipTest("nothing running in this market")
        self.assertLess(game.player.cash, before)
        self.assertIsNotNone(game.tip)
        self.assertEqual(game.tip["from"], "the platform")

    def test_a_refused_ask_costs_nothing(self):
        """Paying for silence would be the worst bug this could have."""
        game = warmed(7)
        game.player.cash = 40_000.0
        game.state.trends = {sym: 0.0 for sym in game.state.trends}
        game.state.levels = {c.symbol: c.mid for c in __import__(
            "cryptowarz.coins", fromlist=["COINS"]).COINS}
        before = game.player.cash
        with self.assertRaises(ValueError):
            game.ask_around()
        self.assertEqual(game.player.cash, before)

    def test_you_cannot_ask_with_somebody_in_front_of_you(self):
        game = warmed(8)
        game.player.cash = 40_000.0
        game.pending = {"kind": "stickup", "day": 1, "line": "x", "station": "y"}
        with self.assertRaises(ValueError):
            game.ask_around()


class TestTheTipItLeaves(unittest.TestCase):
    def test_it_says_who_told_you(self):
        game = warmed(9)
        game.player.cash = 40_000.0
        try:
            game.ask_around(tout=True)
        except ValueError:
            self.skipTest("nothing running")
        self.assertEqual(game.tip["from"], "a tout")

    def test_it_goes_stale_like_any_other_word(self):
        game = warmed(10)
        game.player.cash = 40_000.0
        try:
            game.ask_around()
        except ValueError:
            self.skipTest("nothing running")
        self.assertIsNotNone(game.tip)
        game.day += TIP_FRESH_FOR + 1
        self.assertIsNone(game.tip)

    def test_the_dice_man_is_unchanged(self):
        """He asks the loud question, as he always did - the refactor that
        added leaks must not have quietly upgraded him."""
        self.assertLess(TIP_ACCURACY, LEAK_ACCURACY)
        self.assertGreater(TIP_ACCURACY, TOUT_ACCURACY)


if __name__ == "__main__":
    unittest.main()
