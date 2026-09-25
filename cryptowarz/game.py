"""Game state and the rules that move it.

Thirty days, ten stations, one wallet.  Buy where a coin is cheap, sell where it
is dear, and be somewhere else when the SEC arrives.

Two numbers shape every decision:

**Capacity.** Your hot wallet holds a limited dollar amount *at cost*.  Selling
frees it up; a coin doubling in value does not.  This is what stops the game
becoming "put everything in the best trade" - you are always choosing which
edge is worth the space.

**The Shark.** Debt compounds at 10% a day and never forgives.  Borrowing early
is usually correct and always dangerous; the loan that got you started is often
the thing that eats the win.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .coins import COINS, Coin, coin
from .market import Market, MarketState, generate
from .stations import STATIONS, Station, station

DAYS = 30            # tier 1; a tier can shorten the run
START_CASH = 2_000.0
START_DEBT = 5_500.0
#: What your pockets hold, in CASH. The crypto wallet has no ceiling at all.
#:
#: This is the inversion the game was missing. A cold wallet that refuses to
#: hold another coin is not a thing that exists, and the old cap did something
#: worse than being unrealistic: it made free money disappear. An airdrop
#: landed on a full wallet and expired. A prize was clipped. You watched a coin
#: run and could not buy it because a number said your wallet was full.
#:
#: Now the only limit is what a person can physically walk around with. Coins
#: are weightless, cash is not - which is what the vault has always been for.
START_CASH_CAP = 50_000.0
#: Kept as the old name for one release so an existing save still reads.
START_CAPACITY = 25_000.0
SHARK_RATE = 0.10        # per day, compounding, no mercy
VAULT_RATE = 0.04        # per day, if you can bear to leave it behind
SUBWAY_FARE = 2.90       # it is still the best deal in the city
#: Reserved on top of the fare when sizing a "max" buy. Reserving the fare
#: exactly is not enough: price * (cash - fare) / price lands a fraction of a
#: cent above cash - fare, leaving $2.8999999999 and a player who cannot afford
#: the very fare the reserve existed to protect. A cent is beneath notice in a
#: game with a $25,000 wallet and removes the whole class of boundary failure.
FARE_BUFFER = 0.01

# ------------------------------------------------------------------ the card
#: Rides you can buy before you need them, and what a book of them costs.
#:
#: The subway has always sold fares in advance, and the game had no answer to
#: the one situation everybody in this city has been in: money in the bank,
#: nothing in your pocket, standing the wrong side of a turnstile. Rides bought
#: ahead are insurance against exactly that - and they pair with playing broke,
#: because the cheapest way to look poor is to actually be carrying nothing.
OMNY_RIDES = 5
#: Five rides for the price of four and a half. Buying ahead should be worth
#: something, or nobody would plan.
OMNY_PRICE = 13.00

# ------------------------------------------------------------------- the dice
#: Somebody runs dice on the platform every few rides. There is no stake: the
#: worst outcome is nothing, so this is a flourish rather than a decision, and
#: it is deliberately not a way to gamble your way out of a bad run.
DICE_EVERY = 4           # rides between offers
DICE_SIDES = 6           # an actual die. Call a number, one to six
DICE_TOP_PRIZE = 1_450.0 # what calling it exactly is worth

#: How close you got, and what share of the top prize that is worth. Binary
#: hit-or-miss made nine calls in ten pay nothing, which is a slot machine
#: rather than a call - you read the result and learned nothing from it. Graded
#: by distance, almost every call tells you something and most of them pay
#: something, and the number you say out loud starts to matter.
#:
#: Retuned for six sides. A d6 lands close far more often than a d10, so the
#: same ladder and the same pot would have paid half as much again; the rungs
#: are tighter and the pot is smaller, which puts one offer back at about $536
#: for the best call and $396 for the worst - where the ten-sided version sat.
#:
#: There is a quiet consequence worth leaving in: middle numbers are worth more
#: than 1 or 6, because a call at the edge has nowhere to be close on one side.
#: On six sides that gap is wider than it was on ten - $536 against $396 - so
#: it is a little easier to notice, which is the right direction for a detail
#: that rewards paying attention.
DICE_LADDER = (
    (0, "DEAD ON", 1.00),
    (1, "ONE OFF", 0.40),
    (2, "CLOSE",   0.18),
    (3, "WARM",    0.06),
)
#: Opening calls that put a player on a streak, and what a streak pays.
#: Not every ride and not the same amount: a fixed payment on a metronome
#: stopped being a windfall by the third station and started being a salary.
HOT_HAND = (4, 2)
HOT_HAND_CHANCE = 0.75            # roughly three rides in four
HOT_HAND_MIN = 250.0
HOT_HAND_MAX = 10_000.0

# -------------------------------------------------------------------- a word
#: How often the man on the dice has heard something, and how often what he
#: heard is right ABOUT THE RUN. Deliberately not an oracle: a tip you can bank
#: is not information, it is an instruction, and the whole point is deciding
#: whether to believe it.
#:
#: What the player actually experiences is weaker than TIP_ACCURACY, and that is
#: worth knowing rather than guessing at. Measured against what the price really
#: does over the next three days, tips land about 59% of the time - because a
#: run pushes at roughly half a coin's daily noise, so three days of noise can
#: and does bury it. A 59/41 edge is a real one and wrong often enough that
#: following a whisper stays a decision. Raising accuracy to 90% only moved the
#: felt hit rate to 61%, so the honest lever here is small.
TIP_CHANCE = 0.60
TIP_ACCURACY = 0.85
#: A coin has to be running hard RELATIVE TO ITS OWN NOISE before anyone gossips
#: about it - a 4% run is a rumour on Bitcoin and a rounding error on WIF.
TIP_MIN_RUN = 0.5
#: How many days a whisper is worth anything.
TIP_FRESH_FOR = 3

# ------------------------------------------------------------------ the wheel
#: Somebody has a prize wheel set up on the mezzanine at some stops. ONE SPIN
#: PER STOP PER RUN, which is the whole design: it pays for going somewhere you
#: have not been, not for bouncing between two stations. Without that it is a
#: lever you pull instead of a map you explore, and a bigger map earns nothing.
#:
#: (label, weight, cash, gives gear)
WHEEL: Tuple[Tuple[str, float, float, bool], ...] = (
    ("BUST",    24.0,     0.0, False),
    ("SMALL",   30.0,   300.0, False),
    ("MIDDLE",  22.0,   750.0, False),
    ("BIG",     13.0, 1_600.0, False),
    ("JACKPOT",  7.0, 3_400.0, False),
    ("GEAR",     4.0,     0.0, True),
)
WHEEL_LINES = {
    "BUST":    "It lands between two wedges. The man shrugs.",
    "SMALL":   "A small one. He counts it out slowly, to make it last.",
    "MIDDLE":  "A decent wedge. He looks mildly disappointed for you.",
    "BIG":     "The crowd makes a noise. He stops smiling.",
    "JACKPOT": "JACKPOT. He looks at the wheel, then at you, then at the wheel.",
    "GEAR":    "The wheel stops on the wedge nobody ever hits.",
}

def dice_tier(distance: int) -> tuple:
    """How close that was, as (label, share of the top prize)."""
    for reach, label, share in DICE_LADDER:
        if distance <= reach:
            return (label, share)
    return ("", 0.0)


class GameOver(Exception):
    """Raised when the run ends early - wiped out, or caught for good."""


@dataclass
class Holding:
    qty: float = 0.0
    cost: float = 0.0     # total spent, so capacity and average price are exact

    @property
    def avg_price(self) -> float:
        return self.cost / self.qty if self.qty > 0 else 0.0


@dataclass
class Player:
    cash: float = START_CASH
    debt: float = START_DEBT
    vault: float = 0.0
    #: the cash ceiling - what your pockets hold. Coins are not capped.
    cash_cap: float = START_CASH_CAP
    #: fares already paid for. The turnstile takes these when your pockets
    #: cannot, which is the whole point of buying them early.
    rides: int = 0
    wallet: Dict[str, Holding] = field(default_factory=dict)
    vpn: int = 0          # each level cuts the odds of trouble

    def holding(self, symbol: str) -> Holding:
        return self.wallet.setdefault(symbol.upper(), Holding())

    def drop_empty(self) -> None:
        """Forget positions that have gone to zero.

        An empty bag is not a holding. Keeping the key around made the live
        wallet and a reloaded one disagree - a save prunes them, memory did
        not - which is harmless right now and exactly the sort of difference
        that turns into a confusing bug the first time something iterates the
        wallet and assumes every key is a real position.
        """
        for symbol in [s for s, h in self.wallet.items() if h.qty <= 1e-12 and h.cost <= 1e-12]:
            del self.wallet[symbol]

    @property
    def used_capacity(self) -> float:
        """What the wallet is carrying at cost. Reported, never enforced."""
        return math.fsum(h.cost for h in self.wallet.values())

    @property
    def carry_room(self) -> float:
        """How much more cash you could pick up before your pockets are full."""
        return max(0.0, self.cash_cap - self.cash)

    @property
    def over_carrying(self) -> float:
        """Cash you are carrying beyond what the pockets are meant to hold.

        A windfall you did not ask for - a wallet on the floor, a whale paying
        over the odds - is never confiscated for being inconvenient. It puts
        you over instead, which is a problem you can see and solve by finding a
        vault, rather than money the game quietly ate.
        """
        return max(0.0, self.cash - self.cash_cap)

    def portfolio_value(self, market: Market) -> float:
        return math.fsum(h.qty * market.price(sym) for sym, h in self.wallet.items() if h.qty > 0)

    def net_worth(self, market: Market) -> float:
        return self.cash + self.vault + self.portfolio_value(market) - self.debt


@dataclass
class Game:
    seed: Optional[int] = None
    day: int = 1
    player: Player = field(default_factory=Player)
    station: Station = field(default_factory=lambda: station("14 St-Union Sq"))
    log: List[str] = field(default_factory=list)
    finished: bool = False
    #: difficulty level, 1-5; see progress.TIERS
    tier: int = 1
    #: how hard the city is playing; see progress.DIFFICULTIES. Free to choose
    #: on any run, unlike a tier, and it pays the board a different multiple.
    difficulty: str = "normal"
    #: one carried-over advantage, unlocked by an achievement
    perk: Optional[str] = None
    #: earned gear, as {coin class: level}; see gear.py
    gear: Dict[str, int] = field(default_factory=dict)
    #: what happened this run, for achievements and the end-of-run story
    stats: dict = field(default_factory=dict)
    rng: random.Random = field(init=False)
    state: MarketState = field(init=False)
    market: Market = field(init=False)

    def __post_init__(self) -> None:
        from .progress import PERK_BY_KEY, TIER_BY_LEVEL

        from .progress import difficulty_of

        tier = TIER_BY_LEVEL.get(self.tier, TIER_BY_LEVEL[1])
        hardness = difficulty_of(self.difficulty)
        self.difficulty = hardness.key          # normalise an unknown key
        self.player.debt = tier.debt * hardness.debt_mult
        self.player.cash += hardness.cash
        #: the tier's number is what your POCKETS hold now; the crypto wallet
        #: has no ceiling. Doubled from the old crypto cap so tier 1 starts at
        #: the $50,000 the design calls for.
        self.starting_cash_cap = tier.capacity * 2.0
        self.player.cash_cap = self.starting_cash_cap
        self.days = tier.days
        # the two axes multiply: a hard run of a hot tier really is both
        self.heat_mult = tier.heat_mult * hardness.heat_mult

        if self.perk and self.perk in PERK_BY_KEY:
            if self.perk == "seed_round":
                self.player.cash += 2_000.0
            elif self.perk == "cold_storage":
                self.player.cash_cap += 15_000.0

        self.stats = {"stations": {self.station.name},
                      "visits": {self.station.name: 1},
                      "raids": 0, "peak_worth": 0.0,
                      "best_multiple": 0.0, "worth_by_day": [],
                      "dice_picks": [], "dice_days": [], "hot_hand": False}
        self.hot_hand = False
        #: set by spin_wheel to a gear class the caller should bank, or None.
        #: The Game does not own the profile, so it cannot bank it itself.
        self.wheel_award: Optional[str] = None
        #: the same, for a piece bought from a dealer.
        self.gear_award: Optional[str] = None
        #: somebody standing in front of you, waiting for an answer. While this
        #: is set the run is stopped: see `_not_now`. It rides the save, so a
        #: reload cannot be used to walk away from it.
        self.pending: Optional[dict] = None
        #: what you are carrying, by key; see encounter.WEAPONS. One at a time.
        self.weapon: Optional[str] = None
        self.rng = random.Random(self.seed)
        self.state = MarketState(self.rng)
        self.market = generate(self.station, self.rng, self.state,
                               luck=self._luck_by_symbol())
        self._mark_stats()
        self.say(f"Day 1. You're at {self.station.name} with "
                 f"${self.player.cash:,.0f} and a ${self.player.debt:,.0f} problem.")
        if self.market.headline:
            self.say(self.market.headline)

    def lose_a_day(self) -> None:
        """A day gone that you did not spend travelling.

        Two things in the game can take one - a stopped train and a beating -
        and both used to do it by incrementing the clock alone. That froze the
        market for a day, which is both wrong fiction and a small free lunch:
        prices cannot move against a player who is unconscious. It also broke
        the one-price-per-day invariant the sparklines are drawn from, which is
        how it was finally noticed.
        """
        self.day += 1
        self.player.debt *= (1.0 + self.shark_rate)
        self.player.vault *= (1.0 + VAULT_RATE)
        self.state.drift(self.rng)
        self.market = generate(self.station, self.rng, self.state,
                               luck=self._luck_by_symbol())
        self._mark_stats()
        self._end_if_over()

    def _end_if_over(self) -> None:
        """Close the run the moment the clock passes the last day.

        The check used to live only in ``travel``, which was true while the
        only way to spend a day was to ride somewhere. A stopped train and a
        beating also take one - and a beating arrives inside a standoff, whose
        resolution had no check at all. So a run could walk past day thirty and
        simply keep going: the header clamps the day to the last one, so it
        reads as a game that has stopped moving, the end screen never comes,
        and the score is never banked. Every day that passes now goes through
        one place that asks whether the run is over.
        """
        if not self.finished and self.day > self.days:
            self.finished = True

    def _not_now(self) -> None:
        """Refuse anything that is not an answer while somebody is waiting.

        Every door out of the standoff goes through `resolve`. Without this the
        player could simply buy, sell and ride away from a man holding a knife,
        which would make the whole encounter a message rather than a decision.
        """
        if self.pending:
            raise ValueError("there is somebody in front of you. Answer him first")

    @property
    def standoff(self) -> Optional[dict]:
        return self.pending

    def choices(self) -> List[dict]:
        from .encounter import choices
        return choices(self)

    def resolve(self, choice: str) -> List[str]:
        from .encounter import resolve
        return resolve(self, choice)

    def buy_weapon(self, key: str) -> List[str]:
        """Buy something to carry. One at a time, and only where they sell it."""
        from .encounter import FOR_SALE, WEAPON_BY_KEY, weapon_of

        self._not_now()
        if not self.station.has_upgrades:
            raise ValueError("nobody here sells that. Try a stop with a shop")
        if key not in FOR_SALE:
            raise ValueError(f"no such thing; they stock {', '.join(FOR_SALE)}")
        want = WEAPON_BY_KEY[key]
        if self.player.cash < want.price:
            raise ValueError(f"the {want.name} is ${want.price:,.0f} and you have "
                             f"${self.player.cash:,.2f}")
        had = weapon_of(self.weapon)
        self.player.cash -= want.price
        self.weapon = want.key
        message = f"You buy the {want.name}. ${want.price:,.0f}, no receipt."
        if had:
            message += f" The {had.name.lower()} goes in a bin on the way out."
        self.say(message)
        return [message]

    # --------------------------------------------------------------- tracking

    def _mark_stats(self) -> None:
        worth = self.player.net_worth(self.market)
        self.stats["peak_worth"] = max(self.stats.get("peak_worth", 0.0), worth)
        self.stats.setdefault("worth_by_day", []).append(round(worth, 2))

    @property
    def luck(self) -> float:
        """The best single bonus you have right now, 0.0 to 0.15.

        Gear you are holding for, or the nerve of whatever is in your coat -
        whichever is larger, and never the two added together. "Never a sum" is
        the rule the whole luck system rests on, and a weapon is not an
        exception to it: what carrying something buys is a floor under your
        luck, which matters most early, when you have no gear at all.
        """
        from .encounter import nerve
        from .gear import best_luck
        return max(best_luck(self.gear, self.player.wallet), nerve(self))

    def _luck_by_symbol(self) -> Dict[str, float]:
        from .gear import luck_by_symbol
        return luck_by_symbol(self.gear, self.player.wallet)

    @property
    def fare(self) -> float:
        return 0.0 if self.perk == "metrocard" else SUBWAY_FARE

    @property
    def shark_rate(self) -> float:
        """The Shark's daily rate: the difficulty's, less the Fixer's discount.

        The discount is a ratio rather than a fixed rate so that it is worth
        the same everywhere. At Express it still lands on exactly the 8.5% the
        perk has always promised.
        """
        from .progress import difficulty_of
        rate = difficulty_of(self.difficulty).shark
        return rate * 0.85 if self.perk == "fixer" else rate

    # ------------------------------------------------------------------ log

    def say(self, message: str) -> None:
        self.log.append(message)
        if len(self.log) > 200:
            del self.log[: len(self.log) - 200]

    # --------------------------------------------------------------- trading

    def max_buyable(self, symbol: str) -> float:
        """Most you could buy - always leaving the subway fare behind.

        Spending the literal last cent strands you at a station with no way to
        reach a better price, which is a dead end rather than a decision. The
        fare is cheap enough that reserving it costs nothing real.
        """
        price = self.market.price(symbol)
        if price <= 0:
            return 0.0
        spendable = max(0.0, self.player.cash - self.fare - FARE_BUFFER)
        return max(0.0, spendable / price)      # coins are weightless

    def buy(self, symbol: str, qty: float) -> str:
        self._not_now()
        symbol = symbol.upper()
        if symbol not in {c.symbol for c in COINS}:
            raise ValueError(f"nobody here trades {symbol}")
        if qty <= 0:
            raise ValueError("buy how much?")
        price = self.market.price(symbol)
        cost = price * qty
        if cost > self.player.cash + 1e-9:
            raise ValueError(f"that costs ${cost:,.2f} and you have ${self.player.cash:,.2f}")
        h = self.player.holding(symbol)
        h.qty += qty
        h.cost += cost
        self.player.cash -= cost
        return f"Bought {qty:,.6f} {symbol} at ${price:,.6f} for ${cost:,.2f}"

    def max_sellable(self, symbol: str) -> float:
        """The most of a coin you can sell and still carry the proceeds.

        The counterweight to an uncapped crypto wallet, and the reason the
        vault matters: coins are weightless, cash is not, so turning a big
        position back into money is a logistical problem rather than a button.
        """
        price = self.market.price(symbol)
        held = self.player.holding(symbol).qty
        if price <= 0:
            return held
        return max(0.0, min(held, self.player.carry_room / price))

    def sell(self, symbol: str, qty: float) -> str:
        self._not_now()
        symbol = symbol.upper()
        h = self.player.holding(symbol)
        if qty <= 0:
            raise ValueError("sell how much?")
        if qty > h.qty + 1e-12:
            raise ValueError(f"you only hold {h.qty:,.6f} {symbol}")
        price = self.market.price(symbol)
        proceeds = price * qty
        # you cannot carry away more than your pockets hold. This is the whole
        # counterweight to a bottomless crypto wallet: getting OUT of a big
        # position takes trips, and a vault.
        if proceeds > self.player.carry_room + 1e-9:
            room = self.player.carry_room
            most = self.max_sellable(symbol)
            raise ValueError(
                f"that comes to ${proceeds:,.2f} and you can only carry another "
                f"${room:,.2f}. Sell {most:,.6f} {symbol} or vault what you have")
        # release capacity proportionally, so partial sells behave sanely
        released = h.cost * (qty / h.qty) if h.qty > 0 else 0.0
        profit = proceeds - released
        h.qty -= qty
        h.cost -= released
        if h.qty <= 1e-12:
            h.qty, h.cost = 0.0, 0.0
        self.player.drop_empty()
        self.player.cash += proceeds
        if released > 0:
            self.stats["best_multiple"] = max(self.stats.get("best_multiple", 0.0),
                                              proceeds / released)
        verb = "made" if profit >= 0 else "lost"
        return (f"Sold {qty:,.6f} {symbol} at ${price:,.6f} for ${proceeds:,.2f} "
                f"({verb} ${abs(profit):,.2f})")

    # ----------------------------------------------------------------- wheel

    @property
    def wheel_ready(self) -> bool:
        """A wheel at this stop that you have not already spun this run."""
        return (self.station.has_wheel
                and self.station.name not in (self.stats.get("wheels") or []))

    def spin_wheel(self) -> List[str]:
        """One spin. Sets ``wheel_award`` to a gear class on a rare wedge."""
        self._not_now()
        if not self.wheel_ready:
            raise ValueError("no wheel here, or you've already had your spin")

        self.wheel_award = None
        self.stats.setdefault("wheels", []).append(self.station.name)
        labels = [w[0] for w in WHEEL]
        weights = [w[1] for w in WHEEL]
        label = self.rng.choices(labels, weights=weights, k=1)[0]
        _, _, cash, gives_gear = next(w for w in WHEEL if w[0] == label)

        messages = [f"You spin. {WHEEL_LINES[label]}"]
        if cash > 0:
            # the same gear bonus the dice pay, for the same reason
            messages.extend(self.gift(cash * (1.0 + self.luck), f"Wheel - {label}"))
        if gives_gear:
            from .gear import GEAR, GEAR_BY_KEY, winning_class
            from .progress import counts_for_progress
            if not counts_for_progress(self):
                messages.append("It would have been a piece of gear. This run keeps nothing.")
            else:
                # the class you are actually carrying, so the wheel reinforces a
                # style rather than handing out a random fifth of a collection
                cls = winning_class(self) or self.rng.choice([g.key for g in GEAR])
                self.wheel_award = cls
                messages.append(f"{GEAR_BY_KEY[cls].name}. That is a win banked "
                                f"toward it, and they are not given away.")
        elif not cash:
            messages.append("Nothing. It cost you nothing either.")
        for m in messages:
            self.say(m)
        return messages

    # ------------------------------------------------------------- dead end

    @property
    def stranded(self) -> bool:
        """No fare, nothing to sell, and no way to raise it at this stop.

        The game can genuinely corner you: an SEC raid takes the bags, a gas
        spike takes the cash, and you are standing on a platform that has no
        Shark and no vault with $1.40 in your pocket. Every other loss in this
        game is a decision that went wrong. This one is a wall, and a wall the
        player cannot see is just a frozen screen with a working button bar.
        """
        if self.finished or self.player.cash + 1e-9 >= self.fare:
            return False
        if self.player.rides > 0:
            return False                       # a fare already paid for
        if any(h.qty > 0 for h in self.player.wallet.values()):
            return False                       # something to sell is a way out
        if self.station.has_vault and self.player.vault > 0:
            return False
        if self.station.has_shark and self.borrowable() > 0:
            return False
        return True

    def give_up(self) -> List[str]:
        """End the run here and let it be scored for what it is.

        Deliberately not a way to erase the run: it finishes, so it is graded,
        recorded and - if it was ranked - it spends the slot. Walking away from
        a bad position is allowed. Pretending it never happened is not.
        """
        if self.finished:
            return []
        self.finished = True
        message = ("You give up the run at "
                   f"{self.station.name} on day {self.day}. That's it.")
        self.say(message)
        return [message]

    # --------------------------------------------------------------- broker

    def buy_gear(self) -> List[str]:
        """Buy a banked gear win, at a price that costs you the run's score."""
        self._not_now()
        from .gear import BROKER_PRICE, GEAR_BY_KEY, broker_offer

        cls = broker_offer(self)
        if cls is None:
            if self.stats.get("gear_bought"):
                raise ValueError("he only has the one, and you bought it")
            if not self.station.has_upgrades:
                raise ValueError("nobody's dealing here. Try a stop with a shop")
            raise ValueError(f"he wants {BROKER_PRICE:,.0f} in cash, and not a dollar less")
        self.player.cash -= BROKER_PRICE
        self.stats["gear_bought"] = True
        self.gear_award = cls
        piece = GEAR_BY_KEY[cls]
        message = (f"A million dollars, in a station. He hands over the "
                   f"{piece.name} and is gone before you turn around.")
        self.say(message)
        return [message]

    # ----------------------------------------------------------------- tips

    @property
    def tip(self) -> Optional[Dict[str, object]]:
        """A rumour you were given recently, or None once it has gone stale."""
        rumour = self.stats.get("tip")
        if not rumour:
            return None
        if self.day - int(rumour.get("day", 0)) > TIP_FRESH_FOR:
            return None
        return rumour

    def _hear_something(self) -> List[str]:
        """The man on the dice passes on what he heard. Sometimes it is true."""
        if self.rng.random() > TIP_CHANCE:
            return []
        running = [(c.symbol, self.state.running(c.symbol)) for c in COINS
                   if c.symbol != "USDC"
                   and abs(self.state.running(c.symbol)) >= c.vol * TIP_MIN_RUN]
        if not running:
            return []
        symbol, trend = max(running, key=lambda st: abs(st[1]))
        truthful = self.rng.random() < TIP_ACCURACY
        going_up = (trend > 0) if truthful else (trend <= 0)
        self.stats["tip"] = {"symbol": symbol, "up": going_up, "day": self.day}
        word = "about to run" if going_up else "about to fall over"
        return [f'"Word is {coin(symbol).name} is {word}." He might be wrong. '
                f"He usually isn't."]

    # ----------------------------------------------------------------- dice

    @property
    def dice_ready(self) -> bool:
        """The dice come around a few rides after the last time you played.

        Measured from the last roll rather than off the calendar: a signal
        delay costs two days instead of one, and a plain `day % 4` offer
        silently skipped every time one landed on the wrong day. Counting from
        the last roll also means an offer you ignore keeps standing.
        """
        days = self.stats.get("dice_days") or []
        return self.day - (days[-1] if days else 0) >= DICE_EVERY

    def gift(self, value: float, why: str) -> List[str]:
        """Hand over free crypto, at fair value.

        Fair value rather than zero cost on purpose: a bag with no cost basis
        would take up no wallet room and make every sale an infinite multiple.
        Free means you did not pay cash for it, not that it weighs nothing.
        """
        from .coins import COINS

        target = self.rng.choice([c for c in COINS if c.symbol != "USDC"])
        price = self.market.price(target.symbol)
        if price <= 0:
            return []
        h = self.player.holding(target.symbol)
        h.qty += value / price
        h.cost += value
        return [f"{why}: {value / price:,.6f} {target.symbol} (~${value:,.2f})."]

    def _streak_gift(self) -> List[str]:
        """Sometimes, and never the same amount twice.

        The draw is squared, which pulls most payouts down toward the floor and
        leaves the ceiling rare - a flat draw made five figures ordinary, and a
        windfall you can count on is not a windfall.
        """
        if self.rng.random() > HOT_HAND_CHANCE:
            return []
        draw = self.rng.random() ** 2
        return self.gift(HOT_HAND_MIN + (HOT_HAND_MAX - HOT_HAND_MIN) * draw,
                         "The turnstile blesses you")

    def roll_dice(self, pick: int) -> List[str]:
        """Call a number. Costs nothing, and once in a while pays."""
        self._not_now()
        if not self.dice_ready:
            raise ValueError("nobody's running dice right now")
        try:
            pick = int(pick)
        except (TypeError, ValueError):
            raise ValueError(f"call a number from 1 to {DICE_SIDES}")
        if not 1 <= pick <= DICE_SIDES:
            raise ValueError(f"call a number from 1 to {DICE_SIDES}")

        self.stats.setdefault("dice_days", []).append(self.day)
        picks = self.stats.setdefault("dice_picks", [])
        picks.append(pick)
        rolled = self.rng.randint(1, DICE_SIDES)

        distance = abs(rolled - pick)
        label, share = dice_tier(distance)
        messages = [f"You call {pick}. The dice come up {rolled}."]
        if share > 0:
            # gear pays out here too: a bag you are geared for is the thing that
            # makes the platform friendlier, and the dice are on the platform
            value = DICE_TOP_PRIZE * share * (1.0 + self.luck)
            bonus = f" (+{self.luck:.0%} on your gear)" if self.luck > 0 else ""
            messages.extend(self.gift(
                value, f"{label} - {share:.0%} of the pot{bonus}"))
        else:
            messages.append(f"Off by {distance}. Nothing, and it was free to play.")
        messages.extend(self._check_streak(picks))
        for m in messages:
            self.say(m)
        return messages

    def _check_streak(self, picks: List[int]) -> List[str]:
        if self.hot_hand or tuple(picks[:len(HOT_HAND)]) != HOT_HAND:
            return []
        self.hot_hand = True
        self.stats["hot_hand"] = True
        return ["", "The dice stop mid-air.",
                "GOD MODE. The turnstile swings open for you from now on - "
                "free crypto every ride.",
                "This run is a sandbox now: it posts nothing and unlocks nothing."]

    # ---------------------------------------------------------------- money

    def borrow_limit(self) -> float:
        """The most total debt The Shark will carry on you.

        Measured against what he could actually seize - cash, vault and the
        bags in your wallet - rather than net worth. Net worth already
        subtracts the debt, so the more you owed the less you could borrow,
        and since a run opens $3,500 underwater the ceiling sat below the
        opening loan: borrowing was refused every time a player first tried
        it, while the button sat there inviting them to.
        """
        seizable = (self.player.cash + self.player.vault
                    + self.player.portfolio_value(self.market))
        # The floor is twice the opening loan on purpose. Set any lower and the
        # Shark is dead UI: a $6,000 ceiling is already below day two's $6,050
        # of debt, so the button would exist purely to refuse you. At twice the
        # opening loan the classic move is available - borrow big, trade hard,
        # repay before the interest catches you - which is a real decision and
        # usually a trap, rather than no decision at all.
        return max(START_DEBT * 2.0, seizable * 2.0)

    def borrowable(self) -> float:
        """How much more he will actually hand over right now."""
        return max(0.0, self.borrow_limit() - self.player.debt)

    def borrow(self, amount: float) -> str:
        self._not_now()
        if not self.station.has_shark:
            raise ValueError("The Shark doesn't work this station")
        if amount <= 0:
            raise ValueError("borrow how much?")
        if self.player.debt + amount > self.borrow_limit():
            raise ValueError(f"The Shark looks you up and down. Not a chance over "
                             f"${self.borrowable():,.0f}")
        self.player.debt += amount
        self.player.cash += amount
        return f"Borrowed ${amount:,.2f}. The Shark smiles. That's never good."

    def repay(self, amount: float) -> str:
        self._not_now()
        if not self.station.has_shark:
            raise ValueError("The Shark doesn't work this station")
        amount = min(amount, self.player.debt, self.player.cash)
        if amount <= 0:
            raise ValueError("nothing to repay, or nothing to repay it with")
        self.player.debt -= amount
        self.player.cash -= amount
        tail = " Debt cleared. You can breathe." if self.player.debt <= 0 else ""
        return f"Repaid ${amount:,.2f}.{tail}"

    def deposit(self, amount: float) -> str:
        self._not_now()
        if not self.station.has_vault:
            raise ValueError("no vault at this station")
        amount = min(amount, self.player.cash)
        if amount <= 0:
            raise ValueError("deposit how much?")
        self.player.cash -= amount
        self.player.vault += amount
        return f"Deposited ${amount:,.2f}. It earns {VAULT_RATE:.0%} a day in there."

    def withdraw(self, amount: float) -> str:
        self._not_now()
        if not self.station.has_vault:
            raise ValueError("no vault at this station")
        amount = min(amount, self.player.vault)
        if amount <= 0:
            raise ValueError("withdraw how much?")
        self.player.vault -= amount
        self.player.cash += amount
        return f"Withdrew ${amount:,.2f}."

    # --------------------------------------------------------------- upgrades

    #: What one upgrade adds to what you can carry.
    CARRY_STEP = 25_000.0

    def upgrade_cost(self) -> float:
        """Each upgrade costs more than the last."""
        steps = round((self.player.cash_cap - self.starting_cash_cap) / self.CARRY_STEP)
        return 3_500.0 * (1.7 ** max(0, steps))

    def buy_capacity(self) -> str:
        """Buy more room in your pockets - the only thing that is capped."""
        self._not_now()
        if not self.station.has_upgrades:
            raise ValueError("nowhere to buy hardware here")
        price = self.upgrade_cost()
        if self.player.cash < price:
            raise ValueError(f"carrying more costs ${price:,.2f}")
        self.player.cash -= price
        self.player.cash_cap += self.CARRY_STEP
        return (f"A better way to carry it: ${price:,.2f}. "
                f"You can hold ${self.player.cash_cap:,.0f} in cash now.")

    def buy_rides(self) -> str:
        """Put fares on the card before you need them."""
        self._not_now()
        if self.player.cash < OMNY_PRICE:
            raise ValueError(f"a book of {OMNY_RIDES} rides is ${OMNY_PRICE:,.2f}")
        self.player.cash -= OMNY_PRICE
        self.player.rides += OMNY_RIDES
        return (f"{OMNY_RIDES} rides on the card for ${OMNY_PRICE:,.2f}. "
                f"You have {self.player.rides} now, and they do not care how "
                f"broke you look.")

    def buy_vpn(self) -> str:
        self._not_now()
        if not self.station.has_upgrades:
            raise ValueError("nowhere to buy hardware here")
        price = 2_200.0 * (2.0 ** self.player.vpn)
        if self.player.vpn >= 3:
            raise ValueError("you are already as invisible as this gets")
        if self.player.cash < price:
            raise ValueError(f"that VPN costs ${price:,.2f}")
        self.player.cash -= price
        self.player.vpn += 1
        return f"VPN level {self.player.vpn}. You draw less attention now. (${price:,.2f})"

    # ---------------------------------------------------------------- travel

    def _note_visit(self, target) -> None:
        """Where you have been and how often, kept where the save can carry it.

        Deliberately unable to raise: nothing in here is worth losing a day
        over, and on the web port this bookkeeping once took a ride down with
        it halfway through.
        """
        try:
            self.stats["stations"].add(target.name)
            # how well they know your face here - see events.visit_pressure
            seen = self.stats.setdefault("visits", {})
            seen[target.name] = int(seen.get(target.name, 0)) + 1
        except Exception:      # a stop you cannot write down is still a stop
            pass

    def travel(self, name: str) -> List[str]:
        """Ride to another station. Costs a day - the only thing you can't buy."""
        self._not_now()
        from .events import roll_event

        was_ready = self.dice_ready          # so the offer is announced once
        target = station(name)
        if target.name == self.station.name:
            raise ValueError("you're already here")
        paid_with_card = False
        if self.player.cash + 1e-9 < self.fare:
            if self.player.rides <= 0:
                raise ValueError(f"you can't even make the ${self.fare:.2f} fare")
            paid_with_card = True

        if paid_with_card:
            self.player.rides -= 1
        else:
            self.player.cash -= self.fare
        # The station and the day move together, and the bookkeeping comes
        # after. They used to be separated by two lines of stats work, and on
        # the web port that work could throw - leaving the ride half made: the
        # station changed, the day did not, and the market never regenerated,
        # because that is downstream of the day.
        self.station = target
        self.day += 1
        self._note_visit(target)
        self.player.debt *= (1.0 + self.shark_rate)
        self.player.vault *= (1.0 + VAULT_RATE)
        self.state.drift(self.rng)          # the market moves whether you do or not
        self.market = generate(self.station, self.rng, self.state,
                               luck=self._luck_by_symbol())

        messages = [f"Day {self.day}. {target.name} ({target.lines}).", target.flavor]
        if self.market.headline:
            messages.append(self.market.headline)
        if self.hot_hand:
            messages.extend(self._streak_gift())
        messages.extend(roll_event(self))
        if self.wheel_ready:
            messages.append("There's a prize wheel set up on the mezzanine here. "
                            "One spin, and only at stops you haven't worked yet.")
        if self.dice_ready and not was_ready:
            messages.append(f"Somebody's running dice on the platform. "
                            f"Call a number, 1 to {DICE_SIDES}.")
            messages.extend(self._hear_something())

        self._mark_stats()
        for m in messages:
            self.say(m)
        if self.day > self.days:
            self.finished = True
            messages.append("Thirty days gone. That's the run.")
        return messages

    # ----------------------------------------------------------------- score

    def final_score(self) -> float:
        return self.player.net_worth(self.market)

    def finalise(self) -> None:
        """Close the books on a finished run before it is scored."""
        from .coins import BY_SYMBOL
        held = [sym for sym, h in self.player.wallet.items() if h.qty > 0]
        self.stats["meme_only_finish"] = bool(held) and all(BY_SYMBOL[s].meme for s in held)
        self._mark_stats()

    def verdict(self) -> str:
        score = self.final_score()
        if self.player.debt > self.player.cash + self.player.vault + self.player.portfolio_value(self.market):
            return "The Shark owns you. Try a smaller loan next time."
        if score < START_CASH:
            return "You went thirty days and finished poorer. The subway still got its fare."
        if score < 25_000:
            return "A living. Barely."
        if score < 100_000:
            return "Respectable. You could do this for real. Please don't."
        if score < 500_000:
            return "You cleaned up. Somebody is going to ask questions."
        return "Legendary. They'll name a station after you."
