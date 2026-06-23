"""夺A快跑 — 牌组构建、发牌与抢A阶段"""

import random
from models import Card


def build_deck(num_players: int = 5) -> list[Card]:
    """构建 num_players×5 张牌（5人=25张, 6人=30张, 7人=35张, 8人=40张）。

    只取 globalOrder 0 ~ (num_players×5 - 1) 的牌。
    """
    if num_players not in (5, 6, 7, 8):
        raise ValueError(f"仅支持5~8人局，收到: {num_players}")
    total = num_players * 5  # 25/30/35/40
    deck: list[Card] = []
    for rank in range(13):
        for suit in range(4):
            card = Card(rank, suit)
            if card.order >= total:
                break
            deck.append(card)
        else:
            continue
        break
    return deck


def shuffle_and_deal(deck: list[Card], num_players: int = 5) -> list[list[Card]]:
    """洗牌后发给 num_players 人，每人5张"""
    shuffled = deck[:]
    random.shuffle(shuffled)
    hands: list[list[Card]] = [[] for _ in range(num_players)]
    for i, card in enumerate(shuffled):
        hands[i % num_players].append(card)
    return hands


def hands_to_masks(hands: list[list[Card]]) -> tuple[int, ...]:
    """将 N 个玩家的手牌各自转为 bitmask，返回动态长度 tuple"""
    masks: list[int] = []
    for hand in hands:
        m = 0
        for c in hand:
            m |= 1 << c.order
        masks.append(m)
    return tuple(masks)


def find_diamond_a_holder(hands: list[list[Card]]) -> int:
    """返回 ♦A（rank=0, suit=0）所在的玩家索引 (0~4)"""
    for i, hand in enumerate(hands):
        for c in hand:
            if c.rank == 0 and c.suit == 0:
                return i
    raise ValueError("♦A 不存在")


def take_bid_logic(
    hands: list[list[Card]], bidder: int | None
) -> tuple[int | None, list[list[Card]]]:
    """
    抢A纯逻辑：已知 bidder 后执行换手（或不换）。

    若 bidder 为 None → 无人抢，返回原手牌。
    若 bidder 非 None → ♦A 从原持有者移到 bidder 手中，每副手牌按 order 排序。

    返回:
        (bidder, updated_hands)
    """
    if bidder is None:
        return (None, hands)

    original_owner = find_diamond_a_holder(hands)

    # ── 换手：bidder 拿走 ♦A ──
    updated: list[list[Card]] = [list(h) for h in hands]

    # 从原持有者移除 ♦A
    updated[original_owner] = [
        c for c in updated[original_owner]
        if not (c.rank == 0 and c.suit == 0)
    ]
    # bidder 获得 ♦A
    updated[bidder].append(Card(0, 0))

    # 换手后每副手牌按 order 排序
    for hand in updated:
        hand.sort(key=lambda c: c.order)

    return (bidder, updated)


def take_bid(hands: list[list[Card]], num_players: int = 5) -> tuple[int | None, list[list[Card]]]:
    """
    抢A CLI轮询（交互式）。

    从 ♦A 持有者开始顺时针轮询，每个玩家输入 y/n。
    首个 y 成为 bidder，停止轮询；无人抢 → 返回 (None, 原手牌)。

    返回:
        (bidder, updated_hands)
        bidder 是抢到A的玩家在原顺序中的索引；
        updated_hands 保持原顺序不重排，仅交换 ♦A。

    输入容错：大写Y/小写y 均视为抢。
    """
    original_owner = find_diamond_a_holder(hands)

    # ── 顺时针轮询 ──
    bidder: int | None = None
    for offset in range(num_players):
        player = (original_owner + offset) % num_players
        ans = input(f"玩家{player} 是否抢A？(y/n): ").strip().lower()
        if ans == "y":
            bidder = player
            break

    return take_bid_logic(hands, bidder)
