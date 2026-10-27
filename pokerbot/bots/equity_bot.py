"""
EquityBot - decisions driven by equity, pot odds and an opponent model.

Every decision follows the same recipe:

1. Estimate the opponent's *range*. If they have bet or raised this hand we
   assume they hold roughly the top X% of hands, where X is how often we
   have seen them be aggressive (an aggressive opponent has a wide range).
2. Estimate our *equity* against that range by Monte Carlo simulation.
3. Compare equity with the *pot odds* to decide whether calling is +EV,
   and bet/raise for value when equity is high. Size bets as a fraction
   of the pot that grows with equity.
4. Bluff a small, controlled fraction of the time so we are not purely
   predictable - most often when we also have outs (a semi-bluff).
"""

import random
from typing import Dict, Optional

from ..engine import (Bot, CallAction, CheckAction, FoldAction, GameView,
                      HandResult, RaiseAction)
from ..equity import (board_range, chen_range, chen_threshold_for_top,
                      count_outs, hand_class, monte_carlo_equity)
from ._sizing import raise_to


class OpponentModel:
    """Running statistics about the opponent, updated after every hand.

    VPIP - % of hands where they voluntarily put chips in preflop
    PFR  - % of hands where they raised preflop
    aggression - fraction of decisions that were bets/raises
    postflop aggression - the same, after the flop only
    """

    def __init__(self):
        self.hands = 0
        self.vpip_hands = 0
        self.pfr_hands = 0
        self.raises = 0
        self.calls = 0
        self.checks = 0
        self.folds = 0
        self.post_raises = 0
        self.post_decisions = 0

    def update(self, result: HandResult, opp_seat: int) -> None:
        self.hands += 1
        pre = [h for h in result.history if h.seat == opp_seat and h.street == "preflop"
               and h.action != "post"]
        if any(h.action in ("call", "raise") for h in pre):
            self.vpip_hands += 1
        if any(h.action == "raise" for h in pre):
            self.pfr_hands += 1
        for h in result.history:
            if h.seat != opp_seat or h.action == "post":
                continue
            if h.street != "preflop":
                self.post_decisions += 1
                self.post_raises += h.action == "raise"
            if h.action == "raise":
                self.raises += 1
            elif h.action == "call":
                self.calls += 1
            elif h.action == "check":
                self.checks += 1
            elif h.action == "fold":
                self.folds += 1

    @property
    def vpip(self) -> float:
        return (self.vpip_hands + 3) / (self.hands + 5)  # prior: ~60% (HU is loose)

    @property
    def pfr(self) -> float:
        return (self.pfr_hands + 2) / (self.hands + 5)   # prior: ~40%

    @property
    def aggression(self) -> float:
        """Fraction of their decisions that were bets/raises (smoothed)."""
        total = self.raises + self.calls + self.checks + self.folds
        return (self.raises + 3) / (total + 10)

    @property
    def post_aggression(self) -> float:
        return (self.post_raises + 3) / (self.post_decisions + 10)

    @property
    def fold_rate(self) -> float:
        total = self.raises + self.calls + self.checks + self.folds
        return (self.folds + 2) / (total + 10)

    def __str__(self) -> str:
        return (f"hands={self.hands} VPIP={self.vpip:.0%} PFR={self.pfr:.0%} "
                f"aggr={self.aggression:.0%} postflop-aggr={self.post_aggression:.0%} "
                f"fold={self.fold_rate:.0%}")


