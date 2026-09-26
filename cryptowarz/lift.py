"""Other players are on the platform too, and they are carrying.

Everything else in this game is you against a market and the weather. This is
the one system where the thing in front of you is somebody who made their own
choices, in their own run, on their own night - and it is built on four rules
that are not negotiable, because each one is a way this kind of feature
normally ruins a game.

**Only the pockets are liftable.** Not the vault, not one coin of the crypto
wallet. The wallet inversion said cash is the heavy thing you carry and coins
are weightless numbers; a mugging is the most literal possible consequence of
that, and it hands the vault a second reason to exist. Walking around with
$80,000 in your coat was already slow. Now it is also *visible*.

**Nobody loses money without answering for it.** A lift is not applied to the
mark - it *waits* for them, the way a standoff waits, and comes up the next
time they open the game. Their gear may have already turned it. They can brace,
or they can go after the thief. This is not politeness: a published page cannot
write into another player's save at all, because each viewer's storage is
private even from the artifact's owner. The one architecture the platform
permits is also the only fair one, which is a nice thing to be able to say.

**The thief can only lose what they put up.** A lift costs a *stake*, taken
from the thief's pockets the moment they try it. If the mark turns it, the mark
takes that stake. That cap is not squeamishness, it is honesty: the settlement
is written by the mark's client and read by the thief's, so the only loss a
thief can be made to take is one already collected. Designing as if more were
enforceable would be designing a hole.

**The roll belongs to the mark.** The thief attempts and learns nothing. The
outcome is decided by the mark's own saved RNG when they answer, which means it
rides their save like every other roll in the game and cannot be scummed by
either side - the thief cannot reload to reroll a result they have not seen,
and the mark cannot reload into a better one.

What is actually being competed for is three things at once, and only one of
them is money: the cash, a *reputation* that changes your odds in every
single-player encounter afterwards, and a street record that stands next to the
daily board. A run can be robbed. A run cannot be ended by being robbed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .encounter import REP_MAX, REP_ODDS, weapon_of

# ------------------------------------------------------------ the numbers

#: A lift starts slightly against the thief. Robbing somebody who is standing
#: still, in a run they are not currently in, should not be the good bet - if
#: it were, everyone would do nothing else.
LIFT_BASE = 0.46
#: **A lift is sized by what the thief puts up.** This is the number the whole
#: economy turns on, and the first version got it wrong: a stake taken as a
#: share of the THIEF's pockets was tiny next to a cut taken as a share of the
#: MARK's, so a bare thief robbing a bare mark made $7,495 on a coin flip and
#: nobody would ever have played the game again. Measured, then fixed.
#:
#: Priced so that an even matchup is worth almost exactly nothing: at the base
#: chance a thief wins 46% of the time, so 0.46 x cut - 0.54 x 0.85 x cut is
#: within a rounding error of zero. Robbing a peer is a waste of a day. Robbing
#: somebody worse equipped than you pays, and robbing somebody better does not
#: - which is the only version of this that is a decision.
STAKE_OF_CUT = 0.85
#: Nobody is ever made to put up more than half of what they are carrying, so
#: a lift is always affordable to somebody - it is just smaller.
MAX_STAKE_SHARE = 0.5
#: Below this there is nothing in it for either side.
STAKE_MIN = 250.0
STAKE_MAX = 25_000.0
#: The ceiling on what a clean lift can take, as a share of the mark's pockets.
#: Well under half on purpose: being robbed is a bad night, never a run.
CUT_SHARE = 0.35
CUT_MAX = 40_000.0
#: What each level of the mark's best gear is worth in defence.
GUARD_PER_LUCK = 1.4
#: How much of a weapon defends, versus how much it attacks. A bat is better at
#: taking than at keeping, which is why armour is not just a weapon backwards.
GUARD_FROM_WEAPON = 0.5
#: Chasing somebody is harder than standing your ground - bare-handed. What a
#: weapon buys is the chance to turn that round, which is the whole point of
#: carrying one: gear does not just make you harder to rob, it changes which
#: answer is the right one.
COUNTER_PENALTY = 0.14
#: And what it costs when the chase goes wrong. A counter is the only answer
#: that can cost you more than a clean lift would have: you swung, you missed,
#: and they had both hands free. Bounded so that no single answer can take half
#: the coat - being robbed is a bad night, never a run.
COUNTER_LOSS = 1.3
COUNTER_LOSS_CAP = 0.45
#: Paying a thief off costs this share of what a clean lift would have taken.
BUYOFF_SHARE = 0.5
#: Odds never reach certainty in either direction.
ODDS_FLOOR, ODDS_CEIL = 0.05, 0.95
#: A mark goes cold. Nobody wants to rob a snapshot from last week.
MARK_STALE_SECONDS = 72 * 3600
#: The same grace the SEC gives you, for the same reason. A run does not leave
#: a mark until it has had a few days to become worth robbing - which means a
#: player opening the game for the first time cannot be met by somebody in full
#: kit taking a third of everything they have. Taking your bank early sucks.
LIFT_GRACE_DAYS = 5
#: One attempt on one person per day of your run. Stops a thief emptying
#: somebody by tapping the same button eleven times.
LIFTS_PER_DAY = 1


# -------------------------------------------------------------- the mark

@dataclass(frozen=True)
class Mark:
    """What another player looks like from across the platform.

    Deliberately not their save. It is what you could tell by looking: roughly
    how loaded they are, what they seem to be carrying, whether people leave
    them alone. Enough to make the decision a real one and nothing that would
    let a client reconstruct somebody else's run.
    """

    uid: str
    name: str
    station: str
    day: int
    pockets: float          # cash in hand, the only liftable thing there is
    luck: float             # their best single bonus, gear or nerve
    weapon: Optional[str]
    rep: int
    at: float               # when they were last seen, epoch seconds


def mark_from(game, uid: str, name: str, at: float) -> Mark:
    """The mark a run leaves behind it when it saves."""
    from .encounter import rep_of

    return Mark(uid=str(uid), name=str(name or "Straphanger"),
                station=game.station.name, day=int(game.day),
                pockets=float(game.player.cash), luck=float(game.luck),
                weapon=getattr(game, "weapon", None), rep=rep_of(game),
                at=float(at))


def is_stale(mark: Mark, now: float) -> bool:
    return (now - mark.at) > MARK_STALE_SECONDS


def leaves_a_mark(game) -> bool:
    """Whether a run is visible on the platform at all.

    Not in its first few days, and not once it is over. A finished run is a
    score, not a person standing somewhere.
    """
    return (not getattr(game, "finished", False)
            and int(game.day) > LIFT_GRACE_DAYS)


def worth_lifting(mark: Mark, pockets: float = float("inf")) -> bool:
    """Below the floor there is nothing in it for either side."""
    return stake_for(pockets, mark) >= STAKE_MIN


# ------------------------------------------------------------- the money

def cut_ceiling(mark: Mark) -> float:
    """The most that could ever come out of this coat in one go."""
    return min(CUT_MAX, max(0.0, mark.pockets) * CUT_SHARE)


def stake_for(pockets: float, mark: Mark) -> float:
    """What the thief must put up to try this particular mark.

    Two ceilings, and the lower one wins: what the coat is worth going for, and
    half of what the thief is carrying. A thief with $400 in their pocket can
    still have a go at a rich mark - they simply cannot go for much of it.
    """
    return min(max(0.0, pockets) * MAX_STAKE_SHARE,
               cut_ceiling(mark) * STAKE_OF_CUT,
               STAKE_MAX)


def cut_for(mark: Mark, stake: Optional[float] = None) -> float:
    """What a clean lift takes: exactly what the stake bought, never more."""
    ceiling = cut_ceiling(mark)
    if stake is None:
        return ceiling
    return min(ceiling, max(0.0, stake) / STAKE_OF_CUT)


def buyoff_for(mark: Mark, stake: Optional[float] = None) -> float:
    """What it costs to hand something over and end it there."""
    return cut_for(mark, stake) * BUYOFF_SHARE


def botched_loss(lift: Dict[str, Any]) -> float:
    """What a counter costs when it misses - more than standing still would
    have, and never half the coat."""
    cut = float(lift.get("cut", 0.0))
    ceiling = cut / CUT_SHARE * COUNTER_LOSS_CAP if CUT_SHARE else cut
    return min(cut * COUNTER_LOSS, ceiling)


def can_afford(pockets: float, mark: Mark) -> bool:
    stake = stake_for(pockets, mark)
    return stake >= STAKE_MIN and pockets + 1e-9 >= stake


# -------------------------------------------------------------- the odds

def guard_of(luck: float, weapon_key: Optional[str], rep: int) -> float:
    """How hard somebody is to take from, before the thief is considered.

    The same three things that decide every other encounter in the game: what
    you have learnt to hold, what is in your coat, and whether people have
    heard about you.
    """
    weapon = weapon_of(weapon_key)
    edge = weapon.edge * GUARD_FROM_WEAPON if weapon else 0.0
    return luck * GUARD_PER_LUCK + edge + max(-REP_MAX, min(REP_MAX, rep)) * REP_ODDS


def lift_odds(thief_luck: float, thief_weapon: Optional[str], thief_rep: int,
              mark: Mark) -> float:
    """The thief's chance, which neither side is shown before it is rolled.

    A loaded mark is a slow mark - the same rule that governs running from a
    stickup, pointed the other way. The richest coat on the platform is also
    the easiest one, which is what makes the vault a decision instead of a
    chore.
    """
    weapon = weapon_of(thief_weapon)
    chance = LIFT_BASE
    chance += weapon.edge if weapon else 0.0
    chance += thief_luck * 0.5
    chance += max(-REP_MAX, min(REP_MAX, thief_rep)) * REP_ODDS
    chance -= guard_of(mark.luck, mark.weapon, mark.rep)
    return max(ODDS_FLOOR, min(ODDS_CEIL, chance))


#: What the mark may say. Paying is certain, which is the deal everywhere else
#: in this game too.
ANSWERS = ("brace", "counter", "buyoff")


def answer_odds(choice: str, lift: Dict[str, Any],
                luck: float, weapon_key: Optional[str], rep: int) -> float:
    """The mark's chance of coming out of it well, per answer."""
    if choice == "buyoff":
        return 1.0
    thief = 1.0 - _thief_chance(lift, luck, weapon_key, rep)
    if choice == "counter":
        weapon = weapon_of(weapon_key)
        thief += (weapon.edge if weapon else 0.0) + luck * 0.5 - COUNTER_PENALTY
    return max(ODDS_FLOOR, min(ODDS_CEIL, thief))


