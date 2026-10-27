"""Shared bet-sizing helpers for bots."""

from ..engine import CallAction, CheckAction, FoldAction, GameView, RaiseAction


def raise_to(view: GameView, pot_fraction: float) -> RaiseAction:
    """Bet or raise so that we add `pot_fraction` of the pot *after* calling.

    Facing no bet, pot_fraction=0.5 is a half-pot bet. Facing a bet,
    pot_fraction=1.0 is the classic "pot-sized raise".
    """
    pot_after_call = view.pot + view.to_call
    target = max(view.my_bet, view.opp_bet) + int(round(pot_fraction * pot_after_call))
    return RaiseAction(max(view.min_raise, min(target, view.max_raise)))


def passive(view: GameView):
    """Check when free, otherwise fold."""
    return CheckAction() if view.can(CheckAction) else FoldAction()


def call_or_check(view: GameView):
    return CheckAction() if view.can(CheckAction) else CallAction()
