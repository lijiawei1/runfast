"""夺A快跑 — CLI 交互层与强制执行机制"""

from models import Card, GameState, Trick, _TYPE_CN, format_cards, _format_hand
from moves import get_legal_moves_free, get_legal_moves_response, is_global_max, get_max_single
from solver import solve, _apply_move, analyze_moves, advance_turn


def apply_move(state: GameState, move: tuple, player: int) -> GameState:
    """公开版本的 _apply_move，供外部调用。"""
    return _apply_move(state, move, player)


# ── 回合调度 ──


def play_turn(state: GameState) -> GameState:
    """
    处理一个玩家的回合。

    ★的回合（turn == 0）：
        - 显示局面分析
        - 列出所有合法出牌，标注胜招（✅）和败招（❌）
        - 让玩家输入要出的牌
        - 验证并应用

    对手回合（turn != 0）：
        - 枚举合法出牌
        - 选"最恶毒"的move
        - 打印对手出牌，应用并返回
    """
    player = state.turn
    mask = state.masks[player]
    next_player_mask = state.masks[(player + 1) % 5]

    # 获取合法出牌
    if state.trick is None:
        moves = get_legal_moves_free(mask, next_player_mask)
    else:
        moves = get_legal_moves_response(mask, state.trick, next_player_mask)

    # 处理无法出牌的情况（Pass）
    if not moves:
        remaining = _format_hand(mask)
        if player == 0:
            print(f"\n😔 ★ 无牌可出，选择不出(Pass)")
            print(f"★ 剩余手牌: [{remaining}]")
        else:
            print(f"\n👤 玩家{player} 选择不出(Pass)")
            print(f"玩家{player} 剩余手牌: [{remaining}]")
        return advance_turn(state)

    # ★的回合
    if player == 0:
        return _play_star_turn(state, moves)
    else:
        return _play_opponent_turn(state, moves, player)


# ── ★ 回合交互 ──


def _build_moves_display(
    moves: list,
    winning_set: set[tuple[int, ...]],
    losing_set: set[tuple[int, ...]],
) -> list[tuple[str, str, str, list[int], tuple]]:
    """
    构建带标注的出牌展示列表（接收预计算的胜/败集合）。
    返回: [(label, type_cn, cards_str, orders, raw_move), ...]
    label: "✅" 或 "❌"
    """
    display: list[tuple[str, str, str, list[int], tuple]] = []

    for move in moves:
        if len(move) == 5:
            _nm, ttype, _rank, _ts, orders = move
        else:
            _nm, trick_obj, orders = move
            ttype = trick_obj.type

        type_cn = _TYPE_CN.get(ttype, ttype)
        cards_str = format_cards(orders)
        orders_key = tuple(sorted(orders))

        if orders_key in winning_set:
            label = "✅"
        elif orders_key in losing_set:
            label = "❌"
        else:
            label = "  "

        display.append((label, type_cn, cards_str, orders, move))

    return display


