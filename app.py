"""夺A快跑 — Streamlit Web 应用入口

独立于 CLI 的 Web 交互层，不修改任何核心模块。
使用 st.session_state 管理所有游戏状态。

拆分为:
    app_styles.py   — CSS 样式
    app_render.py   — 牌面渲染 HTML
    app_play.py     — 出牌交互组件
"""

import streamlit as st
import random as _random

from models import GameState, Trick, Card, _TYPE_CN, RANK_NAMES
from deck import build_deck, shuffle_and_deal, hands_to_masks, take_bid_logic
from solver import solve, check_terminal
from sequence import (
    verify_all_da_moves, format_multi_da_verification,
    find_best_response, format_best_response,
)
from config_loader import load_yaml_config, validate_and_parse_scenario
from log_engine import to_web_dict, log_event

from app_styles import inject_styles
from app_render import (
    format_hand_from_mask,
    render_hand,
    render_trick_history_html,
)
from app_play import (
    render_star_play,
    render_mode2_star_play,
    render_opponent_turn,
    render_mode2_opponent_turn,
    process_opponent_chain,
    _toggle_card_order,
)

# ══════════════════════════════════════════════════════════════════════
# 页面配置
# ══════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="夺A快跑",
    page_icon="♦",
    layout="wide",
)

inject_styles()

# ══════════════════════════════════════════════════════════════════════
# Session State 初始化
# ══════════════════════════════════════════════════════════════════════

DEFAULTS = {
    "state": None,
    "mode": 1,
    "num_players": 5,
    "log": [],
    "current_sequence": [],
    "game_started": False,
    "mode2_static_done": False,
    "mode2_da_verification": None,
    "star_move_input": "",
    "selected_orders": [],
    "bidder_selected": None,
    "bidding_hands": None,
    "bidding_info": None,
    "trick_history": [],
    "all_trick_history": [],
    "current_round": 1,
}

for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ══════════════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════════════

def _reset_game():
    """重置游戏状态"""
    for key in DEFAULTS:
        st.session_state[key] = DEFAULTS[key]


# ══════════════════════════════════════════════════════════════════════
# 发牌工具
# ══════════════════════════════════════════════════════════════════════

def _deal_only():
    """随机发牌 → 返回 (hands, da_owner)"""
    n = st.session_state.get("num_players", 5)
    deck = build_deck(n)
    hands = shuffle_and_deal(deck, n)

    da_owner = None
    for i, hand in enumerate(hands):
        for c in hand:
            if c.rank == 0 and c.suit == 0:
                da_owner = i
                break
        if da_owner is not None:
            break
    return hands, da_owner


# ══════════════════════════════════════════════════════════════════════
# 抢A阶段界面
# ══════════════════════════════════════════════════════════════════════

def show_bid_selection():
    """抢A选择界面：显示所有玩家手牌，手动选择抢A玩家。"""
    hands = st.session_state.bidding_hands
    info = st.session_state.bidding_info or {}
    config_bidder = info.get("bidder_from_config")

    st.subheader("🎯 抢A阶段 — 选择★玩家")
    st.caption("请查看所有玩家手牌，点击「选择」指定★玩家（抢A者）")

    if config_bidder is not None:
        st.info(f"📋 配置文件中指定抢A玩家：玩家{config_bidder}")

    n = st.session_state.get("num_players", 5)
    for i in range(n):
        mask = sum(1 << c.order for c in hands[i])
        label = "★" if config_bidder == i else f"玩家{i}"
        da_badge = ""
        for c in hands[i]:
            if c.rank == 0 and c.suit == 0:
                da_badge = " ♦A"
                break

        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(
                f'<div class="hand-label">{label}{da_badge} 的手牌</div>',
                unsafe_allow_html=True,
            )
            st.markdown(render_hand(mask, face_up=True), unsafe_allow_html=True)
        with c2:
            is_current = st.session_state.bidder_selected == i
            btn_label = f"✓ 已选" if is_current else "选择"
            btn_type = "primary" if is_current else "secondary"
            if st.button(btn_label, key=f"bid_{i}", type=btn_type,
                         use_container_width=True):
                st.session_state.bidder_selected = i
                st.rerun()
        st.divider()

    col_btn, _ = st.columns([1, 3])
    with col_btn:
        disabled = st.session_state.bidder_selected is None
        if st.button("✅ 确认抢A", type="primary", use_container_width=True,
                     disabled=disabled, key="confirm_bid"):
            _finalize_bidder()
            st.rerun()


