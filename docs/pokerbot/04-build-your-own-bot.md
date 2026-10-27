# 4. Build your own bot – a hands-on tutorial

You'll build a bot in seven small steps. After each one, **run it** and see
the effect – that feedback loop is the whole craft of bot building.

The finished result is `pokerbot/examples/tutorial_bot.py`; peek at it if you
get stuck.

> **Goal of the chapter:** write, test and measure a bot that beats the
> calling station and the random bot by a wide margin and breaks even with
> RuleBot – and know how to keep improving it.

---

## Step 0 – Set up

Work from the repository root. Nothing to install; Python 3.9+ is enough.

```bash
python -m unittest discover -s pokerbot/tests -t .      # everything should say OK
cp pokerbot/examples/my_first_bot.py my_bot.py           # your bot lives here
```

Any file with a `Bot` subclass can be loaded by the CLI with
`path/to/file.py:ClassName`:

```bash
python -m pokerbot match my_bot.py:MyFirstBot station --hands 500
python -m pokerbot play --bot my_bot.py:MyFirstBot          # play it yourself
```

## Step 1 – The smallest legal bot

Replace the contents of `my_bot.py` with:

```python
from pokerbot.engine import Bot, CallAction, CheckAction

class MyBot(Bot):
    name = "mybot"

    def get_action(self, view):
        return CheckAction() if view.can(CheckAction) else CallAction()
```

Run it against `random`:

```bash
python -m pokerbot match my_bot.py:MyBot random --hands 2000
```

This is the calling station. It never makes a mistake by folding, but it never
wins a pot unless it has the best hand at showdown. **Lesson:** always
check `view.can(...)` before returning an action (illegal actions become
check/fold).

## Step 2 – Choose your starting hands

Most of the money in heads-up is won or lost by playing too many or too few
hands. Use the Chen score (chapter 2.5):

```python
from pokerbot.engine import Bot, CallAction, CheckAction, FoldAction, RaiseAction
from pokerbot.equity import chen_score
from pokerbot.bots._sizing import raise_to

class MyBot(Bot):
    name = "mybot"

    def get_action(self, view):
        if view.street == "preflop":
            score = chen_score(view.hole_cards)
            if score >= 8 and view.can(RaiseAction):
                return raise_to(view, 1.0)          # pot-sized raise
            if score >= 4 or view.to_call == 0:
                return CheckAction() if view.can(CheckAction) else CallAction()
            return FoldAction()
        return CheckAction() if view.can(CheckAction) else CallAction()
```

Try different thresholds (6, 8, 10). Heads-up rewards **wide** ranges: with
only one opponent, average hands are often the best hand.

## Step 3 – Equity vs pot odds after the flop

Replace the last line with a real postflop decision (chapter 2.1–2.2):

```python
from pokerbot.equity import monte_carlo_equity

        # ... inside get_action, after the preflop block:
        equity = monte_carlo_equity(view.hole_cards, view.board, iterations=250)
        if view.to_call == 0:
            return CheckAction()
        return CallAction() if equity > view.pot_odds else FoldAction()
```

Now the bot folds weak hands to bets and calls with good ones. It still
**never bets** after the flop, so it leaves value on the table.

Speed check: 250 iterations take a few milliseconds. If your bot is slow, time
a match (`match` prints elapsed seconds) and reduce iterations.

## Step 4 – Bet your strong hands (value betting)

Add, before the `to_call == 0` check:

```python
        if equity > 0.75 and view.can(RaiseAction):
            return raise_to(view, 0.75)             # 3/4 pot
        if equity > 0.6 and view.to_call == 0 and view.can(RaiseAction):
            return raise_to(view, 0.5)              # 1/2 pot
```

Measure against the calling station – this step is where you start crushing
it, because the station pays off every value bet:

```bash
python -m pokerbot match my_bot.py:MyBot station --hands 2000 --seed 1
```

## Step 5 – Use position

On the button you act last after the flop, so you can play more hands:

```python
            open_threshold = 7 if view.is_button else 9
            if score >= open_threshold and view.can(RaiseAction):
                return raise_to(view, 1.0)
```

## Step 6 – Watch your opponent (and bluff the ones who fold)

Give the bot memory. `handle_hand_over` sees every action of every hand:

```python
import random

class MyBot(Bot):
    name = "mybot"

    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.opp_decisions = self.opp_folds = self.opp_raises = 0

    def handle_hand_over(self, result, seat):
        for entry in result.history:
            if entry.seat != seat and entry.action != "post":
                self.opp_decisions += 1
                self.opp_folds += entry.action == "fold"
                self.opp_raises += entry.action == "raise"

    def fold_rate(self):
        return (self.opp_folds + 1) / (self.opp_decisions + 5)   # smoothed
```

Then, when checked to on the button, sometimes bet as a bluff – more often
against folders, and more often with a draw (a semi-bluff):

```python
from pokerbot.equity import count_outs

        if view.to_call == 0:
            has_draw = count_outs(view.hole_cards, view.board) >= 8
            bluff_chance = self.fold_rate() * (0.6 if has_draw else 0.25)
            if view.is_button and view.can(RaiseAction) and self.rng.random() < bluff_chance:
                return raise_to(view, 0.5)
            return CheckAction()
```

