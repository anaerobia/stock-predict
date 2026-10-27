"""
Heads-up No-Limit Texas Hold'em engine.

The engine owns the cards and the chips; bots only ever see a `GameView` and
answer with an action. This mirrors how competition engines (e.g. MIT
Pokerbots) work: the engine calls your bot's `get_action`, validates the
answer, and moves the game forward.

Rules implemented
-----------------
* Two players. Each hand both start with `starting_stack` chips (stacks reset
  every hand; the running total is tracked as each bot's *bankroll*).
* The button posts the small blind and acts first preflop; the other player
  posts the big blind and acts first on the flop, turn and river.
* No-limit betting. `RaiseAction(amount)` means "raise TO amount" (the total
  you will have put in on this street), not "raise BY".
* Minimum raise: the previous raise size (at least one big blind). A player
  may always go all-in for less. Bets are capped at the effective stack so
  nobody can bet chips the opponent could never call.
* Showdown: best five-card hand from hole cards + board wins; ties split.

Illegal actions never crash the game: they are converted to CHECK if that is
legal and FOLD otherwise, and raise sizes are clamped into the legal range.
"""

import random
import time
from dataclasses import dataclass, field
from typing import List, NamedTuple, Optional, Sequence, Tuple, Type, Union

from .cards import Card, Deck, cards_str
from .evaluator import evaluate, hand_name

STREETS = ["preflop", "flop", "turn", "river"]
BOARD_SIZE = {"preflop": 0, "flop": 3, "turn": 4, "river": 5}


# --------------------------------------------------------------------- actions
class FoldAction(NamedTuple):
    def __str__(self) -> str:
        return "fold"


class CheckAction(NamedTuple):
    def __str__(self) -> str:
        return "check"


class CallAction(NamedTuple):
    def __str__(self) -> str:
        return "call"


class RaiseAction(NamedTuple):
    amount: int  # raise TO this street total

    def __str__(self) -> str:
        return f"raise to {self.amount}"


Action = Union[FoldAction, CheckAction, CallAction, RaiseAction]


class QuitGame(BaseException):
    """Raised by a bot (e.g. the human player) to stop the match immediately.

    It derives from BaseException so the engine's "a crashing bot just loses
    the decision" handler (which catches Exception) does not swallow it.
    """


class HistoryEntry(NamedTuple):
    street: str
    seat: int
    action: str    # "post", "fold", "check", "call", "raise"
    amount: int    # street total after the action (blinds/raises/calls)


# ------------------------------------------------------------------ bot view
@dataclass(frozen=True)
class GameView:
    """Everything a bot is allowed to know when it must act.

    All chip amounts are integers. "bet" values are amounts put in on the
    *current street*; `pot` includes everything committed so far by both
    players, including current-street bets.
    """
    seat: int                      # 0 or 1
    hand_number: int
    street: str                    # "preflop", "flop", "turn", "river"
    hole_cards: Tuple[Card, ...]
    board: Tuple[Card, ...]
    is_button: bool                # True = small blind / in position postflop
    pot: int
    my_stack: int                  # chips behind (not yet committed)
    opp_stack: int
    my_bet: int                    # committed this street
    opp_bet: int
    to_call: int                   # chips needed to call (0 = can check)
    min_raise: int                 # smallest legal RaiseAction amount
    max_raise: int                 # largest legal RaiseAction amount (all-in)
    legal_actions: Tuple[Type, ...]
    big_blind: int
    history: Tuple[HistoryEntry, ...]
    bankroll: int                  # my running profit across the match

    def can(self, action_type: Type) -> bool:
        return action_type in self.legal_actions

    @property
    def pot_odds(self) -> float:
        """Fraction of the final pot we must contribute to call: to_call / (pot + to_call)."""
        return self.to_call / (self.pot + self.to_call) if self.to_call else 0.0

    def street_actions(self, street: Optional[str] = None) -> List[HistoryEntry]:
        street = street or self.street
        return [h for h in self.history if h.street == street and h.action != "post"]


@dataclass
class HandResult:
    hand_number: int
    button: int
    deltas: Tuple[int, int]               # chips won (+) / lost (-) per seat
    hole_cards: Tuple[Tuple[Card, ...], Tuple[Card, ...]]
    board: Tuple[Card, ...]
    showdown: bool                        # True if cards were revealed
    winner: Optional[int]                 # None on a split pot
    history: Tuple[HistoryEntry, ...]
    pot: int
    description: str = ""

    def visible_cards(self, seat: int) -> Optional[Tuple[Card, ...]]:
        """Opponent cards a bot is allowed to see (only after a showdown)."""
        return self.hole_cards[seat] if self.showdown else None


