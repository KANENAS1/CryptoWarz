"""What survives a run: achievements, perks, and the difficulty ladder.

A run-based game lives or dies on what happens *after* you lose. Until now a
lost run gave you nothing but a number, so the only reason to start another was
that you felt like it - and the thirtieth loss looked exactly like the first.

Three things change that, and all three are the honest kind of hook: they pay
you for playing rather than punish you for stopping.

**Achievements** name things worth trying, so the game teaches its own depth -
most players never think to sit out a raid in the vault until "Untouchable"
tells them it is possible.

**Perks** turn achievements into something you carry into the next run. This is
the load-bearing one: a run that ends badly still moves a bar, so quitting
costs you progress you can see.

**Tiers** raise the ceiling once you have beaten the game, because mastery with
nowhere left to go is where people stop.

**Ranked runs** give the day a shape: three markets, the same three for
everybody, and one attempt at each. That is the part a leaderboard needs -
without a fixed slate, comparing two players compares their patience.

Three rules keep it honest. Practice is unlimited and always available, so
nobody is ever locked out of their own game. A missed day takes nothing away:
there is no streak to break, just a new slate tomorrow. And the three markets
differ from one another, so run two cannot be run one replayed with the
answers.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .gear import CLASSES

PROGRESS_VERSION = 3


# --------------------------------------------------------------- achievements

@dataclass(frozen=True)
class Achievement:
    key: str
    name: str
    blurb: str
    #: given a finished game, did this happen?
    test: Callable[[Any], bool]


def _visited_all(g) -> bool:
    from .stations import STATIONS
    return len(g.stats.get("stations", set())) >= len(STATIONS)


ACHIEVEMENTS: List[Achievement] = [
    Achievement("first_run", "Off Peak", "Finish a run, any run.",
                lambda g: True),
    Achievement("in_the_black", "In the Black", "Finish a run worth more than you started.",
                lambda g: g.final_score() > 2_000),
    Achievement("debt_free", "Paid in Full", "Clear the Shark completely.",
                lambda g: g.player.debt <= 0),
    Achievement("whale", "Whale Watching", "Be worth $100,000 at any point.",
                lambda g: g.stats.get("peak_worth", 0) >= 100_000),
    Achievement("tourist", "The Whole Map", "Visit all ten stations in one run.",
                _visited_all),
    Achievement("untouchable", "Untouchable", "Finish thirty days without a single SEC raid.",
                lambda g: g.stats.get("raids", 0) == 0 and g.day > 25),
    Achievement("moonshot", "Moonshot", "Triple your money on a single trade.",
                lambda g: g.stats.get("best_multiple", 0) >= 3.0),
    Achievement("degen", "Nothing but Vibes", "Finish in profit holding only memecoins.",
                lambda g: g.final_score() > 2_000 and g.stats.get("meme_only_finish", False)),
    Achievement("six_figures", "Six Figures", "Finish a run above $100,000.",
                lambda g: g.final_score() >= 100_000),
    Achievement("legend", "They Named a Station", "Finish a run above $500,000.",
                lambda g: g.final_score() >= 500_000),
]
BY_KEY = {a.key: a for a in ACHIEVEMENTS}


# ---------------------------------------------------------------------- perks

@dataclass(frozen=True)
class Perk:
    key: str
    name: str
    blurb: str
    unlocked_by: str


PERKS: List[Perk] = [
    Perk("metrocard", "Unlimited MetroCard",
         "Rides are free, and signal delays never cost you a day.", "first_run"),
    Perk("seed_round", "Seed Round", "Start with $2,000 more.", "in_the_black"),
    Perk("burner", "Burner Phone", "Trouble finds you a third less often.", "untouchable"),
    Perk("cold_storage", "Cold Storage", "+$15,000 wallet capacity.", "whale"),
    Perk("fixer", "The Fixer", "The Shark charges 8.5% a day, not 10%.", "debt_free"),
    Perk("insider", "Insider", "The map shows which coin each station pays most for.", "tourist"),
]
PERK_BY_KEY = {p.key: p for p in PERKS}


# ---------------------------------------------------------------------- tiers

@dataclass(frozen=True)
class Tier:
    level: int
    name: str
    blurb: str
    debt: float
    capacity: float
    heat_mult: float
    days: int
    #: what a dollar of net worth is worth on the leaderboard here. A tier 5
    #: run is worth more than a tier 1 run of the same size because it is a
    #: harder thing to have done; the ladder is roughly the inverse of the
    #: measured clear rate, flattened so tier 1 stays worth playing.
    score_mult: float = 1.0

    @property
    def unlocked_by_beating(self) -> int:
        return self.level - 1


TIERS: List[Tier] = [
    # Tuned by simulation, not by feel. Starting debt is a far sharper lever
    # than it looks - it compounds daily while trading profit scales linearly
    # with capacity - so an early table that raised debt to $19,000 made the
    # top tier mathematically unwinnable (0-3% even with a perk and good play).
    # The ladder leans on capacity and heat instead, and the top tier now sits
    # at 8% solo and 22% with a perk: hard, and beatable.
    Tier(1, "Off Peak",   "The standard thirty days.",           5_500.0, 25_000.0, 1.00, 30, 1.00),
    Tier(2, "Rush Hour",  "A bigger loan and more eyes on you.", 6_800.0, 21_000.0, 1.25, 30, 1.30),
    Tier(3, "Track Work", "Deeper in, carrying less.",           7_800.0, 17_000.0, 1.50, 30, 1.65),
    Tier(4, "Last Train", "Four fewer days to do it in.",        7_800.0, 15_000.0, 1.60, 26, 2.00),
    Tier(5, "Blackout",   "Everything at once.",                 9_000.0, 13_000.0, 1.80, 26, 2.40),
]
TIER_BY_LEVEL = {t.level: t for t in TIERS}


# ------------------------------------------------------------------- grading

#: Three ranked runs a day, each a full thirty-day market. Three is the number
#: that makes a bad opening survivable without letting anyone grind the board.
RUNS_PER_DAY = 3

#: A finished run is graded on what it was finally worth, weighted by the tier
#: it was played on. Thresholds are the verdict ladder's, subdivided: a run has
#: to roughly triple to move up a letter, which is a step you can feel without
#: being a step you can only take by luck.
GRADES: List[tuple] = [
    (750_000.0, "S+", "They'll name a station after you."),
    (300_000.0, "S",  "Somebody is going to ask questions."),
    (100_000.0, "A",  "Six figures. Quit while you're ahead."),
    (35_000.0,  "B",  "A real score."),
    (10_000.0,  "C",  "Out of the hole and then some."),
    (2_000.0,   "D",  "You finished. Barely."),
    (0.0,       "F",  "The Shark got paid. You didn't."),
]


#: Shown instead of a letter for a run that is not eligible to be ranked.
UNRANKED_GRADE = "G"


def counts_for_progress(game) -> bool:
    """Whether a finished run may touch the board, the goals or the ladder.

    Some runs are handed money they did not earn. Letting one post a score
    would end the leaderboard, and letting it unlock perks and tiers would hand
    somebody the whole progression for nothing. Such a run is a sandbox - and
    because it never spends a ranked slot either, it costs the player nothing.
    """
    return not getattr(game, "hot_hand", False)


def run_grade(game) -> str:
    """The letter a finished run is shown. Both front ends must agree."""
    if not counts_for_progress(game):
        return UNRANKED_GRADE
    return grade(run_points(game))


def tier_mult(tier: int) -> float:
    return TIER_BY_LEVEL.get(tier, TIER_BY_LEVEL[1]).score_mult


def run_points(game) -> float:
    """What a finished run is worth on the board.

    Net worth times the tier weight, floored at zero: a run that ends underwater
    scores nothing rather than scoring negatively, because a leaderboard that
    can be dragged down is one where the safe play is not to play.
    """
    return max(0.0, game.final_score()) * tier_mult(getattr(game, "tier", 1))


def grade(points: float) -> str:
    for threshold, letter, _ in GRADES:
        if points >= threshold:
            return letter
    return GRADES[-1][1]


def grade_blurb(points: float) -> str:
    for threshold, _, blurb in GRADES:
        if points >= threshold:
            return blurb
    return GRADES[-1][2]


def daily_seeds(when: Optional[float] = None) -> List[int]:
    """The three markets everyone gets today, in order.

    Derived from the date, so every player on a given day plays the same slate,
    and derived per slot, so the second run is a new market rather than the
    first one replayed with the answers.
    """
    day = daily_seed(when)
    return [day * 10 + slot for slot in range(RUNS_PER_DAY)]


# -------------------------------------------------------------------- profile

@dataclass
class Profile:
    version: int = PROGRESS_VERSION
    runs: int = 0
    achievements: List[str] = field(default_factory=list)
    best_net: float = 0.0
    best_tier_cleared: int = 0
    #: the date (YYYYMMDD) the ranked slate below belongs to
    daily_day: Optional[int] = None
    #: one entry per ranked run finished today, at most RUNS_PER_DAY of them
    daily_runs: List[Dict[str, Any]] = field(default_factory=list)
    #: best daily total ever posted, and the day it happened
    best_daily: float = 0.0
    best_daily_day: Optional[int] = None
    #: wins banked per coin class, which is what gear levels are made of
    gear_wins: Dict[str, int] = field(default_factory=dict)
    #: what the player calls each piece, if they have renamed it
    gear_names: Dict[str, str] = field(default_factory=dict)
    updated_at: float = 0.0

    # ----------------------------------------------------------- derived view

    @property
    def unlocked_perks(self) -> List[Perk]:
        earned = set(self.achievements)
        return [p for p in PERKS if p.unlocked_by in earned]

    @property
    def gear_levels(self) -> Dict[str, int]:
        from .gear import levels_from_wins
        return levels_from_wins(self.gear_wins)

    @property
    def max_tier(self) -> int:
        """Tier 1 always; each cleared tier opens the next."""
        return max(1, min(len(TIERS), self.best_tier_cleared + 1))

    def has(self, key: str) -> bool:
        return key in self.achievements

    # --------------------------------------------------------- the daily slate

    def roll_day(self, day: Optional[int] = None) -> int:
        """Point the profile at today's slate, clearing yesterday's.

        Nothing is lost by missing a day - the old slate is simply not today's
        any more. Call this before reading anything about the ranked day.
        """
        day = daily_seed() if day is None else day
        if self.daily_day != day:
            self.daily_day, self.daily_runs = day, []
        return day

    def runs_today(self, day: Optional[int] = None) -> List[Dict[str, Any]]:
        return list(self.daily_runs) if self.daily_day == (daily_seed() if day is None else day) else []

    def next_slot(self, day: Optional[int] = None) -> Optional[int]:
        """Which ranked run is next, or None when all three are spent."""
        done = {r.get("slot") for r in self.runs_today(day)}
        for slot in range(RUNS_PER_DAY):
            if slot not in done:
                return slot
        return None

    def daily_total(self, day: Optional[int] = None) -> float:
        return sum(float(r.get("points", 0.0)) for r in self.runs_today(day))

    def to_dict(self) -> Dict[str, Any]:
        return {"version": self.version, "runs": self.runs,
                "achievements": list(self.achievements), "best_net": self.best_net,
                "best_tier_cleared": self.best_tier_cleared,
                "daily_day": self.daily_day, "daily_runs": list(self.daily_runs),
                "best_daily": self.best_daily, "best_daily_day": self.best_daily_day,
                "gear_wins": dict(self.gear_wins),
                "gear_names": dict(self.gear_names),
                "updated_at": self.updated_at}

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Profile":
        # Older profiles predate ranked runs and gear. Their achievements were
        # still earned, so they migrate rather than being thrown away - losing
        # somebody's unlocks to a format change is the one thing a profile must
        # not do. Anything missing simply starts at zero.
        if not isinstance(data, dict) or data.get("version") not in (1, 2, PROGRESS_VERSION):
            return Profile()          # a profile is a reward, never a blocker
        known = {a.key for a in ACHIEVEMENTS}
        runs = data.get("daily_runs", [])
        return Profile(
            runs=int(data.get("runs", 0)),
            achievements=[k for k in data.get("achievements", []) if k in known],
            best_net=float(data.get("best_net", 0.0)),
            best_tier_cleared=int(data.get("best_tier_cleared", 0)),
            daily_day=data.get("daily_day"),
            daily_runs=[r for r in runs if isinstance(r, dict)] if isinstance(runs, list) else [],
            best_daily=float(data.get("best_daily", 0.0)),
            best_daily_day=data.get("best_daily_day"),
            gear_wins={k: int(v) for k, v in (data.get("gear_wins") or {}).items()
                       if k in CLASSES},
            gear_names={k: str(v)[:22] for k, v in (data.get("gear_names") or {}).items()
                        if k in CLASSES and str(v).strip()},
            updated_at=float(data.get("updated_at", 0.0)),
        )


def profile_path() -> Path:
    from .save import home
    return home() / "profile.json"


def read_profile() -> Profile:
    path = profile_path()
    if not path.exists():
        return Profile()
    try:
        return Profile.from_dict(json.loads(path.read_text()))
    except (json.JSONDecodeError, OSError, ValueError):
        return Profile()              # never let a bad profile block a game


def write_profile(profile: Profile) -> Profile:
    profile.updated_at = time.time()
    path = profile_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(profile.to_dict(), indent=1))
    tmp.replace(path)
    return profile


def daily_seed(when: Optional[float] = None) -> int:
    """Today's date as YYYYMMDD - the key the ranked slate hangs on.

    Derived from the date alone, so the same day always deals the same markets
    to everybody. Not a streak: miss a day and nothing is taken away, there is
    simply a new slate waiting.
    """
    stamp = time.strftime("%Y%m%d", time.gmtime(when if when is not None else time.time()))
    return int(stamp)


def award(profile: Profile, game) -> List[Achievement]:
    """Score a finished run against the profile. Returns what was newly earned."""
    if not counts_for_progress(game):
        return []
    earned = []
    for achievement in ACHIEVEMENTS:
        if achievement.key in profile.achievements:
            continue
        try:
            if achievement.test(game):
                profile.achievements.append(achievement.key)
                earned.append(achievement)
        except Exception:
            continue                  # a broken check must never end a run
    profile.runs += 1
    profile.best_net = max(profile.best_net, game.final_score())
    tier = getattr(game, "tier", 1)
    if game.final_score() > 2_000 and tier > profile.best_tier_cleared:
        profile.best_tier_cleared = tier
    return earned


def record_daily(profile: Profile, game, slot: int,
                 day: Optional[int] = None) -> Dict[str, Any]:
    """Log a finished ranked run against today's slate. Returns the entry.

    Re-recording a slot is ignored rather than overwriting: the point of three
    ranked runs is that each is played once, and the way that quietly breaks is
    a crash-and-retry posting a second, better result for the same market.
    """
    day = profile.roll_day(day)
    points = run_points(game)
    if not counts_for_progress(game):
        # the slot is not spent either, so an ineligible run costs nothing
        return {"slot": int(slot), "points": 0.0, "net": round(game.final_score(), 2),
                "grade": UNRANKED_GRADE, "tier": int(getattr(game, "tier", 1)),
                "at": time.time()}
    entry = {"slot": int(slot), "points": round(points, 2),
             "net": round(game.final_score(), 2), "grade": grade(points),
             "tier": int(getattr(game, "tier", 1)), "at": time.time()}
    if any(r.get("slot") == slot for r in profile.daily_runs):
        return entry
    profile.daily_runs.append(entry)
    profile.daily_runs.sort(key=lambda r: r.get("slot", 0))
    total = profile.daily_total(day)
    if total > profile.best_daily:
        profile.best_daily, profile.best_daily_day = total, day
    return entry
