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


#: How often a coin's trend re-rolls. At 0.22 a run lasts about four or five
#: days, which is long enough to notice you are in one and short enough that
#: thirty days holds six or seven of them.
TREND_FLIP = 0.22
#: How hard a trend pushes, as a multiple of the coin's daily volatility. A
#: pure random walk wanders; it does not pump and it does not dump. This is the
#: term that makes a chart have SHAPES in it - a climb that builds over four
#: days and then rolls over is a thing a player can see coming, be wrong about,
#: and act on. Noise alone is none of those.
TREND_STRENGTH = 0.55
#: How many days of level history to keep per coin. The chart shows a fortnight;
#: the rest is slack so a reload never draws a shorter line than the player had.
HISTORY_KEPT = 20
#: How many of those a sparkline draws.
SPARK_DAYS = 14

# ------------------------------------------------------------------ the tide
#: Every coin used to drift entirely alone. Measured: SHIB and BTC had a daily
#: correlation of +0.01, and across 1,500 simulated markets the whole board was
#: never red - not rarely, never. That made spreading your money across twelve
#: coins a free lunch: a HIGHER median return and a third of the variance, with
#: nothing given up for it. A crypto game where the market never moves as one
#: is missing the thing crypto is actually famous for.
#:
#: So there is one extra number a day - the tide - and every coin rides it
#: according to its class. The crucial decision is that the tide is carved OUT
#: of each coin's existing volatility rather than piled on top: a single coin
#: swings about as hard as it always did, and the correlation comes for free
#: from redistributing variance the market already had. Piling it on would just
#: make everything louder, which is not the same thing as making it move
#: together.
#:
#: How much of a coin's daily movement is the market's rather than its own.
#:
#: Chosen by sweeping it, not by feel. At 0.30 the shelter diversifying buys
#: falls from 72% of the risk to 58% - the free lunch is priced without being
#: abolished - the board visibly moves as one on 12% of days rather than 7%,
#: and solvency for a sensible strategy stays at 51%, inside the band. Higher
#: settings price the lunch harder and cost more than they are worth: at 0.45
#: the median run goes negative.
#:
#: **What this does NOT do, measured five ways.** The pitch for the tide was
#: that it would create a decision - rotate to USDC in a bear, tilt by beta,
#: bank ahead of the weather. It does not. A bot handed tomorrow's regime in
#: advance does WORSE than one that ignores the weather entirely, whichever of
#: those it does with the knowledge. The reason is structural and worth writing
#: down: this market's edge is mean reversion, the debt compounds at 10% a day
#: so being out of the market is never affordable, and a factor that moves
#: everything at once does not interact with either. The tide is texture and a
#: price on diversifying. It is not a new decision, and a comment claiming
#: otherwise would be a comment that reads well and is false.
TIDE_SHARE = 0.30
#: What is left for the coin itself. Squared, the two shares sum to one, which
#: is what keeps the volatility budget honest.
IDIO_SHARE = math.sqrt(1.0 - TIDE_SHARE ** 2)
#: How often the tide re-rolls. Lower than TREND_FLIP on purpose: a market
#: regime should outlast any one coin's run, so that "everything is falling"
#: is a weather system you can be caught in rather than a bad afternoon.
TIDE_FLIP = 0.16
#: How much of the TIDE's OWN variance is the persistent regime rather than
#: today's noise around it. The two square to one for the same reason the coin
#: split does: the tide has a fixed variance budget of its own, and this decides
#: how much of it is weather you can see coming versus weather you cannot.
#:
#: The first version got this wrong in a way worth recording. The regime was
#: drawn at full strength REGARDLESS of TIDE_SHARE, so it was piled on top of
#: every coin's volatility instead of carved out of it - which inflated a single
#: coin's daily swing by 12% and, worse, meant the tide could not be turned down
#: at all. Turning the dial to zero left the weather exactly where it was. A
#: constant that does not control the thing it is named after is not a dial, it
#: is a decoration.
TIDE_REGIME = 0.85
#: How hard each class of coin rides it.
#:
#: Normalised so the average risky coin has a beta of 1.0 - the first table
#: averaged 1.23 and quietly inflated every coin's volatility by 12%, which is
#: precisely the "made it louder instead of making it move together" failure
#: this design is supposed to avoid. USDC is zero, and that is the whole point
#: of it: the one asset on the board that does not care what the market does
#: finally has a reason to exist.
TIDE_BETA: Dict[str, float] = {"meme": 1.22, "alt": 0.94, "major": 0.69, "stable": 0.0}
#: What a turning tide is called, and what it is worth knowing about.
TIDE_LEVELS = (
    (0.65, "EUPHORIA", "Everything is green. Nobody is asking why."),
    (0.22, "BULL", "The whole board is drifting up."),
    (-0.22, "CHOP", "No direction. Coins are on their own."),
    (-0.65, "BEAR", "The whole board is leaking."),
    (-9.9, "CAPITULATION", "Everything is red. Everyone is selling everything."),
)


#: A typical risky coin's daily volatility, so the tide has a sensible scale of
#: its own rather than borrowing one coin's.
TYPICAL_VOL = math.fsum(c.vol for c in COINS if c.symbol != "USDC") / max(
    1, sum(1 for c in COINS if c.symbol != "USDC"))


def beta_of(symbol: str) -> float:
    """How hard this coin rides the tide."""
    from .gear import CLASS_OF

    return TIDE_BETA.get(CLASS_OF.get(symbol, "alt"), 1.0)


