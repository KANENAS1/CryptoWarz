"""The grace period, the ramp behind it, and the meter that tells you.

Losing a third of your bags on day three is not a hard position - it is a coin
flip that decides the run before you have made a decision worth judging. The
SEC now stays away for the first fifteen days. The pressure is not deleted,
though: it is moved into the back half, where you actually have something worth
taking and the choice to sit on it or push on is the most interesting decision
in the game.

The meter that reports all this has one property worth more than the rest: it
reads the same weight table the roll uses. A forecast computed from a second,
parallel formula is a meter that can disagree with the game, and one a player
learns to distrust is worse than no meter at all.
"""

import unittest

from cryptowarz import events as E
from cryptowarz.game import Game
from cryptowarz.stations import STATIONS

HOT = max(STATIONS, key=lambda s: s.heat)
COLD = min(STATIONS, key=lambda s: s.heat)


def at(day, difficulty="normal", vpn=0, gear=None):
    game = Game(seed=3, difficulty=difficulty, gear=gear or {})
    game.day = day
    game.player.vpn = vpn
    return game


class TestTheGracePeriod(unittest.TestCase):
    def test_fifteen_days_is_fifteen_days(self):
        self.assertEqual(E.RAID_GRACE, 15)

    def test_no_raid_weight_at_all_before_it_ends(self):
        """Not 'less likely' - impossible. A 2% chance of losing the run on day
        four is still a coin flip you cannot plan around."""
        for day in range(1, E.RAID_GRACE + 1):
            game = at(day)
            weights = E.event_weights(game, HOT, day)
            index = [e[0] for e in E.EVENTS].index(E.sec_raid)
            self.assertEqual(weights[index], 0.0, f"day {day}")
            self.assertEqual(E.raid_chance(game, HOT, day), 0.0, f"day {day}")

    def test_and_it_really_cannot_happen(self):
        """The weights are the whole story - nothing else can summon a raid."""
        game = at(9)
        game.player.capacity = 1e9
        for symbol in ("BTC", "DOGE"):
            held = game.player.holding(symbol)
            held.qty += 10.0
            held.cost += 1_000.0
        raids = 0
        for _ in range(4_000):
            game.day = 9
            game.pending = None
            E.roll_event(game)
            if game.pending and game.pending.get("kind") == "badge":
                raids += 1
                break
        game.pending = None
        self.assertEqual(raids, 0, "the SEC turned up during the grace period")

    def test_the_day_after_the_grace_it_is_back(self):
        self.assertGreater(E.raid_chance(at(E.RAID_GRACE + 1), HOT), 0.0)


class TestThePressureMoves(unittest.TestCase):
    def test_the_ramp_climbs_to_the_last_day(self):
        game = at(30)
        early = E.raid_pressure(game, E.RAID_GRACE + 1)
        late = E.raid_pressure(game, game.days)
        self.assertAlmostEqual(late, E.RAID_RAMP_TO, places=6)
        self.assertLess(early, late, "the back half must get worse, not stay flat")

    def test_a_short_tier_ramps_over_its_own_length(self):
        """Tiers 4 and 5 are 26 days; the ramp must still finish on the last
        one rather than stopping two thirds of the way up."""
        short = Game(seed=3, tier=4)
        self.assertAlmostEqual(E.raid_pressure(short, short.days), E.RAID_RAMP_TO, places=6)

    def test_the_grace_costs_the_game_less_than_it_looks(self):
        """Measured, not asserted by feel: the ramp gives back most of what the
        grace hands out. See the README for the solvency numbers."""
        game = at(30)
        after = [E.raid_pressure(game, d) for d in range(E.RAID_GRACE + 1, game.days + 1)]
        # the average weight over the days raids CAN happen is above 1.0
        self.assertGreater(sum(after) / len(after), 1.3)


