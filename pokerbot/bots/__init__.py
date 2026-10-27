"""Built-in bots, from trivial to reasonably strong.

    random   - picks a random legal action (a baseline that any bot should beat)
    station  - "calling station": never folds, never raises
    rule     - hand-strength rules: preflop Chen score + postflop hand tiers
    equity   - Monte Carlo equity, pot odds, bet sizing and opponent modeling
    human    - you, typing into the terminal
"""

from .random_bot import RandomBot
from .calling_station import CallingStation
from .rule_bot import RuleBot
from .equity_bot import EquityBot
from .human import HumanBot

BOTS = {
    "random": RandomBot,
    "station": CallingStation,
    "rule": RuleBot,
    "equity": EquityBot,
    "human": HumanBot,
}


def load_bot_class(spec: str):
    """Resolve a bot spec to a class.

    "equity"                         -> a built-in bot
    "examples/my_first_bot.py:MyBot" -> class MyBot from that file
    "mypackage.mybot:MyBot"          -> class MyBot from an importable module
    """
    if spec in BOTS:
        return BOTS[spec]
    if ":" not in spec:
        raise ValueError(f"Unknown bot {spec!r}; choose from {', '.join(BOTS)} "
                         "or give path/to/file.py:ClassName")
    import importlib
    import importlib.util
    from pathlib import Path

    target, class_name = spec.rsplit(":", 1)
    if target.endswith(".py"):
        path = Path(target)
        if not path.exists():
            raise ValueError(f"Bot file {target!r} not found")
        module_spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
    else:
        module = importlib.import_module(target)
    try:
        return getattr(module, class_name)
    except AttributeError:
        raise ValueError(f"{target!r} has no class {class_name!r}") from None


def make_bot(spec: str, seed=None, **kwargs):
    """Instantiate a bot. `seed` is passed on only if the bot accepts one."""
    import inspect

    cls = load_bot_class(spec)
    if seed is not None and "seed" in inspect.signature(cls).parameters:
        kwargs["seed"] = seed
    return cls(**kwargs)
