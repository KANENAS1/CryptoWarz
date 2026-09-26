"""Robbing other players, and the four rules that stop it ruining the game.

These are not incidental checks. Each one guards a way this kind of feature
normally goes wrong: it eats somebody's run, it settles behind their back, it
lets a thief conjure money, or it can be reloaded until it pays.
"""

import unittest

from cryptowarz import lift as L
from cryptowarz.encounter import REP_MAX, bump_rep
from cryptowarz.game import Game


def a_mark(**over):
    base = dict(uid="u2", name="Somebody", station="Wall Street", day=9,
                pockets=40_000.0, luck=0.0, weapon=None, rep=0, at=1000.0)
    base.update(over)
    return L.Mark(**base)


class TestOnlyThePocketsAreLiftable(unittest.TestCase):
    """The vault and the whole crypto wallet are out of reach, always.

    This is the rule the wallet inversion was for: cash is the heavy, visible
    thing you carry, and coins are weightless numbers nobody can take off you
    on a platform. It also hands the vault a second reason to exist.
    """

    def test_a_mark_advertises_pockets_and_nothing_else(self):
        game = Game(seed=4)
        game.player.cash = 30_000.0
        game.player.vault = 500_000.0
        qty = game.max_buyable("DOGE") * 0.5
        if qty > 0:
            game.buy("DOGE", qty)
        mark = L.mark_from(game, "u1", "Me", at=1.0)
        self.assertEqual(mark.pockets, game.player.cash)
        blob = mark.__dict__ if hasattr(mark, "__dict__") else {}
        for hidden in ("vault", "wallet", "debt"):
            self.assertNotIn(hidden, blob)

    def test_the_cut_is_bounded_by_the_pockets_and_by_a_ceiling(self):
        self.assertAlmostEqual(L.cut_for(a_mark(pockets=10_000.0)),
                               10_000.0 * L.CUT_SHARE)
        self.assertEqual(L.cut_for(a_mark(pockets=10_000_000.0)), L.CUT_MAX)
        self.assertEqual(L.cut_for(a_mark(pockets=0.0)), 0.0)

    def test_being_robbed_is_a_bad_night_and_never_a_run(self):
        """However rich the mark and however badly they answer, a lift leaves
        most of the coat behind. Checked against the WORST answer, not the
        average one - the floor has to hold where it is lowest."""
        for pockets in (5_000.0, 50_000.0, 250_000.0, 2_000_000.0):
            mark = a_mark(pockets=pockets)
            opened = L.open_lift("u1", "Me", mark, 0.0, None, 0, 1000.0, 3, 5.0)
            worst = max(-L.settle(opened, choice, 0.999, 0.0, None, 0)["mark_delta"]
                        for choice in L.ANSWERS)
            self.assertLess(worst, pockets * 0.5,
                            f"a single lift took half of {pockets:,.0f}")

    def test_a_vaulted_run_carries_nothing_worth_taking(self):
        game = Game(seed=7)
        game.player.cash = 0.0
        game.player.vault = 300_000.0
        mark = L.mark_from(game, "u1", "Me", at=1.0)
        self.assertFalse(L.worth_lifting(mark, 100_000.0),
                         "money in the vault is still showing on the platform")


class TestNobodyLosesMoneyWithoutAnswering(unittest.TestCase):
    """An attempt waits. It is not applied to anybody."""

    def test_an_attempt_opens_unsettled(self):
        opened = L.open_lift("u1", "Me", a_mark(), 0.0, None, 0, stake=1000.0,
                             day=3, at=5.0)
        self.assertEqual(opened["state"], "open")
        for settled_only in ("outcome", "mark_delta", "thief_delta"):
            self.assertNotIn(settled_only, opened,
                             "the attempt already decided something")

    def test_every_answer_settles_it(self):
        opened = L.open_lift("u1", "Me", a_mark(), 0.0, None, 0, stake=1000.0,
                             day=3, at=5.0)
        for choice in L.ANSWERS:
            done = L.settle(opened, choice, roll=0.5, luck=0.0, weapon_key=None, rep=0)
            self.assertEqual(done["state"], "settled", choice)
            self.assertIn(done["outcome"],
                          ("held", "taken", "countered", "botched", "paid"))

    def test_an_answer_nobody_offered_is_refused(self):
        opened = L.open_lift("u1", "Me", a_mark(), 0.0, None, 0, 1000.0, 3, 5.0)
        with self.assertRaises(ValueError):
            L.settle(opened, "vanish", 0.5, 0.0, None, 0)

    def test_paying_is_certain_and_costs_less_than_being_taken(self):
        mark = a_mark()
        self.assertEqual(L.answer_odds("buyoff", {}, 0.0, None, 0), 1.0)
        self.assertLess(L.buyoff_for(mark), L.cut_for(mark))