def _finalize_bidder():
    """确认抢A：完成换手、重排、创建 GameState、进入游戏。"""
    hands = st.session_state.bidding_hands
    bidder = st.session_state.bidder_selected
    n = len(hands)  # 动态玩家数

    # 使用 deck.py 纯函数完成换手
    _, updated_hands = take_bid_logic(hands, bidder)

    # 重排：★ → 索引 0
    reordered = [updated_hands[bidder]] + [
        updated_hands[i] for i in range(n) if i != bidder
    ]
    masks = hands_to_masks(reordered)

    state = GameState(masks=masks, trick=None, turn=0, starter=0)
    st.session_state.state = state
    st.session_state.game_started = True
    st.session_state.log = []
    st.session_state.trick_history = []
    st.session_state.all_trick_history = []
    st.session_state.current_round = 1
    entry = log_event("🚀", f"游戏开始 ★=原玩家{bidder}", to_web=True)
    st.session_state.log.append(to_web_dict(entry))

    # 模式二：静态分析
    if st.session_state.mode == 2:
        st.session_state.mode2_da_verification = verify_all_da_moves(state)
        st.session_state.mode2_static_done = True
        has_star_win = any(
            seq is None
            for seq in st.session_state.mode2_da_verification.values()
        )
        if not has_star_win:
            seq = find_best_response(state)
            st.session_state.current_sequence = seq if seq else []


# ══════════════════════════════════════════════════════════════════════
# 抢A阶段初始化
# ══════════════════════════════════════════════════════════════════════

def _init_bidding_random():
    """随机发牌 → 进入抢A选择阶段"""
    hands, da_owner = _deal_only()
    if da_owner is None:
        st.error("发牌错误：♦A 缺失")
        return
    _reset_game()
    st.session_state.bidding_hands = hands
    st.session_state.bidding_info = {"bidder_from_config": da_owner}
    st.session_state.bidder_selected = da_owner


def _init_bidding_from_config(config_path: str, scene_id: int | None):
    """从 YAML 配置加载 → 进入抢A选择阶段"""
    try:
        config_data = load_yaml_config(config_path)
        bidder, hands, info = validate_and_parse_scenario(config_data, scene_id)
    except Exception as e:
        st.error(f"配置加载失败: {e}")
        return

    auto_bidder = bidder
    if auto_bidder is None:
        for i, hand in enumerate(hands):
            for c in hand:
                if c.rank == 0 and c.suit == 0:
                    auto_bidder = i
                    break
            if auto_bidder is not None:
                break

    _reset_game()
    st.session_state.bidding_hands = hands
    st.session_state.bidding_info = {
        "bidder_from_config": auto_bidder,
        "scene_info": info,
    }
    st.session_state.bidder_selected = auto_bidder


# ══════════════════════════════════════════════════════════════════════
# UI 组件
# ══════════════════════════════════════════════════════════════════════

def render_sidebar():
    """侧边栏：模式选择 + 配置加载"""
    with st.sidebar:
        st.header("🎮 夺A快跑")
        st.caption("基于上帝视角的抢A训练工具")

        st.divider()

        st.radio(
            "训练模式",
            options=[1, 2],
            index=0 if st.session_state.mode == 1 else 1,
            format_func=lambda x: f"模式{'一' if x == 1 else '二'}: "
                                   f"{'实时交互训练' if x == 1 else '同盟必胜序列分析'}",
            key="mode_selector",
            on_change=lambda: _on_mode_change(),
            disabled=st.session_state.game_started and st.session_state.state is not None,
        )

        st.divider()

        st.subheader("⚙️ 游戏设置")
        st.number_input(
            "玩家人数", min_value=5, max_value=8, value=st.session_state.get("num_players", 5),
            key="num_players_input",
            disabled=st.session_state.game_started,
            on_change=lambda: st.session_state.update(
                {"num_players": st.session_state.num_players_input}
            ) if not st.session_state.game_started else None,
        )
        if not st.session_state.game_started:
            st.session_state.num_players = st.session_state.num_players_input

        st.divider()

        st.subheader("📂 预设场景")
        use_config = st.checkbox("加载 YAML 配置文件", disabled=st.session_state.game_started)
        config_file = None
        scene_id_input = None
        if use_config:
            config_file = st.text_input("配置文件路径", value="configs/hands.yaml")
            scene_select = st.selectbox(
                "场景选择",
                options=["交互选择"] + [str(i + 1) for i in range(5)],
                index=0,
            )
            if scene_select != "交互选择":
                scene_id_input = int(scene_select)

        st.divider()

        if not st.session_state.game_started:
            if st.button("🚀 开始游戏", type="primary", use_container_width=True):
                if use_config and config_file:
                    _init_bidding_from_config(config_file, scene_id_input)
                else:
                    _init_bidding_random()
                st.rerun()

        if st.session_state.game_started:
            if st.button("🔄 重新开始", use_container_width=True):
                _reset_game()
                st.rerun()


def _on_mode_change():
    st.session_state.mode = st.session_state.mode_selector


def render_game_area():
    """主区域：抢A阶段 或 游戏阶段"""
    if st.session_state.bidding_hands is not None and not st.session_state.game_started:
        show_bid_selection()
        return

    render_game_state()
    render_interaction()
    render_log()


