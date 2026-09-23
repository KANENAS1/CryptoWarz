"""Gear: earned by winning, bounded by design.

Two properties carry this feature. Gear must follow the *bag* rather than the
player, so owning a charm and holding nothing does nothing. And luck must never
be a sum, because a build that stacks four bonuses into immunity would flatten
a game that is supposed to be about nerve. Both are asserted here rather than
assumed.
"""

import unittest

from cryptowarz import gear as G
from cryptowarz import progress as P
from cryptowarz import save as S
from cryptowarz.coins import COINS
from cryptowarz.game import Game
from cryptowarz.stations import STATIONS

FULL = {key: G.MAX_LEVEL for key in G.CLASSES}


def finished(net_worth, symbols=(), tier=1, gear=None, streak=False):
    """A finished run worth roughly ``net_worth``, holding ``symbols``."""
    game = Game(seed=5, tier=tier, gear=gear or {})
    game.player.debt = 0.0
    game.player.wallet.clear()
    game.player.capacity = 1e9
    game.player.cash = net_worth
    game.hot_hand = streak
    for symbol in symbols:
        price = game.market.price(symbol)
        held = game.player.holding(symbol)
        held.qty += 1_000.0 / price
        held.cost += 1_000.0
        game.player.cash -= 1_000.0
    game.finalise()
    return game


def _answer_any(game):
    """These tests ride trains; a standoff blocks everything until answered.

    The encounter is a real part of a run now, so a harness that ignored one
    would simply stop at the first mugger. Answering with the best odds is what
    a player does and what the balance bots do.
    """
    from cryptowarz.encounter import best_choice

    if getattr(game, "pending", None):
        game.resolve(best_choice(game))


class TestTheClassTable(unittest.TestCase):
    def test_every_coin_belongs_to_exactly_one_class(self):
        listed = [sym for syms in G.CLASSES.values() for sym in syms]
        self.assertEqual(sorted(listed), sorted(c.symbol for c in COINS))
        self.assertEqual(len(listed), len(set(listed)), "a coin is in two classes")

    def test_there_is_one_piece_of_gear_per_class(self):
        self.assertEqual(sorted(p.key for p in G.GEAR), sorted(G.CLASSES))

    def test_levels_arrive_on_the_advertised_wins(self):
        self.assertEqual([G.level_for(w) for w in (0, 1, 2, 3, 6, 7, 40)],
                         [0, 1, 1, 2, 2, 3, 3])
        self.assertEqual(G.level_for(10 ** 6), G.MAX_LEVEL, "levels must cap")


class TestLuckFollowsTheBag(unittest.TestCase):
    def test_gear_you_are_not_holding_for_does_nothing(self):
        game = Game(seed=5, gear=FULL)
        self.assertEqual(game.luck, 0.0, "full gear paid out on an empty wallet")

    def test_holding_the_right_coin_turns_it_on(self):
        game = Game(seed=5, gear={"meme": 3})
        game.buy("DOGE", game.max_buyable("DOGE") * 0.5)
        self.assertAlmostEqual(game.luck, 3 * G.LUCK_PER_LEVEL)

    def test_holding_a_coin_you_have_no_gear_for_does_nothing(self):
        game = Game(seed=5, gear={"meme": 3})
        game.buy("BTC", game.max_buyable("BTC") * 0.5)
        self.assertEqual(game.luck, 0.0)

    def test_selling_out_turns_it_off_again(self):
        game = Game(seed=5, gear={"meme": 3})
        game.buy("DOGE", game.max_buyable("DOGE") * 0.5)
        game.sell("DOGE", game.player.wallet["DOGE"].qty)
        self.assertEqual(game.luck, 0.0)


class TestLuckIsNeverASum(unittest.TestCase):
    """The property that stops a collection becoming immunity."""

    def test_four_pieces_are_worth_the_same_as_the_best_one(self):
        game = Game(seed=5, gear=FULL)
        game.player.capacity = 1e9
        for symbol in ("DOGE", "SOL", "BTC", "USDC"):
            game.player.holding(symbol).qty = 1.0
        self.assertAlmostEqual(game.luck, G.MAX_LEVEL * G.LUCK_PER_LEVEL)

    def test_a_mixed_bag_gives_the_better_piece(self):
        game = Game(seed=5, gear={"meme": 1, "major": 3})
        game.player.holding("DOGE").qty = 1.0
        game.player.holding("BTC").qty = 1.0
        self.assertAlmostEqual(game.luck, 3 * G.LUCK_PER_LEVEL)

    def test_luck_can_never_exceed_the_advertised_ceiling(self):
        game = Game(seed=5, gear={key: 99 for key in G.CLASSES})
        for c in COINS:
            game.player.holding(c.symbol).qty = 1.0
        self.assertAlmostEqual(game.luck, G.MAX_LEVEL * G.LUCK_PER_LEVEL)


