"""Persistence, and the one property that makes saving honest.

A game of raids and rug pulls invites savescumming: quit before a bad outcome,
reload, take the ride again and hope for different dice. If reloading rerolled,
the risk would be optional - and a game where the risk is optional has no
decisions in it. So the generator state is saved, and these tests pin that down
rather than merely checking the numbers came back.
"""

import json
import os
import random
import tempfile
import unittest
from pathlib import Path

from cryptowarz import save as S
from cryptowarz.game import SUBWAY_FARE, Game
from cryptowarz.stations import STATIONS


class SaveTestCase(unittest.TestCase):
    """Every test gets its own CRYPTOWARZ_HOME; none touch the real one."""

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self._prev = os.environ.get("CRYPTOWARZ_HOME")
        os.environ["CRYPTOWARZ_HOME"] = self._dir.name

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("CRYPTOWARZ_HOME", None)
        else:
            os.environ["CRYPTOWARZ_HOME"] = self._prev
        self._dir.cleanup()

    def played(self, seed=21, hops=2):
        g = Game(seed=seed)
        qty = g.max_buyable("DOGE") * 0.3
        if qty > 0:
            g.buy("DOGE", qty)
        for _ in range(hops):
            try:
                g.travel(next(s.name for s in STATIONS if s.name != g.station.name))
            except ValueError:
                break
        return g


class TestRoundTrip(SaveTestCase):
    def test_everything_comes_back(self):
        g = self.played()
        S.write_save(g)
        r = S.read_save()
        self.assertEqual(r.day, g.day)
        self.assertEqual(r.station.name, g.station.name)
        self.assertAlmostEqual(r.player.cash, g.player.cash)
        self.assertAlmostEqual(r.player.debt, g.player.debt)
        self.assertAlmostEqual(r.player.vault, g.player.vault)
        self.assertAlmostEqual(r.player.cash_cap, g.player.cash_cap)
        self.assertEqual(r.player.vpn, g.player.vpn)

    def test_the_wallet_comes_back_exactly(self):
        g = self.played()
        S.write_save(g)
        r = S.read_save()
        self.assertEqual(sorted(r.player.wallet), sorted(g.player.wallet))
        for sym, h in g.player.wallet.items():
            self.assertAlmostEqual(r.player.wallet[sym].qty, h.qty, msg=sym)
            self.assertAlmostEqual(r.player.wallet[sym].cost, h.cost, msg=sym)

    def test_prices_are_stored_not_regenerated(self):
        """Regenerating would draw from the generator and desync everything after."""
        g = self.played()
        S.write_save(g)
        r = S.read_save()
        self.assertEqual(r.market.prices, g.market.prices)
        if g.market.shock:
            self.assertEqual(r.market.shock.symbol, g.market.shock.symbol)
            self.assertEqual(r.market.headline, g.market.headline)

    def test_market_levels_survive(self):
        g = self.played(hops=4)
        S.write_save(g)
        self.assertEqual(S.read_save().state.levels, g.state.levels)


class TestNoSavescumming(SaveTestCase):
    def test_a_reload_replays_the_same_dice(self):
        """The property the whole design exists for."""
        for seed in (3, 11, 21, 40):
            with self.subTest(seed=seed):
                g = self.played(seed=seed)
                S.write_save(g)
                r = S.read_save()
                target = next(s.name for s in STATIONS if s.name != g.station.name)
                try:
                    original = g.travel(target)
                except ValueError:
                    continue
                self.assertEqual(r.travel(target), original)

    def test_the_outcome_is_identical_many_days_later(self):
        g = self.played(seed=7)
        S.write_save(g)
        r = S.read_save()
        names = [s.name for s in STATIONS]
        for _ in range(8):
            target = next(n for n in names if n != g.station.name)
            try:
                a = g.travel(target)
            except ValueError:
                break
            self.assertEqual(r.travel(target), a)
        self.assertAlmostEqual(r.final_score(), g.final_score(), places=6)


class TestRefusesBadSaves(SaveTestCase):
    def test_a_future_version_is_refused_not_guessed_at(self):
        g = self.played()
        data = S.to_dict(g)
        data["save_version"] = S.SAVE_VERSION + 1
        S.save_path().parent.mkdir(parents=True, exist_ok=True)
        S.save_path().write_text(json.dumps(data))
        with self.assertRaises(S.SaveError):
            S.read_save()

    def test_corrupt_json_is_reported_clearly(self):
        S.save_path().parent.mkdir(parents=True, exist_ok=True)
        S.save_path().write_text("{not json at all")
        with self.assertRaises(S.SaveError):
            S.read_save()

    def test_a_save_missing_a_coin_is_refused(self):
        """A save from before a coin existed cannot be completed by guessing."""
        g = self.played()
        data = S.to_dict(g)
        del data["levels"]["SOL"]
        S.save_path().parent.mkdir(parents=True, exist_ok=True)
        S.save_path().write_text(json.dumps(data))
        with self.assertRaises(S.SaveError):
            S.read_save()

    def test_no_save_is_not_an_error(self):
        self.assertIsNone(S.read_save())
        self.assertFalse(S.has_save())

    def test_clearing_a_missing_save_is_harmless(self):
        S.clear_save()
        S.clear_save()


