"""The dealer: the one thing in the game you can buy progression with.

A million dollars for a piece of gear is either a great sink or a hole in the
economy, and which one depends entirely on the fences around it. Three of them
matter enough to assert: the price actually leaves your net worth (so buying is
a trade against your own score rather than a free upgrade at the end of a good
run), the deal is one per run at stops that already sell things (so it is not a
lever you pull at every station), and a run the board will not rank cannot buy
anything at all (whatever hands a run free money must not let it buy
progression either).
"""

import unittest

from cryptowarz import gear as G
from cryptowarz import progress as P
from cryptowarz.game import Game
from cryptowarz.stations import STATIONS

SHOP = next(s for s in STATIONS if s.has_upgrades)
BARE = next(s for s in STATIONS if not s.has_upgrades)


def rich(cash=G.BROKER_PRICE, station=SHOP, holding=None, streak=False):
    """A run standing in front of a dealer with ``cash`` in hand."""
    game = Game(seed=5)
    game.station = station
    game.player.capacity = 1e9
    game.player.wallet.clear()
    game.player.cash = cash
    game.hot_hand = streak
    if holding:
        held = game.player.holding(holding)
        held.qty += 1_000.0 / game.market.price(holding)
        held.cost += 1_000.0
    return game


class TestWhenThereIsADeal(unittest.TestCase):
    def test_a_shop_stop_with_the_money_has_one(self):
        self.assertIsNotNone(G.broker_offer(rich()))

    def test_a_dollar_short_is_short(self):
        self.assertIsNone(G.broker_offer(rich(cash=G.BROKER_PRICE - 1)))

    def test_a_stop_without_a_shop_has_nobody(self):
        self.assertIsNone(G.broker_offer(rich(station=BARE)))

    def test_a_run_the_board_will_not_rank_cannot_buy(self):
        """God mode hands out money; it must not hand out progression."""
        game = rich(streak=True)
        self.assertFalse(P.counts_for_progress(game))
        self.assertIsNone(G.broker_offer(game))
        with self.assertRaises(ValueError):
            game.buy_gear()

    def test_he_sells_what_you_are_carrying(self):
        """The purchase reinforces a style rather than handing over a random
        quarter of the collection."""
        self.assertEqual(G.broker_offer(rich(holding="BTC")), "major")
        self.assertEqual(G.broker_offer(rich(holding="DOGE")), "meme")

    def test_an_empty_bag_still_gets_an_offer(self):
        self.assertEqual(G.broker_offer(rich()), "meme")


class TestThePriceIsReal(unittest.TestCase):
    def test_the_million_comes_out_of_the_cash(self):
        game = rich(cash=G.BROKER_PRICE + 25_000.0)
        game.buy_gear()
        self.assertAlmostEqual(game.player.cash, 25_000.0, places=2)

    def test_and_therefore_out_of_the_score(self):
        """The whole design point: you are trading this run's place on the
        board for something permanent."""
        before = rich(cash=G.BROKER_PRICE + 25_000.0)
        after = rich(cash=G.BROKER_PRICE + 25_000.0)
        after.buy_gear()
        self.assertAlmostEqual(before.final_score() - after.final_score(),
                               G.BROKER_PRICE, places=2)

    def test_being_broke_afterwards_is_allowed_but_never_negative(self):
        game = rich(cash=G.BROKER_PRICE)
        game.buy_gear()
        self.assertGreaterEqual(game.player.cash, 0.0)


class TestOnePerRun(unittest.TestCase):
    def test_the_second_visit_finds_nothing(self):
        game = rich(cash=G.BROKER_PRICE * 3)
        game.buy_gear()
        self.assertIsNone(G.broker_offer(game))
        with self.assertRaises(ValueError):
            game.buy_gear()

    def test_the_refusal_costs_nothing(self):
        game = rich(cash=G.BROKER_PRICE * 3)
        game.buy_gear()
        cash = game.player.cash
        with self.assertRaises(ValueError):
            game.buy_gear()
        self.assertEqual(game.player.cash, cash, "a refused deal took money")

    def test_it_rides_the_save(self):
        """Anti-savescum outranks the feature: reloading must not restock him."""
        from cryptowarz import save as S
        game = rich(cash=G.BROKER_PRICE * 3)
        game.buy_gear()
        again = S.from_dict(S.to_dict(game))
        again.station = SHOP
        self.assertTrue(again.stats.get("gear_bought"))
        self.assertIsNone(G.broker_offer(again))


class TestItActuallyBanks(unittest.TestCase):
    """The wheel's gear wedge banked nothing for two releases because the
    caller never ran. The purchase hands the class to the caller the same
    way, so the same mistake is possible here, and worth an assertion."""

    def test_the_purchase_names_a_class_for_the_caller_to_bank(self):
        game = rich(holding="BTC")
        game.buy_gear()
        self.assertEqual(game.gear_award, "major")

    def test_and_that_class_banks_a_win(self):
        game = rich(holding="BTC")
        game.buy_gear()
        profile = P.Profile()
        banked = G.credit_wheel(profile, game.gear_award)
        self.assertEqual(profile.gear_wins, {"major": 1})
        self.assertEqual((banked[1], banked[2]), (0, 1))

    def test_nothing_is_banked_before_the_caller_banks_it(self):
        game = rich(holding="BTC")
        game.buy_gear()
        self.assertEqual(game.gear, {}, "the Game banked a win it does not own")


class TestTheCommandLine(unittest.TestCase):
    def test_the_dealer_command_buys_and_banks(self):
        import pathlib
        import tempfile
        from cryptowarz import cli

        game = rich(cash=G.BROKER_PRICE + 5_000.0, holding="BTC")
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "profile.json"
            old = P.profile_path
            P.profile_path = lambda: path
            try:
                said = cli.handle(game, "dealer")
                profile = P.read_profile()
            finally:
                P.profile_path = old
        self.assertTrue(any("hands over" in line for line in said))
        self.assertEqual(profile.gear_wins, {"major": 1})
        self.assertIsNone(game.gear_award, "the award was banked twice over")


if __name__ == "__main__":
    unittest.main()
