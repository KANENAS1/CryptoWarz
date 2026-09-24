"""The standoff: the one thing in the game that stops and asks.

Three properties carry it, and each is the sort of thing that rots quietly.

It must **block**. If a player can buy, sell or ride away from a man holding a
knife, the encounter is a message rather than a decision, and the whole feature
is decoration.

It must **ride the save**. A standoff you can close the tab on is a standoff
you never have to answer, which is savescumming with extra steps - the same
rule that already governs the dice and the market.

Its **odds must be the real ones**. The screen prints a percentage next to
every option; if that number is decorative, the choice it is attached to is a
button rather than a decision.
"""

import unittest

from cryptowarz import encounter as E
from cryptowarz import save as S
from cryptowarz.game import Game


def cornered(cash=8_000.0, weapon=None, rep=0, load=0.0, seed=11):
    game = Game(seed=seed)
    game.player.cash = cash
    game.player.capacity = 25_000.0
    game.weapon = weapon
    game.stats["rep"] = rep
    if load:
        game.player.holding("DOGE").cost = game.player.capacity * load
        game.player.holding("DOGE").qty = 1.0
    E.open_standoff(game)
    return game


class TestItStopsTheRun(unittest.TestCase):
    def test_everything_else_is_refused_while_somebody_waits(self):
        for call, args in (("buy", ("BTC", 0.001)), ("sell", ("BTC", 0.001)),
                           ("travel", ("Wall Street",)), ("spin_wheel", ()),
                           ("roll_dice", (3,)), ("borrow", (100.0,)),
                           ("repay", (10.0,)), ("deposit", (10.0,)),
                           ("withdraw", (10.0,)), ("buy_capacity", ()),
                           ("buy_vpn", ()), ("buy_weapon", ("pipe",))):
            game = cornered()
            with self.assertRaises(ValueError, msg=call) as caught:
                getattr(game, call)(*args)
            self.assertIn("in front of you", str(caught.exception), call)

    def test_answering_releases_it(self):
        game = cornered()
        game.resolve("pay")
        self.assertIsNone(game.pending)
        game.travel("Wall Street")           # no longer refused

    def test_there_is_no_way_to_answer_twice(self):
        game = cornered()
        game.resolve("run")
        with self.assertRaises(ValueError):
            game.resolve("run")

    def test_a_choice_that_is_not_offered_is_refused(self):
        game = cornered(weapon=None)
        self.assertNotIn("weapon", {c["key"] for c in game.choices()})
        with self.assertRaises(ValueError):
            game.resolve("weapon")
        self.assertIsNotNone(game.pending, "a refused answer must not clear it")


class TestItRidesTheSave(unittest.TestCase):
    def test_a_reload_finds_him_still_standing_there(self):
        game = cornered(weapon="bat")
        back = S.from_dict(S.to_dict(game))
        self.assertIsNotNone(back.pending)
        self.assertEqual(back.pending["kind"], game.pending["kind"])
        self.assertEqual(back.weapon, "bat")
        with self.assertRaises(ValueError):
            back.travel("Wall Street")

    def test_a_save_written_before_this_existed_still_loads(self):
        data = S.to_dict(Game(seed=4))
        del data["pending"]
        del data["weapon"]
        back = S.from_dict(data)
        self.assertIsNone(back.pending)
        self.assertIsNone(back.weapon)


class TestTheOddsAreTheRealOnes(unittest.TestCase):
    def test_the_printed_number_is_what_the_roll_uses(self):
        """Four thousand rolls against the number the screen shows."""
        import random
        game = cornered()
        predicted = E.odds(game, "run")
        wins = 0
        rng = random.Random(7)
        for _ in range(4_000):
            if rng.random() < predicted:
                wins += 1
        self.assertAlmostEqual(wins / 4_000, predicted, delta=0.02)

    def test_a_full_wallet_is_a_slow_wallet(self):
        """The sharpest idea in the encounter: the run that most needs to walk
        away is the one least able to."""
        light, heavy = cornered(load=0.0), cornered(load=1.0)
        self.assertGreater(E.odds(light, "run"), E.odds(heavy, "run"))
        self.assertAlmostEqual(E.odds(light, "run") - E.odds(heavy, "run"),
                               E.MAX_LOAD_PENALTY, places=6)

    def test_something_in_your_hand_beats_nothing(self):
        for key in ("brick", "pipe", "cutter", "bat", "taser"):
            game = cornered(weapon=key)
            self.assertGreater(E.odds(game, "weapon"), E.odds(game, "fight"), key)

    def test_the_armoury_is_ordered_and_every_step_costs_heat(self):
        by_edge = sorted(E.WEAPONS, key=lambda w: w.edge)
        self.assertEqual([w.heat for w in by_edge], sorted(w.heat for w in by_edge),
                         "a better weapon must always draw more attention")
        priced = [w for w in by_edge if w.price > 0]
        self.assertEqual([w.price for w in priced], sorted(w.price for w in priced))

    def test_a_reputation_moves_it_both_ways(self):
        soft, hard = cornered(rep=-3), cornered(rep=3)
        self.assertLess(E.odds(soft, "run"), E.odds(hard, "run"))
        self.assertLess(E.odds(soft, "fight"), E.odds(hard, "fight"))

    def test_paying_is_the_only_certainty_and_it_is_priced_like_one(self):
        game = cornered(cash=10_000.0)
        self.assertEqual(E.odds(game, "pay"), 1.0)
        self.assertGreater(E.pay_cost(game), 1_000.0)


