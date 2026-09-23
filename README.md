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
your odds, and the safest stations pay the worst prices. **They leave you alone
for the first fifteen days** — see below.

## Somebody blocks the stairs, and the game stops to ask

Every other bad thing here happens *to* you: the raid takes a third of the bag
and you read about it afterwards. That is right for weather and wrong for a
person. A person blocking the stairs is a **decision**.

So a stickup does not resolve. It waits. The run stops dead — you cannot trade,
travel, spin a wheel or call the dice until you answer — and **it rides the
save**, so closing the tab is not a way out.

```
SOMEBODY BLOCKS THE STAIRS          CARRYING THE STUN GUN · 0% LOADED

RUN            62%   Down the platform and out. What you are carrying slows you down.
SWING FIRST    34%   Bare hands. It is a coin flip and the coin is not yours.
USE THE STUN GUN  76%   Stun Gun. It might not survive the night either.
HAND IT OVER  CERTAIN   Give up $2,200 and walk away whole. Word gets around.
```

**Every option is bad in a different way.** Running is free and usually works —
but a full wallet is a slow wallet, and that is the sharpest idea here: the run
that most needs to walk away is the one least able to. Fully loaded, running
drops from **62% to 34%**. Fighting bare-handed is a coin flip that can cost you
a day in hospital with the Shark's clock still running. Paying is certain, costs
22% of your cash, and advertises you.

The percentages are the real ones — the screen reads the same function the roll
uses.

### Nothing takes your money without asking

Five things used to reach into your pockets on their own. All five stop and ask
now, and a test holds the list so a future event cannot quietly join it.

**A signature request.** Either the airdrop everyone is posting about or the
thing wearing its name — and **which one is decided when it appears, not when
you answer**, so paying somebody to read the contract reveals a fact rather
than rolling a different die.

| | |
|---|---|
| **SIGN IT** | **25%** it is real. The rest empty 8–22% of the bag |
| **READ THE CONTRACT** | 4% of your cash (min $220). Now you know, and *then* you decide |
| **IGNORE IT** | Free. You never find out what it was |

Ignoring it is always free, which is exactly what stops "read it" being a tax:
paying has to buy something you actually want. And because the loss scales with
your bag while the payout does not, **signing blind punishes the rich** — it is
clearly negative the moment you are holding anything worth taking.

**The network is on fire.** Not a person, still a bill:

| | |
|---|---|
| **PAY THE FEE** | $120–820. Annoying, certain, over with |
| **USE A PRIVATE RELAY** | A tenth of that, and **72%** fine. The rest is somebody's honeypot |

### Everyone who comes for your money is answerable

A stickup was the first one. The other two used to be weather — they happened,
they took what they took, you read about it. Now all three stop and ask.

**The Shark sent somebody.** He came for a payment, and this is the one
encounter where **paying is the good end**: what he takes comes off the loan as
well as the cash. So refusing him is not saving money — it is declining to pay
down something that compounds at 10% a day, and being charged for the privilege.

| | |
|---|---|
| **PAY HIM** | A quarter of the debt, off the cash *and* off the debt |
| **RUN** | You keep the money; the loan grows **8%** and he does not forget |
| **SWING FIRST** / **USE THE…** | You keep it; the loan grows **13%**; the debt stands either way |

**Federal agents at the turnstile.** The seizure itself is unchanged — 18–42%
of the bag — so every number the game was balanced against still holds for
anybody who complies. What is new is that complying is a *choice*:

| | |
|---|---|
| **HANDS WHERE THEY CAN SEE THEM** | The raid as it always was |
| **CALL A LAWYER** | 18% of your cash on a retainer; they leave with **45%** of what they came for |
| **RUN** | Your odds as normal. Get away and you keep everything; get caught and it is **1.4×**, and if they find what you are carrying that is a lost day too |

**No weapon is offered against a badge**, and that is deliberate: a trap you can
only learn by falling into it is a worse teacher than a door that was never
there.