def _play_star_turn(state: GameState, moves: list) -> GameState:
    """★的回合交互逻辑"""
    # 分析所有出牌
    overall_result, winning_moves_info, losing_moves_info = analyze_moves(state)

    # 打印局面
    tie_cn = "★必胜" if overall_result else "★必败"
    emoji = "✅" if overall_result else "❌"
    print(f"\n当前回合：★")
    print(f"📊 局面分析：{emoji} {tie_cn}")

    # 打印手牌
    star_cards: list[Card] = []
    for order in range(25):
        if state.masks[0] & (1 << order):
            star_cards.append(Card(order // 4, order % 4))
    print(f"> ★ 手牌：[{', '.join(str(c) for c in star_cards)}]")

    # 打印桌上
    if state.trick:
        print(f"桌上：{state.trick}")
    else:
        print("桌上：无（首出）")

    # ── 判断是否为首出（trick=None 且 ♦A 仍在手）──
    first_play_requires_da = (
        state.trick is None
        and (state.masks[0] & 1) != 0  # ♦A (order=0) 还在手
    )

    # 构建胜/败集合（复用 analyze_moves 结果，避免重复 solve）
    winning_set = {tuple(sorted(wm[2])) for wm in winning_moves_info}
    losing_set = {tuple(sorted(lm[2])) for lm in losing_moves_info}

    # 列出所有出牌（带 order 标注）
    print(f"\n> 可选出牌：")
    display = _build_moves_display(moves, winning_set, losing_set)
    for label, type_cn, cards_str, orders, _ in display:
        order_tag = ", ".join(str(o) for o in orders)
        print(f"  {label} {type_cn}: {cards_str}  [{order_tag}]")

    # 玩家输入循环
    while True:
        try:
            inp = input(
                "\n> 请输入要出的牌的order（如 \"0\" 或 \"0 1\"）："
            ).strip()
            if not inp:
                print("❌ 输入不能为空，请重新输入。")
                continue
            input_orders = [int(x) for x in inp.split()]
        except ValueError:
            print("❌ 请输入数字，用空格分隔。")
            continue

        # ── 首出 ♦A 验证 ──
        if first_play_requires_da and 0 not in input_orders:
            print("❌ 首出必须包含 ♦A（order=0），请重新选择。")
            continue

        # 查找匹配的出牌
        input_set = set(input_orders)
        for label, type_cn, cards_str, orders, move in display:
            if set(orders) == input_set:
                ns = _apply_move(state, move, 0)
                print(f"★ 出: {cards_str} ({type_cn})")
                if is_global_max(move, state.masks):
                    ns = GameState(ns.masks, None, 0, 0)  # 清空 trick，重新自由出牌
                    print("🎯 全局最大！直接继续出牌")
                remaining = _format_hand(ns.masks[0])
                print(f"★ 剩余手牌: [{remaining}]")
                return ns

        # 未找到 ── 检查是否被"下家只剩一张牌"约束过滤
        star_mask = state.masks[0]
        next_p_mask = state.masks[(state.turn + 1) % 5]
        constraint_active = (
            next_p_mask.bit_count() == 1
            and len(input_orders) == 1
            and (star_mask & (1 << input_orders[0])) != 0  # 牌确实在手
        )
        if constraint_active:
            max_order = get_max_single(star_mask)
            rejected_card = Card(input_orders[0] // 4, input_orders[0] % 4)
            print(f"❌ 无效出牌：因为下家只剩一张牌，你必须出最大的单张 {format_cards([max_order])}（而非 {rejected_card}），请重新选择。")
        else:
            print(f"❌ 无效出牌：{input_orders}，请重新输入。")
        print("  可用的 order 组合：")
        for label, type_cn, cards_str, orders, _ in display:
            print(f"    {orders}")


# ── 对手回合 ──


def _play_opponent_turn(
    state: GameState, moves: list, player: int
) -> GameState:
    """对手回合：选最恶毒的出牌（让★输的move）"""
    # 分析每种出牌，优先选让★输的
    best_move = None
    for move in moves:
        ns = _apply_move(state, move, player)
        result = solve(ns)
        if not result:  # ★输的move
            best_move = move
            break

    # 如果所有move都让★赢，选第一个
    if best_move is None:
        best_move = moves[0]

    # 格式化并打印
    if len(best_move) == 5:
        _nm, ttype, _rank, _ts, orders = best_move
    else:
        _nm, _trick_obj, orders = best_move
        ttype = _trick_obj.type

    type_cn = _TYPE_CN.get(ttype, ttype)
    cards_str = format_cards(orders)

    ns = _apply_move(state, best_move, player)
    print(f"\n👤 玩家{player} 出: {cards_str} ({type_cn})")
    if is_global_max(best_move, state.masks):
        ns = GameState(ns.masks, None, player, player)  # 清空 trick，重新自由出牌
        print("🎯 全局最大！直接继续出牌")
    remaining = _format_hand(ns.masks[player])
    print(f"玩家{player} 剩余手牌: [{remaining}]")

    return ns


# ── 强制执行机制（训练模式二）──


def execute_forced_move(state: GameState, forced_move: tuple) -> GameState:
    """强制玩家按指定的move出牌（用于训练模式二的强制执行）。

    输入：
        state：当前 GameState
        forced_move：预计算的出牌元组（兼容5-tuple和3-tuple）

    输出：应用出牌后的新 GameState

    实现逻辑：
        1. 获取当前玩家 player = state.turn
        2. 调用 _apply_move(state, forced_move, player) 应用出牌
        3. 处理全局最大接管（若 is_global_max 为 True）
        4. 打印出牌信息和剩余手牌
        5. 返回新状态
    """
    player = state.turn

    # 提取 move 信息用于打印
    if len(forced_move) == 5:
        _nm, ttype, _rank, _ts, orders = forced_move
    else:
        _nm, trick_obj, orders = forced_move
        ttype = trick_obj.type

    type_cn = _TYPE_CN.get(ttype, ttype)
    cards_str = format_cards(orders)

    # 应用出牌
    ns = _apply_move(state, forced_move, player)

    # 处理全局最大接管
    if is_global_max(forced_move, state.masks):
        ns = GameState(ns.masks, None, player, player)
        print(f"\n🤖 [强制] 玩家{player} 出: {cards_str} ({type_cn})")
        print("🎯 全局最大！直接继续出牌")
    else:
        print(f"\n🤖 [强制] 玩家{player} 出: {cards_str} ({type_cn})")

    remaining = _format_hand(ns.masks[player])
    print(f"玩家{player} 剩余手牌: [{remaining}]")

    return ns