class TestWhatItCostsYou(unittest.TestCase):
    def test_paying_buys_the_bag_and_sells_your_name(self):
        game = cornered(cash=10_000.0)
        game.player.holding("BTC").qty = 1.0
        game.resolve("pay")
        self.assertEqual(game.player.holding("BTC").qty, 1.0, "paying must keep the bag")
        self.assertLess(game.player.cash, 10_000.0)
        self.assertEqual(E.rep_of(game), -1)

    def test_standing_your_ground_builds_a_name_and_losing_spends_it(self):
        wins = losses = 0
        for seed in range(60):
            game = cornered(seed=seed, rep=0)
            game.resolve("fight")
            if E.rep_of(game) > 0:
                wins += 1
            elif E.rep_of(game) < 0:
                losses += 1
        self.assertGreater(wins, 5, "nobody ever won")
        self.assertGreater(losses, 5, "nobody ever lost")

    def test_it_can_never_strip_the_last_fare(self):
        """The same rule that governs every other event: you can be ruined,
        never made unable to play."""
        from cryptowarz.game import SUBWAY_FARE
        for seed in range(80):
            game = cornered(cash=40.0, seed=seed)
            game.resolve("fight")
            self.assertGreaterEqual(game.player.cash, min(40.0, SUBWAY_FARE) - 1e-9, seed)

    def test_carrying_something_cuts_both_ways(self):
        from cryptowarz import events as ev
        bare, armed = Game(seed=5), Game(seed=5)
        bare.day = armed.day = 22
        armed.weapon = "taser"
        self.assertGreater(ev.raid_chance(armed), ev.raid_chance(bare),
                           "a weapon must make the SEC look twice")
        names = [f.__name__ for f, _, _ in ev.EVENTS]
        i = names.index("stickup")
        self.assertLess(ev.event_weights(armed)[i], ev.event_weights(bare)[i],
                        "a weapon must make a mugger reconsider")


class TestTheShop(unittest.TestCase):
    def test_it_only_sells_where_there_is_a_shop(self):
        from cryptowarz.stations import STATIONS
        game = Game(seed=3)
        game.station = next(s for s in STATIONS if not s.has_upgrades)
        game.player.cash = 20_000.0
        with self.assertRaises(ValueError):
            game.buy_weapon("pipe")

    def test_it_takes_the_money_and_replaces_what_you_had(self):
        from cryptowarz.stations import STATIONS
        game = Game(seed=3)
        game.station = next(s for s in STATIONS if s.has_upgrades)
        game.player.cash = 20_000.0
        game.buy_weapon("pipe")
        self.assertEqual(game.weapon, "pipe")
        game.buy_weapon("bat")
        self.assertEqual(game.weapon, "bat", "you carry one thing")
        self.assertAlmostEqual(game.player.cash,
                               20_000.0 - E.WEAPON_BY_KEY["pipe"].price
                               - E.WEAPON_BY_KEY["bat"].price, places=2)

    def test_the_brick_is_not_for_sale(self):
        self.assertNotIn("brick", E.FOR_SALE, "the brick has to be found")


if __name__ == "__main__":
    unittest.main()