### What you are carrying, and what it costs you

| | Edge in a fight | Nerve | Heat | Breaks | Price |
|---|---|---|---|---|---|
| Half a Brick | +12% | +1% | +2% | 45% | *found only* |
| Length of Pipe | +18% | +2% | +6% | 20% | $400 |
| Box Cutter | +26% | +3% | +14% | 10% | $1,200 |
| Louisville Slugger | +33% | +4% | +20% | 6% | $3,200 |
| Stun Gun | +42% | +5% | +28% | 14% | $9,000 |

**Nerve.** Carrying something also changes how you move — you take the stairs
nobody else takes, you hold when other people fold — and the game already has a
number for that. Each weapon carries **1–5% luck**, the same currency gear pays
in. It tilts a shock toward a pump, keeps trouble away, lifts the dice prize
and tilts the private relay.

It is deliberately **junior to gear** (a third of a full set at best) and
deliberately **not added to it**: your luck is the better of the two, never the
sum. "Never a sum" is the rule the whole system rests on, and a weapon is not
an exception — what carrying something buys is a *floor* under your luck, which
matters most early, when you have no gear at all.

**Heat is the whole trade.** What makes a mugger reconsider is exactly what
makes a federal agent look twice: carrying the Stun Gun raises your raid odds
and lowers the chance of being jumped at all. A better weapon always costs more
attention — that ordering is asserted by a test, so the table can never drift
into a free upgrade.

### The story is your own answers

Standing your ground builds a reputation; paying up builds a different one.
Reputation runs −3 to +3 and changes **both** your odds in the next standoff
and the chance of there being one — at +3, some of them look at you and find
something else to look at. Nothing is scripted. Two runs on the same seed can
read completely differently because you answered differently, and that is the
dynamic part: it is not a branching story, it is consequences.

Win a fight and you might take what he was carrying — which is how you get a
weapon without paying for one.

**Nothing here can end the run outright.** The worst case is a slice of the bag
and a lost day. No death, no game over, no unrecoverable state — the same rule
that stops an event taking your last subway fare.

### What it cost the balance

Measured over 400 runs, weight 8 meant **2.4 standoffs a run** and turned an
event into a routine. It ships at **5.5 — about 1.7 a run**, taking the
buy-the-cheapest bot from 50% to 47% solvent. Often enough that carrying
something is a real question; rare enough that meeting somebody on the stairs
still registers.

### What making the drainer a choice cost

Honestly: at first it made the game *easier*. Turning a guaranteed loss into a
38% chance of a payout took the naive bot from 48% to 56% solvent — blind
signing had become a good bet, which is the opposite of what a drainer is for.
Retuned to **25% real** with a smaller payout, it sits at 51/60 against 48/56
before. The residue is the feature working as intended: the event is no longer
an automatic loss, and a player who reads the contract or walks away does
better still.

### Two bugs this turned up

**A shock never reached the chart.** A headline moves the real price level, but
it lands *after* the day has been recorded — so the sparkline kept the
pre-shock number. A coin could double on a pump and the chart would show the
day it did not move, which is precisely the day a chart exists to show. A shock
now corrects the day rather than adding one, so the point-per-day invariant
still holds. It hid for as long as the seeds happened to be kind.

