"""Gear: what winning leaves you wearing, and what it does for your luck.

Perks are a choice you make before a run. Gear is the opposite - you do not
pick it, you *earn* it by winning while holding something, and it then quietly
favours that same kind of holding forever after. Win with memecoins and the
memecoins start breaking your way; win parked in dollars and dollars stop
attracting trouble.

That loop is the point. A perk answers "how do I want to play this run"; gear
answers "what am I becoming". It rewards a player for having a style rather
than for grinding, because a win only ever credits the one class of coin you
were actually holding at the end - cash out to dollars on day thirty and the
memecoin charm learns nothing.

**Luck is deliberately small.** At full level it is a 15% swing, and only on
coins you are holding right now. Two things keep it from becoming the game:

It is never a sum. Holding one coin from every class gives you the *best* of
your bonuses against trouble, not the total, so there is no build that stacks
to immunity.

It re-weights decisions that already exist rather than adding new rolls. A
shock was always a coin-flip between a crash and a pump; gear tilts that flip.
Trouble was always weighted; gear adds one more factor to the weight. Nothing
here introduces a roll that was not already being made.

That is not the same as promising an identical random stream with and without
gear - changing which branch a shock takes can change what gets drawn after
it, and claiming otherwise would be a comment that reads well and is false.
What is guaranteed is the thing that matters: gear is written into the save,
so a reloaded run carries the same luck and replays exactly as it would have.
The anti-savescum guarantee outranks any feature, and a luck system that
quietly broke it would be worse than no luck system at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .coins import BY_SYMBOL, COINS

#: Coins group into four kinds, because four pieces of gear is a collection and
#: eight is a chore.
CLASSES: Dict[str, Tuple[str, ...]] = {
    "meme":   ("SHIB", "PEPE", "DOGE"),
    "alt":    ("XRP", "SOL"),
    "major":  ("ETH", "BTC"),
    "stable": ("USDC",),
}
CLASS_OF: Dict[str, str] = {sym: cls for cls, syms in CLASSES.items() for sym in syms}


@dataclass(frozen=True)
class GearPiece:
    key: str            # also the coin class it is bound to
    name: str
    blurb: str
    covers: str         # the coins it speaks for, in words


GEAR: List[GearPiece] = [
    GearPiece("meme", "Platform Rat Charm",
              "Found on the roadbed at Canal St. The jokes go your way.",
              "SHIB · PEPE · DOGE"),
    GearPiece("alt", "Brass Subway Token",
              "Minted before the turnstiles took cards. Older money, better odds.",
              "XRP · SOL"),
    GearPiece("major", "Cold-Storage Watch",
              "Heavy, unfashionable, and it has never lost a key.",
              "ETH · BTC"),
    GearPiece("stable", "Laminated MetroCard",
              "Nothing much happens to somebody holding dollars.",
              "USDC"),
]
GEAR_BY_KEY: Dict[str, GearPiece] = {g.key: g for g in GEAR}

MAX_LEVEL = 3
#: Wins - finishing in profit holding that class - needed for each level.
WINS_FOR_LEVEL: Tuple[int, ...] = (1, 3, 7)
#: How much luck one level is worth. Three levels is a 15% swing, no more.
LUCK_PER_LEVEL = 0.05
#: The bar a run has to clear to count as a win, matching "In the Black".
WIN_AT = 2_000.0


def level_for(wins: int) -> int:
    """How many levels that many wins is worth."""
    return sum(1 for needed in WINS_FOR_LEVEL if wins >= needed)


def levels_from_wins(wins: Dict[str, int]) -> Dict[str, int]:
    return {key: level_for(int(wins.get(key, 0))) for key in CLASSES if wins.get(key)}


def luck_of(levels: Dict[str, int], cls: str) -> float:
    return LUCK_PER_LEVEL * min(MAX_LEVEL, int(levels.get(cls, 0)))


def luck_by_symbol(levels: Dict[str, int], wallet) -> Dict[str, float]:
    """Per-coin luck, for the coins actually in the wallet right now.

    Gear you own but are not holding for does nothing: the bonus follows the
    bag, not the player.
    """
    out = {}
    for symbol, holding in (wallet or {}).items():
        qty = holding.qty if hasattr(holding, "qty") else holding.get("qty", 0.0)
        cls = CLASS_OF.get(symbol)
        if qty > 0 and cls:
            luck = luck_of(levels, cls)
            if luck > 0:
                out[symbol] = luck
    return out


def best_luck(levels: Dict[str, int], wallet) -> float:
    """The best single bonus you are holding for - never the sum of them."""
    per_symbol = luck_by_symbol(levels, wallet)
    return max(per_symbol.values()) if per_symbol else 0.0


def winning_class(game) -> Optional[str]:
    """Which class the player had the most value in when the run ended.

    None when they finished holding nothing - gear is earned by *holding*
    something through the finish, so cashing out to dollars earns the dollar
    charm and cashing out entirely earns nothing.
    """
    totals: Dict[str, float] = {}
    for symbol, holding in game.player.wallet.items():
        if holding.qty <= 0 or symbol not in CLASS_OF:
            continue
        value = holding.qty * game.market.price(symbol)
        totals[CLASS_OF[symbol]] = totals.get(CLASS_OF[symbol], 0.0) + value
    if not totals:
        return None
    return max(totals.items(), key=lambda kv: kv[1])[0]


def credit_win(profile, game) -> Optional[Tuple[GearPiece, int, int]]:
    """Record a win against the gear it belongs to.

    Returns (piece, level before, level after), or None when the run did not
    win or finished holding nothing. Levelling up is announced; a win that only
    moves the counter is not, because "3 more to go" is a chore bar.
    """
    from .progress import counts_for_progress

    if not counts_for_progress(game) or game.final_score() <= WIN_AT:
        return None
    cls = winning_class(game)
    if cls is None:
        return None
    before = level_for(int(profile.gear_wins.get(cls, 0)))
    profile.gear_wins[cls] = int(profile.gear_wins.get(cls, 0)) + 1
    after = level_for(profile.gear_wins[cls])
    return (GEAR_BY_KEY[cls], before, after)
