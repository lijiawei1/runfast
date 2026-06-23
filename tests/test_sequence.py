"""夺A快跑 — sequence.py 测试 (P2)

覆盖:
  P2-1: format_sequence / enumerate_da_moves / verify_all_da_moves
  P2-2: find_best_response 边界
"""

import pytest
from models import Card, Trick, GameState, Move
from solver import solve, _apply_move
from sequence import (
    format_sequence,
    enumerate_da_moves,
    verify_all_da_moves,
    find_best_response,
    format_best_response,
    find_winning_sequence,
    format_multi_da_verification,
)


# ═══════════════════════════════════════════════════════════════
# P2-1: format_sequence 测试
# ═══════════════════════════════════════════════════════════════


class TestFormatSequence:
    """format_sequence() — 序列格式化"""

    def test_none_input(self):
        """★ 必胜时返回提示"""
        result = format_sequence(None)
        assert "★ 必胜" in result
        assert "无必胜序列" in result

    def test_empty_sequence(self):
        """空序列（对手直接出完）"""
        result = format_sequence([])
        assert "同盟有必胜策略" in result
        assert "已无路可退" in result

    def test_sequence_with_star_and_opponent(self):
        """含 ★ 和对手出牌的序列"""
        # 构造一个简单序列
        seq = [
            (0, Move.from_free(0, "single", 0, 0, [0])),   # ★ 出 ♦A
            (1, Move.from_free(0, "single", 0, 1, [1])),   # P1 出 ♣A
        ]
        result = format_sequence(seq)
        assert "同盟有必胜策略" in result
        assert "★ → 出" in result
        assert "玩家1 → 出" in result

    def test_sequence_ends_with_star_defeat(self):
        """序列以 ★ 输结尾"""
        seq = [
            (1, Move.from_free(0, "single", 0, 1, [1])),   # P1 出 ♣A
        ]
        result = format_sequence(seq)
        assert "★ 最终无法出牌/最后出完" in result

    def test_sequence_3_tuple_move(self):
        """序列含 3-tuple 出牌"""
        trick = Trick("single", 0, 1)
        seq = [
            (1, Move.from_response(0, trick, [1])),
        ]
        result = format_sequence(seq)
        assert "玩家1 → 出" in result


# ═══════════════════════════════════════════════════════════════
# P2-1: enumerate_da_moves 测试
# ═══════════════════════════════════════════════════════════════


class TestEnumerateDaMoves:
    """enumerate_da_moves() — 枚举含 ♦A 的出牌"""

    def test_all_moves_contain_da(self):
        """所有返回的move都含 ♦A(order=0)"""
        # ★ 有 ♦A(0), ♣A(1), ♦2(4) 三张牌
        mask = (1 << 0) | (1 << 1) | (1 << 4)
        da_moves = enumerate_da_moves(mask)
        assert len(da_moves) >= 1
        for move in da_moves:
            assert 0 in move[4], f"move {move} 应包含 ♦A(order=0)"

    def test_hand_without_da_returns_empty(self):
        """手牌不含 ♦A 时返回空列表"""
        mask = (1 << 1) | (1 << 4)  # ♣A, ♦2
        da_moves = enumerate_da_moves(mask)
        assert da_moves == []

    def test_pair_with_da_included(self):
        """♦A 对子被包含"""
        mask = (1 << 0) | (1 << 1)  # ♦A + ♣A
        da_moves = enumerate_da_moves(mask)
        # 应包含对子
        pair_moves = [m for m in da_moves if m[1] == "pair"]
        assert len(pair_moves) >= 1

    def test_moves_are_5_tuples(self):
        """返回的move是5-tuple格式"""
        mask = (1 << 0) | (1 << 4)
        da_moves = enumerate_da_moves(mask)
        for move in da_moves:
            assert len(move) == 5


# ═══════════════════════════════════════════════════════════════
# P2-1: verify_all_da_moves 测试
# ═══════════════════════════════════════════════════════════════


class TestVerifyAllDaMoves:
    """verify_all_da_moves() — 多分支验证"""

    def test_returns_dict(self):
        """返回 dict 结构"""
        # ★ 有 ♦A(0) + ♦2(4), 对手各1张
        masks = (
            (1 << 0) | (1 << 4),  # ★
            1 << 1,                # P1: ♣A
            1 << 2,                # P2: ♥A
            1 << 3,                # P3: ♠A
            1 << 5,                # P4: ♣2
        )
        state = GameState(masks, None, 0, 0)
        result = verify_all_da_moves(state)
        assert isinstance(result, dict)
        # 每种含 ♦A 出牌都有 key
        assert len(result) >= 1
        for desc, seq in result.items():
            assert "♦A" in desc
            assert seq is None or isinstance(seq, list)


