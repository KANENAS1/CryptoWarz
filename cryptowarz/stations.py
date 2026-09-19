"""Ten NYC subway stops, each with its own idea of what a coin is worth.

The map is the game.  Every station biases certain coins up and others down, so
the loop is always: find out where something is cheap, work out who is paying
over the odds for it, and decide whether the ride is worth a day of your thirty.

Biases are flavour made mechanical - Wall Street institutions bid up Bitcoin and
won't touch a dog coin; Bushwick is the exact inverse.  ``heat`` drives how
often the SEC turns up, and it is highest where the money is easiest.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(frozen=True)
class Station:
    name: str
    lines: str
    borough: str
    flavor: str
    #: per-coin price multipliers; anything unlisted trades at 1.0
    bias: Dict[str, float] = field(default_factory=dict)
    #: 0.0 - 1.0, chance-of-trouble weighting
    heat: float = 0.5
    #: some stops have services
    has_shark: bool = False
    has_vault: bool = False
    has_upgrades: bool = False
    #: somebody is running a prize wheel on the mezzanine. Once per stop per
    #: run, so it pays for going somewhere NEW rather than for bouncing between
    #: two stations - which is the only version of this that makes a bigger map
    #: worth having.
    has_wheel: bool = False

    def multiplier(self, symbol: str) -> float:
        return self.bias.get(symbol, 1.0)


STATIONS: List[Station] = [
    Station(
        "Wall Street", "4 5", "Manhattan",
        "Suits everywhere. Someone is explaining an ETF to a tourist.",
        bias={"BTC": 1.30, "ETH": 1.22, "AVAX": 1.16, "USDC": 1.02, "SUI": 1.06,
              "DOGE": 0.62, "SHIB": 0.55, "PEPE": 0.50, "BONK": 0.48, "WIF": 0.44},
        heat=0.85, has_vault=True,
    ),
    Station(
        "Jefferson St", "L", "Brooklyn",
        "Bushwick. Three people in this car are launching a token this week.",
        bias={"WIF": 1.88, "PEPE": 1.75, "BONK": 1.70, "SHIB": 1.62, "DOGE": 1.45,
              "SOL": 1.14, "SUI": 1.12, "BTC": 0.80},
        heat=0.55, has_upgrades=True,
    ),
    Station(
        "Times Sq-42 St", "N Q R W 1 2 3 7 S", "Manhattan",
        "Tourist money. Everything here costs more and everyone knows it.",
        bias={"BTC": 1.18, "ETH": 1.15, "SOL": 1.20, "DOGE": 1.25, "XRP": 1.15,
              "WIF": 1.32, "BONK": 1.24, "SUI": 1.18, "AVAX": 1.12},
        heat=0.80,
    ),
    Station(
        "Coney Island-Stillwell Av", "D F N Q", "Brooklyn",
        "End of the line. Salt air, dead arcade, suspiciously cheap everything.",
        bias={"SHIB": 0.45, "PEPE": 0.42, "BONK": 0.40, "WIF": 0.38, "DOGE": 0.58,
              "XRP": 0.70, "SOL": 0.82, "SUI": 0.72, "AVAX": 0.80},
        heat=0.30,
    ),
    Station(
        "125 St", "4 5 6", "Manhattan",
        "Harlem. A man with a folding table will sell you anything.",
        bias={"DOGE": 1.30, "XRP": 1.34, "SHIB": 1.20, "WIF": 1.36, "BONK": 1.28,
              "SUI": 1.12, "ETH": 0.88},
        heat=0.60, has_shark=True,
    ),
    Station(
        "Grand Central-42 St", "4 5 6 7 S", "Manhattan",
        "Commuters moving with purpose. Liquidity, but no bargains.",
        bias={"BTC": 1.08, "ETH": 1.10, "USDC": 1.01, "SOL": 1.05, "AVAX": 1.07, "SUI": 1.04},
        heat=0.70, has_vault=True,
    ),
    Station(
        "Flushing-Main St", "7", "Queens",
        "The busiest station outside Manhattan. Cash moves fast here.",
        bias={"XRP": 0.62, "USDC": 0.98, "SOL": 0.86, "ETH": 0.92, "SUI": 0.66,
              "AVAX": 0.88, "WIF": 0.78},
        heat=0.45,
    ),
    Station(
        "161 St-Yankee Stadium", "4 B D", "Bronx",
        "Game day. Everyone is up, everyone is buying, nobody is reading.",
        bias={"DOGE": 1.52, "SHIB": 1.40, "PEPE": 1.38, "WIF": 1.60, "BONK": 1.48,
              "SUI": 1.22, "BTC": 0.92},
        heat=0.65, has_shark=True,
    ),
    Station(
        "St George", "SIR", "Staten Island",
        "Off the ferry. Quiet, cheap, and a long way from anywhere.",
        bias={"BTC": 0.78, "ETH": 0.80, "SOL": 0.74, "USDC": 0.99, "AVAX": 0.76,
              "SUI": 0.70, "WIF": 0.72, "BONK": 0.74},
        heat=0.20, has_upgrades=True,
    ),
    Station(
        "14 St-Union Sq", "4 5 6 L N Q R W", "Manhattan",
        "Everything connects here. Fair prices, which is its own kind of trap.",
        bias={},
        heat=0.50, has_vault=True, has_upgrades=True,
    ),
    Station(
        "Bedford Av", "L", "Brooklyn",
        "Williamsburg. Every third person here has a podcast about this.",
        bias={"WIF": 1.72, "BONK": 1.58, "PEPE": 1.50, "SOL": 1.18, "SUI": 1.16,
              "BTC": 0.86, "ETH": 0.90},
        heat=0.58, has_wheel=True,
    ),
    Station(
        "Atlantic Av-Barclays Ctr", "2 3 4 5 B D N Q R", "Brooklyn",
        "Nine lines and a arena. Everybody is going somewhere else.",
        bias={"BTC": 1.12, "ETH": 1.09, "AVAX": 1.10, "DOGE": 1.18, "SUI": 1.08,
              "USDC": 1.01},
        heat=0.72, has_shark=True, has_wheel=True,
    ),
    Station(
        "Roosevelt Av-Jackson Hts", "7 E F M R", "Queens",
        "Five lines, forty languages, and a remittance shop on every corner.",
        bias={"XRP": 1.30, "USDC": 1.02, "SOL": 1.08, "AVAX": 1.04, "SHIB": 1.12,
              "BTC": 0.90},
        heat=0.62, has_vault=True, has_wheel=True,
    ),
    Station(
        "Canal St", "6 J N Q R W Z", "Manhattan",
        "Chinatown. Cash only, and everything is a slightly better price.",
        bias={"USDC": 0.99, "BTC": 0.84, "ETH": 0.86, "SOL": 0.80, "XRP": 0.76,
              "SUI": 0.78, "AVAX": 0.82},
        heat=0.68, has_upgrades=True, has_wheel=True,
    ),
    Station(
        "Woodlawn", "4", "Bronx",
        "The top of the 4. A cemetery, a golf course, and nobody watching.",
        bias={"SHIB": 0.52, "PEPE": 0.50, "BONK": 0.48, "WIF": 0.46, "DOGE": 0.66,
              "ETH": 0.88},
        heat=0.18, has_wheel=True,
    ),
    Station(
        "Far Rockaway-Mott Av", "A", "Queens",
        "Ninety minutes from Midtown. The board here has not been updated in a while.",
        bias={"WIF": 0.44, "BONK": 0.46, "SUI": 0.68, "AVAX": 0.74, "SOL": 0.78,
              "XRP": 1.28, "USDC": 1.02},
        heat=0.22, has_shark=True, has_wheel=True,
    ),
]

BY_NAME = {s.name: s for s in STATIONS}


def station(name: str) -> Station:
    try:
        return BY_NAME[name]
    except KeyError:
        raise KeyError(f"no such station {name!r}") from None