# ---------------------------------------------------------------- base bot
class Bot:
    """Base class. Override `get_action`; the two hooks are optional.

    Bots must not mutate the GameView. Keep any memory (opponent statistics,
    learned parameters) on `self` - the same bot object plays the whole match.
    """

    name = "bot"

    def handle_new_hand(self, view: GameView) -> None:
        """Called once per hand after cards are dealt, before any action."""

    def get_action(self, view: GameView) -> Action:
        raise NotImplementedError

    def handle_hand_over(self, result: HandResult, seat: int) -> None:
        """Called after every hand. `result.visible_cards(1 - seat)` reveals
        the opponent's cards if there was a showdown."""


# ------------------------------------------------------------------ engine
class _Hand:
    """Mutable state of a single hand. Internal - bots never touch this."""

    def __init__(self, bots, button, hand_number, rng, starting_stack, small_blind,
                 big_blind, bankrolls, log, time_limit, show_hole_cards=False):
        self.bots = bots
        self.button = button
        self.hand_number = hand_number
        self.sb, self.bb = small_blind, big_blind
        self.stacks = [starting_stack, starting_stack]
        self.committed = [0, 0]       # total put in this hand
        self.bets = [0, 0]            # put in this street
        self.folded: Optional[int] = None
        self.history: List[HistoryEntry] = []
        self.bankrolls = bankrolls
        self.log = log
        self.time_limit = time_limit
        self.show_hole_cards = show_hole_cards
        self.street = "preflop"

        deck = Deck(rng)
        self.hole = (tuple(deck.deal(2)), tuple(deck.deal(2)))
        self.full_board = tuple(deck.deal(5))

    # -- helpers -------------------------------------------------------------
    @property
    def board(self) -> Tuple[Card, ...]:
        return self.full_board[:BOARD_SIZE[self.street]]

    @property
    def pot(self) -> int:
        return sum(self.committed)

    def _put_in(self, seat: int, street_total: int) -> None:
        """Move chips from the stack so this street's bet equals street_total."""
        add = min(street_total - self.bets[seat], self.stacks[seat])
        self.stacks[seat] -= add
        self.bets[seat] += add
        self.committed[seat] += add

    def _raise_bounds(self, seat: int, last_raise: int) -> Tuple[int, int]:
        opp = 1 - seat
        current = max(self.bets)
        max_to = min(self.bets[seat] + self.stacks[seat], self.bets[opp] + self.stacks[opp])
        min_to = min(current + max(last_raise, self.bb), max_to)
        return min_to, max_to

    def _legal(self, seat: int, last_raise: int):
        opp = 1 - seat
        to_call = max(self.bets) - self.bets[seat]
        min_to, max_to = self._raise_bounds(seat, last_raise)
        legal = [CallAction, FoldAction] if to_call > 0 else [CheckAction]
        if self.stacks[opp] > 0 and max_to > max(self.bets):
            legal.append(RaiseAction)
        return tuple(legal), to_call, min_to, max_to

    def view(self, seat: int, last_raise: int = 0) -> GameView:
        legal, to_call, min_to, max_to = self._legal(seat, last_raise)
        return GameView(
            seat=seat, hand_number=self.hand_number, street=self.street,
            hole_cards=self.hole[seat], board=self.board,
            is_button=(seat == self.button), pot=self.pot,
            my_stack=self.stacks[seat], opp_stack=self.stacks[1 - seat],
            my_bet=self.bets[seat], opp_bet=self.bets[1 - seat],
            to_call=min(to_call, self.stacks[seat]),
            min_raise=min_to, max_raise=max_to, legal_actions=legal,
            big_blind=self.bb, history=tuple(self.history),
            bankroll=self.bankrolls[seat],
        )

    def _ask(self, seat: int, view: GameView) -> Action:
        bot = self.bots[seat]
        start = time.perf_counter()
        try:
            action = bot.get_action(view)
        except Exception as exc:  # a crashing bot loses the decision, not the match
            self.log(f"  ! {bot.name} raised {type(exc).__name__}: {exc}")
            action = None
        if self.time_limit and time.perf_counter() - start > self.time_limit:
            self.log(f"  ! {bot.name} exceeded the {self.time_limit}s time limit")
            action = None
        return self._sanitize(action, view)

    @staticmethod
    def _sanitize(action, view: GameView) -> Action:
        fallback = CheckAction() if view.can(CheckAction) else FoldAction()
        if action is None or type(action) not in view.legal_actions:
            if isinstance(action, CallAction) and view.can(CheckAction):
                return CheckAction()  # "call" of zero is a check
            if isinstance(action, RaiseAction) and view.can(CallAction):
                return CallAction()  # can't raise (opponent all-in): call instead
            return fallback
        if isinstance(action, RaiseAction):
            amount = int(action.amount)
            return RaiseAction(max(view.min_raise, min(amount, view.max_raise)))
        return action

    # -- flow ----------------------------------------------------------------
    def post_blinds(self) -> None:
        bb_seat = 1 - self.button
        self._put_in(self.button, self.sb)
        self.history.append(HistoryEntry("preflop", self.button, "post", self.bets[self.button]))
        self._put_in(bb_seat, self.bb)
        self.history.append(HistoryEntry("preflop", bb_seat, "post", self.bets[bb_seat]))

    def betting_round(self) -> None:
        first = self.button if self.street == "preflop" else 1 - self.button
        if self.street != "preflop":
            self.bets = [0, 0]
        if min(self.stacks) == 0 and self.bets[0] == self.bets[1]:
            return  # someone is all-in: no more betting, just run the board out
        acted = [False, False]
        last_raise = self.bb
        seat = first
        while True:
            done = all(
                self.stacks[s] == 0 or (acted[s] and self.bets[s] == max(self.bets))
                for s in (0, 1)
            )
            # Facing an all-in for less than our bet (we already matched or exceeded it).
            if done or (self.stacks[1 - seat] == 0 and self.bets[seat] >= self.bets[1 - seat]):
                break
            if self.stacks[seat] == 0:
                seat = 1 - seat
                continue

            view = self.view(seat, last_raise)
            action = self._ask(seat, view)
            acted[seat] = True
            name = self.bots[seat].name

            if isinstance(action, FoldAction):
                self.folded = seat
                self.history.append(HistoryEntry(self.street, seat, "fold", self.bets[seat]))
                self.log(f"  {name} folds")
                return
            if isinstance(action, CheckAction):
                self.history.append(HistoryEntry(self.street, seat, "check", self.bets[seat]))
                self.log(f"  {name} checks")
            elif isinstance(action, CallAction):
                self._put_in(seat, max(self.bets))
                self.history.append(HistoryEntry(self.street, seat, "call", self.bets[seat]))
                allin = " (all-in)" if self.stacks[seat] == 0 else ""
                self.log(f"  {name} calls {view.to_call}{allin}")
            else:  # RaiseAction
                current = max(self.bets)
                self._put_in(seat, action.amount)
                last_raise = max(last_raise, self.bets[seat] - current)
                acted[1 - seat] = False  # the opponent must respond to the raise
                self.history.append(HistoryEntry(self.street, seat, "raise", self.bets[seat]))
                verb = "bets" if current == 0 else "raises to"
                allin = " (all-in)" if self.stacks[seat] == 0 else ""
                self.log(f"  {name} {verb} {self.bets[seat]}{allin}")
            seat = 1 - seat

        self._refund_uncalled()

    def _refund_uncalled(self) -> None:
        """If one player bet more than the other could match, return the excess."""
        hi = 0 if self.bets[0] > self.bets[1] else 1
        excess = self.bets[hi] - self.bets[1 - hi]
        if excess > 0:
            self.bets[hi] -= excess
            self.committed[hi] -= excess
            self.stacks[hi] += excess

    def play(self) -> HandResult:
        names = [b.name for b in self.bots]
        self.log(f"Hand #{self.hand_number}: {names[self.button]} has the button")
        if self.show_hole_cards:
            for s in (0, 1):
                self.log(f"  {names[s]} is dealt {cards_str(self.hole[s])}")
        self.post_blinds()
        for seat in (0, 1):
            self.bots[seat].handle_new_hand(self.view(seat, self.bb))

        for street in STREETS:
            self.street = street
            if street != "preflop":
                self.log(f" {street.upper()}: {cards_str(self.board)}  (pot {self.pot})")
            self.betting_round()
            if self.folded is not None:
                break

        pot = self.pot
        if self.folded is not None:
            winner = 1 - self.folded
            gains = [0, 0]
            gains[winner] = pot
            showdown = False
            desc = f"{names[winner]} wins {pot} (opponent folded)"
        else:
            self.street = "river"
            showdown = True
            values = [evaluate(list(self.hole[s]) + list(self.full_board)) for s in (0, 1)]
            for s in (0, 1):
                self.log(f"  {names[s]} shows {cards_str(self.hole[s])}: {hand_name(values[s])}")
            if values[0] == values[1]:
                winner = None
                half = pot // 2
                gains = [half, half]
                gains[1 - self.button] += pot - 2 * half  # odd chip: out of position
                desc = f"Split pot of {pot}"
            else:
                winner = 0 if values[0] > values[1] else 1
                gains = [0, 0]
                gains[winner] = pot
                desc = f"{names[winner]} wins {pot} with {hand_name(values[winner])}"
        self.log(f"  => {desc}")

        deltas = (gains[0] - self.committed[0], gains[1] - self.committed[1])
        return HandResult(
            hand_number=self.hand_number, button=self.button, deltas=deltas,
            hole_cards=self.hole, board=self.full_board if showdown else self.board,
            showdown=showdown, winner=winner, history=tuple(self.history), pot=pot,
            description=desc,
        )


