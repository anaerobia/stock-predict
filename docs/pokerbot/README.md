# Pokerbot documentation

A five-chapter course that goes from the rules of heads-up No-Limit Hold'em to
writing, measuring and improving your own bot. Each chapter ends with
exercises. The code lives in [`pokerbot/`](../../pokerbot/README.md).

| # | Chapter | You will learn |
|---|---------|----------------|
| 1 | [Poker rules for bot builders](01-poker-rules.md) | Streets, positions, blinds, legal actions, min-raise, hand rankings, reading a hand log |
| 2 | [Strategy and the maths behind it](02-strategy-and-math.md) | Equity, Monte Carlo, pot odds, outs, EV, implied odds, ranges, opponent stats, bet sizing, bluffing, bb/100 and variance |
| 3 | [Engine and architecture](03-engine-and-architecture.md) | The bot contract, `GameView`/`HandResult` fields, how a hand is played, illegal-action handling, the evaluator, reproducibility, tests |
| 4 | [Build your own bot](04-build-your-own-bot.md) | A 7-step tutorial, benchmarking, reading hand histories, common bugs |
| 5 | [Going further](05-going-further.md) | Nash equilibrium, CFR on Kuhn poker, abstraction, Libratus/Pluribus, competitions |

## Glossary

| Term | Meaning |
|---|---|
| **Button / BTN** | Dealer seat; posts the small blind heads-up, acts first preflop, last postflop |
| **Big blind (BB)** | The larger forced bet; also the unit win rates are measured in |
| **Street** | A betting round: preflop, flop, turn, river |
| **Hole cards** | Your two private cards |
| **Board** | The shared community cards |
| **Limp** | Calling the big blind preflop instead of raising |
| **Open** | The first raise of a hand |
| **3-bet** | A re-raise preflop (the blind was the 1st bet, the open the 2nd) |
| **Equity** | Share of the pot you win on average at showdown |
| **Pot odds** | `to_call / (pot + to_call)` – the equity needed to call |
| **EV** | Expected value: average chips won by a decision |
| **Outs** | Unseen cards that improve you to a likely winner |
| **Range** | The set of hands a player could hold given their actions |
| **Value bet** | A bet that wants worse hands to call |
| **Bluff / semi-bluff** | A bet that wants better hands to fold (semi: with a draw as backup) |
| **In position (IP)** | Acting last on a street |
| **VPIP / PFR** | % of hands voluntarily played / raised preflop |
| **bb/100** | Big blinds won per 100 hands |
| **GTO** | Game-theory optimal: a Nash equilibrium strategy |
| **CFR** | Counterfactual Regret Minimization, the algorithm that finds one |
| **Hero / Villain** | The player whose view we take / their opponent |
