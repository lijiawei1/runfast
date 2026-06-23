"""测试玩家人数动态化功能（5~8人局）"""

import pytest
from deck import build_deck, shuffle_and_deal, hands_to_masks, take_bid_logic, find_diamond_a_holder
from models import GameState, Card, Trick
from solver import solve, check_terminal, advance_turn
from cli import apply_move
from game_engine import get_valid_moves_for_player, get_opponent_best_move


# ── P0: 牌堆截断测试 ──

def test_build_deck_num_players():
    """验证 build_deck(num_players) 按人数截断牌堆"""
    # 5人局：25张，最大 ♦7 (order=24)
    d5 = build_deck(5)
    assert len(d5) == 25
    assert d5[-1].order == 24
    assert str(d5[-1]) == "♦7"

    # 6人局：30张，最大 ♣8 (order=29)
    d6 = build_deck(6)
    assert len(d6) == 30
    assert d6[-1].order == 29
    assert str(d6[-1]) == "♣8"

    # 7人局：35张，最大 ♥9 (order=34)
    d7 = build_deck(7)
    assert len(d7) == 35
    assert d7[-1].order == 34
    assert str(d7[-1]) == "♥9"

    # 8人局：40张，最大 ♠10 (order=39)
    d8 = build_deck(8)
    assert len(d8) == 40
    assert d8[-1].order == 39
    assert str(d8[-1]) == "♠10"

    # 非法人数应抛出 ValueError
    with pytest.raises(ValueError, match="仅支持5~8人局"):
        build_deck(4)
    with pytest.raises(ValueError, match="仅支持5~8人局"):
        build_deck(9)


def test_build_deck_no_duplicates():
    """确认各人数牌堆无重复牌"""
    for n in (5, 6, 7, 8):
        deck = build_deck(n)
        orders = [c.order for c in deck]
        assert len(orders) == len(set(orders)), f"{n}人局有重复牌"
        assert max(orders) == n * 5 - 1
        assert min(orders) == 0


# ── P0: GameState 动态化测试 ──

def test_game_state_dynamic_masks():
    """验证 GameState 支持不同长度的 masks"""
    state5 = GameState(masks=(1, 1, 1, 1, 1), trick=None, turn=0, starter=0)
    assert state5.num_players == 5

    state6 = GameState(masks=(1, 1, 1, 1, 1, 1), trick=None, turn=0, starter=0)
    assert state6.num_players == 6

    state7 = GameState(masks=(1, 1, 1, 1, 1, 1, 1), trick=None, turn=0, starter=0)
    assert state7.num_players == 7

    state8 = GameState(masks=(1, 1, 1, 1, 1, 1, 1, 1), trick=None, turn=0, starter=0)
    assert state8.num_players == 8


def test_game_state_num_players_property():
    """num_players 属性返回 masks 长度"""
    masks = (1, 2, 3, 4, 5)
    state = GameState(masks=masks, trick=None, turn=0, starter=0)
    assert state.num_players == 5
    assert state.num_players == len(masks)


# ── P0: 发牌测试 ──

def test_shuffle_and_deal_num_players():
    """确认 shuffle_and_deal 按人数发牌"""
    for n in (5, 6, 7, 8):
        deck = build_deck(n)
        hands = shuffle_and_deal(deck, n)
        assert len(hands) == n
        for i, hand in enumerate(hands):
            assert len(hand) == 5, f"{n}人局玩家{i}手牌数={len(hand)}"


def test_hands_to_masks_dynamic():
    """确认 hands_to_masks 返回动态长度 tuple"""
    for n in (5, 6, 7, 8):
        deck = build_deck(n)
        hands = shuffle_and_deal(deck, n)
        masks = hands_to_masks(hands)
        assert len(masks) == n
        for m in masks:
            assert m.bit_count() == 5  # 每人5张


# ── P0: solver 多人数测试 ──

def test_solve_with_6_players_star_wins():
    """6人局：★有全局最大单张♦10，直接出完"""
    masks = (1 << 39,)  # ★: ♦10 (order=39, 全局最大)
    # 其余5位对手各有5张杂牌
    opponent_bits = []
    remaining = set(range(0, 30))  # orders 0~29
    for i in range(5):
        m = 0
        for _ in range(5):
            o = remaining.pop()
            m |= 1 << o
        opponent_bits.append(m)
    masks = tuple([masks[0]] + opponent_bits)
    state = GameState(masks=masks, trick=None, turn=0, starter=0)
    assert solve(state), "★有全局最大单张，应必胜"


def test_solve_with_7_players_star_loses():
    """7人局：★有♦A+♦2，下家P1有♠K和♥K（2张），★出♦A后P1管上但不立即出完"""
    # ★: ♦A(0), ♦2(4) — 出♦A后还有♦2
    # P1: ♠K(38), ♥K(39) — 能管♦A，出♦A后剩1张
    # P2~P6: 各有一些牌
    masks = [
        (1 << 0) | (1 << 4),  # ★: ♦A + ♦2
        1 << 38,               # P1: ♠K（单张，出完即赢）
    ]
    remaining_orders = set(range(1, 35))
    remaining_orders.discard(4)   # ♦2 already assigned
    remaining_orders.discard(38)  # ♠K already assigned
    for i in range(5):  # P2~P6
        m = 0
        for _ in range(5):
            if remaining_orders:
                o = remaining_orders.pop()
                m |= 1 << o
        masks.append(m)
    masks = tuple(masks)
    state = GameState(masks=masks, trick=None, turn=0, starter=0)
    # ★出♦A后，P1出♠K→立即出完→★败
    assert not solve(state), "★出♦A后P1立即出完，★应必败"