class TestTheMeterCannotLie(unittest.TestCase):
    def test_the_chance_is_read_off_the_roll_weights(self):
        game = at(22)
        weights = E.event_weights(game, HOT, 22)
        index = [e[0] for e in E.EVENTS].index(E.sec_raid)
        self.assertAlmostEqual(E.raid_chance(game, HOT, 22),
                               weights[index] / sum(weights), places=12)

    def test_it_measures_what_actually_happens(self):
        """Roll it four thousand times and the meter must have been right.

        A raid now opens a standoff rather than resolving itself, so what is
        counted is the agents turning up - which is exactly what the meter
        claims to predict. The pending one is cleared each time so the next
        roll is not refused.
        """
        game = at(24)
        game.player.capacity = 1e9
        predicted = E.raid_chance(game, game.station, 24)
        hits = 0
        for _ in range(4_000):
            game.day = 24
            game.pending = None
            E.roll_event(game)
            if game.pending and game.pending.get("kind") == "badge":
                hits += 1
        game.pending = None
        self.assertAlmostEqual(hits / 4_000, predicted, delta=0.02,
                               msg="the meter and the game disagree")

    def test_a_hotter_stop_reads_hotter(self):
        game = at(22)
        self.assertGreater(E.raid_chance(game, HOT, 22), E.raid_chance(game, COLD, 22))

    def test_a_vpn_visibly_buys_a_lower_reading(self):
        bare, safe = at(22), at(22, vpn=3)
        self.assertLess(E.raid_chance(safe, HOT, 22), E.raid_chance(bare, HOT, 22))

    def test_gear_you_are_holding_for_lowers_it_too(self):
        bare, geared = at(22), at(22, gear={"major": 3})
        for game in (bare, geared):
            game.player.capacity = 1e9
            held = game.player.holding("BTC")
            held.qty += 1.0
            held.cost += 1_000.0
        self.assertLess(E.raid_chance(geared, HOT, 22), E.raid_chance(bare, HOT, 22))


class TestTheBars(unittest.TestCase):
    def test_nothing_reads_quiet_once_a_raid_is_possible(self):
        self.assertEqual(E.threat_level(0.0), ("QUIET", 0))
        self.assertEqual(E.threat_level(0.0001)[0], "LOW")

    def test_the_labels_climb_with_the_number(self):
        bars = [E.threat_level(c)[1] for c in (0.0, 0.02, 0.09, 0.14, 0.30)]
        self.assertEqual(bars, [0, 1, 2, 3, 4])
        self.assertTrue(all(b <= E.THREAT_BARS for b in bars))

    def test_the_map_is_worth_reading_rather_than_all_one_colour(self):
        """A meter where every stop says the same thing is decoration."""
        for day in (16, 22, 30):
            game = at(day)
            labels = {E.threat_level(E.raid_chance(game, s, day))[0] for s in STATIONS}
            self.assertGreaterEqual(len(labels), 2, f"day {day} reads flat")

    def test_and_the_whole_map_gets_worse_as_the_run_goes_on(self):
        game = at(30)
        readings = [sum(E.raid_chance(game, s, day) for s in STATIONS)
                    for day in (16, 22, 30)]
        self.assertEqual(readings, sorted(readings))


class TestTheNewsPost(unittest.TestCase):
    def test_it_says_how_long_the_quiet_lasts(self):
        w = E.wire(at(8), day=8)
        self.assertEqual(w["label"], "QUIET")
        self.assertEqual(w["grace_left"], E.RAID_GRACE - 8)

    def test_two_stops_is_worse_than_one(self):
        w = E.wire(at(24), day=24)
        self.assertGreater(w["two_stops"], w["chance"])
        self.assertAlmostEqual(w["two_stops"], 1 - (1 - w["chance"]) ** 2, places=12)

    def test_the_headline_names_the_station_it_is_about(self):
        game = at(24)
        seen = {E.wire(game, s, 24)["text"] for s in STATIONS}
        self.assertGreater(len(seen), 3, "every stop got the same headline")

    def test_it_does_not_re_roll_on_every_redraw(self):
        """A headline that changes each time you look at it reads as noise -
        and drawing for it here would move the run's random stream."""
        game = at(24)
        before = game.rng.getstate()
        first = E.wire(game, day=24)["text"]
        for _ in range(5):
            self.assertEqual(E.wire(game, day=24)["text"], first)
        self.assertEqual(game.rng.getstate(), before, "the wire drew from the run's RNG")

    def test_every_level_has_something_to_say(self):
        for label in ("QUIET", "LOW", "WATCH", "HIGH", "SEVERE"):
            self.assertGreaterEqual(len(E.WIRE_LINES[label]), 3, label)


