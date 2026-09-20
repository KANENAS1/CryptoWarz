"""The web port must stay the same game as the Python one.

CryptoWarz now has two implementations of identical rules: the terminal version
in ``cryptowarz/`` and the phone version in ``web/game.js``. Two copies of a
rule set drift - a coin retuned on one side, a station bias edited on the
other - and the drift is silent, because each version works perfectly well on
its own while quietly being a different game.

So the data is compared exactly, and the behaviour is compared by shape. These
tests skip cleanly where node is unavailable, since the Python package itself
has no dependencies and must stay runnable anywhere.
"""

import json
import shutil
import subprocess
import unittest
from pathlib import Path

from cryptowarz.coins import COINS
from cryptowarz.game import DAYS, START_CAPACITY, START_CASH, START_DEBT, SUBWAY_FARE
from cryptowarz.market import station_markup
from cryptowarz.stations import STATIONS

WEB = Path(__file__).resolve().parent.parent / "web"
NODE = shutil.which("node")
requires_node = unittest.skipUnless(NODE, "node is not installed; the web port cannot be checked")


def run_node(script, *args):
    out = subprocess.run([NODE, str(WEB / script), *args],
                         capture_output=True, text=True, timeout=300, check=True)
    return json.loads(out.stdout)


class TestWebSourcesExist(unittest.TestCase):
    def test_the_web_version_is_in_the_repo(self):
        for name in ("game.js", "index.html", "build.py", "balance.js", "dump.js"):
            self.assertTrue((WEB / name).exists(), f"web/{name} is missing")

    def test_the_standalone_page_loads_the_logic_it_does_not_inline_it(self):
        """index.html stays readable; only the published build is flattened."""
        html = (WEB / "index.html").read_text()
        self.assertIn('<script src="game.js"></script>', html)
        self.assertIn("viewport-fit=cover", html)   # iPhone safe areas

    def test_a_fresh_open_starts_a_ranked_run_not_practice(self):
        """The bug this guards is the one that shipped.

        Opening the page started a practice run, so a player who simply pressed
        play went thirty days and posted nothing - the score was "not saving"
        because it had never been a ranked run. A slot is spent by finishing,
        not by starting, so booting into one costs a wanderer nothing.
        """
        html = (WEB / "index.html").read_text()
        boot = html[html.index("function boot()"):html.index('$("newgame")')]
        self.assertIn("nextSlot(profile)", boot)
        self.assertIn("dailySeeds()", boot)

    def test_a_board_write_reports_back_instead_of_vanishing(self):
        """A score that fails to save silently is worse than one that never did."""
        html = (WEB / "index.html").read_text()
        self.assertIn('id="fsave"', html)
        self.assertIn('return "saved"', html)
        self.assertIn("boardDirty", html)          # a failed post is retried

    def test_the_page_never_writes_the_die_size_down(self):
        """The die went from ten sides to six and the panel still said ten.

        Any literal count in the markup is a second source of truth that nobody
        remembers to change. The page must read DICE_SIDES instead.
        """
        html = (WEB / "index.html").read_text()
        self.assertNotIn("1 to 10", html)
        self.assertIn("1 to ${DICE_SIDES}", html)
        self.assertIn("repeat(var(--faces", html, "the face grid is hardcoded")

    def test_the_wheel_can_actually_turn(self):
        """Guarding a bug that shipped, from a cause that has now bitten twice.

        Tidying up once cut a range of CSS by its start and end selectors, and
        the wheel's rules happened to sit inside that range. Nothing threw, no
        test failed, and the wheel silently stopped being able to move: it kept
        paying out and just snapped to its answer. Structural, because a unit
        test cannot see a stylesheet.
        """
        html = (WEB / "index.html").read_text()
        for rule in (".wheelbox{", ".wheelstage{", "#wheelart{", ".needle{"):
            self.assertIn(rule, html, f"the wheel lost its {rule} rule")
        art = html[html.index("#wheelart{"):html.index("}", html.index("#wheelart{"))]
        self.assertIn("transition:transform", art, "the wheel cannot animate")

    def test_the_wheel_result_outlives_the_spin(self):
        """The spin makes wheelReady false, which used to hide the answer."""
        html = (WEB / "index.html").read_text()
        i = html.index("function renderWheel()")
        body = html[i:html.index("\n}", i)]
        self.assertIn("wheelResult", body,
                      "renderWheel hides the box without checking for a result")

    def test_the_artifact_build_inlines_everything(self):
        import sys
        sys.path.insert(0, str(WEB))
        from build import build                     # noqa: E402
        page = build()
        self.assertNotIn("<script src=", page)      # the CSP blocks relative loads
        self.assertIn("function Game", page)
        self.assertIn("<title>CryptoWarz</title>", page)


