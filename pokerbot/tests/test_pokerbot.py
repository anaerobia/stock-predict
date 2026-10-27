"""Run with:  python -m unittest discover -s pokerbot/tests -t ."""

import random
import unittest

from pokerbot.bots import BOTS, CallingStation, EquityBot, HumanBot, RandomBot, RuleBot
from pokerbot.bots.rule_bot import hand_tier
from pokerbot.cards import Card, Deck, parse_cards
from pokerbot.engine import (Bot, CallAction, CheckAction, FoldAction, RaiseAction,
                             play_hand, run_match)
from pokerbot.equity import (board_range, chen_score, chen_threshold_for_top, count_outs,
                             exact_equity, hand_class, monte_carlo_equity)
from pokerbot.evaluator import (FLUSH, FULL_HOUSE, HIGH_CARD, PAIR, QUADS, STRAIGHT,
                                STRAIGHT_FLUSH, TRIPS, TWO_PAIR, evaluate, hand_name)


def ev(text):
    return evaluate(parse_cards(text))


class CardTests(unittest.TestCase):
    def test_parse_and_print(self):
        self.assertEqual(str(Card.from_str("as")), "As")
        self.assertEqual(str(Card.from_str("10h")), "Th")
        self.assertEqual([str(c) for c in parse_cards("AsKd")], ["As", "Kd"])
        self.assertEqual(len(parse_cards("As, Kd, 2c")), 3)

    def test_bad_cards(self):
        for bad in ("1s", "Ax", "A", "As As"):
            with self.assertRaises(ValueError):
                parse_cards(bad)

    def test_deck(self):
        deck = Deck(random.Random(0))
        self.assertEqual(len(deck), 52)
        dealt = deck.deal(5)
        self.assertEqual(len(set(dealt)), 5)
        self.assertEqual(len(deck), 47)
        self.assertEqual(len(Deck(exclude=dealt)), 47)


class EvaluatorTests(unittest.TestCase):
    def test_categories(self):
        cases = {
            "As Ks Qs Js Ts": STRAIGHT_FLUSH, "9h 9d 9c 9s 2d": QUADS,
            "Kh Kd Kc 2s 2d": FULL_HOUSE, "Ah 9h 7h 4h 2h": FLUSH,
            "9c 8d 7h 6s 5c": STRAIGHT, "Ah 2d 3c 4s 5h": STRAIGHT,
            "7c 7d 7h Ks 2c": TRIPS, "Jc Jd 4h 4s Ac": TWO_PAIR,
            "Qc Qd 9h 5s 2c": PAIR, "Ac Jd 9h 5s 2c": HIGH_CARD,
        }
        for cards, category in cases.items():
            self.assertEqual(ev(cards)[0], category, cards)

    def test_ordering(self):
        ranked = ["As Ks Qs Js Ts", "9h 9d 9c 9s 2d", "Kh Kd Kc 2s 2d", "Ah 9h 7h 4h 2h",
                  "9c 8d 7h 6s 5c", "7c 7d 7h Ks 2c", "Jc Jd 4h 4s Ac", "Qc Qd 9h 5s 2c",
                  "Ac Jd 9h 5s 2c"]
        values = [ev(h) for h in ranked]
        self.assertEqual(values, sorted(values, reverse=True))

    def test_wheel_is_lowest_straight(self):
        self.assertLess(ev("Ah 2d 3c 4s 5h"), ev("2h 3d 4c 5s 6h"))
        self.assertEqual(ev("Ah 2d 3c 4s 5h"), (STRAIGHT, 5))

    def test_kickers(self):
        self.assertGreater(ev("Ac Ad Kh 5s 2c"), ev("Ac Ad Qh 5s 2c"))
        self.assertEqual(ev("Ac Ad Kh 5s 2c"), ev("Ah As Kd 5c 2d"))  # suits don't matter

    def test_seven_cards(self):
        self.assertEqual(ev("Kh Kd Kc 2s 2d 2h 9c"), (FULL_HOUSE, 13, 2))
        self.assertEqual(ev("2h 3h 4h 5h 6h 7h 8d"), (STRAIGHT_FLUSH, 7))
        self.assertEqual(ev("Ah Ad Kc Kd Qh Qs 2c"), (TWO_PAIR, 14, 13, 12))
        self.assertEqual(ev("9h 9d 9c 9s Ah Ad 2c"), (QUADS, 9, 14))
        # The board plays: both players have the same straight.
        board = "9c 8d 7h 6s 5c"
        self.assertEqual(ev("Ah Ad " + board), ev("Kh Kd " + board))

    def test_hand_names(self):
        self.assertEqual(hand_name(ev("As Ks Qs Js Ts")), "Royal Flush")
        self.assertEqual(hand_name(ev("Kh Kd Kc 2s 2d")), "Full House, Kings full of Twos")
        self.assertEqual(hand_name(ev("6c 6d 9h 5s 2c")), "Pair of Sixes")


