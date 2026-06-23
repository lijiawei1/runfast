"""夺A快跑 — solver.py 测试 (P1)

覆盖: analyze_moves / advance_turn / check_terminal / _apply_move / solve / move 格式
"""

import pytest
from models import Card, Trick, GameState
from solver import (
    solve, _apply_move, analyze_moves,
    advance_turn, check_terminal,
)
from moves import get_legal_moves_free, get_legal_moves_response


# ═══════════════════════════════════════════════════════════════
# P1-1: analyze_moves 测试
# ═══════════════════════════════════════════════════════════════


class TestAnalyzeMoves:
    """analyze_moves() — 局面分析与胜败招识别"""

    def test_star_winning_has_winning_moves(self, fixture_star_winning_state):
        """★ 必胜局面 → winning_moves 非空"""
        state = fixture_star_winning_state
        overall, winning, losing = analyze_moves(state)
        assert overall is True
        assert len(winning) > 0

    def test_star_losing_all_moves_are_losing(self, fixture_star_losing_state):
        """★ 必败局面 → winning_moves 为空"""
        state = fixture_star_losing_state
        overall, winning, losing = analyze_moves(state)
        assert overall is False
        assert len(winning) == 0
        assert len(losing) > 0

    def test_non_star_turn_returns_none(self):
        """非 ★ 回合返回 (None, [], [])"""
        masks = (
            (1 << 0), 1 << 1, 1 << 2, 1 << 3, 1 << 4,
        )
        state = GameState(masks, None, 1, 1)  # P1 回合
        overall, winning, losing = analyze_moves(state)
        assert overall is None
        assert winning == []
        assert losing == []

    def test_analyze_with_trick_on_table(self, fixture_five_players_basic):
        """桌上有牌时的 analyze_moves"""
        state, _ = fixture_five_players_basic
        # 设置 trick 为 P1 刚出的单张 ♦A 的某种替代
        # 直接测试非首出场景
        trick_state = GameState(state.masks, Trick("single", 0, 0), 0, 1)
        overall, winning, losing = analyze_moves(trick_state)
        # ★ 在 trick 场景下应该仍能分析
        assert overall is not None
        assert isinstance(winning, list)
        assert isinstance(losing, list)

    def test_move_info_structure(self, fixture_star_winning_state):
        """每个 move_info 格式: [type_cn, cards_str, orders, raw_move]"""
        state = fixture_star_winning_state
        _, winning, _ = analyze_moves(state)
        for mi in winning:
            assert len(mi) == 4
            assert isinstance(mi[0], str)  # type_cn
            assert isinstance(mi[1], str)  # cards_str
            assert isinstance(mi[2], list)  # orders
            assert isinstance(mi[3], tuple)  # raw_move


# ═══════════════════════════════════════════════════════════════
# P1-2: advance_turn 测试
# ═══════════════════════════════════════════════════════════════


class TestAdvanceTurn:
    """advance_turn() — 回合推进（Pass 情况）"""

    def test_normal_advance_to_next_player(self):
        """正常推进：turn 0→1"""
        masks = (
            (1 << 0), 1 << 1, 1 << 2, 1 << 3, 1 << 4,
        )
        state = GameState(masks, Trick("single", 0, 0), 0, 0)
        ns = advance_turn(state)
        assert ns.turn == 1
        assert ns.starter == 0  # starter 不变
        assert ns.trick is not None  # trick 保持

    def test_advance_cycle_around(self):
        """正常推进：turn 4→0（循环）"""
        masks = (
            (1 << 0), 1 << 1, 1 << 2, 1 << 3, 1 << 4,
        )
        state = GameState(masks, Trick("single", 0, 0), 4, 0)
        ns = advance_turn(state)
        assert ns.turn == 0
        # turn==starter → trick 清空
        assert ns.trick is None

    def test_pass_clears_trick_when_back_to_starter(self):
        """回到 starter 时 trick 清空"""
        masks = (
            (1 << 0), 1 << 1, 1 << 2, 1 << 3, 1 << 4,
        )
        # starter=1, turn=0, 推进到 1 回到 starter
        state = GameState(masks, Trick("single", 0, 0), 0, 1)
        ns = advance_turn(state)
        assert ns.turn == 1
        assert ns.trick is None  # 回到 starter 清空
        assert ns.starter == 1

    def test_pass_skips_to_next_when_not_starter(self):
        """非回到 starter 时 trick 保持"""
        masks = (
            (1 << 0), 1 << 1, 1 << 2, 1 << 3, 1 << 4,
        )
        state = GameState(masks, Trick("single", 0, 0), 2, 0)
        ns = advance_turn(state)
        assert ns.turn == 3
        assert ns.trick is not None


