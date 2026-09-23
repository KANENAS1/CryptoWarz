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
