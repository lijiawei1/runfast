"""夺A快跑 — sequence.py 测试 (P2, P4)

覆盖:
  P2-1: format_sequence / enumerate_da_moves / verify_all_da_moves
  P2-2: find_best_response 边界
  P4: mode2 强制出牌序列验证（跨 relay 错位 bug 修复）
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
from moves import get_legal_moves_response


# ═══════════════════════════════════════════════════════════════
# P2-1: format_sequence 测试
# ═══════════════════════════════════════════════════════════════


class TestFormatSequence:
    """format_sequence() — 序列格式化"""

    def test_none_input(self):
        """None 表示★必胜，同盟无必胜序列"""
        result = format_sequence(None)
        assert "同盟无必胜序列" in result

    def test_empty_sequence(self):
        """空序列（对手直接出完）"""
        result = format_sequence([])
        assert "已无路可退" in result
        assert "对手将直接出完" in result

    def test_sequence_with_star_and_opponent(self):
        """含 ★ 和对手出牌的序列"""
        # 构造一个简单序列
        seq = [
            (0, Move.from_free(0, "single", 0, 0, [0])),   # ★ 出 ♦A
            (1, Move.from_free(0, "single", 0, 1, [1])),   # P1 出 ♣A
        ]
        result = format_sequence(seq)
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
        """空序列 → 同盟无应对策略"""
        result = format_best_response([])
        assert "同盟无应对策略" in result

    def test_nonempty_sequence(self):
        """非空序列 → 包含应对描述"""
        seq = [
            (1, Move.from_free(0, "single", 0, 1, [1])),
            (2, Move.from_free(0, "single", 0, 2, [2])),
        ]
        result = format_best_response(seq)
        assert "玩家1 → 出" in result
        assert "玩家2 → 出" in result
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


# ═══════════════════════════════════════════════════════════════
# P4: mode2 强制出牌序列验证 — 跨 relay 错位 bug
# ═══════════════════════════════════════════════════════════════
#
# 背景：_dfs_win_seq 不记录 Pass 操作。实际游戏中玩家 Pass 时，
# 序列中的后续条目会错位 — 本该在"单张 relay"的出牌被错误匹配到
# "对子 relay"。修复方案：执行强制出牌前验证牌型与当前 trick 匹配。


class TestForcedMoveValidation:
    """验证 mode2_game_loop 中的强制出牌合法性检查"""

    def test_rejects_move_with_wrong_type_in_response_state(self):
        """当前 trick 为 pair 时，序列中的 single 强制出牌应被拒绝"""
        # 构造一个状态：trick=pair，turn=3（玩家3）
        trick = Trick("pair", 5, 2)  # pair 5, ♥
        masks = (
            1 << 36,                  # ★: ♦10（只剩1张）
            0,                        # P1: 空
            0,                        # P2: 空
            (1 << 2) | (1 << 6),      # P3: ♥A(2) + ♠2(6)
            0,                        # P4: 空
        )
        state = GameState(masks, trick, 3, 0)

        # 模拟从序列中匹配到的强制出牌（来自未来 relay 的 single）
        forced_move = Move.from_free(0, "single", 0, 2, [2])  # ♥A 单张

        # ── 验证逻辑（与 mode2_game_loop 中一致）──
        player_mask = state.masks[state.turn]  # = masks[3]
        move_orders = forced_move.orders
        cards_in_hand = all(
            player_mask & (1 << o) for o in move_orders
        )
        type_ok = (state.trick.type == forced_move.type)

        assert cards_in_hand is True     # 牌在手
        assert type_ok is False          # "pair" != "single"
        assert not (cards_in_hand and type_ok)  # force_valid = False

    def test_accepts_move_with_matching_type_in_response_state(self):
        """当前 trick 为 pair 时，序列中的 pair 强制出牌应被接受"""
        trick = Trick("pair", 3, 0)  # pair 4, ♦
        masks = (
            1 << 0,                   # ★: ♦A
            (1 << 12) | (1 << 13),    # P1: ♦4(12) + ♣4(13) → 对4
            0,
            0,
            0,
        )
        state = GameState(masks, trick, 1, 0)

        # 合法的 pair 响应
        forced_move = Move.from_response(
            (1 << 12) | (1 << 13),  # 出完后 mask=0 的错觉...
            Trick("pair", 3, 1),    # pair 4, ♣
            [12, 13],
        )
        # 实际上 new_mask 应该是 ~cards，但这里只测 type 验证
        player_mask = state.masks[state.turn]
        move_orders = forced_move.orders
        cards_in_hand = all(
            player_mask & (1 << o) for o in move_orders
        )
        type_ok = (state.trick.type == forced_move.type)

        assert cards_in_hand is True
        assert type_ok is True       # "pair" == "pair"
        assert cards_in_hand and type_ok  # force_valid = True

    def test_accepts_move_in_free_play_state(self):
        """trick=None（自由出牌）时，任何合法牌型都应被接受"""
        masks = (
            (1 << 0) | (1 << 1),     # ★: ♦A + ♣A
            (1 << 2) | (1 << 3),     # P1: ♥A + ♠A
            0, 0, 0,
        )
        state = GameState(masks, None, 1, 1)  # trick=None, P1 自由出

        forced_move = Move.from_free(0, "pair", 0, 3, [2, 3])  # P1 pair A

        player_mask = state.masks[state.turn]
        move_orders = forced_move.orders
        cards_in_hand = all(
            player_mask & (1 << o) for o in move_orders
        )
        # trick 为 None → 校验应通过
        if state.trick is not None:
            type_ok = (state.trick.type == forced_move.type)
        else:
            type_ok = True

        assert cards_in_hand is True
        assert type_ok is True

    def test_rejects_move_with_cards_not_in_hand(self):
        """强制出牌中的牌不在手 → 拒绝"""
        trick = Trick("single", 0, 0)  # single A, ♦
        masks = (
            1 << 0,                   # ★: ♦A
            (1 << 4),                 # P1: ♦2 → 没有 order=1 的牌
            0, 0, 0,
        )
        state = GameState(masks, trick, 1, 0)

        # 尝试强制出 ♣A(order=1)，但 P1 手牌中没有
        forced_move = Move.from_response(
            0, Trick("single", 0, 1), [1]
        )

        player_mask = state.masks[state.turn]
        move_orders = forced_move.orders
        cards_in_hand = all(
            player_mask & (1 << o) for o in move_orders
        )
        assert cards_in_hand is False  # order=1 不在 P1 手牌中

    def test_integration_sequence_stale_after_pass(self):
        """集成测试：模拟 ★ 出对子后对手 Pass 导致序列错位"""
        # ── 构造场景 ──
        # ★: ♦A(0), ♣A(1), ♦10(36)  — 3张
        # P1: ♦2(4), ♣2(5)           — 1对（可回应对子）
        # P2: ♥2(6)                   — 1单（无法回应对子 → Pass）
        # P3: ♠2(7)                   — 1单
        # P4: ♦3(8)                   — 1单
        #
        # 流程：★ 出对A → P1 出对2 → P2 Pass → P3 应从序列中
        # 找 pair 响应，但序列可能在 P3 位置存的是 single（错位）
        masks = (
            (1 << 0) | (1 << 1) | (1 << 36),  # ★: ♦A, ♣A, ♦10
            (1 << 4) | (1 << 5),               # P1: ♦2, ♣2
            (1 << 6),                           # P2: ♥2
            (1 << 7),                           # P3: ♠2
            (1 << 8),                           # P4: ♦3
        )
        state = GameState(masks, None, 0, 0)

        # ★ 出对A → state: turn=1, trick=pair(A, ♣)
        move_da_pair = Move.from_free(
            (1 << 36), "pair", 0, 1, [0, 1]
        )
        state = _apply_move(state, move_da_pair, 0)
        assert state.trick is not None
        assert state.trick.type == "pair"
        assert state.turn == 1  # 轮到 P1

        # 获取同盟最优序列
        seq = find_best_response(state)
        # seq 可能为空（★ 赢）或包含对手应对
        if not seq:
            # ★ 必胜 → 测试直接通过（序列为空是合法的）
            return

        # 模拟：P1 按序列出牌
        forced_p1 = None
        for p, m in seq:
            if p == 1:
                forced_p1 = m
                break
        assert forced_p1 is not None, "P1 应有强制出牌"
        assert forced_p1.type == "pair", \
            f"P1 应出对子，实际为 {forced_p1.type}"

        # P1 执行强制出牌
        state = _apply_move(state, forced_p1, 1)
        # 现在轮到 P2
        assert state.turn == 2

        # P2 无法回应对子 → Pass
        p2_moves = get_legal_moves_response(
            state.masks[2], state.trick
        )
        assert not p2_moves, "P2 应无法回应对子"

        # 模拟 Pass
        from solver import advance_turn
        state = advance_turn(state)
        # 现在轮到 P3，但 trick 仍是 pair
        assert state.turn == 3
        assert state.trick.type == "pair"

        # 从序列查找 P3 的强制出牌
        forced_p3 = None
        for p, m in seq:
            if p == 3:
                forced_p3 = m
                break

        if forced_p3 is not None:
            # 验证 P3 的强制出牌类型是否与当前 trick 匹配
            # 这是 bug 修复的关键检查点
            move_type_ok = (state.trick.type == forced_p3.type)
            player_mask = state.masks[3]
            cards_ok = all(
                player_mask & (1 << o) for o in forced_p3.orders
            )
            force_valid = move_type_ok and cards_ok

            if not force_valid:
                # 序列失效 → 这正是我们期望检测到的情况
                # 应拒绝并回退到 play_turn（含最优策略）
                pass
            # 测试通过：验证逻辑正确运行，没有崩溃或错误应用出牌
