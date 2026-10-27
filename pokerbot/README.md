# Pokerbot

A heads-up (two-player) **No-Limit Texas Hold'em** engine, a ladder of bots
from trivial to reasonably strong, and a step-by-step guide to building your
own. Pure Python 3.9+, **no dependencies**.

It is modelled on the way bot competitions such as
[MIT Pokerbots](https://pokerbots.org/) run: an engine owns the cards and
chips, calls your bot's `get_action(view)` whenever it is your turn, checks the
answer is legal and moves the game on. Write one class, and you can play it
against the built-in bots, against yourself, or in a round-robin tournament.

```
$ python -m pokerbot tournament --hands 1000 --seed 7
Round robin, 1000 hands per pairing (seed 7)

    random vs station    -145.8 bb/100
    random vs rule       -139.2 bb/100
    random vs equity     -264.8 bb/100
   station vs rule       -272.3 bb/100
   station vs equity     -561.2 bb/100
      rule vs equity      -41.5 bb/100

Total bb/100 across pairings:
    equity   +867.5
      rule   +370.0
    random   -549.7
   station   -687.8
```

## Quick start

Run everything from the **repository root** (the folder that contains
`pokerbot/`).

```bash
# 1. Play against the strongest built-in bot (type c / k / f / r 10 / a / q)
python -m pokerbot play --bot equity

# 2. Watch two bots play one hand, action by action
python -m pokerbot match equity rule --hands 1 --verbose

# 3. Bot vs bot over many hands (same seed = same cards = fair comparison)
python -m pokerbot match equity rule --hands 2000 --seed 1

# 4. Round robin of all bots
python -m pokerbot tournament --hands 500

# 5. Learning tools: equity calculator and hand evaluator
python -m pokerbot equity AhKh --board "Qh Jh 2d"
python -m pokerbot equity AhAd --vs KsKc
python -m pokerbot eval "Kh Kd Kc 2s 2d 2h 9c"

# 6. Your own bot (copy the template first)
python -m pokerbot match pokerbot/examples/my_first_bot.py:MyFirstBot station

# 7. Game theory: solve Kuhn poker with CFR
python -m pokerbot.examples.kuhn_cfr

# Tests
python -m unittest discover -s pokerbot/tests -t .
```

## The bots

| Name      | Idea | Teaches |
|-----------|------|---------|
| `random`  | Random legal action, random raise size | The baseline every bot must beat |
| `station` | "Calling station": always check/call | Value betting beats players who never fold; bluffing doesn't |
| `rule`    | Chen score preflop, hand *tiers* postflop, fixed bet sizes | Hand strength, hand reading, why predictable bots get exploited |
| `equity`  | Monte Carlo equity vs an estimated *range*, pot odds, bet sizing, controlled bluffing, opponent model (VPIP/PFR/aggression) | The core loop of a real pokerbot |
| `human`   | You, at the terminal | – |

`EquityBot` has a switch that shows why opponent modelling matters. Against
RuleBot over 3 000 hands (match seed 2, bot seed 1; ± is a 95% confidence interval):

| EquityBot setting | Result |
|---|---|
| `use_model=False` – assumes the opponent could hold any two cards | **−197 ± 84 bb/100** |
| `use_model=True` – narrows the opponent's range when they bet | **+38 ± 34 bb/100** |

Same cards, same maths, one difference: *who it thinks it is up against*.

## Project layout

```
pokerbot/
├── __main__.py          CLI: play / match / tournament / equity / eval
├── cards.py             Card, Deck, parse_cards ("As Kd" notation)
├── evaluator.py         evaluate(5-7 cards) -> comparable tuple; hand_name()
├── equity.py            Monte Carlo + exact equity, Chen score, ranges, outs
├── engine.py            Rules, betting, showdown, GameView, Bot base, run_match
├── bots/
│   ├── random_bot.py    RandomBot
│   ├── calling_station.py
│   ├── rule_bot.py      RuleBot + hand_tier()
│   ├── equity_bot.py    EquityBot + OpponentModel
│   ├── human.py         HumanBot (terminal)
│   └── _sizing.py       raise_to(view, pot_fraction) helper
├── examples/
│   ├── my_first_bot.py  Template for your own bot
│   ├── tutorial_bot.py  The finished bot from the chapter 4 tutorial
│   └── kuhn_cfr.py      CFR solver for Kuhn poker
└── tests/test_pokerbot.py
```

## Documentation

Read in order if you are new to poker bots; each chapter ends with exercises.

1. [Poker rules for bot builders](../docs/pokerbot/01-poker-rules.md) – heads-up NLHE, positions, blinds, legal actions, min-raise, hand rankings.
2. [Strategy and the maths behind it](../docs/pokerbot/02-strategy-and-math.md) – equity, pot odds, EV, Monte Carlo, outs, ranges, bet sizing, bluffing, opponent statistics, bb/100 and variance.
3. [Engine and architecture](../docs/pokerbot/03-engine-and-architecture.md) – how a hand is played, the `GameView` API, illegal-action handling, the evaluator.
4. [Build your own bot](../docs/pokerbot/04-build-your-own-bot.md) – hands-on tutorial from a 5-line bot to an opponent-modelling one.
5. [Going further: game theory, CFR and competitions](../docs/pokerbot/05-going-further.md) – Nash equilibrium, CFR on Kuhn poker, abstraction, where to compete.

## References and inspiration

- [MIT Pokerbots](https://pokerbots.org/) – annual competition where student-written bots play a Hold'em variant through an engine; the inspiration for the engine/bot split here.
- [FIU PokerBots](https://github.com/FIU-PokerBots/) – a university pokerbot club's public repositories.
- [OpenPoker – Build a poker bot in Python](https://openpoker.ai/blog/build-poker-bot-python) – tutorial-style introduction to writing a bot.
- [HMC – Poker bot project](https://www.cs.hmc.edu/~ktantia/poker.html) – a student poker AI project write-up.