class TestScores(SaveTestCase):
    def finished(self, seed, cash):
        g = Game(seed=seed)
        g.player.cash = cash
        g.player.debt = 0.0
        g.finished = True
        return g

    def test_scores_persist_and_sort_best_first(self):
        for seed, cash in ((1, 5_000.0), (2, 90_000.0), (3, 400.0)):
            S.record_score(self.finished(seed, cash))
        scores = S.read_scores()
        self.assertEqual([round(s.net_worth) for s in scores], [90_000, 5_000, 400])
        self.assertEqual(round(S.best_score().net_worth), 90_000)

    def test_the_board_is_capped(self):
        for i in range(S.MAX_SCORES + 10):
            S.record_score(self.finished(i, float(i * 100)))
        self.assertEqual(len(S.read_scores()), S.MAX_SCORES)

    def test_a_corrupt_score_file_never_blocks_a_game(self):
        S.scores_path().parent.mkdir(parents=True, exist_ok=True)
        S.scores_path().write_text("garbage")
        self.assertEqual(S.read_scores(), [])
        S.record_score(self.finished(1, 1_000.0))
        self.assertEqual(len(S.read_scores()), 1)

    def test_one_bad_row_does_not_lose_the_good_ones(self):
        S.record_score(self.finished(1, 1_000.0))
        rows = json.loads(S.scores_path().read_text())
        rows.append({"net_worth": "not a number"})
        S.scores_path().write_text(json.dumps(rows))
        self.assertEqual(len(S.read_scores()), 1)


class TestEventsCannotStrandYou(SaveTestCase):
    def test_cash_draining_events_always_leave_the_fare(self):
        """Stripped to nothing with an empty wallet there is no legal move left."""
        from cryptowarz import events as E
        for seed in range(120):
            g = Game(seed=seed)
            g.player.cash = 45.0
            g.player.wallet = {}
            for fn in (E.gas_spike, E.sec_raid, E.shark_visit):
                g.rng = random.Random(seed)
                fn(g)
            self.assertGreaterEqual(g.player.cash, SUBWAY_FARE - 1e-9,
                                    f"stranded at seed {seed}")


if __name__ == "__main__":
    unittest.main()


class TestARideIsAllOrNothing(unittest.TestCase):
    """The bug behind "the days aren't changing, the prices aren't changing".

    ``travel`` used to set the station, then do two lines of stats bookkeeping,
    then increment the day. On the web port that bookkeeping could throw - the
    restore adopted the database's document by reference and the database hands
    documents back frozen, so ``stations.push`` raised "object is not
    extensible". The ride half happened: the station changed, the day did not,
    and the market never regenerated, because that is downstream of the day.

    New stop, same prices, same day, forever - and nothing in the save that
    looked wrong, because "station A, day 1" is a shape a save can express.
    """

    def test_a_ride_that_cannot_be_written_down_still_happens(self):
        from cryptowarz.game import Game
        from cryptowarz.stations import STATIONS

        game = Game(seed=5)
        target = next(s for s in STATIONS if s.name != game.station.name)

        class Sealed(set):
            """A container that refuses to grow, the way a frozen array does.

            This is exactly the shape of the real failure: ``Array.prototype.push``
            on a frozen array raises, and the ride was standing on that line.
            """

            def add(self, value):
                raise TypeError("object is not extensible")

        game.stats["stations"] = Sealed(game.stats["stations"])
        day = game.day
        prices = dict(game.market.prices)
        game.travel(target.name)

        self.assertEqual(game.station.name, target.name, "the ride happened")
        self.assertEqual(game.day, day + 1, "and so did the day")
        self.assertNotEqual(dict(game.market.prices), prices,
                            "and the market moved with it")

    def test_the_station_and_the_day_can_never_disagree(self):
        """Whatever goes wrong, you are never at a stop you did not spend a day
        reaching, and the stop you are at is one your own stats have heard of.
        That pair is what the whole run is counted in."""
        from cryptowarz.game import Game
        from cryptowarz.stations import STATIONS

        game = Game(seed=9)
        for i in range(12):
            target = STATIONS[(i * 3 + 1) % len(STATIONS)]
            if target.name == game.station.name:
                continue
            game.pending = None      # answered; the standoff is not what this measures
            before = game.day
            game.travel(target.name)
            # a day at least - an event may cost another one on top
            self.assertGreater(game.day, before)
            self.assertEqual(game.station.name, target.name)
            self.assertIn(target.name, game.stats["stations"],
                          "arrived somewhere the run has no record of")
            self.assertGreaterEqual(game.stats["visits"].get(target.name, 0), 1)
            if game.finished:
                break

    def test_a_loader_owns_its_stats_rather_than_borrowing_them(self):
        """The restore must not keep a live reference into the caller's data.

        Invisible for as long as every save came out of ``json.load``. Then the
        server copy arrived, frozen, and the run could not record a thing.
        """
        import json

        from cryptowarz import save as S
        from cryptowarz.game import Game
        from cryptowarz.stations import STATIONS

        game = Game(seed=3)
        game.travel(next(s.name for s in STATIONS if s.name != game.station.name))
        blob = json.loads(json.dumps(S.to_dict(game)))
        restored = S.from_dict(blob)
        restored.stats["visits"]["somewhere new"] = 99
        self.assertNotIn("somewhere new", blob["stats"].get("visits", {}),
                         "the loader is still writing through to the caller's document")

    def test_a_run_stranded_by_the_old_bug_loads_repaired(self):
        """A save from the broken build sits at a station its stats never saw."""
        import json

        from cryptowarz import save as S
        from cryptowarz.game import Game
        from cryptowarz.stations import STATIONS

        game = Game(seed=11)
        elsewhere = next(s for s in STATIONS if s.name != game.station.name)
        blob = json.loads(json.dumps(S.to_dict(game)))
        blob["station"] = elsewhere.name            # what the half-ride left
        restored = S.from_dict(blob)
        self.assertIn(elsewhere.name, restored.stats["stations"])
        self.assertEqual(restored.stats["visits"][elsewhere.name], 1)
        # and loading it twice must not make the stop look hotter than it is
        again = S.from_dict(json.loads(json.dumps(S.to_dict(restored))))
        self.assertEqual(again.stats["visits"][elsewhere.name], 1,
                         "a reload counted itself as another visit")
