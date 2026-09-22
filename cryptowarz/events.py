"""What happens to you between stations.

Events are the texture of the game and its main source of loss.  They fire on
arrival, weighted by the station's ``heat`` and softened by however many VPN
levels you have bought - so the rich stations that pay best are also the ones
most likely to cost you everything, which is the trade the whole game is about.

Anything that takes coins takes them *proportionally* across the wallet rather
than emptying one position.  Losing a fixed slice of everything is a setback;
losing one entire bag at random is a coin flip, and a coin flip is not a
decision.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Callable, List, Optional, Tuple

if TYPE_CHECKING:                       # pragma: no cover
    from .game import Game

from .game import SUBWAY_FARE  # noqa: E402  (module-level constant, no cycle)


def _confiscate(game: "Game", fraction: float) -> float:
    """Take a share of every holding. Returns the cost basis removed."""
    removed = 0.0
    for holding in game.player.wallet.values():
        if holding.qty <= 0:
            continue
        take_qty = holding.qty * fraction
        take_cost = holding.cost * fraction
        holding.qty -= take_qty
        holding.cost -= take_cost
        removed += take_cost
    return removed


def _has_coins(game: "Game") -> bool:
    return any(h.qty > 0 for h in game.player.wallet.values())


def _take_cash(game: "Game", amount: float) -> float:
    """Take cash, but never the last subway fare.

    Stripped to nothing with an empty wallet, a player cannot buy, cannot sell
    and cannot travel - the run is over with twenty days left and no move
    available. That is a dead end rather than a hard position, and it is the
    same reason ``max_buyable`` reserves the fare. Events can ruin you; they
    should not be able to strip you of the ability to play.
    """
    from .game import SUBWAY_FARE
    spendable = max(0.0, game.player.cash - SUBWAY_FARE)
    taken = min(amount, spendable)
    game.player.cash -= taken
    return taken


# ---------------------------------------------------------------- the events

def sec_raid(game: "Game") -> List[str]:
    if not _has_coins(game):
        game.stats["raids"] = game.stats.get("raids", 0) + 1
        fine = _take_cash(game, 400.0 + game.rng.random() * 900.0)
        return [f"SEC agents stop you at the turnstile. Nothing to seize, so they "
                f"write you a ${fine:,.2f} fine instead."]
    game.stats["raids"] = game.stats.get("raids", 0) + 1
    fraction = game.rng.uniform(0.18, 0.42)
    lost = _confiscate(game, fraction)
    return [f"SEC raid on the platform. They seize {fraction:.0%} of your wallet - "
            f"${lost:,.2f} at cost. Your lawyer is not returning calls."]


def phishing(game: "Game") -> List[str]:
    if not _has_coins(game):
        return ["A DM offers you a free NFT. You ignore it. Small victories."]
    fraction = game.rng.uniform(0.08, 0.22)
    lost = _confiscate(game, fraction)
    return [f"You signed something you shouldn't have. A drainer takes "
            f"${lost:,.2f} of your bags."]


def gas_spike(game: "Game") -> List[str]:
    fee = _take_cash(game, 120.0 + game.rng.random() * 700.0)
    return [f"Network congestion. Gas eats ${fee:,.2f} just to move your own money."]


def airdrop(game: "Game") -> List[str]:
    from .coins import COINS
    target = game.rng.choice([c for c in COINS if c.symbol != "USDC"])
    price = game.market.price(target.symbol)
    value = 300.0 + game.rng.random() * 2_600.0
    if game.player.free_capacity < value:
        return [f"An {target.symbol} airdrop lands, but your wallet is full. "
                f"It expires unclaimed. That one will sting."]
    qty = value / price
    h = game.player.holding(target.symbol)
    h.qty += qty
    h.cost += value          # counts against capacity at fair value
    return [f"Airdrop: {qty:,.6f} {target.symbol} (~${value:,.2f}) for a wallet you "
            f"forgot you'd connected."]


def found_wallet(game: "Game") -> List[str]:
    found = 250.0 + game.rng.random() * 1_800.0
    game.player.cash += found
    return [f"A seed phrase on the back of a MetroCard. It still had "
            f"${found:,.2f} on it. You don't ask."]


def shark_visit(game: "Game") -> List[str]:
    if game.player.debt <= 0:
        return ["A large man studies you on the platform, decides you're nobody, "
                "and goes back to his phone."]
    demand = min(max(0.0, game.player.cash - SUBWAY_FARE), game.player.debt * 0.25)
    if demand < 50:
        return ["The Shark's associate finds you. You have nothing. He is patient. "
                "That's worse."]
    game.player.cash -= demand
    game.player.debt -= demand
    return [f"The Shark's associate takes ${demand:,.2f} off you on the platform. "
            f"Consider it a payment."]


def whale_offer(game: "Game") -> List[str]:
    holdings = [(s, h) for s, h in game.player.wallet.items() if h.qty > 0]
    if not holdings:
        return ["A whale wallet DMs you asking what you're holding. Nothing. Awkward."]
    symbol, holding = game.rng.choice(holdings)
    premium = game.rng.uniform(1.25, 1.85)
    price = game.market.price(symbol) * premium
    proceeds = holding.qty * price
    game.player.cash += proceeds
    holding.qty, holding.cost = 0.0, 0.0
    game.player.drop_empty()
    return [f"A whale takes your entire {symbol} bag off you at {premium:.0%} of "
            f"market - ${proceeds:,.2f}. Ask no questions."]


def delay(game: "Game") -> List[str]:
    if getattr(game, "perk", None) == "metrocard":
        return ["Signal problems at Chambers St. You know the workaround and "
                "reroute without losing the day."]
    game.day += 1
    game.player.debt *= (1.0 + game.shark_rate)
    return ["Signal problems at Chambers St. You lose a day on a stopped train "
            "while your debt keeps compounding."]


def quiet(game: "Game") -> List[str]:
    return []


# ------------------------------------------------------------ enforcement

#: Days the SEC leaves you alone at the start of a run.
#:
#: Losing a third of your bags on day three is not a hard position, it is a
#: coin flip that decides the run before you have made a decision worth
#: judging - you have no capacity, no cash and nothing to trade your way out
#: with. The grace period buys every run the same fair opening, and it costs
#: the game nothing, because the pressure is not removed - it is *moved*.
RAID_GRACE = 15

#: Where raid weight ends up on the final day, relative to the day it comes
#: back. The back half is more dangerous than it used to be, deliberately: by
#: then you have something worth taking and the choice to sit on it or keep
#: pushing is the most interesting decision in the game. A flat rate after the
#: grace would have made the first half safe and changed nothing else.
RAID_RAMP_TO = 1.8


def raid_pressure(game, day: Optional[int] = None) -> float:
    """What the SEC's weight is multiplied by on a given day. Zero = grace."""
    day = game.day if day is None else day
    if day <= RAID_GRACE:
        return 0.0
    span = max(1, int(getattr(game, "days", 30)) - RAID_GRACE)
    return 1.0 + (RAID_RAMP_TO - 1.0) * min(1.0, (day - RAID_GRACE) / span)


