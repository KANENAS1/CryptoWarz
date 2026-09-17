"""The game loop.

A plain prompt-and-parse REPL, because the game is about the decisions rather
than the interface, and a text prompt runs everywhere without a dependency.
"""

from __future__ import annotations

import argparse
import random
import sys
from typing import List, Optional

from . import gear as gear_module
from . import progress as progress_module
from . import save as save_module
from . import ui
from .coins import BY_SYMBOL
from .game import DAYS, DICE_SIDES, Game, GameOver
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
    if cmd in ("roll", "dice"):
        if not args:
            return [f"call a number from 1 to {DICE_SIDES}"]
        return game.roll_dice(args[0])
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
    if cmd in ("gear", "kit"):
        return [ui.gear_board(progress_module.read_profile(), game)]
    if cmd in ("goals", "trophies", "achievements"):
        return [ui.goals_board(progress_module.read_profile())]
    if cmd in ("scores", "score", "hof"):
        return [ui.scoreboard(save_module.read_scores())]
    if cmd in ("help", "h", "?"):
        return [ui.HELP]
    if cmd in ("quit", "exit", "q"):
        raise GameOver("You walk out of the station and don't look back.")
    return [f"'{cmd}'? try 'help'"]


def new_game(args) -> Game:
    profile = progress_module.read_profile()
    tier = min(max(1, args.tier), profile.max_tier)
    if args.tier > profile.max_tier:
        print(ui.c(f"  Tier {args.tier} is locked - clear tier {profile.max_tier} first. "
                   f"Starting tier {tier}.", ui.YELL))
    perk = args.perk
    if perk and perk not in {p.key for p in profile.unlocked_perks}:
        print(ui.c(f"  You haven't unlocked '{perk}' yet. Running without it.", ui.YELL))
        perk = None
    slot = None
    seed = args.seed
    if args.daily:
        profile.roll_day()
        slot = profile.next_slot()
        if slot is None:
            print(ui.c(f"  All {progress_module.RUNS_PER_DAY} ranked runs are spent today "
                       f"(total {ui.money(profile.daily_total())}). "
                       f"This one is practice - it won't count.", ui.YELL))
        else:
            seed = progress_module.daily_seeds()[slot]
            print(ui.c(f"  Ranked run {slot + 1} of {progress_module.RUNS_PER_DAY}. "
                       f"Everyone plays this same market today.", ui.CYAN))
    game = Game(seed=seed, tier=tier, perk=perk, gear=profile.gear_levels)
    game.is_daily = slot is not None
    game.daily_slot = slot
    return game


def resume_or_new(seed: Optional[int], force_new: bool) -> Game:
    """Offer to pick up an interrupted run, unless told to start fresh."""
    if force_new or not save_module.has_save():
        save_module.clear_save()
        return Game(seed=seed, gear=progress_module.read_profile().gear_levels)
    try:
        saved = save_module.read_save()
    except save_module.SaveError as exc:
        print(ui.c(f"  {exc}", ui.RED))
        save_module.clear_save()
        return Game(seed=seed)
    if saved is None or saved.finished:
        save_module.clear_save()
        return Game(seed=seed)

    worth = saved.player.net_worth(saved.market)
    print(ui.c(f"  You have a run in progress: day {saved.day}, {saved.station.name}, "
               f"net {ui.money(worth)}.", ui.YELL))
    try:
        answer = input(ui.c("  Pick it up? [Y/n] ", ui.MAG, True)).strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = "y"
    if answer in ("", "y", "yes"):
        return saved
    save_module.clear_save()
    return Game(seed=seed)


