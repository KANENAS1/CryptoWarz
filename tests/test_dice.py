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
from cryptowarz.game import (DICE_EVERY, DICE_LADDER, DICE_SIDES, DICE_TOP_PRIZE,
                             HOT_HAND, HOT_HAND_CHANCE, HOT_HAND_MAX,
                             HOT_HAND_MIN, Game, dice_tier)
from cryptowarz.stations import STATIONS


#: The middle of the die, and a call low enough that every rung of the ladder
#: still fits above it. Derived rather than written down, because the die has
#: already changed size once and these tests should not have to.
MIDDLE = (DICE_SIDES + 1) // 2
LOW = 1


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
        game.roll_dice(MIDDLE)
        self.assertFalse(game.dice_ready)
        with self.assertRaises(ValueError):
            game.roll_dice(MIDDLE)

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

    def paid_for_calling(self, call, rolled=None, gear=None):
        """What one rigged roll actually puts in the wallet."""
        rolled = LOW if rolled is None else rolled
        game = Game(seed=4, gear=gear or {})
        while not game.dice_ready:
            ride(game)
        game.rng.randint = lambda a, b: rolled   # the dice are rigged, for once
        game.player.capacity = 1e9               # so no payout is clipped
        if gear:                                 # luck only counts while holding
            game.player.holding("DOGE").qty = 1_000.0
        before = game.player.used_capacity
        game.roll_dice(call)
        return game.player.used_capacity - before

    def test_a_call_miles_off_pays_nothing(self):
        game = to_first_offer()
        game.rng.randint = lambda a, b: 1
        before = game.player.used_capacity
        messages = game.roll_dice(DICE_SIDES)
        self.assertIn("Nothing", " ".join(messages))
        self.assertAlmostEqual(game.player.used_capacity, before)

    def test_the_payout_falls_off_the_further_you_are(self):
        """The whole point of grading it: closer is worth more, every step."""
        paid = [self.paid_for_calling(LOW + d) for d in range(len(DICE_LADDER) + 1)]
        self.assertEqual(paid, sorted(paid, reverse=True), f"not monotonic: {paid}")
        self.assertGreater(paid[0], 0.0)
        self.assertEqual(paid[-1], 0.0, "something beyond the ladder still paid")

    def test_every_rung_pays_its_advertised_share(self):
        for reach, _label, share in DICE_LADDER:
            self.assertAlmostEqual(self.paid_for_calling(LOW + reach),
                                   DICE_TOP_PRIZE * share, places=4, msg=f"±{reach}")

    def test_being_one_off_is_worth_a_real_fraction_not_a_token(self):
        """A consolation nobody notices is the same as no consolation."""
        self.assertGreater(self.paid_for_calling(LOW + 1), self.paid_for_calling(LOW) * 0.2)

    def test_gear_you_are_holding_for_lifts_the_prize(self):
        from cryptowarz.gear import LUCK_PER_LEVEL, MAX_LEVEL
        bare = self.paid_for_calling(LOW)
        geared = self.paid_for_calling(LOW, gear={"meme": MAX_LEVEL})
        self.assertAlmostEqual(geared, bare * (1 + MAX_LEVEL * LUCK_PER_LEVEL), places=4)

    def test_a_middle_call_is_worth_more_than_an_edge_one(self):
        """Exact arithmetic, and the only decision the dice actually offer."""
        def value(pick):
            return sum(dice_tier(abs(pick - r))[1] for r in range(1, DICE_SIDES + 1))
        self.assertGreater(value(MIDDLE), value(1))
        # the die is symmetric, so mirrored calls must be worth the same
        for pick in range(1, DICE_SIDES + 1):
            self.assertAlmostEqual(value(pick), value(DICE_SIDES + 1 - pick), msg=str(pick))


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

    def test_it_pays_often_but_not_every_time(self):
        game = play(HOT_HAND)
        game.player.capacity = 1e9          # so nothing is clipped
        paid = 0
        for _ in range(2_000):
            before = game.player.used_capacity
            game._streak_gift()
            if game.player.used_capacity > before:
                paid += 1
        self.assertAlmostEqual(paid / 2_000, HOT_HAND_CHANCE, delta=0.05)
        self.assertLess(paid, 2_000, "a payout you can count on is not a windfall")

    def test_the_amount_varies_and_never_clears_the_ceiling(self):
        game = play(HOT_HAND)
        game.player.capacity = 1e9
        amounts = []
        for _ in range(2_000):
            before = game.player.used_capacity
            game._streak_gift()
            got = game.player.used_capacity - before
            if got > 0:
                amounts.append(got)
        self.assertGreater(len(set(round(a, 2) for a in amounts)), 100, "a flat payout")
        self.assertLessEqual(max(amounts), HOT_HAND_MAX + 1e-6)
        self.assertGreaterEqual(min(amounts), HOT_HAND_MIN - 1e-6)
        # squared draw: most payouts sit nearer the floor than the ceiling
        midpoint = (HOT_HAND_MIN + HOT_HAND_MAX) / 2
        self.assertGreater(sum(a < midpoint for a in amounts) / len(amounts), 0.6)

    def test_a_full_wallet_is_why_a_ride_can_pay_nothing(self):
        """The other reason a ride comes up empty, and the one worth saying.

        Free crypto still needs somewhere to go. A player on a streak who never
        sells fills the wallet and then watches rides arrive with nothing on
        them - that is the capacity rule doing its job, not a broken payout.
        """
        game = play(HOT_HAND)
        game.player.capacity = game.player.used_capacity   # not a cent of room
        before = game.player.used_capacity
        for _ in range(20):
            game._streak_gift()
        self.assertAlmostEqual(game.player.used_capacity, before)

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