#: (function, base weight, scales_with_heat)
EVENTS: List[Tuple[Callable[["Game"], List[str]], float, bool]] = [
    (sec_raid,     10.0, True),
    (phishing,      8.0, True),
    (gas_spike,     9.0, False),
    (shark_visit,   7.0, False),
    (delay,         5.0, False),
    (airdrop,       8.0, False),
    (found_wallet,  6.0, False),
    (whale_offer,   6.0, False),
    (quiet,        34.0, False),
]


def event_weights(game: "Game", station=None, day: Optional[int] = None) -> List[float]:
    """The weight of every event for an arrival, in EVENTS order.

    Factored out of ``roll_event`` so the threat meter is computed from the
    *same* numbers the roll uses. A forecast drawn from a second, parallel
    formula is a meter that can disagree with the game, and a meter that lies
    is worse than no meter: the player would learn to distrust the one piece of
    information the game volunteers.
    """
    station = station or game.station
    # a tier or a difficulty turns the whole map up; a VPN or a burner turns it
    # back down
    heat = min(1.0, station.heat * getattr(game, "heat_mult", 1.0))
    shelter = 1.0 - min(0.66, 0.22 * game.player.vpn)
    if getattr(game, "perk", None) == "burner":
        shelter *= 0.66
    # gear you are currently holding for; the best piece, never the sum, so no
    # build stacks its way to immunity
    shelter *= 1.0 - game.luck
    pressure = raid_pressure(game, day)
    weights = []
    for fn, weight, scales in EVENTS:
        w = weight
        if scales:
            w *= (0.35 + 1.4 * heat) * shelter
        if fn is sec_raid:
            w *= pressure
        weights.append(w)
    return weights


