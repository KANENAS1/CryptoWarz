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

DAYS = 30            # tier 1; a tier can shorten the run
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

# ------------------------------------------------------------------- the dice
#: Somebody runs dice on the platform every few rides. There is no stake: the
#: worst outcome is nothing, so this is a flourish rather than a decision, and
#: it is deliberately not a way to gamble your way out of a bad run.
DICE_EVERY = 4           # rides between offers
DICE_SIDES = 10          # call a number, one to ten
DICE_TOP_PRIZE = 2_200.0 # what calling it exactly is worth

#: How close you got, and what share of the top prize that is worth. Binary
#: hit-or-miss made nine calls in ten pay nothing, which is a slot machine
#: rather than a call - you read the result and learned nothing from it. Graded
#: by distance, almost every call tells you something and most of them pay
#: something, and the number you say out loud starts to matter.
#:
#: Tuned so the WORST call is worth roughly what the old hit-or-miss version
#: averaged, and the best is worth about 40% more. Rolling at all is then worth
#: about five points of win rate - perk-sized, for a button nobody would ever
#: decline to press.
#:
#: There is a quiet consequence worth leaving in: middle numbers are worth more
#: than 1 or 10, because a call at the edge has nowhere to be close on one side.
#: Calling 5 averages $541 against $381 for calling 1. It is exact arithmetic
#: and it is also small - measured, it does not reliably move a win rate - so
#: it is a detail for a player to notice, not a headline.
DICE_LADDER = (
    (0, "DEAD ON", 1.00),
    (1, "ONE OFF", 0.40),
    (2, "CLOSE",   0.20),
    (3, "WARM",    0.09),
    (4, "COLD",    0.04),
)
#: Opening calls that put a player on a streak, and what a streak pays.
#: Not every ride and not the same amount: a fixed payment on a metronome
#: stopped being a windfall by the third station and started being a salary.
HOT_HAND = (4, 2)
HOT_HAND_CHANCE = 0.75            # roughly three rides in four
HOT_HAND_MIN = 250.0
HOT_HAND_MAX = 10_000.0

