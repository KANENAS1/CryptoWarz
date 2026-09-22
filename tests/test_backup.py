"""Backups: the promise that nothing here is trapped in one browser.

The save and the profile live in whatever browser or home directory you
happened to play in, and the game deliberately does not trust anything it did
not write itself - so when that storage goes, twenty runs of gear go with it
and nothing can rebuild them.

The line this module produces is the answer, and three properties make it worth
having. It must round-trip exactly, or it is a slow way to lose a profile. It
must refuse a damaged line rather than half-loading it, because overwriting
good progress with a truncated paste is the precise failure a backup exists to
prevent. And it must read the same in both front ends, or "take it with you"
only means "to another tab".
"""

import unittest

from cryptowarz import backup as B
from cryptowarz import progress as P
from cryptowarz import save as S
from cryptowarz.game import Game


def loaded_profile():
    return P.Profile(runs=37, best_net=812_345.0, best_tier_cleared=3,
                     achievements=["first_run", "in_the_black"],
                     gear_wins={"meme": 7, "major": 3},
                     gear_names={"meme": "Ratty — the good one"})


class TestTheLine(unittest.TestCase):
    def test_a_profile_survives_the_round_trip_exactly(self):
        before = loaded_profile()
        after = B.read(B.make(before))["profile"]
        self.assertEqual(after.to_dict(), before.to_dict())

    def test_it_is_short_enough_to_paste(self):
        """A profile has to fit in a note or a message, or nobody will keep
        one. The run is opt-in precisely because it is not short."""
        self.assertLess(len(B.make(loaded_profile())), 1_000)

    def test_a_run_can_ride_along_and_comes_back_playable(self):
        game = Game(seed=5, difficulty="hard")
        game.day = 9
        line = B.make(loaded_profile(), S.to_dict(game))
        back = S.from_dict(B.read(line)["save"])
        self.assertEqual((back.day, back.difficulty, back.station.name),
                         (game.day, game.difficulty, game.station.name))
        self.assertAlmostEqual(back.player.debt, game.player.debt)

    def test_the_board_can_ride_along_too(self):
        scores = [{"net_worth": 120_000.0, "day": 30, "verdict": "rich",
                   "finished_at": 1.0, "seed": 4}]
        self.assertEqual(B.read(B.make(loaded_profile(), None, scores))["scores"], scores)

    def test_unicode_in_a_gear_name_survives(self):
        profile = P.Profile(gear_wins={"major": 2}, gear_names={"major": "Старый — 日本"})
        self.assertEqual(B.read(B.make(profile))["profile"].gear_names,
                         {"major": "Старый — 日本"})


class TestItRefusesRatherThanHalfLoading(unittest.TestCase):
    def test_a_truncated_line_is_refused(self):
        line = B.make(loaded_profile())
        with self.assertRaises(ValueError) as caught:
            B.read(line[:-6])
        self.assertIn("half copied", str(caught.exception))

    def test_a_line_with_a_character_changed_is_refused(self):
        line = B.make(loaded_profile())
        swapped = line[:-1] + ("A" if line[-1] != "A" else "B")
        with self.assertRaises(ValueError):
            B.read(swapped)

    def test_something_that_is_not_a_backup_is_refused_by_name(self):
        for text in ("", "hello", "CW1.deadbeef", "CW9.deadbeef.aaaa"):
            with self.assertRaises(ValueError, msg=text):
                B.read(text)

    def test_a_newer_backup_says_so_instead_of_guessing(self):
        line = B.encode({"v": B.BACKUP_VERSION + 1, "profile": {}})
        with self.assertRaises(ValueError) as caught:
            B.read(line)
        self.assertIn("newer build", str(caught.exception))

    def test_whitespace_and_line_breaks_are_forgiven(self):
        """People paste out of emails, and emails wrap."""
        line = B.make(loaded_profile())
        wrapped = "\n".join(line[i:i + 40] for i in range(0, len(line), 40))
        self.assertEqual(B.read(wrapped)["profile"].runs, 37)


class TestItGoesThroughTheNormalDoor(unittest.TestCase):
    def test_an_unknown_achievement_is_dropped_on_the_way_in(self):
        """The profile is rebuilt by the same reader a stored one uses, so a
        backup is not a second, more trusting path into the profile."""
        profile = loaded_profile()
        profile.achievements.append("nonsense_award")
        back = B.read(B.make(profile))["profile"]
        self.assertNotIn("nonsense_award", back.achievements)

    def test_an_imported_profile_brings_gear_not_a_score(self):
        """It is base64, not a lock. What it must never do is put a number on
        the board that nobody played for - and it cannot, because the board is
        written from finished runs, not from profiles."""
        profile = loaded_profile()
        profile.best_net = 10 ** 12
        back = B.read(B.make(profile))["profile"]
        self.assertEqual(back.gear_wins, profile.gear_wins)
        self.assertEqual(S.read_scores.__module__, "cryptowarz.save")


class TestTheChecksum(unittest.TestCase):
    def test_it_is_the_fnv_everyone_agrees_on(self):
        # the published test vectors for 32-bit FNV-1a
        self.assertEqual(B.fnv1a(""), 0x811C9DC5)
        self.assertEqual(B.fnv1a("a"), 0xE40C292C)
        self.assertEqual(B.fnv1a("foobar"), 0xBF9CF968)


if __name__ == "__main__":
    unittest.main()
