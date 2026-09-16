# CryptoWarz

Dope Wars, but it's crypto and the map is the NYC subway.

Thirty days. Ten stations. One wallet, and a loan shark who compounds at 10% a
day. Buy a coin cheap in Coney Island, sell it dear on Wall Street, and try to
be somewhere else when the SEC works the platform.

**Zero dependencies.** Pure Python 3.9+ standard library.

```bash
git clone https://github.com/KANENAS1/CryptoWarz.git
cd CryptoWarz
python3 -m cryptowarz
```

Windows: `python -m cryptowarz`.

```
   ___                 _        __    __
  / __|_ _ _  _ _ __| |_ ___ / / /\ \ \__ _ _ _ ____
 | (__| '_| || | '_ \  _/ _ \ \ \/  \/ / _` | '_|_ /
  \___|_|  \_, | .__/\__\___/  \_/\__/\__,_|_| /__|
           |__/|_|        thirty days · ten stops · one wallet

DAY 15/30   14 St-Union Sq (4 5 6 L N Q R W)
CASH $210.59   DEBT $20,886.24   VAULT $0.00   NET -$17,658.79

  COIN            PRICE          YOU HOLD         WORTH      AVG PAID
  DOGE           0.6775                 -             -             -  DEAR
  SOL            111.01                 -             -             -
  ETH             1,893          1.593756     $3,016.86         1,559
  BTC            63,760                 -             -             -

  ! SEC raid on the platform. They seize 38% of your wallet.
```

---

## These prices are made up

There is no live market here and there is deliberately no connection to one.
Prices are invented to make interesting decisions, and each coin's behaviour is
tuned for how it *plays*, not for how its real counterpart trades. Nothing you
learn in this game transfers to a real exchange, except possibly "the loan was
a mistake".

## How to play

| | |
|---|---|
| `buy DOGE max` | buy — `max` leaves you the subway fare |
| `sell SOL all` | sell — frees wallet capacity |
| `map` then `go 4` | ride somewhere. **Costs a day.** |
| `borrow 5000` / `repay all` | only where The Shark works (`$`) |
| `deposit 2000` / `withdraw 500` | vaults (`V`) pay 4% a day |
| `wallet` / `vpn` | upgrades at a shop (`S`) |
| `help` | everything above |

## The map

Every station has its own idea of what a coin is worth. That disagreement is
the entire game.

| Station | Lines | Character |
|---|---|---|
| Wall Street | 4 5 | Bids up BTC and ETH, won't touch a dog coin. Heavily policed. |
| Jefferson St | L | Bushwick. Memecoin country, and the exact inverse of Wall Street. |
| Times Sq-42 St | many | Tourist money. Everything costs more and everyone knows it. |
| Coney Island | D F N Q | End of the line. Cheap, weird, and quiet. |
| 125 St | 4 5 6 | Harlem. The Shark works here. |
| Grand Central | 4 5 6 7 S | Liquidity, no bargains. |
| Flushing-Main St | 7 | Cash moves fast. |
| 161 St-Yankee Stadium | 4 B D | Game day. Everyone is buying, nobody is reading. |
| St George | SIR | Staten Island. Safest stop on the map, and the cheapest. |
| 14 St-Union Sq | 4 5 6 L N Q R W | Everything connects. Fair prices, which is its own trap. |

Stations marked `$` have The Shark, `V` a vault, `S` a hardware shop.
**`heat`** drives how often the SEC finds you — and it is highest exactly where
the money is easiest.

## Three things that will kill you

**The Shark.** $5,500 at 10% a day is $87,000 by day 30. Borrowing early is
usually correct and always dangerous. The loan that got you started is the most
common cause of death.

**Capacity.** Your wallet holds a limited dollar amount *at cost*. Selling frees
it; a coin doubling does not. You are always choosing which edge deserves the
space.

**Heat.** An SEC raid takes 18–42% of everything you're holding. A VPN halves
your odds, and the safest stations pay the worst prices.

## How it's balanced

The first version of the price model drew each station's price independently
from the coin's whole range, so Solana could be $20 at one stop and $200 at the
next. "Buy whatever is cheapest" then won **100% of runs at ~$850,000** — a
formula, not a game.

So prices now have two layers: a **level per coin** that random-walks day to
day (which is what makes *holding* a decision), and a **station's bias** on top
of it, deliberately bounded to roughly 2× between the keenest buyer and the
cheapest seller. Measured over 200 simulated runs:

| Strategy | Median | p90 | Best | Finished solvent |
|---|---|---|---|---|
| Do nothing | −11,451 | −6,039 | 41 | **0%** |
| Buy at random | −87,903 | −67,632 | — | **1%** |
| Buy the cheapest | 401 | 90,008 | 244,040 | **50%** |
| + clear the debt when you can afford to | 8,745 | 158,552 | **466,321** | **53%** |

Doing nothing loses. Acting at random loses badly. A sensible heuristic is a
coin flip with real upside, and better judgement raises both the median and the
ceiling. That is the shape a game should have.

## Tests

```bash
python3 -m unittest discover -s tests     # 36 tests, no install needed
```

They cover the arithmetic a player would try to exploit — partial sells
releasing capacity proportionally, `max` leaving the fare behind, capacity and
cash limits, the debt compounding — plus the balance band itself, so a future
tweak that quietly turns the game back into a formula fails the suite.

## Licence

MIT
