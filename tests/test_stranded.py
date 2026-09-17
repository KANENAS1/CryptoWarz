"""The dead end, and the two honest ways out of it.

The game can genuinely corner a player: a raid takes the bags, a gas spike
takes the cash, and they are standing on a platform with no Shark and no vault
and $1.40 in their pocket. Every other loss here is a decision that went wrong.
This one is a wall, and a wall the player cannot see is just a frozen screen
with a working button bar.

What is tested is mostly the *negative* side - every way out that exists must
stop the game claiming you are stuck, because a false dead end would tell a
player to abandon a run they could still have saved.
"""

import unittest

from cryptowarz.game import Game
from cryptowarz.stations import STATIONS

BARE = next(s for s in STATIONS if not s.has_shark and not s.has_vault)
SHARK = next(s for s in STATIONS if s.has_shark)
VAULT = next(s for s in STATIONS if s.has_vault)


def cornered(station=BARE):
    game = Game(seed=5)
    game.player.cash = 1.40
    game.player.wallet.clear()
    game.player.vault = 0.0
    game.station = station
    return game


class TestSpottingIt(unittest.TestCase):
    def test_a_fresh_run_is_not_stranded(self):
        self.assertFalse(Game(seed=5).stranded)

    def test_no_fare_and_nothing_to_sell_at_a_bare_stop_is(self):
        self.assertTrue(cornered().stranded)

    def test_something_to_sell_is_a_way_out(self):
        game = cornered()
        game.player.holding("DOGE").qty = 1_000.0
        self.assertFalse(game.stranded)

    def test_the_shark_is_a_way_out(self):
        self.assertFalse(cornered(SHARK).stranded)

    def test_a_maxed_out_shark_is_not(self):
        game = cornered(SHARK)
        game.player.debt = game.borrow_limit() * 2
        self.assertTrue(game.stranded, "he won't lend and there is nothing else")

    def test_money_in_the_vault_is_a_way_out_at_a_vault(self):
        game = cornered(VAULT)
        game.player.vault = 500.0
        self.assertFalse(game.stranded)

    def test_money_in_the_vault_is_no_help_anywhere_else(self):
        game = cornered(BARE)
        game.player.vault = 500.0
        self.assertTrue(game.stranded, "you cannot reach the vault from here")

    def test_enough_for_the_fare_is_never_stranded(self):
        game = cornered()
        game.player.cash = game.fare
        self.assertFalse(game.stranded)

    def test_a_free_ride_is_never_stranded(self):
        """The MetroCard perk makes the fare zero, so broke is still mobile."""
        game = Game(seed=5, perk="metrocard")
        game.player.cash = 0.0
        game.player.wallet.clear()
        game.station = BARE
        self.assertFalse(game.stranded)

    def test_a_finished_run_is_not_stranded_it_is_over(self):
        game = cornered()
        game.finished = True
        self.assertFalse(game.stranded)


class TestGivingUp(unittest.TestCase):
    def test_it_ends_the_run(self):
        game = cornered()
        game.give_up()
        self.assertTrue(game.finished)

    def test_it_says_so_in_the_log(self):
        game = cornered()
        self.assertIn("give up", " ".join(game.give_up()).lower())
        self.assertIn("give up", " ".join(game.log).lower())

    def test_giving_up_twice_is_harmless(self):
        game = cornered()
        game.give_up()
        self.assertEqual(game.give_up(), [])

    def test_the_run_is_still_scored_for_what_it_is(self):
        """Walking away is allowed. Pretending it never happened is not."""
        from cryptowarz import progress as P
        game = cornered()
        game.give_up()
        game.finalise()
        self.assertTrue(P.counts_for_progress(game))
        self.assertEqual(P.run_grade(game), "F")


if __name__ == "__main__":
    unittest.main()