class EquityTests(unittest.TestCase):
    def test_exact_equity(self):
        # A set vs an overpair on the flop is a huge favourite.
        eq = exact_equity(parse_cards("7c 7d"), parse_cards("Ah As"), parse_cards("7h Kd 2s"))
        self.assertGreater(eq, 0.85)
        # Identical hands split every runout.
        eq = exact_equity(parse_cards("Ac Kc"), parse_cards("Ad Kd"), parse_cards("2h 7s 9h Js"))
        self.assertAlmostEqual(eq, 0.5)

    def test_monte_carlo_close_to_known_values(self):
        rng = random.Random(42)
        aa_kk = monte_carlo_equity(parse_cards("Ah Ad"), (), 4000, rng, known_opp=parse_cards("Ks Kc"))
        self.assertAlmostEqual(aa_kk, 0.82, delta=0.03)
        aa_rand = monte_carlo_equity(parse_cards("Ah Ad"), (), 4000, rng)
        self.assertAlmostEqual(aa_rand, 0.85, delta=0.03)
        trash = monte_carlo_equity(parse_cards("7h 2d"), (), 4000, rng)
        self.assertAlmostEqual(trash, 0.35, delta=0.03)

    def test_range_lowers_equity(self):
        rng = random.Random(1)
        hole = parse_cards("Kh Td")
        vs_any = monte_carlo_equity(hole, (), 3000, rng)
        vs_tight = monte_carlo_equity(hole, (), 3000, rng,
                                      opp_range=lambda c: chen_score(c) >= 10)
        self.assertLess(vs_tight, vs_any - 0.05)

    def test_board_range(self):
        board = parse_cards("Ah 8d 3c")
        strong = board_range(board, parse_cards("2s 2d"), 0.1, random.Random(0))
        self.assertTrue(strong(parse_cards("Ac Kd")))   # top pair, top kicker
        self.assertFalse(strong(parse_cards("7c 6d")))  # nothing

    def test_chen(self):
        self.assertEqual(chen_score(parse_cards("Ah Ad")), 20)
        self.assertEqual(chen_score(parse_cards("Ah Kh")), 12)
        self.assertEqual(chen_score(parse_cards("7h 2d")), -1)
        self.assertEqual(chen_score(parse_cards("2h 2d")), 5)
        self.assertEqual(chen_score(parse_cards("Th 9h")), 8)  # 5 + 2 suited + 1 connector
        self.assertGreater(chen_threshold_for_top(0.05), chen_threshold_for_top(0.5))

    def test_hand_class(self):
        self.assertEqual(hand_class(parse_cards("Kd As")), "AKo")
        self.assertEqual(hand_class(parse_cards("9s Ts")), "T9s")
        self.assertEqual(hand_class(parse_cards("5c 5d")), "55")

    def test_outs(self):
        # Nut flush draw + gutshot: 9 hearts + 3 non-heart tens.
        self.assertEqual(count_outs(parse_cards("Ah Kh"), parse_cards("Qh Jh 2d")), 12)
        # Open-ended straight draw: 8 outs.
        self.assertEqual(count_outs(parse_cards("9c 8d"), parse_cards("7h 6s Kc")), 8)