def _thief_chance(lift: Dict[str, Any], luck: float, weapon_key: Optional[str],
                  rep: int) -> float:
    """The thief's chance, recomputed against the mark as they are NOW.

    Not as they were when the mark was left. Gear bought, a weapon picked up or
    a night's cash banked between the attempt and the answer all count - you
    are robbed as you are, not as you were advertised.
    """
    chance = float(lift.get("base", LIFT_BASE))
    chance -= guard_of(luck, weapon_key, rep)
    return max(ODDS_FLOOR, min(ODDS_CEIL, chance))


# ---------------------------------------------------------- the outcome

def open_lift(thief_uid: str, thief_name: str, mark: Mark, thief_luck: float,
              thief_weapon: Optional[str], thief_rep: int, stake: float,
              day: int, at: float) -> Dict[str, Any]:
    """The attempt, as it is left for the mark to find.

    ``base`` carries the thief's side of the sum already worked out, so the
    mark's client can finish it against their own current numbers without ever
    being handed the thief's run.
    """
    weapon = weapon_of(thief_weapon)
    base = (LIFT_BASE + (weapon.edge if weapon else 0.0) + thief_luck * 0.5
            + max(-REP_MAX, min(REP_MAX, thief_rep)) * REP_ODDS)
    return {
        "thief": str(thief_uid), "thief_name": str(thief_name or "Straphanger"),
        "mark": mark.uid, "station": mark.station,
        "base": round(base, 6), "stake": round(stake, 2),
        "cut": round(cut_for(mark, stake), 2),
        "buyoff": round(buyoff_for(mark, stake), 2),
        "thief_day": int(day), "at": float(at), "state": "open",
    }


