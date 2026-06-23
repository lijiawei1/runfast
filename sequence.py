"""夺A快跑 — 同盟必胜序列分析与最优应对"""

from models import GameState, Trick, _TYPE_CN, format_cards
from moves import get_legal_moves_free, get_legal_moves_response, is_global_max
from solver import solve, _apply_move


# ── 同盟必胜序列 ──

_MAX_SEQ_DEPTH = 200


def find_winning_sequence(state: GameState) -> list | None:
    """
    搜索一条同盟必胜序列（★无论怎么出都输）。

    输入: GameState（初始状态，如抢A后 turn=bidder, trick=None）
    输出:
        - 若存在同盟必胜序列：返回 List[Action]，每个 Action 是 (player_index, move) 元组
        - 若不存在（★必胜）：返回 None

    实现逻辑（DFS 沿"让 ★ 输"分支搜索）：
        1. 调用 solve(state)，若返回 True（★必胜）→ 返回 None
        2. 否则从当前状态 DFS：
           - ★ 回合：所有合法出牌都通向必败，任选一个记录并递归
           - 对手回合：选一个让 ★ 继续输的 move，记录并递归
        3. 找到第一条完整路径（★最终失败）即可返回
    """
    # 先检查 ★ 是否必胜
    if solve(state):
        return None

    # ★ 处于必败状态，搜索一条通向 ★ 失败的路径
    seq = _dfs_win_seq(state)
    if seq is None:
        # 安全网：DFS 未能完成（深度超限等极端情况），降级返回 None
        return None
    return seq


def _dfs_win_seq(state: GameState, depth: int = 0) -> list | None:
    """
    DFS 辅助函数：沿"让 ★ 输"分支搜索第一条完整路径。

    返回:
        - [(player, move), ...] 序列，到达对手先出完牌时返回空列表
        - None：未能找到完整路径（边界情况或异常）

    安全机制: depth 参数防止极端情况下的无限递归。
    """
    # ── 递归深度保护 ──
    if depth > _MAX_SEQ_DEPTH:
        return None

    # ── 终局检查 ──
    if state.masks[0] == 0:
        return []  # ★ 手牌为空，★ 赢了（不应在 solve=False 时到达）
    for i in range(1, state.num_players):
        if state.masks[i] == 0:
            return []  # 对手先出完，★ 输了 → 路径结束

    n = state.num_players
    player = state.turn
    mask = state.masks[player]
    next_player_mask = state.masks[(player + 1) % n]

    # 获取合法出牌
    if state.trick is None:
        moves = get_legal_moves_free(mask, next_player_mask)
    else:
        moves = get_legal_moves_response(mask, state.trick, next_player_mask)

    # 无合法出牌 → Pass（不记录到序列中，只推进状态）
    if not moves:
        next_t = (state.turn + 1) % n
        if next_t == state.starter:
            ns = GameState(state.masks, None, state.starter, state.starter)
        else:
            ns = GameState(state.masks, state.trick, next_t, state.starter)
        return _dfs_win_seq(ns, depth + 1)

    if player == 0:
        # ★ 的回合：solve(state)==False 保证所有合法出牌都通向必败
        # 任选一个记录即可
        move = moves[0]
        ns = _apply_move(state, move, 0)
        # 全局最大接管：trick 清空，turn 保持在 0
        if is_global_max(move, state.masks):
            ns = GameState(ns.masks, None, 0, 0)
        tail = _dfs_win_seq(ns, depth + 1)
        if tail is None:
            return None  # 子路径断裂
        return [(0, move)] + tail
    else:
        # 对手回合：选一个让 ★ 继续输的 move（最恶毒路径）
        for move in moves:
            ns = _apply_move(state, move, player)
            actual_ns = ns
            if is_global_max(move, state.masks):
                actual_ns = GameState(ns.masks, None, player, player)
            if not solve(actual_ns):  # ★ 仍然必败
                tail = _dfs_win_seq(actual_ns, depth + 1)
                if tail is not None:
                    return [(player, move)] + tail
        # 所有路径都无法完成（边界情况：该状态下对手无必胜路径）
        return None