class TestEveryMoneyTakerIsAnswerable(unittest.TestCase):
    """The promise: nothing takes money without asking first.

    Four things used to reach into your pockets on their own - the mugger, the
    Shark's man, the SEC and a drainer - plus gas, which is not a person but is
    still a bill. All five stop now. This test is the list, so a future event
    that quietly takes money has to be added to it on purpose.
    """

    TAKERS = ("stickup", "followed", "collector", "badge", "drain", "gas")

    def test_every_one_of_them_offers_at_least_two_answers(self):
        for kind in self.TAKERS:
            game = cornered()
            game.pending = None
            E.open_standoff(game, kind)
            options = [c["key"] for c in game.choices()]
            self.assertGreaterEqual(len(options), 2, kind)
            self.assertEqual(len(options), len(set(options)), kind)

    def test_every_offered_answer_actually_resolves(self):
        """No option may be shown and then refused, and every one must clear."""
        for kind in self.TAKERS:
            for option in [c["key"] for c in
                           (lambda g: (E.open_standoff(g, kind), g.choices())[1])(cornered())]:
                game = cornered(weapon="bat", cash=9_000.0)
                game.pending = None
                game.player.debt = 12_000.0
                game.player.capacity = 1e9
                game.player.holding("BTC").qty = 1.0
                game.player.holding("BTC").cost = 5_000.0
                E.open_standoff(game, kind)
                if option not in {c["key"] for c in game.choices()}:
                    continue
                game.resolve(option)
                # "check" deliberately re-opens the same one, with the answer showing
                if option == "check":
                    self.assertTrue(game.pending["known"])
                    game.resolve("walk")
                self.assertIsNone(game.pending, f"{kind}/{option} left it open")

    def test_none_of_them_can_take_the_last_fare(self):
        from cryptowarz.game import SUBWAY_FARE
        for kind in self.TAKERS:
            for seed in range(20):
                game = cornered(cash=40.0, seed=seed)
                game.pending = None
                game.player.debt = 5_000.0
                E.open_standoff(game, kind)
                options = [c["key"] for c in game.choices()]
                game.resolve(options[-1])
                if game.pending:                 # "check" re-opens; finish it
                    game.resolve("walk")
                self.assertGreaterEqual(game.player.cash, min(40.0, SUBWAY_FARE) - 1e-9,
                                        f"{kind} seed {seed}")


class TestNerve(unittest.TestCase):
    def test_carrying_something_is_worth_luck(self):
        from cryptowarz.game import Game
        game = Game(seed=3)
        self.assertEqual(game.luck, 0.0)
        game.weapon = "taser"
        self.assertAlmostEqual(game.luck, E.WEAPON_BY_KEY["taser"].nerve)

    def test_it_never_stacks_on_gear(self):
        """The rule the whole luck system rests on: the best single bonus you
        have, never the sum. A weapon is not an exception."""
        from cryptowarz.game import Game
        from cryptowarz.gear import LUCK_PER_LEVEL, MAX_LEVEL
        game = Game(seed=3, gear={"major": MAX_LEVEL})
        game.player.holding("BTC").qty = 1.0
        bare = game.luck
        game.weapon = "taser"
        self.assertAlmostEqual(game.luck, bare)
        self.assertAlmostEqual(game.luck, MAX_LEVEL * LUCK_PER_LEVEL)

    def test_it_is_junior_to_gear_at_every_step(self):
        from cryptowarz.gear import LUCK_PER_LEVEL, MAX_LEVEL
        best = max(w.nerve for w in E.WEAPONS)
        self.assertLess(best, MAX_LEVEL * LUCK_PER_LEVEL / 2,
                        "a weapon must never rival a full set of gear")

    def test_better_weapons_carry_more_of_it(self):
        by_edge = sorted(E.WEAPONS, key=lambda w: w.edge)
        self.assertEqual([w.nerve for w in by_edge], sorted(w.nerve for w in by_edge))


class TestADayLostCannotOutrunTheEnd(unittest.TestCase):
    """A run walked past day thirty and kept going.

    The end-of-run check lived only in `travel`, which was true while riding
    somewhere was the only way to spend a day. A stopped train and a beating
    also take one, and a beating arrives inside a standoff, whose resolution
    had no check at all. So the clock passed the last day, the header clamped
    the display to it - a game that reads as frozen - the end screen never
    came, and a finished run was never scored. It happened to a real run worth
    $736,175, which is a bad way to find out.
    """

    def test_losing_a_day_on_the_last_day_ends_the_run(self):
        from cryptowarz.game import Game
        game = Game(seed=5)
        game.day = game.days
        game.lose_a_day()
        self.assertGreater(game.day, game.days)
        self.assertTrue(game.finished, "the clock passed the end and nothing noticed")

    def test_a_beating_at_the_end_ends_the_run(self):
        """The path it actually happened on: a standoff, not a train."""
        from cryptowarz.game import Game
        for seed in range(40):
            game = Game(seed=seed)
            game.day = game.days
            game.player.cash = 4_000.0
            game.player.capacity = 1e9
            game.player.holding("BTC").qty = 1.0
            game.player.holding("BTC").cost = 1_000.0
            E.open_standoff(game, "stickup")
            game.resolve("fight")
            if game.day > game.days:
                self.assertTrue(game.finished, f"seed {seed} ran past the end")
                return
        self.skipTest("no beating landed in forty seeds")

    def test_a_run_already_past_the_end_loads_finished(self):
        """The runs the bug already produced still have to close and score."""
        from cryptowarz.game import Game
        from cryptowarz import save as S
        data = S.to_dict(Game(seed=5))
        data["day"] = data["day"] + 40
        data["finished"] = False
        back = S.from_dict(data)
        self.assertTrue(back.finished)

    def test_an_ordinary_run_is_untouched(self):
        from cryptowarz.game import Game
        from cryptowarz import save as S
        game = Game(seed=5)
        game.day = 12
        self.assertFalse(S.from_dict(S.to_dict(game)).finished)
