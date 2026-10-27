"""
Cards and decks.

A card is a (rank, suit) pair. Ranks are integers 2..14 (11=J, 12=Q, 13=K,
14=A) so they compare naturally; suits are one of "cdhs". Cards print in the
standard two-character notation used by almost every poker tool: "As" is the
ace of spades, "Td" the ten of diamonds.
"""

import random
from typing import Iterable, List, NamedTuple, Optional

RANK_CHARS = "23456789TJQKA"
SUITS = "cdhs"
RANK_NAMES = {
    2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven",
    8: "Eight", 9: "Nine", 10: "Ten", 11: "Jack", 12: "Queen", 13: "King", 14: "Ace",
}


class Card(NamedTuple):
    rank: int  # 2..14
    suit: str  # one of "cdhs"

    @classmethod
    def from_str(cls, text: str) -> "Card":
        """Parse "As", "td", "10h" (10 is accepted as an alias for T)."""
        text = text.strip()
        if text[:2] == "10":
            text = "T" + text[2:]
        if len(text) != 2:
            raise ValueError(f"Invalid card {text!r}: expected rank+suit like 'As'")
        rank_ch, suit_ch = text[0].upper(), text[1].lower()
        if rank_ch not in RANK_CHARS:
            raise ValueError(f"Invalid rank {rank_ch!r} in {text!r}")
        if suit_ch not in SUITS:
            raise ValueError(f"Invalid suit {suit_ch!r} in {text!r}")
        return cls(RANK_CHARS.index(rank_ch) + 2, suit_ch)

    def __str__(self) -> str:
        return RANK_CHARS[self.rank - 2] + self.suit

    def __repr__(self) -> str:
        return f"Card({str(self)!r})"


FULL_DECK: List[Card] = [Card(r, s) for r in range(2, 15) for s in SUITS]


def parse_cards(text: str) -> List[Card]:
    """Parse a whitespace/comma separated list, or a run like "AsKd"."""
    text = text.replace(",", " ").strip()
    if not text:
        return []
    if " " not in text and len(text) > 3:
        text = " ".join(text[i:i + 2] for i in range(0, len(text), 2))
    cards = [Card.from_str(t) for t in text.split()]
    if len(set(cards)) != len(cards):
        raise ValueError(f"Duplicate card in {text!r}")
    return cards


def cards_str(cards: Iterable[Card]) -> str:
    return " ".join(str(c) for c in cards)


class Deck:
    """A shuffled 52-card deck. Pass an `rng` for reproducible games."""

    def __init__(self, rng: Optional[random.Random] = None, exclude: Iterable[Card] = ()):
        self.rng = rng or random.Random()
        excluded = set(exclude)
        self.cards = [c for c in FULL_DECK if c not in excluded]
        self.rng.shuffle(self.cards)

    def deal(self, n: int = 1) -> List[Card]:
        if n > len(self.cards):
            raise ValueError("Not enough cards left in the deck")
        dealt, self.cards = self.cards[:n], self.cards[n:]
        return dealt

    def __len__(self) -> int:
        return len(self.cards)