def format_sequence(seq: list) -> str:
    """
    将 List[Action] 转换为可读字符串。

    格式示例：
        ⚠️ 当前局面同盟有必胜策略！
        必胜序列（示例）：
        玩家1 → 出 ♣A（单张）
        玩家2 → 出 ♥A（单张）
        ★ 最终无法出牌/最后出完
    """
    if seq is None:
        return "✅ ★ 必胜，同盟无必胜序列。"

    if not seq:
        return "⚠️ 当前局面同盟有必胜策略！\n（★ 已无路可退，对手将直接出完）"

    lines = ["⚠️ 当前局面同盟有必胜策略！", "必胜序列（示例）："]

    for player, move in seq:
        ttype = move.type
        orders = move.orders
        type_cn = _TYPE_CN.get(ttype, ttype)
        cards_str = format_cards(orders)

        if player == 0:
            lines.append(f"★ → 出 {cards_str}（{type_cn}）")
        else:
            lines.append(f"玩家{player} → 出 {cards_str}（{type_cn}）")

    lines.append("★ 最终无法出牌/最后出完")
    return "\n".join(lines)


# ── 多♦A出牌分支验证 ──


def enumerate_da_moves(mask: int) -> list[tuple]:
    """
    枚举★手牌中所有包含♦A（order=0）的合法出牌。

    输入: ★的手牌mask（25-bit）
    输出: List[move]，每个move是合法出牌元组（兼容自由出牌的5-tuple格式）

    实现逻辑:
    1. 调用 get_legal_moves_free(mask) 获取所有合法出牌
    2. 筛选出包含 order=0（♦A）的move
    3. 返回筛选后的列表

    注意:
    - 不修改 get_legal_moves_free，只做筛选
    - 返回的move格式必须与 get_legal_moves_free 一致（5-tuple）
    """
    all_moves = get_legal_moves_free(mask)
    da_moves = [m for m in all_moves if 0 in m.orders]
    return da_moves


def verify_all_da_moves(state: GameState) -> dict[str, list | None]:
    """
    验证★的每一种含♦A出牌，同盟是否都有必胜序列。

    输入: GameState（初始状态，turn=0，trick=None）
    输出: Dict[str, List[Action]|None]
        - key：出牌描述字符串，如 "单张: ♦A"、"对子: ♦A ♣A"
        - value：同盟必胜序列（List[Action]）或 None（无必胜序列）

    实现逻辑:
    1. 调用 enumerate_da_moves(state.masks[0]) 获取所有含♦A出牌
    2. 对每种出牌：
        - 应用出牌得到新状态 ns = _apply_move(state, move, 0)
        - 处理全局最大接管（如果适用）
        - 调用 find_winning_sequence(ns) 获取同盟必胜序列
        - 记录结果
    3. 返回字典
    """
    result: dict[str, list | None] = {}
    star_mask = state.masks[0]
    da_moves = enumerate_da_moves(star_mask)

    for move in da_moves:
        # 构建描述 key
        ttype = move.type
        orders = move.orders
        type_cn = _TYPE_CN.get(ttype, ttype)
        cards_str = format_cards(orders)
        desc = f"{type_cn}: {cards_str}"

        # 应用出牌
        ns = _apply_move(state, move, 0)
        # 处理全局最大接管
        if is_global_max(move, state.masks):
            ns = GameState(ns.masks, None, 0, 0)

        # 查找同盟必胜序列
        seq = find_winning_sequence(ns)
        result[desc] = seq

    return result


def _format_sequence_body(seq: list) -> str:
    """格式化同盟必胜序列的主体（不含头部/尾部标题），供多分支展示使用。"""
    if not seq:
        return "（★ 已无路可退，对手将直接出完）"

    lines: list[str] = []
    for player, move in seq:
        ttype = move.type
        orders = move.orders
        type_cn = _TYPE_CN.get(ttype, ttype)
        cards_str = format_cards(orders)

        if player == 0:
            lines.append(f"★ → 出 {cards_str}（{type_cn}）")
        else:
            lines.append(f"玩家{player} → 出 {cards_str}（{type_cn}）")

    lines.append("★ 最终无法出牌/最后出完")
    return "\n".join(lines)


