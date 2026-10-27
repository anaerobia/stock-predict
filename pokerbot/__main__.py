"""
Command-line interface.

    python -m pokerbot play [--bot equity]          play against a bot
    python -m pokerbot match equity rule --hands 2000 --seed 1
    python -m pokerbot tournament --hands 500        round-robin of all bots
    python -m pokerbot equity AsKs --board "Qs Js 2d" [--vs "Ah Ad"]
    python -m pokerbot eval "As Ks Qs Js Ts 2d 3c"
"""

import argparse
import itertools
import sys
import time

from .bots import BOTS, load_bot_class, make_bot
from .cards import cards_str, parse_cards
from .engine import QuitGame, run_match
from .equity import chen_score, count_outs, exact_equity, hand_class, monte_carlo_equity
from .evaluator import evaluate, hand_name

AI_BOTS = [name for name in BOTS if name != "human"]
BOT_HELP = f"one of {', '.join(AI_BOTS)}, or path/to/file.py:ClassName"


def cmd_play(args) -> None:
    from .bots import HumanBot

    print(f"You are playing heads-up No-Limit Hold'em against '{args.bot}'.")
    print(f"Blinds 1/2, {args.stack} chip stacks reset every hand. Type q to quit.\n")
    human, bot = HumanBot(), make_bot(args.bot, seed=args.seed)
    try:
        result = run_match(human, bot, hands=args.hands, seed=args.seed,
                           starting_stack=args.stack, log=print)
    except (KeyboardInterrupt, QuitGame):
        print(f"\nBye! Session result: {human.session:+d} chips")
        return
    print("\n" + result.summary())


def cmd_match(args) -> None:
    # Seed the bots too (if they use randomness) so a run can be replayed exactly.
    a, b = make_bot(args.bot_a, seed=args.seed), make_bot(args.bot_b, seed=args.seed + 1)
    if a.name == b.name:
        b.name += "-2"
    start = time.time()
    result = run_match(a, b, hands=args.hands, seed=args.seed,
                       starting_stack=args.stack, log=print if args.verbose else None,
                       show_hole_cards=args.show_cards)
    print(result.summary())
    print(f"({time.time() - start:.1f}s)")
    if hasattr(a, "model"):
        print(f"{a.name}'s read on {b.name}: {a.model}")


def cmd_tournament(args) -> None:
    names = args.bots or AI_BOTS
    for spec in names:
        load_bot_class(spec)  # fail fast on a typo before playing anything
    totals = {n: 0.0 for n in names}
    print(f"Round robin, {args.hands} hands per pairing (seed {args.seed})\n")
    for x, y in itertools.combinations(names, 2):
        a, b = make_bot(x, seed=args.seed), make_bot(y, seed=args.seed + 1)
        r = run_match(a, b, hands=args.hands, seed=args.seed, starting_stack=args.stack)
        totals[x] += r.bb_per_100(0)
        totals[y] -= r.bb_per_100(0)
        print(f"  {x:>8} vs {y:<8} {r.bb_per_100(0):+8.1f} bb/100")
    print("\nTotal bb/100 across pairings:")
    for name, score in sorted(totals.items(), key=lambda kv: -kv[1]):
        print(f"  {name:>8} {score:+8.1f}")


def cmd_equity(args) -> None:
    hole = parse_cards(args.hole)
    board = parse_cards(args.board) if args.board else []
    print(f"Hand: {cards_str(hole)} ({hand_class(hole)}, Chen score {chen_score(hole):g})")
    if board:
        print(f"Board: {cards_str(board)}")
        if len(board) >= 3:
            print(f"Made hand: {hand_name(evaluate(hole + board))}")
        if len(board) in (3, 4):
            outs = count_outs(hole, board)
            mult = 4 if len(board) == 3 else 2
            print(f"Outs to a straight or better: {outs} (rule of {mult}: ~{outs * mult}%)")
    if args.vs:
        opp = parse_cards(args.vs)
        if len(board) >= 3:
            eq = exact_equity(hole, opp, board)
            print(f"Exact equity vs {cards_str(opp)}: {eq:.1%}")
        else:
            eq = monte_carlo_equity(hole, board, args.iterations, known_opp=opp)
            print(f"Equity vs {cards_str(opp)} ({args.iterations} sims): {eq:.1%}")
    else:
        eq = monte_carlo_equity(hole, board, args.iterations)
        print(f"Equity vs a random hand ({args.iterations} sims): {eq:.1%}")


def cmd_eval(args) -> None:
    cards = parse_cards(args.cards)
    value = evaluate(cards)
    print(f"{cards_str(cards)} -> {hand_name(value)}  {value}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m pokerbot",
                                description="Heads-up No-Limit Hold'em pokerbot toolkit")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("play", help="play against a bot in the terminal")
    s.add_argument("--bot", default="equity", help=BOT_HELP)
    s.add_argument("--hands", type=int, default=100)
    s.add_argument("--stack", type=int, default=200)
    s.add_argument("--seed", type=int)
    s.set_defaults(func=cmd_play)

    s = sub.add_parser("match", help="bot vs bot")
    s.add_argument("bot_a", help=BOT_HELP)
    s.add_argument("bot_b", help=BOT_HELP)
    s.add_argument("--hands", type=int, default=1000)
    s.add_argument("--stack", type=int, default=200)
    s.add_argument("--seed", type=int, default=1)
    s.add_argument("-v", "--verbose", action="store_true", help="print every action")
    s.add_argument("--show-cards", action="store_true",
                   help="with --verbose, also print both players' hole cards")
    s.set_defaults(func=cmd_match)

    s = sub.add_parser("tournament", help="round robin between bots")
    s.add_argument("bots", nargs="*", metavar="BOT", help=BOT_HELP + " (default: all built-ins)")
    s.add_argument("--hands", type=int, default=500)
    s.add_argument("--stack", type=int, default=200)
    s.add_argument("--seed", type=int, default=1)
    s.set_defaults(func=cmd_tournament)

    s = sub.add_parser("equity", help="equity calculator")
    s.add_argument("hole", help='two cards, e.g. "AsKs"')
    s.add_argument("--board", help='0, 3, 4 or 5 cards, e.g. "Qs Js 2d"')
    s.add_argument("--vs", help="opponent's exact cards (otherwise: random hand)")
    s.add_argument("--iterations", type=int, default=5000)
    s.set_defaults(func=cmd_equity)

    s = sub.add_parser("eval", help="name the best hand in 5-7 cards")
    s.add_argument("cards")
    s.set_defaults(func=cmd_eval)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except BrokenPipeError:  # output piped into `head` etc.
        sys.stderr.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