class TestEarningIt(unittest.TestCase):
    def test_a_win_credits_what_you_were_holding(self):
        profile = P.Profile()
        G.credit_win(profile, finished(60_000.0, ("DOGE",)))
        self.assertEqual(profile.gear_wins, {"meme": 1})

    def test_it_credits_the_class_you_held_the_most_value_in(self):
        profile = P.Profile()
        game = finished(60_000.0, ("DOGE",))
        btc = game.player.holding("BTC")
        btc.qty, btc.cost = 5_000.0 / game.market.price("BTC"), 5_000.0
        G.credit_win(profile, game)
        self.assertEqual(profile.gear_wins, {"major": 1})

    def test_finishing_in_cash_earns_nothing(self):
        profile = P.Profile()
        self.assertIsNone(G.credit_win(profile, finished(60_000.0)))
        self.assertEqual(profile.gear_wins, {})

    def test_losing_earns_nothing(self):
        profile = P.Profile()
        self.assertIsNone(G.credit_win(profile, finished(-4_000.0, ("DOGE",))))
        self.assertEqual(profile.gear_wins, {})

    def test_a_run_the_board_will_not_rank_earns_nothing(self):
        """Whatever hands a run free money must not hand it gear either."""
        profile = P.Profile()
        self.assertIsNone(G.credit_win(profile, finished(600_000.0, ("DOGE",), streak=True)))
        self.assertEqual(profile.gear_wins, {})

    def test_the_level_up_is_reported_only_when_it_happens(self):
        profile = P.Profile()
        piece, before, after = G.credit_win(profile, finished(60_000.0, ("DOGE",)))
        self.assertEqual((piece.key, before, after), ("meme", 0, 1))
        _, before, after = G.credit_win(profile, finished(60_000.0, ("DOGE",)))
        self.assertEqual((before, after), (1, 1), "a win that only moves the counter")

    def test_levels_follow_from_wins(self):
        profile = P.Profile(gear_wins={"meme": G.WINS_FOR_LEVEL[-1]})
        self.assertEqual(profile.gear_levels, {"meme": G.MAX_LEVEL})


class TestItActuallyChangesTheGame(unittest.TestCase):
    """Bounded is not the same as absent - measure that it does something."""

    def shocks_on(self, gear, symbol="DOGE", runs=220):
        pumps = crashes = 0
        for seed in range(runs):
            game = Game(seed=seed, gear=gear)
            game.player.capacity = 1e9
            game.player.holding(symbol).qty = 1.0      # held the whole way
            for i in range(12):
                game.player.cash += 400
                here = [s.name for s in STATIONS].index(game.station.name)
                try:
                    game.travel(STATIONS[(here + 3) % len(STATIONS)].name)
                    _answer_any(game)
                except ValueError:
                    break
                shock = game.market.shock
                if shock and shock.symbol == symbol:
                    crashes += shock.is_crash
                    pumps += not shock.is_crash
        return pumps, crashes

    def test_gear_tilts_a_shock_toward_a_pump_on_what_you_hold(self):
        bare_p, bare_c = self.shocks_on({})
        geared_p, geared_c = self.shocks_on({"meme": G.MAX_LEVEL})
        self.assertGreater(bare_p + bare_c, 40, "not enough shocks to conclude anything")
        self.assertGreater(geared_p / (geared_p + geared_c),
                           bare_p / (bare_p + bare_c) + 0.05)

    def test_it_does_not_tilt_a_coin_you_have_no_gear_for(self):
        """Asserted on the coin flip itself, not by comparing two whole runs.

        The first version of this compared shock outcomes across a geared run
        and a bare one and demanded they match to a tenth of a percent. That is
        not a property the game has: taking the pump branch instead of the
        crash branch draws from a different-length list, which shifts every
        random number after it. The test passed on eight coins by luck of the
        sample and failed the moment the roster grew - it was measuring stream
        divergence, not tilt. This rigs one shock and reads the threshold.
        """
        from cryptowarz.market import MarketState, generate
        from cryptowarz.stations import STATIONS

        class Rigged:
            """A shock, on a coin of our choosing, with a chosen crash draw."""

            def __init__(self, target, crash_draw):
                self.target, self.draws = target, iter([0.0, crash_draw])

            def random(self):
                return next(self.draws, 0.5)

            def choice(self, seq):
                return next((x for x in seq
                             if getattr(x, "symbol", None) == self.target), seq[0])

            def uniform(self, a, b):
                return (a + b) / 2.0

            def gauss(self, mu, sigma):
                return mu

        def crashed(luck, draw):
            state = MarketState(Rigged("BTC", 0.0))
            market = generate(STATIONS[0], Rigged("BTC", draw), state, luck=luck)
            return market.shock.is_crash

        # just under an even chance: a crash for anyone the luck map ignores
        self.assertTrue(crashed({"DOGE": 0.4}, 0.49), "an ungeared coin was tilted")
        self.assertTrue(crashed({}, 0.49))
        # and the same draw becomes a pump once the coin IS geared for
        self.assertFalse(crashed({"BTC": 0.4}, 0.49), "gear failed to tilt its own coin")


