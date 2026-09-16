"""Saving a run, and remembering the ones that ended.

The whole design turns on one decision: **the random state is saved too**.

A game full of SEC raids and rug pulls invites savescumming - quit before a bad
outcome, reload, take the ride again and hope for different dice. If reloading
rerolled, the risk in this game would be optional, and a game where the risk is
optional has no decisions in it. So a save restores the generator exactly, and
reloading replays the same day with the same result. The only way past a bad
roll is to live with it.

That also makes a save a faithful snapshot rather than an approximation: the
market levels, the current prices and the pending shock all come back as they
were, because regenerating them would consume the generator and desynchronise
everything after.

Files live in ~/.cryptowarz (override with CRYPTOWARZ_HOME). Saves are plain
JSON, versioned, and refused rather than guessed at when the version does not
match - silently loading a save the rules have moved past would corrupt a run
in ways that look like bugs.
"""

from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .coins import COINS
from .market import Market, MarketState
from .stations import station

#: Bump when the shape changes in a way older saves cannot satisfy.
SAVE_VERSION = 1
MAX_SCORES = 25


class SaveError(RuntimeError):
    """A save exists but cannot be used."""


def home() -> Path:
    return Path(os.environ.get("CRYPTOWARZ_HOME", Path.home() / ".cryptowarz"))


def save_path() -> Path:
    return home() / "save.json"


def scores_path() -> Path:
    return home() / "scores.json"


# ------------------------------------------------------------------ encoding

def _encode_rng(rng: random.Random) -> Dict[str, Any]:
    version, internal, gauss_next = rng.getstate()
    return {"version": version, "state": list(internal), "gauss_next": gauss_next}


def _decode_rng(data: Dict[str, Any]) -> random.Random:
    rng = random.Random()
    rng.setstate((data["version"], tuple(data["state"]), data["gauss_next"]))
    return rng


def to_dict(game) -> Dict[str, Any]:
    p = game.player
    return {
        "save_version": SAVE_VERSION,
        "saved_at": time.time(),
        "seed": game.seed,
        "tier": game.tier,
        "perk": game.perk,
        # which ranked run of today this is, or null for practice. Added after
        # version 1 shipped and read with a default, so an in-progress save from
        # the older build still loads - it simply resumes as practice.
        "daily_slot": getattr(game, "daily_slot", None),
        # stations is a set in memory; JSON needs a list, and the reload
        # converts it back so achievement checks keep working after a resume
        "stats": {**game.stats, "stations": sorted(game.stats.get("stations", []))},
        "day": game.day,
        "finished": game.finished,
        "station": game.station.name,
        "player": {
            "cash": p.cash, "debt": p.debt, "vault": p.vault,
            "capacity": p.capacity, "vpn": p.vpn,
            "wallet": {sym: {"qty": h.qty, "cost": h.cost}
                       for sym, h in p.wallet.items() if h.qty > 0 or h.cost > 0},
        },
        "levels": dict(game.state.levels),
        # prices and the pending shock are stored rather than regenerated:
        # regenerating would draw from the generator and desynchronise the run
        "market": {
            "prices": dict(game.market.prices),
            "shock": None if not game.market.shock else {
                "symbol": game.market.shock.symbol,
                "headline": game.market.shock.headline,
                "factor": game.market.shock.factor,
            },
        },
        "rng": _encode_rng(game.rng),
        "log": list(game.log)[-40:],
    }


def from_dict(data: Dict[str, Any]):
    from .game import Game, Holding    # imported here to avoid a cycle

    found = data.get("save_version")
    if found != SAVE_VERSION:
        raise SaveError(
            f"that save is version {found}, and this build reads version {SAVE_VERSION}. "
            f"Start a new run - loading it anyway would corrupt it in ways that look like bugs."
        )

    game = Game(seed=data.get("seed"), tier=int(data.get("tier", 1)),
                perk=data.get("perk"))
    slot = data.get("daily_slot")
    game.daily_slot = None if slot is None else int(slot)
    game.is_daily = game.daily_slot is not None
    stats = data.get("stats")
    if stats:
        game.stats = {**stats, "stations": set(stats.get("stations", []))}
    # god mode lives in stats, so it reloads with the run rather than needing a
    # save key of its own - and a reload cannot be used to shake it off
    game.god_mode = bool(game.stats.get("god_mode", False))
    game.rng = _decode_rng(data["rng"])
    game.day = int(data["day"])
    game.finished = bool(data.get("finished", False))
    game.station = station(data["station"])
    game.log = list(data.get("log", []))

    p = game.player
    saved = data["player"]
    p.cash = float(saved["cash"])
    p.debt = float(saved["debt"])
    p.vault = float(saved["vault"])
    p.capacity = float(saved["capacity"])
    p.vpn = int(saved.get("vpn", 0))
    p.wallet = {sym: Holding(qty=float(h["qty"]), cost=float(h["cost"]))
                for sym, h in saved.get("wallet", {}).items()}

    state = MarketState(random.Random(0))
    known = {c.symbol for c in COINS}
    missing = known - set(data["levels"])
    if missing:
        raise SaveError(f"that save predates {', '.join(sorted(missing))}. Start a new run.")
    state.levels = {sym: float(v) for sym, v in data["levels"].items() if sym in known}
    game.state = state

    shock_data = data["market"].get("shock")
    shock = None
    if shock_data:
        from .market import Shock
        shock = Shock(shock_data["symbol"], shock_data["headline"], float(shock_data["factor"]))
    game.market = Market(game.station,
                         {sym: float(v) for sym, v in data["market"]["prices"].items()},
                         shock)
    return game


# ------------------------------------------------------------------- on disk

def write_save(game) -> Path:
    path = save_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # write-then-rename, so a crash mid-write cannot leave a half a save behind
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(to_dict(game), indent=1))
    tmp.replace(path)
    return path


def read_save():
    path = save_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        raise SaveError(f"the save file is unreadable ({exc}). Start a new run.") from exc
    return from_dict(data)


def has_save() -> bool:
    return save_path().exists()


def clear_save() -> None:
    try:
        save_path().unlink()
    except FileNotFoundError:
        pass


# -------------------------------------------------------------------- scores

@dataclass
class Score:
    net_worth: float
    day: int
    verdict: str
    finished_at: float
    seed: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"net_worth": self.net_worth, "day": self.day, "verdict": self.verdict,
                "finished_at": self.finished_at, "seed": self.seed}


def read_scores() -> List[Score]:
    path = scores_path()
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return []          # a corrupt score file is never worth blocking a game over
    out = []
    for row in raw if isinstance(raw, list) else []:
        try:
            out.append(Score(float(row["net_worth"]), int(row["day"]), str(row["verdict"]),
                             float(row.get("finished_at", 0.0)), row.get("seed")))
        except (KeyError, TypeError, ValueError):
            continue       # skip a bad row rather than lose every good one
    out.sort(key=lambda s: s.net_worth, reverse=True)
    return out


def record_score(game) -> List[Score]:
    from .progress import counts_for_progress

    scores = read_scores()
    if not counts_for_progress(game):
        return scores          # a god-mode run is a toy, not a result
    scores.append(Score(game.final_score(), min(game.day, 30), game.verdict(),
                        time.time(), game.seed))
    scores.sort(key=lambda s: s.net_worth, reverse=True)
    scores = scores[:MAX_SCORES]
    path = scores_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps([s.to_dict() for s in scores], indent=1))
    tmp.replace(path)
    return scores


def best_score() -> Optional[Score]:
    scores = read_scores()
    return scores[0] if scores else None