class Scripted(Bot):
    """Plays a fixed list of actions, then checks/calls."""

    def __init__(self, name, actions):
        self.name = name
        self.actions = list(actions)
        self.views = []

    def get_action(self, view):
        self.views.append(view)
        if self.actions:
            return self.actions.pop(0)
        return CheckAction() if view.can(CheckAction) else CallAction()


class EngineTests(unittest.TestCase):
    def test_fold_preflop(self):
        sb = Scripted("sb", [FoldAction()])
        bb = Scripted("bb", [])
        result = play_hand([sb, bb], button=0, rng=random.Random(0))
        self.assertEqual(result.deltas, (-1, 1))
        self.assertFalse(result.showdown)
        self.assertEqual(bb.views, [])  # big blind never had to act

    def test_blinds_and_first_view(self):
        sb = Scripted("sb", [FoldAction()])
        play_hand([sb, Scripted("bb", [])], button=0, rng=random.Random(0))
        v = sb.views[0]
        self.assertEqual((v.pot, v.to_call, v.my_stack, v.min_raise, v.max_raise), (3, 1, 199, 4, 200))
        self.assertEqual(set(v.legal_actions), {FoldAction, CallAction, RaiseAction})
        self.assertAlmostEqual(v.pot_odds, 0.25)

    def test_min_reraise(self):
        sb = Scripted("sb", [RaiseAction(6), FoldAction()])
        bb = Scripted("bb", [RaiseAction(1)])  # too small: clamped to the minimum
        result = play_hand([sb, bb], button=0, rng=random.Random(0))
        # SB raised to 6 (a raise of 4), so BB's minimum re-raise is to 10.
        self.assertEqual(bb.views[0].min_raise, 10)
        self.assertEqual(result.deltas, (-6, 6))

    def test_big_blind_option(self):
        sb = Scripted("sb", [CallAction()])
        bb = Scripted("bb", [])
        play_hand([sb, bb], button=0, rng=random.Random(0))
        first = bb.views[0]
        self.assertEqual(first.street, "preflop")
        self.assertIn(CheckAction, first.legal_actions)
        self.assertIn(RaiseAction, first.legal_actions)

    def test_postflop_order(self):
        sb = Scripted("sb", [CallAction()])
        bb = Scripted("bb", [])
        play_hand([sb, bb], button=0, rng=random.Random(0))
        flop_actors = [v.seat for v in sb.views + bb.views if v.street == "flop"]
        self.assertEqual(len(flop_actors), 2)
        self.assertEqual(bb.views[1].street, "flop")  # BB acts first after the flop
        self.assertEqual(len(bb.views[1].board), 3)

    def test_all_in_showdown(self):
        sb = Scripted("sb", [RaiseAction(10_000)])  # clamped to all-in
        bb = Scripted("bb", [CallAction()])
        result = play_hand([sb, bb], button=0, rng=random.Random(3))
        self.assertTrue(result.showdown)
        self.assertEqual(result.pot, 400)
        self.assertEqual(len(result.board), 5)
        self.assertEqual(sum(result.deltas), 0)
        self.assertIn(abs(result.deltas[0]), (0, 200))

    def test_bad_bots_dont_crash(self):
        class Crasher(Bot):
            name = "crasher"
            def get_action(self, view):
                raise RuntimeError("boom")

        class Garbage(Bot):
            name = "garbage"
            def get_action(self, view):
                return "all the chips"

        result = run_match(Crasher(), Garbage(), hands=20, seed=0)
        self.assertEqual(sum(result.bankrolls), 0)

    def test_chip_conservation_random_play(self):
        result = run_match(RandomBot(seed=1), RandomBot(seed=2), hands=2000, seed=5)
        self.assertEqual(sum(result.bankrolls), 0)
        self.assertEqual(sum(result.per_hand), result.bankrolls[0])
        self.assertTrue(all(abs(d) <= 200 for d in result.per_hand))

    def test_views_are_consistent(self):
        class Checker(RandomBot):
            def get_action(inner, view):
                self.assertEqual(len(view.hole_cards), 2)
                self.assertIn(len(view.board), (0, 3, 4, 5))
                self.assertGreaterEqual(view.my_stack, 0)
                self.assertEqual(view.my_stack + view.opp_stack + view.pot, 400)
                if view.can(RaiseAction):
                    self.assertLessEqual(view.min_raise, view.max_raise)
                return super().get_action(view)

        run_match(Checker(seed=3), Checker(seed=4), hands=500, seed=9)

    def test_seed_reproducible(self):
        a = run_match(RuleBot(), CallingStation(), hands=200, seed=11)
        b = run_match(RuleBot(), CallingStation(), hands=200, seed=11)
        self.assertEqual(a.per_hand, b.per_hand)


