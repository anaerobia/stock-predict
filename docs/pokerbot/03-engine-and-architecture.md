# 3. Engine and architecture

This chapter is the reference for the code: how the modules fit together, how a
hand is played, and exactly what your bot receives and may return.

> **Goal of the chapter:** know where every piece of logic lives and the
> contract between the engine and a bot.

---

## 3.1 Module map

```
            ┌────────────┐
            │  cards.py  │  Card, Deck, parse_cards
            └─────┬──────┘
                  │
            ┌─────▼──────┐
            │evaluator.py│  evaluate(cards) -> (category, tiebreaks...)
            └─────┬──────┘
          ┌───────┴────────┐
    ┌─────▼─────┐    ┌─────▼─────┐
    │ equity.py │    │ engine.py │  rules, betting, showdown,
    │ MC/exact  │    │           │  GameView, Bot, run_match
    │ Chen,     │    └─────┬─────┘
    │ ranges,   │          │ calls get_action(view)
    │ outs      │    ┌─────▼──────────────────────────────┐
    └─────▲─────┘    │ bots/  random station rule equity  │
          └──────────┤        human   (and yours)         │
                     └─────▲──────────────────────────────┘
                           │
                     ┌─────┴──────┐
                     │__main__.py │  CLI: play/match/tournament/equity/eval
                     └────────────┘
```

Dependencies only point "down": the engine knows nothing about specific bots,
and bots never touch engine internals.

## 3.2 The bot contract

```python
from pokerbot.engine import Bot, GameView, FoldAction, CheckAction, CallAction, RaiseAction

class MyBot(Bot):
    name = "mybot"

    def handle_new_hand(self, view: GameView) -> None:      # optional
        ...

    def get_action(self, view: GameView):                    # required
        return CheckAction() if view.can(CheckAction) else CallAction()

    def handle_hand_over(self, result, seat: int) -> None:   # optional
        ...
```

- **One object plays the whole match**, so store memory (opponent stats,
  learned parameters) on `self`.
- `get_action` is called every time it is your turn. Return one of the four
  action objects.
