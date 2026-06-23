"""夺A快跑 — Streamlit 出牌交互组件

★ 出牌 UI、对手 AI 出牌、模式二强制执行、出牌链处理。
从 app.py 分离，减少主文件行数。
"""

import streamlit as st
from models import GameState, _TYPE_CN, format_cards
from moves import is_global_max, get_max_single
from solver import advance_turn, check_terminal, analyze_moves
from game_engine import (
    get_valid_moves_for_player,
    get_opponent_best_move,
    apply_move_with_global_max,
    first_play_requires_da,
)
from sequence import find_best_response

from app_render import format_hand_from_mask, render_hand


# ══════════════════════════════════════════════════════════════════════
# 内部辅助
# ══════════════════════════════════════════════════════════════════════

def _add_log(player: int, action: str, cards: str, remaining: str, note: str = ""):
    """添加操作日志（写入 st.session_state）"""
    st.session_state.log.append({
        "player": player,
        "label": "★" if player == 0 else f"玩家{player}",
        "action": action,
        "cards": cards,
        "remaining": remaining,
        "note": note,
    })


def _record_trick_entry(player_id: int, orders: list[int], type_cn: str):
    """向 trick_history 和 all_trick_history 追加一条出牌记录"""
    label = "★" if player_id == 0 else f"P{player_id}"
    entry = {
        "player_id": player_id,
        "label": label,
        "orders": sorted(orders),
        "type_cn": type_cn,
        "round": st.session_state.get("current_round", 1),
    }
    st.session_state.trick_history.append(entry)
    st.session_state.all_trick_history.append(entry)


def _start_new_round():
    """一轮结束 → 清空本轮历史、递增轮次编号"""
    st.session_state.trick_history = []
    st.session_state.current_round += 1


# ══════════════════════════════════════════════════════════════════════
# 对手出牌（模式一）
# ══════════════════════════════════════════════════════════════════════

def opponent_play(state: GameState) -> tuple[GameState, str]:
    """对手自动选择最恶毒出牌。返回 (新状态, 日志描述)"""
    player = state.turn

    best_move = get_opponent_best_move(state, player)
    if best_move is None:
        ns = advance_turn(state)
        log_str = f"玩家{player} Pass（无牌可出）"
        return ns, log_str

    ttype = best_move.type
    orders = best_move.orders
    type_cn = _TYPE_CN.get(ttype, ttype)
    cards_str = format_cards(orders)

    old_trick_existed = state.trick is not None

    ns = apply_move_with_global_max(state, best_move, player)
    gm = is_global_max(best_move, state.masks)

    if old_trick_existed and ns.trick is None:
        _start_new_round()

    _record_trick_entry(player, orders, type_cn)

    remaining = format_hand_from_mask(ns.masks[player])
    glob = " 🎯全局最大" if gm else ""
    log_str = f"玩家{player} 出 {cards_str}（{type_cn}）{glob}"

    _add_log(player, "出牌", cards_str, remaining, "全局最大接管" if gm else "")
    return ns, log_str


def execute_forced_move_web(
    state: GameState, forced_move: tuple
) -> tuple[GameState, str]:
    """强制执行指定 move。返回 (新状态, 日志描述)"""
    player = state.turn

    ttype = forced_move.type
    orders = forced_move.orders
    type_cn = _TYPE_CN.get(ttype, ttype)
    cards_str = format_cards(orders)

    old_trick_existed = state.trick is not None

    ns = apply_move_with_global_max(state, forced_move, player)
    gm = is_global_max(forced_move, state.masks)

    if old_trick_existed and ns.trick is None:
        _start_new_round()

    _record_trick_entry(player, orders, type_cn)

    remaining = format_hand_from_mask(ns.masks[player])
    glob = " 🎯全局最大" if gm else ""
    log_str = f"[强制] 玩家{player} 出 {cards_str}（{type_cn}）{glob}"

    _add_log(player, "强制出牌", cards_str, remaining, "全局最大接管" if gm else "")
    return ns, log_str


# ══════════════════════════════════════════════════════════════════════
# ★ 出牌逻辑
# ══════════════════════════════════════════════════════════════════════

