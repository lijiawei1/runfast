"""夺A快跑 — 游戏规则引擎

抽取 app.py / cli.py 中重复的游戏规则逻辑，提供纯函数（无 IO）。
"""

from models import GameState, Move, _TYPE_CN, format_cards
from moves import get_legal_moves_free, get_legal_moves_response, is_global_max
from solver import solve, _apply_move


def get_valid_moves_for_player(
    state: GameState, player: int
) -> list[Move]:
    """获取指定玩家的所有合法出牌（综合自由/响应出牌）。

    Args:
        state: 当前游戏状态
        player: 玩家索引 (0=★, 1~4=对手)

    Returns:
        list[Move]: 合法出牌列表
    """
    mask = state.masks[player]
    next_player_mask = state.masks[(player + 1) % state.num_players]

    if state.trick is None:
        return get_legal_moves_free(mask, next_player_mask)
    else:
        return get_legal_moves_response(mask, state.trick, next_player_mask)


def get_opponent_best_move(
    state: GameState, player: int
) -> Move | None:
    """对手最优出牌（最恶毒策略）：优先选让★输的 move。

    遍历所有合法出牌，找到第一个使 solve() 返回 False 的 move；
    若所有 move 都让★赢，则返回第一个 move。

    Args:
        state: 当前游戏状态
        player: 对手玩家索引 (1~4)

    Returns:
        Move | None: 最优出牌；无合法出牌返回 None
    """
    moves = get_valid_moves_for_player(state, player)
    if not moves:
        return None

    for move in moves:
        ns = _apply_move(state, move, player)
        if not solve(ns):  # ★ 会输的 move
            return move

    return moves[0]  # 所有 move 都让★赢，取第一个


def apply_move_with_global_max(
    state: GameState, move: Move, player: int
) -> GameState:
    """应用一手出牌，若为全局最大则自动接管（trick 清空，该玩家继续出）。

    Args:
        state: 当前游戏状态
        move: 要应用的出牌
        player: 出牌人索引

    Returns:
        GameState: 出牌后的新状态（可能已被全局最大接管）
    """
    ns = _apply_move(state, move, player)
    if is_global_max(move, state.masks):
        ns = GameState(ns.masks, None, player, player)
    return ns


def first_play_requires_da(state: GameState, player: int = 0) -> bool:
    """判断玩家当前是否为首出且手中有♦A（必须包含♦A出牌）。

    Args:
        state: 当前游戏状态
        player: 玩家索引（默认 0，即★）

    Returns:
        bool: True 表示首出必须包含 ♦A (order=0)
    """
    return (
        state.trick is None
        and (state.masks[player] & 1) != 0
    )