@requires_node
class TestDataParity(unittest.TestCase):
    """Exact comparison - these are the same numbers or they are not."""

    @classmethod
    def setUpClass(cls):
        cls.js = run_node("dump.js")

    def test_constants_match(self):
        c = self.js["constants"]
        self.assertEqual(c["DAYS"], DAYS)
        self.assertAlmostEqual(c["SUBWAY_FARE"], SUBWAY_FARE)
        self.assertAlmostEqual(c["START_CASH"], START_CASH)
        self.assertAlmostEqual(c["START_DEBT"], START_DEBT)
        self.assertAlmostEqual(c["START_CAPACITY"], START_CAPACITY)

    def test_every_coin_matches(self):
        self.assertEqual([c["symbol"] for c in self.js["coins"]], [c.symbol for c in COINS])
        for js, py in zip(self.js["coins"], COINS):
            self.assertEqual(js["name"], py.name, py.symbol)
            self.assertAlmostEqual(js["low"], py.low, msg=py.symbol)
            self.assertAlmostEqual(js["high"], py.high, msg=py.symbol)
            self.assertEqual(js["meme"], py.meme, py.symbol)
            self.assertAlmostEqual(js["vol"], py.vol, msg=py.symbol)
            self.assertAlmostEqual(js["pull"], py.pull, msg=py.symbol)
            self.assertEqual(js["note"], py.note, py.symbol)

    def test_every_station_matches(self):
        self.assertEqual([s["name"] for s in self.js["stations"]], [s.name for s in STATIONS])
        for js, py in zip(self.js["stations"], STATIONS):
            # the port carries the route bullets as a list and Python as a
            # string; regenerating the table once flattened the list and only a
            # browser noticed, because nothing here was comparing them
            self.assertEqual(js["lines"], py.lines.split(), py.name)
            self.assertEqual(js["borough"], py.borough, py.name)
            self.assertAlmostEqual(js["heat"], py.heat, msg=py.name)
            for symbol, value in js["markup"].items():
                self.assertAlmostEqual(value, station_markup(py, symbol),
                                       msg=f"{py.name}/{symbol}")
            self.assertEqual(js["shark"], py.has_shark, py.name)
            self.assertEqual(js["vault"], py.has_vault, py.name)
            self.assertEqual(js["shop"], py.has_upgrades, py.name)
            self.assertEqual(js["wheel"], py.has_wheel, py.name)
            self.assertEqual(set(js["bias"]), set(py.bias), f"{py.name} biases differ")
            for symbol, value in py.bias.items():
                self.assertAlmostEqual(js["bias"][symbol], value, msg=f"{py.name}/{symbol}")


@requires_node
class TestSaveFormatParity(unittest.TestCase):
    """Both front ends must agree on what a save looks like.

    They store in different places - a JSON file versus localStorage - but the
    shape and the version are shared, so a save format change on one side is a
    visible break rather than a quiet divergence.
    """

    @classmethod
    def setUpClass(cls):
        cls.js = run_node("dump.js", "--save")

    def python_save(self):
        import tempfile
        from cryptowarz import save as S
        from cryptowarz.game import Game
        from cryptowarz.stations import STATIONS
        g = Game(seed=21)
        qty = g.max_buyable("DOGE") * 0.3
        if qty > 0:
            g.buy("DOGE", qty)
        try:
            g.travel(next(s.name for s in STATIONS if s.name != g.station.name))
        except ValueError:
            pass
        return S.to_dict(g)

    def test_the_save_version_matches(self):
        from cryptowarz.save import SAVE_VERSION
        self.assertEqual(self.js["save_version"], SAVE_VERSION)

    def test_the_top_level_shape_matches(self):
        py = self.python_save()
        self.assertEqual(sorted(self.js["save"]), sorted(py),
                         "the two save formats have drifted apart")

    def test_the_player_shape_matches(self):
        py = self.python_save()
        self.assertEqual(sorted(self.js["save"]["player"]), sorted(py["player"]))

    def test_both_record_prices_and_the_pending_shock(self):
        for save in (self.js["save"], self.python_save()):
            self.assertIn("prices", save["market"])
            self.assertIn("shock", save["market"])
            self.assertIn("levels", save)
            self.assertIn("rng", save)     # the anti-savescum guarantee


