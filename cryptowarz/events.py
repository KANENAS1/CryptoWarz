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
from typing import TYPE_CHECKING, Callable, List, Tuple

if TYPE_CHECKING:                       # pragma: no cover
    from .game import Game


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


# ---------------------------------------------------------------- the events

def sec_raid(game: "Game") -> List[str]:
    if not _has_coins(game):
        fine = min(game.player.cash, 400.0 + game.rng.random() * 900.0)
        game.player.cash -= fine
        return [f"SEC agents stop you at the turnstile. Nothing to seize, so they "
                f"write you a ${fine:,.2f} fine instead."]
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
    fee = min(game.player.cash, 120.0 + game.rng.random() * 700.0)
    game.player.cash -= fee
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
    demand = min(game.player.cash, game.player.debt * 0.25)
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
    return [f"A whale takes your entire {symbol} bag off you at {premium:.0%} of "
            f"market - ${proceeds:,.2f}. Ask no questions."]


def delay(game: "Game") -> List[str]:
    game.day += 1
    game.player.debt *= 1.10
    return ["Signal problems at Chambers St. You lose a day on a stopped train "
            "while your debt keeps compounding."]


def quiet(game: "Game") -> List[str]:
    return []


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


def roll_event(game: "Game") -> List[str]:
    """Pick one event for this arrival, weighted by heat and VPN level."""
    heat = game.station.heat
    shelter = 1.0 - min(0.66, 0.22 * game.player.vpn)
    weights = []
    for _fn, weight, scales in EVENTS:
        w = weight
        if scales:
            w *= (0.35 + 1.4 * heat) * shelter
        weights.append(w)
    chosen = game.rng.choices([e[0] for e in EVENTS], weights=weights, k=1)[0]
    return chosen(game)
