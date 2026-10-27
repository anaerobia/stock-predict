# 2. Strategy and the maths behind it

Poker is a game of **incomplete information**: you don't know the opponent's
cards or the cards still to come. A bot can't "know" the right move, but it can
**estimate the expected value** of each move and pick the best one. This
chapter builds up the handful of ideas every pokerbot uses, each tied to the
code that implements it.

> **Goal of the chapter:** understand equity, pot odds, EV, ranges and bet
> sizing well enough to read `pokerbot/bots/equity_bot.py` line by line.

---

## 2.1 Equity – "how often do I win?"

**Equity** is the share of the pot you would win on average if all remaining
cards were dealt and nobody folded. Ties count as half a win.

| Matchup (preflop) | Equity of first hand |
|---|---|
| `AhAd` vs `KsKc` | ~81% |
| `AsKs` vs a random hand | ~67% |
| `7h2d` vs a random hand | ~35% (the worst starting hand still wins a third of the time!) |

Measure it yourself:

```bash
python -m pokerbot equity AhAd --vs KsKc
python -m pokerbot equity AsKs
python -m pokerbot equity 7h2d
```

### Computing equity: Monte Carlo simulation

Enumerating every possibility preflop is ~1.7 million boards per opponent hand –
too slow to do in pure Python every decision. Instead, **simulate**:

