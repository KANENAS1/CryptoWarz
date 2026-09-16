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
from typing import Dict, List, Optional

from .coins import COINS, Coin, coin
from .market import Market, MarketState, generate
from .stations import STATIONS, Station, station

DAYS = 30
START_CASH = 2_000.0
START_DEBT = 5_500.0
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
    capacity: float = START_CAPACITY
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
        return math.fsum(h.cost for h in self.wallet.values())

    @property
    def free_capacity(self) -> float:
        return max(0.0, self.capacity - self.used_capacity)

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
    rng: random.Random = field(init=False)
    state: MarketState = field(init=False)
    market: Market = field(init=False)

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)
        self.state = MarketState(self.rng)
        self.market = generate(self.station, self.rng, self.state)
        self.say(f"Day 1. You're at {self.station.name} with "
                 f"${self.player.cash:,.0f} and a ${self.player.debt:,.0f} problem.")
        if self.market.headline:
            self.say(self.market.headline)

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
        spendable = max(0.0, self.player.cash - SUBWAY_FARE - FARE_BUFFER)
        return max(0.0, min(spendable / price, self.player.free_capacity / price))

    def buy(self, symbol: str, qty: float) -> str:
        symbol = symbol.upper()
        if symbol not in {c.symbol for c in COINS}:
            raise ValueError(f"nobody here trades {symbol}")
        if qty <= 0:
            raise ValueError("buy how much?")
        price = self.market.price(symbol)
        cost = price * qty
        if cost > self.player.cash + 1e-9:
            raise ValueError(f"that costs ${cost:,.2f} and you have ${self.player.cash:,.2f}")
        if cost > self.player.free_capacity + 1e-9:
            raise ValueError(f"your wallet only has ${self.player.free_capacity:,.2f} of room left")
        h = self.player.holding(symbol)
        h.qty += qty
        h.cost += cost
        self.player.cash -= cost
        return f"Bought {qty:,.6f} {symbol} at ${price:,.6f} for ${cost:,.2f}"

    def sell(self, symbol: str, qty: float) -> str:
        symbol = symbol.upper()
        h = self.player.holding(symbol)
        if qty <= 0:
            raise ValueError("sell how much?")
        if qty > h.qty + 1e-12:
            raise ValueError(f"you only hold {h.qty:,.6f} {symbol}")
        price = self.market.price(symbol)
        proceeds = price * qty
        # release capacity proportionally, so partial sells behave sanely
        released = h.cost * (qty / h.qty) if h.qty > 0 else 0.0
        profit = proceeds - released
        h.qty -= qty
        h.cost -= released
        if h.qty <= 1e-12:
            h.qty, h.cost = 0.0, 0.0
        self.player.drop_empty()
        self.player.cash += proceeds
        verb = "made" if profit >= 0 else "lost"
        return (f"Sold {qty:,.6f} {symbol} at ${price:,.6f} for ${proceeds:,.2f} "
                f"({verb} ${abs(profit):,.2f})")

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
        if not self.station.has_vault:
            raise ValueError("no vault at this station")
        amount = min(amount, self.player.cash)
        if amount <= 0:
            raise ValueError("deposit how much?")
        self.player.cash -= amount
        self.player.vault += amount
        return f"Deposited ${amount:,.2f}. It earns {VAULT_RATE:.0%} a day in there."

    def withdraw(self, amount: float) -> str:
        if not self.station.has_vault:
            raise ValueError("no vault at this station")
        amount = min(amount, self.player.vault)
        if amount <= 0:
            raise ValueError("withdraw how much?")
        self.player.vault -= amount
        self.player.cash += amount
        return f"Withdrew ${amount:,.2f}."

    # --------------------------------------------------------------- upgrades

    def upgrade_cost(self) -> float:
        """Each wallet upgrade costs more than the last."""
        steps = round((self.player.capacity - START_CAPACITY) / 25_000.0)
        return 3_500.0 * (1.7 ** steps)

    def buy_capacity(self) -> str:
        if not self.station.has_upgrades:
            raise ValueError("nowhere to buy hardware here")
        price = self.upgrade_cost()
        if self.player.cash < price:
            raise ValueError(f"a bigger cold wallet costs ${price:,.2f}")
        self.player.cash -= price
        self.player.capacity += 25_000.0
        return (f"New cold wallet: ${price:,.2f}. "
                f"Capacity now ${self.player.capacity:,.0f}.")

    def buy_vpn(self) -> str:
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

    def travel(self, name: str) -> List[str]:
        """Ride to another station. Costs a day - the only thing you can't buy."""
        from .events import roll_event

        target = station(name)
        if target.name == self.station.name:
            raise ValueError("you're already here")
        if self.player.cash + 1e-9 < SUBWAY_FARE:
            raise ValueError(f"you can't even make the ${SUBWAY_FARE:.2f} fare")

        self.player.cash -= SUBWAY_FARE
        self.station = target
        self.day += 1
        self.player.debt *= (1.0 + SHARK_RATE)
        self.player.vault *= (1.0 + VAULT_RATE)
        self.state.drift(self.rng)          # the market moves whether you do or not
        self.market = generate(self.station, self.rng, self.state)

        messages = [f"Day {self.day}. {target.name} ({target.lines}).", target.flavor]
        if self.market.headline:
            messages.append(self.market.headline)
        messages.extend(roll_event(self))

        for m in messages:
            self.say(m)
        if self.day > DAYS:
            self.finished = True
            messages.append("Thirty days gone. That's the run.")
        return messages

    # ----------------------------------------------------------------- score

    def final_score(self) -> float:
        return self.player.net_worth(self.market)

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
