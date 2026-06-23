"""夺A快跑 — 牌型识别、合法出牌枚举器、全局最大判断"""

from itertools import combinations
from models import Card, Trick, Move


def get_counts(hand: list[Card]) -> dict[int, int]:
    """返回 {rank: count} 字典"""
    counts: dict[int, int] = {}
    for c in hand:
        counts[c.rank] = counts.get(c.rank, 0) + 1
    return counts


def _top_suit(hand: list[Card], rank: int) -> int:
    """返回 hand 中指定 rank 的最大 suit"""
    return max(c.suit for c in hand if c.rank == rank)


def find_pairs(hand: list[Card]) -> list[tuple[int, int]]:
    """返回 [(rank, top_suit), ...]，按 rank 排序"""
    counts = get_counts(hand)
    result = [(r, _top_suit(hand, r)) for r, cnt in counts.items() if cnt == 2]
    result.sort(key=lambda x: x[0])
    return result


def find_triples(hand: list[Card]) -> list[tuple[int, int]]:
    """返回 [(rank, top_suit), ...]，按 rank 排序"""
    counts = get_counts(hand)
    result = [(r, _top_suit(hand, r)) for r, cnt in counts.items() if cnt == 3]
    result.sort(key=lambda x: x[0])
    return result


def find_quads(hand: list[Card]) -> list[tuple[int, int]]:
    """返回 [(rank, top_suit), ...]，按 rank 排序"""
    counts = get_counts(hand)
    result = [(r, _top_suit(hand, r)) for r, cnt in counts.items() if cnt == 4]
    result.sort(key=lambda x: x[0])
    return result


# ── 合法出牌枚举器 ──


def get_all_cards(mask: int) -> list[int]:
    """从 bitmask 里提取所有牌的 order 值"""
    result: list[int] = []
    for order in range(25):
        if mask & (1 << order):
            result.append(order)
    return result


def _mask_to_cards(mask: int) -> list[Card]:
    """将 bitmask 转换为 Card 列表"""
    cards: list[Card] = []
    for order in range(25):
        if mask & (1 << order):
            rank = order // 4
            suit = order % 4
            cards.append(Card(rank, suit))
    return cards


def _combos_of_rank(cards_r: list[Card], k: int) -> list[tuple[list[int], int]]:
    """对同一 rank 的牌，枚举所有 k 张组合。
    返回 [(order_list, top_suit), ...]，top_suit 为该组合中最大花色"""
    result: list[tuple[list[int], int]] = []
    for combo in combinations(cards_r, k):
        orders = [c.order for c in combo]
        top_suit = max(c.suit for c in combo)
        result.append((orders, top_suit))
    return result


def get_max_single(mask: int) -> int | None:
    """
    返回手牌 mask 中最大单张的 order 值（globalOrder 最大）。

    输入: 手牌 mask
    输出: 最大单张的 order 值，mask为空则返回 None
    """
    if mask == 0:
        return None
    # 最高位即最大 order
    return mask.bit_length() - 1


def get_legal_moves_free(
    mask: int, next_player_mask: int | None = None
) -> list[Move]:
    """
    自由出牌枚举器（trick 为空时，玩家可以任意出合法牌型）。

    返回: list[Move]（自由出牌 5-tuple 格式）
    """
    cards = _mask_to_cards(mask)

    # 按 rank 分组
    rank_cards: dict[int, list[Card]] = {}
    for c in cards:
        r = c.rank
        if r not in rank_cards:
            rank_cards[r] = []
        rank_cards[r].append(c)

    moves: list[Move] = []

    for rank, cards_r in rank_cards.items():
        cnt = len(cards_r)

        # 单张
        for c in cards_r:
            new_mask = mask & ~(1 << c.order)
            moves.append(Move.from_free(new_mask, "single", rank, c.suit, [c.order]))

        # 对子
        if cnt >= 2:
            for orders, ts in _combos_of_rank(cards_r, 2):
                new_mask = mask
                for o in orders:
                    new_mask &= ~(1 << o)
                moves.append(Move.from_free(new_mask, "pair", rank, ts, orders))

        # 三条
        if cnt >= 3:
            for orders, ts in _combos_of_rank(cards_r, 3):
                new_mask = mask
                for o in orders:
                    new_mask &= ~(1 << o)
                moves.append(Move.from_free(new_mask, "triple", rank, ts, orders))

        # 四条
        if cnt >= 4:
            for orders, ts in _combos_of_rank(cards_r, 4):
                new_mask = mask
                for o in orders:
                    new_mask &= ~(1 << o)
                moves.append(Move.from_free(new_mask, "quad", rank, ts, orders))

    # ── 下家只剩一张牌约束 ──
    if next_player_mask is not None and next_player_mask.bit_count() == 1:
        singles = [m for m in moves if m.type == "single"]
        non_singles = [m for m in moves if m.type != "single"]
        if singles:
            max_order = get_max_single(mask)
            singles = [m for m in singles if m.orders[0] == max_order]
        moves = non_singles + singles

    return moves


