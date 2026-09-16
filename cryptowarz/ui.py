"""Terminal rendering. Raw ANSI, no dependencies, degrades to plain text."""

from __future__ import annotations

import os
import sys
from typing import List, Optional

from .coins import COINS
from .game import DAYS, Game
from .stations import STATIONS

_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def enable_color(flag: Optional[bool] = None) -> bool:
    global _COLOR
    if flag is not None:
        _COLOR = flag
    if _COLOR and os.name == "nt":
        try:                                   # legacy console needs VT mode
            import ctypes
            k = ctypes.windll.kernel32
            k.SetConsoleMode(k.GetStdHandle(-11), 7)
        except Exception:
            pass
    return _COLOR


GREEN, RED, CYAN, MAG, YELL, GREY, WHITE, BOLD, RESET = (
    "\x1b[38;2;80;220;140m", "\x1b[38;2;255;90;110m", "\x1b[38;2;80;220;230m",
    "\x1b[38;2;255;80;180m", "\x1b[38;2;255;200;90m", "\x1b[38;2;130;130;155m",
    "\x1b[38;2;235;238;245m", "\x1b[1m", "\x1b[0m")


def c(text: str, colour: str, bold: bool = False) -> str:
    if not _COLOR:
        return text
    return f"{BOLD if bold else ''}{colour}{text}{RESET}"


def money(v: float) -> str:
    return f"-${abs(v):,.2f}" if v < 0 else f"${v:,.2f}"


def price(v: float) -> str:
    """Sub-cent coins need more decimals than Bitcoin does."""
    if v >= 1000:
        return f"{v:,.0f}"
    if v >= 1:
        return f"{v:,.2f}"
    if v >= 0.001:
        return f"{v:.4f}"
    return f"{v:.8f}"


BANNER = r"""
   ___                 _        __    __
  / __|_ _ _  _ _ __| |_ ___ / / /\ \ \__ _ _ _ ____
 | (__| '_| || | '_ \  _/ _ \ \ \/  \/ / _` | '_|_ /
  \___|_|  \_, | .__/\__\___/  \_/\__/\__,_|_| /__|
           |__/|_|        thirty days · ten stops · one wallet
"""


def banner() -> str:
    return c(BANNER, MAG)


def header(game: Game) -> str:
    p = game.player
    worth = p.net_worth(game.market)
    left = (f"{c('DAY', GREY)} {c(f'{game.day}/{DAYS}', WHITE, True)}   "
            f"{c(game.station.name, MAG, True)} {c(f'({game.station.lines})', GREY)}")
    right = (f"{c('CASH', GREY)} {c(money(p.cash), GREEN if p.cash > 0 else RED)}   "
             f"{c('DEBT', GREY)} {c(money(p.debt), RED if p.debt > 0 else GREY)}   "
             f"{c('VAULT', GREY)} {c(money(p.vault), CYAN)}   "
             f"{c('NET', GREY)} {c(money(worth), GREEN if worth >= 0 else RED, True)}")
    return f"{left}\n{right}"


def market_table(game: Game) -> str:
    rows = [c(f"  {'COIN':<6}{'PRICE':>15}{'YOU HOLD':>18}{'WORTH':>14}{'AVG PAID':>14}", GREY)]
    for coin in COINS:
        p = game.market.price(coin.symbol)
        h = game.player.wallet.get(coin.symbol)
        qty = h.qty if h else 0.0
        worth = qty * p
        # flag where this price sits in the coin's normal range
        span = coin.high - coin.low
        pos = (p - coin.low) / span if span > 0 else 0.5
        if pos <= 0.2:
            tag, col = "CHEAP", GREEN
        elif pos >= 0.8:
            tag, col = "DEAR ", RED
        else:
            tag, col = "     ", GREY
        held = f"{qty:,.6f}" if qty > 0 else c("-", GREY)
        rows.append(
            f"  {c(coin.symbol, WHITE, True):<6}{price(p):>15}"
            f"{held:>18}{(money(worth) if qty > 0 else '-'):>14}"
            f"{(price(h.avg_price) if h and qty > 0 else '-'):>14}  {c(tag, col)}"
        )
    if game.market.headline:
        rows.append("")
        rows.append("  " + c("! " + game.market.headline, YELL, True))
    return "\n".join(rows)


def wallet_panel(game: Game) -> str:
    p = game.player
    used, cap = p.used_capacity, p.capacity
    filled = int(round(used / cap * 28)) if cap else 0
    bar = c("█" * filled, CYAN) + c("░" * (28 - filled), GREY)
    lines = [
        f"  {c('wallet', GREY)}   {bar} {money(used)} / {money(cap)}",
        f"  {c('vpn', GREY)}      level {p.vpn}",
    ]
    return "\n".join(lines)


def services(game: Game) -> str:
    s = game.station
    have = []
    if s.has_shark:
        have.append(c("SHARK", RED) + c(" borrow/repay", GREY))
    if s.has_vault:
        have.append(c("VAULT", CYAN) + c(" deposit/withdraw", GREY))
    if s.has_upgrades:
        have.append(c("SHOP", YELL) + c(" wallet/vpn", GREY))
    return "  " + ("   ".join(have) if have else c("no services at this stop", GREY))


def station_menu() -> str:
    rows = []
    for i, s in enumerate(STATIONS, 1):
        marks = "".join(m for m, f in (("$", s.has_shark), ("V", s.has_vault), ("S", s.has_upgrades)) if f)
        rows.append(f"  {c(f'{i:>2}', YELL)} {s.name:<28}{c(s.lines[:16], GREY):<16} {c(marks, CYAN)}")
    return "\n".join(rows)


def recent(game: Game, n: int = 6) -> str:
    return "\n".join("  " + c(line, GREY) for line in game.log[-n:])


def scoreboard(scores, limit: int = 10) -> str:
    """The board, or an honest note that there isn't one yet."""
    if not scores:
        return "  " + c("No finished runs yet. Survive thirty days and you'll have one.", GREY)
    from datetime import datetime
    rows = ["  " + c(f"{'#':<3}{'NET WORTH':>15}{'DAY':>6}  WHEN         VERDICT", GREY)]
    for i, s in enumerate(scores[:limit], 1):
        when = datetime.fromtimestamp(s.finished_at).strftime("%d %b %H:%M") if s.finished_at else ""
        colour = GREEN if s.net_worth > 0 else RED
        rows.append(f"  {c(f'{i:<3}', YELL)}{c(money(s.net_worth), colour):>15}"
                    f"{s.day:>6}  {c(f'{when:<12}', GREY)} {c(s.verdict[:38], GREY)}")
    return "\n".join(rows)


HELP = f"""
  {c('TRADE', MAG, True)}
    buy  <coin> <qty|max>     {c('b BTC 0.1   ·   buy DOGE max', GREY)}
    sell <coin> <qty|all>     {c('s DOGE all  ·   sell SOL 12', GREY)}

  {c('MOVE', MAG, True)}
    go <number>               {c('ride to a station - costs one day', GREY)}
    map                       {c('list the stations', GREY)}

  {c('MONEY', MAG, True)}
    borrow <amt> / repay <amt|all>   {c('only where The Shark works ($)', GREY)}
    deposit <amt> / withdraw <amt>   {c('only at a vault (V)', GREY)}
    wallet <n> / vpn                 {c('upgrades at a shop (S)', GREY)}

  {c('ELSE', MAG, True)}
    look        {c('redraw the market', GREY)}
    scores      {c('your best runs', GREY)}
    help        quit  {c('- quitting saves; reloading replays the same dice', GREY)}
"""