def settle(lift: Dict[str, Any], choice: str, roll: float,
           luck: float, weapon_key: Optional[str], rep: int) -> Dict[str, Any]:
    """What happened, decided by the mark's own roll.

    Returns the settlement both sides read: what the mark loses or keeps, what
    the thief collects or forfeits, the reputation each side walks away with,
    and the line that gets told about it.
    """
    if choice not in ANSWERS:
        raise ValueError(f"nobody answers a mugging with {choice!r}")
    stake = float(lift.get("stake", 0.0))
    cut = float(lift.get("cut", 0.0))
    thief_name = str(lift.get("thief_name") or "somebody")

    if choice == "buyoff":
        paid = float(lift.get("buyoff", cut * BUYOFF_SHARE))
        return _settlement(
            mark_delta=-paid, thief_delta=stake + paid, mark_rep=-1, thief_rep=0,
            outcome="paid",
            mark_line=f"You hand {thief_name} something to make it stop. It stops.",
            thief_line=f"They paid rather than find out. ${paid:,.0f}, and no trouble.")

    won = roll < answer_odds(choice, lift, luck, weapon_key, rep)
    if choice == "brace":
        if won:
            return _settlement(
                mark_delta=0.0, thief_delta=0.0, mark_rep=1, thief_rep=-1,
                outcome="held",
                mark_line=f"{thief_name} went through your coat and found it shut. "
                          f"You keep everything, and their stake with it.",
                thief_line="They were wearing more than you thought. You are out the stake.",
                to_mark=stake)
        return _settlement(
            mark_delta=-cut, thief_delta=stake + cut, mark_rep=0, thief_rep=1,
            outcome="taken",
            mark_line=f"{thief_name} was quicker. ${cut:,.0f} gone before you turned round.",
            thief_line=f"Clean. ${cut:,.0f} out of their coat.")

    # counter: you go after them, and there is no middle result
    if won:
        return _settlement(
            mark_delta=0.0, thief_delta=0.0, mark_rep=2, thief_rep=-2,
            outcome="countered",
            mark_line=f"You went after {thief_name} and got there first. "
                      f"Everything you had, and everything they put up.",
            thief_line="They came back at you. You lost the stake and some standing with it.",
            to_mark=stake)
    worse = botched_loss(lift)
    return _settlement(
        mark_delta=-worse, thief_delta=stake + worse, mark_rep=-1, thief_rep=2,
        outcome="botched",
        mark_line=f"You went after {thief_name} and caught a door. "
                  f"${worse:,.0f} gone, and people saw.",
        thief_line=f"They tried to chase it. ${worse:,.0f}, and now they know better.")


