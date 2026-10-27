"""
Hand evaluator: turns 5, 6 or 7 cards into a comparable strength value.

`evaluate(cards)` returns a tuple `(category, tiebreak...)`. Python compares
tuples element by element, so a bigger tuple is always the better hand:

    evaluate(parse_cards("As Ks Qs Js Ts")) > evaluate(parse_cards("9h 9d 9c 9s 2d"))

Categories (higher is better):
    0 high card, 1 pair, 2 two pair, 3 three of a kind, 4 straight,
    5 flush, 6 full house, 7 four of a kind, 8 straight flush

The evaluator looks at all the cards at once (it never enumerates 5-card
subsets), which keeps Monte Carlo simulations fast enough in pure Python.
"""

from collections import Counter
from typing import Iterable, List, Optional, Sequence, Tuple

from .cards import RANK_NAMES, Card

HIGH_CARD, PAIR, TWO_PAIR, TRIPS, STRAIGHT, FLUSH, FULL_HOUSE, QUADS, STRAIGHT_FLUSH = range(9)

CATEGORY_NAMES = [
    "High Card", "Pair", "Two Pair", "Three of a Kind", "Straight",
    "Flush", "Full House", "Four of a Kind", "Straight Flush",
]

HandValue = Tuple[int, ...]


def _straight_high(ranks: Iterable[int]) -> Optional[int]:
    """Highest card of the best straight in `ranks`, or None. Handles A-2-3-4-5."""
    present = set(ranks)
    if 14 in present:
        present.add(1)  # the ace also plays low in the "wheel"
    for high in range(14, 4, -1):
        if all(r in present for r in range(high - 4, high + 1)):
            return high
    return None


def evaluate(cards: Sequence[Card]) -> HandValue:
    """Strength of the best 5-card hand that can be made from `cards` (5-7 cards)."""
    if not 5 <= len(cards) <= 7:
        raise ValueError(f"evaluate() needs 5-7 cards, got {len(cards)}")

    # Flushes and straight flushes: look only at the cards of the flush suit.
    suit_counts = Counter(c.suit for c in cards)
    flush_suit, flush_count = suit_counts.most_common(1)[0]
    flush_ranks: List[int] = []
    if flush_count >= 5:
        flush_ranks = sorted((c.rank for c in cards if c.suit == flush_suit), reverse=True)
        sf_high = _straight_high(flush_ranks)
        if sf_high:
            return (STRAIGHT_FLUSH, sf_high)

    # Group ranks by how many times they appear: [(count, rank), ...] best first.
    rank_counts = Counter(c.rank for c in cards)
    groups = sorted(((n, r) for r, n in rank_counts.items()), reverse=True)
    ranks_desc = sorted(rank_counts, reverse=True)

    if groups[0][0] == 4:
        quad = groups[0][1]
        kicker = max(r for r in ranks_desc if r != quad)
        return (QUADS, quad, kicker)

    trips = [r for n, r in groups if n == 3]
    pairs = [r for n, r in groups if n == 2]
    if trips and (len(trips) > 1 or pairs):
        top = trips[0]
        # The pair part may come from a second set of trips.
        pair = max([r for r in trips[1:]] + pairs)
        return (FULL_HOUSE, top, pair)

    if flush_ranks:
        return (FLUSH, *flush_ranks[:5])

    st_high = _straight_high(ranks_desc)
    if st_high:
        return (STRAIGHT, st_high)

    if trips:
        kickers = [r for r in ranks_desc if r != trips[0]][:2]
        return (TRIPS, trips[0], *kickers)

    if len(pairs) >= 2:
        hi, lo = pairs[0], pairs[1]
        kicker = max(r for r in ranks_desc if r not in (hi, lo))
        return (TWO_PAIR, hi, lo, kicker)

    if pairs:
        kickers = [r for r in ranks_desc if r != pairs[0]][:3]
        return (PAIR, pairs[0], *kickers)

    return (HIGH_CARD, *ranks_desc[:5])


def _plural(rank: int) -> str:
    name = RANK_NAMES[rank]
    return name + ("es" if name == "Six" else "s")


def hand_name(value: HandValue) -> str:
    """Human-readable description, e.g. 'Full House, Kings full of Twos'."""
    cat = value[0]
    if cat == STRAIGHT_FLUSH:
        return "Royal Flush" if value[1] == 14 else f"Straight Flush, {RANK_NAMES[value[1]]} high"
    if cat == QUADS:
        return f"Four of a Kind, {_plural(value[1])}"
    if cat == FULL_HOUSE:
        return f"Full House, {_plural(value[1])} full of {_plural(value[2])}"
    if cat == FLUSH:
        return f"Flush, {RANK_NAMES[value[1]]} high"
    if cat == STRAIGHT:
        return f"Straight, {RANK_NAMES[value[1]]} high"
    if cat == TRIPS:
        return f"Three of a Kind, {_plural(value[1])}"
    if cat == TWO_PAIR:
        return f"Two Pair, {_plural(value[1])} and {_plural(value[2])}"
    if cat == PAIR:
        return f"Pair of {_plural(value[1])}"
    return f"High Card, {RANK_NAMES[value[1]]}"