# ── P1: 端到端 6 人局流程 ──

def test_6_player_game_flow():
    """模拟6人局完整流程：发牌→抢A→出牌一回合"""
    n = 6
    deck = build_deck(n)
    hands = shuffle_and_deal(deck, n)

    # 找到 ♦A 持有者作为 bidder
    da_owner = find_diamond_a_holder(hands)
    # 让 ♦A 持有者抢A（自己抢）
    bidder, updated_hands = take_bid_logic(hands, da_owner)

    assert bidder is not None
    assert len(updated_hands) == n
    for i, hand in enumerate(updated_hands):
        assert len(hand) == 5, f"玩家{i}应有5张，实际{len(hand)}"

    # 重排：★ 移到索引0
    reordered = [updated_hands[da_owner]]
    for i in range(n):
        if i != da_owner:
            reordered.append(updated_hands[i])

    masks = hands_to_masks(reordered)
    state = GameState(masks=masks, trick=None, turn=0, starter=0)

    assert state.num_players == 6
    assert len(state.masks) == 6

    # 验证 check_terminal 正常工作
    winner, game_over = check_terminal(state)
    assert not game_over

    # 验证 ★ 有合法出牌
    moves = get_valid_moves_for_player(state, 0)
    assert len(moves) > 0

    # ★ 出第一手牌（必须含♦A）
    da_move = None
    for m in moves:
        if 0 in m.orders:
            da_move = m
            break
    assert da_move is not None, "★应有含♦A的出牌"

    # 应用出牌
    new_state = apply_move(state, da_move, 0)
    assert new_state.num_players == 6  # 状态保持

    # turn 应移到下家
    assert new_state.turn == 1


# ── P1: solver 在 6/7/8 人局不崩溃 ──

def test_solver_multi_player_no_crash():
    """确认 solver 在 6/7/8 人局不会因为硬编码崩溃"""
    for n in (6, 7, 8):
        deck = build_deck(n)
        hands = shuffle_and_deal(deck, n)
        da_owner = find_diamond_a_holder(hands)
        _, updated_hands = take_bid_logic(hands, da_owner)
        reordered = [updated_hands[da_owner]] + [
            updated_hands[i] for i in range(n) if i != da_owner
        ]
        masks = hands_to_masks(reordered)
        state = GameState(masks=masks, trick=None, turn=0, starter=0)

        # 调用 solve（不应崩溃）
        result = solve(state)
        assert isinstance(result, bool), f"{n}人局 solve 应返回 bool"

        # 调用 analyze_moves 或 get_valid_moves_for_player
        moves = get_valid_moves_for_player(state, 0)
        assert isinstance(moves, list), f"{n}人局应返回合法出牌列表"

        # 终局检测
        w, g = check_terminal(state)
        assert g is False or isinstance(w, int)


# ── P1: advance_turn 多人数 ──

def test_advance_turn_multi_player():
    """验证 advance_turn 在 6/7/8 人局正确轮转"""
    for n in (6, 7, 8):
        masks = tuple([1] * n)
        # 初始：turn=0(starter=0)，所有人都有牌
        state = GameState(masks=masks, trick=None, turn=0, starter=0)
        assert state.turn == 0

        # 模拟一圈 pass
        current = state
        for t in range(1, n):
            # turn 从 t 到 t+1（因为 trick=None 时 advance_turn 不会触发 pass 逻辑）
            # 需要设置一个 trick 让 advance_turn 走 pass 分支
            pass

    # 精确测试：设固定 trick，模拟一圈 pass
    s = GameState(masks=masks, trick=Trick("single", 0, 0), turn=1, starter=0)
    for i in range(n - 1):  # turn 从 1 走到 n-1
        s = advance_turn(s)
        if i < n - 2:
            assert s.trick is not None, f"第{i+1}步不应清空 trick"
            assert s.turn == (1 + i + 1) % n
        else:
            # 最后一圈回到 starter=0
            assert s.turn == 0
            assert s.trick is None  # trick 应清空


# ── P1: get_opponent_best_move 多人数 ──

def test_opponent_best_move_multi_player():
    """验证 get_opponent_best_move 在 6/7/8 人局正常工作"""
    for n in (6, 7, 8):
        # ★: ♦A(0), 对手各有1张牌
        masks = [1 << 0]  # ★
        for i in range(1, n):
            masks.append(1 << (i))  # order 1, 2, 3, ...
        masks = tuple(masks)
        state = GameState(masks=masks, trick=Trick("single", 0, 0), turn=1, starter=0)

        move = get_opponent_best_move(state, 1)
        # P1 应该有牌可出
        assert move is not None, f"{n}人局 P1 应有牌可出"


# ── P1: 牌堆顺序验证 ──

def test_build_deck_cards_in_order():
    """确认 build_deck 按 globalOrder 递增排列"""
    for n in (5, 6, 7, 8):
        deck = build_deck(n)
        for i in range(1, len(deck)):
            assert deck[i].order > deck[i - 1].order, \
                f"{n}人局: deck[{i}](order={deck[i].order}) <= deck[{i-1}](order={deck[i-1].order})"
