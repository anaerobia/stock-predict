"""
The finished bot from docs/pokerbot/04-build-your-own-bot.md.

Each `get_action` branch is labelled with the tutorial step that added it.

    python -m pokerbot match pokerbot/examples/tutorial_bot.py:TutorialBot rule --hands 1000
"""

import random

from pokerbot.bots._sizing import raise_to
from pokerbot.engine import Bot, CallAction, CheckAction, FoldAction, GameView, RaiseAction
from pokerbot.equity import (board_range, chen_range, chen_score, chen_threshold_for_top,
                             count_outs, monte_carlo_equity)


class TutorialBot(Bot):
    name = "tutorial"

    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        # Step 6: opponent statistics.
        self.opp_decisions = 0
        self.opp_folds = 0
        self.opp_raises = 0

    # Step 6: learn from every finished hand.
    def handle_hand_over(self, result, seat):
        for entry in result.history:
            if entry.seat != seat and entry.action != "post":
                self.opp_decisions += 1
                self.opp_folds += entry.action == "fold"
                self.opp_raises += entry.action == "raise"

    def fold_rate(self):
        return (self.opp_folds + 1) / (self.opp_decisions + 5)

    def raise_rate(self):
        return (self.opp_raises + 1) / (self.opp_decisions + 4)

    # Step 7: what range does the opponent's betting represent?
    def opponent_range(self, view: GameView):
        opp = 1 - view.seat
        raised = [h for h in view.history if h.seat == opp and h.action == "raise"]
        if not raised:
            return None
        width = max(self.raise_rate(), 0.15)
        if view.board:
            return board_range(view.board, view.hole_cards, width, self.rng)
        return chen_range(chen_threshold_for_top(width))

    def get_action(self, view: GameView):
        # Step 2: preflop hand selection, looser on the button (step 5).
        if view.street == "preflop":
            score = chen_score(view.hole_cards)
            open_threshold = 7 if view.is_button else 9
            if score >= open_threshold and view.can(RaiseAction):
                return raise_to(view, 1.0)
            if score >= 4 or view.to_call == 0:
                return CheckAction() if view.can(CheckAction) else CallAction()
            return FoldAction()

        # Step 3: equity vs the opponent's range (step 7).
        equity = monte_carlo_equity(view.hole_cards, view.board, iterations=250,
                                    rng=self.rng, opp_range=self.opponent_range(view))

        # Step 4: value bets sized with hand strength.
        if equity > 0.75 and view.can(RaiseAction):
            return raise_to(view, 0.75)
        if equity > 0.6 and view.to_call == 0 and view.can(RaiseAction):
            return raise_to(view, 0.5)

        if view.to_call == 0:
            # Step 6: bluff (preferably with a draw) against opponents who fold.
            has_draw = count_outs(view.hole_cards, view.board) >= 8
            bluff_chance = self.fold_rate() * (0.6 if has_draw else 0.25)
            if view.is_button and view.can(RaiseAction) and self.rng.random() < bluff_chance:
                return raise_to(view, 0.5)
            return CheckAction()

        # Step 3: call when equity beats pot odds.
        return CallAction() if equity > view.pot_odds else FoldAction()