def tide_level(tide_trend: float) -> str:
    """What the weather is called, from the regime rather than today's draw.

    The regime is the part worth naming: today's number is noise around it, and
    a label that flickered daily would be a label nobody could act on.
    """
    scaled = tide_trend / max(1e-9, TYPICAL_VOL * TIDE_SHARE * TIDE_REGIME)
    for threshold, name, _ in TIDE_LEVELS:
        if scaled >= threshold:
            return name
    return TIDE_LEVELS[-1][1]


def tide_blurb(tide_trend: float) -> str:
    scaled = tide_trend / max(1e-9, TYPICAL_VOL * TIDE_SHARE * TIDE_REGIME)
    for threshold, _, blurb in TIDE_LEVELS:
        if scaled >= threshold:
            return blurb
    return TIDE_LEVELS[-1][2]


class MarketState:
    """The drifting level of every coin, and which way each is running."""

    def __init__(self, rng: random.Random) -> None:
        self.levels: Dict[str, float] = {}
        #: the current run for each coin: a daily push that persists for a few
        #: days and then re-rolls, so movement arrives in arcs rather than fuzz
        self.trends: Dict[str, float] = {c.symbol: 0.0 for c in COINS}
        #: the market's own run, and today's draw from it. Both ride the save:
        #: a reload that reshuffled the weather would be a reload that rerolled
        #: the run, which is the one thing this game does not allow.
        self.tide_trend: float = 0.0
        self.tide: float = 0.0
        for c in COINS:
            # Start in the middle of the range - but clamped to the coin's own
            # bounds. Unclamped, USDC opened anywhere from $0.78 to $1.21, which
            # made the one asset that exists to be safe the best trade on the
            # board: buy the "stablecoin" at $0.86, wait for it to revert, take
            # a risk-free 16%. drift() clamped it every later day; day one did
            # not, so the exploit was only ever available on the first screen.
            self.levels[c.symbol] = max(c.low, min(c.mid * rng.uniform(0.8, 1.2), c.high))
        #: The last few days of every coin's level - filled AFTER the opening
        #: levels exist, which the first version of this line did not do. The
        #: game has always moved like this and never let anyone see it: a market
        #: game showing one number per coin is a trading screen with the chart
        #: switched off, and a rumour that a coin is running is unusable if you
        #: cannot check whether it has been.
        self.history: Dict[str, List[float]] = {c.symbol: [self.levels[c.symbol]]
                                                for c in COINS}

    def roll_tide(self, rng: random.Random) -> None:
        """One number for the whole board, before any coin moves.

        Drawn once per day and shared by everything, which is the entire
        mechanism: correlation is not something coins do to each other, it is
        something they all do to the same number.
        """
        budget = TYPICAL_VOL * TIDE_SHARE
        if rng.random() < TIDE_FLIP:
            self.tide_trend = rng.gauss(0.0, budget * TIDE_REGIME)
        self.tide = self.tide_trend + rng.gauss(
            0.0, budget * math.sqrt(max(0.0, 1.0 - TIDE_REGIME ** 2)))

    def drift(self, rng: random.Random) -> None:
        """One day of movement: the tide, a run, some noise, and a pull back."""
        self.roll_tide(rng)
        for c in COINS:
            level = self.levels[c.symbol]
            if c.symbol == "USDC":
                # immune by construction, and that is what it is FOR: the one
                # thing on the board that does not care which way the tide runs
                self.levels[c.symbol] = max(0.97, min(1.03, level * rng.uniform(0.997, 1.003)))
                continue
            # the run re-rolls now and then; the rest of the time it carries on,
            # which is what turns a walk into a pump and then a dump
            if rng.random() < TREND_FLIP:
                self.trends[c.symbol] = rng.gauss(0.0, c.vol * TREND_STRENGTH)
            # the coin's own noise is REDUCED to make room for the tide, so the
            # two shares square to one and a coin swings as hard as it always did
            own = rng.gauss(0.0, c.vol * IDIO_SHARE)
            step = self.trends[c.symbol] + own + beta_of(c.symbol) * self.tide
            # pull back toward the middle so nothing drifts off forever
            pull = c.pull * math.log(c.mid / level) if level > 0 else 0.0
            level *= math.exp(step + pull)
            self.levels[c.symbol] = max(c.low * 0.4, min(level, c.high * 1.6))
        self.remember()

    def remember(self) -> None:
        """Append today's levels to the history, keeping only what a chart needs."""
        for c in COINS:
            past = self.history.setdefault(c.symbol, [])
            past.append(self.levels[c.symbol])
            if len(past) > HISTORY_KEPT:
                del past[:len(past) - HISTORY_KEPT]

    def running(self, symbol: str) -> float:
        """How hard this coin is currently running, and which way."""
        return self.trends.get(symbol, 0.0)

    def apply(self, symbol: str, factor: float, coin: Coin) -> None:
        """A shock moves the real level, so it persists beyond one station.

        It also **corrects today's history point** rather than adding one. The
        shock lands after ``drift`` has already recorded the day, so without
        this the chart quietly kept the pre-shock number: a coin could double
        on a headline and the sparkline would show the day it did not move.
        The one bad day in a fortnight is exactly the day a chart exists to
        show, and it was the only one being left out.
        """
        level = self.levels[symbol] * factor
        self.levels[symbol] = max(coin.low * 0.15, min(level, coin.high * 2.2))
        past = self.history.get(symbol)
        if past:
            past[-1] = self.levels[symbol]      # the same day, corrected


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
