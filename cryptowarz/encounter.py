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
    #: whether a weapon is a sane answer to this. It is not, against a badge:
    #: the game declines to offer the option rather than offering it and
    #: punishing it, because a trap you can only learn by falling into is a
    #: worse teacher than a door that was never there.
    armable: bool
    #: which answers this one accepts, in the order they are shown
    options: Tuple[str, ...] = ("run", "fight", "weapon", "pay")


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
KINDS.extend([
    Kind("collector", "THE SHARK SENT SOMEBODY",
         ("The large man from the platform at {station} is not large by accident, "
          "and he knows your name, and he would like some of it back.",
          "\"He says you've been busy.\" The associate does not sit down. Nobody "
          "at {station} is looking at either of you, very deliberately.",
          "He is waiting at the bottom of the stairs at {station} with his hands "
          "where you can see them, which is somehow worse."),
         severity=1.0, armable=True,
         options=("pay", "run", "fight", "weapon")),
    Kind("badge", "FEDERAL AGENTS AT THE TURNSTILE",
         ("Two of them at the {station} turnstile, and they were waiting for you "
          "rather than for a train.",
          "The suit at {station} shows you something in a wallet and asks you to "
          "step to one side. He is not really asking.",
          "They come down both stairwells at {station} at once, which tells you "
          "how long they have known."),
         severity=1.0, armable=False,
         options=("comply", "lawyer", "run")),
])
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


#: What a lawyer costs, and what he is worth. Certain, expensive, and the only
#: answer to a badge that does not involve running: you are buying the seizure
#: down rather than betting on getting away with it.
LAWYER_SHARE = 0.18
LAWYER_MIN = 800.0
LAWYER_SAVES = 0.55


def lawyer_cost(game) -> float:
    return max(LAWYER_MIN, game.player.cash * LAWYER_SHARE)


def collector_demand(game) -> float:
    """What the Shark's man came for: a quarter of the debt, if you have it."""
    from .game import SUBWAY_FARE

    return min(max(0.0, game.player.cash - SUBWAY_FARE), game.player.debt * 0.25)


def choices(game) -> List[Dict[str, object]]:
    """What the player may do, with the true odds on each. Never a guess.

    Every option a kind accepts is built here, so the terminal, the phone and
    the tests all read one list. A kind that does not accept an answer simply
    does not show it - there is no hidden option and no option that is shown
    and then refused.
    """
    pending = getattr(game, "pending", None)
    if not pending:
        return []
    kind = KIND_BY_KEY.get(str(pending.get("kind")), KINDS[0])
    weapon = weapon_of(getattr(game, "weapon", None))
    built: Dict[str, Dict[str, object]] = {
        "run": {"key": "run", "label": "RUN", "odds": odds(game, "run"),
                "note": "Down the platform and out. What you are carrying slows you down."},
        "fight": {"key": "fight", "label": "SWING FIRST", "odds": odds(game, "fight"),
                  "note": "Bare hands. It is a coin flip and the coin is not yours."},
        "pay": {"key": "pay", "label": "HAND IT OVER", "odds": 1.0,
                "note": f"Give up {pay_cost(game):,.0f} and walk away whole. "
                        f"Word gets around that you do."},
        "comply": {"key": "comply", "label": "HANDS WHERE THEY CAN SEE THEM",
                   "odds": 1.0,
                   "note": "Let them take what they came for. Nothing else happens "
                           "to you today."},
    }
    if weapon and kind.armable:
        built["weapon"] = {"key": "weapon", "label": f"USE THE {weapon.name.upper()}",
                           "odds": odds(game, "weapon"),
                           "note": f"{weapon.name}. It might not survive the night either."}
    if kind.key == "collector":
        demand = collector_demand(game)
        built["pay"] = {"key": "pay", "label": "PAY HIM", "odds": 1.0,
                        "note": f"{demand:,.0f} off the cash and the same off the debt. "
                                f"It is a payment, not a robbery."}
        built["run"] = {**built["run"],
                        "note": "You keep the money. The Shark adds a fee for the "
                                "inconvenience, and he does not forget."}
        for key in ("fight", "weapon"):
            if key in built:
                built[key] = {**built[key],
                              "note": built[key]["note"] + " The debt stands either way."}
    if kind.key == "badge":
        built["lawyer"] = {"key": "lawyer", "label": "CALL A LAWYER", "odds": 1.0,
                           "note": f"{lawyer_cost(game):,.0f} on a retainer, and they "
                                   f"leave with {1 - LAWYER_SAVES:.0%} of what they came "
                                   f"for. Certain, and it hurts."}
        built["run"] = {**built["run"],
                        "note": "From federal agents, in a subway station. If it works "
                                "you keep everything. They will remember you either way."}
    return [built[key] for key in kind.options if key in built]


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

    if kind.key == "collector":
        return _collector(game, kind, choice, weapon)
    if kind.key == "badge":
        return _badge(game, kind, choice)

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


