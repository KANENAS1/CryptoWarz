#!/usr/bin/env python3
"""Simulate strategies to check CryptoWarz is still a game.

A tuning change that makes one simple heuristic win every run turns the game
into a formula - which is exactly what the first price model did. Run this
after touching prices, biases, debt or capacity, and read the table: doing
nothing must lose, acting at random must lose badly, and better judgement must
raise both the median and the ceiling.
"""

from __future__ import annotations

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cryptowarz.coins import COINS          # noqa: E402
from cryptowarz.game import DAYS, Game      # noqa: E402
from cryptowarz.stations import STATIONS    # noqa: E402

RUNS = 200


def _liquidate(game: Game) -> None:
    for symbol, holding in list(game.player.wallet.items()):
        if holding.qty > 0:
            game.sell(symbol, holding.qty)


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
    if game.station.has_upgrades and game.player.debt == 0 and game.player.cash > 80_000:
        try:
            game.buy_capacity()
        except ValueError:
            pass
    symbol = _cheapest(game)
    qty = game.max_buyable(symbol)
    if qty > 0:
        game.buy(symbol, qty * 0.95)


STRATEGIES = [
    ("do nothing", do_nothing),
    ("buy at random", at_random),
    ("buy the cheapest", buy_the_dip),
    ("+ clear the debt", dip_and_clear_debt),
]


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

    for problem in problems:
        print(f"  BALANCE: {problem}")
    if not problems:
        print("  BALANCE: healthy - nothing wins for free, nothing is hopeless.")
    print()
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
