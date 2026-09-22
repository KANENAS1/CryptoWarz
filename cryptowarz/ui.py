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
    from .progress import difficulty_of

    hardness = difficulty_of(getattr(game, "difficulty", "normal"))
    days = getattr(game, "days", DAYS)
    left = (f"{c('DAY', GREY)} {c(f'{game.day}/{days}', WHITE, True)}   "
            f"{c(game.station.name, MAG, True)} {c(f'({game.station.lines})', GREY)}   "
            f"{c(hardness.name.upper(), CYAN)}")
    right = (f"{c('CASH', GREY)} {c(money(p.cash), GREEN if p.cash > 0 else RED)}   "
             f"{c('DEBT', GREY)} {c(money(p.debt), RED if p.debt > 0 else GREY)}   "
             f"{c('VAULT', GREY)} {c(money(p.vault), CYAN)}   "
             f"{c('NET', GREY)} {c(money(worth), GREEN if worth >= 0 else RED, True)}")
    return f"{left}\n{right}"


#: Eight heights of block, which is all the resolution a terminal has and all a
#: shape needs. The terminal gets the same fortnight the phone draws.
BLOCKS = "▁▂▃▄▅▆▇█"


#: A sparkline scales its own window to full height, which is right for a coin
#: that moved and a lie for one that did not: USDC wanders 3% around a dollar
#: and was drawn with the same dramatic peaks as a memecoin that tripled. Below
#: this much total movement, the line is drawn flat, because flat is the truth.
FLAT_BELOW = 0.05


def spark(values, width: int = 12) -> str:
    """A fortnight of a coin, in one column of a table."""
    from .market import SPARK_DAYS

    points = [v for v in list(values)[-min(SPARK_DAYS, width):] if v > 0]
    if len(points) < 2:
        return " " * width
    low, high = min(points), max(points)
    if high <= 0 or (high - low) / high < FLAT_BELOW:
        return ("▄" * len(points)).rjust(width)
    span = high - low
    drawn = "".join(BLOCKS[min(7, max(0, int((v - low) / span * 7.999)))] for v in points)
    return drawn.rjust(width)


def pct_str(frac: float) -> str:
    """A percentage at a precision that earns its place.

    "179.2%" is three characters of noise; "4.4%" is a real difference from 4%.
    """
    value = abs(frac) * 100.0
    body = f"{value:.1f}" if value < 10 else f"{value:.0f}"
    return f"{'+' if frac >= 0 else '-'}{body}%"


def qty_str(qty: float) -> str:
    """A holding, at a sensible number of decimals for its size.

    Six decimals on thirteen million SHIB is eighteen characters of false
    precision that shunts the whole table sideways.
    """
    if qty >= 1_000:
        return f"{qty:,.0f}"
    if qty >= 1:
        return f"{qty:,.3f}"
    return f"{qty:,.6f}"