def _settlement(*, mark_delta: float, thief_delta: float, mark_rep: int,
                thief_rep: int, outcome: str, mark_line: str, thief_line: str,
                to_mark: float = 0.0) -> Dict[str, Any]:
    return {
        "state": "settled", "outcome": outcome,
        #: what the mark's pockets do: a loss, or a forfeited stake collected
        "mark_delta": round(mark_delta + to_mark, 2),
        #: what the thief's client may credit, stake included. Zero means the
        #: stake is gone; it is never negative, because a thief's only
        #: enforceable loss is the one already taken off them.
        "thief_delta": round(max(0.0, thief_delta), 2),
        "mark_rep": int(mark_rep), "thief_rep": int(thief_rep),
        "mark_line": mark_line, "thief_line": thief_line,
    }


# ------------------------------------------------------------ the record

def street_record(profile: Dict[str, Any]) -> Dict[str, int]:
    """Lifts made, lifts turned - the thing that outlives any one run."""
    street = profile.get("street") or {}
    return {
        "took": int(street.get("took", 0)),
        "held": int(street.get("held", 0)),
        "lost": int(street.get("lost", 0)),
        "countered": int(street.get("countered", 0)),
    }


def street_points(record: Dict[str, int]) -> int:
    """One number for the board. Turning somebody away is worth more than
    taking from somebody who was not there, because standing still and being
    hard to rob should be a way to play this, not a way to lose slowly."""
    return (record["took"] * 2 + record["held"] * 3 + record["countered"] * 5
            - record["lost"])


def credit_street(profile: Dict[str, Any], outcome: str, *, as_thief: bool) -> None:
    """Record one settled lift on whichever side of it you were."""
    street = dict(street_record(profile))
    if as_thief:
        street["took" if outcome in ("taken", "botched", "paid") else "lost"] += 1
    elif outcome == "held":
        street["held"] += 1
    elif outcome == "countered":
        street["countered"] += 1
    else:
        street["lost"] += 1
    profile["street"] = street
