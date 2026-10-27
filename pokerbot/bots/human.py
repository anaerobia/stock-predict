"""Play against the bots yourself from the terminal."""

from ..cards import cards_str
from ..engine import (Bot, CallAction, CheckAction, FoldAction, GameView,
                      HandResult, QuitGame, RaiseAction)


class HumanBot(Bot):
    name = "Hero"  # poker slang for "the player whose view we follow"

    def __init__(self, input_fn=input, print_fn=print):
        self.input = input_fn
        self.print = print_fn
        self.session = 0  # chips won/lost so far

    def get_action(self, view: GameView):
        p = self.print
        p("")
        p(f"  Your cards: {cards_str(view.hole_cards)}   Board: {cards_str(view.board) or '-'}")
        p(f"  Pot: {view.pot}   Your stack: {view.my_stack}   Opponent stack: {view.opp_stack}")
        options = []
        if view.can(CheckAction):
            options.append("[k]check")
        if view.can(CallAction):
            options.append(f"[c]all {view.to_call} (pot odds {view.pot_odds:.0%})")
        if view.can(FoldAction):
            options.append("[f]old")
        if view.can(RaiseAction):
            verb = "raise" if view.to_call else "bet"
            options.append(f"[r]{verb} <to {view.min_raise}-{view.max_raise}>  [a]ll-in")
        p("  " + "   ".join(options) + "   [q]uit")
        while True:
            try:
                raw = self.input("  > ").strip().lower().split()
            except EOFError:
                raise QuitGame() from None
            if not raw:
                continue
            cmd, args = raw[0], raw[1:]
            if cmd in ("q", "quit", "exit"):
                raise QuitGame()
            if cmd in ("k", "check", "x") and view.can(CheckAction):
                return CheckAction()
            if cmd in ("c", "call"):
                return CallAction() if view.can(CallAction) else CheckAction()
            if cmd in ("f", "fold") and view.can(FoldAction):
                return FoldAction()
            if cmd in ("a", "allin", "all-in") and view.can(RaiseAction):
                return RaiseAction(view.max_raise)
            if cmd in ("r", "b", "raise", "bet") and view.can(RaiseAction):
                if args and args[0].isdigit():
                    amount = int(args[0])
                    if view.min_raise <= amount <= view.max_raise:
                        return RaiseAction(amount)
                p(f"  Enter an amount between {view.min_raise} and {view.max_raise}, e.g. 'r {view.min_raise}'")
                continue
            p("  Not a legal choice, try again.")

    def handle_hand_over(self, result: HandResult, seat: int) -> None:
        self.session += result.deltas[seat]
        mine = result.deltas[seat]
        self.print(f"  Net this hand: {mine:+d}   Session: {self.session:+d}")
