"""The tradeable assets.

Deliberately *not* real market data.  CryptoWarz is a game about arbitrage and
nerve, not a market simulator - prices here are invented to make interesting
decisions, and a coin's behaviour is tuned for how it plays, not for how its
real counterpart trades.

The spread between ``low`` and ``high`` is the whole game: a coin you can buy at
its floor in one station and unload at its ceiling three stops away is where the
money is.  Wide-spread coins are cheap and volatile; tight-spread coins are
expensive and dull but safe to park value in.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class Coin:
    symbol: str
    name: str
    low: float          # cheapest it ever trades
    high: float         # dearest it ever trades
    meme: bool = False  # memecoins get wilder swings and sillier events
    note: str = ""

    @property
    def spread(self) -> float:
        """How much room there is between the floor and the ceiling."""
        return self.high / self.low if self.low > 0 else 1.0

    @property
    def mid(self) -> float:
        return (self.low + self.high) / 2.0


#: Ordered cheap-to-dear, which is also roughly safe-to-degenerate.
COINS: List[Coin] = [
    Coin("SHIB", "Shiba Inu",    0.000008, 0.000075, meme=True,
         note="fractions of a cent, whole lot of hope"),
    Coin("PEPE", "Pepe",         0.000002, 0.000031, meme=True,
         note="pure vibes, no roadmap"),
    Coin("DOGE", "Dogecoin",     0.06,     0.71,     meme=True,
         note="started as a joke, still is"),
    Coin("XRP",  "Ripple",       0.38,     3.40,
         note="perpetually in court"),
    Coin("USDC", "USD Coin",     0.97,     1.03,
         note="a dollar, mostly - park cash here when it gets hot"),
    Coin("SOL",  "Solana",       18.0,     260.0,
         note="fast chain, frequent outages"),
    Coin("ETH",  "Ethereum",     1100.0,   4900.0,
         note="gas fees will eat you alive"),
    Coin("BTC",  "Bitcoin",      21000.0,  109000.0,
         note="the original, and the heaviest to carry"),
]

BY_SYMBOL: Dict[str, Coin] = {c.symbol: c for c in COINS}


def coin(symbol: str) -> Coin:
    try:
        return BY_SYMBOL[symbol.upper()]
    except KeyError:
        raise KeyError(f"no such coin {symbol!r}; try one of {', '.join(BY_SYMBOL)}") from None