# ═══════════════════════════════════════════════════════════════
# P1-3: check_terminal 测试
# ═══════════════════════════════════════════════════════════════


class TestCheckTerminal:
    """check_terminal() — 终局检测"""

    def test_star_empty_wins(self):
        """★ 手牌空 → (0, True)"""
        masks = (0, 1 << 4, 1 << 8, 1 << 12, 1 << 16)
        state = GameState(masks, None, 0, 0)
        winner, is_terminal = check_terminal(state)
        assert is_terminal is True
        assert winner == 0

    def test_opponent_empty_star_loses(self):
        """对手 P3 手牌空 → (3, True)"""
        masks = ((1 << 0), (1 << 4), (1 << 8), 0, (1 << 16))
        state = GameState(masks, None, 0, 0)
        winner, is_terminal = check_terminal(state)
        assert is_terminal is True
        assert winner == 3

    def test_no_one_empty(self):
        """无人出完 → (None, False)"""
        masks = (
            (1 << 0), 1 << 4, 1 << 8, 1 << 12, 1 << 16,
        )
        state = GameState(masks, None, 0, 0)
        winner, is_terminal = check_terminal(state)
        assert is_terminal is False
        assert winner is None

    def test_multiple_players_not_empty(self):
        """多人在场时未终局"""
        masks = (
            (1 << 0) | (1 << 1),
            (1 << 4) | (1 << 5),
            (1 << 8) | (1 << 9),
            (1 << 12) | (1 << 13),
            (1 << 16) | (1 << 17),
        )
        state = GameState(masks, None, 0, 0)
        _, is_terminal = check_terminal(state)
        assert is_terminal is False


# ═══════════════════════════════════════════════════════════════
# P1-4: _apply_move 与 move 格式转换测试
# ═══════════════════════════════════════════════════════════════


class TestApplyMoveInternals:
    """_apply_move() — 两种格式 (5-tuple & 3-tuple) 正确解析"""

    def test_free_move_5_tuple_format(self):
        """自由出牌 5-tuple 格式：(new_mask, ttype, rank, top_suit, [orders])"""
        masks = (
            (1 << 0) | (1 << 4),
            1 << 1, 1 << 2, 1 << 3, 1 << 5,
        )
        state = GameState(masks, None, 0, 0)
        move = (1 << 4, "single", 0, 0, [0])
        ns = _apply_move(state, move, 0)
        assert ns.masks[0] == (1 << 4)
        assert ns.trick.type == "single"

    def test_response_move_3_tuple_format(self):
        """接力压制 3-tuple 格式：(new_mask, trick_obj, [orders])"""
        trick = Trick("single", 0, 0)
        masks = (
            (1 << 4),       # ★: ♦2
            1 << 1,         # P1: ♣A
            0, 0, 0,
        )
        state = GameState(masks, trick, 1, 0)
        new_trick = Trick("single", 0, 1)
        move = (0, new_trick, [1])
        ns = _apply_move(state, move, 1)
        assert ns.masks[1] == 0
        assert ns.trick == new_trick

    def test_free_pair_5_tuple(self):
        """自由出对子 5-tuple"""
        masks = (
            (1 << 0) | (1 << 1) | (1 << 4) | (1 << 5),
            1 << 8, 1 << 9, 1 << 12, 1 << 13,
        )
        state = GameState(masks, None, 0, 0)
        # 出 ♦A+♣A 对子
        move = ((1 << 4) | (1 << 5), "pair", 0, 1, [0, 1])
        ns = _apply_move(state, move, 0)
        assert ns.masks[0] == (1 << 4) | (1 << 5)
        assert ns.trick.type == "pair"
        assert ns.trick.rank == 0

    def test_response_triple_3_tuple(self):
        """接力三条 3-tuple"""
        from moves import get_legal_moves_response
        trick = Trick("triple", 0, 1)  # ♣A 三条在路上
        # ★ 有 ♥A + ♠A (+ 一张 ♦A 但不在同一 rank 足够)
        # 构造：★ 有 ♥A(order=2) + 两张其他 A 被偷
        # 实际上我们直接 low-level 构造 3-tuple
        masks = (
            1 << 4,             # ★: ♦2
            (1 << 0) | (1 << 1) | (1 << 2),  # P1: ♦A♣A♥A
            0, 0, 0,
        )
        state = GameState(masks, trick, 1, 0)
        new_trick = Trick("triple", 0, 2)  # ♥A top_suit
        move = (0, new_trick, [0, 1, 2])
        ns = _apply_move(state, move, 1)
        assert ns.masks[1] == 0


