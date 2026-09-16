"""The dice on the platform, and the run they can turn into something else.

The dice are a flourish: free to play, no stake, and the worst outcome is
nothing. What needs testing is not the payout but the blast radius - a run that
ends up on a streak is handed money every ride, and if that could reach the
leaderboard, the goals or the difficulty ladder it would quietly undo all
three. So most of what is below is about what such a run is NOT allowed to
touch.
"""

import unittest

from cryptowarz import progress as P
from cryptowarz import save as S
from cryptowarz.game import DICE_EVERY, DICE_SIDES, HOT_HAND, Game
from cryptowarz.stations import STATIONS


def ride(game, rides=1):
    """Move the run forward, keeping the fare topped up.

    The fare is not what these tests are about, and a player who runs out of it
    mid-test fails for the wrong reason.
    """
    for _ in range(rides):
        game.player.cash += 500.0
        here = [s.name for s in STATIONS].index(game.station.name)
        game.travel(STATIONS[(here + 3) % len(STATIONS)].name)


def to_first_offer(seed=5):
    game = Game(seed=seed)
    while not game.dice_ready:
        ride(game)
    return game


class TestWhenTheDiceAreOut(unittest.TestCase):
    def test_not_on_the_first_day(self):
        self.assertFalse(Game(seed=1).dice_ready)

    def test_they_come_around_within_a_few_rides(self):
        game = Game(seed=1)
        ride(game, DICE_EVERY)
        self.assertTrue(game.dice_ready)

    def test_one_roll_per_offer(self):
        game = to_first_offer()
        game.roll_dice(7)
        self.assertFalse(game.dice_ready)
        with self.assertRaises(ValueError):
            game.roll_dice(7)

    def test_a_number_off_the_dice_is_refused(self):
        game = to_first_offer()
        for bad in (0, -1, DICE_SIDES + 1, "banana"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                game.roll_dice(bad)

    def test_an_offer_you_ignore_keeps_standing(self):
        game = to_first_offer()
        ride(game, 2)
        self.assertTrue(game.dice_ready)

    def test_a_skipped_day_does_not_skip_the_offer(self):
        """A signal delay costs two days, and used to eat a whole offer.

        Counting off `day % 4` meant an offer whose day was jumped over never
        happened at all - invisible, because the next one along looked normal.
        """
        game = to_first_offer()
        game.roll_dice(1)
        game.day += DICE_EVERY + 1          # as a delay event would
        self.assertTrue(game.dice_ready)


class TestTheGift(unittest.TestCase):
    def test_free_crypto_is_free_but_not_weightless(self):
        """It costs no cash, and still takes up wallet room at fair value.

        A bag with no cost basis would be invisible to capacity and would make
        every later sale an infinite multiple.
        """
        game = Game(seed=3)
        before_cash, before_used = game.player.cash, game.player.used_capacity
        game.gift(1_000.0, "Here")
        self.assertAlmostEqual(game.player.cash, before_cash)
        self.assertAlmostEqual(game.player.used_capacity, before_used + 1_000.0, places=6)

    def test_it_never_overflows_the_wallet(self):
        game = Game(seed=3)
        game.player.capacity = 250.0
        game.gift(5_000.0, "Here")
        self.assertLessEqual(game.player.used_capacity, 250.0 + 1e-6)

    def test_a_full_wallet_is_told_plainly(self):
        game = Game(seed=3)
        game.player.capacity = 0.0
        self.assertIn("full", game.gift(5_000.0, "Here")[0])

    def test_a_missed_call_pays_nothing(self):
        game = to_first_offer()
        game.rng.randint = lambda a, b: 5        # the dice are rigged, for once
        before = game.player.used_capacity
        messages = game.roll_dice(10)
        self.assertIn("Nothing", " ".join(messages))
        self.assertAlmostEqual(game.player.used_capacity, before)

    def test_calling_it_exactly_pays_the_most(self):
        exact, near = Game(seed=4), Game(seed=4)
        for game, call in ((exact, 5), (near, 6)):
            while not game.dice_ready:
                ride(game)
            game.rng.randint = lambda a, b: 5
            game.player.capacity = 1e9           # so neither payout is capped
            game.roll_dice(call)
        self.assertGreater(exact.player.used_capacity, near.player.used_capacity)
        self.assertGreater(near.player.used_capacity, 0.0)


def play(calls, seed=5):
    game = to_first_offer(seed)
    for call in calls:
        while not game.dice_ready:
            ride(game)
        game.roll_dice(call)
    return game


class TestTheStreak(unittest.TestCase):
    def test_the_calls_start_it(self):
        self.assertTrue(play(HOT_HAND).hot_hand)

    def test_the_same_numbers_the_other_way_round_do_not(self):
        self.assertFalse(play(list(reversed(HOT_HAND))).hot_hand)

    def test_a_near_miss_does_not(self):
        self.assertFalse(play((HOT_HAND[0], HOT_HAND[1] + 1)).hot_hand)

    def test_it_pays_on_every_ride(self):
        game = play(HOT_HAND)
        game.player.capacity = 1e9          # so the gift is never capped
        before = game.player.used_capacity
        ride(game)
        self.assertGreater(game.player.used_capacity, before)

    def test_a_reload_cannot_shake_it_off(self):
        self.assertTrue(S.from_dict(S.to_dict(play(HOT_HAND))).hot_hand)


class TestAStreakCannotReachTheBoard(unittest.TestCase):
    """The whole reason a run can be handed money and nothing breaks."""

    def finished_streak_run(self):
        game = Game(seed=5)
        game.hot_hand = True
        game.stats["hot_hand"] = True
        game.player.debt = 0.0
        game.player.wallet.clear()
        game.player.cash = 900_000.0
        game.finalise()
        return game

    def test_it_is_not_given_a_grade_it_could_have_earned(self):
        self.assertEqual(P.run_grade(self.finished_streak_run()), P.UNRANKED_GRADE)

    def test_an_honest_run_is_still_graded_honestly(self):
        game = Game(seed=5)
        game.player.debt, game.player.cash = 0.0, 900_000.0
        game.player.wallet.clear()
        game.finalise()
        self.assertEqual(P.run_grade(game), "S+")

    def test_it_unlocks_nothing(self):
        profile = P.Profile()
        self.assertEqual(P.award(profile, self.finished_streak_run()), [])
        self.assertEqual(profile.runs, 0)
        self.assertEqual(profile.achievements, [])
        self.assertEqual(profile.best_net, 0.0)
        self.assertEqual(profile.best_tier_cleared, 0)

    def test_it_posts_nothing_and_costs_no_ranked_slot(self):
        profile = P.Profile()
        day = profile.roll_day(20_260_101)
        P.record_daily(profile, self.finished_streak_run(), 0, day)
        self.assertEqual(profile.daily_runs, [])
        self.assertEqual(profile.next_slot(day), 0)
        self.assertAlmostEqual(profile.daily_total(day), 0.0)

    def test_it_stays_off_the_personal_scoreboard(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(S, "home", lambda: Path(tmp)):
                self.assertEqual(S.record_score(self.finished_streak_run()), [])


if __name__ == "__main__":
    unittest.main()
