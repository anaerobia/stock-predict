"""
A starter bot - copy this file and make it yours.

Try it:
    python -m pokerbot match pokerbot/examples/my_first_bot.py:MyFirstBot station
    python -m pokerbot play --bot pokerbot/examples/my_first_bot.py:MyFirstBot

The tutorial in docs/pokerbot/04-build-your-own-bot.md walks through
improving it step by step.
"""

from pokerbot.engine import Bot, CallAction, CheckAction, FoldAction, GameView, RaiseAction
from pokerbot.equity import chen_score, monte_carlo_equity


class MyFirstBot(Bot):
    name = "my-first-bot"

    def get_action(self, view: GameView):
        # Step 1 - preflop: play good starting hands, fold bad ones.
        if view.street == "preflop":
            if chen_score(view.hole_cards) >= 8 and view.can(RaiseAction):
                return RaiseAction(min(3 * view.big_blind, view.max_raise))
            if chen_score(view.hole_cards) >= 4 or view.to_call == 0:
                return CheckAction() if view.can(CheckAction) else CallAction()
            return FoldAction()

        # Step 2 - postflop: how often do we win if the hand goes to showdown?
        equity = monte_carlo_equity(view.hole_cards, view.board, iterations=200)

        # Step 3 - bet our strong hands (half the pot).
        if equity > 0.7 and view.can(RaiseAction):
            amount = max(view.opp_bet, view.my_bet) + (view.pot + view.to_call) // 2
            return RaiseAction(max(view.min_raise, min(amount, view.max_raise)))

        # Step 4 - call only when the price is right (equity beats pot odds).
        if view.to_call == 0:
            return CheckAction()
        if equity > view.pot_odds:
            return CallAction()
        return FoldAction()