Note `seed=None` in `__init__`: the CLI passes `--seed` to any bot that accepts
a `seed` argument, so your runs stay reproducible.

## Step 7 – Put the opponent on a range

The biggest single upgrade (chapter 2.5 showed EquityBot going from −197 to
+38 bb/100 with it). When the opponent has raised, compute equity against the
hands they'd plausibly raise with instead of any two cards:

```python
from pokerbot.equity import board_range, chen_range, chen_threshold_for_top

    def raise_rate(self):
        return (self.opp_raises + 1) / (self.opp_decisions + 4)

    def opponent_range(self, view):
        opp = 1 - view.seat
        if not any(h.seat == opp and h.action == "raise" for h in view.history):
            return None                                     # any two cards
        width = max(self.raise_rate(), 0.15)                # top X% of hands
        if view.board:
            return board_range(view.board, view.hole_cards, width, self.rng)
        return chen_range(chen_threshold_for_top(width))

        # ... and in get_action:
        equity = monte_carlo_equity(view.hole_cards, view.board, iterations=250,
                                    rng=self.rng, opp_range=self.opponent_range(view))
```

## Checkpoint – how good is it?

The finished tutorial bot, 1 000 hands per opponent (seed 3):

```bash
python -m pokerbot match pokerbot/examples/tutorial_bot.py:TutorialBot station --hands 1000 --seed 3
```

| Opponent | Result (bb/100, ± 95% CI) |
|---|---|
| `station` | **+269 ± 68** |
| `random`  | **+447 ± 244** |
| `rule`    | −12 ± 70 (break-even) |
| `equity`  | −57 ± 64 |

Your challenge: **beat `equity`**. The next sections tell you how to work on
that systematically.

---

## How to improve a bot systematically

### 1. Measure properly

- Same deck seed for every version: `--seed 1`.
- Enough hands: a ±50 bb/100 interval needs a few thousand hands.
- Several seeds: run `--seed 1`, `2`, `3` and average.
- Read the `±` in the summary. If the interval includes zero, you haven't
  proven anything yet.

A tiny benchmark script you can keep next to your bot (run it from the
repository root with `PYTHONPATH=. python bench.py`):

```python
# bench.py
from pokerbot.bots import make_bot
from pokerbot.engine import run_match

def bench(spec, opponents=("station", "random", "rule", "equity"), hands=2000, seeds=(1, 2, 3)):
    for opp in opponents:
        scores = [run_match(make_bot(spec, seed=s), make_bot(opp, seed=s + 1),
                            hands=hands, seed=s).bb_per_100() for s in seeds]
        print(f"vs {opp:8} {sum(scores) / len(scores):+7.1f} bb/100  {[round(x) for x in scores]}")

bench("my_bot.py:MyBot")
```

### 2. Find the leak – read hand histories

```bash
python -m pokerbot match my_bot.py:MyBot equity --hands 50 --seed 1 --verbose --show-cards > hands.txt
```

Search `hands.txt` for the big pots (`grep -E "wins [0-9]{3}" hands.txt` finds
pots of 100 chips or more). For each one, ask: *at which decision did I go wrong, and what
did my bot believe at that moment?* Then add a `print` of `equity` and
`view.pot_odds` in `get_action` and replay with the same seed.

### 3. Test specific situations

Copy the `Scripted` bot from `pokerbot/tests/test_pokerbot.py` to force a
situation (e.g. "opponent raises to 6, then bets pot on every street") and
assert what your bot does.

### 4. Ideas that make bots stronger

- **Better preflop:** replace Chen with a precomputed equity table for all 169
  hand classes (EquityBot caches exactly this on the fly).
- **Separate stats per street and position:** "folds to a flop bet" is far more
  useful than an overall fold rate.
- **Hand-strength buckets:** group hands into e.g. 5 buckets and pick an
  action distribution per bucket – the first step towards abstraction (ch. 5).
- **Balanced sizing:** use the same bet size for value and bluffs so your size
  leaks nothing.
- **Exploit known bots:** RuleBot's bet size tells you its tier – a
  half-pot flop bet means "top pair". Can your bot learn that from data?

### Common bugs

| Symptom | Likely cause |
|---|---|
| Bot folds when it could check | Returned `FoldAction` without checking `view.can(CheckAction)` |
| Raises are tiny | Used "raise by" maths; `RaiseAction(x)` is "raise **to** x" |
| Raises ignored | Amount outside `[min_raise, max_raise]` is clamped – print both |
| Results change between identical runs | Bot uses `random` without a seed – accept a `seed` argument |
| Matches are very slow | Too many Monte Carlo iterations, or a range filter that rejects almost everything |
| `ModuleNotFoundError: pokerbot` | Run from the repository root |

---

## Exercises

1. Do steps 1–7 yourself, measuring after each step. Which step gave the
   biggest jump against `station`? Against `rule`?
2. Make the bot beat `rule` by more than its confidence interval over 5 000
   hands.
3. Write a bot that specifically exploits `RuleBot` (read its source!). Then
   check how that bot does against `equity` – exploitation has a cost.
4. Beat `equity`.

Next: [5. Going further →](05-going-further.md)
