from ..engine import Bot, CallAction, CheckAction, GameView


class CallingStation(Bot):
    """Never folds, never raises. Beat it by betting your good hands for value
    and never bluffing - it will not fold."""

    name = "station"

    def get_action(self, view: GameView):
        return CheckAction() if view.can(CheckAction) else CallAction()
