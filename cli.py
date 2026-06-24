"""夺A快跑 — CLI 交互层与强制执行机制（纯 IO 层）"""

from models import Card, GameState, Trick, _TYPE_CN, format_cards, _format_hand
from moves import get_max_single, is_global_max
from solver import _apply_move, analyze_moves, advance_turn
from game_engine import (
    get_valid_moves_for_player,
    get_opponent_best_move,
    apply_move_with_global_max,
    first_play_requires_da,
)
from log_engine import (
    log_section,
    log_star_move,
    log_opponent_move,
    log_pass,
    log_analysis,
    log_moves_list,
    log_event,
    log_global_max,
    print_box_bottom,
    print_box_line,
    print_box_sep,
    print_box_top,
    print_section_star,
    print_section_opponent,
)


def apply_move(state: GameState, move: tuple, player: int) -> GameState:
    """公开版本的 _apply_move，供外部调用。"""
    return _apply_move(state, move, player)


# ── 抢A玩家选择（优化1：跳过轮询）──


def select_bidder(hands: list[list], num_players: int = 5) -> int:
    """显示所有玩家手牌（明牌），让用户直接选择抢A玩家序号。

    替代原有的 take_bid() 轮询方式，一次输入确定★。
    """
    # ── 框内显示 ──
    print()
    print_box_top()
    print_box_line("抢A玩家选择", align="center")
    print_box_sep()

    for i, hand in enumerate(hands):
        cards_str = ", ".join(str(c) for c in sorted(hand, key=lambda c: c.order))
        print_box_line(f"  玩家{i}: [{cards_str}]")

    print_box_line()
    # 输入循环
    while True:
        try:
            inp = input(
                f"  请输入抢A玩家序号 (0~{num_players - 1}): "
            ).strip()
            idx = int(inp)
            if 0 <= idx < num_players:
                print_box_line(f"  ★ 玩家{idx} 抢到A！")
                print_box_bottom()
                return idx
            print(f"  ❌ 序号超出范围 (0~{num_players - 1})，"
                  f"请重新输入。")
        except ValueError:
            print("  ❌ 请输入有效数字。")

    # unreachable
    return 0


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

    # 获取合法出牌
    moves = get_valid_moves_for_player(state, player)

    # 处理无法出牌的情况（Pass）
    if not moves:
        remaining = _format_hand(state.masks[player])
        label = "★" if player == 0 else f"玩家{player}"
        log_pass(player, label, f"[{remaining}]")
        return advance_turn(state)

    # ★的回合
    if player == 0:
        return _play_star_turn(state, moves)
    else:
        return _play_opponent_turn(state, player)


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
        ttype = move.type
        orders = move.orders

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

    # ── 局面分析（框内）──
    star_cards: list[Card] = []
    max_bit = state.masks[0].bit_length()
    for order in range(max_bit):
        if state.masks[0] & (1 << order):
            star_cards.append(Card(order // 4, order % 4))
    hand_str = f"[{', '.join(str(c) for c in star_cards)}]"
    trick_str = str(state.trick) if state.trick else "无（首出）"

    # ── 打印 ★ 回合框 ──
    print_section_star()
    emoji = "✅" if overall_result else "❌"
    result = "★必胜" if overall_result else "★必败"
    print_box_line(f"  📊 局面：{emoji} {result}")
    print_box_line(f"  ★ 手牌：{hand_str}")
    print_box_line(f"  桌上：{trick_str}")

    # ── 判断是否为首出（trick=None 且 ♦A 仍在手）──
    requires_da = first_play_requires_da(state)

    # 构建胜/败集合（复用 analyze_moves 结果，避免重复 solve）
    winning_set = {tuple(sorted(wm[2])) for wm in winning_moves_info}
    losing_set = {tuple(sorted(lm[2])) for lm in losing_moves_info}

    # 构建可选出牌列表
    display = _build_moves_display(moves, winning_set, losing_set)
    move_entries: list[tuple[bool, str, str, str]] = []
    for label, type_cn, cards_str, orders, _ in display:
        order_tag = ", ".join(str(o) for o in orders)
        is_win = label == "✅"
        move_entries.append((is_win, type_cn, cards_str, order_tag))

    # 可选出牌列表（框内）
    print_box_line()
    print_box_line("  📋 可选出牌：")
    for is_win, type_cn, cards_str, orders_str in move_entries:
        mark = "✅" if is_win else "❌"
        print_box_line(f"     {mark} {type_cn}: {cards_str}  [{orders_str}]")
    print_box_bottom()

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
        if requires_da and 0 not in input_orders:
            print("❌ 首出必须包含 ♦A（order=0），请重新选择。")
            continue

        # 查找匹配的出牌
        input_set = set(input_orders)
        for label, type_cn, cards_str, orders, move in display:
            if set(orders) == input_set:
                ns = apply_move_with_global_max(state, move, 0)
                gm = is_global_max(move, state.masks)
                remaining = _format_hand(ns.masks[0])
                log_star_move(f"[{remaining}]", f"{cards_str}（{type_cn}）",
                              global_max=gm)
                return ns

        # 未找到 ── 检查是否被"下家只剩一张牌"约束过滤
        star_mask = state.masks[0]
        next_p_mask = state.masks[(state.turn + 1) % state.num_players]
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


def _play_opponent_turn(state: GameState, player: int) -> GameState:
    """对手回合：选最恶毒的出牌（让★输的move）"""
    best_move = get_opponent_best_move(state, player)
    if best_move is None:
        remaining = _format_hand(state.masks[player])
        log_pass(player, f"玩家{player}", f"[{remaining}]")
        return advance_turn(state)

    ttype = best_move.type
    orders = best_move.orders
    type_cn = _TYPE_CN.get(ttype, ttype)
    cards_str = format_cards(orders)

    ns = apply_move_with_global_max(state, best_move, player)
    gm = is_global_max(best_move, state.masks)
    remaining = _format_hand(ns.masks[player])

    # ── 对手回合框 ──
    print_section_opponent()
    print_box_line(f"  🤖 玩家{player} 出: {cards_str}（{type_cn}）")
    print_box_line(f"    剩余: [{remaining}]")
    if gm:
        print_box_line(f"  🎯 全局最大！直接继续出牌")
    print_box_bottom()

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

    # 提取 move 信息用于打印（Move 对象统一通过属性访问）
    ttype = forced_move.type
    orders = forced_move.orders
    type_cn = _TYPE_CN.get(ttype, ttype)
    cards_str = format_cards(orders)

    # 应用出牌（含全局最大接管）
    ns = apply_move_with_global_max(state, forced_move, player)
    gm = is_global_max(forced_move, state.masks)
    remaining = _format_hand(ns.masks[player])

    # ── 对手回合（强制执行）框 ──
    print_section_opponent(is_forced=True)
    print_box_line(f"  🤖 玩家{player} 出: {cards_str}（{type_cn}）")
    print_box_line(f"    剩余: [{remaining}]")
    if gm:
        print_box_line(f"  🎯 全局最大！直接继续出牌")
    print_box_bottom()

    return ns