**The JS balance bot had stopped playing.** A standoff blocks every other
action until answered, and the bot never answered — so from its first mugger it
was not skipping an event, it was standing still for the rest of the run and
reporting the game as unwinnable (23% solvent against Python's 48%). Both bots
now answer the way a player does. They take the answer each event used to take
on its own — comply with the badge, pay the collector — so every number measured
before these became choices stays comparable afterwards.

### A lost day now moves the market

Found while building this. A stopped train and a beating both take a day off
you, and both used to advance the clock *without* moving prices — wrong fiction,
a small free lunch (prices cannot move against you while you are unconscious),
and a break in the one-price-per-day invariant the sparklines are drawn from.
Both now go through one place that drifts the market, compounds the debt and
records the day. The parity test that caught it asserts the invariant instead of
the old magic number.

## The wire: they are coming, and you can see it

Losing a third of your bags on day three was not a hard position. It was a coin
flip that decided the run before you had made a decision worth judging — no
capacity, no cash, nothing to trade your way out with. So:

**The SEC cannot raid you for the first 15 days.** Not "rarely" — the weight is
zero. Every run gets the same fair opening.

The pressure isn't deleted, it's **moved**. From day 16 raid weight comes back
and then climbs, reaching **1.8×** on the final day. The back half is more
dangerous than it used to be, deliberately: by then you have something worth
taking, and the choice between sitting on it and pushing on is the best
decision in the game.

And you can read it. Every stop shows **THE WIRE** — a news post with a threat
bar, the real odds, and what the city is saying:

```
  THE WIRE ▮▮▮▯ HIGH  1 in 7 per stop · 27% over the next two
  Word on the platform: the feds are working this line. A day or two, maybe less.
```

The travel screen shows the same reading **for the day you would arrive**, on
every destination, so the fare buys an informed choice rather than a surprise.

Two things make this worth trusting. The odds are computed from **the same
weight table the roll uses** — there is no second, parallel formula that could
drift, and a test rolls four thousand arrivals to confirm the meter matched
what happened. And the headline is picked by day and station rather than by a
die, so it doesn't churn on every redraw and doesn't touch the run's random
stream.

The meter is also what a **VPN** visibly buys: at Express with no VPN the map
spans LOW to HIGH the day the grace ends and WATCH to SEVERE by day thirty; two
VPN levels pull that same map back to LOW and WATCH. Gear you're holding for
moves it too — measured, a raid at a hot stop on day 22 goes from **14.7% to
13.0%** with the right piece at full level.

## Pick how hard the city plays

The tiers are *progression* — you unlock one by beating the one below.
Difficulty is a **second axis, open on every run from the first**, because
somebody who wants a gentler thirty days shouldn't have to grind for it and
somebody who has cleared tier 5 should be able to make tier 1 hurt again.

| | Start | Debt | Shark | Heat | Score |
|---|---|---|---|---|---|
| **Local** | +$1,500 | 85% | 7.5%/day | 80% | **×0.70** |
| **Express** | — | 100% | 10%/day | 100% | **×1.00** |
| **Third Rail** | — | 125% | 12.5%/day | 130% | **×1.50** |

The two axes **multiply**, on the levers and on the board: a hard run of a hot
tier really is both, and an easier run is worth less on the leaderboard while a
harder one is worth more. Nobody has to trust anybody's restraint. Measured
over 400 runs of the same bot:

| | Buy the cheapest | + clear the debt |
|---|---|---|
| Local | **85%** solvent | **89%** |
| Express | **50%** | **57%** |
| Third Rail | **14%** | **28%** |

The difficulty rides the save, so a reload can't change the rules mid-run, and
a save written before this existed still loads — as Express.

`python3 -m cryptowarz --difficulty hard`, or tap **HOW HARD** on the new-run
screen. The phone remembers your choice.

### What the grace period cost, measured

Honestly: the grace on its own made the game noticeably softer — buy-the-
cheapest went from **41% to 55%** solvent over 400 runs. The 1.8× ramp puts
most of that back, at **50%**, and moves raids per run from **3.25 to 2.38**.
The game is a little more forgiving than it was, and the losses now land when
you have something to lose. If you want the old pressure and more, Third Rail
is right there.

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
| Do nothing | −16,238 | −5,922 | 11,511 | **2%** |
| Buy at random | −86,979 | −46,265 | 42,285 | **4%** |
| Buy the cheapest | −581 | 123,715 | 294,034 | **50%** |
| + clear the debt when you can afford to | 18,846 | 200,842 | **535,237** | **56%** |

Doing nothing loses. Acting at random loses badly. A sensible heuristic is a
coin flip with real upside, and better judgement raises both the median and the
ceiling. That is the shape a game should have.

## Three ways to open it

**A file on your machine.** `docs/index.html` is the whole game in one
self-contained file — no server, no network, no dependencies. Save it, open it,
play. The build checks it is a *complete* document (doctype, charset, viewport)
because the artifact build deliberately isn't: the host page there supplies the
head, and the same bytes saved to disk opened in quirks mode, at desktop width
on a phone, with no declared charset. That shipped once; two tests now fail if
it ever does again.

**A web page.** The same file is at `docs/index.html` so GitHub Pages can serve
it: *Settings → Pages → Source: deploy from a branch → `main` / `/docs`*, which
gives a permanent URL anyone can open. Note that **Pages on a private
repository is a paid feature** — on a free account the repo has to be public
first.

**A Claude artifact.** Private by default: it opens for the account that
published it, and for nobody else until it is shared from the page's Share
menu. Handy, and not a link to send to a friend.

All three are the same build and keep the same saves *per browser* — and the
backup line below moves progress between them.

**One thing differs between them, and only one.** The shared leaderboard runs
on the artifact runtime, so it exists on the Claude page and nowhere else.
Everything else — ranked runs, the three-a-day slate, grades, gear, the
dealer, the wire — works identically on a public web host and on a file opened
from disk. The board screen says which of the two it is rather than offering
one explanation for both: on the published page a signed-out viewer can fix it
by signing in, while a copy served from any other host has no Claude runtime
and never will, so telling that viewer to "sign in" would point them at
nothing. Where there is no shared board the screen opens on YOUR RUNS instead
of an empty list.

### Safari, specifically

Two things about WebKit that are worth knowing, both fixed rather than
documented around:

**The toolbars.** iOS Safari sizes `100%` and `100vh` against the viewport you
get with the toolbars *hidden*, so a page exactly one screen tall hides its
last row under the address bar — and with `overflow:hidden` there is no way to
scroll it back. The RIDE THE TRAIN button was simply unreachable.

The unit is **`svh`, not `dvh`**. `dvh` is the *current* height, which is right
until the toolbars slide back in and the layout is suddenly taller than the
screen — top and bottom go missing for as long as they show. `svh` is the
*smallest* viewport: the one with every piece of chrome visible. A layout built
to that fits at all times, and when the toolbars retract the extra strip is
just more black. `-webkit-fill-available` covers WebKit before 15.4, and the
plain `100%` is written first for anything that knows neither.

**A short viewport scrolls rather than clips.** Landscape on a phone, a split
view, or a host that lays its own bars over the page leaves less room than the
browser reports, and a locked-height layout answers that by hiding the top and
bottom rows — the one failure with no way out. Below 520px tall the page
scrolls instead: worse looking, always usable.

Measured on the real CSS sizes of an iPhone SE, 13/14 and 15 Pro Max, with
toolbars showing and hidden, and with a 47px notch and 34px home indicator
forced in: the top row clears the notch and the button clears the home bar in
all six, with no overflow. In landscape the page scrolls and the button still
works.

**Private Browsing.** Safari *has* `localStorage` in a private tab; it just
throws on every write. Every write here is already wrapped, which stops that
ending a run — and would have let somebody play thirty days and lose all of it
without ever being told. The page now probes the store on the way in and says
so in red if nothing is being kept, with a pointer at BACKUP. Verified with
`localStorage` rigged to throw: the warning appears, and the game still loads
and trades normally.

**Add to Home Screen** works: the page already carries the Apple web-app meta
tags, so it opens full-screen without Safari's chrome.

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
| Insider | The map shows who pays most for what | visit every station |

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

Measured over 400 runs of the same bot on the current build: **57% solvent with
no gear, 63% with everything at full level**, and the median roughly doubles
(18,952 → 39,613). Raids per run drop from **2.38 to 2.12**, and a raid at a hot
stop on day 22 reads **14.7% without gear, 13.0% with the right piece at full
level** — while gear for a class you are *not* holding leaves the number exactly
where it was, which is the rule the whole feature stands on.

### The gear screen, and the dealer

Gear used to be a footnote at the bottom of the goals sheet, which is a poor
place for the only thing in the game you *keep*. It now has its own screen —
the **GEAR** button in the footer, or the luck pill in the header. It shows all
four pieces, the level of each, a bar to the next one, and an **ACTIVE** tag on
the piece that is earning you luck *right now*, because "what am I holding for"
is the question the screen is there to answer. The goals live underneath it.

**The dealer.** Somewhere in the stations there is a man who sells a piece of
gear for **$1,000,000** in cash. He appears at stops that already sell things,
**once a run**, and he sells you the class you are currently carrying most of —
so a purchase reinforces a style rather than handing over a random quarter of
the collection.

The price is absurd on purpose, and it is a *real decision* rather than a
victory lap:

*The million comes off your net worth, and therefore off your score.* You are
trading this run's place on the leaderboard for a win banked forever. A money
sink that costs nothing you care about is just a bigger number.

*He will not serve a run the board won't rank.* Anything that hands a run free
money must not let it buy progression either, or god mode launders cash into
permanent luck. The same gate that keeps such a run off the board keeps it away
from the dealer, on both front ends — `test_broker.py` and the parity suite
both assert it.

*He only has the one.* The purchase rides the save, so reloading doesn't
restock him.

A note worth recording: while wiring the dealer up, the wheel's rare **GEAR
wedge turned out to have been banking nothing since it shipped**. In the
browser the function is `creditWheel`; the port also exported it as
`credit_wheel`, an alias that exists only inside the CommonJS export object the
build strips out — so the page called a name that wasn't there, on the one
branch in 25 that calls it, and no test ever rolled that wedge. It is fixed,
and two structural tests in `test_web_parity.py` now fail if the page ever
calls an export-only name again.

### The dice on the platform

Every few rides somebody is running dice — **an actual die, one to six**. Free
to play, no stake. **What you win is graded by how close you land**, as a share
of a $1,450 pot:

| | | share | pays |
|---|---|---|---|
| exact | DEAD ON | 100% | $1,450 |
| ±1 | ONE OFF | 40% | $580 |
| ±2 | CLOSE | 18% | $261 |
| ±3 | WARM | 6% | $87 |

Six sides land close far more often than ten, so the same ladder and the same
pot would have paid half as much again. The rungs are tighter and the pot is
smaller, which puts one offer back where it was: **$537 for the best call, $396
for the worst.**

Hit-or-miss made nine calls in ten pay nothing, which is a slot machine rather
than a call — you read the result and learned nothing from it. Graded by
distance, most calls pay something and the number you say out loud starts to
matter. **The ladder is shown before you call**, not after; a prize table you
only learn by losing is a slot machine too.

**Gear pays out here as well.** Whatever luck you're holding for is added on
top — up to +15% on any prize. A bag you're geared for is what makes the
platform friendlier, and the dice are on the platform.

Tuned so the *worst* call is worth roughly what the old hit-or-miss version
averaged, and the best about 40% more. Rolling at all is worth about five
points of win rate — perk-sized, for a button nobody would ever decline to
press.

**And somebody will tell you something.** When the dice come out, six times in
ten the man running them has heard a rumour: a coin that's *about to run*, or
*about to fall over*. It's good information and it is not an oracle — he's
right about the run 85% of the time, but three days of market noise can bury a
run, so **measured against what the price actually does, a tip lands 59% of the
time.** A real edge, wrong often enough that believing one stays a decision.
Whispers go stale after three days.

<details>
<summary>A quiet consequence worth leaving in.</summary>

Middle numbers are worth more than 1 or 6, because a call at the edge has
nowhere to be close on one side. Calling 3 averages **$537** an offer against
**$396** for calling 1 — exact arithmetic, and the only actual decision the
dice offer. On six sides that gap is wider than it was on ten, which is the
right direction for a detail that rewards paying attention.
</details>

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

## The prize wheel, and a map worth crossing

Sixteen stops now, across all five boroughs. Six of them have somebody running a
prize wheel on the mezzanine, and the rule that makes it work is **one spin per
stop, per run**.

That single constraint is the whole design. A wheel you can spin repeatedly is a
lever you pull; a wheel you get once per station is a reason to ride somewhere
you haven't been. Without it, six extra stations earn nothing.

| wedge | chance | pays |
|---|---|---|
| SMALL | 30% | $300 |
| BUST | 24% | nothing |
| MIDDLE | 22% | $750 |
| BIG | 13% | $1,600 |
| JACKPOT | 7% | $3,400 |
| **GEAR** | **4%** | a win banked toward a piece |

Gear you hold for lifts the cash prizes, same as the dice. A full sweep of all
six wheels averages **$4,223** and about **0.23 gear wins** — roughly one piece
of progress every four complete crossings of the map, which costs you six of
your thirty days to collect.

**On the phone it's an actual wheel**, and the wedges are drawn from the same
weighted table the game scores against — a wedge's slice of the circle *is* its
chance. A wheel whose art disagrees with its maths is the oldest trick in this
particular book and not one worth reproducing.

The gear wedge banks into the same pool as winning a run, deliberately: two
parallel progress tracks for the same four pieces would be a UI problem
pretending to be a feature. And a run the board won't rank gets the cash but
never the gear, like everything else here.

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

## "I bet on one coin and it stayed down"

Reported from a real run, and worth writing down because the answer was two
things and only one of them was the market.

**Nothing in the game watches what you hold and punishes it.** `market.py`
never looks at the player. The only code that reads your wallet either helps
you (gear luck) or is an event with its own name on it (an SEC raid).

**What actually happened, most likely: you overpaid and couldn't see it.** Each
stop marks coins up or down, and buying WIF at the stop that loves it and
selling anywhere else loses **60% with the market completely still**. The
interface showed a CHEAP/DEAR tag measured against the *coin's own range* — a
fact about the market — and said nothing at all about the stop you were
standing in. A player who can't see the markup experiences their own overpaying
as the coin turning on them.

So every coin row now carries a second badge: **`+55% HERE`** or **`-38% HERE`**,
the markup at this stop, in the same number the till is using. Standing at
Jefferson St you can finally see that WIF is +55% and BTC is −12% before you
spend anything.

**The second thing was mine.** The fast coins were given a very weak pull back
toward the middle to stop "buy whatever's cheapest" being a formula, and it
overshot: a 25% drop on WIF left you underwater for **27 days** in the worst
tenth of cases and never recovered at all 8% of the time. That's a whole run
with nothing to do.

| after a 25% drop | before | now |
|---|---|---|
| WIF, 90th percentile | 27 days | **18 days** |
| WIF, never recovers in 30 | 8% | **4%** |
| BONK, never recovers | 7% | **3%** |

The cost is that the naive strategy gets better: buy-the-cheapest goes from 52%
to 60% solvent. That's the trade, stated plainly — being stuck for a whole run
with nothing to do is a worse failure than a strategy being slightly too good.

## You can finally see it

The game recorded your net worth every single day of every run and never drew
it once, and kept no price history at all. It moved the way it moves and never
let anyone watch — one number per coin is a trading screen with the chart
switched off, and a whisper that a coin is *about to run* is unusable if you
can't check whether it has been.

**Every coin row now carries a fortnight.** A sparkline, recessive for the
history and accented for the last few days, with a triangle end-marker pointing
the way it went. And the line that turns a shape into a decision: **a dashed
line at your average cost**, so "is it up" becomes "is it up *on me*".

**The percentage answers whichever question you're actually asking.** Holding
it, you get **your** number — what you paid against what this stop pays right
now, labelled `YOU`. That's your sellable profit, and it's the same gap the
dashed cost line draws on the sparkline. Not holding it, you get the coin's own
fortnight, labelled `14D` and greyed back, because there is no "since I bought"
to report. Two different numbers, two different labels: an unlabelled
percentage that silently changes meaning is worse than no percentage.

Measured against the market *level* would have been the neater-looking number
and the wrong one — the level is abstract, and what you can actually sell for
is the station price, which is the figure printed beside it.

**The end screen draws the run as one line** — net worth across thirty days,
over a labelled break-even line, with a crosshair you can drag to read any day.
A number tells you the result; a line tells you the story.

The terminal gets the same fortnight in block characters, and its **AVG PAID**
column is now **YOUR P/L** — the average price was a number you had to do
arithmetic on; the profit is the arithmetic.

Percentages are written at a precision that earns its place: `4.4%` because the
decimal is a real difference from 4%, `179%` because `179.2%` is three
characters of noise. And the station-markup chip only appears when the stop is
**8% or more** off the market — at a 2% floor nearly every row carried one,
which is wallpaper rather than a signal.

**Two things a chart can get wrong, both handled:**

*A sparkline scales its own window to full height.* That's right for a coin
that moved and a fabrication for one that didn't — USDC wanders 3% around a
dollar and was being drawn with the same dramatic peaks as a memecoin that
tripled. Below 5% total movement the line is drawn **flat**, because flat is
the truth. There's a test for it on both front ends.

*Red and green are the two colours most people can't tell apart.* The chart
colours are **not** the MTA palette the rest of the page wears: `#34d07a`
against `#EE352E` clears deuteranope separation at ΔE 13.2 — checked with a
validator, not an opinion — where the signage green `#00933C` managed only 7.2
and would have left a red-green trading game unreadable to exactly the people
most likely to be squinting at it. Direction is never colour alone anyway: the
end-marker is a triangle and the number beside it carries a sign.

## Pumps, dumps, and the reverse

A random walk wanders. It does not pump, and it does not dump. So every coin
now carries a **run** — a daily push that persists for four or five days and
then re-rolls, on top of the noise. That's the term that gives a chart shapes:
a climb that builds and then rolls over is something you can see coming, be
wrong about, and act on. Noise alone is none of those.

Thirty days now holds six or seven of these, and moves about **30% further**:

| | swing over 30 days, before | after |
|---|---|---|
| WIF | 9.7× | **13.6×** |
| BONK | 8.8× | **11.3×** |
| DOGE | 4.8× | **6.5×** |
| BTC | 1.8× | **2.1×** |

Runs cut both ways, and the cost is on the record: **buy-the-cheapest fell from
58% solvent to 43%**, because a coin that's cheap may simply keep falling. That
is the naive formula getting worse, which is the right direction — and the
whispers on the dice are the compensation. The drawdown tail barely moved (a
25% drop on WIF still clears in 3 days at the median, 21 at the 90th against 18
before), so bags don't get stickier; the market just goes further.

## The roster: twelve coins at four speeds

The spread between `low` and `high` is where the money is. The spread between
**speeds** is where the decisions are.

| | coin | daily move | reverts? |
|---|---|---|---|
| 🔥 | **WIF** Dogwifhat | ~29% | barely |
| 🔥 | **BONK** | ~28% | barely |
| | SHIB · PEPE · DOGE | ~21% | yes |
| | **SUI** | ~16% | some |
| | **AVAX** | ~14% | mostly |
| | XRP · SOL · ETH | ~9% | yes |
| | BTC | ~8% | yes |
| | USDC | ~0.1% | it's a dollar |

Eight coins where everything either crawled or ripped gave you two settings.
Twelve across a range give you a dial — there's always something moving enough
to be worth a trip, and the slow end is what makes the fast end mean something.

**The fast coins wander; the slow ones come back.** That pairing is deliberate
and it is the whole reason the roster is safe to grow.

<details>
<summary>The first version of this broke the game. The numbers.</summary>

Adding four fast coins and nothing else took the naive strategy — *buy whatever
sits lowest in its own range* — from **50% solvent to 70%**. Two things
compound: the best-of-N pick gets better every day as N grows, and a wild coin
sits near its floor more often, so it looks cheap more often. With a strong pull
back toward the middle, "cheap" was a promise. That's a formula, not a game.

So volatility and mean reversion are now separate per-coin dials, and the fast
coins get a *weak* pull — they move further and owe you nothing. Being cheap
stops being a promise.

| | before | naive add | shipped |
|---|---|---|---|
| buy the cheapest, solvent | 50% | **70%** | 52% |
| median | $423 | $40,276 | $4,422 |
| p10 | −$75,351 | −$59,857 | **−$84,437** |
| best | $244,044 | $315,377 | $316,950 |

The roster grew by half and the naive formula gained two points. What did move
is the variance: a worse floor and a higher ceiling, which is what "faster" is
supposed to buy you.

</details>

## Nothing here is trapped in one browser

The save and the profile live in whatever browser or home directory you played
in. That is fine until a new phone, a cleared cache, or a copy of the page
saved to disk — and twenty runs of gear are gone, with nothing able to rebuild
them, because the game deliberately doesn't trust anything it didn't write.

So the game hands you the bytes. **BACKUP**, on the gear screen, gives you your
progress as **one line of text**:

```
CW1.2a9534e8.eyJ2IjoxLCJwcm9maWxlIjp7InJ1bnMiOjIzLCJ…
```

About **390 characters** — gear, goals, tiers, best scores. Short enough to
paste into a note or message to yourself. Tick *include the run I'm in the
middle of* and it carries the live run too (~2,600 characters): the day, the
station, the wallet, the market, the RNG state.

**Both front ends read and write the same line.** A run started in a browser
can be finished in the terminal and the other way round:

```bash
python3 -m cryptowarz --export backup.txt      # or --export to print it
python3 -m cryptowarz --export --export-run    # with the run in progress
python3 -m cryptowarz --import backup.txt
```

Three decisions worth naming:

**It's text, not a file.** A download is blocked or awkward in half the places
this game runs — a sandboxed frame, a page opened from disk, a phone browser. A
line you can select and copy works everywhere. A file is still offered where
files work, and the page tries the artifact runtime's download, then a normal
one, and tells you plainly if neither is available.

**It carries a checksum.** A half-copied paste that silently loaded would
overwrite good progress with a broken profile — the exact failure a backup
exists to prevent. FNV-1a, four lines in both languages so they can't drift,
checked against the published test vectors. A damaged line is refused by name
and nothing is touched.

**It is not a cheat guard.** It's base64, not a lock, and pretending otherwise
would be theatre. What it protects is the leaderboard, and that is protected
where it always was: the board is written from finished runs, not from
profiles, so an imported profile brings gear and history, never a score.

Verified end to end in a real browser on the built page: progress written,
`localStorage` cleared the way a wiped cache would, the line pasted back, and
the profile *and* the run in progress came back — day 6, $41,000, gear intact.
A truncated paste was refused with the good profile untouched, and a line
written by the terminal loaded in the browser.

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
#   in-game: spin · dealer · gear name · gear move · giveup
python3 -m cryptowarz --daily      # your next ranked run of the day
python3 -m cryptowarz --difficulty hard    # local · express · third rail
python3 -m cryptowarz --export backup.txt # your gear and goals, as one line
python3 -m cryptowarz --import backup.txt # ... and back again, anywhere
python3 -m cryptowarz --tier 3 --perk fixer
```

Both front ends write the **same save shape** and the same version, and
`test_web_parity.py` checks it — which caught a real divergence the first time
it ran, where Python recorded the run's seed and the port didn't.

## Tests

```bash
python3 -m unittest discover -s tests     # 278 tests, no install needed
```

They cover the arithmetic a player would try to exploit — partial sells
releasing capacity proportionally, `max` leaving the fare behind, capacity and
cash limits, the debt compounding — plus the balance band itself, so a future
tweak that quietly turns the game back into a formula fails the suite.

## Licence

MIT