class BotTests(unittest.TestCase):
    def test_every_bot_plays_legally(self):
        for name, cls in BOTS.items():
            if name == "human":
                continue
            result = run_match(cls(), RandomBot(seed=0), hands=60, seed=2)
            self.assertEqual(sum(result.bankrolls), 0, name)

    def test_rule_bot_tiers(self):
        self.assertEqual(hand_tier(parse_cards("Ah Kd"), parse_cards("As 7c 2d")), 2)
        self.assertEqual(hand_tier(parse_cards("7h 7d"), parse_cards("As 7c 2d")), 3)
        self.assertEqual(hand_tier(parse_cards("4h 3d"), parse_cards("As Kc Jd")), 0)

    def test_rule_beats_station(self):
        result = run_match(RuleBot(), CallingStation(), hands=1000, seed=3)
        self.assertGreater(result.bankrolls[0], 0)

    def test_equity_bot_beats_random(self):
        result = run_match(EquityBot(iterations=100, seed=0), RandomBot(seed=0), hands=300, seed=4)
        self.assertGreater(result.bankrolls[0], 0)

    def test_human_bot(self):
        inputs = iter(["nonsense", "r 3", "r 6"])
        out = []
        human = HumanBot(input_fn=lambda prompt: next(inputs), print_fn=out.append)
        sb = Scripted("bot", [FoldAction()])
        result = play_hand([human, sb], button=0, rng=random.Random(0))
        self.assertEqual(result.deltas, (2, -2))
        self.assertTrue(any("Not a legal choice" in line for line in out))


if __name__ == "__main__":
    unittest.main()


class LoaderAndExampleTests(unittest.TestCase):
    def test_load_bot_from_file_and_seed(self):
        from pokerbot.bots import load_bot_class, make_bot
        cls = load_bot_class("pokerbot/examples/tutorial_bot.py:TutorialBot")
        self.assertEqual(cls.name, "tutorial")
        bot = make_bot("pokerbot/examples/my_first_bot.py:MyFirstBot", seed=3)  # no seed arg: ignored
        self.assertEqual(bot.name, "my-first-bot")
        self.assertIsInstance(make_bot("equity", seed=3), EquityBot)
        for bad in ("nope", "missing.py:X", "pokerbot/examples/tutorial_bot.py:Nope"):
            with self.assertRaises(ValueError):
                load_bot_class(bad)

    def test_example_bots_play(self):
        from pokerbot.bots import make_bot
        for spec in ("pokerbot/examples/my_first_bot.py:MyFirstBot",
                     "pokerbot/examples/tutorial_bot.py:TutorialBot"):
            result = run_match(make_bot(spec, seed=1), CallingStation(), hands=40, seed=1)
            self.assertEqual(sum(result.bankrolls), 0)

    def test_kuhn_cfr_converges(self):
        from pokerbot.examples.kuhn_cfr import train
        nodes, value = train(iterations=20_000)
        self.assertAlmostEqual(value, -1 / 18, delta=0.01)
        self.assertAlmostEqual(nodes["Q"].average_strategy()[1], 0.0, delta=0.05)  # never bet Q
        self.assertAlmostEqual(nodes["Kb"].average_strategy()[1], 1.0, delta=0.01)  # always call K
        self.assertAlmostEqual(nodes["Qb"].average_strategy()[1], 1 / 3, delta=0.06)
        alpha = nodes["J"].average_strategy()[1]
        self.assertAlmostEqual(nodes["K"].average_strategy()[1], 3 * alpha, delta=0.08)
