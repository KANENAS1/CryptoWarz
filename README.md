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

## Play it on a phone

The terminal version is canonical, but the same rules run in a browser — open
`web/index.html` on your phone, or add it to the Home Screen and it runs
fullscreen. It is dressed as MTA station signage: Helvetica (the subway's
typeface since 1989) on signage black, with real route bullets in real MTA
colours. Profit green and loss red are the **4·5·6 green** and **1·2·3 red**,
so even the semantic colours come off the map.

```
web/game.js      the rules, ported from cryptowarz/*.py
web/index.html   the phone UI - loads game.js, readable as source
web/build.py     flattens both into one file for publishing
web/balance.js   the balance table, run against the port
web/dump.js      the port's game data as JSON, for the parity test
```

**Two implementations of one rule set drift**, and the drift is silent — each
version keeps working perfectly while quietly becoming a different game. So
`tests/test_web_parity.py` compares the data **exactly** (every coin's range,
every station's bias and services, every constant) and the behaviour **by
shape** (doing nothing loses, random loses badly, a sensible strategy is a real
contest, better judgement raises the ceiling). Exact medians can't match — the
two languages seed different RNG streams — but every conclusion the balance
table supports must hold on both sides.

Those tests skip cleanly when node isn't installed, because the Python package
itself stays dependency-free.

## What a lost run leaves behind

Losing used to give you nothing but a number, so the thirtieth loss looked
exactly like the first. Three things changed that, and all three pay you for
playing rather than punish you for stopping.

**Goals** name things worth trying, which is how the game teaches its own
depth — most players never think to sit out a raid until *Untouchable* tells
them it's possible. Ten of them, and finishing *any* run earns at least one.

**Perks** turn a goal into something you carry into the next run. This is the
load-bearing one: a run that ends badly still moves a bar you can see.

| Perk | Effect | Unlocked by |
|---|---|---|
| Unlimited MetroCard | Rides are free, signal delays never cost a day | finish a run |
| Seed Round | Start with $2,000 more | finish above water |
| The Fixer | The Shark charges 8.5% a day | clear the Shark |
| Cold Storage | +$15,000 wallet | be worth $100k |
| Burner Phone | Trouble finds you a third less often | survive raid-free |
| Insider | The map shows who pays most for what | visit all ten stations |

**Tiers** raise the ceiling once you've beaten it, because mastery with nowhere
left to go is where people stop. Each is unlocked by clearing the one below.

| Tier | | Debt | Wallet | Days | Solo win rate |
|---|---|---|---|---|---|
| 1 | Off Peak | $5,500 | $25,000 | 30 | 53% |
| 2 | Rush Hour | $6,800 | $21,000 | 30 | 30% |
| 3 | Track Work | $7,800 | $17,000 | 30 | 20% |
| 4 | Last Train | $7,800 | $15,000 | 26 | 20% |
| 5 | Blackout | $9,000 | $13,000 | 26 | 8% |

## Ranked runs, grades and the board

**Three ranked runs a day.** The date deals a slate of three markets — the same
three for everybody, in the same order — and you get one attempt at each. A
leaderboard needs a fixed slate or it just ranks patience, and three is the
number that makes a bad opening survivable without letting anyone grind the
board. Practice runs stay unlimited and don't touch it.

**Every finished run gets a grade.** What you are finally worth, weighted by
the tier you played it on:

| Points | Grade | |
|---|---|---|
| $750,000+ | **S+** | They'll name a station after you |
| $300,000+ | **S** | Somebody is going to ask questions |
| $100,000+ | **A** | Six figures |
| $35,000+ | **B** | A real score |
| $10,000+ | **C** | Out of the hole and then some |
| $2,000+ | **D** | You finished. Barely |
| below | **F** | The Shark got paid. You didn't |

Points are net worth × the tier weight (×1.00 at Off Peak up to ×2.40 at
Blackout), floored at zero — a board you can drag yourself *down* is a board
where the safe play is not to play. Your day's score is the three runs added
up; the day's grade is their average.

The tier weights are roughly the inverse of the measured clear rate, flattened
so tier 1 stays worth playing. Without them a leaderboard quietly instructs
everyone to farm the easiest tier, and the ladder above it stops meaning
anything.

**The board itself** is shared, and lives on the published page — it rides the
artifact `db` capability, one document per player rewritten when a ranked run
lands, so it stays a few hundred rows rather than growing by a document per run
forever. TODAY ranks the current slate; ALL TIME ranks best days. Your name is
whatever you type and is the only thing that leaves the device. Where `db`
isn't available — the local file, a signed-out viewer — the board degrades to
your own runs and nothing breaks.

Missing a day still takes nothing away: there's no streak, just a new slate.

### These numbers were simulated, not guessed

Starting debt turned out to be a far sharper lever than it looks — it compounds
daily while trading profit scales linearly with capacity. An early tier table
raised debt to $19,000 and made the top tier **mathematically unwinnable**: 0–3%
even with a perk and good play. The ladder leans on capacity and heat instead,
and the top tier now sits at 8% solo, 22% with a perk.

The same pass caught three broken perks: `insider` did literally nothing,
`metrocard` saved $84 across a whole run, and `fixer` at 7% halved the debt over
29 days — 74% win rate, easy mode rather than a perk.

Across 40 simulated players the curve lands about right: a median of **2 goals
after one run, 4 after two**, then a long tail — none of the 40 finished all ten
inside thirty runs.

### Gear: what winning leaves you wearing

Perks are a choice you make before a run. **Gear is the opposite** — you don't
pick it, you earn it by *winning while holding something*, and it then quietly
favours that same kind of holding forever after.

| | Gear | Covers |
|---|---|---|
| ●●● | Platform Rat Charm | SHIB · PEPE · DOGE |
| ●●● | Brass Subway Token | XRP · SOL |
| ●●● | Cold-Storage Watch | ETH · BTC |
| ●●● | Laminated MetroCard | USDC |

Finish a run above $2,000 and the class you had the most value in at the end
banks a win. **1 / 3 / 7 wins** gets you levels 1 / 2 / 3, worth **+5% luck per
level** while you're holding coins that piece covers. Luck does two things: it
tilts a market shock toward a *pump* rather than a crash on what you're
holding, and it keeps trouble away from you.

That loop is the point. A perk answers "how do I want to play this run"; gear
answers "what am I becoming". It rewards having a style rather than grinding,
because a win only credits the one class you were actually holding at the end
— cash out to dollars on day thirty and the memecoin charm learns nothing.

**Customising it.** Gear is shaped, not just accumulated. Any piece you've
earned can be **renamed** (`gear name meme Ratty`, or tap it on the goals
screen), and you can **move a banked win** to another piece at **two for one**
(`gear move meme major`). Free respec would make four pieces one piece with a
dropdown; a punitive rate means nobody ever touches it. Two-for-one is enough
to hurt and cheap enough to use when your style actually changes.

Gear **applies in ranked runs**, like perks do.

**Three rules keep it from becoming the game:**

*It follows the bag, not the player.* Own every piece at full level, hold
nothing, and your luck is zero. The bonus is on the coins in your wallet right
now.

*It is never a sum.* Hold one coin from every class and you get your **best**
piece against trouble, not the total. There is no build that stacks to
immunity — measured, one piece at full level is worth as much as four.

*It re-weights decisions that already exist* rather than adding new rolls. A
shock was always a coin-flip between a crash and a pump; gear tilts that flip.
Gear is written into the save, so a reloaded run carries the same luck and
replays as it would have — the anti-savescum guarantee outranks any feature.

Measured over 400 simulated runs of the same trading bot: **26.2% solvent with
no gear, 32.0% with everything at full level** — about the weight of a perk.
Shocks on a coin you're geared for went from 51.9% pumps to 67.2%.

### The skim: gambling on a dip

Bet cash on where a coin goes by the next stop. `skim DOGE 500 dip` — or
`pump`. It settles the moment you ride, against the coin's **real market move**
rather than a station's take on it, because betting on the station price would
just be betting on which stop you rode to.

It costs you attention. A position is somebody else's coin moving on your
say-so, and while one is open the exchange is watching: trouble is up to 40%
likelier, **scaled by how much of everything you own is riding**. That's the
only reason a maximum bet is a decision at all.

**It pays fixed odds — win and you get your stake back plus 0.6×, lose and it's
gone, and a move under 1% is a push.** That flatness is the entire balance of
the feature, and it is the second thing in this repo that had to be rebuilt
after being measured.

<details>
<summary>The first version was a printing press. The numbers.</summary>

It paid in proportion to how far the coin moved, at 2× leverage. That reads
like a gamble, and it was arithmetic: the market pulls a stretched coin back
toward its middle, a player can read exactly how stretched a coin is straight
off the price, and a payout that scales with the move turns that read into
compound interest over thirty days.

| strategy | solvent | best run |
|---|---|---|
| no skimming | 26.2% | $165k |
| bet against the stretch, 50% of cash | **62.0%** | **$39.8M** |

Fixed odds severs the payout from the size of the move. The multiple is set so
that the *best read available* is worth about two percent a ride — a coin at
the top of its range drifts down ~11% against noise of ~30%, so calling the dip
on it is right roughly 64% of the time, and 0.6× turns that into almost
nothing. Anything repeatable and positive compounds, so "barely worth it when
you're right" is the target, not "fair".

| strategy | solvent | median | best run |
|---|---|---|---|
| never skims | 26.2% | −$7,986 | $165k |
| best read, 25% of cash | **33.2%** | −$12,144 | $329k |
| best read, 50% | 31.5% | −$13,369 | $2.5M |
| best read, all in | **0.5%** | −$6,655 | $2.8k |
| careless, 50% | 8.8% | **−$41,549** | $94k |

Skill pays a little. Carelessness costs a lot. Greed is fatal — going all in
repeatedly draws the heat that kills the run. That's a gamble; the first one
was a salary.
</details>

### The dice on the platform

Every few rides somebody is running dice. Call a number, 1 to 10 — free to
play, no stake, and the worst outcome is nothing. Hit it exactly and you walk
away with free crypto; land one off and you get a smaller cut.

Free means you didn't pay cash for it, not that it weighs nothing: the gift
lands in your wallet **at fair value**, so it takes up capacity like anything
else and has an honest cost basis. A bag with no cost basis would be invisible
to the capacity rule and would make every later sale an infinite multiple.

The offer is counted from your last roll, not off the calendar. `day % 4`
looked equivalent and wasn't: a signal delay costs two days, so any offer whose
day got jumped over never happened at all — invisible, because the next one
along looked perfectly normal.

### What is deliberately absent

No streak counter that punishes a missed day, and no lockout: when the three
ranked runs are spent, practice is still there, unlimited, with the same rules.
The daily slate exists to make scores comparable, not to ration the game.

## When the run has nowhere left to go

The game can genuinely corner you. A raid takes the bags, a gas spike takes the
cash, and you're standing on a platform with no Shark and no vault and $1.40 in
your pocket. Every other loss here is a decision that went wrong; this one is a
wall — and a wall the player can't see is just a frozen screen with a working
button bar.

So the game says so, and offers two honest exits:

- **END THE RUN** (`giveup`) — finishes it and scores it for what it is. Walking
  away from a bad position is allowed.
- **START OVER** — throws it away and deals a new one.

The dead end is only shown when it's real. Anything that could still raise the
fare — a bag to sell, a Shark at this stop who'll still lend, your own vault
when you're standing at one, or the MetroCard perk making the fare free — means
you aren't stranded, and the panel stays away. A *false* dead end is worse than
none: it tells a player to abandon a run they could have saved.

**One rule attached to it.** On a ranked run you've actually played (past day
one), starting over still spends the slot. The daily markets are the same three
for everybody, so a free retry against a market you've already seen would make
the leaderboard meaningless. Backing out on day one costs nothing.

