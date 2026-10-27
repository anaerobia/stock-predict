# 5. Going further: game theory, CFR and competitions

Everything so far has been **exploitative**: estimate what the opponent does,
then play the best response. That wins a lot against weak opponents – and can
be counter-exploited by a strong one. The bots that beat top human
professionals took the opposite approach: approximate a **Nash equilibrium**.

> **Goal of the chapter:** understand what a poker equilibrium is, run a real
> CFR solver on a tiny poker game, and know what it would take to scale it up.

---

## 5.1 Nash equilibrium, in poker terms

A pair of strategies is a **Nash equilibrium** when neither player can gain by
changing their own strategy alone. In two-player zero-sum games like heads-up
poker this has a strong consequence: an equilibrium strategy **cannot lose in
expectation** against *any* opponent (beyond the inherent disadvantage of a
seat, which evens out as the button alternates). Poker players call it
**GTO** ("game-theory optimal").

Equilibrium strategies are **mixed**: they take different actions with
specific probabilities in the same spot. That's where bluffing comes from –
not as a trick, but as the mathematically required frequency that keeps the
opponent indifferent (chapter 2.8).

Trade-off:

| | Exploitative (e.g. `EquityBot`) | Equilibrium (CFR-style) |
|---|---|---|
| Against weak opponents | wins more | wins, but less |
| Against strong opponents | can be exploited | unexploitable |
| Needs | an opponent model | lots of computation up front |

The strongest practical bots combine both: an equilibrium "blueprint" with
adjustments for the specific opponent.

## 5.2 Kuhn poker – a game small enough to solve

- Deck: J, Q, K. Each player antes 1 and gets one card.
- Player 1 may **pass** or **bet** 1.
- After a pass, player 2 may pass (showdown for the antes) or bet.
- After a bet, the other player may **call** (showdown for 2) or **fold**.

Its equilibrium is known analytically: player 1 bluff-bets the J with some
probability α ∈ [0, 1/3], bets the K with probability 3α, always checks the Q
first and calls a bet with it α + 1/3 of the time; player 2 bluffs the J 1/3 of
the time after a check, calls with the Q 1/3 of the time, always bets/calls
with the K. Player 1's expected value is **−1/18** per hand.

## 5.3 Counterfactual Regret Minimization (CFR)

CFR learns an equilibrium by **self-play**:

1. Walk the game tree. At every **information set** (what a player knows: own
   card + betting so far) play the current strategy.
2. For each action, compute how much better it would have been than the
   current mixed strategy – the **regret** – weighted by how likely the
   opponent was to reach this point.
3. **Regret matching:** next iteration, play each action in proportion to its
   accumulated positive regret.
4. The **average** strategy over all iterations converges to a Nash
   equilibrium.

It's about 60 lines: `pokerbot/examples/kuhn_cfr.py`.

```bash
python -m pokerbot.examples.kuhn_cfr
```

```
Average game value for player 1: -0.0516  (theory: -1/18 = -0.0556)

Info set   P(pass)  P(bet)      (history: p = pass/check/fold, b = bet/call)
  J          0.82    0.18       <- P1 bluffs the J 18% (alpha)
  K          0.44    0.56       <- P1 bets the K ~3 x alpha
  Q          1.00    0.00       <- P1 always checks the Q
  Jb         1.00    0.00       <- P2 with J facing a bet: always fold
  Jp         0.66    0.34       <- P2 with J after a check: bluff 1/3
  Kb         0.00    1.00
  Kp         0.00    1.00
  Qb         0.65    0.35       <- P2 calls with the Q 1/3
  Qp         1.00    0.00
  Jpb        1.00    0.00
  Kpb        0.00    1.00
  Qpb        0.47    0.53       <- P1 calls with the Q alpha + 1/3
```

Every line matches the theory from 5.2, learned from nothing but the rules.

### Reading the code

- `Node.strategy()` is regret matching: positive regrets, normalised.
- `cfr()` returns the value for the player to act and is called recursively
  with the probabilities `p0`, `p1` of each player reaching this node.
- `node.regret_sum[a] += reach_opp * (utils[a] - node_util)` is the whole
  algorithm in one line.

## 5.4 Scaling to Texas Hold'em

Heads-up no-limit hold'em has on the order of 10^160 decision points, so
plain CFR is impossible. Research bots combine:

- **Card abstraction:** group strategically similar hands into buckets (e.g.
  by equity distribution) and solve the bucketed game.
- **Action abstraction:** only allow a few bet sizes (e.g. ½ pot, pot, all-in)
  and map real bets to the nearest one.
- **Monte Carlo CFR (MCCFR):** sample parts of the tree each iteration
  instead of walking all of it.
- **CFR+ / Linear CFR / Discounted CFR:** variants that converge much faster.
- **Real-time subgame solving:** re-solve the current part of the game more
  precisely during play (Libratus, Pluribus), or use a neural network to
  estimate values at a depth limit (DeepStack).

Milestones worth reading about: **Cepheus** (2015, essentially solved heads-up
*limit* hold'em), **DeepStack** and **Libratus** (2017, beat professionals at
heads-up no-limit), **Pluribus** (2019, six-player no-limit).

A good project path from here:

1. Extend `kuhn_cfr.py` to **Leduc hold'em** (6-card deck, two rounds, one
   community card) – the standard next step in research papers.
2. Write a **best-response** calculator to measure how exploitable a strategy
   is ("exploitability" is how equilibrium bots are scored).
3. Build a tiny abstraction for this engine: 5 equity buckets × 3 bet sizes
   per street, solve it with MCCFR, and play the result as a `Bot`.

## 5.5 Competing

- **[MIT Pokerbots](https://pokerbots.org/)** – a long-running annual
  competition where teams write bots for a hold'em variant (the rules change
  each year) and play them against each other on a shared engine. The
  structure of this project – an engine that calls `get_action` with a view
  of legal actions, chip-count scoring over many hands – follows the same
  model, so the skills transfer directly.
- **University clubs** such as [FIU PokerBots](https://github.com/FIU-PokerBots/)
  publish their bots and engines on GitHub – reading other people's bots is
  one of the fastest ways to learn.
- **Tutorials and project write-ups:**
  [OpenPoker – Build a poker bot in Python](https://openpoker.ai/blog/build-poker-bot-python),
  [HMC student poker bot project](https://www.cs.hmc.edu/~ktantia/poker.html).

Before porting a bot from here to a competition, check:

- The competition's **action API** and whether raises are "to" or "by".
- **Time limits** – they are usually per match; budget your Monte Carlo
  iterations accordingly.
- **The variant's rules** – equity code and the evaluator may need changes.

---

## Exercises

1. Change `train(iterations=...)` in `kuhn_cfr.py` to 1 000, 10 000 and
   100 000. How fast does the game value approach −1/18?
2. Replace regret matching with **CFR+** (clip `regret_sum` at zero after
   every update). Does it converge faster?
3. Turn the Kuhn equilibrium into a `play_kuhn(strategy_a, strategy_b)`
   simulator and verify that no fixed pure strategy beats it.
4. Implement Leduc hold'em CFR.

[← Back to the overview](../../pokerbot/README.md)