@requires_node
class TestProgressParity(unittest.TestCase):
    """The ladder, the grades and the ranked slate must be one rule set.

    This is the part a leaderboard cannot survive drifting on: if the phone
    version grades a run differently, or deals a different market for today's
    second ranked run, the two front ends are posting incomparable numbers to
    the same board.
    """

    @classmethod
    def setUpClass(cls):
        cls.js = run_node("dump.js")["progress"]

    def test_the_profile_format_version_matches(self):
        from cryptowarz.progress import PROGRESS_VERSION
        self.assertEqual(self.js["version"], PROGRESS_VERSION)

    def test_the_number_of_ranked_runs_a_day_matches(self):
        from cryptowarz.progress import RUNS_PER_DAY
        self.assertEqual(self.js["runs_per_day"], RUNS_PER_DAY)

    def test_the_grade_ladder_matches(self):
        from cryptowarz.progress import GRADES
        self.assertEqual(len(self.js["grades"]), len(GRADES))
        for js, (threshold, letter, blurb) in zip(self.js["grades"], GRADES):
            self.assertAlmostEqual(js["threshold"], threshold, msg=letter)
            self.assertEqual(js["letter"], letter)
            self.assertEqual(js["blurb"], blurb, letter)

    def test_every_tier_matches_including_its_score_weight(self):
        from cryptowarz.progress import TIERS
        self.assertEqual([t["level"] for t in self.js["tiers"]], [t.level for t in TIERS])
        for js, py in zip(self.js["tiers"], TIERS):
            self.assertEqual(js["name"], py.name, py.name)
            self.assertAlmostEqual(js["debt"], py.debt, msg=py.name)
            self.assertAlmostEqual(js["capacity"], py.capacity, msg=py.name)
            self.assertAlmostEqual(js["heat"], py.heat_mult, msg=py.name)
            self.assertEqual(js["days"], py.days, py.name)
        self.assertEqual(self.js["tier_mults"], [t.score_mult for t in TIERS])

    def test_todays_slate_is_the_same_three_markets_on_both_sides(self):
        from cryptowarz.progress import daily_seeds
        self.assertEqual(self.js["daily_seeds"], daily_seeds(1_700_000_000))

    def test_the_goals_and_their_unlocks_match(self):
        from cryptowarz.progress import ACHIEVEMENTS, PERKS
        self.assertEqual(self.js["achievements"], [a.key for a in ACHIEVEMENTS])
        self.assertEqual(self.js["perks"],
                         [{"key": p.key, "by": p.unlocked_by} for p in PERKS])


@requires_node
class TestGearParity(unittest.TestCase):
    """Gear changes the odds, so the two ports must agree on every number.

    The behavioural half is the important half: both sides must refuse to pay
    out on an empty wallet, must take the best piece rather than the sum, and
    must refuse to hand gear to a run the board will not rank.
    """

    @classmethod
    def setUpClass(cls):
        cls.js = run_node("dump.js")["gear"]

    def test_the_class_table_matches(self):
        from cryptowarz.gear import CLASSES
        self.assertEqual({k: tuple(v) for k, v in self.js["classes"].items()},
                         {k: tuple(v) for k, v in CLASSES.items()})

    def test_every_piece_matches(self):
        from cryptowarz.gear import GEAR
        self.assertEqual([p["key"] for p in self.js["pieces"]], [p.key for p in GEAR])
        for js, py in zip(self.js["pieces"], GEAR):
            self.assertEqual(js["name"], py.name, py.key)
            self.assertEqual(js["covers"], py.covers, py.key)
            self.assertEqual(js["blurb"], py.blurb, py.key)

    def test_the_numbers_match(self):
        from cryptowarz import gear as gr
        self.assertEqual(self.js["max_level"], gr.MAX_LEVEL)
        self.assertEqual(self.js["wins_for_level"], list(gr.WINS_FOR_LEVEL))
        self.assertAlmostEqual(self.js["luck_per_level"], gr.LUCK_PER_LEVEL)
        self.assertAlmostEqual(self.js["win_at"], gr.WIN_AT)
        self.assertEqual(self.js["levels"],
                         [gr.level_for(w) for w in (0, 1, 2, 3, 6, 7, 40)])

    def test_luck_follows_the_bag_on_both_sides(self):
        self.assertEqual(self.js["empty_wallet_is_zero"], 0)

    def test_luck_is_never_a_sum_on_either_side(self):
        from cryptowarz.gear import LUCK_PER_LEVEL, MAX_LEVEL
        self.assertTrue(self.js["four_pieces_equal_the_best"])
        self.assertAlmostEqual(self.js["mixed_bag_takes_the_better"],
                               MAX_LEVEL * LUCK_PER_LEVEL)

    def test_both_ports_earn_it_the_same_way(self):
        self.assertEqual(self.js["win_credits_what_you_held"], {"meme": 1})
        self.assertEqual(self.js["cash_finish_earns_nothing"], {})
        self.assertEqual(self.js["loss_earns_nothing"], {})
        self.assertEqual(self.js["unrankable_run_earns_nothing"], {})