def apply_star_move(state: GameState, move: tuple) -> tuple[GameState, str]:
    """★ 打出一手牌。返回 (新状态, 错误信息（空=成功）)"""
    ttype = move.type
    orders = move.orders
    cards_str = format_cards(orders)
    type_cn = _TYPE_CN.get(ttype, ttype)

    # 首出 ♦A 验证
    if first_play_requires_da(state) and 0 not in orders:
        return state, "首出必须包含 ♦A（order=0），请重新选择。"

    # 下家独张约束
    next_mask = state.masks[(state.turn + 1) % 5]
    star_mask = state.masks[0]
    if next_mask.bit_count() == 1 and len(orders) == 1:
        max_order = get_max_single(star_mask)
        if orders[0] != max_order:
            rejected_card = type("Card", (), {"__str__": lambda s: f"{'♦♣♥♠'[orders[0]%4]}{'A234567890JQK'[orders[0]//4]}"})()
            return state, (
                f"下家只剩一张牌，你必须出最大的单张 "
                f"{format_cards([max_order])}（而非 {rejected_card}）"
            )

    old_trick_existed = state.trick is not None

    ns = apply_move_with_global_max(state, move, 0)
    gm = is_global_max(move, state.masks)

    if old_trick_existed and ns.trick is None:
        _start_new_round()

    remaining = format_hand_from_mask(ns.masks[0])
    _add_log(0, "出牌", cards_str, remaining, "全局最大接管" if gm else "")

    return ns, ""


# ══════════════════════════════════════════════════════════════════════
# 对手出牌链
# ══════════════════════════════════════════════════════════════════════

def process_opponent_chain():
    """处理对手连续出牌链（全局最大接力）"""
    max_chain = 20
    count = 0
    while count < max_chain:
        state = st.session_state.state
        winner, game_over = check_terminal(state)
        if game_over or state.turn == 0:
            break
        new_state, _ = opponent_play(state)
        st.session_state.state = new_state
        count += 1
    if count >= max_chain:
        st.warning("对手出牌链过长，已截断")


def process_forced_chain():
    """处理强制执行链"""
    max_chain = 20
    count = 0
    while count < max_chain:
        state = st.session_state.state
        winner, game_over = check_terminal(state)
        if game_over or state.turn == 0:
            break

        player = state.turn
        seq = st.session_state.current_sequence
        forced_move = None
        for p, m in seq:
            if p == player:
                forced_move = m
                break

        if forced_move:
            new_state, _ = execute_forced_move_web(state, forced_move)
            st.session_state.state = new_state
            st.session_state.current_sequence = [
                (p, m) for p, m in st.session_state.current_sequence
                if not (p == player and m == forced_move)
            ]
        else:
            new_state, _ = opponent_play(state)
            st.session_state.state = new_state
        count += 1
    if count >= max_chain:
        st.warning("链条过长，已截断")


# ══════════════════════════════════════════════════════════════════════
# ★ 出牌 UI（模式一）
# ══════════════════════════════════════════════════════════════════════

def _toggle_card_order(order: int):
    """切换单张牌的选中状态"""
    selected = list(st.session_state.selected_orders)
    if order in selected:
        selected.remove(order)
    else:
        selected.append(order)
    st.session_state.selected_orders = selected
    st.rerun()


def execute_star_play(state: GameState, move: tuple):
    """执行★出牌 + 记录 trick_history + 对手链"""
    ttype = move.type
    orders = move.orders
    type_cn = _TYPE_CN.get(ttype, ttype)

    new_state, error = apply_star_move(state, move)
    if error:
        st.error(error)
        st.stop()

    st.session_state.state = new_state
    _record_trick_entry(0, orders, type_cn)
    st.session_state.selected_orders = []

    if st.session_state.mode == 2:
        _update_mode2_sequence(new_state)
    process_opponent_chain()