class TestTheThiefCanOnlyLoseTheStake(unittest.TestCase):
    """The settlement is written by the mark and read by the thief, so a loss
    the thief has not already taken is a loss that cannot be collected."""

    def test_no_settlement_ever_asks_the_thief_for_more(self):
        opened = L.open_lift("u1", "Me", a_mark(), 0.0, None, 0, stake=1000.0,
                             day=3, at=5.0)
        for choice in L.ANSWERS:
            for roll in (0.0, 0.25, 0.5, 0.75, 0.999):
                done = L.settle(opened, choice, roll, 0.0, None, 0)
                self.assertGreaterEqual(done["thief_delta"], 0.0,
                                        f"{choice}/{roll} bills the thief")

    def test_a_turned_lift_pays_the_mark_exactly_the_stake(self):
        opened = L.open_lift("u1", "Me", a_mark(), 0.0, None, 0, stake=1500.0,
                             day=3, at=5.0)
        held = L.settle(opened, "brace", roll=0.0, luck=0.15, weapon_key="bat", rep=REP_MAX)
        self.assertEqual(held["outcome"], "held")
        self.assertEqual(held["mark_delta"], 1500.0)
        self.assertEqual(held["thief_delta"], 0.0, "the stake was paid twice")

    def test_money_is_conserved_across_every_settlement(self):
        """What one side gains, the other side put up. No settlement invents
        cash, and none of it evaporates."""
        stake, mark = 1500.0, a_mark()
        opened = L.open_lift("u1", "Me", mark, 0.0, None, 0, stake=stake, day=3, at=5.0)
        for choice in L.ANSWERS:
            for roll in (0.0, 0.5, 0.999):
                done = L.settle(opened, choice, roll, 0.0, None, 0)
                # the thief is already out the stake; the books must balance
                moved = done["mark_delta"] + done["thief_delta"] - stake
                self.assertAlmostEqual(moved, 0.0, places=2,
                                       msg=f"{choice}/{roll} moved {moved:,.2f} "
                                           f"that nobody paid")

    def test_a_lift_is_sized_by_what_the_thief_puts_up(self):
        """The number the whole economy turns on. A thief with very little can
        still have a go at a rich mark - they simply cannot go for much of it,
        because what you can take is bought by what you are risking."""
        rich = a_mark(pockets=200_000.0)
        poor_stake = L.stake_for(2_000.0, rich)
        rich_stake = L.stake_for(200_000.0, rich)
        self.assertLess(poor_stake, rich_stake)
        self.assertLessEqual(poor_stake, 2_000.0 * L.MAX_STAKE_SHARE + 1e-9,
                             "nobody is made to put up more than half their coat")
        self.assertLess(L.cut_for(rich, poor_stake), L.cut_for(rich, rich_stake),
                        "a small stake bought a big lift")

    def test_an_even_matchup_is_worth_almost_nothing(self):
        """Priced so that robbing a peer is a waste of a day. Measured, not
        asserted: the first version paid a bare thief $7,495 on a coin flip."""
        mark = a_mark(pockets=60_000.0)
        stake = L.stake_for(30_000.0, mark)
        lift = L.open_lift("u1", "Me", mark, 0.0, None, 0, stake, 3, 5.0)
        odds = 1.0 - L.answer_odds("brace", lift, 0.0, None, 0)
        edge = odds * lift["cut"] - (1.0 - odds) * stake
        self.assertLess(abs(edge), stake * 0.1,
                        f"robbing a peer is worth {edge:,.0f} a go")

    def test_a_new_run_is_not_on_the_platform_at_all(self):
        """The same grace the SEC gives you, for the same reason."""
        game = Game(seed=6)
        game.player.cash = 50_000.0
        self.assertFalse(L.leaves_a_mark(game), "day one is already a target")
        game.day = L.LIFT_GRACE_DAYS + 1
        self.assertTrue(L.leaves_a_mark(game))
        game.finished = True
        self.assertFalse(L.leaves_a_mark(game),
                         "a finished run is a score, not a person standing somewhere")