@requires_node
class TestStrandedParity(unittest.TestCase):
    """A false dead end is worse than none.

    If one port says "stranded" where the other still has a Shark to borrow
    from, it is telling that player to abandon a run they could have saved.
    """

    @classmethod
    def setUpClass(cls):
        cls.js = run_node("dump.js")["stranded"]

    def test_both_ports_agree_on_when_you_are_stuck(self):
        self.assertFalse(self.js["fresh"])
        self.assertTrue(self.js["bare_stop"])

    def test_both_ports_agree_on_every_way_out(self):
        self.assertFalse(self.js["something_to_sell"], "a bag to sell is a way out")
        self.assertFalse(self.js["at_the_shark"], "the Shark is a way out")
        self.assertFalse(self.js["vault_at_a_vault"], "your own vault is a way out")
        self.assertFalse(self.js["free_ride"], "a free fare is never stranded")

    def test_both_ports_agree_on_what_is_not_a_way_out(self):
        self.assertTrue(self.js["maxed_out_shark"], "he won't lend and there is nothing else")
        self.assertTrue(self.js["vault_elsewhere"], "you cannot reach the vault from here")

    def test_giving_up_works_the_same_way(self):
        self.assertTrue(self.js["give_up_finishes"])
        self.assertTrue(self.js["give_up_says_so"])
        self.assertTrue(self.js["give_up_twice_is_harmless"])


@requires_node
class TestGearCustomisationParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = run_node("dump.js")["custom"]

    def test_the_cost_of_moving_a_win_matches(self):
        from cryptowarz import gear as gr
        self.assertEqual(self.js["retune_cost"], gr.RETUNE_COST)
        self.assertEqual(self.js["max_name"], gr.MAX_NAME)

    def test_both_sides_tidy_a_name_the_same_way(self):
        from cryptowarz import gear as gr
        from cryptowarz.progress import Profile
        profile = Profile(gear_wins={"meme": 4})
        gr.rename(profile, "meme", "  Lucky   Rat  ")
        self.assertEqual(self.js["cleaned"], gr.display_name(profile, gr.GEAR_BY_KEY["meme"]))

    def test_both_sides_charge_the_same_to_move_a_win(self):
        from cryptowarz import gear as gr
        from cryptowarz.progress import Profile
        profile = Profile(gear_wins={"meme": 4})
        gr.retune(profile, "meme", "major")
        self.assertEqual(self.js["wins_after_move"], profile.gear_wins)

    def test_both_sides_refuse_the_same_things(self):
        self.assertTrue(self.js["refused_unearned_rename"])
        self.assertTrue(self.js["refused_broke_retune"])
        self.assertTrue(self.js["drops_the_name_when_the_piece_is_gone"])