def render_star_play(state: GameState):
    """★ 出牌交互 — 欢乐斗地主式：点击手牌选牌 → 点出牌"""
    st.write("⭐ 你的回合，请选择出牌")

    overall, winning_moves_info, losing_moves_info = analyze_moves(state)

    all_moves = get_valid_moves_for_player(state, 0)

    if not all_moves:
        st.warning("无牌可出，将自动 Pass")
        if st.button("确认 Pass", key="pass_btn", type="primary", use_container_width=True):
            old_trick = state.trick
            ns = advance_turn(state)
            if old_trick is not None and ns.trick is None:
                _start_new_round()
            st.session_state.state = ns
            remaining = format_hand_from_mask(ns.masks[0])
            _add_log(0, "Pass", "—", remaining)
            process_opponent_chain()
            st.rerun()
        return

    # ── 构建合法出牌映射（orders_key → move）──
    winning_set = {tuple(sorted(wm[2])) for wm in winning_moves_info}
    losing_set = {tuple(sorted(lm[2])) for lm in losing_moves_info}
    move_order_map: dict[str, tuple] = {}
    legal_hints = []

    for move in all_moves:
        ttype = move.type
        orders = move.orders
        type_cn = _TYPE_CN.get(ttype, ttype)
        cards_str = format_cards(orders)
        orders_key = tuple(sorted(orders))
        orders_str = " ".join(str(o) for o in sorted(orders))

        if orders_key in winning_set:
            tag = "✅"
        elif orders_key in losing_set:
            tag = "❌"
        else:
            tag = "  "

        move_order_map[orders_str] = move
        legal_hints.append(f"{tag} {type_cn}: {cards_str}")

    # ── 已选牌匹配检查 ──
    selected_orders_sorted = sorted(st.session_state.selected_orders)
    selected_key = " ".join(str(o) for o in selected_orders_sorted)
    can_play_selected = selected_key in move_order_map

    # ── 已选牌预览 ──
    selected_set = set(st.session_state.selected_orders)
    if selected_set:
        sel_preview = format_cards(sorted(selected_set))
        if can_play_selected:
            st.success(f"已选：{sel_preview}")
        else:
            st.warning(f"已选：{sel_preview}（⚠️ 无效组合）")

    # ── 出牌 + 清空按钮 ──
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        disabled = not can_play_selected
        if st.button("🃏 出牌", type="primary", key="play_btn_main",
                     use_container_width=True, disabled=disabled):
            if can_play_selected:
                move = move_order_map[selected_key]
                execute_star_play(state, move)
                st.rerun()
            else:
                st.error("请先选择合法出牌组合")
                st.stop()
    with col2:
        if st.button("✕ 清空", key="clear_sel", use_container_width=True):
            st.session_state.selected_orders = []
            st.rerun()
    with col3:
        if st.button("⏭ Pass", key="pass_btn2", use_container_width=True):
            old_trick = state.trick
            ns = advance_turn(state)
            if old_trick is not None and ns.trick is None:
                _start_new_round()
            st.session_state.state = ns
            st.session_state.selected_orders = []
            remaining = format_hand_from_mask(ns.masks[0])
            _add_log(0, "Pass", "—", remaining)
            process_opponent_chain()
            st.rerun()

    # ── 出牌选项提示（折叠）──
    with st.expander("📋 合法出牌列表", expanded=False):
        st.write(f"**{overall}**")
        for hint in legal_hints:
            st.write(hint)


# ══════════════════════════════════════════════════════════════════════
# ★ 出牌 UI（模式二）
# ══════════════════════════════════════════════════════════════════════

def _update_mode2_sequence(state: GameState):
    """模式二：★出牌后更新同盟最优序列"""
    seq = find_best_response(state)
    if seq:
        st.session_state.current_sequence = seq
    else:
        st.session_state.current_sequence = []


