"""Price generation: a drifting market, sampled differently at each station.

The first version of this drew every station's price independently from the
coin's whole range, so Solana could be $20 at one stop and $200 at the next.
That made "buy whatever is cheapest relative to its range" a formula that won
every single run - no judgement, no tension, no game.

So there are two layers now.

**A level per coin** that random-walks day to day, pulled gently back toward the
middle of its range and shoved hard by shocks. This is the market's real price,
shared by every station, and it is what makes *holding* a decision: a bag can
appreciate overnight, or rug while you sleep.

**A station's take on that level** - its bias, plus small noise. This is the
arbitrage, and it is deliberately bounded: roughly 2x between the keenest buyer
and the cheapest seller, not the 10x the old model allowed. Enough to be worth
a trip, not enough to print money without thinking.

Still not a market model. It is tuned for how it plays.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .coins import COINS, Coin
from .stations import Station


@dataclass(frozen=True)
class Shock:
    symbol: str
    headline: str
    factor: float

    @property
    def is_crash(self) -> bool:
        return self.factor < 1.0


CRASHES = [
    ("{name} rugged - devs deleted the repo", 0.34),
    ("Exchange delists {name} without warning", 0.46),
    ("{name} bridge drained overnight", 0.38),
    ("Influencer who shilled {name} deletes the account", 0.55),
]
PUMPS = [
    ("{name} trending #1 - the normies are buying", 2.10),
    ("Major fund announces a {name} allocation", 1.75),
    ("{name} listed everywhere at once", 1.95),
    ("Somebody's grandma asks about {name} on TV", 1.60),
]
MEME_PUMPS = [
    ("A billionaire tweets a dog picture - {name} goes vertical", 3.10),
    ("{name} adopted by an entire subreddit", 2.45),
]


class MarketState:
    """The drifting level of every coin. One of these per game."""

    def __init__(self, rng: random.Random) -> None:
        self.levels: Dict[str, float] = {}
        for c in COINS:
            # Start in the middle of the range - but clamped to the coin's own
            # bounds. Unclamped, USDC opened anywhere from $0.78 to $1.21, which
            # made the one asset that exists to be safe the best trade on the
            # board: buy the "stablecoin" at $0.86, wait for it to revert, take
            # a risk-free 16%. drift() clamped it every later day; day one did
            # not, so the exploit was only ever available on the first screen.
            self.levels[c.symbol] = max(c.low, min(c.mid * rng.uniform(0.8, 1.2), c.high))

    def drift(self, rng: random.Random) -> None:
        """One day of movement: a random walk that resists the extremes."""
        for c in COINS:
            level = self.levels[c.symbol]
            if c.symbol == "USDC":
                self.levels[c.symbol] = max(0.97, min(1.03, level * rng.uniform(0.997, 1.003)))
                continue
            step = rng.gauss(0.0, c.vol)
            # pull back toward the middle so nothing drifts off forever
            pull = c.pull * math.log(c.mid / level) if level > 0 else 0.0
            level *= math.exp(step + pull)
            self.levels[c.symbol] = max(c.low * 0.4, min(level, c.high * 1.6))

    def apply(self, symbol: str, factor: float, coin: Coin) -> None:
        """A shock moves the real level, so it persists beyond one station."""
        level = self.levels[symbol] * factor
        self.levels[symbol] = max(coin.low * 0.15, min(level, coin.high * 2.2))


@dataclass
class Market:
    station: Station
    prices: Dict[str, float]
    shock: Optional[Shock] = None

    def price(self, symbol: str) -> float:
        return self.prices[symbol.upper()]

    @property
    def headline(self) -> Optional[str]:
        return self.shock.headline if self.shock else None


#: How much of a station's raw opinion actually reaches the price. Compressed
#: toward 1.0 so no single stop is a money printer.
BIAS_COMPRESSION = 0.62


def station_markup(station: Station, symbol: str) -> float:
    """What this stop adds to, or takes off, the market price. 1.0 is fair.

    This is the single biggest thing that happens to a player's money and it
    used to be invisible: buying WIF at the stop that loves it and selling
    anywhere else loses 60% with the market completely still. A player who
    cannot see it experiences their own overpaying as the coin betraying them.
    """
    return 1.0 + (station.multiplier(symbol) - 1.0) * BIAS_COMPRESSION


def _station_price(coin: Coin, level: float, station: Station, rng: random.Random) -> float:
    """What this station will trade at, given the market level."""
    bias = station_markup(station, coin.symbol)
    noise = rng.uniform(0.94, 1.06) if coin.meme else rng.uniform(0.975, 1.025)
    price = level * bias * noise
    if coin.symbol == "USDC":
        # the safe harbour has to actually be safe, at every station
        return max(coin.low, min(price, coin.high))
    return max(coin.low * 0.1, price)


def generate(station: Station, rng: random.Random, state: Optional[MarketState] = None,
             shock_chance: float = 0.24, luck: Optional[Dict[str, float]] = None) -> Market:
    """Prices at one station. Pass a MarketState to get a market with memory.

    ``luck`` maps a symbol to how far the crash/pump coin-flip tilts toward a
    pump for it - gear the player is holding for. It moves the threshold on a
    draw that already happens rather than adding one; the flip is the same
    flip, weighted differently.
    """
    if state is None:
        state = MarketState(rng)

    shock: Optional[Shock] = None
    if rng.random() < shock_chance:
        target = rng.choice([c for c in COINS if c.symbol != "USDC"])
        crash_odds = 0.5 - (luck or {}).get(target.symbol, 0.0)
        if rng.random() < crash_odds:
            template, factor = rng.choice(CRASHES)
        else:
            template, factor = rng.choice(MEME_PUMPS + PUMPS if target.meme else PUMPS)
        shock = Shock(target.symbol, template.format(name=target.name), factor)
        state.apply(target.symbol, factor, target)

    prices = {c.symbol: _station_price(c, state.levels[c.symbol], station, rng) for c in COINS}
    return Market(station, prices, shock)
