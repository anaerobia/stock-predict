"""
Pokerbot — a heads-up No-Limit Texas Hold'em engine and a family of bots.

Start here:
    python -m pokerbot --help

See pokerbot/README.md and docs/pokerbot/ for the full guide.
"""

from .cards import Card, Deck, parse_cards
from .evaluator import evaluate, hand_name
from .engine import (
    FoldAction, CheckAction, CallAction, RaiseAction,
    GameView, HandResult, play_hand, run_match,
)

__all__ = [
    "Card", "Deck", "parse_cards",
    "evaluate", "hand_name",
    "FoldAction", "CheckAction", "CallAction", "RaiseAction",
    "GameView", "HandResult", "play_hand", "run_match",
]