# ═══════════════════════════════════════════════════════════════
# solve 基本测试
# ═══════════════════════════════════════════════════════════════


class TestSolve:
    """solve() — 核心求解器"""

    def test_star_empty_is_win(self):
        """★ 手牌空 → True"""
        masks = (0, 1 << 4, 1 << 8, 1 << 12, 1 << 16)
        state = GameState(masks, None, 0, 0)
        assert solve(state) is True

    def test_opponent_empty_is_lose(self):
        """对手先出完 → False"""
        masks = ((1 << 0), 0, 1 << 8, 1 << 12, 1 << 16)
        state = GameState(masks, None, 0, 0)
        assert solve(state) is False

    def test_star_winning_fixture(self, fixture_star_winning_state):
        """★ 必胜局面 fixture 验证"""
        assert solve(fixture_star_winning_state) is True

    def test_star_losing_fixture(self, fixture_star_losing_state):
        """★ 必败局面 fixture 验证"""
        assert solve(fixture_star_losing_state) is False

    def test_star_has_pair_a(self, fixture_star_has_pair_a_state):
        """★ 有对A 局面必胜"""
        assert solve(fixture_star_has_pair_a_state) is True


# ═══════════════════════════════════════════════════════════════
# move 格式集成测试 (P1-4 续)
# ═══════════════════════════════════════════════════════════════


class TestMoveFormatIntegration:
    """move 格式从枚举到应用的集成验证"""

    def test_free_moves_all_5_tuple(self):
        """get_legal_moves_free 返回的全部是 5-tuple"""
        from moves import get_legal_moves_free
        mask = (1 << 0) | (1 << 4) | (1 << 1) | (1 << 5) | (1 << 8)
        moves = get_legal_moves_free(mask)
        for move in moves:
            assert len(move) == 5, f"move 应为 5-tuple，实际 {len(move)}"

    def test_response_moves_all_3_tuple(self):
        """get_legal_moves_response 返回的全部是 3-tuple"""
        from moves import get_legal_moves_response
        mask = (1 << 1) | (1 << 5)  # ♣A, ♣2
        trick = Trick("single", 0, 0)  # ♦A
        moves = get_legal_moves_response(mask, trick)
        for move in moves:
            assert len(move) == 3, f"move 应为 3-tuple，实际 {len(move)}"
            assert isinstance(move[1], Trick), "第二个元素应是 Trick 实例"

    def test_free_move_applicable(self):
        """自由出牌 5-tuple 能被 _apply_move 正确消费"""
        masks = (
            (1 << 0) | (1 << 4),
            1 << 1, 1 << 2, 1 << 3, 1 << 5,
        )
        state = GameState(masks, None, 0, 0)
        from moves import get_legal_moves_free
        moves = get_legal_moves_free(state.masks[0])
        for move in moves:
            ns = _apply_move(state, move, 0)
            assert isinstance(ns, GameState)

    def test_response_move_applicable(self):
        """响应出牌 3-tuple 能被 _apply_move 正确消费"""
        masks = (
            (1 << 4),           # ★: ♦2
            1 << 1,             # P1: ♣A
            1 << 2, 1 << 3, 1 << 5,
        )
        trick = Trick("single", 0, 0)
        state = GameState(masks, trick, 1, 0)
        from moves import get_legal_moves_response
        moves = get_legal_moves_response(state.masks[1], state.trick)
        if moves:
            ns = _apply_move(state, moves[0], 1)
            assert isinstance(ns, GameState)