@requires_node
class TestMarketShapeParity(unittest.TestCase):
    """Both ports must move the market the same way, not just price it the same.

    The constants are the easy half. What matters is that a run really does
    persist for a few days on both sides - a port that read TREND_FLIP and then
    re-rolled every day would have the same numbers in it and a completely
    different game coming out.
    """

    @classmethod
    def setUpClass(cls):
        cls.js = run_node("dump.js")["market"]

    def test_the_constants_match(self):
        from cryptowarz import game as gm
        from cryptowarz import market as mk
        self.assertAlmostEqual(self.js["trend_flip"], mk.TREND_FLIP)
        self.assertAlmostEqual(self.js["trend_strength"], mk.TREND_STRENGTH)
        self.assertAlmostEqual(self.js["tip_chance"], gm.TIP_CHANCE)
        self.assertAlmostEqual(self.js["tip_accuracy"], gm.TIP_ACCURACY)
        self.assertAlmostEqual(self.js["tip_min_run"], gm.TIP_MIN_RUN)
        self.assertEqual(self.js["tip_fresh_for"], gm.TIP_FRESH_FOR)

    def test_a_run_persists_for_days_on_the_port(self):
        import random
        import statistics

        from cryptowarz.market import MarketState

        flips = []
        for seed in range(400):
            rng = random.Random(seed)
            state = MarketState(rng)
            changes, prev = 0, state.running("DOGE")
            for _ in range(30):
                state.drift(rng)
                if state.running("DOGE") != prev:
                    changes += 1
                    prev = state.running("DOGE")
            flips.append(changes)
        self.assertAlmostEqual(self.js["shape"]["trend_changes_per_run"],
                               statistics.median(flips), delta=2)
        self.assertLess(self.js["shape"]["trend_changes_per_run"], 15,
                        "the port re-rolls its trend far too often to be a trend")

    def test_the_port_swings_as_hard(self):
        import random
        import statistics

        from cryptowarz.market import MarketState

        swings = []
        for seed in range(400):
            rng = random.Random(seed)
            state = MarketState(rng)
            base = state.levels["DOGE"]
            path = []
            for _ in range(30):
                state.drift(rng)
                path.append(state.levels["DOGE"] / base)
            swings.append(max(path) / min(path))
        self.assertAlmostEqual(self.js["shape"]["doge_swing"], statistics.median(swings),
                               delta=statistics.median(swings) * 0.45)

    def test_the_port_carries_the_run_and_the_chart_through_a_reload(self):
        self.assertTrue(self.js["trends_survive_a_reload"])

    def test_the_port_keeps_the_same_amount_of_history(self):
        from cryptowarz.market import HISTORY_KEPT, SPARK_DAYS
        self.assertEqual(self.js["history_kept"], HISTORY_KEPT)
        self.assertEqual(self.js["spark_days"], SPARK_DAYS)

    def test_the_port_records_a_day_per_day(self):
        self.assertEqual(self.js["chart_truth"]["days_recorded"], 13)
        self.assertTrue(self.js["chart_truth"]["first_point_is_the_opening_level"])

    def test_the_port_would_draw_the_peg_flat_and_the_memecoin_moving(self):
        """A sparkline scales its window, so a flat coin must be KNOWN flat."""
        self.assertTrue(self.js["chart_truth"]["peg_barely_moves"])
        self.assertTrue(self.js["chart_truth"]["memecoin_really_moves"])


@requires_node
class TestWheelParity(unittest.TestCase):
    """The odds a wheel really pays, measured on both sides.

    Comparing the tables alone would miss a port that read the table correctly
    and then sampled it wrong, which is the failure that matters - so the share
    of each wedge is measured over thousands of spins and checked against the
    weight it is supposed to have.
    """

    @classmethod
    def setUpClass(cls):
        cls.js = run_node("dump.js")["wheel"]

    def test_the_wedge_table_matches(self):
        from cryptowarz.game import WHEEL
        self.assertEqual([(w["label"], w["weight"], w["cash"], w["gear"])
                          for w in self.js["table"]],
                         [tuple(rung) for rung in WHEEL])

    def test_the_port_really_pays_those_odds(self):
        from cryptowarz.game import WHEEL
        total = sum(w[1] for w in WHEEL)
        for label, weight, _cash, _gear in WHEEL:
            self.assertAlmostEqual(self.js["shares"].get(label, 0.0), weight / total,
                                   delta=0.02, msg=label)

    def test_gear_stays_rare_on_the_port(self):
        from cryptowarz.game import WHEEL
        expected = sum(w[1] for w in WHEEL if w[3]) / sum(w[1] for w in WHEEL)
        self.assertAlmostEqual(self.js["gear_rate"], expected, delta=0.015)
        self.assertLess(self.js["gear_rate"], 0.08, "the rare wedge is not rare")

    def test_the_port_allows_one_spin_per_stop(self):
        self.assertFalse(self.js["second_spin_at_the_same_stop"])