def render_mode2_star_play(state: GameState):
    """模式二的★出牌 — 斗地主式选牌 + 序列分析专用界面"""
    st.write("⭐ 你的回合（模式二·同盟序列分析），请选择出牌")

    all_moves = get_valid_moves_for_player(state, 0)

    if not all_moves:
        st.warning("无牌可出，将自动 Pass")
        if st.button("确认 Pass", key="pass_btn", type="primary", use_container_width=True):
            old_trick = state.trick
            ns = advance_turn(state)
            if old_trick is not None and ns.trick is None:
                _start_new_round()
            st.session_state.state = ns
            st.session_state.selected_orders = []
            remaining = format_hand_from_mask(ns.masks[0])
            _add_log(0, "Pass", "—", remaining)
            process_opponent_chain()
            st.rerun()
        return

    # ── 构建出牌映射 ──
    move_order_map: dict[str, tuple] = {}
    hints = []
    for move in all_moves:
        ttype = move.type
        orders = move.orders
        type_cn = _TYPE_CN.get(ttype, ttype)
        cards_str = format_cards(orders)
        orders_str = " ".join(str(o) for o in sorted(orders))
        move_order_map[orders_str] = move
        hints.append(f"{type_cn}: {cards_str}")

    # ── 已选牌预览 ──
    selected_orders_sorted = sorted(st.session_state.selected_orders)
    selected_key = " ".join(str(o) for o in selected_orders_sorted)
    can_play_selected = selected_key in move_order_map

    selected_set = set(st.session_state.selected_orders)
    if selected_set:
        sel_preview = format_cards(sorted(selected_set))
        if can_play_selected:
            st.success(f"已选：{sel_preview}")
        else:
            st.warning(f"已选：{sel_preview}（⚠️ 无效组合）")

    # ── 出牌操作 ──
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        disabled = not can_play_selected
        if st.button("🃏 出牌", type="primary", key="play_btn_m2",
                     use_container_width=True, disabled=disabled):
            if can_play_selected:
                move = move_order_map[selected_key]
                execute_star_play(state, move)
                st.rerun()
            else:
                st.error("请先选择合法出牌组合")
                st.stop()
    with col2:
        if st.button("✕ 清空", key="clear_sel_m2", use_container_width=True):
            st.session_state.selected_orders = []
            st.rerun()
    with col3:
        if st.button("⏭ Pass", key="pass_btn2_m2", use_container_width=True):
            old_trick = state.trick
            ns = advance_turn(state)
            if old_trick is not None and ns.trick is None:
                _start_new_round()
            st.session_state.state = ns
            st.session_state.selected_orders = []
            remaining = format_hand_from_mask(ns.masks[0])
            _add_log(0, "Pass", "—", remaining)
            process_opponent_chain()
            st.rerun()

    # ── 出牌选项提示 ──
    with st.expander("📋 合法出牌列表", expanded=False):
        for hint in hints:
            st.write(hint)


# ══════════════════════════════════════════════════════════════════════
# 对手回合 UI
# ══════════════════════════════════════════════════════════════════════

def render_opponent_turn(state: GameState):
    """模式一：对手自动出牌按钮"""
    st.write(f"👤 当前：玩家{state.turn} 的回合")
    if st.button("▶ 对手自动出牌", type="primary", use_container_width=True):
        new_state, log_msg = opponent_play(state)
        st.session_state.state = new_state
        process_opponent_chain()


def render_mode2_opponent_turn(state: GameState):
    """模式二：对手强制执行按钮"""
    st.write(f"👤 当前：玩家{state.turn} 的回合（模式二）")

    result_dict = st.session_state.mode2_da_verification
    has_star_win = result_dict and any(seq is None for seq in result_dict.values())
    if has_star_win and not st.session_state.current_sequence:
        st.info("★ 有胜招，模式二无法进入强制执行阶段。")
        return

    player = state.turn
    seq = st.session_state.current_sequence
    forced_move = None
    for p, m in seq:
        if p == player:
            forced_move = m
            break

    if forced_move:
        if st.button(f"🤖 强制执行 玩家{player} 出牌", type="primary", use_container_width=True):
            new_state, _ = execute_forced_move_web(state, forced_move)
            st.session_state.state = new_state
            st.session_state.current_sequence = [
                (p, m) for p, m in st.session_state.current_sequence
                if not (p == player and m == forced_move)
            ]
            process_forced_chain()
            st.rerun()
    else:
        st.write(f"玩家{player} 回合（无强制序列）")
        if st.button("▶ 自动出牌", use_container_width=True):
            new_state, _ = opponent_play(state)
            st.session_state.state = new_state
            process_opponent_chain()
            st.rerun()
