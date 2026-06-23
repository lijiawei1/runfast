"""夺A快跑 — 共享测试 fixtures"""

import pytest
from models import Card, Trick, GameState
from solver import solve


# ── 工具函数 ──

def _cards(specs: list[str]) -> list[Card]:
    """字符串列表 → Card 列表，如 ['♦A', '♦2', '♣4']"""
    SUIT_MAP = {'♦': 0, '♣': 1, '♥': 2, '♠': 3}
    RANK_MAP = {
        'A': 0, '2': 1, '3': 2, '4': 3, '5': 4,
        '6': 5, '7': 6, '8': 7, '9': 8, '10': 9,
        'J': 10, 'Q': 11, 'K': 12,
    }
    result: list[Card] = []
    for s in specs:
        suit_char = s[0]
        rank_str = s[1:]
        result.append(Card(RANK_MAP[rank_str], SUIT_MAP[suit_char]))
    return result


def _mask(cards: list[Card]) -> int:
    """Card 列表 → 25-bit mask"""
    m = 0
    for c in cards:
        m |= 1 << c.order
    return m


# ── 复用 Fixtures ──


@pytest.fixture
def fixture_star_winning_state():
    """★ 必胜局面：★只剩 ♦7（全局最大单张），对手各有5张低牌。
    调用前验证 solve()=True。"""
    masks = (
        1 << 24,                                    # ★: ♦7(全局最大)
        (1 << 0) | (1 << 4) | (1 << 8) | (1 << 12) | (1 << 16),   # P1
        (1 << 1) | (1 << 5) | (1 << 9) | (1 << 13) | (1 << 17),   # P2
        (1 << 2) | (1 << 6) | (1 << 10) | (1 << 14) | (1 << 18),  # P3
        (1 << 3) | (1 << 7) | (1 << 11) | (1 << 15) | (1 << 19),  # P4
    )
    state = GameState(masks, None, 0, 0)
    assert solve(state), "fixture 前提：★应当必胜"
    return state


@pytest.fixture
def fixture_star_losing_state():
    """★ 必败局面：★有 ♦A+♦2，对手各有1张牌（出♦A后下家立即出完）。
    调用前验证 solve()=False。"""
    masks = (
        (1 << 0) | (1 << 4),        # ★: ♦A + ♦2
        1 << 1,                     # P1: ♣A
        1 << 2,                     # P2: ♥A
        1 << 3,                     # P3: ♠A
        1 << 5,                     # P4: ♣2
    )
    state = GameState(masks, None, 0, 0)
    assert not solve(state), "fixture 前提：★应当必败"
    return state


@pytest.fixture
def fixture_star_has_pair_a_state():
    """★ 有对A（♦A+♣A），对手只有单张的状态。★必胜。"""
    masks = (
        (1 << 0) | (1 << 1),        # ★: ♦A + ♣A (对A)
        1 << 4,                     # P1: ♦2
        1 << 5,                     # P2: ♣2
        1 << 8,                     # P3: ♦3
        1 << 12,                    # P4: ♦4
    )
    state = GameState(masks, None, 0, 0)
    assert solve(state), "fixture 前提：★应当必胜"
    return state


@pytest.fixture
def fixture_five_players_basic():
    """5人各有5张牌的基本局面，★有 ♦A。
    返回 (state, masks_tuple)。"""
    # ★: ♦A(0), ♠2(7), ♦4(12), ♣5(17), ♦7(24)
    star_mask = 0
    for o in [0, 7, 12, 17, 24]:
        star_mask |= 1 << o

    masks = (
        star_mask,
        (1 << 1) | (1 << 4) | (1 << 8) | (1 << 13) | (1 << 16),  # P1
        (1 << 2) | (1 << 5) | (1 << 9) | (1 << 14) | (1 << 18),  # P2
        (1 << 3) | (1 << 6) | (1 << 10) | (1 << 15) | (1 << 19), # P3
        (1 << 11) | (1 << 20) | (1 << 21) | (1 << 22) | (1 << 23), # P4
    )
    state = GameState(masks, None, 0, 0)
    return state, masks


@pytest.fixture
def fixture_next_single_card_state():
    """下家只剩1张（♥3, order=10）的局面，★有5张杂牌。"""
    star_mask = 0
    for o in [0, 7, 12, 17, 24]:
        star_mask |= 1 << o
    next_mask = 1 << 10  # ♥3

    masks = (star_mask, next_mask, 0, 0, 0)
    state = GameState(masks, None, 0, 0)
    return state, masks, star_mask, next_mask