def play(args) -> int:
    ui.enable_color()
    print(ui.banner())
    profile = progress_module.read_profile()
    if profile.runs:
        print(ui.c(f"  {profile.runs} runs · best {ui.money(profile.best_net)} · "
                   f"{len(profile.achievements)}/{len(progress_module.ACHIEVEMENTS)} goals · "
                   f"tier {profile.max_tier} unlocked", ui.GREY))
    force_new = args.new or args.no_save or args.tier > 1 or args.perk or args.daily
    if force_new or not save_module.has_save():
        save_module.clear_save()
        game = new_game(args)
    else:
        game = resume_or_new(args.seed, False)
    autosave = not args.no_save
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
            if autosave and not game.finished:
                save_module.write_save(game)
        except GameOver as exc:
            print("\n  " + str(exc))
            if autosave and not game.finished:
                save_module.write_save(game)
                print(ui.c("  Run saved. It will be waiting.", ui.GREY))
            break
        except (ValueError, KeyError) as exc:
            print("  " + ui.c(str(exc), ui.RED))
            continue
        except OSError as exc:
            # a read-only home directory must not end a game
            print("  " + ui.c(f"could not save ({exc}); play on, nothing else is affected", ui.RED))
            autosave = False
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

    if game.finished:
        try:
            game.finalise()
            profile = progress_module.read_profile()
            earned = progress_module.award(profile, game)
            points = progress_module.run_points(game)
            counts = progress_module.counts_for_progress(game)
            letter = progress_module.run_grade(game)
            if counts and getattr(game, "is_daily", False):
                progress_module.record_daily(profile, game, game.daily_slot)
            progress_module.write_profile(profile)
            print()
            print("  " + ui.c(f"GRADE {letter}", ui.YELL, True)
                  + ui.c(f"   {points:,.0f} pts"
                         f" (tier {game.tier} ×{progress_module.tier_mult(game.tier):.2f})"
                         if counts else "   unranked", ui.GREY))
            print("  " + ui.c(progress_module.grade_blurb(points) if counts else
                              "You found the turnstile. None of this counts, "
                              "and it never did - not even the ranked run.", ui.GREY))
            if counts and getattr(game, "is_daily", False):
                left = progress_module.RUNS_PER_DAY - len(profile.runs_today())
                print("  " + ui.c(f"Today: {ui.money(profile.daily_total())} across "
                                  f"{len(profile.runs_today())} ranked run(s)"
                                  + (f" · {left} left" if left else " · that's the slate"),
                                  ui.CYAN))
            levelled = gear_module.credit_win(profile, game)
            progress_module.write_profile(profile)
            if levelled and levelled[2] > levelled[1]:
                piece, _, after = levelled
                print()
                print("  " + ui.c(f"◆ {piece.name} — level {after}", ui.CYAN, True))
                print("  " + ui.c(f"    {piece.blurb}", ui.GREY))
                print("  " + ui.c(f"    +{after * gear_module.LUCK_PER_LEVEL:.0%} luck while "
                                  f"you're holding {piece.covers}", ui.GREY))
            if earned:
                print()
                for a in earned:
                    print("  " + ui.c(f"◆ {a.name}", ui.YELL, True) + ui.c(f" — {a.blurb}", ui.GREY))
                unlocked = [p for p in progress_module.PERKS
                            if p.unlocked_by in {a.key for a in earned}]
                for p in unlocked:
                    print("  " + ui.c(f"  unlocked: {p.name} — {p.blurb}", ui.CYAN))
            scores = save_module.record_score(game)
            save_module.clear_save()
            rank = next((i for i, s in enumerate(scores)
                         if abs(s.net_worth - score) < 1e-9), None) if counts else None
            # a personal best is only worth announcing if it is worth having
            if rank == 0 and score > 0 and len(scores) > 1:
                print("  " + ui.c("A new best run.", ui.GREEN, True))
            elif rank is not None and 0 < rank < 5 and score > 0:
                print("  " + ui.c(f"Number {rank + 1} on your board.", ui.CYAN))
            print()
            print(ui.scoreboard(scores, limit=5))
        except OSError as exc:
            print("  " + ui.c(f"could not record the score ({exc})", ui.RED))
    print()
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="cryptowarz",
                                description="Buy low, sell high, ride the subway, dodge the SEC.")
    p.add_argument("--seed", type=int, default=None, help="replay the same thirty days")
    p.add_argument("--tier", type=int, default=1, help="difficulty 1-5; higher ones unlock as you clear them")
    p.add_argument("--perk", default=None, help="carry an unlocked perk (see 'goals')")
    p.add_argument("--daily", action="store_true", help="a ranked run - three a day, same markets for everyone")
    p.add_argument("--gear", action="store_true", help="show your gear and exit")
    p.add_argument("--goals", action="store_true", help="show achievements and unlocks, then exit")
    p.add_argument("--new", action="store_true", help="start fresh, discarding any saved run")
    p.add_argument("--no-save", action="store_true", help="do not read or write save files")
    p.add_argument("--scores", action="store_true", help="show the scoreboard and exit")
    p.add_argument("--no-color", action="store_true")
    args = p.parse_args(argv)
    if args.no_color:
        ui.enable_color(False)
    if args.scores:
        ui.enable_color()
        print(ui.scoreboard(save_module.read_scores()))
        return 0
    if args.gear:
        print(ui.gear_board(progress_module.read_profile()))
        return 0
    if args.goals:
        ui.enable_color()
        print(ui.goals_board(progress_module.read_profile()))
        return 0
    return play(args)


if __name__ == "__main__":
    raise SystemExit(main())
