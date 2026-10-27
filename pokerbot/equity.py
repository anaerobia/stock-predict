"""
Equity: how often a hand wins against an opponent if all cards are dealt out.

Two tools live here:

* `monte_carlo_equity` - deal random opponent hands and random remaining board
  cards thousands of times, count wins/ties. The result converges to the true
  equity as `iterations` grows (error shrinks like 1/sqrt(iterations)).

* `chen_score` - Bill Chen's quick preflop formula. It is a cheap stand-in for
  equity before the flop and is useful for describing *ranges*, e.g. "the
  opponent only raises hands with a Chen score of 7 or more".
"""

import math
import random
from typing import Callable, List, Optional, Sequence

from .cards import FULL_DECK, Card
from .evaluator import evaluate

# A range filter decides whether a sampled opponent hand is plausible.
RangeFilter = Callable[[Sequence[Card]], bool]


def monte_carlo_equity(
    hole: Sequence[Card],
    board: Sequence[Card] = (),
    iterations: int = 1000,
    rng: Optional[random.Random] = None,
    opp_range: Optional[RangeFilter] = None,
    known_opp: Optional[Sequence[Card]] = None,
) -> float:
    """Probability that `hole` beats one opponent at showdown (ties count half).

    hole:      our two hole cards
    board:     0, 3, 4 or 5 community cards already dealt
    opp_range: optional filter; sampled opponent hands that fail it are redrawn
               (up to a retry limit) so we estimate equity *versus a range*
    known_opp: fix the opponent's cards instead of sampling them (for tools/tests)
    """
    rng = rng or random.Random()
    used = set(hole) | set(board)
    if known_opp:
        used |= set(known_opp)
    stub = [c for c in FULL_DECK if c not in used]
    need_board = 5 - len(board)
    hole, board = list(hole), list(board)

    score = 0.0
    for _ in range(iterations):
        if known_opp:
            opp = list(known_opp)
            runout = rng.sample(stub, need_board)
        else:
            # Draw opponent cards, retrying when they fall outside the range.
            for _attempt in range(20):
                drawn = rng.sample(stub, 2 + need_board)
                opp = drawn[:2]
                if opp_range is None or opp_range(opp):
                    break
            runout = drawn[2:]
        full_board = board + runout
        mine = evaluate(hole + full_board)
        theirs = evaluate(opp + full_board)
        if mine > theirs:
            score += 1.0
        elif mine == theirs:
            score += 0.5
    return score / iterations


def exact_equity(hole: Sequence[Card], opp: Sequence[Card], board: Sequence[Card]) -> float:
    """Exact equity of `hole` vs a known `opp` hand by enumerating every runout.

    Fast on the turn/river; on the flop it enumerates C(45, 2) = 990 runouts.
    """
    from itertools import combinations

    used = set(hole) | set(opp) | set(board)
    stub = [c for c in FULL_DECK if c not in used]
    hole, opp, board = list(hole), list(opp), list(board)
    total = score = 0.0
    for runout in combinations(stub, 5 - len(board)):
        full = board + list(runout)
        a, b = evaluate(hole + full), evaluate(opp + full)
        score += 1.0 if a > b else 0.5 if a == b else 0.0
        total += 1
    return score / total


def chen_score(hole: Sequence[Card]) -> float:
    """Bill Chen's preflop hand score (roughly -1 for 72o up to 20 for AA).

    1. Score the highest card: A=10, K=8, Q=7, J=6, 10..2 = half their rank.
    2. Pairs: double it (minimum 5).
    3. Suited: +2.
    4. Gap between the cards: 1 gap -1, 2 gaps -2, 3 gaps -4, 4+ gaps -5.
    5. Straight bonus: +1 if gap <= 1 and both cards below a queen.
    6. Round half points up.
    """
    a, b = sorted(hole, key=lambda c: c.rank, reverse=True)
    high_points = {14: 10, 13: 8, 12: 7, 11: 6}
    score = high_points.get(a.rank, a.rank / 2)

    if a.rank == b.rank:
        return max(score * 2, 5)

    if a.suit == b.suit:
        score += 2
    gap = a.rank - b.rank - 1
    score -= {0: 0, 1: 1, 2: 2, 3: 4}.get(gap, 5)
    if gap <= 1 and a.rank < 12:
        score += 1
    return math.ceil(score)


def chen_range(min_score: float) -> RangeFilter:
    """A range filter: "hands with a Chen score of at least `min_score`"."""
    return lambda cards: chen_score(cards) >= min_score


def hand_class(hole: Sequence[Card]) -> str:
    """Canonical 169-class name of a starting hand: 'AA', 'AKs', 'T9o'."""
    from .cards import RANK_CHARS

    a, b = sorted(hole, key=lambda c: c.rank, reverse=True)
    ra, rb = RANK_CHARS[a.rank - 2], RANK_CHARS[b.rank - 2]
    if a.rank == b.rank:
        return ra + rb
    return ra + rb + ("s" if a.suit == b.suit else "o")


def count_outs(hole: Sequence[Card], board: Sequence[Card]) -> int:
    """Number of unseen cards that would improve us to a straight or better.

    Only meaningful on the flop or turn. Combine with the "rule of 2 and 4":
    equity of a draw ~= outs * 4% with two cards to come, outs * 2% with one.
    """
    from .evaluator import STRAIGHT

    if len(board) not in (3, 4):
        return 0
    cards = list(hole) + list(board)
    if evaluate(cards)[0] >= STRAIGHT:
        return 0
    seen = set(cards)
    return sum(
        1 for c in FULL_DECK
        if c not in seen and evaluate(cards + [c])[0] >= STRAIGHT
    )


def _chen_percentiles() -> List[float]:
    """Chen score of every one of the 1326 starting combos, best first."""
    from itertools import combinations
    return sorted((chen_score(combo) for combo in combinations(FULL_DECK, 2)), reverse=True)


_CHEN_SORTED: List[float] = []


def chen_threshold_for_top(fraction: float) -> float:
    """Chen score that marks the top `fraction` of starting hands.

    chen_threshold_for_top(0.10) -> the score you need to be in the best 10%.
    """
    global _CHEN_SORTED
    if not _CHEN_SORTED:
        _CHEN_SORTED = _chen_percentiles()
    fraction = min(max(fraction, 0.0), 1.0)
    index = min(int(fraction * len(_CHEN_SORTED)), len(_CHEN_SORTED) - 1)
    return _CHEN_SORTED[index]


def board_range(board: Sequence[Card], dead: Sequence[Card], top_fraction: float,
                rng: Optional[random.Random] = None, samples: int = 300) -> RangeFilter:
    """A range filter: "the top `top_fraction` of hands on this board".

    Postflop, preflop scores stop mattering - what counts is how strong a hand
    is *now*. We sample random opponent hands, rank them by their current
    made-hand strength, and keep everything at least as good as the cut-off.
    `dead` are cards the opponent cannot hold (our hole cards).
    """
    if len(board) < 3:
        raise ValueError("board_range needs a flop")
    rng = rng or random.Random()
    used = set(board) | set(dead)
    stub = [c for c in FULL_DECK if c not in used]
    board = list(board)
    values = sorted((evaluate(rng.sample(stub, 2) + board) for _ in range(samples)), reverse=True)
    cutoff = values[min(int(top_fraction * samples), samples - 1)]
    return lambda cards: evaluate(list(cards) + board) >= cutoff