class EquityBot(Bot):
    name = "equity"

    def __init__(self, iterations: int = 300, bluff_freq: float = 0.08,
                 seed: Optional[int] = None, use_model: bool = True):
        self.iterations = iterations
        self.bluff_freq = bluff_freq
        self.use_model = use_model
        self.rng = random.Random(seed)
        self.model = OpponentModel()
        self._preflop_cache: Dict[str, float] = {}

    # -- learning --------------------------------------------------------------
    def handle_hand_over(self, result: HandResult, seat: int) -> None:
        self.model.update(result, 1 - seat)

    # -- ranges & equity -------------------------------------------------------
    def opponent_range(self, view: GameView):
        """Filter for the hands the opponent plausibly holds, or None (= any)."""
        if not self.use_model:
            return None
        opp = 1 - view.seat
        raises = [h for h in view.history if h.seat == opp and h.action == "raise"]
        post_raises = [h for h in raises if h.street != "preflop"]
        if post_raises:
            # They bet after the flop: assume the top X% of hands *on this
            # board*, X = how often they bet postflop. Each extra bet narrows it.
            width = max(self.model.post_aggression, 0.15)
            width = max(width / (1 + 0.5 * (len(post_raises) - 1)), 0.05)
            return board_range(view.board, view.hole_cards, width, self.rng)
        if raises:
            # They raised preflop: assume the top X% of starting hands,
            # X = their observed preflop raise rate (never narrower than 10%).
            width = max(self.model.pfr, 0.10)
            width = max(width / (1 + 0.5 * (len(raises) - 1)), 0.05)
            return chen_range(chen_threshold_for_top(width))
        return None

    def equity(self, view: GameView) -> float:
        opp_range = self.opponent_range(view)
        if view.street == "preflop" and opp_range is None:
            # Preflop equity vs a random hand depends only on the hand class
            # (AKs, 72o, ...), so compute it once per class and cache it.
            key = hand_class(view.hole_cards)
            if key not in self._preflop_cache:
                self._preflop_cache[key] = monte_carlo_equity(
                    view.hole_cards, (), iterations=600, rng=self.rng)
            return self._preflop_cache[key]
        return monte_carlo_equity(view.hole_cards, view.board, self.iterations,
                                  rng=self.rng, opp_range=opp_range)

    # -- decisions -------------------------------------------------------------
    def get_action(self, view: GameView):
        eq = self.equity(view)
        if view.street == "preflop":
            return self._preflop(view, eq)
        return self._postflop(view, eq)

    def _preflop(self, view: GameView, eq: float):
        if view.to_call == 0:  # big blind after a limp
            if eq > 0.60 and view.can(RaiseAction):
                return raise_to(view, 1.0)
            return CheckAction()
        unopened = view.is_button and view.opp_bet == view.big_blind
        if unopened:
            if eq > 0.55 and view.can(RaiseAction):
                return RaiseAction(min(max(3 * view.big_blind, view.min_raise), view.max_raise))
            if eq > 0.40:
                return CallAction()
            return FoldAction()
        # Facing a raise.
        if eq > 0.62 and view.can(RaiseAction):
            return raise_to(view, 1.0)
        return CallAction() if eq > view.pot_odds + 0.05 else FoldAction()

    def _postflop(self, view: GameView, eq: float):
        outs = count_outs(view.hole_cards, view.board)
        # Value bet / raise. Bigger equity -> bigger bet (50% .. 100% pot).
        if eq > 0.70 and view.can(RaiseAction):
            if eq > 0.90 and view.max_raise <= view.pot * 1.5:
                return RaiseAction(view.max_raise)  # small stack behind: just shove
            return raise_to(view, 0.5 + (eq - 0.70) * 2.5)

        if view.to_call == 0:
            if eq > 0.55 and view.can(RaiseAction):
                return raise_to(view, 0.5)
            # Bluff more against opponents who fold a lot; prefer semi-bluffs.
            bluff = self.bluff_freq * (2 if outs >= 8 else 1) * (self.model.fold_rate / 0.2)
            if view.can(RaiseAction) and self.rng.random() < min(bluff, 0.35):
                return raise_to(view, 0.5)
            return CheckAction()

        # Facing a bet: call when equity beats the price (plus a safety margin).
        # Drawing hands with outs get a small bonus for implied odds.
        implied = 0.03 if outs >= 8 and view.street != "river" else 0.0
        if eq + implied > view.pot_odds + 0.03:
            return CallAction()
        return FoldAction()