class TestTheRollBelongsToTheMark(unittest.TestCase):
    """Neither side can reload into a better answer."""

    def test_the_attempt_carries_no_result(self):
        opened = L.open_lift("u1", "Me", a_mark(), 0.10, "bat", 2, 1000.0, 3, 5.0)
        self.assertNotIn("roll", opened)
        self.assertNotIn("won", opened)

    def test_the_same_roll_always_settles_the_same_way(self):
        opened = L.open_lift("u1", "Me", a_mark(), 0.0, None, 0, 1000.0, 3, 5.0)
        first = L.settle(opened, "brace", 0.4, 0.05, "pipe", 1)
        again = L.settle(opened, "brace", 0.4, 0.05, "pipe", 1)
        self.assertEqual(first, again)

    def test_a_mark_is_robbed_as_they_are_not_as_they_advertised(self):
        """Gear bought between the attempt and the answer counts."""
        opened = L.open_lift("u1", "Me", a_mark(), 0.0, None, 0, 1000.0, 3, 5.0)
        bare = L.answer_odds("brace", opened, luck=0.0, weapon_key=None, rep=0)
        armed = L.answer_odds("brace", opened, luck=0.15, weapon_key="bat", rep=REP_MAX)
        self.assertGreater(armed, bare, "turning up prepared bought nothing")


class TestGearAndNerveActuallyDefend(unittest.TestCase):
    """What the player asked for: gear blocks, and a counter takes."""

    def test_gear_makes_you_harder_to_take_from(self):
        plain = L.guard_of(0.0, None, 0)
        geared = L.guard_of(0.15, None, 0)
        self.assertGreater(geared, plain)

    def test_a_weapon_defends_but_attacks_better(self):
        mark = a_mark()
        unarmed = L.lift_odds(0.0, None, 0, mark)
        armed = L.lift_odds(0.0, "bat", 0, mark)
        defended = L.lift_odds(0.0, None, 0, a_mark(weapon="bat"))
        self.assertGreater(armed, unarmed, "a weapon did not help the thief")
        self.assertLess(defended, unarmed, "a weapon did not help the mark")
        self.assertGreater(armed - unarmed, unarmed - defended,
                           "a bat should take better than it keeps")

    def test_a_loaded_mark_is_a_slow_mark(self):
        """The same rule as running from a stickup, pointed the other way: the
        richest coat on the platform is also the one worth the most."""
        self.assertGreater(L.cut_for(a_mark(pockets=80_000.0)),
                           L.cut_for(a_mark(pockets=8_000.0)))

    def test_a_reputation_works_on_both_sides_of_it(self):
        mark = a_mark()
        self.assertGreater(L.lift_odds(0.0, None, REP_MAX, mark),
                           L.lift_odds(0.0, None, -REP_MAX, mark))
        self.assertLess(L.lift_odds(0.0, None, 0, a_mark(rep=REP_MAX)),
                        L.lift_odds(0.0, None, 0, a_mark(rep=-REP_MAX)))

    def test_bare_handed_a_counter_is_the_harder_call(self):
        opened = L.open_lift("u1", "Me", a_mark(), 0.0, None, 0, 1000.0, 3, 5.0)
        self.assertLess(L.answer_odds("counter", opened, 0.0, None, 0),
                        L.answer_odds("brace", opened, 0.0, None, 0),
                        "chasing somebody empty-handed should be the worse bet")

    def test_a_weapon_is_what_makes_a_counter_worth_calling(self):
        """The point of carrying something: gear does not only make you harder
        to rob, it changes which answer is the right one."""
        opened = L.open_lift("u1", "Me", a_mark(), 0.0, None, 0, 1000.0, 3, 5.0)
        bare = L.answer_odds("counter", opened, 0.0, None, 0)
        armed = L.answer_odds("counter", opened, 0.05, "bat", 0)
        self.assertGreater(armed, bare)
        self.assertGreater(armed, L.answer_odds("brace", opened, 0.0, None, 0),
                           "a bat should make the chase worth having")

    def test_a_counter_pays_more_and_costs_more(self):
        """It is never strictly better than bracing: the same weapon that wins
        the chase makes losing it more expensive than standing still."""
        opened = L.open_lift("u1", "Me", a_mark(), 0.0, None, 0, 1000.0, 3, 5.0)
        won_brace = L.settle(opened, "brace", 0.0, 0.05, "bat", 0)
        won_counter = L.settle(opened, "counter", 0.0, 0.05, "bat", 0)
        self.assertGreater(won_counter["mark_rep"], won_brace["mark_rep"])
        self.assertLess(won_counter["thief_rep"], won_brace["thief_rep"])

        lost_brace = L.settle(opened, "brace", 0.999, 0.05, "bat", 0)
        lost_counter = L.settle(opened, "counter", 0.999, 0.05, "bat", 0)
        self.assertLess(lost_counter["mark_delta"], lost_brace["mark_delta"],
                        "a missed chase cost no more than standing still")

    def test_a_botched_counter_costs_standing_as_well_as_cash(self):
        opened = L.open_lift("u1", "Me", a_mark(), 0.0, None, 0, 1000.0, 3, 5.0)
        lost = L.settle(opened, "counter", 0.999, 0.0, None, 0)
        self.assertEqual(lost["outcome"], "botched")
        self.assertLess(lost["mark_rep"], 0)


