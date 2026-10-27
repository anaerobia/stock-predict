import random
from typing import Optional

from ..engine import Bot, GameView, RaiseAction


class RandomBot(Bot):
    """Chooses uniformly among legal action types; random raise sizes."""

    name = "random"

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)

    def get_action(self, view: GameView):
        action_type = self.rng.choice(view.legal_actions)
        if action_type is RaiseAction:
            return RaiseAction(self.rng.randint(view.min_raise, view.max_raise))
        return action_type()