@requires_node
class TestDiceParity(unittest.TestCase):
    """Both front ends must run the dice, and gate them, identically.

    The behavioural half matters more than the constants: a port that quietly
    stopped gating would keep passing every other test while handing the
    leaderboard to a run that is not supposed to reach it.
    """

    @classmethod
    def setUpClass(cls):
        cls.js = run_node("dump.js")["dice"]

    def test_the_dice_constants_match(self):
        from cryptowarz import game as gm
        self.assertEqual(self.js["every"], gm.DICE_EVERY)
        self.assertEqual(self.js["sides"], gm.DICE_SIDES)
        self.assertAlmostEqual(self.js["top_prize"], gm.DICE_TOP_PRIZE)

    def test_the_closeness_ladder_matches(self):
        from cryptowarz.game import DICE_LADDER, dice_tier
        self.assertEqual([(r["reach"], r["label"], r["share"]) for r in self.js["ladder"]],
                         [tuple(rung) for rung in DICE_LADDER])
        self.assertEqual(self.js["tiers"],
                         [dice_tier(d)[1] for d in (0, 1, 2, 3, 4, 5, 9)])

    def test_both_ports_value_a_call_the_same(self):
        from cryptowarz.game import DICE_SIDES, DICE_TOP_PRIZE, dice_tier
        expected = [round(DICE_TOP_PRIZE
                          * sum(dice_tier(abs(pick - r))[1]
                                for r in range(1, DICE_SIDES + 1)) / DICE_SIDES)
                    for pick in range(1, DICE_SIDES + 1)]
        self.assertEqual(self.js["ev_by_call"], expected)

    def test_gear_lifts_the_dice_prize_on_both_sides(self):
        self.assertTrue(self.js["gear_lifts_the_prize"])

    def test_the_streak_constants_match(self):
        from cryptowarz import game as gm
        self.assertEqual(self.js["streak_calls"], list(gm.HOT_HAND))
        self.assertAlmostEqual(self.js["streak_chance"], gm.HOT_HAND_CHANCE)
        self.assertAlmostEqual(self.js["streak_min"], gm.HOT_HAND_MIN)
        self.assertAlmostEqual(self.js["streak_max"], gm.HOT_HAND_MAX)

    def test_the_unranked_grade_matches(self):
        from cryptowarz.progress import UNRANKED_GRADE
        self.assertEqual(self.js["unranked_grade"], UNRANKED_GRADE)
        self.assertEqual(self.js["grade_shown"], UNRANKED_GRADE)

    def test_the_port_hides_it_the_same_way(self):
        self.assertFalse(self.js["ready_on_day_one"])
        self.assertTrue(self.js["calls_start_it"])
        self.assertFalse(self.js["reversed_does_not"])

    def test_the_payout_has_the_same_shape_on_both_sides(self):
        """Measured, not read off the constants.

        Two generators from one seed produce different streams, so the exact
        payouts cannot match. What must match is the behaviour the player
        feels: it skips some rides, the amounts vary widely, and nothing ever
        comes out above the ceiling.
        """
        from cryptowarz.game import HOT_HAND_CHANCE, HOT_HAND_MAX, HOT_HAND_MIN
        js = self.js["payouts"]
        self.assertAlmostEqual(js["paid_share"], HOT_HAND_CHANCE, delta=0.05)
        self.assertLessEqual(js["biggest"], HOT_HAND_MAX + 1e-6)
        self.assertGreaterEqual(js["smallest"], HOT_HAND_MIN - 1e-6)
        self.assertTrue(js["distinct_enough"], "the port pays a flat amount")

    def test_the_port_gates_it_the_same_way(self):
        self.assertTrue(self.js["unlocks_nothing"])
        self.assertTrue(self.js["spends_no_ranked_slot"])
        self.assertTrue(self.js["survives_reload"])


@requires_node
class TestBalanceParity(unittest.TestCase):
    """Shape comparison.

    Exact medians cannot match - mulberry32 and the Mersenne Twister produce
    different streams from the same seed - so what is asserted is every
    conclusion the balance table is supposed to support.
    """

    @classmethod
    def setUpClass(cls):
        cls.js = run_node("balance.js", "150", "--json")

    def test_doing_nothing_still_loses(self):
        r = self.js["do nothing"]
        self.assertLess(r["median"], 0)
        self.assertLessEqual(r["solvent"], 0.05)

    def test_random_play_still_loses_badly(self):
        r = self.js["buy at random"]
        self.assertLess(r["median"], self.js["do nothing"]["median"])
        self.assertLessEqual(r["solvent"], 0.15)

    def test_a_sensible_strategy_is_a_real_contest(self):
        r = self.js["buy the cheapest"]
        self.assertGreater(r["solvent"], 0.25, "punishing, not hard")
        self.assertLess(r["solvent"], 0.85, "a formula, not a game")
        self.assertGreater(r["best"], 100_000, "no upside worth chasing")

    def test_better_judgement_raises_the_ceiling(self):
        self.assertGreater(self.js["+ clear the debt"]["best"],
                           self.js["buy the cheapest"]["best"])
        self.assertGreater(self.js["+ clear the debt"]["p90"],
                           self.js["buy at random"]["p90"])


if __name__ == "__main__":
    unittest.main()