class TestRepAndTheStreetRecord(unittest.TestCase):
    def test_reputation_stays_inside_its_bounds(self):
        game = Game(seed=2)
        for _ in range(20):
            bump_rep(game, 2)
        self.assertLessEqual(game.stats["rep"], REP_MAX)
        for _ in range(40):
            bump_rep(game, -2)
        self.assertGreaterEqual(game.stats["rep"], -REP_MAX)

    def test_turning_somebody_away_is_worth_more_than_taking(self):
        took = L.street_points({"took": 1, "held": 0, "lost": 0, "countered": 0})
        held = L.street_points({"took": 0, "held": 1, "lost": 0, "countered": 0})
        countered = L.street_points({"took": 0, "held": 0, "lost": 0, "countered": 1})
        self.assertGreater(held, took)
        self.assertGreater(countered, held)

    def test_the_record_counts_each_side_of_the_same_lift(self):
        thief, mark = {}, {}
        L.credit_street(thief, "held", as_thief=True)
        L.credit_street(mark, "held", as_thief=False)
        self.assertEqual(L.street_record(thief)["lost"], 1)
        self.assertEqual(L.street_record(mark)["held"], 1)

        thief2, mark2 = {}, {}
        L.credit_street(thief2, "taken", as_thief=True)
        L.credit_street(mark2, "taken", as_thief=False)
        self.assertEqual(L.street_record(thief2)["took"], 1)
        self.assertEqual(L.street_record(mark2)["lost"], 1)

    def test_a_blank_profile_reads_as_a_blank_record(self):
        self.assertEqual(L.street_record({}),
                         {"took": 0, "held": 0, "lost": 0, "countered": 0})


class TestMarksGoCold(unittest.TestCase):
    def test_a_week_old_mark_is_not_a_target(self):
        fresh = a_mark(at=1_000.0)
        self.assertFalse(L.is_stale(fresh, now=1_000.0 + 3600))
        self.assertTrue(L.is_stale(fresh, now=1_000.0 + L.MARK_STALE_SECONDS + 1))

    def test_the_odds_never_reach_certainty_either_way(self):
        hopeless = L.lift_odds(0.0, None, -REP_MAX,
                               a_mark(luck=0.15, weapon="taser", rep=REP_MAX))
        certain = L.lift_odds(0.15, "taser", REP_MAX,
                              a_mark(luck=0.0, weapon=None, rep=-REP_MAX))
        self.assertGreaterEqual(hopeless, L.ODDS_FLOOR)
        self.assertLessEqual(certain, L.ODDS_CEIL)


if __name__ == "__main__":
    unittest.main()
