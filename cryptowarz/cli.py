"""The game loop.

A plain prompt-and-parse REPL, because the game is about the decisions rather
than the interface, and a text prompt runs everywhere without a dependency.
"""

from __future__ import annotations

import argparse
import random
import sys
from typing import List, Optional

from . import ui
from .coins import BY_SYMBOL
from .game import DAYS, Game, GameOver
from .stations import STATIONS


def draw(game: Game) -> None:
    print()
    print(ui.header(game))
    print()
    print(ui.market_table(game))
    print()
    print(ui.wallet_panel(game))
    print(ui.services(game))
    print()


def _qty(game: Game, symbol: str, token: str, selling: bool) -> float:
    if token in ("max", "all"):
        if selling:
            h = game.player.wallet.get(symbol.upper())
            return h.qty if h else 0.0
        return game.max_buyable(symbol)
    try:
        return float(token.replace(",", "").replace("$", ""))
    except ValueError:
        raise ValueError(f"'{token}' is not a quantity")


def handle(game: Game, raw: str) -> List[str]:
    parts = raw.strip().split()
    if not parts:
        return []
    cmd, args = parts[0].lower(), parts[1:]

    if cmd in ("buy", "b"):
        if len(args) < 2:
            return ["buy what, and how much? e.g. buy DOGE max"]
        return [game.buy(args[0], _qty(game, args[0], args[1], selling=False))]
    if cmd in ("sell", "s"):
        if len(args) < 2:
            return ["sell what, and how much? e.g. sell DOGE all"]
        return [game.sell(args[0], _qty(game, args[0], args[1], selling=True))]
    if cmd in ("go", "travel", "g"):
        if not args:
            return ["go where? try 'map'"]
        try:
            index = int(args[0])
        except ValueError:
            raise ValueError("give the station number from 'map'")
        if not 1 <= index <= len(STATIONS):
            raise ValueError(f"pick 1-{len(STATIONS)}")
        return game.travel(STATIONS[index - 1].name)
    if cmd == "map":
        return [ui.station_menu()]
    if cmd == "borrow":
        return [game.borrow(_qty(game, "", args[0], False) if args else 0)]
    if cmd == "repay":
        amount = game.player.debt if (args and args[0] == "all") else (
            float(args[0].replace(",", "")) if args else 0)
        return [game.repay(amount)]
    if cmd in ("deposit", "dep"):
        return [game.deposit(float(args[0].replace(",", "")) if args else 0)]
    if cmd in ("withdraw", "wd"):
        return [game.withdraw(float(args[0].replace(",", "")) if args else 0)]
    if cmd == "wallet":
        return [game.buy_capacity()]
    if cmd == "vpn":
        return [game.buy_vpn()]
    if cmd in ("look", "l", ""):
        return []
    if cmd in ("help", "h", "?"):
        return [ui.HELP]
    if cmd in ("quit", "exit", "q"):
        raise GameOver("You walk out of the station and don't look back.")
    return [f"'{cmd}'? try 'help'"]


def play(seed: Optional[int] = None) -> int:
    ui.enable_color()
    game = Game(seed=seed)
    print(ui.banner())
    print(ui.c("  Buy low at one stop, sell high at another. You have thirty days\n"
               "  and a debt that grows 10% a day. Type 'help' for commands.", ui.GREY))
    draw(game)

    while not game.finished:
        try:
            raw = input(ui.c(f"  [{game.day}] > ", ui.MAG, True))
        except (EOFError, KeyboardInterrupt):
            print()
            break
        try:
            for line in handle(game, raw):
                # multi-line blocks (map, help) carry their own indentation
                print(line if "\n" in line else "  " + line)
        except GameOver as exc:
            print("\n  " + str(exc))
            break
        except (ValueError, KeyError) as exc:
            print("  " + ui.c(str(exc), ui.RED))
            continue
        if game.day > DAYS:
            game.finished = True
            break
        if raw.strip().split()[:1] and raw.strip().split()[0].lower() not in ("help", "h", "?", "map"):
            draw(game)

    score = game.final_score()
    print()
    print(ui.c("  ── FINAL ────────────────────────────────────", ui.MAG))
    print(f"  cash     {ui.money(game.player.cash)}")
    print(f"  vault    {ui.money(game.player.vault)}")
    print(f"  holdings {ui.money(game.player.portfolio_value(game.market))}")
    print(f"  debt     {ui.c('-' + ui.money(game.player.debt)[1:], ui.RED)}")
    print(f"  {ui.c('NET WORTH', ui.WHITE, True)}  "
          f"{ui.c(ui.money(score), ui.GREEN if score > 0 else ui.RED, True)}")
    print()
    print("  " + ui.c(game.verdict(), ui.YELL))
    print()
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="cryptowarz",
                                description="Buy low, sell high, ride the subway, dodge the SEC.")
    p.add_argument("--seed", type=int, default=None, help="replay the same thirty days")
    p.add_argument("--no-color", action="store_true")
    args = p.parse_args(argv)
    if args.no_color:
        ui.enable_color(False)
    return play(args.seed)


if __name__ == "__main__":
    raise SystemExit(main())
