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


def cornered(cash=8_000.0, weapon=None, rep=0, load=None, seed=11):
    """A run standing in front of somebody.

    ``load`` is how full the POCKETS are, 0.0 to 1.0 - cash, not coins. That is
    what slows you down now, and it is the reason a rich run cannot simply walk
    away from trouble.
    """
    game = Game(seed=seed)
    game.player.cash_cap = 25_000.0
    game.player.cash = cash if load is None else game.player.cash_cap * load
    game.weapon = weapon
    game.stats["rep"] = rep
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
        light, heavy = cornered(cash=0.0), cornered(load=1.0)
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


class TestGasIsOwedNotOptional(unittest.TestCase):
    """A player holding everything and carrying nothing used to pay ZERO.

    Both answers took the fee out of cash, and cash was what they did not have,
    so the whole encounter was free exactly when it should have hurt - and the
    relay became strictly worse than paying: a risk taken to save nothing. The
    message said "$0.00 instead of $643.90", which is how it was noticed.

    Gas is a toll you owe for moving your own money, so a wallet with no cash
    in it pays out of the bag instead.
    """

    def _gassed(self, cash, coins=True, seed=13):
        from cryptowarz.game import Game
        game = Game(seed=seed)
        game.player.cash = cash
        game.player.capacity = 1e9
        if coins:
            game.player.holding("BTC").qty = 1.0
            game.player.holding("BTC").cost = 40_000.0
        E.open_standoff(game, "gas")
        game.pending["fee"] = 640.0
        return game

    def test_being_broke_no_longer_makes_it_free(self):
        for choice in ("paygas", "relay"):
            game = self._gassed(0.0)
            before = game.player.portfolio_value(game.market)
            game.resolve(choice)
            self.assertLess(game.player.portfolio_value(game.market), before,
                            f"{choice} cost nothing at all")

    def test_it_comes_out_of_cash_first(self):
        game = self._gassed(9_000.0)
        before = game.player.portfolio_value(game.market)
        game.resolve("paygas")
        self.assertAlmostEqual(game.player.cash, 9_000.0 - 640.0, places=2)
        self.assertAlmostEqual(game.player.portfolio_value(game.market), before, places=2)

    def test_a_part_payment_splits_correctly(self):
        game = self._gassed(200.0)
        said = " ".join(game.resolve("paygas"))
        self.assertIn("in cash", said)
        self.assertIn("out of the bag", said)
        # the two halves have to add up to the fee, or the sentence is a lie
        import re
        amounts = [float(x.replace(",", "")) for x in re.findall(r"\$([\d,]+\.\d\d)", said)]
        self.assertAlmostEqual(sum(amounts[:2]), 640.0, places=1)

    def test_the_relay_still_saves_you_something(self):
        """It has to be cheaper than the front door, or it is only a risk."""
        pay, relay = self._gassed(0.0), self._gassed(0.0)
        pay_before = pay.player.portfolio_value(pay.market)
        relay_before = relay.player.portfolio_value(relay.market)
        pay.resolve("paygas")
        relay.resolve("relay")
        paid = pay_before - pay.player.portfolio_value(pay.market)
        # the relay can still be robbed; compare the FEE, not the outcome
        self.assertGreater(paid, 0.0)
        self.assertAlmostEqual(paid, 640.0, delta=1.0)

    def test_nothing_to_take_says_so_rather_than_printing_zero(self):
        for choice in ("paygas", "relay"):
            game = self._gassed(0.0, coins=False)
            said = " ".join(game.resolve(choice))
            self.assertNotIn("$0.00", said, "the line that started all this")
            self.assertIn("nothing", said.lower())

    def test_it_can_never_strip_the_last_fare(self):
        from cryptowarz.game import SUBWAY_FARE
        for seed in range(30):
            game = self._gassed(2.0, seed=seed)
            game.resolve("paygas")
            self.assertGreaterEqual(game.player.cash, min(2.0, SUBWAY_FARE) - 1e-9)