def raid_chance(game: "Game", station=None, day: Optional[int] = None) -> float:
    """The exact probability the SEC turns up on one arrival. Never a guess."""
    weights = event_weights(game, station, day)
    total = sum(weights)
    if total <= 0:
        return 0.0
    return weights[[e[0] for e in EVENTS].index(sec_raid)] / total


def roll_event(game: "Game") -> List[str]:
    """Pick one event for this arrival, weighted by heat, tier, VPN and perk."""
    weights = event_weights(game)
    chosen = game.rng.choices([e[0] for e in EVENTS], weights=weights, k=1)[0]
    return chosen(game)


# ------------------------------------------------------------- the threat bar

#: Five readings, and the number of bars each one fills. The cut points are
#: read off the real per-arrival chance rather than chosen to look dramatic:
#: at Express with no VPN the map spans LOW to HIGH the day the grace ends and
#: WATCH to SEVERE by day thirty, so the spread across stations stays readable
#: at every point in the run while the whole board drifts upward. Two VPN
#: levels pull the same map back to LOW and WATCH, which is the point of
#: showing any of this - the meter is the thing a VPN visibly buys.
THREAT: Tuple[Tuple[float, str, int], ...] = (
    (0.185, "SEVERE", 4),
    (0.130, "HIGH",   3),
    (0.085, "WATCH",  2),
    (0.0,   "LOW",    1),      # anything above zero is never "quiet"
)
THREAT_BARS = 4
QUIET = ("QUIET", 0)

#: Three lines per reading so the wire does not repeat itself, picked by day
#: and station rather than by a die - a headline that re-rolls on every redraw
#: reads as noise, and drawing here would also move the run's random stream.
WIRE_LINES: dict = {
    "QUIET": (
        "Enforcement is still working last quarter's cases. Nobody downtown knows your name.",
        "The regulator's press office is talking about something else entirely.",
        "Nothing on the wire. It will not last, and everybody knows it.",
    ),
    "LOW": (
        "A subcommittee asks for documents. Nothing moves fast in Washington.",
        "An enforcement notice goes out to somebody else. You read it twice anyway.",
        "Quiet, but the tone has changed. They are writing things down.",
    ),
    "WATCH": (
        "Two agents were seen at {station} this week. They were not commuting.",
        "The {borough} field office has been busy. Ask anyone on the platform.",
        "Somebody at {station} got stopped on Tuesday. Nobody has seen him since.",
    ),
    "HIGH": (
        "Word on the platform: the feds are working this line. A day or two, maybe less.",
        "They have a van on the street above {station}. It has not moved since Monday.",
        "Three seizures in {borough} this week. {station} is next, if you believe the wire.",
    ),
    "SEVERE": (
        "They are at {station}. The only question left is who they stop.",
        "{station} is crawling. Turnstiles, mezzanine, both platforms.",
        "If you are carrying anything, {station} is the worst place in the city today.",
    ),
}


def standing_heat(station) -> int:
    """The stop's own reputation, in bars, for use while the grace holds.

    During the first fifteen days every stop reads QUIET, which is true and
    useless - a column that says the same thing sixteen times is not worth the
    width. This is what the stop is *like*, so the early map still tells you
    which places will be bad later, and it never pretends to be the live
    number: the two are labelled differently everywhere they are drawn.
    """
    return max(0, min(THREAT_BARS, int(round(station.heat * THREAT_BARS))))


def threat_level(chance: float) -> Tuple[str, int]:
    """(label, bars filled) for a per-arrival raid chance."""
    if chance <= 0:
        return QUIET
    for floor, label, bars in THREAT:
        if chance >= floor:
            return (label, bars)
    return QUIET


def wire(game: "Game", station=None, day: Optional[int] = None) -> dict:
    """The threat reading for a stop, as a news post both front ends can draw.

    Returns the label, how many bars to fill, the true per-arrival chance, the
    chance of being hit at least once across the next two arrivals - which is
    the number a player actually wants when deciding whether to make one more
    run - and a line of copy.
    """
    station = station or game.station
    when = game.day if day is None else day
    chance = raid_chance(game, station, day)
    label, bars = threat_level(chance)
    lines = WIRE_LINES[label]
    pick = lines[(when + len(station.name)) % len(lines)]
    text = pick.format(station=station.name, borough=station.borough)
    grace_left = max(0, RAID_GRACE - when)
    return {
        "label": label,
        "bars": bars,
        "of": THREAT_BARS,
        "chance": chance,
        "two_stops": 1.0 - (1.0 - chance) ** 2,
        "grace_left": grace_left,
        "text": text,
    }