if __name__ == "__main__":
    unittest.main()


class TestAStopRemembersYourFace(unittest.TestCase):
    """Working one lucrative station over and over used to cost nothing.

    It should: the fourth time you get off at the same platform carrying a bag,
    somebody has noticed. This is the counterweight to a map you were otherwise
    free to farm, and it partners the wheel's one-spin-per-stop rule - both pay
    you for going somewhere new.

    The part that matters most is the SEPARATION. A VPN answers "how dangerous
    is this stop right now"; the visit level answers "how well do they know me
    here". They are different questions, a VPN moves the first and never the
    second, and the map shows both.
    """

    def test_the_first_visit_costs_nothing(self):
        game = at(22)
        self.assertAlmostEqual(E.visit_pressure(game, game.station), 1.0)

    def test_coming_back_makes_a_stop_hotter(self):
        game = at(22)
        chances = []
        for been in range(1, 9):
            game.stats["visits"][game.station.name] = been
            chances.append(E.raid_chance(game, game.station))
        self.assertEqual(chances, sorted(chances), "returning must never be safer")
        self.assertGreater(chances[-1], chances[0] * 1.3)

    def test_it_is_capped_so_a_stop_never_becomes_certain_death(self):
        game = at(22)
        game.stats["visits"][game.station.name] = 500
        self.assertAlmostEqual(E.visit_pressure(game, game.station), 1.0 + E.VISIT_MAX)

    def test_a_vpn_cools_the_threat_and_not_the_memory(self):
        bare, safe = at(22), at(22, vpn=3)
        for game in (bare, safe):
            game.stats["visits"][game.station.name] = 8
        self.assertLess(E.raid_chance(safe, safe.station), E.raid_chance(bare, bare.station))
        self.assertEqual(E.visit_label(safe), E.visit_label(bare), "a VPN erased the memory")
        self.assertEqual(E.visit_label(safe), "BURNED")

    def test_the_levels_climb_with_the_visits(self):
        game = at(22)
        seen = []
        for been in range(0, 10):
            game.stats["visits"][game.station.name] = been
            seen.append(E.visit_label(game))
        self.assertEqual(seen[0], "NEW")
        self.assertEqual(seen[-1], "BURNED")
        levels = [E.visit_level(game) for been in range(0, 10)
                  if not game.stats["visits"].__setitem__(game.station.name, been)]
        self.assertEqual(levels, sorted(levels), "a level must never go backwards")

    def test_travelling_records_the_visit(self):
        from cryptowarz.stations import STATIONS
        game = at(5)
        here = game.station.name
        target = next(s for s in STATIONS if s.name != here)
        from cryptowarz.encounter import best_choice

        def ride(to):
            game.player.cash = 500.0
            game.travel(to)
            if game.pending:                 # a standoff blocks everything
                game.resolve(best_choice(game))

        ride(target.name)
        self.assertEqual(E.visits(game, target), 1)
        ride(here)
        ride(target.name)
        self.assertEqual(E.visits(game, target), 2)

    def test_the_stop_you_start_at_counts_as_visited(self):
        game = at(1)
        self.assertEqual(E.visits(game, game.station), 1)

    def test_it_rides_the_save(self):
        from cryptowarz import save as S
        from cryptowarz.game import Game
        game = Game(seed=5)
        game.stats["visits"][game.station.name] = 6
        back = S.from_dict(S.to_dict(game))
        self.assertEqual(E.visits(back, back.station), 6)