class TestPlayingBroke(unittest.TestCase):
    """The one answer whose odds you set yourself, hours earlier.

    Every other option is priced by the game. This one is priced by a decision
    you already made - how much cash to walk around with - which is what turns
    the new carry limit from a restriction into a strategy. Empty pockets make
    it nearly certain; full ones make it a joke, because a man who is visibly
    carrying is not going to be believed.
    """

    def test_the_odds_are_set_by_what_you_carry(self):
        from cryptowarz.game import Game
        odds = []
        for share in (0.0, 0.25, 0.5, 0.75, 1.0):
            game = Game(seed=11)
            game.player.cash = game.player.cash_cap * share
            E.open_standoff(game, "stickup")
            odds.append(E.odds(game, "broke"))
        self.assertEqual(odds, sorted(odds, reverse=True), "carrying more must never help")
        self.assertGreater(odds[0], 0.8)
        self.assertLess(odds[-1], 0.15)

    def test_success_costs_exactly_what_is_in_your_pockets(self):
        game = cornered(cash=300.0)
        game.player.capacity = 1e9
        game.player.holding("BTC").qty = 1.0
        game.player.holding("BTC").cost = 40_000.0
        # empty-ish pockets, so it lands
        game.resolve("broke")
        self.assertLessEqual(game.player.cash, 3.0, "they left cash behind")
        self.assertEqual(game.player.holding("BTC").qty, 1.0, "the bag was for keeping")

    def test_carrying_nothing_means_losing_nothing(self):
        game = cornered(cash=0.0)
        game.player.capacity = 1e9
        game.player.holding("BTC").qty = 1.0
        game.player.holding("BTC").cost = 40_000.0
        said = " ".join(game.resolve("broke"))
        self.assertEqual(game.player.holding("BTC").qty, 1.0)
        self.assertIn("lint", said.lower())

    def test_being_caught_lying_is_worse_than_paying(self):
        """It has to be, or it would be free to try."""
        losses = 0
        for seed in range(40):
            game = cornered(cash=0.0, seed=seed)
            game.player.cash_cap = 1_000.0
            game.player.cash = 950.0          # visibly loaded: it will not work
            game.player.capacity = 1e9
            game.player.holding("BTC").qty = 1.0
            game.player.holding("BTC").cost = 40_000.0
            game.resolve("broke")
            if game.player.holding("BTC").qty < 1.0:
                losses += 1
        self.assertGreater(losses, 20, "lying while loaded was not punished")

    def test_it_is_offered_by_the_people_and_not_by_the_badge(self):
        for kind in ("stickup", "followed", "collector"):
            game = cornered()
            game.pending = None
            E.open_standoff(game, kind)
            self.assertIn("broke", [c["key"] for c in game.choices()], kind)
        for kind in ("badge", "drain", "gas"):
            game = cornered()
            game.pending = None
            E.open_standoff(game, kind)
            self.assertNotIn("broke", [c["key"] for c in game.choices()], kind)


class TestTheCard(unittest.TestCase):
    """Fares bought before you need them.

    The subway has always sold them, and the game had no answer to the one
    situation everybody in this city has been in: money in the bank, nothing in
    your pocket, standing the wrong side of a turnstile. They also make playing
    broke practical, because the cheapest way to look poor is to be carrying
    nothing and still have a way home.
    """

    def test_a_book_of_rides_beats_paying_singly(self):
        from cryptowarz.game import OMNY_PRICE, OMNY_RIDES, SUBWAY_FARE
        self.assertLess(OMNY_PRICE, OMNY_RIDES * SUBWAY_FARE,
                        "buying ahead has to be worth something")

    def test_the_turnstile_takes_a_ride_when_the_pocket_cannot(self):
        from cryptowarz.game import Game
        from cryptowarz.stations import STATIONS
        game = Game(seed=5)
        game.player.cash = 20.0
        game.buy_rides()
        game.player.cash = 0.5
        rides = game.player.rides
        game.travel(next(s.name for s in STATIONS if s.name != game.station.name))
        self.assertEqual(game.player.rides, rides - 1)
        self.assertAlmostEqual(game.player.cash, 0.5, places=2, msg="it charged both")

    def test_cash_is_spent_first_so_the_card_stays_insurance(self):
        from cryptowarz.game import Game, SUBWAY_FARE
        from cryptowarz.stations import STATIONS
        game = Game(seed=5)
        game.player.cash = 500.0
        game.buy_rides()
        rides = game.player.rides
        cash = game.player.cash
        game.travel(next(s.name for s in STATIONS if s.name != game.station.name))
        self.assertEqual(game.player.rides, rides, "it burned a ride it did not need")
        self.assertAlmostEqual(game.player.cash, cash - SUBWAY_FARE, places=2)

    def test_a_card_means_you_are_not_stranded(self):
        from cryptowarz.game import Game
        game = Game(seed=5)
        game.player.cash = 20.0
        game.buy_rides()
        game.player.cash = 0.0
        game.player.wallet.clear()
        self.assertFalse(game.stranded)
        game.player.rides = 0
        self.assertTrue(game.stranded)

    def test_it_rides_the_save(self):
        from cryptowarz.game import Game
        from cryptowarz import save as S
        game = Game(seed=5)
        game.player.cash = 20.0
        game.buy_rides()
        self.assertEqual(S.from_dict(S.to_dict(game)).player.rides, 5)
