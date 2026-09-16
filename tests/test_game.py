"""Rules, arithmetic and the things a player would exploit."""

import random
import unittest

from cryptowarz.coins import BY_SYMBOL, COINS, coin
from cryptowarz.game import DAYS, SHARK_RATE, START_CASH, SUBWAY_FARE, Game, GameOver
from cryptowarz.market import generate
from cryptowarz.stations import STATIONS, station


class TestCoins(unittest.TestCase):
    def test_every_coin_has_a_real_spread(self):
        for c in COINS:
            self.assertGreater(c.high, c.low, c.symbol)
            self.assertGreater(c.low, 0, c.symbol)

    def test_usdc_is_the_boring_one(self):
        """It exists to be a safe harbour, so its spread must stay tiny."""
        self.assertLess(coin("USDC").spread, 1.2)
        for c in COINS:
            if c.symbol != "USDC":
                self.assertGreater(c.spread, 3.0, c.symbol)

    def test_lookup_is_case_insensitive_and_explains_itself(self):
        self.assertIs(coin("btc"), BY_SYMBOL["BTC"])
        with self.assertRaises(KeyError):
            coin("DOGECOIN")


class TestStations(unittest.TestCase):
    def test_every_service_exists_somewhere(self):
        self.assertTrue(any(s.has_shark for s in STATIONS))
        self.assertTrue(any(s.has_vault for s in STATIONS))
        self.assertTrue(any(s.has_upgrades for s in STATIONS))

    def test_heat_is_a_probability(self):
        for s in STATIONS:
            self.assertGreaterEqual(s.heat, 0.0)
            self.assertLessEqual(s.heat, 1.0)

    def test_biases_reference_real_coins(self):
        symbols = {c.symbol for c in COINS}
        for s in STATIONS:
            for sym in s.bias:
                self.assertIn(sym, symbols, f"{s.name} biases unknown {sym}")

    def test_station_disagreement_is_worth_a_trip_but_not_a_printer(self):
        """The arbitrage band is the core balance knob.

        Too narrow and travelling is pointless. Too wide and "buy whatever is
        cheapest" wins every run without judgement - which is exactly what the
        first version of the price model did, at roughly 10x.
        """
        from cryptowarz.market import MarketState
        for symbol in ("DOGE", "SOL", "BTC"):
            medians = {}
            for s in STATIONS:
                state = MarketState(random.Random(0))
                prices = [generate(s, random.Random(i), state, shock_chance=0.0).price(symbol)
                          for i in range(150)]
                medians[s.name] = sorted(prices)[75]
            spread = max(medians.values()) / min(medians.values())
            self.assertGreater(spread, 1.25, f"{symbol}: nothing to arbitrage")
            self.assertLess(spread, 3.0, f"{symbol}: too easy")


class TestMarket(unittest.TestCase):
    def test_unshocked_prices_stay_near_the_coin_range(self):
        for s in STATIONS:
            for i in range(80):
                m = generate(s, random.Random(i), shock_chance=0.0)
                for c in COINS:
                    p = m.price(c.symbol)
                    self.assertGreater(p, 0, c.symbol)
                    self.assertLess(p, c.high * 2.0, f"{c.symbol} at {s.name}")
                    self.assertGreater(p, c.low * 0.3, f"{c.symbol} at {s.name}")

    def test_shocks_deliberately_break_the_range(self):
        """A pump that stayed inside the normal range would not be a pump.

        This is the game's biggest single swing, so it is asserted rather than
        left to chance - but it still must not run away to infinity.
        """
        extremes = []
        for s in STATIONS:
            for i in range(200):
                m = generate(s, random.Random(i))
                if m.shock and not m.shock.is_crash:
                    c = BY_SYMBOL[m.shock.symbol]
                    extremes.append(m.price(c.symbol) / c.high)
        self.assertTrue(extremes, "no pumps generated at all")
        self.assertGreater(max(extremes), 2.0)     # genuinely dramatic
        self.assertLess(max(extremes), 12.0)       # not unbounded

    def test_same_seed_same_market(self):
        a = generate(station("Wall Street"), random.Random(5)).prices
        b = generate(station("Wall Street"), random.Random(5)).prices
        self.assertEqual(a, b)

    def test_usdc_is_never_shocked(self):
        """Shocking the safe harbour would defeat the point of having one."""
        for i in range(600):
            m = generate(station("14 St-Union Sq"), random.Random(i))
            if m.shock:
                self.assertNotEqual(m.shock.symbol, "USDC")

    def test_shocks_happen_but_are_not_the_norm(self):
        hits = sum(1 for i in range(600)
                   if generate(station("14 St-Union Sq"), random.Random(i)).shock)
        self.assertGreater(hits, 60)
        self.assertLess(hits, 300)