#: What refusing the Shark's man costs on the loan. He does not take it
#: personally; he takes it out of the principal.
SHARK_FEE_RAN = 0.08
SHARK_FEE_FOUGHT = 0.13


def _collector(game, kind, choice, weapon) -> List[str]:
    """The Shark's associate. The one encounter where paying is the *good* end.

    What he takes is a payment - it comes off the debt as well as the cash - so
    refusing him is not saving money, it is declining to pay down a loan that
    compounds at ten per cent a day, and being charged for the privilege. That
    is the whole decision, and it is the opposite shape to a mugging.
    """
    from .events import _take_cash

    out: List[str] = []
    demand = collector_demand(game)

    if choice == "pay":
        if demand < 50:
            out.append("You turn out your pockets. He counts what is there, which "
                       "does not take long, and tells you he will find you again.")
            return _finish(game, out)
        taken = _take_cash(game, demand)
        game.player.debt = max(0.0, game.player.debt - taken)
        out.append(f"You pay him ${taken:,.2f}. It comes straight off the loan, "
                   f"which is the only good thing anybody can say about it.")
        return _finish(game, out)

    won = game.rng.random() < odds(game, choice)

    if choice == "run":
        if won:
            game.player.debt *= (1.0 + SHARK_FEE_RAN)
            out.append("You lose him on the mezzanine. Nothing leaves your pocket "
                       "today.")
            out.append(f"By the evening the loan has grown {SHARK_FEE_RAN:.0%}. "
                       f"He made a phone call before he lost you.")
            return _finish(game, out)
        taken = _take_cash(game, demand * 1.2)
        game.player.debt = max(0.0, game.player.debt - taken)
        out.append(f"He is faster than he looks. ${taken:,.2f}, off the cash and "
                   f"off the loan, and he keeps the difference for his trouble.")
        return _finish(game, out)

    # swinging at the Shark's man
    if won:
        bump_rep(game, +1)
        if choice == "weapon" and weapon:
            out.append(f"The {weapon.name.lower()} settles it. He goes back up the "
                       f"stairs with a message you did not write down.")
            if game.rng.random() < weapon.breaks:
                game.weapon = None
                out.append(f"You leave the {weapon.name.lower()} in a bin two blocks "
                           f"away. It was that or explain it.")
        else:
            out.append("You put him on the floor of the mezzanine. People step "
                       "around both of you without breaking stride.")
        game.player.debt *= (1.0 + SHARK_FEE_FOUGHT)
        out.append(f"The Shark hears about it within the hour and adds "
                   f"{SHARK_FEE_FOUGHT:.0%} to what you owe. He can afford to be "
                   f"philosophical.")
        return _finish(game, out)

    bump_rep(game, -1)
    if choice == "weapon" and weapon:
        game.weapon = None
        out.append(f"He takes the {weapon.name.lower()} off you before you have "
                   f"finished deciding to use it.")
    taken = _take_cash(game, demand * 1.35)
    game.player.debt = max(0.0, game.player.debt - taken)
    out.append(f"It does not go your way. ${taken:,.2f}, and he counts it twice.")
    if game.rng.random() < HOSPITAL_CHANCE:
        game.lose_a_day()
        out.append("You lose a day to it, and the loan does not stop for that either.")
    return _finish(game, out)