1. Deal the opponent a random hand (from the cards we can't see).
2. Deal the rest of the board at random.
3. See who wins. Repeat N times.
4. Equity ≈ (wins + ties/2) / N.

That is `monte_carlo_equity()` in `pokerbot/equity.py` – about 30 lines. The
error shrinks like **1/√N**: 100 samples give roughly ±5%, 1 000 give ±1.5%,
10 000 give ±0.5%. Bots trade accuracy for speed; `EquityBot` uses 300
samples postflop and **caches** preflop equity per hand class (there are only
169 distinct starting hands: 13 pairs, 78 suited, 78 offsuit).

On the turn and river there are few enough runouts to be exact:
`exact_equity(hole, opp, board)` enumerates them all.

## 2.2 Pot odds – "is the price right?"

When the opponent bets, you are offered a **price**. If calling costs `C` and
the pot (including their bet) is `P`, you are risking `C` to win `P + C`
total. You break even when your equity equals

```
pot odds = C / (P + C)
```

This is `view.pot_odds` in the engine.

**Rule:** call when `equity > pot odds`; fold when it's lower.

**Worked example** (from the hand in chapter 1.7). On a `5c 9h 7d` flop,
holding `Td 8d`, the opponent bets 6 into a pot of 12.

- Pot odds = 6 / (18 + 6) = **25%**.
- Equity vs their actual `Qd Qc` (`python -m pokerbot equity Td8d --board "5c 9h 7d" --vs QdQc`) = **36.4%**.
- 36% > 25% → **calling is profitable**, even though we're behind right now.

## 2.3 Outs and the rule of 2 and 4

An **out** is an unseen card that improves you to a (probably) winning hand.
`Td 8d` on `5c 9h 7d` has an **open-ended straight draw**: any 6 or J makes a
straight → 4 + 4 = **8 outs**.

Quick mental equity:

- Two cards to come (on the flop): **outs × 4%** → 8 × 4 = 32%
- One card to come (on the turn): **outs × 2%** → 8 × 2 = 16%

`count_outs(hole, board)` counts cards that make a straight or better, and the
`equity` command prints the rule-of-4 estimate next to the true number.

**Caveat – tainted outs.** `AhKh` on `Qh Jh 2d` has 12 "outs" (9 hearts + 3
non-heart tens), so the rule says ~48%. Against a set of queens the real
equity is **34%** – some of those cards also give the opponent a full house.
Simulation beats rules of thumb; rules of thumb are for humans.

## 2.4 Expected value (EV)

Every decision has an **expected value**: the average chips it wins or loses.
For a call:

```
EV(call) = equity × (pot + to_call) − to_call
```

From the example: 0.364 × (18 + 6) − 6 = **+2.7 chips**. Folding is always
EV 0 (from this point on), so call.

For a bet it's more complicated because the opponent can fold:

```
EV(bet B) = fold% × pot  +  (1 − fold%) × [equity_when_called × (pot + 2B) − B]
```

Two ways a bet makes money:

- **Value bet:** worse hands call. You win more when ahead.
- **Bluff:** better hands fold. You win the pot when behind.

A bet with neither effect (only better hands call, only worse hands fold) is a
mistake. This is why `RuleBot` loses value: its bets are only called by hands
that beat it.

### Implied odds

Pot odds only count the money in the pot *now*. If you hit your draw you will
often win **more bets later** – the **implied odds**. In the chapter 1.7 hand,
after the straight came, `equity` won another 113 chips from the queens.
`EquityBot` gives drawing hands (8+ outs, not on the river) a small 3% bonus
for this.

## 2.5 Ranges – the single most important idea

Strong players (and strong bots) don't put an opponent on one hand; they put
them on a **range**: the set of all hands they could hold given what they've
done.

- A player who raises preflop 20% of the time is raising roughly the **top 20%**
  of starting hands.
- A player who bets the flop is more likely to have connected with that board.

Equity **against a range** is very different from equity against a random
hand. `Td 8d` on `5c 9h 7d` has **52.6%** vs a random hand but **36.4%** vs
`QQ`. If your bot assumes "random" when the opponent's betting says "strong",
it will call far too much.

### How the bots represent ranges

A range in this project is a **filter function**: `opp_range(cards) -> bool`.
`monte_carlo_equity(..., opp_range=f)` redraws any sampled opponent hand that
fails the filter.

- **Preflop – Chen score.** `chen_score()` implements Bill Chen's quick
  hand-scoring formula (AA = 20, AKs = 12, T9s = 8, 72o = −1).
  `chen_threshold_for_top(0.2)` returns the score marking the top 20% of hands
  (it's 6), and `chen_range(6)` builds the filter.

  | Top % of hands | Minimum Chen score |
  |---|---|
  | 5% | 9 |
  | 10% | 8 |
  | 20% | 6 |
  | 30% | 5 |
  | 50% | 4 |

- **Postflop – strength on this board.** `board_range(board, dead, 0.2)`
  samples random hands, ranks them by their *current* made hand on this board,
  and keeps the top 20%. A bet on `A 8 3` suddenly means "probably an ace",
  not "probably a high Chen score".

### Proof that it matters

`EquityBot(use_model=False)` assumes any two cards; `use_model=True` narrows the
range when the opponent bets. Same cards, same maths:

```python
from pokerbot.engine import run_match
from pokerbot.bots import EquityBot, RuleBot

for use_model in (False, True):
    r = run_match(EquityBot(seed=1, use_model=use_model), RuleBot(), hands=3000, seed=2)
    print(use_model, round(r.bb_per_100(), 1), "+-", round(1.96 * r.std_error_bb100(), 1))
# False -197.1 +- 83.7      (takes a minute or two)
# True    37.6 +- 34.0
```

Assuming "any two cards" turns a winning bot into a heavy loser.

## 2.6 Opponent modelling

To size a range you need to know **how this opponent plays**. Bots keep simple
counting statistics – the same ones online players track with HUDs:

| Stat | Meaning | Typical HU value |
|---|---|---|
| **VPIP** | % of hands they Voluntarily Put chips In preflop | 50–80% |
| **PFR**  | % of hands they raised preflop | 30–60% |
| **Aggression** | share of their decisions that are bets/raises | 20–40% |
| **Fold rate** | share of decisions that are folds | – |

`OpponentModel` in `equity_bot.py` updates these after every hand from
`HandResult.history`. Two details worth copying:

- **Priors / smoothing.** After 2 hands, "VPIP = 100%" is noise. The model
  starts from a sensible prior (`(count + 3) / (hands + 5)`) that real data
  gradually overrides – Bayesian thinking in one line.
- **Use the stats for decisions.** Range width = observed raise rate; bluff
  frequency scales with observed fold rate. A stat you don't act on is
  wasted.

`python -m pokerbot match equity rule` prints EquityBot's final read on its
opponent.

## 2.7 Bet sizing

Bet sizes are usually expressed as a **fraction of the pot**:

| Size | Gives the opponent pot odds of | Typical use |
|---|---|---|
| 1/3 pot | 20% | thin value, cheap bluffs |
| 1/2 pot | 25% | standard |
| pot | 33% | strong hands, draws you want to deny odds to |
| overbet (>pot) | >33% | very polarised: nuts or air |

The helper `raise_to(view, pot_fraction)` in `bots/_sizing.py` converts a
fraction to a legal `RaiseAction`, clamped to `[min_raise, max_raise]`.

`EquityBot` sizes **with equity** – 50% pot at 70% equity up to 125% at 100%.
That's simple and profitable against weak bots, but note the leak: *the size
tells the opponent how strong you are*. Strong human players and equilibrium
bots use the **same sizes for value hands and bluffs** so the size gives
nothing away.

## 2.8 Bluffing and balance

If you only bet strong hands, a thinking opponent folds every time you bet and
you never get paid. Mixing in bluffs makes your bets credible.

How many bluffs? If you bet `B` into pot `P`, the opponent needs equity
`B / (P + 2B)` to call. On the river a **balanced** bettor bluffs just often
enough that the opponent is indifferent between calling and folding:

```
bluff share of your betting range = B / (P + 2B)     # pot-sized bet -> 1/3 bluffs
```

The best bluffs are **semi-bluffs**: bets with a draw, which can win by
the opponent folding *or* by hitting. `EquityBot` doubles its bluff frequency
when it has 8+ outs, and scales it with the opponent's fold rate.

Against a `CallingStation`, the correct number of bluffs is **zero**. Against
the `RandomBot`, which folds a third of the time it faces a bet, bluffs print money.
*Exploitative play* means adapting to the opponent in front of you; *balanced
(GTO) play* means being unexploitable regardless – see chapter 5.

## 2.9 Position

Acting last (in position) means seeing the opponent's action before deciding.
Practical consequences:

- Play more hands on the button, fewer from the big blind.
- In position you can check behind to take a free card with a draw, or bet
  when the opponent shows weakness by checking.

A good exercise is to make your bot read `view.is_button` and play
differently.

## 2.10 Measuring a bot: bb/100 and variance

The standard win-rate unit is **big blinds per 100 hands (bb/100)**.
`MatchResult.bb_per_100()` computes it.

Poker is **high variance**. One all-in is worth 100 bb, so a few hundred hands
prove very little. `MatchResult.summary()` prints a 95% confidence interval
(`± 1.96 × standard error`):

```
equity: +631 chips (+105.2 bb/100 ± 146.8)
```

means "probably somewhere between −42 and +252 bb/100" – not conclusive!
Rules of thumb:

- Use **thousands** of hands to compare bots, and the **same seed** for both
  versions (the same cards are dealt – *common random numbers*, which removes
  much of the luck from a comparison).
- Run with several seeds and average.
- Duplicate poker (play the same cards twice with seats swapped) cuts variance
  further; it's an exercise in chapter 4.

---

## Exercises

1. You hold a flush draw on the turn (9 outs). The opponent bets 50 into 100.
   What are your pot odds? Your rough equity? Call or fold?
   *(Pot odds 50/200 = 25%; equity ≈ 18%; fold – unless the implied odds are
   big.)*
2. Run `python -m pokerbot equity <hand> --board <flop>` for your favourite
   hand on three different flops. Compare to the rule of 4.
3. In a Python shell, compare `monte_carlo_equity(hole, board, 100)` with
   `iterations=10000` five times each. How much does the 100-sample estimate
   jump around?
4. Change `EquityBot(bluff_freq=0.0)` and `0.3` and play each against
   `station` and `random` for 2 000 hands. Explain the results.

Next: [3. Engine and architecture →](03-engine-and-architecture.md)