# ------------------------------------------------------------------- the skim
#: A bet on where a coin goes next, settled on your next ride. Not a trade: you
#: put up nothing but cash and take nothing but cash, so it pays no attention to
#: wallet capacity - which is exactly why it has to cost something else.
#:
#: What it costs is attention. A position is somebody else's coin moving on your
#: say-so, and while one is open the exchange is looking at you: trouble is
#: SKIM_HEAT times more likely on the ride that settles it. That is the whole
#: design. Without the heat this is free optionality bolted onto a game about
#: carrying risk around on a train, and the correct play would be to skim on
#: every single ride forever.
#: FIXED ODDS, and that is the whole balance of it. The first version paid out
#: in proportion to how far the coin moved, at 2x leverage. It looked like a
#: gamble and was a printing press: the market pulls a stretched coin back
#: toward its middle, a player can read exactly how stretched a coin is off the
#: price, and a payout that scales with the move turns that read into compound
#: interest. Measured, it took a trading bot from 26% solvent to 62%, with a
#: best run of $39.8 million. Paying a flat multiple severs the payout from the
#: size of the move, which is what removes the blow-up.
#:
#: The multiple is set so that the best read available is worth almost nothing.
#: A coin at the top of its range drifts down about 11% against noise of 30%,
#: so calling the dip on it is right roughly 64% of the time; at 0.6 that is an
#: edge of about two percent a ride. Careless betting is a clear loss. Anything
#: repeatable and positive compounds over thirty days, so "barely worth it when
#: you are right" is the target, not "fair".
SKIM_MIN = 100.0          # below this it is not a bet, it is a rounding error
SKIM_PAYS = 0.6           # win and you get the stake back plus this much again
SKIM_DEADBAND = 0.01      # a move smaller than this is a push, not a free win
SKIM_HEAT = 1.4           # trouble multiplier when your whole roll is riding
SKIM_SIDES = ("dip", "pump")



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
    #: difficulty level, 1-5; see progress.TIERS
    tier: int = 1
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

        tier = TIER_BY_LEVEL.get(self.tier, TIER_BY_LEVEL[1])
        self.player.debt = tier.debt
        self.player.capacity = tier.capacity
        self.days = tier.days
        self.heat_mult = tier.heat_mult

        if self.perk and self.perk in PERK_BY_KEY:
            if self.perk == "seed_round":
                self.player.cash += 2_000.0
            elif self.perk == "cold_storage":
                self.player.capacity += 15_000.0

        self.stats = {"stations": {self.station.name}, "raids": 0, "peak_worth": 0.0,
                      "best_multiple": 0.0, "worth_by_day": [],
                      "dice_picks": [], "dice_days": [], "hot_hand": False}
        self.hot_hand = False
        #: an open bet, or None. See open_skim.
        self.skim: Optional[Dict[str, object]] = None
        self.rng = random.Random(self.seed)
        self.state = MarketState(self.rng)
        self.market = generate(self.station, self.rng, self.state,
                               luck=self._luck_by_symbol())
        self._mark_stats()
        self.say(f"Day 1. You're at {self.station.name} with "
                 f"${self.player.cash:,.0f} and a ${self.player.debt:,.0f} problem.")
        if self.market.headline:
            self.say(self.market.headline)

    # --------------------------------------------------------------- tracking

    def _mark_stats(self) -> None:
        worth = self.player.net_worth(self.market)
        self.stats["peak_worth"] = max(self.stats.get("peak_worth", 0.0), worth)
        self.stats.setdefault("worth_by_day", []).append(round(worth, 2))

    @property
    def luck(self) -> float:
        """The best gear bonus you are holding for right now, 0.0 to 0.15."""
        from .gear import best_luck
        return best_luck(self.gear, self.player.wallet)

    def _luck_by_symbol(self) -> Dict[str, float]:
        from .gear import luck_by_symbol
        return luck_by_symbol(self.gear, self.player.wallet)

    @property
    def fare(self) -> float:
        return 0.0 if self.perk == "metrocard" else SUBWAY_FARE

    @property
    def shark_rate(self) -> float:
        return 0.085 if self.perk == "fixer" else SHARK_RATE

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
        if released > 0:
            self.stats["best_multiple"] = max(self.stats.get("best_multiple", 0.0),
                                              proceeds / released)
        verb = "made" if profit >= 0 else "lost"
        return (f"Sold {qty:,.6f} {symbol} at ${price:,.6f} for ${proceeds:,.2f} "
                f"({verb} ${abs(profit):,.2f})")

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

    # ----------------------------------------------------------------- skim

    @property
    def skim_open(self) -> bool:
        return self.skim is not None

    @property
    def skim_exposure(self) -> float:
        """How much of everything you have is riding on the bet, 0.0 to 1.0.

        Trouble scales with this rather than switching on, so shoving your whole
        roll onto one call is a louder thing to do than putting a little down -
        which is the only reason a maximum bet is a decision at all.
        """
        if self.skim is None:
            return 0.0
        stake = float(self.skim["stake"])
        # the stake counts toward what you have: it is money you still own, it
        # is just not in your pocket while the bet is open
        rest = max(0.0, self.player.cash + self.player.vault
                   + self.player.portfolio_value(self.market))
        return max(0.0, min(1.0, stake / (stake + rest)))

    def max_skim(self) -> float:
        """The most you could stake - the fare is never part of it."""
        return max(0.0, self.player.cash - self.fare - FARE_BUFFER)

    def open_skim(self, symbol: str, amount: float, side: str) -> str:
        """Bet cash on where a coin goes by the next station.

        One at a time, deliberately. A player who could stack a bet on every
        coin would have bought the market rather than made a call, and the
        whole point is that it is a call.
        """
        symbol = symbol.upper()
        side = str(side).lower()
        if side not in SKIM_SIDES:
            raise ValueError(f"bet the {' or the '.join(SKIM_SIDES)}")
        if symbol not in {c.symbol for c in COINS}:
            raise ValueError(f"nobody here trades {symbol}")
        if symbol == "USDC":
            raise ValueError("a dollar is not going anywhere. Pick something with a pulse")
        if self.skim is not None:
            raise ValueError("you already have something riding. One at a time")
        amount = float(amount)
        if amount < SKIM_MIN:
            raise ValueError(f"${SKIM_MIN:,.0f} is the smallest they'll take")
        if amount > self.max_skim() + 1e-9:
            raise ValueError(f"you can stake ${self.max_skim():,.2f} and still make the fare")

        self.player.cash -= amount
        self.skim = {"symbol": symbol, "stake": amount, "side": side,
                     "level": self.state.levels[symbol]}
        self.stats["skims"] = int(self.stats.get("skims", 0)) + 1
        return (f"${amount:,.2f} on {symbol} to {side}. Settles when you move. "
                f"Somebody is watching you now.")

    def _settle_skim(self) -> List[str]:
        """Close the open bet against the coin's real move, not a station's take.

        The market level is what is being bet on, deliberately: betting on the
        station price would just be betting on which stop you rode to, which is
        a decision the player already makes with their wallet.
        """
        if self.skim is None:
            return []
        bet = self.skim
        self.skim = None
        symbol = str(bet["symbol"])
        stake = float(bet["stake"])
        opened = float(bet["level"])
        now = self.state.levels[symbol]
        move = (now / opened - 1.0) if opened > 0 else 0.0
        toward = move if bet["side"] == "pump" else -move
        side = str(bet["side"])
        if abs(move) < SKIM_DEADBAND:
            self.player.cash += stake
            return [f"{symbol} barely moved ({move:+.1%}). Nobody wins. "
                    f"You get your ${stake:,.2f} back."]
        if toward > 0:
            payout = stake * (1.0 + SKIM_PAYS)
            self.player.cash += payout
            self.stats["skims_won"] = int(self.stats.get("skims_won", 0)) + 1
            self.stats["best_skim"] = max(float(self.stats.get("best_skim", 0.0)),
                                          payout - stake)
            return [f"The {side} came in on {symbol} ({move:+.1%}). "
                    f"You take ${payout:,.2f} - up ${payout - stake:,.2f}."]
        return [f"{symbol} went {move:+.1%}. The ${stake:,.2f} is gone. "
                f"That is what the word gamble means."]

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
        room = self.player.free_capacity
        if room < 1.0:
            return [f"{why} - and your wallet is full. It goes to somebody else."]
        value = min(value, room)
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

        was_ready = self.dice_ready          # so the offer is announced once
        target = station(name)
        if target.name == self.station.name:
            raise ValueError("you're already here")
        if self.player.cash + 1e-9 < self.fare:
            raise ValueError(f"you can't even make the ${self.fare:.2f} fare")

        self.player.cash -= self.fare
        self.station = target
        self.stats["stations"].add(target.name)
        self.day += 1
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
        # settled after the events, so the heat a position attracts lands on the
        # ride you were actually exposed on
        messages.extend(self._settle_skim())
        if self.dice_ready and not was_ready:
            messages.append(f"Somebody's running dice on the platform. "
                            f"Call a number, 1 to {DICE_SIDES}.")

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
