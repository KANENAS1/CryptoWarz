"""What the game records, and whether a picture of it tells the truth.

The game has always moved the way it moves and never let anyone see it: one
number per coin is a trading screen with the chart switched off, and a whisper
that a coin is running is unusable if you cannot check whether it has been.

The tests that matter here are the ones about a chart LYING - a sparkline
scales its own window to full height, which is correct for a coin that moved
and a fabrication for one that did not.
"""

import random
import unittest

from cryptowarz import save as S
from cryptowarz import ui
from cryptowarz.coins import BY_SYMBOL, COINS
from cryptowarz.game import Game
from cryptowarz.market import HISTORY_KEPT, SPARK_DAYS, MarketState
from cryptowarz.stations import STATIONS


def ride(game, rides):
    for _ in range(rides):
        game.player.cash += 800.0
        here = [s.name for s in STATIONS].index(game.station.name)
        try:
            game.travel(STATIONS[(here + 3) % len(STATIONS)].name)
            _answer_any(game)
        except ValueError:
            break
    return game


def _answer_any(game):
    """These tests ride trains; a standoff blocks everything until answered."""
    from cryptowarz.encounter import best_choice

    if getattr(game, "pending", None):
        game.resolve(best_choice(game))


class TestTheGameRemembers(unittest.TestCase):
    def test_a_fresh_market_already_has_a_first_point(self):
        state = MarketState(random.Random(3))
        for coin in COINS:
            self.assertEqual(len(state.history[coin.symbol]), 1, coin.symbol)
            self.assertAlmostEqual(state.history[coin.symbol][0], state.levels[coin.symbol])

    def test_every_day_is_recorded(self):
        game = ride(Game(seed=5), 6)
        self.assertEqual(len(game.state.history["DOGE"]), game.day)

    def test_what_is_recorded_is_what_the_market_says(self):
        game = ride(Game(seed=5), 4)
        for coin in COINS:
            self.assertAlmostEqual(game.state.history[coin.symbol][-1],
                                   game.state.levels[coin.symbol], msg=coin.symbol)

    def test_history_is_capped_so_a_save_cannot_grow_forever(self):
        game = ride(Game(seed=5), 40)
        for coin in COINS:
            self.assertLessEqual(len(game.state.history[coin.symbol]), HISTORY_KEPT)
        self.assertGreaterEqual(HISTORY_KEPT, SPARK_DAYS,
                                "the chart draws more days than the game keeps")

    def test_the_chart_survives_a_reload(self):
        """Blanking every sparkline mid-run looks exactly like a bug."""
        game = ride(Game(seed=5), 7)
        back = S.from_dict(S.to_dict(game))
        self.assertEqual(back.state.history["DOGE"], game.state.history["DOGE"])

    def test_a_save_from_before_charts_still_loads(self):
        game = ride(Game(seed=5), 5)
        data = S.to_dict(game)
        del data["history"]
        back = S.from_dict(data)
        for coin in COINS:
            self.assertEqual(len(back.state.history[coin.symbol]), 1, coin.symbol)


class TestTheSparklineTellsTheTruth(unittest.TestCase):
    def test_a_coin_that_moved_is_drawn_moving(self):
        drawn = ui.spark([1.0, 2.0, 1.4, 3.1, 0.9, 2.2])
        self.assertGreater(len(set(drawn.strip())), 2, f"a moving coin drawn flat: {drawn!r}")

    def test_a_coin_that_barely_moved_is_drawn_FLAT(self):
        """USDC wanders 3% around a dollar and was drawn like a memecoin."""
        peg = [1.0, 1.004, 0.997, 1.002, 0.999, 1.001, 1.003]
        drawn = ui.spark(peg)
        self.assertEqual(set(drawn.strip()), {"▄"}, f"the peg was dramatised: {drawn!r}")

    def test_the_real_stablecoin_is_drawn_flat_in_a_real_run(self):
        game = ride(Game(seed=5), 12)
        self.assertEqual(set(ui.spark(game.state.history["USDC"]).strip()), {"▄"})

    def test_a_real_memecoin_is_not(self):
        game = ride(Game(seed=5), 12)
        self.assertGreater(len(set(ui.spark(game.state.history["WIF"]).strip())), 2)

    def test_it_draws_the_most_recent_days_not_the_first(self):
        values = [1.0] * 30 + [9.0]
        self.assertEqual(ui.spark(values).strip()[-1], "█")

    def test_nothing_to_draw_is_drawn_as_nothing(self):
        self.assertEqual(ui.spark([]).strip(), "")
        self.assertEqual(ui.spark([1.0]).strip(), "")

    def test_it_never_exceeds_its_column(self):
        for width in (8, 12, 20):
            self.assertEqual(len(ui.spark([1, 5, 2, 8, 3, 9, 1, 4, 7, 2], width)), width)

    def test_a_flat_line_at_zero_does_not_divide_by_it(self):
        self.assertEqual(ui.spark([0.0, 0.0, 0.0]).strip(), "")