- `handle_new_hand` runs after the deal and blinds, before any action. (Its
  `view.legal_actions` is informational – you aren't being asked to act.)
- `handle_hand_over` runs after every hand with a `HandResult`. This is where
  learning happens.

### `GameView` fields

`GameView` is a frozen dataclass – read-only.

| Field | Type | Meaning |
|---|---|---|
| `seat` | int | 0 or 1 |
| `hand_number` | int | 1-based |
| `street` | str | `"preflop"`, `"flop"`, `"turn"`, `"river"` |
| `hole_cards` | tuple of Card | your two cards |
| `board` | tuple of Card | 0, 3, 4 or 5 community cards |
| `is_button` | bool | True = small blind, acts first preflop and last postflop |
| `pot` | int | everything committed by both players so far, including this street |
| `my_stack`, `opp_stack` | int | chips still behind (not yet committed) |
| `my_bet`, `opp_bet` | int | chips each put in *on this street* |
| `to_call` | int | chips needed to call; 0 means you may check |
| `min_raise`, `max_raise` | int | legal range for `RaiseAction(amount)` ("raise **to**") |
| `legal_actions` | tuple of classes | e.g. `(CallAction, FoldAction, RaiseAction)` |
| `big_blind` | int | 2 by default |
| `history` | tuple of `HistoryEntry` | every action this hand, blinds included |
| `bankroll` | int | your running profit in this match |

Helpers: `view.can(RaiseAction)`, `view.pot_odds`, `view.street_actions()`
(non-blind actions on the current street).

A `HistoryEntry` is `(street, seat, action, amount)` where `action` is
`"post"`, `"fold"`, `"check"`, `"call"` or `"raise"`, and `amount` is that
player's street total after the action. Postflop, a `"raise"` with nobody
having bet before is a *bet*.

Invariant (tested): `my_stack + opp_stack + pot == 2 × starting_stack`.

### `HandResult` fields

| Field | Meaning |
|---|---|
| `deltas` | `(seat0_profit, seat1_profit)`; always sums to 0 |
| `hole_cards` | both hands – **use `visible_cards(seat)`**, which returns the opponent's cards only if there was a showdown |
| `board` | cards dealt (all 5 at showdown) |
| `showdown`, `winner` | `winner` is `None` on a split pot |
| `history`, `pot`, `description` | full action list, final pot, one-line summary |

Peeking at `result.hole_cards[1 - seat]` after a fold would be cheating – a
real engine wouldn't send them. Stick to `visible_cards`.

## 3.3 How a hand is played (`engine._Hand.play`)

```
deal 2+2 hole cards and 5 board cards (board revealed street by street)
post blinds: button -> small blind, other -> big blind
for street in preflop, flop, turn, river:
    betting_round()
    if someone folded: stop
award the pot (fold, or showdown with evaluate())
call handle_hand_over on both bots
```

`betting_round()`:

```
first to act = button preflop, big blind postflop
reset street bets (postflop)
if someone is already all-in: skip (just deal the board out)
loop:
    stop if every player is all-in or has acted with bets equal
    stop if the opponent is all-in and we've matched them
    view   = snapshot for the player to act
    action = bot.get_action(view)   -> sanitised to something legal
    apply: fold ends the hand; check; call; raise reopens the action
           for the opponent and records the raise size for min-raise
    switch player
refund any uncalled chips
```

Seat 0 and seat 1 alternate the button every hand in `run_match`, so neither
bot gets a positional edge over a match.

## 3.4 Illegal moves, crashes and time

The engine never trusts a bot:

| Bot does | Engine does |
|---|---|
| Returns `CallAction` with nothing to call | treats it as `CheckAction` |
| Returns `RaiseAction` when raising is illegal (opponent all-in) | `CallAction` |
| Raise amount below `min_raise` / above `max_raise` | clamps into range |
| Returns anything else illegal / `None` / garbage | `CheckAction` if legal, else `FoldAction` |
| Raises an exception | logs it, then same fallback |
| Takes longer than `time_limit` seconds (if set) | logs it, then same fallback |

The time limit is checked *after* the bot returns (pure Python can't safely
interrupt a function), so it penalises slow decisions but can't stop an
infinite loop.

To *stop* a match on purpose a bot raises `QuitGame` (a `BaseException`, so the
crash handler above doesn't swallow it) – that's how `HumanBot` quits on `q`.

## 3.5 The evaluator (`evaluator.py`)

`evaluate(cards)` accepts 5, 6 or 7 cards and returns a tuple whose **first
element is the category** (0 high card … 8 straight flush) followed by
tie-breakers. Python compares tuples left to right, so "better hand" is just
`>`:

```python
>>> from pokerbot import evaluate, parse_cards, hand_name
>>> evaluate(parse_cards("Kh Kd Kc 2s 2d 2h 9c"))
(6, 13, 2)                       # full house, kings full of twos
>>> hand_name(_)
'Full House, Kings full of Twos'
```

Instead of trying all 21 five-card subsets of 7 cards, it works on counts:

1. If one suit has ≥ 5 cards: check those for a straight (straight flush),
   else remember the flush.
2. Group ranks by multiplicity → quads, full house (including two sets of
   trips), trips, two pair, pair.
3. Straights use a set of ranks; the ace is added as rank 1 for the wheel.

On 7 cards this measures ~11 µs per hand versus ~216 µs for trying all 21
subsets (about 19× faster), and it is the hot loop of every Monte Carlo
simulation. Serious bots use lookup-table evaluators
(e.g. the "Cactus Kev" or "two-plus-two" evaluators) that are another 100×
faster – a fun exercise.

## 3.6 Randomness and reproducibility

- `run_match(..., seed=S)` seeds the **deck**: the same seed deals the same
  cards in the same order.
- Bots that use randomness take their own `seed` argument (`RandomBot`,
  `EquityBot`). The CLI passes `--seed` to bot A and `--seed + 1` to bot B,
  so a CLI run is fully reproducible.
- When comparing two versions of your bot, keep **both** seeds fixed and only
  change the bot.

## 3.7 Tests

```bash
python -m unittest discover -s pokerbot/tests -t .
```

`pokerbot/tests/test_pokerbot.py` covers card parsing, every hand category and
ordering, kickers and the wheel, equity against known values, the Chen
formula, outs, blinds, min-raise, the big-blind option, postflop order,
all-ins, crashing/garbage bots, chip conservation over 2 000
random hands, view invariants, seed reproducibility and the human input loop.

A `Scripted` bot in the tests plays a fixed list of actions – copy it when you
need to test a specific situation for your own bot.

## 3.8 Extending the engine

Ideas, roughly in order of difficulty:

- **Different stacks / blinds:** `run_match(..., starting_stack=1000, big_blind=10)`.
- **Hand-history files:** pass `log=` a function that writes to a file.
- **Duplicate matches:** run the same seed twice with the bots swapped seats
  and sum the results – luck largely cancels.
- **A variant:** competitions often change the rules (MIT Pokerbots has used
  variants with extra cards or auctions each year). Most changes live in
  `_Hand.play` and `betting_round`.
- **Multi-way:** generalising to 3+ players touches nearly everything
  (side pots, action order) – a substantial project.

---

## Exercises

1. Add a `print(view)` to `MyFirstBot.get_action` and play one hand. Find
   each field from the table above.
2. Write a test (copy `Scripted`) where the small blind raises to 6, the big
   blind re-raises to 20, and check the small blind's `min_raise`.
   *(Answer: the re-raise was 14, so min is 34.)*
3. Implement a duplicate-match helper (`run_duplicate(bot_a_factory,
   bot_b_factory, hands, seed)`) and compare its standard error with
   `run_match` for the same number of hands.

Next: [4. Build your own bot →](04-build-your-own-bot.md)
