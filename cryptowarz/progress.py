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

Deliberately absent: streak counters that punish a missed day, timers that gate
play, and anything that manufactures urgency. This is a game you own - it
should be worth returning to, not costly to leave.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

PROGRESS_VERSION = 1


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
    Tier(1, "Off Peak",   "The standard thirty days.",           5_500.0, 25_000.0, 1.00, 30),
    Tier(2, "Rush Hour",  "A bigger loan and more eyes on you.", 6_800.0, 21_000.0, 1.25, 30),
    Tier(3, "Track Work", "Deeper in, carrying less.",           7_800.0, 17_000.0, 1.50, 30),
    Tier(4, "Last Train", "Four fewer days to do it in.",        7_800.0, 15_000.0, 1.60, 26),
    Tier(5, "Blackout",   "Everything at once.",                 9_000.0, 13_000.0, 1.80, 26),
]
TIER_BY_LEVEL = {t.level: t for t in TIERS}


# -------------------------------------------------------------------- profile

@dataclass
class Profile:
    version: int = PROGRESS_VERSION
    runs: int = 0
    achievements: List[str] = field(default_factory=list)
    best_net: float = 0.0
    best_tier_cleared: int = 0
    daily_seed: Optional[int] = None
    daily_net: Optional[float] = None
    updated_at: float = 0.0

    # ----------------------------------------------------------- derived view

    @property
    def unlocked_perks(self) -> List[Perk]:
        earned = set(self.achievements)
        return [p for p in PERKS if p.unlocked_by in earned]

    @property
    def max_tier(self) -> int:
        """Tier 1 always; each cleared tier opens the next."""
        return max(1, min(len(TIERS), self.best_tier_cleared + 1))

    def has(self, key: str) -> bool:
        return key in self.achievements

    def to_dict(self) -> Dict[str, Any]:
        return {"version": self.version, "runs": self.runs,
                "achievements": list(self.achievements), "best_net": self.best_net,
                "best_tier_cleared": self.best_tier_cleared,
                "daily_seed": self.daily_seed, "daily_net": self.daily_net,
                "updated_at": self.updated_at}

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Profile":
        if not isinstance(data, dict) or data.get("version") != PROGRESS_VERSION:
            return Profile()          # a profile is a reward, never a blocker
        known = {a.key for a in ACHIEVEMENTS}
        return Profile(
            runs=int(data.get("runs", 0)),
            achievements=[k for k in data.get("achievements", []) if k in known],
            best_net=float(data.get("best_net", 0.0)),
            best_tier_cleared=int(data.get("best_tier_cleared", 0)),
            daily_seed=data.get("daily_seed"),
            daily_net=data.get("daily_net"),
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
    """One shared run per calendar day - a reason to come back tomorrow.

    Derived from the date alone, so the same day always deals the same market.
    Not a streak: miss a day and nothing is taken away, there is simply a new
    one waiting.
    """
    stamp = time.strftime("%Y%m%d", time.gmtime(when if when is not None else time.time()))
    return int(stamp)


def award(profile: Profile, game) -> List[Achievement]:
    """Score a finished run against the profile. Returns what was newly earned."""
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
