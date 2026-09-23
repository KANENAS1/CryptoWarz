"""Somebody is standing in front of you, and the game stops to ask.

Every other bad thing in this game happens *to* you: the raid takes a third of
the bag, the drainer takes what it takes, and you read about it afterwards.
That is fine for weather - a market that moves without asking is the point -
but it is a poor way to handle a person. A person blocking the stairs is a
*decision*, and a decision is the only thing a game can actually be made of.

So a stickup does not resolve. It waits. The run stops dead until you answer,
and until you do you cannot trade, cannot travel, cannot spin a wheel and
cannot quietly reload - the standoff rides the save like everything else.

Three ideas hold the feature up.

**Every option is bad in a different way.** Running is free and usually works,
but not when you are carrying the whole bag - a full wallet is slow, and that
is the point: the richer the run, the worse the odds of simply leaving.
Fighting bare-handed is a coin flip that can cost you a day. Paying is certain
and expensive. A weapon turns the fight from a gamble into a favourite - and
costs you something else entirely, because a man carrying a bat is somebody the
SEC notices.

**What you did last time changes what happens next.** Standing your ground
builds a reputation that makes the next one think twice; paying up builds one
that invites them. That is the story the run tells: it is not written anywhere,
it is just the consequence of your own answers, and it is the reason two runs
with the same seed can read completely differently.

**Nothing here can take the run off you outright.** The worst outcome is a
mauling: a slice of the bag and a day in the hospital. There is no death, no
game over, no unrecoverable state - the same rule that stops events stripping
your last fare. A game that can end without a decision being available is not
asking you anything.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


# --------------------------------------------------------------- weapons

@dataclass(frozen=True)
class Weapon:
    key: str
    name: str
    blurb: str
    #: how much it moves your odds of winning a fight, 0.0 - 1.0
    edge: float
    #: extra weight on the SEC's dice while you are carrying it. The trade the
    #: whole armoury is built on: what makes a mugger reconsider is exactly
    #: what makes a federal agent look twice.
    heat: float
    #: chance it breaks, is dropped, or has to be left behind after a fight
    breaks: float
    #: what a shop wants for it. Zero means it is not sold anywhere - the only
    #: way to hold one is to find it.
    price: float


WEAPONS: List[Weapon] = [
    Weapon("brick", "Half a Brick",
           "It was holding a door open. Now it is holding your nerve together.",
           edge=0.12, heat=0.02, breaks=0.45, price=0.0),
    Weapon("pipe", "Length of Pipe",
           "Scaffolding offcut. Heavier than it looks, which is the entire idea.",
           edge=0.18, heat=0.06, breaks=0.20, price=400.0),
    Weapon("cutter", "Box Cutter",
           "Nobody wants to find out whether you would. That is usually enough.",
           edge=0.26, heat=0.14, breaks=0.10, price=1_200.0),
    Weapon("bat", "Louisville Slugger",
           "You tell people you play softball. Nobody has ever believed you.",
           edge=0.33, heat=0.20, breaks=0.06, price=3_200.0),
    Weapon("taser", "Stun Gun",
           "Legal in some states. This is not one of them, and it is the good kind.",
           edge=0.42, heat=0.28, breaks=0.14, price=9_000.0),
]
WEAPON_BY_KEY: Dict[str, Weapon] = {w.key: w for w in WEAPONS}
#: what a shop will actually stock; the brick you have to come across
FOR_SALE: Tuple[str, ...] = tuple(w.key for w in WEAPONS if w.price > 0)


def weapon_of(key: Optional[str]) -> Optional[Weapon]:
    return WEAPON_BY_KEY.get(key) if key else None


def carry_heat(game) -> float:
    """Extra raid weight from whatever is in your coat."""
    weapon = weapon_of(getattr(game, "weapon", None))
    return weapon.heat if weapon else 0.0


# ------------------------------------------------------------ reputation

#: How far a reputation can run in either direction. Kept short on purpose: a
#: number that climbs forever ends the feature, because a player who has won
#: six fights would stop being asked anything.
REP_MAX = 3
#: What one point of standing is worth, per side.
REP_ENCOUNTER = 0.06      # on the chance of being jumped at all
REP_ODDS = 0.05           # on your odds once you are


def rep_of(game) -> int:
    return max(-REP_MAX, min(REP_MAX, int(game.stats.get("rep", 0))))


def bump_rep(game, delta: int) -> None:
    game.stats["rep"] = max(-REP_MAX, min(REP_MAX, rep_of(game) + delta))


# ------------------------------------------------------------- the odds

#: A full wallet is a slow wallet. This is the sharpest idea in the encounter:
#: the run that most needs to walk away is the run least able to.
MAX_LOAD_PENALTY = 0.28


def load_penalty(game) -> float:
    """How much what you are carrying slows you down, 0.0 - MAX_LOAD_PENALTY."""
    capacity = max(1.0, game.player.capacity)
    used = min(1.0, game.player.used_capacity / capacity)
    return MAX_LOAD_PENALTY * used


#: Base chances before anything is applied. Running is the default answer and
#: is priced like one: usually right, never certain, and worst when it matters.
RUN_BASE = 0.62
FIGHT_BASE = 0.34


def odds(game, choice: str) -> float:
    """The real chance a choice comes off, 0.0 - 1.0. What the UI shows."""
    rep = rep_of(game)
    if choice == "run":
        chance = RUN_BASE - load_penalty(game) + rep * REP_ODDS
    elif choice in ("fight", "weapon"):
        chance = FIGHT_BASE + rep * REP_ODDS
        if choice == "weapon":
            weapon = weapon_of(getattr(game, "weapon", None))
            if weapon is None:
                return 0.0
            chance += weapon.edge
        # gear luck tilts a coin-flip that was already being flipped
        chance += game.luck * 0.5
    else:
        return 1.0                         # paying always works. That is the deal.
    return max(0.05, min(0.95, chance))


# ------------------------------------------------------------ the script

@dataclass(frozen=True)
class Kind:
    key: str
    title: str
    #: what they say they want
    opening: Tuple[str, ...]
    #: multiplier on what it costs you when it goes wrong
    severity: float
    #: whether a weapon is a sane answer to this
    armable: bool


KINDS: List[Kind] = [
    Kind("stickup", "SOMEBODY BLOCKS THE STAIRS",
         ("A man steps out of the stairwell at {station} and does not move. "
          "\"Phone. Wallet. Whatever's in the bag.\"",
          "Two of them, one either side of the turnstile at {station}. The one "
          "on the left is doing the talking and the one on the right is why.",
          "He has been on the platform at {station} since you got off, and now "
          "he is close enough that you can smell the cigarettes."),
         severity=1.0, armable=True),
    Kind("followed", "YOU WERE FOLLOWED OFF THE TRAIN",
         ("Somebody got off at {station} when you did, and took the same stairs, "
          "and is now standing closer than anybody stands by accident.",
          "He rode three cars down and got off at {station} behind you. He is "
          "not looking at his phone. Nobody on this platform is not looking at "
          "their phone.",
          "The kid who was watching your screen on the ride gets off at "
          "{station} too, and he has friends."),
         severity=0.85, armable=True),
]
KIND_BY_KEY: Dict[str, Kind] = {k.key: k for k in KINDS}


# ------------------------------------------------------- opening a standoff

def open_standoff(game, kind_key: str = "stickup") -> List[str]:
    """Put somebody in front of the player and stop the run until answered."""
    kind = KIND_BY_KEY.get(kind_key, KINDS[0])
    line = game.rng.choice(kind.opening).format(station=game.station.name)
    game.pending = {
        "kind": kind.key,
        "day": game.day,
        "station": game.station.name,
        "line": line,
    }
    game.stats["standoffs"] = int(game.stats.get("standoffs", 0)) + 1
    return [line]


def choices(game) -> List[Dict[str, object]]:
    """What the player may do, with the true odds on each. Never a guess."""
    pending = getattr(game, "pending", None)
    if not pending:
        return []
    kind = KIND_BY_KEY.get(str(pending.get("kind")), KINDS[0])
    out: List[Dict[str, object]] = [
        {"key": "run", "label": "RUN", "odds": odds(game, "run"),
         "note": "Down the platform and out. What you are carrying slows you down."},
        {"key": "fight", "label": "SWING FIRST", "odds": odds(game, "fight"),
         "note": "Bare hands. It is a coin flip and the coin is not yours."},
    ]
    weapon = weapon_of(getattr(game, "weapon", None))
    if weapon and kind.armable:
        out.append({"key": "weapon", "label": f"USE THE {weapon.name.upper()}",
                    "odds": odds(game, "weapon"),
                    "note": f"{weapon.name}. It might not survive the night either."})
    out.append({"key": "pay", "label": "HAND IT OVER", "odds": 1.0,
                "note": f"Give up {pay_cost(game):,.0f} and walk away whole. "
                        f"Word gets around that you do."})
    return out


def pay_cost(game) -> float:
    """What buying your way out costs: a slice of the cash, with a floor.

    Proportional so it stays a real decision at both ends of a run - a flat
    number is pocket change on day thirty and the whole game on day two.
    """
    pending = getattr(game, "pending", None)
    kind = KIND_BY_KEY.get(str((pending or {}).get("kind")), KINDS[0])
    return max(150.0, game.player.cash * 0.22 * kind.severity)


# ----------------------------------------------------------- the outcome

#: What a robbery takes, as a share of cash and of the bag. Deliberately in the
#: same range as a raid: the point of a standoff is the choice, not a new and
#: bigger hammer.
TAKE_CASH = (0.30, 0.60)
TAKE_BAG = (0.10, 0.26)
#: A beating costs a day. It is the only outcome here that touches the clock,
#: which is what makes swinging first feel like something.
HOSPITAL_CHANCE = 0.35


def _rob(game, scale: float) -> Tuple[float, float]:
    """Take cash and a slice of the bag. Returns (cash taken, cost basis taken)."""
    from .events import _confiscate, _take_cash

    cash_share = game.rng.uniform(*TAKE_CASH) * scale
    bag_share = min(0.9, game.rng.uniform(*TAKE_BAG) * scale)
    cash = _take_cash(game, game.player.cash * cash_share)
    bag = _confiscate(game, bag_share)
    return cash, bag


def _loss_line(cash: float, bag: float) -> str:
    if cash > 0 and bag > 0:
        return f"${cash:,.2f} and ${bag:,.2f} of the bag, at cost."
    if cash > 0:
        return f"${cash:,.2f}."
    if bag > 0:
        return f"${bag:,.2f} of the bag, at cost."
    return "nothing, because you had nothing. Small mercies."


def resolve(game, choice: str) -> List[str]:
    """Answer the standoff. Clears it either way - there is no third option."""
    pending = getattr(game, "pending", None)
    if not pending:
        raise ValueError("nobody is in front of you")
    kind = KIND_BY_KEY.get(str(pending.get("kind")), KINDS[0])
    valid = {c["key"] for c in choices(game)}
    if choice not in valid:
        raise ValueError(f"you can't do that here; try {', '.join(sorted(valid))}")

    game.pending = None                   # answered, whatever happens next
    weapon = weapon_of(getattr(game, "weapon", None))
    out: List[str] = []

    if choice == "pay":
        from .events import _take_cash
        paid = _take_cash(game, pay_cost(game))
        bump_rep(game, -1)
        out.append(f"You hand it over. ${paid:,.2f}, and he counts it in front of "
                   f"you to make the point. Word gets around.")
        return _finish(game, out)

    won = game.rng.random() < odds(game, choice)

    if choice == "run":
        if won:
            out.append(game.rng.choice([
                "You go down the platform and through the crowd at the far stairs. "
                "Nobody follows you up. Your heart does not get the message for "
                "another ten minutes.",
                "You move before he finishes the sentence. Two flights, one turnstile, "
                "and a street you do not recognise. Everything you had, you still have.",
                "He is not as interested as he looked. You are three blocks away "
                "before you slow down.",
            ]))
            return _finish(game, out)
        cash, bag = _rob(game, kind.severity)
        out.append("You get four steps. The bag is the problem - it always is.")
        out.append(f"They take {_loss_line(cash, bag)}")
        return _finish(game, out)

    # a fight, with or without something in your hand
    if won:
        bump_rep(game, +1)
        if choice == "weapon" and weapon:
            out.append(game.rng.choice([
                f"You bring the {weapon.name.lower()} out and the conversation ends. "
                f"He decides, quickly, that this is not his night.",
                f"One swing. It does not connect and it does not have to - "
                f"he is already going the other way.",
            ]))
            if game.rng.random() < weapon.breaks:
                game.weapon = None
                out.append(f"The {weapon.name.lower()} does not survive the night. "
                           f"You leave it where it lands.")
        else:
            out.append(game.rng.choice([
                "You swing first, which is the only part of this you get to choose. "
                "He goes down the stairs the fast way and does not come back up.",
                "It is short, ugly and entirely unlike the movies. You are still "
                "standing at the end of it, and he is not.",
            ]))
        out.extend(_spoils(game))
        return _finish(game, out)

    bump_rep(game, -1)
    if choice == "weapon" and weapon:
        game.weapon = None
        out.append(f"He takes the {weapon.name.lower()} off you, which is worse "
                   f"than not having had one.")
    cash, bag = _rob(game, kind.severity * 1.25)
    out.append(f"It goes badly. They take {_loss_line(cash, bag)}")
    if game.rng.random() < HOSPITAL_CHANCE:
        game.lose_a_day()
        out.append("You come round on a bench with a day gone and the Shark's "
                   "clock still running.")
    return _finish(game, out)


def _spoils(game) -> List[str]:
    """What standing your ground is occasionally worth."""
    roll = game.rng.random()
    if roll < 0.30:
        found = 80.0 + game.rng.random() * 620.0
        game.player.cash += found
        return [f"He leaves ${found:,.2f} on the platform. You are not too proud."]
    if roll < 0.44 and not getattr(game, "weapon", None):
        dropped = game.rng.choice([w for w in WEAPONS if w.price <= 3_200.0])
        game.weapon = dropped.key
        return [f"He drops what he was holding. {dropped.name}. It is yours now."]
    return []


def _finish(game, out: List[str]) -> List[str]:
    for line in out:
        game.say(line)
    return out


def best_choice(game) -> Optional[str]:
    """The answer with the best odds, for bots and simulations.

    Not used by the game itself - a standoff is the player's to answer. It
    exists so that the balance bots and the parity harness face the same
    decisions a player does rather than being exempt from them, which is the
    only way the measured numbers stay honest once encounters exist.
    """
    options = choices(game)
    if not options:
        return None
    # paying always "works", so a bot that picked purely on odds would pay
    # every time and measure a game nobody plays; it is the fallback, not the
    # favourite
    fighting = [c for c in options if c["key"] != "pay"]
    best = max(fighting, key=lambda c: float(c["odds"]))
    return str(best["key"]) if float(best["odds"]) >= 0.45 else "pay"
