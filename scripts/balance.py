#!/usr/bin/env python3
"""Simulate strategies to check CryptoWarz is still a game.

A tuning change that makes one simple heuristic win every run turns the game
into a formula - which is exactly what the first price model did. Run this
after touching prices, biases, debt or capacity, and read the table: doing
nothing must lose, acting at random must lose badly, and better judgement must
raise both the median and the ceiling.
"""

from __future__ import annotations

import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cryptowarz.coins import COINS          # noqa: E402
from cryptowarz.game import DAYS, Game      # noqa: E402
from cryptowarz.stations import STATIONS    # noqa: E402

RUNS = 200


def _liquidate(game: Game) -> None:
    """Sell out - but only as much as the player can carry away.

    The crypto wallet has no ceiling and cash does, so "sell everything" is no
    longer a thing anybody can do in one go. A bot that kept asking for it
    would throw on every attempt and quietly stop trading, and the table would
    be measuring a bot that had given up rather than the game.
    """
    for symbol, holding in list(game.player.wallet.items()):
        if holding.qty <= 0:
            continue
        qty = min(holding.qty, game.max_sellable(symbol))
        if qty > 0:
            game.sell(symbol, qty)


def _cheapest(game: Game) -> str:
    return min(((c.symbol, (game.market.price(c.symbol) - c.low) / (c.high - c.low))
                for c in COINS if c.symbol != "USDC"), key=lambda x: x[1])[0]


def do_nothing(game: Game) -> None:
    pass


def at_random(game: Game) -> None:
    _liquidate(game)
    coin = game.rng.choice(COINS)
    qty = game.max_buyable(coin.symbol)
    if qty > 0:
        game.buy(coin.symbol, qty * 0.9)


def buy_the_dip(game: Game) -> None:
    _liquidate(game)
    symbol = _cheapest(game)
    qty = game.max_buyable(symbol)
    if qty > 0:
        game.buy(symbol, qty * 0.95)


def dip_and_clear_debt(game: Game) -> None:
    _liquidate(game)
    if game.station.has_shark and 0 < game.player.debt < game.player.cash * 0.55:
        try:
            game.repay(game.player.debt)
        except ValueError:
            pass
    # bigger pockets are how a large run gets its money out at all now
    if game.station.has_upgrades and game.player.debt == 0 and game.player.cash > 40_000:
        try:
            game.buy_capacity()
        except ValueError:
            pass
    symbol = _cheapest(game)
    qty = game.max_buyable(symbol)
    if qty > 0:
        game.buy(symbol, qty * 0.95)


def dip_clear_and_vault(game: Game) -> None:
    """The same, plus using a vault when the pockets are overflowing.

    With cash capped, a player who never banks anything cannot take a profit
    larger than their pockets. This is the strategy the new rule is supposed to
    reward, so it belongs in the table.
    """
    if game.station.has_vault and game.player.cash > game.player.cash_cap * 0.6:
        try:
            game.deposit(game.player.cash * 0.7)
        except ValueError:
            pass
    dip_and_clear_debt(game)


STRATEGIES = [
    ("do nothing", do_nothing),
    ("buy at random", at_random),
    ("buy the cheapest", buy_the_dip),
    ("+ clear the debt", dip_and_clear_debt),
    ("+ use the vault", dip_clear_and_vault),
]


def _answer(game: Game) -> None:
    """A bot faces the same standoffs a player does rather than being exempt."""
    from cryptowarz.encounter import best_choice

    if game.pending:
        game.resolve(best_choice(game))


def play(seed: int, strategy) -> float:
    game = Game(seed=seed)
    for _ in range(DAYS):
        if game.finished:
            break
        try:
            strategy(game)
        except (ValueError, KeyError):
            pass
        options = [s.name for s in STATIONS if s.name != game.station.name]
        try:
            game.travel(game.rng.choice(options))
        except ValueError:
            break
        _answer(game)
    return game.final_score()


def main() -> int:
    print(f"\n  {RUNS} runs per strategy\n")
    print(f"  {'strategy':<20}{'median':>12}{'p10':>12}{'p90':>12}{'best':>13}{'solvent':>10}")
    print("  " + "-" * 79)
    results = {}
    for name, strategy in STRATEGIES:
        scores = sorted(play(i, strategy) for i in range(RUNS))
        results[name] = scores
        solvent = sum(1 for s in scores if s > 0) / len(scores)
        print(f"  {name:<20}{statistics.median(scores):>12,.0f}"
              f"{scores[len(scores) // 10]:>12,.0f}{scores[-len(scores) // 10]:>12,.0f}"
              f"{scores[-1]:>13,.0f}{solvent:>9.0%}")
    print()

    problems = []
    if statistics.median(results["do nothing"]) > 0:
        problems.append("doing nothing is profitable - the debt is too soft")
    if sum(1 for s in results["buy at random"] if s > 0) / RUNS > 0.35:
        problems.append("random play survives too often - the market is too forgiving")
    solvent = sum(1 for s in results["buy the cheapest"] if s > 0) / RUNS
    if solvent > 0.85:
        problems.append(f"one simple heuristic wins {solvent:.0%} of runs - it is a formula, not a game")
    if solvent < 0.15:
        problems.append(f"a sensible strategy only survives {solvent:.0%} of runs - it is punishing, not hard")

    problems += lift_table()
    problems += grade_table()

    for problem in problems:
        print(f"  BALANCE: {problem}")
    if not problems:
        print("  BALANCE: healthy - nothing wins for free, nothing is hopeless.")
    print()
    return 1 if problems else 0


