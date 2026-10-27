"""
Counterfactual Regret Minimization (CFR) on Kuhn poker.

Kuhn poker is the "hello world" of game-theoretic poker AI: a 3-card deck
(J, Q, K), one card each, one ante each, one betting round where a player may
pass (check/fold) or bet 1. It is small enough to solve in a second, yet it
already needs bluffing and slow-playing to be played optimally.

CFR - the algorithm family behind Libratus and Pluribus - plays the game
against itself many times. At every decision point ("information set") it
tracks *regret*: how much better each action would have done than what was
actually played. Next time it plays actions in proportion to their positive
regret ("regret matching"). The AVERAGE strategy over all iterations converges
to a Nash equilibrium - a strategy that cannot be exploited.

Run:
    python -m pokerbot.examples.kuhn_cfr
Expected: player 1's game value approaches -1/18 = -0.0556, and the strategy
shows the known equilibrium features (e.g. bluff-betting the J sometimes,
always calling a bet with the K).
"""

import random
from typing import Dict, List

PASS, BET = 0, 1
CARDS = ["J", "Q", "K"]


class Node:
    """One information set: what a player knows (own card + betting so far)."""

    def __init__(self):
        self.regret_sum = [0.0, 0.0]
        self.strategy_sum = [0.0, 0.0]

    def strategy(self, weight: float) -> List[float]:
        positive = [max(r, 0.0) for r in self.regret_sum]
        total = sum(positive)
        strat = [p / total for p in positive] if total > 0 else [0.5, 0.5]
        for a in (PASS, BET):
            self.strategy_sum[a] += weight * strat[a]
        return strat

    def average_strategy(self) -> List[float]:
        total = sum(self.strategy_sum)
        return [s / total for s in self.strategy_sum] if total > 0 else [0.5, 0.5]


def terminal_payoff(history: str, cards: List[int]) -> "float | None":
    """Payoff for the player to move at `history`, or None if not terminal."""
    player = len(history) % 2
    opponent = 1 - player
    if len(history) > 1:
        player_wins = cards[player] > cards[opponent]
        if history[-1] == "p":
            if history == "pp":            # check, check: showdown for the antes
                return 1.0 if player_wins else -1.0
            return 1.0                     # opponent folded to our bet
        if history[-2:] == "bb":          # bet, call: showdown for 2
            return 2.0 if player_wins else -2.0
    return None


def cfr(nodes: Dict[str, Node], cards: List[int], history: str, p0: float, p1: float) -> float:
    """Returns the expected value for the player to act at `history`."""
    payoff = terminal_payoff(history, cards)
    if payoff is not None:
        return payoff
    player = len(history) % 2
    key = CARDS[cards[player]] + history
    node = nodes.setdefault(key, Node())
    strat = node.strategy(p0 if player == 0 else p1)

    utils = [0.0, 0.0]
    node_util = 0.0
    for a, ch in ((PASS, "p"), (BET, "b")):
        if player == 0:
            utils[a] = -cfr(nodes, cards, history + ch, p0 * strat[a], p1)
        else:
            utils[a] = -cfr(nodes, cards, history + ch, p0, p1 * strat[a])
        node_util += strat[a] * utils[a]

    # Regret is weighted by the probability that the OPPONENT reached here.
    reach_opp = p1 if player == 0 else p0
    for a in (PASS, BET):
        node.regret_sum[a] += reach_opp * (utils[a] - node_util)
    return node_util


def train(iterations: int = 50_000, seed: int = 0):
    rng = random.Random(seed)
    nodes: Dict[str, Node] = {}
    cards = [0, 1, 2]
    total = 0.0
    for _ in range(iterations):
        rng.shuffle(cards)
        total += cfr(nodes, cards, "", 1.0, 1.0)
    return nodes, total / iterations


def main() -> None:
    nodes, value = train()
    print(f"Average game value for player 1: {value:+.4f}  (theory: -1/18 = {-1/18:+.4f})\n")
    print("Info set   P(pass)  P(bet)      (history: p = pass/check/fold, b = bet/call)")
    for key in sorted(nodes, key=lambda k: (len(k), k)):
        pas, bet = nodes[key].average_strategy()
        print(f"  {key:<6}   {pas:6.2f}  {bet:6.2f}")


if __name__ == "__main__":
    main()