def render_game_state():
    """主区域：可视化局面"""
    state = st.session_state.state
    if state is None:
        st.info("👈 请先在侧边栏点击「开始游戏」")
        return

    # ── 顶部状态条 ──
    result = solve(state)
    emoji = "✅" if result else "❌"
    label = "★必胜" if result else "★必败"
    turn_label = "★" if state.turn == 0 else f"玩家{state.turn}"

    st.markdown(
        f"**{emoji} {label}** · "
        f"当前回合：<span class='trick-player-active'>{turn_label}</span>",
        unsafe_allow_html=True,
    )

    # ── 出牌区：历史出牌 ──
    with st.expander("🎴 历史出牌", expanded=True):
        if state.trick:
            trick_type_cn = _TYPE_CN.get(state.trick.type, state.trick.type)
            rank_str = RANK_NAMES.get(state.trick.rank, str(state.trick.rank))
            st.caption(f"桌上：{trick_type_cn} {rank_str}")
        else:
            st.caption("桌上：无（首出）")
        st.markdown(
            render_trick_history_html(st.session_state.all_trick_history),
            unsafe_allow_html=True,
        )

    # ── ★ 出牌控件 ──
    if state.turn == 0:
        winner, game_over = check_terminal(state)
        if not game_over:
            if st.session_state.mode == 1:
                render_star_play(state)
            else:
                render_mode2_star_play(state)

    # ── ★手牌区 ──
    st.markdown('<div class="hand-label star">⭐ ★ 你的手牌（点击选牌）</div>',
                unsafe_allow_html=True)
    st.markdown(render_hand(state.masks[0], face_up=True, clickable=True,
                             selected_orders=st.session_state.selected_orders,
                             toggle_callback=_toggle_card_order),  # type: ignore
                unsafe_allow_html=True)

    # ── 对手手牌区 ──
    st.markdown('<div class="hand-label">👤 对手手牌</div>', unsafe_allow_html=True)
    for i in range(1, state.num_players):
        icon = "🏁" if state.masks[i] == 0 else f"P{i}"
        st.markdown(
            f'<div class="hand-label" style="font-weight:400;">{icon} 玩家{i}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(render_hand(state.masks[i], face_up=True), unsafe_allow_html=True)  # type: ignore

    # ── ★ 文字手牌 ──
    with st.expander("📝 ★ 手牌文字列表", expanded=False):
        st.write(format_hand_from_mask(state.masks[0]))

    # ── 模式二静态分析 ──
    if st.session_state.mode == 2 and st.session_state.mode2_static_done:
        st.divider()
        st.subheader("📋 静态分析：多♦A出牌分支验证")
        result_dict = st.session_state.mode2_da_verification
        if result_dict:
            formatted = format_multi_da_verification(result_dict)
            st.text(formatted)

        if st.session_state.current_sequence:
            st.divider()
            st.subheader("📋 同盟最优应对序列")
            seq = st.session_state.current_sequence
            if seq:
                formatted_seq = format_best_response(seq)
                st.text(formatted_seq)
            else:
                st.success("★ 必胜，同盟无应对策略。")


def render_log():
    """操作日志（可折叠）"""
    with st.expander("📜 操作日志", expanded=False):
        if not st.session_state.log or len(st.session_state.log) <= 1:
            st.caption("暂无操作记录")
            return
        for entry in st.session_state.log:
            etype = entry.get("type", "")
            if etype == "event":
                st.write(f"--- {entry.get('emoji', '')} {entry.get('message', '')} ---")
            elif etype == "move":
                prefix = "🤖 " if entry.get("is_forced") else ""
                note = f" {entry.get('note', '')}" if entry.get("note") else ""
                st.write(
                    f"{prefix}{entry['label']} 出: {entry['cards']} "
                    f"→ 剩余 {entry['remaining']}{note}"
                )
            elif etype == "pass":
                st.write(f"{entry['label']} Pass → 剩余 {entry['remaining']}")
            elif etype == "setup":
                pass  # setup 信息在游戏主界面展示
            else:
                # 兼容旧格式或未知类型
                player = entry.get("player", -2)
                if player == -1:
                    st.write("--- 🚀 游戏开始 ---")
                elif entry.get("action") == "出牌":
                    st.write(
                        f"{entry['label']} 出: {entry['cards']} "
                        f"→ 剩余 [{entry['remaining']}] {entry.get('note', '')}"
                    )
                elif entry.get("action") == "强制出牌":
                    st.write(
                        f"🤖 {entry['label']} [强制] 出: {entry['cards']} "
                        f"→ 剩余 [{entry['remaining']}] {entry.get('note', '')}"
                    )
                elif entry.get("action") == "Pass":
                    st.write(f"{entry['label']} Pass → 剩余 [{entry['remaining']}]")


def render_interaction():
    """对手交互控件"""
    state = st.session_state.state
    if state is None:
        return

    # 终局检查
    winner, game_over = check_terminal(state)
    if game_over:
        if winner == 0:
            st.balloons()
            st.success("🎉 ★ 获胜！")
        else:
            st.error(f"💀 玩家{winner}（对手）先出完，★失败！")
        return

    # ★ 回合 → 控件已在 render_game_state 中
    if state.turn == 0:
        return

    # 对手回合
    if st.session_state.mode == 1:
        render_opponent_turn(state)
    else:
        render_mode2_opponent_turn(state)


# ══════════════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════════════

def main():
    st.title("♦ 夺A快跑")
    st.caption("基于上帝视角的抢A牌局训练工具 — Streamlit Web 版")
    render_sidebar()
    render_game_area()


if __name__ == "__main__":
    main()