class TestCustomisingIt(unittest.TestCase):
    """Gear you can shape, not just accumulate."""

    def test_you_can_name_a_piece_you_have_earned(self):
        profile = P.Profile(gear_wins={"meme": 1})
        G.rename(profile, "meme", "Ratty")
        self.assertEqual(G.display_name(profile, G.GEAR_BY_KEY["meme"]), "Ratty")

    def test_an_empty_name_puts_the_original_back(self):
        profile = P.Profile(gear_wins={"meme": 1}, gear_names={"meme": "Ratty"})
        G.rename(profile, "meme", "   ")
        self.assertEqual(G.display_name(profile, G.GEAR_BY_KEY["meme"]),
                         G.GEAR_BY_KEY["meme"].name)

    def test_a_name_is_tidied_and_capped(self):
        profile = P.Profile(gear_wins={"meme": 1})
        G.rename(profile, "meme", "  a   very    long name that runs off the screen  ")
        shown = G.display_name(profile, G.GEAR_BY_KEY["meme"])
        self.assertLessEqual(len(shown), G.MAX_NAME)
        self.assertNotIn("  ", shown)

    def test_you_cannot_name_gear_you_have_not_earned(self):
        with self.assertRaises(ValueError):
            G.rename(P.Profile(), "meme", "Ratty")

    def test_moving_a_win_costs_more_than_it_gives(self):
        profile = P.Profile(gear_wins={"meme": 4})
        G.retune(profile, "meme", "major")
        self.assertEqual(profile.gear_wins, {"meme": 4 - G.RETUNE_COST, "major": 1})

    def test_moving_a_win_you_do_not_have_is_refused(self):
        profile = P.Profile(gear_wins={"meme": 1})
        with self.assertRaises(ValueError):
            G.retune(profile, "meme", "major")
        self.assertEqual(profile.gear_wins, {"meme": 1}, "a refused move must change nothing")

    def test_moving_a_win_to_where_it_already_is_is_refused(self):
        with self.assertRaises(ValueError):
            G.retune(P.Profile(gear_wins={"meme": 4}), "meme", "meme")

    def test_a_piece_you_move_away_from_entirely_loses_its_name(self):
        profile = P.Profile(gear_wins={"meme": 2}, gear_names={"meme": "Ratty"})
        G.retune(profile, "meme", "alt")
        self.assertEqual(profile.gear_wins, {"alt": 1})
        self.assertEqual(profile.gear_names, {}, "an unearned piece kept a custom name")

    def test_names_survive_a_save(self):
        profile = P.Profile(gear_wins={"meme": 1}, gear_names={"meme": "Ratty"})
        self.assertEqual(P.Profile.from_dict(profile.to_dict()).gear_names, {"meme": "Ratty"})


class TestItSurvivesAReload(unittest.TestCase):
    def test_a_saved_run_keeps_its_gear(self):
        game = Game(seed=5, gear={"meme": 2})
        game.buy("DOGE", game.max_buyable("DOGE") * 0.5)
        back = S.from_dict(S.to_dict(game))
        self.assertEqual(back.gear, {"meme": 2})
        self.assertAlmostEqual(back.luck, game.luck)

    def test_the_profile_keeps_its_wins(self):
        profile = P.Profile(gear_wins={"meme": 4, "stable": 1})
        back = P.Profile.from_dict(profile.to_dict())
        self.assertEqual(back.gear_wins, {"meme": 4, "stable": 1})

    def test_a_profile_from_before_gear_keeps_its_unlocks(self):
        legacy = {"version": 2, "runs": 9, "achievements": ["first_run", "whale"],
                  "best_net": 120_000.0, "best_tier_cleared": 2, "daily_day": None,
                  "daily_runs": [], "best_daily": 0.0, "updated_at": 1.0}
        profile = P.Profile.from_dict(legacy)
        self.assertEqual(profile.achievements, ["first_run", "whale"])
        self.assertEqual(profile.gear_wins, {})
        self.assertEqual(profile.gear_levels, {})

    def test_junk_in_the_gear_field_is_dropped_rather_than_trusted(self):
        profile = P.Profile.from_dict({"version": 3, "gear_wins": {"meme": 2, "wizard": 99}})
        self.assertEqual(profile.gear_wins, {"meme": 2})


if __name__ == "__main__":
    unittest.main()