_TRICK_SIZE = {"single": 1, "pair": 2, "triple": 3, "quad": 4}


def get_legal_moves_response(
    mask: int, trick: Trick, next_player_mask: int | None = None
) -> list[Move]:
    """
    接力压制枚举器（trick 不为空时，只能出同牌型且更大的牌）。

    返回: list[Move]（接力压制 3-tuple 格式）

    规则: 必须同牌型；先比 rank 再比 top_suit；无可管牌返回空列表。
    """
    cards = _mask_to_cards(mask)
    if not cards:
        return []

    counts = get_counts(cards)

    rank_cards: dict[int, list[Card]] = {}
    for c in cards:
        r = c.rank
        if r not in rank_cards:
            rank_cards[r] = []
        rank_cards[r].append(c)

    ttype = trick.type
    k = _TRICK_SIZE[ttype]
    moves: list[Move] = []

    # 单张
    if ttype == "single":
        for rank, cards_r in rank_cards.items():
            if rank < trick.rank:
                continue
            for c in cards_r:
                if rank > trick.rank or c.suit > trick.top_suit:
                    new_mask = mask & ~(1 << c.order)
                    new_trick = Trick("single", rank, c.suit)
                    moves.append(Move.from_response(new_mask, new_trick, [c.order]))

        # ── 下家只剩一张牌约束 ──
        if next_player_mask is not None and next_player_mask.bit_count() == 1 and moves:
            max_order = get_max_single(mask)
            moves = [m for m in moves if m.orders[0] == max_order]

        return moves

    # 对子 / 三条 / 四条
    for rank, cards_r in rank_cards.items():
        cnt = len(cards_r)
        if cnt < k:
            continue
        if rank < trick.rank:
            continue

        for orders, ts in _combos_of_rank(cards_r, k):
            if rank > trick.rank:
                new_mask = mask
                for o in orders:
                    new_mask &= ~(1 << o)
                new_trick = Trick(ttype, rank, ts)
                moves.append(Move.from_response(new_mask, new_trick, orders))
            elif rank == trick.rank and ts > trick.top_suit:
                new_mask = mask
                for o in orders:
                    new_mask &= ~(1 << o)
                new_trick = Trick(ttype, rank, ts)
                moves.append(Move.from_response(new_mask, new_trick, orders))

    # 非单张牌型不受下家只剩一张牌约束
    return moves


# ── 全局最大判断 ──


def _ensure_move(move: Move | tuple) -> Move:
    """将原始 tuple 转换为 Move 对象（向后兼容辅助函数）。

    处理两种格式：
      - 自由出牌 (5-tuple):  (new_mask, type_str, rank, top_suit, [orders])
      - 接力压制 (3-tuple):  (new_mask, trick_obj, [orders])
    """
    if isinstance(move, Move):
        return move
    if len(move) == 5:
        return Move.from_free(move[0], move[1], move[2], move[3], move[4])
    return Move.from_response(move[0], move[1], move[2])


def is_global_max(move: Move | tuple, all_masks: tuple[int, ...]) -> bool:
    """
    判断一手出牌是否为该牌型的全局唯一最大。

    输入:
        move: Move 对象或原始 tuple（向后兼容），支持两种格式：
              - 自由出牌: (new_mask, type_str, rank, top_suit, [orders])  (5-tuple)
              - 接力压制: (new_mask, trick_obj, [orders])                 (3-tuple)
        all_masks: 所有玩家的手牌 mask（含出牌人自己的 mask）

    返回: True 表示这是全局最大且唯一（直接接管）；False 则正常轮询。
    """
    move = _ensure_move(move)
    ttype = move.type
    rank = move.rank
    top_suit = move.top_suit
    orders = move.orders

    # ── 单张：比 order ──
    if ttype == "single":
        order = orders[0]
        for mask in all_masks:
            if mask == 0:
                continue
            if mask.bit_length() - 1 > order:
                return False
        return True

    # ── 对子 / 三条 / 四条：比 (rank, top_suit) ──
    k = _TRICK_SIZE[ttype]
    global_max_rank = -1
    global_max_suit = -1
    max_player_count = 0

    for mask in all_masks:
        if mask == 0:
            continue
        cards = _mask_to_cards(mask)
        counts: dict[int, int] = {}
        for c in cards:
            counts[c.rank] = counts.get(c.rank, 0) + 1

        for r, cnt in counts.items():
            if cnt < k:
                continue
            r_top_suit = max(c.suit for c in cards if c.rank == r)

            if r > global_max_rank or (r == global_max_rank and r_top_suit > global_max_suit):
                global_max_rank = r
                global_max_suit = r_top_suit
                max_player_count = 1
            elif r == global_max_rank and r_top_suit == global_max_suit:
                max_player_count += 1

    # 检查 move 是否匹配全局最大
    if rank < global_max_rank:
        return False
    if rank == global_max_rank and top_suit < global_max_suit:
        return False

    # 唯一性：不能有多个玩家拥有相同的最大牌型
    if max_player_count > 1:
        return False

    return True
