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
    meme: bool = False  # memecoins get sillier events and wider station spreads
    note: str = ""
    #: how hard the market level moves in a day, as the sd of a log step.
    #: Separate from ``meme`` on purpose: ``meme`` is how silly the LOCAL price
    #: gets from stop to stop, ``vol`` is how fast the real market moves under
    #: all of them. A coin can be a serious asset and still rip.
    vol: float = 0.13
    #: how hard the level is dragged back toward the middle of its range each
    #: day. Low vol with a strong pull is a coin that always comes back; high
    #: vol with a strong pull would be free money, because "buy whatever sits
    #: lowest in its range" would be a formula rather than a judgement. The
    #: fast coins wander instead: they move further and owe you nothing.
    #:
    #: Tuned twice. The first pass set the fast coins to 0.05-0.07, which shut
    #: the exploit hardest and was miserable to play: a 25% drop on WIF left you
    #: underwater for 27 days in the worst tenth of cases, and 8% of the time it
    #: never came back inside a run. At 0.10-0.11 that is 17 days and 4%, and
    #: the naive strategy gains about four points. Worth it - being stuck for a
    #: whole run with nothing to do is a worse failure than a strategy being
    #: slightly too good.
    pull: float = 0.18

    @property
    def spread(self) -> float:
        """How much room there is between the floor and the ceiling."""
        return self.high / self.low if self.low > 0 else 1.0

    @property
    def mid(self) -> float:
        return (self.low + self.high) / 2.0


#: Ordered cheap-to-dear, which is also roughly safe-to-degenerate.
#:
#: The roster is built around a SPREAD OF SPEEDS, not just a spread of prices.
#: Eight coins where everything either crawled at 0.13 or ripped at 0.30 gave a
#: player two settings; twelve with volatility from 0.11 to 0.45 give them a
#: dial. The fast end exists so there is always something moving enough to be
#: worth a trip, and the slow end exists so the fast end means something.
COINS: List[Coin] = [
    Coin("SHIB", "Shiba Inu",    0.000008, 0.000075, meme=True, vol=0.30,
         note="fractions of a cent, whole lot of hope"),
    Coin("PEPE", "Pepe",         0.000002, 0.000031, meme=True, vol=0.30,
         note="pure vibes, no roadmap"),
    Coin("BONK", "Bonk",         0.0000090, 0.000105, meme=True, vol=0.42,
         pull=0.11,
         note="moves like a firework - lit at one stop, gone by the next"),
    Coin("DOGE", "Dogecoin",     0.06,     0.71,     meme=True, vol=0.30,
         note="started as a joke, still is"),
    Coin("WIF",  "Dogwifhat",    0.22,     4.80,     meme=True, vol=0.45,
         pull=0.10,
         note="the fastest thing on the board, in both directions"),
    Coin("XRP",  "Ripple",       0.38,     3.40,     vol=0.13,
         note="perpetually in court"),
    Coin("SUI",  "Sui",          0.45,     6.20,     vol=0.24,
         pull=0.12,
         note="a real chain that trades like a rumour"),
    Coin("USDC", "USD Coin",     0.97,     1.03,     vol=0.01,
         note="a dollar, mostly - park cash here when it gets hot"),
    Coin("SOL",  "Solana",       18.0,     260.0,    vol=0.13,
         note="fast chain, frequent outages"),
    Coin("AVAX", "Avalanche",    9.0,      78.0,     vol=0.20,
         pull=0.14,
         note="serious money that still can't sit still"),
    Coin("ETH",  "Ethereum",     1100.0,   4900.0,   vol=0.13,
         note="gas fees will eat you alive"),
    Coin("BTC",  "Bitcoin",      21000.0,  109000.0, vol=0.11,
         note="the original, and the heaviest to carry"),
]

BY_SYMBOL: Dict[str, Coin] = {c.symbol: c for c in COINS}


def coin(symbol: str) -> Coin:
    try:
        return BY_SYMBOL[symbol.upper()]
    except KeyError:
        raise KeyError(f"no such coin {symbol!r}; try one of {', '.join(BY_SYMBOL)}") from None