def play_hand(bots: Sequence[Bot], button: int = 0, hand_number: int = 1,
              rng: Optional[random.Random] = None, starting_stack: int = 200,
              small_blind: int = 1, big_blind: int = 2,
              bankrolls: Sequence[int] = (0, 0), log=None,
              time_limit: Optional[float] = None,
              show_hole_cards: bool = False) -> HandResult:
    """Play one hand between bots[0] (seat 0) and bots[1] (seat 1).

    log:             callable receiving one line of hand history (e.g. print)
    time_limit:      seconds a bot may think per decision (None = unlimited)
    show_hole_cards: also log both players' hole cards (spectator mode)
    """
    hand = _Hand(list(bots), button, hand_number, rng or random.Random(), starting_stack,
                 small_blind, big_blind, list(bankrolls), log or (lambda msg: None), time_limit,
                 show_hole_cards)
    result = hand.play()
    for seat in (0, 1):
        bots[seat].handle_hand_over(result, seat)
    return result


@dataclass
class MatchResult:
    names: Tuple[str, str]
    hands: int
    bankrolls: Tuple[int, int]
    big_blind: int
    showdowns: int = 0
    per_hand: List[int] = field(default_factory=list)  # seat-0 delta per hand

    def bb_per_100(self, seat: int = 0) -> float:
        """Win rate in big blinds per 100 hands - the standard poker metric."""
        return 100.0 * self.bankrolls[seat] / self.big_blind / max(self.hands, 1)

    def std_error_bb100(self) -> float:
        """Standard error of seat 0's bb/100, to judge if a result is just luck."""
        n = len(self.per_hand)
        if n < 2:
            return float("inf")
        mean = sum(self.per_hand) / n
        var = sum((x - mean) ** 2 for x in self.per_hand) / (n - 1)
        return 100.0 * (var / n) ** 0.5 / self.big_blind

    def summary(self) -> str:
        a, b = self.names
        bb100 = self.bb_per_100(0)
        se = self.std_error_bb100()
        return (f"{a}: {self.bankrolls[0]:+d} chips ({bb100:+.1f} bb/100 ± {1.96 * se:.1f})\n"
                f"{b}: {self.bankrolls[1]:+d} chips ({-bb100:+.1f} bb/100)\n"
                f"hands: {self.hands}, showdowns: {self.showdowns}")