## Saving, and why you can't scum it

Quit whenever. The terminal game writes to `~/.cryptowarz/save.json` after
every move and offers to pick the run back up; the phone version does the same
in `localStorage`, so closing the tab mid-run loses nothing. Finished runs go
on a scoreboard (`scores` in the game, or `--scores`).

**The save includes the random state.** That is the whole design, not a
detail. A game of SEC raids and rug pulls invites savescumming — quit before a
bad outcome, reload, take the ride again and hope for different dice. If
reloading rerolled, the risk here would be optional, and a game where the risk
is optional has no decisions in it. So a reload replays the same day with the
same result, and the only way past a bad roll is to live with it.

It follows that prices and the pending shock are stored rather than
regenerated — regenerating would draw from the generator and desynchronise
everything after it.

A save from a different version is **refused**, not guessed at. Silently
loading one the rules have moved past would corrupt a run in ways that look
like bugs.

```bash
python3 -m cryptowarz              # resumes if there's a run in progress
python3 -m cryptowarz --new        # start fresh, discard the save
python3 -m cryptowarz --scores     # the board
python3 -m cryptowarz --no-save    # touch nothing on disk
python3 -m cryptowarz --goals      # achievements, perks and tiers
python3 -m cryptowarz --gear       # your gear and what it's worth
#   in-game: skim <coin> <amt> dip|pump · gear name · gear move
python3 -m cryptowarz --daily      # your next ranked run of the day
python3 -m cryptowarz --tier 3 --perk fixer
```

Both front ends write the **same save shape** and the same version, and
`test_web_parity.py` checks it — which caught a real divergence the first time
it ran, where Python recorded the run's seed and the port didn't.

## Tests

```bash
python3 -m unittest discover -s tests     # 225 tests, no install needed
```

They cover the arithmetic a player would try to exploit — partial sells
releasing capacity proportionally, `max` leaving the fare behind, capacity and
cash limits, the debt compounding — plus the balance band itself, so a future
tweak that quietly turns the game back into a formula fails the suite.

## Licence

MIT