def grade_table():
    """Does every letter on the ladder catch anything?

    The old ladder had a dead bottom half - D and C together caught 3% of runs
    while F swallowed 41% - because the outcome distribution is bimodal. A
    grade nothing can earn is decoration, so this counts them.
    """
    import collections

    from cryptowarz.progress import DEBT_GRADE, GRADES, run_grade
    from cryptowarz.stations import STATIONS

    def one(seed, strategy, tier):
        game = Game(seed=seed, tier=tier)
        for _ in range(DAYS):
            if game.finished:
                break
            try:
                strategy(game)
            except (ValueError, KeyError):
                pass
            options = [s.name for s in STATIONS if s.name != game.station.name]
            try:
                game.travel(game.rng.choice(options))
            except ValueError:
                break
            _answer(game)
        game.finished = True
        return game

    order = [letter for _, letter, _ in GRADES[:-1]] + [DEBT_GRADE, "F"]
    strategy = dict(STRATEGIES)["+ clear the debt"]
    print("  THE GRADE LADDER")
    print(f"  {GRADE_RUNS} runs of a sensible strategy, per tier.")
    print()
    print("  " + " " * 8 + "".join(f"{g:>7}" for g in order))
    seen = collections.Counter()
    for tier in (1, 3, 5):
        counts = collections.Counter(run_grade(one(i, strategy, tier))
                                     for i in range(GRADE_RUNS))
        seen += counts
        row = "".join(f"{100 * counts.get(g, 0) / GRADE_RUNS:>6.0f}%" for g in order)
        print(f"  tier {tier}  {row}")
    print()

    total = sum(seen.values())
    dead = [g for g in order if seen.get(g, 0) / total < 0.005]
    if dead:
        return [f"nothing earns {', '.join(dead)} - a grade that cannot be "
                f"reached is decoration, not a ladder"]
    biggest = max(order, key=lambda g: seen.get(g, 0))
    if seen[biggest] / total > 0.5:
        return [f"{biggest} swallows {seen[biggest] / total:.0%} of all runs - "
                f"the ladder is one letter wearing a costume"]
    return []


#: How many runs per tier the grade table simulates.
GRADE_RUNS = 250

#: Four ways a player can turn up to a robbery, from nothing to everything.
KITS = (("bare", 0.00, None, 0), ("nervy", 0.03, "pipe", 0),
        ("geared", 0.10, "cutter", 1), ("full kit", 0.15, "taser", 3))
LIFTS = 3000


def _best_answer(lift, luck, weapon, rep):
    """What a mark who can read the odds would say."""
    from cryptowarz import lift as L

    def value(choice):
        odds = L.answer_odds(choice, lift, luck, weapon, rep)
        if choice == "buyoff":
            return -lift["buyoff"]
        loss = lift["cut"] if choice == "brace" else L.botched_loss(lift)
        return odds * lift["stake"] - (1 - odds) * loss

    return max(L.ANSWERS, key=value)


def lift_table():
    """Is robbing another player worth it? It must not be, at parity.

    The first version of this feature paid a bare thief $7,495 for a coin flip
    against a bare mark, which would have meant nobody ever played the actual
    game again. The numbers below are the reason the stake is sized by the cut
    rather than by the thief's pockets.
    """
    from cryptowarz import lift as L

    print("  ROBBING OTHER PLAYERS")
    print(f"  {LIFTS:,} lifts per matchup, against a mark who answers sensibly.")
    print("  Thief carrying $30,000, mark carrying $60,000. Thief's average take:")
    print()
    print("  " + " " * 10 + "".join(f"{m[0]:>12}" for m in KITS) + "   (the mark)")
    grid = {}
    for tname, tluck, tweapon, trep in KITS:
        row = []
        for mname, mluck, mweapon, mrep in KITS:
            mark = L.Mark(uid="m", name="M", station="X", day=9, pockets=60_000.0,
                          luck=mluck, weapon=mweapon, rep=mrep, at=0.0)
            stake = L.stake_for(30_000.0, mark)
            lift = L.open_lift("t", "T", mark, tluck, tweapon, trep, stake, 9, 0.0)
            rng = random.Random(11)
            total = 0.0
            for _ in range(LIFTS):
                choice = _best_answer(lift, mluck, mweapon, mrep)
                done = L.settle(lift, choice, rng.random(), mluck, mweapon, mrep)
                total += done["thief_delta"] - stake
            grid[(tname, mname)] = total / LIFTS
            row.append(total / LIFTS)
        print(f"  {tname:<10}" + "".join(f"{v:>12,.0f}" for v in row))
    print()

    trouble = []
    level = [grid[(k[0], k[0])] for k in KITS]
    if max(level) > 4_000:
        trouble.append(f"robbing an equal is worth {max(level):,.0f} - everyone would "
                       f"rob and nobody would trade")
    if grid[("bare", "full kit")] > 0:
        trouble.append("robbing somebody better equipped than you still pays")
    if grid[("full kit", "bare")] > 12_000:
        trouble.append(f"a maxed player takes {grid[('full kit', 'bare')]:,.0f} off a "
                       f"bare one - new players are food")
    return trouble


if __name__ == "__main__":
    raise SystemExit(main())
