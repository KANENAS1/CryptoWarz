"""The skim: a bet on where a coin goes, and the reason it is fixed odds.

The first version paid in proportion to how far the coin moved, at 2x leverage.
It read like a gamble and behaved like a printing press, because the market
pulls a stretched coin back toward its middle, a player can read how stretched
a coin is straight off the price, and a payout that scales with the move turns
that read into compound interest. A trading bot went from 26% solvent to 62%,
best run $39.8 million.

So the payout is flat, and the tests that matter are the ones that would catch
that coming back: a win pays a fixed multiple whatever the move, and betting
big is punished rather than rewarded.
"""

import unittest

from cryptowarz import save as S
from cryptowarz.game import (SKIM_DEADBAND, SKIM_HEAT, SKIM_MIN, SKIM_PAYS, Game)
from cryptowarz.stations import STATIONS


def ride(game):
    game.player.cash += 500.0
    here = [s.name for s in STATIONS].index(game.station.name)
    return game.travel(STATIONS[(here + 3) % len(STATIONS)].name)


def settle(game, move):
    """Force the coin the bet is on to have moved by ``move``, then settle."""
    symbol = str(game.skim["symbol"])
    game.state.levels[symbol] = float(game.skim["level"]) * (1.0 + move)
    return game._settle_skim()


class TestPlacingOne(unittest.TestCase):
    def test_a_bet_takes_the_cash_out_of_your_pocket(self):
        game = Game(seed=5)
        before = game.player.cash
        game.open_skim("DOGE", 500.0, "dip")
        self.assertAlmostEqual(game.player.cash, before - 500.0)
        self.assertTrue(game.skim_open)

    def test_only_one_at_a_time(self):
        game = Game(seed=5)
        game.open_skim("DOGE", 200.0, "dip")
        with self.assertRaises(ValueError):
            game.open_skim("SOL", 200.0, "pump")

    def test_the_fare_is_never_part_of_the_stake(self):
        game = Game(seed=5)
        game.open_skim("DOGE", game.max_skim(), "dip")
        self.assertGreaterEqual(game.player.cash + 1e-9, game.fare)

    def test_nonsense_is_refused(self):
        game = Game(seed=5)
        for args in (("DOGE", 500.0, "sideways"), ("WIZARDCOIN", 500.0, "dip"),
                     ("USDC", 500.0, "dip"), ("DOGE", SKIM_MIN - 1, "dip"),
                     ("DOGE", 1e9, "dip")):
            with self.assertRaises(ValueError, msg=repr(args)):
                Game(seed=5).open_skim(*args)


class TestTheOddsAreFixed(unittest.TestCase):
    """The property whose absence was the bug."""

    def bet_and_settle(self, side, move, stake=1_000.0):
        game = Game(seed=5)
        game.player.cash = 50_000.0
        game.open_skim("DOGE", stake, side)
        before = game.player.cash
        settle(game, move)
        return game.player.cash - before

    def test_a_win_pays_the_same_whatever_the_move(self):
        small = self.bet_and_settle("pump", 0.03)
        huge = self.bet_and_settle("pump", 4.00)
        self.assertAlmostEqual(small, huge)
        self.assertAlmostEqual(small, 1_000.0 * (1.0 + SKIM_PAYS))

    def test_a_loss_costs_the_stake_and_never_more(self):
        for move in (-0.03, -0.40, -0.99):
            self.assertAlmostEqual(self.bet_and_settle("pump", move), 0.0)

    def test_betting_the_dip_is_the_mirror_of_betting_the_pump(self):
        self.assertAlmostEqual(self.bet_and_settle("dip", -0.20),
                               self.bet_and_settle("pump", 0.20))

    def test_a_flat_market_is_a_push_not_a_free_win(self):
        returned = self.bet_and_settle("pump", SKIM_DEADBAND / 2)
        self.assertAlmostEqual(returned, 1_000.0, msg="a push must return the stake")

    def test_the_payout_is_worse_than_even_money(self):
        """Anything repeatable and positive compounds over thirty days."""
        self.assertLess(SKIM_PAYS, 1.0)


class TestBettingBigIsLouder(unittest.TestCase):
    def test_exposure_is_the_share_of_everything_you_have(self):
        game = Game(seed=5)
        game.player.cash = 10_000.0
        game.open_skim("DOGE", 2_500.0, "dip")
        self.assertAlmostEqual(game.skim_exposure, 0.25)

    def test_a_small_bet_barely_raises_the_temperature(self):
        game = Game(seed=5)
        game.player.cash = 100_000.0
        game.open_skim("DOGE", SKIM_MIN, "dip")
        self.assertLess(game.skim_exposure, 0.01)

    def test_nothing_riding_is_no_exposure(self):
        self.assertEqual(Game(seed=5).skim_exposure, 0.0)

    def test_trouble_really_does_scale_with_it(self):
        """Measured, not asserted from the constant."""
        def trouble(stake):
            caught = 0
            for seed in range(400):
                game = Game(seed=seed)
                game.player.cash = 10_000.0
                if stake:
                    game.open_skim("DOGE", stake, "dip")
                messages = ride(game)
                caught += any("SEC" in m or "drainer" in m for m in messages)
            return caught
        self.assertGreater(trouble(9_000.0), trouble(0) * 1.05,
                           "a big open bet must actually attract trouble")


class TestItSurvivesAReload(unittest.TestCase):
    def test_closing_the_tab_is_not_a_way_out_of_a_bet(self):
        game = Game(seed=5)
        game.open_skim("SOL", 400.0, "dip")
        back = S.from_dict(S.to_dict(game))
        self.assertEqual(back.skim, game.skim)

    def test_no_bet_reloads_as_no_bet(self):
        self.assertIsNone(S.from_dict(S.to_dict(Game(seed=5))).skim)

    def test_a_bet_settles_on_the_ride_after_a_reload(self):
        game = Game(seed=5)
        game.open_skim("SOL", 400.0, "dip")
        back = S.from_dict(S.to_dict(game))
        ride(back)
        self.assertFalse(back.skim_open, "a reloaded bet never settled")


if __name__ == "__main__":
    unittest.main()