def market_table(game: Game) -> str:
    from .market import station_markup

    rows = [c(f"  {'COIN':<6}{'PRICE':>15}{'14 DAYS':>14}{'YOU HOLD':>16}{'WORTH':>13}"
              f"{'YOUR P/L':>13}  {'MARKET':<6}  {'THIS STOP':<10}", GREY)]
    for coin in COINS:
        p = game.market.price(coin.symbol)
        h = game.player.wallet.get(coin.symbol)
        qty = h.qty if h else 0.0
        worth = qty * p
        # Two different facts, which the old single tag ran together: where the
        # MARKET has this coin, and what THIS STOP is adding on top. A player
        # who only sees the first experiences their own overpaying as the coin
        # turning on them.
        span = coin.high - coin.low
        pos = (p - coin.low) / span if span > 0 else 0.5
        # six wide, because the heading above it is the six-letter word MARKET
        # and a format spec never truncates - {'MARKET':<5} is still six chars,
        # which is exactly how this column came to sit one place off its rows
        if pos <= 0.2:
            tag, col = "CHEAP ", GREEN
        elif pos >= 0.8:
            tag, col = "DEAR  ", RED
        else:
            tag, col = "      ", GREY
        markup = station_markup(game.station, coin.symbol) - 1.0
        # padded to a fixed width, because a column whose content varies in
        # length is a column that makes the whole table ragged one row at a time
        if abs(markup) < 0.02:
            here, here_col = "".ljust(10), GREY
        else:
            here = f"{markup:+.0%} here".ljust(10)
            here_col = RED if markup > 0 else GREEN
        held = qty_str(qty) if qty > 0 else c("-", GREY)
        # what you paid against what this stop pays now - the sellable number,
        # which is what a player means by "how am I doing on this"
        if h and qty > 0 and h.cost > 0:
            move = p / h.avg_price - 1.0
            pl = c(pct_str(move), GREEN if move >= 0 else RED)
        else:
            pl = c("-", GREY)
        past = game.state.history.get(coin.symbol, [])
        trail = spark(past)
        rising = len(past) >= 2 and past[-1] >= past[-min(len(past), 14)]
        rows.append(
            f"  {c(coin.symbol, WHITE, True):<6}{price(p):>15}"
            f"  {c(trail, GREEN if rising else RED)}"
            f"{held:>16}{(money(worth) if qty > 0 else '-'):>13}"
            f"{pl:>13}  {c(tag, col)}"
            f"  {c(here, here_col)}"
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
    if game.luck > 0:
        lines.append(f"  {c('luck', GREY)}     {c(f'+{game.luck:.0%}', GREEN)}"
                     f"{c(' on what you are holding', GREY)}")
    return "\n".join(lines)


def threat_bar(bars: int, of: int = 4) -> str:
    """Filled blocks for a threat reading, coloured by how bad it is."""
    colour = (GREY, GREEN, YELL, YELL, RED)[min(bars, 4)]
    return c("▮" * bars, colour, bars >= 3) + c("▯" * max(0, of - bars), GREY)


def wire(game: Game, station=None) -> str:
    """The news post: how likely the SEC is at a stop, and what the city says.

    The odds printed here are the real ones - ``events.wire`` reads the same
    weight table the roll uses - because a meter a player learns to distrust is
    worse than no meter at all.
    """
    from .events import wire as read_wire

    w = read_wire(game, station)
    head = c("THE WIRE", MAG, True)
    bar = threat_bar(int(w["bars"]), int(w["of"]))
    label = c(str(w["label"]), (GREY, GREEN, YELL, YELL, RED)[min(int(w["bars"]), 4)], True)
    if w["label"] == "QUIET":
        odds = c(f"no raids for {int(w['grace_left'])} more day"
                 f"{'s' if int(w['grace_left']) != 1 else ''}", GREY)
    else:
        one_in = 1.0 / w["chance"] if w["chance"] > 0 else 0.0
        odds = c(f"1 in {one_in:.0f} per stop · {w['two_stops']:.0%} over the next two", GREY)
    return (f"  {head} {bar} {label}  {odds}\n"
            f"  {c(str(w['text']), WHITE)}")


def whisper(game: Game) -> str:
    """A rumour you were given, while it is still worth anything."""
    from .coins import coin as get_coin

    tip = game.tip
    if not tip:
        return ""
    name = get_coin(str(tip["symbol"])).name
    way = c("about to run", GREEN, True) if tip["up"] else c("about to fall over", RED, True)
    age = game.day - int(tip["day"])
    when = "just heard" if age <= 0 else f"{age} day{'s' if age > 1 else ''} old"
    return ("\n  " + c("WORD ON THE PLATFORM", YELL, True)
            + f"  {c(name, WHITE, True)} is {way}  {c('(' + when + ')', GREY)}")


def dice_ladder(game: Game) -> str:
    """What each degree of closeness is worth - shown before the call, not after."""
    from .game import DICE_LADDER, DICE_SIDES, DICE_TOP_PRIZE

    if not game.dice_ready:
        return ""
    boost = 1.0 + game.luck
    rungs = "  ".join(
        c(("exact" if reach == 0 else f"±{reach}"), MAG, True)
        + c(f" {label} {money(DICE_TOP_PRIZE * share * boost)}", GREY)
        for reach, label, share in DICE_LADDER)
    lines = ["", "  " + c(f"DICE - call 1 to {DICE_SIDES}, free to play", MAG, True),
             "  " + rungs]
    if game.luck > 0:
        lines.append("  " + c(f"your gear adds {game.luck:+.0%} to whatever it pays", GREEN))
    return "\n".join(lines)


def dead_end(game: Game) -> str:
    """Say so, loudly, when the run genuinely cannot continue."""
    if not game.stranded:
        return ""
    return "\n".join([
        "",
        "  " + c("─── STRANDED " + "─" * 31, RED, True),
        "  " + c(f"{money(game.player.cash)} in your pocket, nothing left to sell, and no "
                 f"way to raise", WHITE),
        "  " + c(f"the {money(game.fare)} fare at {game.station.name}. The run can't go on.",
                 WHITE),
        "  " + c("type 'giveup' to end it and be scored, or 'quit' to walk away", YELL),
    ])


def services(game: Game) -> str:
    s = game.station
    have = []
    if s.has_shark:
        have.append(c("SHARK", RED) + c(" borrow/repay", GREY))
    if s.has_vault:
        have.append(c("VAULT", CYAN) + c(" deposit/withdraw", GREY))
    if s.has_upgrades:
        have.append(c("SHOP", YELL) + c(" wallet/vpn", GREY))
    from .gear import BROKER_PRICE, broker_offer
    if broker_offer(game):
        have.append(c("DEALER", YELL, True) + c(f" gear for {money(BROKER_PRICE)} - 'dealer'", GREY))
    if s.has_wheel:
        have.append(c("WHEEL", MAG, True) + c(" spin" if game.wheel_ready
                                              else " already spun", GREY))
    return "  " + ("   ".join(have) if have else c("no services at this stop", GREY))


def station_menu(game: Optional[Game] = None) -> str:
    """The map. With a game in hand it also prices the risk of each stop.

    The threat column is what makes the map a decision rather than a list: the
    stop that pays best for what you are carrying is usually the one the SEC is
    working, and now you can see that before you pay the fare rather than
    afterwards.
    """
    rows = []
    for i, s in enumerate(STATIONS, 1):
        marks = "".join(m for m, f in (("$", s.has_shark), ("V", s.has_vault),
                                       ("S", s.has_upgrades), ("W", s.has_wheel)) if f)
        risk = ""
        if game is not None:
            from .events import raid_chance, standing_heat, threat_level
            # the day you would actually arrive, not the day you are leaving
            chance = raid_chance(game, s, game.day + 1)
            label, bars = threat_level(chance)
            if bars == 0:
                # still in the grace: show what the stop is like, not a column
                # of identical QUIETs
                risk = f"  {threat_bar(standing_heat(s))} {c('heat', GREY)}"
            else:
                risk = f"  {threat_bar(bars)} {c(label.lower(), GREY)}"
        rows.append(f"  {c(f'{i:>2}', YELL)} {s.name:<28}{c(s.lines[:16], GREY):<16} "
                    f"{c(marks, CYAN):<6}{risk}")
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


def goals_board(profile) -> str:
    """Achievements, what they unlock, and where the ladder stands."""
    from .progress import ACHIEVEMENTS, PERKS, TIERS
    earned = set(profile.achievements)
    rows = ["  " + c(f"GOALS  {len(earned)}/{len(ACHIEVEMENTS)}", MAG, True), ""]
    for a in ACHIEVEMENTS:
        got = a.key in earned
        mark = c("✓", GREEN, True) if got else c("·", DARK := GREY)
        name = c(f"{a.name:<22}", WHITE if got else GREY)
        perk = next((p for p in PERKS if p.unlocked_by == a.key), None)
        tail = c(f"unlocks {perk.name}", YELL) if perk else ""
        rows.append(f"  {mark} {name}{c(a.blurb, GREY)}")
        if tail:
            rows.append(f"      {tail}")
    rows += ["", "  " + c(f"TIERS  {profile.max_tier}/{len(TIERS)} unlocked", MAG, True)]
    for t in TIERS:
        open_ = t.level <= profile.max_tier
        rows.append(f"  {c('✓' if open_ else '·', GREEN if open_ else GREY)} "
                    f"{c(f'{t.level} {t.name:<12}', WHITE if open_ else GREY)}"
                    f"{c(t.blurb, GREY)}")
    rows += ["", "  " + c(f"{profile.runs} runs played · best {money(profile.best_net)}", GREY)]
    rows += ["", daily_board(profile), "", gear_board(profile)]
    return "\n".join(rows)


def gear_board(profile, game=None) -> str:
    """What you have earned by winning, and what it is doing for you."""
    from .gear import (GEAR, GEAR_BY_KEY, LUCK_PER_LEVEL, MAX_LEVEL, RETUNE_COST,
                       WINS_FOR_LEVEL, display_name, level_for)

    def GEAR_BY_KEY_NAME(prof, key):
        return display_name(prof, GEAR_BY_KEY[key])


    levels = profile.gear_levels
    rows = ["  " + c("GEAR", MAG, True), ""]
    for piece in GEAR:
        wins = int(profile.gear_wins.get(piece.key, 0))
        level = level_for(wins)
        pips = c("●" * level, YELL) + c("○" * (MAX_LEVEL - level), GREY)
        shown = display_name(profile, piece)
        name = c(f"{shown:<22}", WHITE if level else GREY)
        rows.append(f"  {pips}  {name}{c(piece.covers, GREY)}")
        if level:
            rows.append(f"        {c(f'+{level * LUCK_PER_LEVEL:.0%} luck while holding', GREEN)}"
                        f"{c(' · ' + piece.blurb, GREY)}")
        else:
            rows.append(f"        {c('win a run holding these to earn it', GREY)}")
        nxt = next((n for n in WINS_FOR_LEVEL if n > wins), None)
        if nxt:
            rows.append(f"        {c(f'{wins} win(s) · {nxt - wins} more for level {level + 1}', GREY)}")
    from .gear import BROKER_PRICE, broker_offer
    if game is not None and broker_offer(game):
        rows += ["", "  " + c("A DEALER IS HERE", YELL, True)
                 + c(f"  {money(BROKER_PRICE)} in cash, right now, for the "
                     f"{GEAR_BY_KEY_NAME(profile, broker_offer(game))}.", GREY),
                 "  " + c("It comes off your net worth, so it comes off your score. "
                          "Type 'dealer'.", GREY)]
    if game is not None:
        held = game.luck
        rows += ["", "  " + c(f"holding right now: {held:+.0%} luck" if held
                              else "holding right now: nothing your gear covers", CYAN)]
    rows += ["", "  " + c("Luck tilts a shock toward a pump on what you hold, and keeps "
                          "trouble away.", GREY),
             "  " + c("It is never a sum - you get your best piece, not all of them.", GREY),
             "", "  " + c(f"gear name <piece> <your name>   ·   "
                          f"gear move <from> <to>  ({RETUNE_COST} wins for 1)", CYAN),
             "  " + c("pieces: " + ", ".join(p.key for p in GEAR), GREY)]
    return "\n".join(rows)


def daily_board(profile) -> str:
    """Today's ranked slate: three markets, one attempt each."""
    from .progress import RUNS_PER_DAY, grade
    profile.roll_day()
    done = {r.get("slot"): r for r in profile.runs_today()}
    rows = ["  " + c(f"TODAY  {len(done)}/{RUNS_PER_DAY} ranked runs", MAG, True)]
    for slot in range(RUNS_PER_DAY):
        run = done.get(slot)
        if run:
            net = float(run.get("net", 0.0))
            pts = float(run.get("points", 0.0))
            letter = str(run.get("grade", "F"))
            colour = GREEN if net > 0 else RED
            rows.append(f"  {c('✓', GREEN)} {c(f'Run {slot + 1}', WHITE)}  "
                        f"{c(f'grade {letter}', YELL, True)}"
                        f"{c(f'{pts:>12,.0f} pts', colour)}"
                        f"   {c(money(net), GREY)}")
        else:
            rows.append(f"  {c('·', GREY)} {c(f'Run {slot + 1}', GREY)}  {c('not played', GREY)}")
    total = profile.daily_total()
    rows.append("  " + c(f"today {total:,.0f} pts · grade {grade(total / max(1, RUNS_PER_DAY))}"
                         f" · best day {profile.best_daily:,.0f} pts", GREY))
    return "\n".join(rows)


HELP = f"""
  {c('TRADE', MAG, True)}
    buy  <coin> <qty|max>     {c('b BTC 0.1   ·   buy DOGE max', GREY)}
    sell <coin> <qty|all>     {c('s DOGE all  ·   sell SOL 12', GREY)}

  {c('GAMBLE', MAG, True)}
    spin                      {c('the prize wheel - one go per stop, per run', GREY)}
    dealer                    {c('buy a piece of gear for $1m, if he shows up', GREY)}
    gear                      {c('what you have earned · gear name · gear move', GREY)}
    giveup                    {c('end a run that has nowhere left to go', GREY)}

  {c('MOVE', MAG, True)}
    go <number>               {c('ride to a station - costs one day', GREY)}
    roll <1-10>               {c("call a number when there's dice on the platform", GREY)}
    map                       {c('list the stations', GREY)}

  {c('MONEY', MAG, True)}
    borrow <amt> / repay <amt|all>   {c('only where The Shark works ($)', GREY)}
    deposit <amt> / withdraw <amt>   {c('only at a vault (V)', GREY)}
    wallet <n> / vpn                 {c('upgrades at a shop (S)', GREY)}

  {c('ELSE', MAG, True)}
    look        {c('redraw the market', GREY)}
    scores      {c('your best runs', GREY)}
    goals       {c('achievements, perks and tiers', GREY)}
    help        quit  {c('- quitting saves; reloading replays the same dice', GREY)}
"""
