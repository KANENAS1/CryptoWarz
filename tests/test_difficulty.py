"""Difficulty: a dial, not a ladder.

The tiers were already a difficulty ladder, but they are *progression* - you
unlock one by beating the one below. Somebody who wants a gentler thirty days
should not have to grind for it, and somebody who has cleared tier 5 should be
able to make tier 1 hurt again. So difficulty is a second axis, open on every
run from the first.

Two axes only work if they pay the board honestly, which is what most of this
file is about: an easier run must be worth less and a harder one more, the two
multipliers must compose rather than one quietly winning, and the choice has to
ride the save so a reload cannot change the rules mid-run.
"""

import unittest

from cryptowarz import progress as P
from cryptowarz import save as S
from cryptowarz.game import Game


class TestTheTable(unittest.TestCase):
    def test_there_is_a_normal_and_it_changes_nothing(self):
        normal = P.difficulty_of("normal")
        self.assertEqual(P.DEFAULT_DIFFICULTY, "normal")
        self.assertEqual((normal.cash, normal.debt_mult, normal.heat_mult, normal.score_mult),
                         (0.0, 1.0, 1.0, 1.0))
        self.assertEqual(normal.shark, 0.10, "Express must be the game as it was")

    def test_they_are_ordered_and_distinct(self):
        keys = [d.key for d in P.DIFFICULTIES]
        self.assertEqual(keys, ["easy", "normal", "hard"])
        mults = [d.score_mult for d in P.DIFFICULTIES]
        self.assertEqual(mults, sorted(mults), "a harder run must be worth more")
        sharks = [d.shark for d in P.DIFFICULTIES]
        self.assertEqual(sharks, sorted(sharks))

    def test_an_unknown_key_falls_back_rather_than_raising(self):
        """A save from an older build carries no difficulty at all, and a run
        that refuses to load is worse than a run that loads as Express."""
        self.assertEqual(P.difficulty_of(None).key, "normal")
        self.assertEqual(P.difficulty_of("nonsense").key, "normal")
        self.assertEqual(Game(seed=1, difficulty="nonsense").difficulty, "normal")


class TestItReachesTheRun(unittest.TestCase):
    def test_every_lever_lands(self):
        easy, normal, hard = (Game(seed=1, difficulty=k) for k in ("easy", "normal", "hard"))
        self.assertGreater(easy.player.cash, normal.player.cash)
        self.assertLess(easy.player.debt, normal.player.debt)
        self.assertGreater(hard.player.debt, normal.player.debt)
        self.assertLess(easy.shark_rate, normal.shark_rate)
        self.assertGreater(hard.shark_rate, normal.shark_rate)
        self.assertLess(easy.heat_mult, normal.heat_mult)
        self.assertGreater(hard.heat_mult, normal.heat_mult)

    def test_the_two_axes_multiply_rather_than_one_winning(self):
        from cryptowarz.progress import TIER_BY_LEVEL
        game = Game(seed=1, tier=3, difficulty="hard")
        self.assertAlmostEqual(game.heat_mult,
                               TIER_BY_LEVEL[3].heat_mult * P.difficulty_of("hard").heat_mult)

    def test_the_fixer_keeps_the_rate_it_always_promised(self):
        """The perk is a ratio now, so it is worth the same on every
        difficulty - and on Express it still lands on exactly 8.5%."""
        self.assertAlmostEqual(Game(seed=1, perk="fixer").shark_rate, 0.085)
        for key in ("easy", "hard"):
            plain = Game(seed=1, difficulty=key).shark_rate
            fixed = Game(seed=1, difficulty=key, perk="fixer").shark_rate
            self.assertAlmostEqual(fixed / plain, 0.85, places=9, msg=key)

    def test_the_debt_really_compounds_faster_on_hard(self):
        normal, hard = Game(seed=1), Game(seed=1, difficulty="hard")
        for _ in range(10):
            for game in (normal, hard):
                game.player.debt *= 1 + game.shark_rate
        self.assertGreater(hard.player.debt, normal.player.debt * 1.5)


class TestItPaysTheBoardHonestly(unittest.TestCase):
    def _finished(self, difficulty):
        game = Game(seed=9, difficulty=difficulty)
        game.player.debt = 0.0
        game.player.wallet.clear()
        game.player.cash = 100_000.0
        game.finalise()
        return game

    def test_the_same_net_worth_is_worth_less_on_easy(self):
        points = {k: P.run_points(self._finished(k)) for k in ("easy", "normal", "hard")}
        self.assertLess(points["easy"], points["normal"])
        self.assertGreater(points["hard"], points["normal"])

    def test_the_multipliers_compose_with_the_tier(self):
        game = self._finished("hard")
        game.tier = 3
        self.assertAlmostEqual(P.run_points(game),
                               100_000.0 * P.tier_mult(3) * P.difficulty_mult("hard"))

    def test_an_unrankable_run_is_still_unrankable_on_hard(self):
        """Difficulty must not become a way to launder god mode onto the
        board - the gate that was there before still comes first."""
        game = self._finished("hard")
        game.hot_hand = True
        self.assertFalse(P.counts_for_progress(game))
        self.assertEqual(P.run_grade(game), P.UNRANKED_GRADE)


class TestItRidesTheSave(unittest.TestCase):
    def test_a_reload_cannot_change_the_rules_mid_run(self):
        game = Game(seed=4, difficulty="hard")
        game.day = 12
        back = S.from_dict(S.to_dict(game))
        self.assertEqual(back.difficulty, "hard")
        self.assertAlmostEqual(back.shark_rate, game.shark_rate)
        self.assertAlmostEqual(back.player.debt, game.player.debt)
        self.assertAlmostEqual(back.heat_mult, game.heat_mult)

    def test_a_save_written_before_this_feature_still_loads(self):
        data = S.to_dict(Game(seed=4))
        del data["difficulty"]
        self.assertEqual(S.from_dict(data).difficulty, "normal")


if __name__ == "__main__":
    unittest.main()