class TestThePercentageAnswersTheRightQuestion(unittest.TestCase):
    """Held: what you paid against what this stop pays. Not held: the fortnight.

    These are different numbers, and the one a player wants when they are
    holding something is theirs, not the coin's. Showing the coin's fortnight
    beside a bag you bought yesterday answers a question nobody asked.
    """

    def held_game(self, symbol="DOGE"):
        """Buy, then read. No riding: an SEC raid taking the bag mid-test is a
        real outcome of the game and has nothing to do with the formula."""
        game = ride(Game(seed=5), 5)
        game.player.cash = 60_000.0
        game.player.capacity = 1e9
        game.buy(symbol, game.max_buyable(symbol) * 0.2)
        return game

    def pl_column(self, table):
        """The P/L field of every row, sliced by the header's own geometry."""
        lines = [ln for ln in table.splitlines() if ln.strip()]
        header = lines[0]
        end = header.index("YOUR P/L") + len("YOUR P/L")
        return [ln[end - 13:end].strip() for ln in lines[1:len(COINS) + 1]]

    def test_it_is_measured_from_what_you_paid(self):
        game = self.held_game()
        holding = game.player.wallet["DOGE"]
        expected = game.market.price("DOGE") / holding.avg_price - 1.0
        self.assertIn(ui.pct_str(expected), self.pl_column(ui.market_table(game)))

    def test_it_is_measured_against_what_this_stop_pays(self):
        """Not the abstract market level - the price you could sell at, here."""
        game = self.held_game()
        holding = game.player.wallet["DOGE"]
        against_price = game.market.price("DOGE") / holding.avg_price - 1.0
        against_level = game.state.levels["DOGE"] / holding.avg_price - 1.0
        column = self.pl_column(ui.market_table(game))
        self.assertIn(ui.pct_str(against_price), column)
        if abs(against_level - against_price) > 0.02:
            self.assertNotIn(ui.pct_str(against_level), column)

    def test_a_coin_you_do_not_hold_reports_no_profit(self):
        game = ride(Game(seed=5), 4)
        game.player.wallet.clear()
        self.assertEqual(set(self.pl_column(ui.market_table(game))), {"-"})

    def test_a_percentage_is_written_at_a_precision_that_means_something(self):
        self.assertEqual(ui.pct_str(0.044), "+4.4%")
        self.assertEqual(ui.pct_str(1.792), "+179%")
        self.assertEqual(ui.pct_str(-0.096), "-9.6%")
        self.assertEqual(ui.pct_str(-0.625), "-62%")

    def test_the_sign_is_in_the_text_not_only_the_colour(self):
        for value in (0.5, -0.5):
            self.assertIn("+" if value > 0 else "-", ui.pct_str(value))


class TestHoldingsReadSensibly(unittest.TestCase):
    def test_a_huge_holding_is_not_written_to_six_decimals(self):
        """Eighteen characters of false precision shunted the whole table."""
        self.assertEqual(ui.qty_str(13_800_040.180373), "13,800,040")
        self.assertLessEqual(len(ui.qty_str(999_999_999.123456)), 13)

    def test_a_small_holding_keeps_its_precision(self):
        self.assertEqual(ui.qty_str(0.000123), "0.000123")
        self.assertIn(".", ui.qty_str(2.5))

    def test_the_table_still_lines_up_with_a_huge_holding(self):
        game = ride(Game(seed=5), 6)
        game.player.capacity = 1e12
        game.player.cash = 500_000.0
        game.buy("SHIB", game.max_buyable("SHIB") * 0.9)
        lines = [ln for ln in ui.market_table(game).splitlines() if ln.strip()]
        widths = {len(ln) for ln in lines[:len(COINS) + 1]}
        self.assertEqual(len(widths), 1, f"the table is ragged: {sorted(widths)}")


if __name__ == "__main__":
    unittest.main()