class TestTrading(unittest.TestCase):
    def setUp(self):
        self.game = Game(seed=1)

    def test_buy_moves_cash_into_the_wallet(self):
        cash = self.game.player.cash
        self.game.buy("DOGE", 100)
        h = self.game.player.holding("DOGE")
        self.assertAlmostEqual(h.qty, 100)
        self.assertAlmostEqual(self.game.player.cash + h.cost, cash)

    def test_cannot_buy_what_you_cannot_afford(self):
        with self.assertRaises(ValueError):
            self.game.buy("BTC", 10)

    def test_cannot_exceed_wallet_capacity(self):
        self.game.player.cash = 10_000_000.0
        with self.assertRaises(ValueError):
            self.game.buy("DOGE", 10_000_000)

    def test_max_buyable_leaves_the_fare(self):
        """Spending the last cent would strand you, which is a dead end."""
        qty = self.game.max_buyable("DOGE")
        self.game.buy("DOGE", qty)
        self.assertGreaterEqual(self.game.player.cash, SUBWAY_FARE - 1e-9)

    def test_selling_releases_capacity_proportionally(self):
        self.game.buy("DOGE", 1000)
        used = self.game.player.used_capacity
        self.game.sell("DOGE", 500)
        self.assertAlmostEqual(self.game.player.used_capacity, used / 2, places=6)

    def test_round_trip_at_the_same_price_is_flat(self):
        self.game.buy("DOGE", 100)
        cash = self.game.player.cash
        self.game.sell("DOGE", 100)
        expected = cash + 100 * self.game.market.price("DOGE")
        self.assertAlmostEqual(self.game.player.cash, expected, places=6)

    def test_cannot_sell_what_you_do_not_hold(self):
        with self.assertRaises(ValueError):
            self.game.sell("BTC", 1)

    def test_unknown_coin_is_rejected(self):
        with self.assertRaises(ValueError):
            self.game.buy("LUNA", 1)

    def test_selling_everything_clears_the_position(self):
        self.game.buy("DOGE", 100)
        self.game.sell("DOGE", 100)
        h = self.game.player.holding("DOGE")
        self.assertEqual(h.qty, 0.0)
        self.assertEqual(h.cost, 0.0)


class TestMoney(unittest.TestCase):
    def shark_station(self):
        g = Game(seed=2)
        g.station = next(s for s in STATIONS if s.has_shark)
        return g

    def test_debt_compounds_on_travel(self):
        """Isolated from events - a 'delay' legitimately costs a second day."""
        import cryptowarz.game as game_module
        g = Game(seed=3)
        debt = g.player.debt
        original = game_module.__dict__.get("roll_event")
        import cryptowarz.events as events
        saved = events.roll_event
        events.roll_event = lambda _g: []
        try:
            g.travel("Wall Street")
        finally:
            events.roll_event = saved
        self.assertAlmostEqual(g.player.debt, debt * (1 + SHARK_RATE))

    def test_a_delay_costs_a_second_day_of_interest(self):
        import cryptowarz.events as events
        g = Game(seed=3)
        debt = g.player.debt
        events.delay(g)
        self.assertAlmostEqual(g.player.debt, debt * 1.10)

    def test_debt_is_brutal_over_thirty_days(self):
        """The loan that starts you is usually the thing that eats the win."""
        self.assertGreater(5_500 * (1 + SHARK_RATE) ** 29, 85_000)

    def test_borrow_only_where_the_shark_works(self):
        g = Game(seed=2)
        g.station = next(s for s in STATIONS if not s.has_shark)
        with self.assertRaises(ValueError):
            g.borrow(100)

    def test_borrowing_is_capped(self):
        g = self.shark_station()
        with self.assertRaises(ValueError):
            g.borrow(10_000_000)

    def test_repay_cannot_exceed_debt_or_cash(self):
        g = self.shark_station()
        g.player.cash = 1_000_000.0
        g.repay(1_000_000.0)
        self.assertEqual(g.player.debt, 0.0)

    def test_vault_needs_a_vault(self):
        g = Game(seed=4)
        g.station = next(s for s in STATIONS if not s.has_vault)
        with self.assertRaises(ValueError):
            g.deposit(100)

    def test_vault_round_trip(self):
        g = Game(seed=4)
        g.station = next(s for s in STATIONS if s.has_vault)
        g.deposit(500)
        self.assertEqual(g.player.vault, 500)
        g.withdraw(500)
        self.assertEqual(g.player.vault, 0)


class TestTravel(unittest.TestCase):
    def test_travel_advances_the_day_and_changes_the_market(self):
        g = Game(seed=5)
        before = dict(g.market.prices)
        g.travel("Coney Island-Stillwell Av")
        self.assertEqual(g.day, 2)
        self.assertEqual(g.station.name, "Coney Island-Stillwell Av")
        self.assertNotEqual(before, g.market.prices)

    def test_cannot_travel_to_where_you_already_are(self):
        g = Game(seed=5)
        with self.assertRaises(ValueError):
            g.travel(g.station.name)

    def test_cannot_travel_without_the_fare(self):
        g = Game(seed=5)
        g.player.cash = 0.0
        with self.assertRaises(ValueError):
            g.travel("Wall Street")

    def test_game_ends_after_thirty_days(self):
        g = Game(seed=6)
        names = [s.name for s in STATIONS]
        while not g.finished:
            g.player.cash = max(g.player.cash, 100.0)
            g.travel(next(n for n in names if n != g.station.name))
        self.assertGreaterEqual(g.day, DAYS)
        self.assertTrue(g.finished)


class TestScoring(unittest.TestCase):
    def test_net_worth_counts_everything(self):
        g = Game(seed=7)
        g.buy("DOGE", 100)
        expected = (g.player.cash + g.player.vault
                    + 100 * g.market.price("DOGE") - g.player.debt)
        self.assertAlmostEqual(g.final_score(), expected, places=6)

    def test_verdict_is_honest_about_a_bad_run(self):
        g = Game(seed=8)
        g.player.cash = 10.0
        g.player.debt = 50_000.0
        self.assertIn("Shark", g.verdict())

    def test_verdict_rewards_a_good_run(self):
        g = Game(seed=8)
        g.player.cash = 900_000.0
        g.player.debt = 0.0
        self.assertIn("Legendary", g.verdict())


if __name__ == "__main__":
    unittest.main()