def run_match(bot_a: Bot, bot_b: Bot, hands: int = 1000, seed: Optional[int] = None,
              starting_stack: int = 200, small_blind: int = 1, big_blind: int = 2,
              log=None, time_limit: Optional[float] = None,
              show_hole_cards: bool = False) -> MatchResult:
    """Play `hands` hands, alternating the button every hand.

    Pass the same `seed` to replay exactly the same cards - essential when you
    compare two versions of a bot.
    """
    rng = random.Random(seed)
    bots = [bot_a, bot_b]
    bankrolls = [0, 0]
    result = MatchResult(names=(bot_a.name, bot_b.name), hands=hands,
                         bankrolls=(0, 0), big_blind=big_blind)
    for n in range(1, hands + 1):
        hr = play_hand(bots, button=(n - 1) % 2, hand_number=n, rng=rng,
                       starting_stack=starting_stack, small_blind=small_blind,
                       big_blind=big_blind, bankrolls=bankrolls, log=log,
                       time_limit=time_limit, show_hole_cards=show_hole_cards)
        bankrolls[0] += hr.deltas[0]
        bankrolls[1] += hr.deltas[1]
        result.showdowns += hr.showdown
        result.per_hand.append(hr.deltas[0])
    result.bankrolls = (bankrolls[0], bankrolls[1])
    return result