#: Running from federal agents works or it does not, and if it does not they
#: are considerably less interested in your side of it.
CAUGHT_MULTIPLIER = 1.4


def _badge(game, kind, choice) -> List[str]:
    """Agents at the turnstile. No weapon is offered, and that is deliberate.

    A raid used to be weather: it happened, it took a third of the bag, you
    read about it. Now it is three bad options - take it, buy it down, or bet
    the run on a staircase - and the seizure itself is unchanged, so the
    numbers the rest of the game was balanced against still hold for anybody
    who complies.
    """
    from .events import _confiscate, _take_cash

    out: List[str] = []

    def seize(scale: float) -> str:
        if not any(h.qty > 0 for h in game.player.wallet.values()):
            fine = _take_cash(game, (400.0 + game.rng.random() * 900.0) * scale)
            return (f"Nothing to seize, so they write you a ${fine:,.2f} fine "
                    f"instead and take your name twice.")
        fraction = min(0.95, game.rng.uniform(0.18, 0.42) * scale)
        lost = _confiscate(game, fraction)
        return (f"They seize {fraction:.0%} of the wallet - ${lost:,.2f} at cost. "
                f"Your lawyer is not returning calls.")

    game.stats["raids"] = int(game.stats.get("raids", 0)) + 1

    if choice == "comply":
        out.append("You put your hands where they can see them and let it happen.")
        out.append(seize(1.0))
        return _finish(game, out)

    if choice == "lawyer":
        paid = _take_cash(game, lawyer_cost(game))
        out.append(f"You make the call. ${paid:,.2f} on a retainer, and somebody "
                   f"who knows the words arrives inside the hour.")
        out.append(seize(1.0 - LAWYER_SAVES))
        return _finish(game, out)

    # running from a badge
    if game.rng.random() < odds(game, "run"):
        game.stats["fled_sec"] = int(game.stats.get("fled_sec", 0)) + 1
        out.append(game.rng.choice([
            "You go over the turnstile and out through the service door before "
            "either of them is through the crowd. Nothing of yours leaves with them.",
            "Down the stairs, along the platform, up the far exit. You are on a bus "
            "before anybody has said your name into a radio.",
        ]))
        out.append("They have your face now, which is a bill that arrives later.")
        return _finish(game, out)

    out.append("They have you before the turnstile, and they are not gentle about "
               "the fact that you tried.")
    out.append(seize(CAUGHT_MULTIPLIER))
    weapon = weapon_of(getattr(game, "weapon", None))
    if weapon:
        game.weapon = None
        out.append(f"They find the {weapon.name.lower()}. That goes in a bag with a "
                   f"label on it, and so does the rest of your afternoon.")
        game.lose_a_day()
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
    keys = {str(c["key"]) for c in options}
    # For the two encounters that replaced an event, a bot takes the answer
    # that event used to take on its own - comply with the badge, pay the
    # collector - so every balance number measured before these became choices
    # stays comparable afterwards. The new options are the player's edge, and a
    # bot that used them would quietly flatter the game.
    pending = getattr(game, "pending", None)
    kind = str((pending or {}).get("kind", ""))
    if kind == "badge":
        return "comply"
    if kind == "collector":
        return "pay"
    # elsewhere: paying always "works", so a bot picking purely on odds would
    # pay every time and measure a game nobody plays. It is the fallback.
    fighting = [c for c in options if c["key"] != "pay"]
    best = max(fighting, key=lambda c: float(c["odds"]))
    return str(best["key"]) if float(best["odds"]) >= 0.45 else (
        "pay" if "pay" in keys else str(best["key"]))
