"""
RuleBot - a "tight-aggressive" bot built from human-readable rules.

Preflop it uses the Chen score; postflop it sorts its hand into a tier:

    3  monster  - two pair or better that uses our hole cards
    2  strong   - top pair or an overpair
    1  marginal - a weaker pair, or a draw with 8+ outs
    0  nothing

and then acts on the tier. No simulations, so it is very fast - and also
exploitable, because its bet size tells you its tier.
"""

from collections import Counter

from ..engine import Bot, CallAction, GameView, RaiseAction
from ..equity import chen_score, count_outs
from ..evaluator import PAIR, TRIPS, TWO_PAIR, evaluate
from ._sizing import call_or_check, passive, raise_to


def board_category(board) -> int:
    """Category the board makes on its own (only pairs/trips matter here)."""
    counts = sorted(Counter(c.rank for c in board).values(), reverse=True)
    if counts and counts[0] >= 3:
        return TRIPS
    if len(counts) > 1 and counts[0] == 2 and counts[1] == 2:
        return TWO_PAIR
    if counts and counts[0] == 2:
        return PAIR
    return 0


def hand_tier(hole, board) -> int:
    value = evaluate(list(hole) + list(board))
    category = value[0]
    improved = category > board_category(board)  # our hole cards actually help
    if category >= TWO_PAIR and improved:
        return 3
    if category == PAIR and improved:
        pair_rank = value[1]
        top_board = max(c.rank for c in board)
        return 2 if pair_rank >= top_board else 1
    if count_outs(hole, board) >= 8:
        return 1
    return 0


class RuleBot(Bot):
    name = "rule"

    def __init__(self, open_chen: float = 6, three_bet_chen: float = 10,
                 defend_chen: float = 5):
        self.open_chen = open_chen            # raise first in with this or better
        self.three_bet_chen = three_bet_chen  # re-raise with this or better
        self.defend_chen = defend_chen        # call a raise with this or better

    def get_action(self, view: GameView):
        if view.street == "preflop":
            return self._preflop(view)
        return self._postflop(view)

    def _preflop(self, view: GameView):
        score = chen_score(view.hole_cards)
        facing_raise = view.to_call > 0 and view.opp_bet > view.big_blind
        if facing_raise:
            if score >= self.three_bet_chen and view.can(RaiseAction):
                return raise_to(view, 1.0)
            if score >= self.defend_chen or view.pot_odds < 0.2:
                return CallAction()
            return passive(view)
        # Unopened pot (small blind) or the big blind's option after a limp.
        if score >= self.open_chen and view.can(RaiseAction):
            return RaiseAction(min(max(3 * view.big_blind, view.min_raise), view.max_raise))
        if score >= self.defend_chen - 2:
            return call_or_check(view)
        return passive(view)

    def _postflop(self, view: GameView):
        tier = hand_tier(view.hole_cards, view.board)
        if tier == 3:
            if view.can(RaiseAction):
                return raise_to(view, 0.75)
            return call_or_check(view)
        if tier == 2:
            if view.to_call == 0 and view.can(RaiseAction):
                return raise_to(view, 0.5)
            return CallAction() if view.pot_odds < 0.4 else passive(view)
        if tier == 1:
            return CallAction() if 0 < view.pot_odds < 0.3 else passive(view)
        return passive(view)