def format_multi_da_verification(result_dict: dict[str, list | None]) -> str:
    """
    将多分支验证结果格式化为可读字符串。

    输入: verify_all_da_moves 返回的字典
    输出: 格式化字符串

    输出格式（同盟全有必胜序列时）:
        ⚠️ 当前局面同盟有必胜策略！
        ★ 可选择以下含♦A出牌，同盟均有必胜应对：
        【出法1】单张: ♦A
        同盟必胜序列：...

    输出格式（存在★胜招时）:
        ⚠️ ★ 有胜招！
        【出法1】单张: ♦A → 同盟必胜 ✅
        【出法2】对子: ♦A ♣A → 同盟无必胜序列 ❌
        建议：出对子 ♦A ♣A 可破局！
    """
    has_star_winning = any(seq is None for seq in result_dict.values())
    lines: list[str] = []

    if has_star_winning:
        lines.append("⚠️ ★ 有胜招！")
        lines.append("")
        winning_moves: list[str] = []
        for i, (desc, seq) in enumerate(result_dict.items(), 1):
            if seq is None:
                lines.append(f"【出法{i}】{desc} → 同盟无必胜序列 ❌")
                winning_moves.append(desc)
            else:
                lines.append(f"【出法{i}】{desc} → 同盟必胜 ✅")
        if winning_moves:
            lines.append("")
            lines.append(f"建议：出 {winning_moves[0]} 可破局！")
    else:
        lines.append("⚠️ 当前局面同盟有必胜策略！")
        lines.append("")
        lines.append("★ 可选择以下含♦A出牌，同盟均有必胜应对：")
        lines.append("")
        for i, (desc, seq) in enumerate(result_dict.items(), 1):
            lines.append(f"【出法{i}】{desc}")
            if seq is not None:
                body = _format_sequence_body(seq)
                lines.append("同盟必胜序列：")
                for line in body.split("\n"):
                    lines.append("  " + line)
            lines.append("")

    return "\n".join(lines)


# ── 同盟最优应对 ──


def find_best_response(state: GameState) -> list:
    """
    在★出牌后，搜索同盟的最优应对序列（最恶毒路径）。

    输入: GameState（★已出牌后的状态）
    输出:
        - 若同盟有必胜策略：返回 list[Action]，每条 Action 是 (player_index, move) 元组
        - 若★必胜：返回空列表 []

    实现逻辑（复用 solve 和合法出牌枚举器）：
        1. 调用 solve(state)，若返回 True（★必胜）→ 返回 []
        2. 否则沿"让★输"的分支 DFS，复用 _dfs_win_seq
        3. 找到第一条完整路径（★失败）即可返回
    """
    if solve(state):
        return []
    seq = _dfs_win_seq(state)
    if seq is None:
        # 安全网：DFS 未能完成，降级返回空列表
        return []
    return seq


def format_best_response(seq: list) -> str:
    """
    将同盟最优应对序列格式化为可读文本。

    格式示例：
        ⚠️ 同盟有最优应对策略！
        最优应对序列：
        玩家1 → 出 ♣A（单张）
        ★ 最终失败！
    """
    if not seq:
        return "✅ ★ 必胜，同盟无应对策略。"

    lines = ["⚠️ 同盟有最优应对策略！", "同盟最优应对序列："]

    for player, move in seq:
        ttype = move.type
        orders = move.orders
        type_cn = _TYPE_CN.get(ttype, ttype)
        cards_str = format_cards(orders)

        if player == 0:
            lines.append(f"★ → 出 {cards_str}（{type_cn}）")
        else:
            lines.append(f"玩家{player} → 出 {cards_str}（{type_cn}）")

    lines.append("★ 最终失败！")
    return "\n".join(lines)
