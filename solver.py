"""夺A快跑 — 核心求解器与局面分析"""

from functools import lru_cache
from models import GameState, Trick, Move, _TYPE_CN, format_cards
from moves import get_legal_moves_free, get_legal_moves_response, is_global_max, _ensure_move


def _apply_move(
    state: GameState, move: Move | tuple, player: int
) -> GameState:
    """
    应用一手出牌，返回新 GameState。

    move 兼容 Move 对象和原始 tuple：
      - 自由出牌: (new_mask, trick_type_str, rank, top_suit, [orders])  (5 元组)
      - 接力压制: (new_mask, trick_obj, [orders])                       (3 元组)
    """
    move = _ensure_move(move)
    masks = list(state.masks)
    new_mask = move.new_mask
    new_trick = move.trick if move.trick is not None else Trick(move.type, move.rank, move.top_suit)

    masks[player] = new_mask
    next_turn = (state.turn + 1) % 5

    # 无论自由出牌还是响应，出牌人都是当前的"牌权持有者"，
    # 一圈无人管时回到此人继续出（DPEC: "出牌人继续出"）。
    starter = player

    return GameState(tuple(masks), new_trick, next_turn, starter)


@lru_cache(maxsize=500000)
def solve(state: GameState) -> bool:
    """
    memoized DFS 求解器：判断 ★（玩家0）从当前状态是否必胜。

    终局: ★空→True，对手空→False
    ★回合: 存在一条路径通向 True → True
    对手回合: 所有路径都通向 True → True
    """
    if state.masks[0] == 0:
        return True
    for i in range(1, 5):
        if state.masks[i] == 0:
            return False

    if state.turn == 0:
        return _solve_star_turn(state)
    else:
        return _solve_opponent_turn(state)


def _solve_star_turn(state: GameState) -> bool:
    """★ 的回合一 存在任一种出牌通向 True 即返回 True"""
    mask = state.masks[0]
    next_player_mask = state.masks[(state.turn + 1) % 5]

    if state.trick is None:
        moves = get_legal_moves_free(mask, next_player_mask)
    else:
        moves = get_legal_moves_response(mask, state.trick, next_player_mask)

        if not moves:
            next_t = (state.turn + 1) % 5
            if next_t == state.starter:
                ns = GameState(state.masks, None, state.starter, state.starter)
            else:
                ns = GameState(state.masks, state.trick, next_t, state.starter)
            return solve(ns)

    for move in moves:
        ns = _apply_move(state, move, 0)
        if solve(ns):
            return True
    return False


def _solve_opponent_turn(state: GameState) -> bool:
    """对手回合 — 所有合法出牌都通向 True 才返回 True"""
    player = state.turn
    mask = state.masks[player]
    next_player_mask = state.masks[(player + 1) % 5]

    if state.trick is None:
        moves = get_legal_moves_free(mask, next_player_mask)
    else:
        moves = get_legal_moves_response(mask, state.trick, next_player_mask)

        if not moves:
            next_t = (state.turn + 1) % 5
            if next_t == state.starter:
                ns = GameState(state.masks, None, state.starter, state.starter)
            else:
                ns = GameState(state.masks, state.trick, next_t, state.starter)
            return solve(ns)

    for move in moves:
        ns = _apply_move(state, move, player)
        if not solve(ns):
            return False
    return True


# ── 局面分析 ──

def analyze_moves(state: GameState) -> tuple[bool | None, list, list]:
    """
    分析 ★（player 0）当前回合的所有合法出牌。

    返回:
        (overall_result, winning_moves, losing_moves)
        - overall_result: True（★必胜）/ False（★必败）/ None（非★回合）
        - winning_moves: 能让★走向必胜的出牌列表
        - losing_moves: 让★走向必败的出牌列表

    每个 move 元素为 [type_cn, cards_str, orders, raw_move_tuple]
    """
    if state.turn != 0:
        return (None, [], [])

    mask = state.masks[0]
    next_player_mask = state.masks[(state.turn + 1) % 5]

    if state.trick is None:
        moves = get_legal_moves_free(mask, next_player_mask)
    else:
        moves = get_legal_moves_response(mask, state.trick, next_player_mask)

    winning_moves: list = []
    losing_moves: list = []

    for move in moves:
        ns = _apply_move(state, move, 0)
        result = solve(ns)

        # 提取 move 信息（Move 对象统一通过属性访问）
        ttype = move.type
        orders = move.orders

        type_cn = _TYPE_CN.get(ttype, ttype)
        cards_str = format_cards(orders)
        move_info = [type_cn, cards_str, orders, move]

        if result:
            winning_moves.append(move_info)
        else:
            losing_moves.append(move_info)

    overall = len(winning_moves) > 0
    return (overall, winning_moves, losing_moves)


# ── 状态推进 ──

def advance_turn(state: GameState) -> GameState:
    """
    处理"不能管"的情况：当前玩家无法出牌，turn 移到下家。
    如果转回出牌人 → trick 设为 None，出牌人继续出。
    """
    next_turn = (state.turn + 1) % 5
    if next_turn == state.starter:
        return GameState(state.masks, None, state.starter, state.starter)
    else:
        return GameState(state.masks, state.trick, next_turn, state.starter)


def check_terminal(state: GameState) -> tuple[int | None, bool]:
    """
    检查终局：有人手牌为空 → 返回 (winner, True)。
    winner 为第一个手牌为空的玩家索引（0=★, 1~4=对手）。
    否则返回 (None, False)。
    """
    for i in range(5):
        if state.masks[i] == 0:
            return (i, True)
    return (None, False)
