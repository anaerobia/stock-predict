# 1. Poker rules for bot builders

This chapter covers exactly the rules the engine in `pokerbot/engine.py`
implements: **heads-up No-Limit Texas Hold'em** (HUNL), the format used by most
bot competitions and research (Libratus, DeepStack, MIT Pokerbots variants).

> **Goal of the chapter:** by the end you can read a hand log, say who acts
> next, and work out what a legal raise is. Those are the facts your bot
> receives in every `GameView`.

---

## 1.1 The deal

- A standard 52-card deck. A card is written **rank + suit**: `As` = ace of
  spades, `Td` = ten of diamonds. Ranks `2 3 4 5 6 7 8 9 T J Q K A`, suits
  `c d h s`.
- Each player gets **two private hole cards**.
- Up to **five community cards** (the *board*) are dealt face up in stages,
  shared by both players.

| Street   | Board cards | Total visible to you |
|----------|-------------|----------------------|
| Preflop  | 0           | 2 (your hole cards)  |
| Flop     | 3           | 5                    |
| Turn     | 4 (+1)      | 6                    |
| River    | 5 (+1)      | 7                    |

There is a betting round on every street. If nobody folds, the hand goes to
**showdown**: each player makes the **best 5-card hand** from their 7 cards
(any combination of hole + board, including the board alone, called "playing
the board").

## 1.2 Hand rankings

From best to worst. The number is the category the evaluator returns as the
first element of its tuple.

| # | Hand            | Example            | Ties broken by |
|---|-----------------|--------------------|----------------|
| 8 | Straight flush  | `9h 8h 7h 6h 5h`   | High card (A-high = royal flush) |
| 7 | Four of a kind  | `Qc Qd Qh Qs 4d`   | Quad rank, then kicker |
| 6 | Full house      | `Kh Kd Kc 2s 2d`   | Trips rank, then pair rank |
| 5 | Flush           | `Ah Jh 8h 4h 2h`   | All five cards, high to low |
| 4 | Straight        | `9c 8d 7h 6s 5c`   | High card; `A 2 3 4 5` (the *wheel*) is the lowest |
| 3 | Three of a kind | `7c 7d 7h Ks 2c`   | Trips rank, then 2 kickers |
| 2 | Two pair        | `Jc Jd 4h 4s Ac`   | High pair, low pair, kicker |
| 1 | One pair        | `Qc Qd 9h 5s 2c`   | Pair, then 3 kickers |
| 0 | High card       | `Ac Jd 9h 5s 2c`   | All five cards |

Suits never break ties. Equal hands **split the pot**.

**Try it:**

```bash
python -m pokerbot eval "Ah 2d 3c 4s 5h"        # Straight, Five high
python -m pokerbot eval "Kh Kd Kc 2s 2d 2h 9c"  # Full House, Kings full of Twos
python -m pokerbot eval "Ah Ad Kc Kd Qh Qs 2c"  # Two Pair, Aces and Kings (Q kicker)
```

## 1.3 Positions and blinds (heads-up specific)

Two seats. The **button** (also called the dealer) moves every hand.

- The **button posts the small blind** (1 chip) and the other player posts the
  **big blind** (2 chips). Blinds are forced bets that create a pot to fight
  over.
- **Preflop the button acts first.** It faces 1 more chip to call.
- **On the flop, turn and river the big blind acts first**, so the button acts
  *last*. Acting last is called being **in position (IP)**; it is a real
  advantage because you see what the opponent did before you decide.

> Heads-up is the one format where the button is also the small blind. In
> full-ring games the small blind sits to the left of the button.

In this engine, each hand both players start with **200 chips (100 big
blinds)**. Stacks reset every hand and the running profit is tracked as each
bot's **bankroll** - the same convention MIT Pokerbots uses, so one huge pot
can't eliminate a bot.

## 1.4 The four actions

| Action | When legal | Engine class |
|--------|-----------|--------------|
| **Check** – pass without betting | Nothing to call (`to_call == 0`) | `CheckAction()` |
| **Fold** – give up the hand | Facing a bet | `FoldAction()` |
| **Call** – match the current bet | Facing a bet | `CallAction()` |
| **Bet / Raise** – put in more | You and the opponent both have chips behind | `RaiseAction(amount)` |

A "bet" is just the first raise on a street; the engine uses `RaiseAction` for
both.

**Important:** `RaiseAction(amount)` means **raise *to* `amount`** – your total
chips on *this street* after the action – not "raise *by*". If the opponent bet
10 and you want to make it 30, you send `RaiseAction(30)`.

Your bot never has to guess what is legal: `view.legal_actions` lists the
allowed action classes, and `view.can(RaiseAction)` checks one.

## 1.5 How much can you raise? (no-limit rules)

- **Minimum raise:** the new total must exceed the current bet by at least the
  size of the *previous* raise on this street, and by at least one big blind.
  - Preflop the BB is 2, so the button's minimum raise is **to 4**.
  - If the button raises to 6 (a raise of 4), the minimum re-raise is **to 10**.
- **Maximum raise:** all your chips (all-in). The engine caps this at the
  *effective stack* – the smaller of the two stacks – because chips the
  opponent can never call are pointless.
- **All-in for less:** if you can't afford a full minimum raise you can still
  shove everything.

The engine gives you both numbers: `view.min_raise` and `view.max_raise`. If
you send an amount outside the range it is **clamped** into it.

## 1.6 When does a betting round end?

When both players have acted and have put in the same amount on this street, or
somebody is all-in. Examples:

- Preflop: button **calls** (limps) → the big blind still gets its **option**
  to check or raise.
- Flop: BB checks, button checks → next street.
- Flop: BB bets 4, button raises to 12, BB calls → next street.
- Anybody folds → the other wins the pot immediately; cards are not shown.
- If a player is all-in, the remaining board is dealt with no more betting.
- If one player bet more than the other could call, the **uncalled** part is
  returned.

## 1.7 Reading a hand log

```bash
python -m pokerbot match equity rule --hands 2 --seed 7 --verbose --show-cards
```

prints (comments added). `--show-cards` is *spectator mode*: the log shows both
hands, but the bots themselves only ever see their own cards.

```
Hand #1: equity has the button          # equity = small blind, acts first preflop
  equity is dealt 6d Js
  rule is dealt 9s 4h
  equity calls 1                        # "limps": completes the small blind to 2
  rule checks                           # big blind's option: no raise
 FLOP: Qc 4s 2c  (pot 4)
  rule checks                           # BB acts first after the flop
  equity checks
 TURN: Qc 4s 2c 6s  (pot 4)
  rule checks
  equity bets 2                         # equity paired its 6
  rule calls 2
 RIVER: Qc 4s 2c 6s 5h  (pot 8)
  rule checks
  equity bets 4
  rule calls 4
  equity shows 6d Js: Pair of Sixes     # showdown: best 5 of 7 cards
  rule shows 9s 4h: Pair of Fours
  => equity wins 16 with Pair of Sixes  # pot of 16; equity's profit is +8
Hand #2: rule has the button            # the button alternates every hand
  equity is dealt Td 8d
  rule is dealt Qd Qc
  rule raises to 6                      # a 3-big-blind "open"
  equity calls 4                        # 4 more chips to match 6
 FLOP: 5c 9h 7d  (pot 12)
  equity checks
  rule bets 6                           # half the pot
  equity calls 6                        # a straight draw: any 6 or J completes it
 TURN: 5c 9h 7d 6d  (pot 24)            # ...and the 6 arrives
  equity bets 25
  rule calls 25
 RIVER: 5c 9h 7d 6d 4c  (pot 74)
  equity bets 88                        # an "overbet" (~1.2x the pot): huge equity -> big bet
  rule calls 88                         # (EquityBot's sizing formula, chapter 2)
  equity shows Td 8d: Straight, Ten high
  rule shows Qd Qc: Pair of Queens
  => equity wins 250 with Straight, Ten high
```

Chapter 2 explains *why* calling the flop with a draw was correct there.

---

## Exercises

1. Run `python -m pokerbot play --bot station --hands 10`. Before every
   decision, predict which options will be offered and the min/max raise.
2. Preflop, the button raises to 8. What is the big blind's minimum re-raise?
   *(Answer: the raise was 8 − 2 = 6, so 8 + 6 = 14.)*
3. Which wins: `Ah Kh` or `Qs Qd` on a board of `Jh Th 9h 2c 3d`? Check with
   `python -m pokerbot eval`.
4. Find the test in `pokerbot/tests/test_pokerbot.py` that checks the
   big-blind option, and read it.

Next: [2. Strategy and the maths behind it →](02-strategy-and-math.md)
