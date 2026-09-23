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
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from cryptowarz.coins import COINS
from cryptowarz.game import DAYS, START_CAPACITY, START_CASH, START_DEBT, SUBWAY_FARE
from cryptowarz.market import station_markup
from cryptowarz.stations import STATIONS

WEB = Path(__file__).resolve().parent.parent / "web"
ROOT = Path(__file__).resolve().parent.parent
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

    def test_the_page_never_calls_an_export_only_alias(self):
        """A real bug, shipped, and invisible to every other test.

        game.js exports some functions under a different name for the CommonJS
        tests - `credit_wheel: creditWheel`. That alias exists only inside the
        export object, which the build neutralises, so a page calling
        `credit_wheel(...)` throws at runtime and only on the branch that calls
        it. The wheel's 4% gear wedge did exactly that: it announced a piece of
        gear and banked nothing, for two releases, because no browser test ever
        rolled that wedge.
        """
        js = (WEB / "game.js").read_text()
        html = (WEB / "index.html").read_text()
        exports = js[js.index("module.exports"):]
        aliases = re.findall(r"(\w+):\s*(\w+)[,\s}]", exports)
        declared = set(re.findall(r"function\s+(\w+)", js)) | set(
            re.findall(r"(?:const|let|var)\s+(\w+)\s*=", js))
        for alias, real in aliases:
            if alias == real or alias in declared:
                continue
            self.assertNotRegex(html, r"\b" + re.escape(alias) + r"\s*\(",
                                f"the page calls {alias}(), which only exists as an "
                                f"export alias for {real}()")

    def test_the_page_only_calls_functions_the_port_declares(self):
        """The same failure with the alias spelled differently."""
        js = (WEB / "game.js").read_text()
        html = (WEB / "index.html").read_text()
        declared = set(re.findall(r"function\s+(\w+)", js)) | set(
            re.findall(r"(?:const|let|var)\s+(\w+)\s*=", js))
        page = html[html.index("<script>", html.index("</style>")):]
        page_own = set(re.findall(r"function\s+(\w+)", page)) | set(
            re.findall(r"(?:const|let|var)\s+(\w+)\s*=", page))
        for name in ("creditWheel", "creditWin", "levelsFromWins", "brokerOffer",
                     "renameGear", "retuneGear", "displayName", "levelFor",
                     "winningClass", "gradeFor", "runGrade", "recordDaily",
                     "wire", "raidChance", "threatLevel", "difficultyOf",
                     "weaponOf", "repOf", "encounterOdds", "encounterChoices",
                     "resolveStandoff", "openStandoff", "payCost",
                     "raidPressure", "eventWeights", "makeBackup", "readBackup",
                     "writeScores", "standingHeat"):
            if re.search(r"\b" + name + r"\s*\(", page):
                self.assertIn(name, declared | page_own,
                              f"the page calls {name}() and nothing declares it")

    def test_the_page_is_sized_for_a_phone_browser_with_toolbars(self):
        """iOS Safari sizes 100% and 100vh against the viewport you get with
        the toolbars HIDDEN, so a page exactly one screen tall puts its last
        row under the address bar - and with overflow:hidden there is no way to
        scroll it back. On a phone that means the RIDE THE TRAIN button is
        simply unreachable. Both fallbacks have to stay."""
        html = (WEB / "index.html").read_text()
        self.assertIn("-webkit-fill-available", html, "older WebKit has no svh")
        self.assertIn("100svh", html, "the layout must be built to the SMALL viewport")
        self.assertNotIn("100dvh", html,
                         "dvh is the current height; it overflows the screen the "
                         "moment the toolbars slide back in")
        # the plain height must still be written first, for anything that
        # understands neither and would otherwise get no height at all
        app = html[html.index(".app{display:flex"):]
        app = app[:app.index("}")]
        self.assertLess(app.index("height:100%"), app.index("height:100svh"))

    def test_a_short_viewport_can_scroll_instead_of_clipping(self):
        """A locked-height layout with overflow:hidden answers a viewport
        smaller than it expected by hiding the top and bottom rows, and that is
        the one failure with no way out - you cannot scroll to what is missing.
        Below a phone-in-landscape height the page scrolls instead."""
        html = (WEB / "index.html").read_text()
        self.assertIn("@media (max-height: 520px)", html)
        block = html[html.index("@media (max-height: 520px)"):]
        block = block[:block.index("\n  }") + 4]
        self.assertIn("body{overflow:auto", block)
        self.assertIn(".app{height:auto", block)
        self.assertIn("main{overflow:visible", block)

    def test_the_edges_are_kept_clear_of_the_notch_and_the_home_bar(self):
        """viewport-fit=cover puts the page under both, so every edge has to
        pay the inset back."""
        html = (WEB / "index.html").read_text()
        self.assertIn("viewport-fit=cover", html)
        for rule in ("header{background:#000", "footer{flex:none", ".sheet{position:fixed"):
            block = html[html.index(rule):]
            block = block[:block.index("}")]
            self.assertIn("env(safe-area-inset-", block, rule)

    def test_the_board_tells_the_truth_about_where_it_is(self):
        """The same file runs in three places, and the shared board only
        exists in one of them. On the published page a signed-out viewer can
        fix it by signing in; served from any other host there is no Claude
        runtime and never will be, so telling that viewer to sign in points
        them at nothing."""
        html = (WEB / "index.html").read_text()
        self.assertIn("function boardIsPossible", html)
        self.assertIn("boardIsPossible() ? \"today\" : \"mine\"", html,
                      "open the board on the tab that has something in it")
        note = html[html.index("if (!rows) {"):]
        note = note[:note.index("return;")]
        self.assertIn("boardIsPossible()", note, "one message for both absences")
        self.assertIn("signed in", note)
        self.assertIn("open-web version", note)

    def test_a_browser_that_refuses_to_save_says_so(self):
        """Every write is wrapped in try/catch, which keeps a blocked store
        from ending the run - and lets somebody in Private Browsing play thirty
        days and lose all of it without being told. The probe exists because
        Safari HAS localStorage in private mode; it just throws on write."""
        js = (WEB / "game.js").read_text()
        html = (WEB / "index.html").read_text()
        self.assertIn("function storageWorks", js)
        self.assertIn("localStorage.setItem(probe", js)
        self.assertIn('id="nosave"', html)
        self.assertIn("warnIfNothingIsBeingSaved", html)
        boot = html[html.index("function boot(){"):]
        self.assertLess(boot.index("warnIfNothingIsBeingSaved"), boot.index("readSave"),
                        "the warning must be up before the first render")

    def test_the_downloadable_page_is_a_whole_document(self):
        """A bug that shipped: the artifact build drops index.html's <head>,
        because the host page owns it. The same bytes saved as a file opened in
        quirks mode, at desktop width on a phone, and with no declared charset
        to fall back on when there is no HTTP header. docs/index.html is the
        standalone build, and it has to be a complete document."""
        page = ROOT / "docs" / "index.html"
        self.assertTrue(page.exists(), "run web/build.py")
        text = page.read_text()
        for needed in ("<!doctype html>", '<meta charset="utf-8">',
                       'name="viewport"', "<title>CryptoWarz</title>",
                       "</head>", "<body>", "</body>", "</html>"):
            self.assertIn(needed, text, needed)
        self.assertEqual(text.count("<html"), 1)
        self.assertEqual(text.count("<body>"), 1)
        self.assertLess(text.index("<meta charset"), text.index("<style>"))
        self.assertLess(text.index("</style>"), text.index("<body>"))
        self.assertNotIn("<script src=", text, "a relative script survived")

    def test_the_two_builds_carry_the_same_game(self):
        """The wrapper is the only difference; a standalone page that had
        drifted from the artifact would be a second game to keep in step."""
        page = (ROOT / "docs" / "index.html").read_text()
        bundle = (WEB / "cryptowarz.artifact.html").read_text()
        end = bundle.index("</style>") + len("</style>")
        self.assertIn(bundle[bundle.index("<style>"):end], page, "the styles drifted")
        self.assertIn(bundle[end:].strip(), page, "the game drifted")

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
class TestBackupParity(unittest.TestCase):
    """The one feature whose entire value is that the two ports agree.

    "Take your progress with you" means nothing if it only travels to another
    tab, so the sharp test here is interoperability rather than sameness: a
    line the browser wrote is read by Python, and a line Python wrote is read
    by the browser, both with a unicode gear name in it. Everything else -
    the checksum vectors, the refusals - exists so that a half-copied paste
    cannot quietly overwrite a good profile on either side.
    """

    @classmethod
    def setUpClass(cls):
        cls.js = run_node("dump.js")["backup"]

    def test_the_envelope_matches(self):
        from cryptowarz import backup as bk
        self.assertEqual(self.js["version"], bk.BACKUP_VERSION)
        self.assertEqual(self.js["prefix"], bk.PREFIX)

    def test_the_checksum_is_the_same_function(self):
        from cryptowarz import backup as bk
        self.assertEqual(self.js["fnv"], [bk.fnv1a(t) for t in ("", "a", "foobar")])

    def test_python_can_read_a_line_the_browser_wrote(self):
        from cryptowarz import backup as bk
        read = bk.read(self.js["line"])
        self.assertEqual(read["profile"].runs, 37)
        self.assertEqual(read["profile"].gear_wins, {"meme": 7, "major": 3})
        self.assertEqual(read["profile"].gear_names, {"meme": "Ratty — the good one"})

    def test_and_the_browser_can_read_one_python_wrote(self):
        """Written here, decoded by node, compared field by field."""
        from cryptowarz import backup as bk
        from cryptowarz.progress import Profile

        profile = Profile(runs=11, best_net=4_242.0, gear_wins={"major": 2},
                          gear_names={"major": "Старый — 日本"})
        line = bk.make(profile)
        script = (
            "const G = require('./game.js');"
            "const out = G.readBackup(process.argv[1]);"
            "console.log(JSON.stringify({runs: out.profile.runs, "
            "best: out.profile.best_net, wins: out.profile.gear_wins, "
            "names: out.profile.gear_names}));"
        )
        result = subprocess.run([shutil.which("node"), "-e", script, line],
                                cwd=WEB, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        got = json.loads(result.stdout)
        self.assertEqual(got["runs"], 11)
        self.assertEqual(got["best"], 4_242.0)
        self.assertEqual(got["wins"], {"major": 2})
        self.assertEqual(got["names"], {"major": "Старый — 日本"})

    def test_a_run_survives_the_trip_on_the_port_too(self):
        from cryptowarz import backup as bk
        from cryptowarz import save as sv
        from cryptowarz.game import Game
        game = Game(seed=5, difficulty="hard")
        game.day = 9
        back = sv.from_dict(bk.read(bk.make(None, sv.to_dict(game)))["save"])
        self.assertEqual(self.js["with_a_run"]["day"], back.day)
        self.assertEqual(self.js["with_a_run"]["difficulty"], back.difficulty)
        self.assertEqual(self.js["with_a_run"]["station"], back.station.name)
        self.assertAlmostEqual(self.js["with_a_run"]["debt"], back.player.debt, places=2)

    def test_both_sides_refuse_the_same_things(self):
        self.assertTrue(self.js["refuses_truncated"])
        self.assertTrue(self.js["refuses_rubbish"])
        self.assertTrue(self.js["refuses_a_newer_version"])

    def test_both_sides_forgive_a_wrapped_paste(self):
        self.assertEqual(self.js["forgives_line_breaks"], 37)

    def test_both_sides_drop_a_goal_that_does_not_exist(self):
        self.assertEqual(self.js["drops_an_unknown_goal"], ["first_run", "in_the_black"])

    def test_both_sides_keep_unicode_intact(self):
        self.assertEqual(self.js["unicode"], {"major": "Старый — 日本"})

    def test_a_pasteable_line_stays_pasteable_on_both_sides(self):
        from cryptowarz import backup as bk
        from cryptowarz.progress import Profile
        self.assertTrue(self.js["short_enough_to_paste"])
        self.assertLess(len(bk.make(Profile(runs=37, gear_wins={"meme": 7}))), 1_000)


@requires_node
class TestEncounterParity(unittest.TestCase):
    """A blocking, save-riding decision is the easiest thing in this game to
    get subtly wrong on one side only: a port that forgot one guard would let
    a phone player trade past a man with a knife, and a port that forgot to
    save the standoff would let them reload out of it."""

    @classmethod
    def setUpClass(cls):
        cls.js = run_node("dump.js")["encounter"]

    def test_the_armoury_matches(self):
        from cryptowarz.encounter import FOR_SALE, WEAPONS
        self.assertEqual([w["key"] for w in self.js["weapons"]], [w.key for w in WEAPONS])
        self.assertEqual(self.js["for_sale"], list(FOR_SALE))
        for js, py in zip(self.js["weapons"], WEAPONS):
            self.assertEqual(js["name"], py.name, py.key)
            self.assertEqual(js["blurb"], py.blurb, py.key)
            for field in ("edge", "heat", "breaks", "price"):
                self.assertAlmostEqual(js[field], getattr(py, field), msg=f"{py.key}.{field}")

    def test_the_script_matches_word_for_word(self):
        from cryptowarz.encounter import KINDS
        self.assertEqual([k["key"] for k in self.js["kinds"]], [k.key for k in KINDS])
        for js, py in zip(self.js["kinds"], KINDS):
            self.assertEqual(js["title"], py.title, py.key)
            self.assertAlmostEqual(js["severity"], py.severity, msg=py.key)
            self.assertEqual(js["armable"], py.armable, py.key)
            self.assertEqual(list(js["opening"]), list(py.opening), py.key)

    def test_the_numbers_match(self):
        from cryptowarz import encounter as en
        n = self.js["numbers"]
        self.assertAlmostEqual(n["run"], en.RUN_BASE)
        self.assertAlmostEqual(n["fight"], en.FIGHT_BASE)
        self.assertAlmostEqual(n["load"], en.MAX_LOAD_PENALTY)
        self.assertEqual(n["rep_max"], en.REP_MAX)
        self.assertAlmostEqual(n["rep_odds"], en.REP_ODDS)
        self.assertEqual(tuple(n["take_cash"]), en.TAKE_CASH)
        self.assertEqual(tuple(n["take_bag"]), en.TAKE_BAG)
        self.assertAlmostEqual(n["hospital"], en.HOSPITAL_CHANCE)

    def test_both_ports_stop_the_run_dead(self):
        """Twelve calls, every one refused, on both sides."""
        self.assertTrue(self.js["blocks_everything"])

    def test_both_ports_keep_him_there_across_a_reload(self):
        from cryptowarz import save as sv
        from cryptowarz import encounter as en
        from cryptowarz.game import Game
        game = Game(seed=11)
        game.weapon = "bat"
        en.open_standoff(game)
        back = sv.from_dict(sv.to_dict(game))
        self.assertEqual(self.js["survives_a_save"]["kind"], back.pending["kind"])
        self.assertEqual(self.js["survives_a_save"]["weapon"], back.weapon)
        self.assertTrue(self.js["survives_a_save"]["blocked"])
        self.assertTrue(self.js["old_save_has_neither"])

    def test_the_odds_match_choice_for_choice(self):
        from cryptowarz import encounter as en
        from cryptowarz.game import Game

        def cornered(weapon=None, rep=0, load=0.0):
            game = Game(seed=11)
            game.player.cash = 8_000.0
            game.player.capacity = 25_000.0
            game.weapon = weapon
            game.stats["rep"] = rep
            if load:
                game.player.holding("DOGE").cost = game.player.capacity * load
                game.player.holding("DOGE").qty = 1.0
            en.open_standoff(game)
            return game

        self.assertAlmostEqual(self.js["odds_empty"], en.odds(cornered(), "run"))
        self.assertAlmostEqual(self.js["odds_loaded"], en.odds(cornered(load=1.0), "run"))
        self.assertEqual(self.js["odds_by_weapon"],
                         [round(en.odds(cornered(weapon=w.key), "weapon"), 4)
                          for w in en.WEAPONS])
        self.assertEqual(self.js["odds_rep"],
                         [round(en.odds(cornered(rep=r), "fight"), 4) for r in (-3, 0, 3)])
        self.assertEqual(self.js["pay_is_certain"], 1)

    def test_both_ports_offer_the_same_options(self):
        self.assertEqual(self.js["choices_bare"], ["run", "fight", "pay"])
        self.assertEqual(self.js["choices_armed"], ["run", "fight", "weapon", "pay"])

    def test_a_weapon_cuts_both_ways_on_both_sides(self):
        self.assertTrue(self.js["carry_cuts_both_ways"]["raid_up"])
        self.assertTrue(self.js["carry_cuts_both_ways"]["stickup_down"])

    def _standoff(self, kind):
        from cryptowarz import encounter as en
        from cryptowarz.game import Game
        game = Game(seed=13)
        game.player.cash = 9_000.0
        game.player.debt = 12_000.0
        game.player.capacity = 1e9
        game.player.holding("BTC").qty = 1.0
        game.player.holding("BTC").cost = 5_000.0
        en.open_standoff(game, kind)
        return game

    def test_the_shark_s_man_costs_the_same_on_both_sides(self):
        """Paying him is the good end - it comes off the loan - so both ports
        have to agree on the demand and on what refusing adds."""
        from cryptowarz import encounter as en
        js = self.js["collector"]
        self.assertEqual(js["options"], ["pay", "run", "fight", "weapon"][:len(js["options"])])
        self.assertEqual(js["demand"], round(en.collector_demand(self._standoff("collector"))))
        self.assertAlmostEqual(js["fee_ran"], en.SHARK_FEE_RAN)
        self.assertAlmostEqual(js["fee_fought"], en.SHARK_FEE_FOUGHT)
        for choice in ("pay", "run"):
            game = self._standoff("collector")
            game.resolve(choice)
            self.assertEqual(js[choice]["cash"], round(game.player.cash), choice)
            self.assertEqual(js[choice]["debt"], round(game.player.debt), choice)

    def test_the_badge_offers_the_same_three_answers_on_both_sides(self):
        from cryptowarz import encounter as en
        js = self.js["badge"]
        self.assertEqual(js["options"], ["comply", "lawyer", "run"])
        self.assertTrue(js["no_weapon_offered"],
                        "no port may offer to swing at a federal agent")
        self.assertEqual(js["lawyer_cost"], round(en.lawyer_cost(self._standoff("badge"))))
        self.assertAlmostEqual(js["lawyer_saves"], en.LAWYER_SAVES)
        self.assertAlmostEqual(js["caught"], en.CAUGHT_MULTIPLIER)
        for choice in ("comply", "lawyer"):
            game = self._standoff("badge")
            game.resolve(choice)
            self.assertEqual(js[choice]["cash"], round(game.player.cash), choice)
            self.assertEqual(js[choice]["raids"], game.stats["raids"], choice)

    def test_paying_keeps_the_bag_on_both_sides(self):
        paid = self.js["paying_keeps_the_bag"]
        self.assertEqual(paid["qty"], 1, "paying must not cost the bag")
        self.assertEqual(paid["rep"], -1)
        self.assertTrue(paid["cheaper"])


@requires_node
class TestDifficultyParity(unittest.TestCase):
    """A second scoring axis is exactly the kind of thing that drifts: one port
    multiplies by it, the other forgets, and the same run is worth two numbers
    on one leaderboard. Every lever is compared, and so is the fallback that
    keeps an old save loading."""

    @classmethod
    def setUpClass(cls):
        cls.js = run_node("dump.js")["hardness"]

    def test_the_table_matches(self):
        from cryptowarz.progress import DEFAULT_DIFFICULTY, DIFFICULTIES
        self.assertEqual([d["key"] for d in self.js["table"]], [d.key for d in DIFFICULTIES])
        self.assertEqual(self.js["default"], DEFAULT_DIFFICULTY)
        for js, py in zip(self.js["table"], DIFFICULTIES):
            self.assertEqual(js["name"], py.name, py.key)
            self.assertEqual(js["blurb"], py.blurb, py.key)
            self.assertAlmostEqual(js["cash"], py.cash, msg=py.key)
            self.assertAlmostEqual(js["debt_mult"], py.debt_mult, msg=py.key)
            self.assertAlmostEqual(js["shark"], py.shark, msg=py.key)
            self.assertAlmostEqual(js["heat_mult"], py.heat_mult, msg=py.key)
            self.assertAlmostEqual(js["mult"], py.score_mult, msg=py.key)

    def test_both_ports_build_the_same_run(self):
        from cryptowarz.game import Game
        for js in self.js["made"]:
            py = Game(seed=1, difficulty=js["key"])
            self.assertAlmostEqual(js["cash"], py.player.cash, places=2, msg=js["key"])
            self.assertAlmostEqual(js["debt"], py.player.debt, places=2, msg=js["key"])
            self.assertAlmostEqual(js["shark"], py.shark_rate, msg=js["key"])
            self.assertAlmostEqual(js["heat_mult"], py.heat_mult, msg=js["key"])

    def test_both_ports_fall_back_the_same_way(self):
        from cryptowarz.progress import difficulty_of
        self.assertEqual(self.js["unknown_falls_back"], difficulty_of("nonsense").key)
        self.assertEqual(self.js["old_save_loads_as_express"], "normal")

    def test_the_fixer_is_a_ratio_on_both_sides(self):
        from cryptowarz.game import Game
        self.assertAlmostEqual(self.js["fixer_still_gets_its_discount"],
                               Game(seed=1, perk="fixer").shark_rate)

    def test_the_same_run_is_worth_the_same_points_on_both_sides(self):
        from cryptowarz.game import Game
        from cryptowarz.progress import run_points
        for key, js_points in self.js["points_by_difficulty"].items():
            game = Game(seed=9, difficulty=key)
            game.player.debt = 0.0
            game.player.wallet.clear()
            game.player.cash = 100_000.0
            game.finalise()
            self.assertEqual(js_points, round(run_points(game)), key)

    def test_it_rides_the_save_on_both_sides(self):
        from cryptowarz.game import Game
        from cryptowarz import save as sv
        game = Game(seed=4, difficulty="hard")
        game.day = 12
        back = sv.from_dict(sv.to_dict(game))
        self.assertEqual(self.js["survives_a_save"]["difficulty"], back.difficulty)
        self.assertAlmostEqual(self.js["survives_a_save"]["debt"], back.player.debt, places=2)
        self.assertAlmostEqual(self.js["survives_a_save"]["shark"], back.shark_rate)


@requires_node
class TestEnforcementParity(unittest.TestCase):
    """The grace period, the ramp, and the meter.

    The map strings are the sharp test here: sixteen stations reduced to one
    letter each, on three different days. Two ports that had drifted by a
    single constant anywhere in the weight chain would produce different
    strings, and the strings are compared exactly because this part of the
    model is arithmetic rather than sampling - no RNG is involved at all.
    """

    @classmethod
    def setUpClass(cls):
        cls.js = run_node("dump.js")["enforcement"]

    def test_the_constants_match(self):
        from cryptowarz import events as ev
        self.assertEqual(self.js["grace"], ev.RAID_GRACE)
        self.assertAlmostEqual(self.js["ramp_to"], ev.RAID_RAMP_TO)
        self.assertEqual(self.js["bars"], ev.THREAT_BARS)
        self.assertEqual([tuple(t) for t in self.js["thresholds"]],
                         [tuple(t) for t in ev.THREAT])

    def test_the_grace_is_absolute_on_both_sides(self):
        self.assertEqual(self.js["chance_in_grace"], 0)
        self.assertEqual(self.js["raid_weight_in_grace"], 0)

    def test_the_ramp_climbs_identically(self):
        from cryptowarz import events as ev
        from cryptowarz.game import Game
        game = Game(seed=3)
        self.assertEqual([round(ev.raid_pressure(game, d), 3) for d in (1, 8, 15, 16, 22, 30)],
                         self.js["pressure"])

    def test_the_whole_map_reads_the_same_on_both_sides(self):
        from cryptowarz import events as ev
        from cryptowarz.game import Game
        from cryptowarz.stations import STATIONS
        for day, js_map in self.js["map_by_day"].items():
            game = Game(seed=3)
            game.day = int(day)
            py_map = "".join(ev.threat_level(ev.raid_chance(game, s, int(day)))[0][0]
                             for s in STATIONS)
            self.assertEqual(js_map, py_map, f"day {day}")

    def test_a_vpn_moves_the_meter_the_same_way_on_both_sides(self):
        from cryptowarz import events as ev
        from cryptowarz.game import Game
        from cryptowarz.stations import STATIONS
        game = Game(seed=3)
        game.day = 22
        game.player.vpn = 2
        py_map = "".join(ev.threat_level(ev.raid_chance(game, s, 22))[0][0] for s in STATIONS)
        self.assertEqual(self.js["map_with_vpn"], py_map)

    def test_the_odds_themselves_match(self):
        from cryptowarz import events as ev
        from cryptowarz.game import Game
        for js_chance, day in zip(self.js["chance_here"], (16, 22, 30)):
            game = Game(seed=3)
            game.day = day
            self.assertAlmostEqual(js_chance, round(ev.raid_chance(game, None, day), 4), msg=day)

    def test_the_news_post_matches_word_for_word(self):
        from cryptowarz import events as ev
        from cryptowarz.game import Game
        quiet = Game(seed=3)
        quiet.day = 8
        py_quiet = ev.wire(quiet, day=8)
        self.assertEqual(self.js["wire_quiet"]["label"], py_quiet["label"])
        self.assertEqual(self.js["wire_quiet"]["bars"], py_quiet["bars"])
        self.assertEqual(self.js["wire_quiet"]["grace_left"], py_quiet["grace_left"])
        self.assertEqual(self.js["wire_quiet"]["text"], py_quiet["text"])
        late = Game(seed=3)
        late.day = 24
        py_late = ev.wire(late, day=24)
        self.assertEqual(self.js["wire_late"]["label"], py_late["label"])
        self.assertEqual(self.js["wire_late"]["text"], py_late["text"])
        self.assertAlmostEqual(self.js["wire_late"]["two_stops"],
                               round(py_late["two_stops"], 4))

    def test_the_grace_period_map_matches(self):
        """What the stops are LIKE, shown while the live reading is all zeros."""
        from cryptowarz import events as ev
        from cryptowarz.stations import STATIONS
        self.assertEqual(self.js["standing_heat"], [ev.standing_heat(s) for s in STATIONS])

    def test_every_line_of_copy_matches(self):
        from cryptowarz import events as ev
        self.assertEqual({k: list(v) for k, v in self.js["lines"].items()},
                         {k: list(v) for k, v in ev.WIRE_LINES.items()})


@requires_node
class TestBrokerParity(unittest.TestCase):
    """The dealer is the only thing in the game that buys progression, so the
    two ports must agree on every fence around him - the price, the one deal
    per run, and above all the refusal to sell to a run the board will not
    rank. A port that let god mode buy gear would launder free money into
    permanent luck."""

    @classmethod
    def setUpClass(cls):
        cls.js = run_node("dump.js")["broker"]

    def test_the_price_matches(self):
        from cryptowarz.gear import BROKER_PRICE
        self.assertEqual(self.js["price"], BROKER_PRICE)

    def test_both_sides_open_the_deal_on_the_same_conditions(self):
        self.assertEqual(self.js["at_a_shop_with_the_money"], "meme")
        self.assertIsNone(self.js["a_dollar_short"])
        self.assertIsNone(self.js["no_shop_no_dealer"])

    def test_neither_port_sells_to_an_unrankable_run(self):
        self.assertIsNone(self.js["unrankable_run_cannot_buy"])
        self.assertTrue(self.js["unrankable_run_is_refused"])

    def test_both_sides_sell_what_you_are_carrying(self):
        self.assertEqual(self.js["sells_what_you_carry"], ["major", "meme"])

    def test_the_million_comes_off_the_score_on_both_sides(self):
        from cryptowarz.gear import BROKER_PRICE
        self.assertEqual(self.js["cash_after"], 25_000)
        self.assertEqual(self.js["off_the_score"], int(BROKER_PRICE))

    def test_one_deal_per_run_on_both_sides(self):
        second = self.js["second_visit"]
        self.assertIsNone(second["offer"])
        self.assertTrue(second["refused"])
        self.assertTrue(second["kept_the_cash"], "a refused deal took money")

    def test_the_purchase_banks_on_both_sides(self):
        """The half that shipped broken once already: naming a class is not
        banking it, and only the caller can finish the job."""
        bought = self.js["award_banks_a_win"]
        self.assertEqual(bought["award"], "major")
        self.assertEqual(bought["wins"], {"major": 1})


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

    def test_the_port_measures_profit_from_the_station_price(self):
        """Compared as a RELATIONSHIP, never as a value.

        The two generators produce different markets from one seed, so the
        actual percentages cannot match and asserting they do only produces a
        test that fails for the wrong reason. What must hold on both sides is
        that the number is computed against what this stop pays rather than the
        abstract market level - so the dump reports both, and they must differ
        wherever the station has an opinion about the coin.
        """
        reads = self.js["profit_reads"]
        self.assertNotAlmostEqual(reads["against_station_price"], reads["against_level"],
                                  places=3,
                                  msg="the port is pricing your bag off the market level")

    def test_the_page_computes_profit_the_way_the_terminal_does(self):
        """Structural, because the web formula lives in the page, not the port."""
        html = (WEB / "index.html").read_text()
        body = html[html.index("function moveFor("):html.index("function hereFor(")]
        self.assertIn("held.cost / held.qty", body)
        self.assertIn("price / paid - 1", body)

    def test_the_port_keeps_the_same_amount_of_history(self):
        from cryptowarz.market import HISTORY_KEPT, SPARK_DAYS
        self.assertEqual(self.js["history_kept"], HISTORY_KEPT)
        self.assertEqual(self.js["spark_days"], SPARK_DAYS)

    def test_the_port_records_a_day_per_day(self):
        """The invariant rather than a fixed count. A stopped train or a
        beating takes a day off you, and both used to move the clock without
        moving the market - which froze prices for a day and broke the one
        point per day the sparklines are drawn from."""
        truth = self.js["chart_truth"]
        self.assertTrue(truth["one_point_per_day"],
                        f"{truth['days_recorded']} points for {truth['day']} days")
        self.assertGreaterEqual(truth["days_recorded"], 13)
        self.assertTrue(truth["first_point_is_the_opening_level"])
        self.assertTrue(truth["shock_reaches_the_chart"],
                        "the port's chart still misses a shock")

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