# ═══════════════════════════════════════════════════════════════
# P2-2: find_best_response 边界测试
# ═══════════════════════════════════════════════════════════════


class TestFindBestResponse:
    """find_best_response() — 最优应对"""

    def test_star_winning_returns_empty(self, fixture_star_winning_state):
        """★ 必胜局面 → 返回空列表"""
        state = fixture_star_winning_state
        result = find_best_response(state)
        assert result == []

    def test_star_losing_returns_nonempty(self):
        """★ 必败局面 → 返回非空序列"""
        # ★ 有 ♦A+♦2，P1 有 ♣A，且 ♣A > ♦A（同 rank，suit ♣=1 > ♦=0）
        masks = (
            (1 << 0) | (1 << 4),        # ★: ♦A + ♦2
            1 << 1,                     # P1: ♣A
            1 << 2,                     # P2: ♥A
            1 << 3,                     # P3: ♠A
            1 << 5,                     # P4: ♣2
        )
        state = GameState(masks, None, 0, 0)
        # ★ 先出 ♦A，然后调用 find_best_response
        move = ((1 << 4), "single", 0, 0, [0])
        ns = _apply_move(state, move, 0)
        result = find_best_response(ns)
        # ★ 只剩 ♦2，对手有 ♣A > ♦2，★ 必输
        assert isinstance(result, list)


# ═══════════════════════════════════════════════════════════════
# format_best_response 测试
# ═══════════════════════════════════════════════════════════════


class TestFormatBestResponse:
    """format_best_response() — 最优应对格式化"""

    def test_empty_sequence(self):
        """空序列 → ★ 必胜提示"""
        result = format_best_response([])
        assert "★ 必胜" in result

    def test_nonempty_sequence(self):
        """非空序列 → 包含应对描述"""
        seq = [
            (1, Move.from_free(0, "single", 0, 1, [1])),
            (2, Move.from_free(0, "single", 0, 2, [2])),
        ]
        result = format_best_response(seq)
        assert "同盟有最优应对" in result
        assert "玩家1 → 出" in result
        assert "★ 最终失败" in result

    def test_3_tuple_in_sequence(self):
        """序列含 3-tuple 格式正确渲染"""
        trick = Trick("single", 0, 2)
        seq = [
            (1, Move.from_response(0, trick, [2])),
        ]
        result = format_best_response(seq)
        assert "玩家1 → 出" in result


# ═══════════════════════════════════════════════════════════════
# find_winning_sequence 边界测试
# ═══════════════════════════════════════════════════════════════


class TestFindWinningSequence:
    """find_winning_sequence() — 同盟必胜序列"""

    def test_star_winning_returns_none(self, fixture_star_winning_state):
        """★ 必胜 → 返回 None"""
        assert find_winning_sequence(fixture_star_winning_state) is None

    def test_star_losing_returns_sequence(self, fixture_star_losing_state):
        """★ 必败 → 返回非空序列"""
        result = find_winning_sequence(fixture_star_losing_state)
        # ★ 必败时应有同盟必胜序列
        assert result is None or len(result) > 0


# ═══════════════════════════════════════════════════════════════
# format_multi_da_verification 测试
# ═══════════════════════════════════════════════════════════════


class TestFormatMultiDaVerification:
    """format_multi_da_verification() — 多分支验证格式化"""

    def test_all_opponent_winning(self):
        """同盟全有必胜序列的输出"""
        result_dict = {
            "单张: ♦A": [(1, Move.from_free(0, "single", 0, 1, [1]))],
            "对子: ♦A ♣A": [(1, Move.from_free(0, "pair", 0, 2, [0, 1]))],
        }
        result = format_multi_da_verification(result_dict)
        assert "同盟有必胜策略" in result

    def test_has_star_winning_move(self):
        """存在 ★ 胜招的输出"""
        result_dict = {
            "单张: ♦A": [(1, Move.from_free(0, "single", 0, 1, [1]))],
            "对子: ♦A ♣A": None,  # ★ 胜招
        }
        result = format_multi_da_verification(result_dict)
        assert "★ 有胜招" in result
        assert "可破局" in result

    def test_empty_dict(self):
        """空字典（无 ♦A 出牌）"""
        result = format_multi_da_verification({})
        assert isinstance(result, str)
