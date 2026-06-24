"""夺A快跑 — Streamlit Web 应用入口

独立于 CLI 的 Web 交互层，不修改任何核心模块。
使用 st.session_state 管理所有游戏状态，以 phase 驱动页面流转。

拆分模块:
    app_styles.py   — CSS 样式
    app_render.py   — 牌面渲染 HTML
    app_play.py     — 出牌交互组件
"""

import streamlit as st

from models import GameState, Trick, Card, _TYPE_CN, RANK_NAMES, format_cards
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
    initial_sidebar_state="expanded",
)

inject_styles()

# ══════════════════════════════════════════════════════════════════════
# Session State 初始化
# ══════════════════════════════════════════════════════════════════════

DEFAULTS = {
    "phase": "init",             # "init" | "bid" | "star_turn" | "opponent_turn" | "game_over"
    "state": None,               # GameState
    "training_mode": 1,          # 1=实时交互, 2=同盟序列分析
    "num_players": 5,            # 5~8
    "deal_method": "random",     # "random" | "config"
    "config_path": "configs/hands.yaml",
    "config_scene_id": None,
    "log": [],
    "current_sequence": [],
    "mode2_static_done": False,
    "mode2_da_verification": None,
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
# 全链路 Debug 工具
# ══════════════════════════════════════════════════════════════════════

_DEBUG_FP = DEFAULTS.get("debug_file", None)  # 设为文件路径可写日志文件
_DEBUG_LOG: list[str] = []  # 内存日志，UI 可展示


def _debug(msg: str, **kwargs):
    """全链路 debug：终端 + UI + 可选文件。

    在所有关键函数入口/出口调用，追踪完整数据流。
    """
    frame = __import__("inspect").currentframe()
    caller = frame.f_back
    func = caller.f_code.co_name
    line = caller.f_lineno

    extra = " " + " ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
    full = f"[DBG|{func}:L{line}] {msg}{extra}"

    # 终端
    print(full, flush=True)
    # UI（追加到 session_state）
    if "debug_log" not in st.session_state:
        st.session_state.debug_log = []
    st.session_state.debug_log.append(full)
    # 文件
    if _DEBUG_FP:
        with open(_DEBUG_FP, "a", encoding="utf-8") as f:
            f.write(full + "\n")


def _render_debug_panel():
    """在侧边栏底部显示最近 debug 日志（可折叠）。"""
    if st.session_state.get("debug_log"):
        with st.sidebar.expander("🐛 全链路 DEBUG 日志", expanded=False):
            recent = st.session_state.debug_log[-30:]
            for line in recent:
                st.code(line, language=None)


# ══════════════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════════════

def _reset_game():
    """重置游戏状态（保留人数/模式/发牌方式设置）。"""
    _debug("_reset_game ENTER",
           nip=st.session_state.get("num_players_input"),
           np=st.session_state.get("num_players"),
           phase=st.session_state.get("phase"))

    keep_keys = {"num_players", "training_mode", "deal_method",
                 "config_path", "config_scene_id"}
    saved = {k: st.session_state.get(k) for k in keep_keys}

    _debug("_reset_game saved", saved_keys=saved)

    for key in DEFAULTS:
        st.session_state[key] = DEFAULTS[key]
    for k, v in saved.items():
        if v is not None:
            st.session_state[k] = v

    _debug("_reset_game EXIT",
           nip=st.session_state.get("num_players_input"),
           np=st.session_state.get("num_players"),
           phase=st.session_state.get("phase"))


# ══════════════════════════════════════════════════════════════════════
# 发牌工具
# ══════════════════════════════════════════════════════════════════════

def _deal_only():
    """随机发牌 → 返回 (hands, da_owner)

    直接读取 num_players_input（widget 权威状态），
    不依赖 num_players 避免同步滞后。
    """
    n = int(st.session_state.get("num_players_input", 5))
    _debug("_deal_only START", n=n, nip=st.session_state.get("num_players_input"),
           np=st.session_state.get("num_players"))

    deck = build_deck(n)
    _debug("_deal_only DECK BUILT", n=n, deck_size=len(deck))

    hands = shuffle_and_deal(deck, n)
    _debug("_deal_only DEALT", num_hands=len(hands),
           hand_sizes=[len(h) for h in hands])

    da_owner = None
    for i, hand in enumerate(hands):
        for c in hand:
            if c.rank == 0 and c.suit == 0:
                da_owner = i
                break
        if da_owner is not None:
            break

    _debug("_deal_only RETURN", num_hands=len(hands), da_owner=da_owner,
           total_cards=sum(len(h) for h in hands))
    return hands, da_owner


# ══════════════════════════════════════════════════════════════════════
# 侧边栏 — 游戏设置
# ══════════════════════════════════════════════════════════════════════

def render_sidebar():
    """侧边栏：人数选择 + 发牌方式 + 训练模式 + 开始游戏"""
    _debug("render_sidebar ENTER",
           phase=st.session_state.get("phase"),
           nip=st.session_state.get("num_players_input"),
           np=st.session_state.get("num_players"),
           bh_len=len(st.session_state.get("bidding_hands") or []))

    with st.sidebar:
        st.header("🎮 夺A快跑")
        st.caption("基于上帝视角的抢A训练工具")

        st.divider()

        # ── 人数选择（5~8）──
        st.subheader("⚙️ 游戏设置")
        game_active = st.session_state.phase not in ("init",)

        _debug("BEFORE number_input", nip=st.session_state.get("num_players_input"),
               np=st.session_state.get("num_players"), game_active=game_active)

        st.number_input(
            "玩家人数", min_value=5, max_value=8,
            value=5,
            key="num_players_input",
            disabled=game_active,
        )

        _debug("AFTER number_input", nip=st.session_state.get("num_players_input"),
               np=st.session_state.get("num_players"))

        if not game_active:
            st.session_state.num_players = st.session_state.num_players_input
            _debug("SYNC num_players", nip=st.session_state.num_players_input,
                   np=st.session_state.num_players)

        # ── 发牌方式 ──
        st.radio(
            "发牌方式",
            options=["random", "config"],
            index=0 if st.session_state.deal_method == "random" else 1,
            format_func=lambda x: "随机发牌" if x == "random" else "加载配置",
            key="deal_method_radio",
            disabled=game_active,
            on_change=lambda: _on_deal_method_change(),
        )
        if not game_active:
            st.session_state.deal_method = st.session_state.deal_method_radio

        # 配置路径（仅加载配置时显示）
        if st.session_state.deal_method == "config" and not game_active:
            st.text_input(
                "配置文件路径", value=st.session_state.config_path,
                key="config_path_input",
                on_change=lambda: st.session_state.update(
                    {"config_path": st.session_state.config_path_input}
                ),
            )
            scene_select = st.selectbox(
                "场景选择",
                options=["交互选择"] + [str(i + 1) for i in range(5)],
                index=0,
                key="scene_select",
            )
            if scene_select != "交互选择":
                st.session_state.config_scene_id = int(scene_select)
            else:
                st.session_state.config_scene_id = None

        st.divider()

        # ── 训练模式 ──
        st.radio(
            "训练模式",
            options=[1, 2],
            index=0 if st.session_state.training_mode == 1 else 1,
            format_func=lambda x: f"模式{'一' if x == 1 else '二'}: "
                                   f"{'实时交互训练' if x == 1 else '同盟必胜序列分析'}",
            key="training_mode_radio",
            disabled=game_active,
            on_change=lambda: _on_training_mode_change(),
        )
        if not game_active:
            st.session_state.training_mode = st.session_state.training_mode_radio

        st.divider()

        # ── 开始游戏 ──
        if not game_active:
            if st.button("🚀 开始游戏", type="primary", use_container_width=True):
                _on_start_game()
                st.rerun()

        # ── 重新开始（游戏中）──
        if game_active:
            if st.button("🔄 重新开始", use_container_width=True):
                _reset_game()
                st.rerun()

        _render_debug_panel()

    _debug("render_sidebar EXIT",
           nip=st.session_state.get("num_players_input"),
           np=st.session_state.get("num_players"),
           phase=st.session_state.get("phase"))


def _on_deal_method_change():
    st.session_state.deal_method = st.session_state.deal_method_radio


def _on_training_mode_change():
    st.session_state.training_mode = st.session_state.training_mode_radio


# ══════════════════════════════════════════════════════════════════════
# 开始游戏 — 发牌 → 进入抢A阶段
# ══════════════════════════════════════════════════════════════════════

def _on_start_game():
    """开始游戏：根据发牌方式初始化手牌，进入 phase="bid"。

    发牌前强制将 num_players 同步为 num_players_input（唯一权威来源），
    避免两者不同步导致 build_deck(n) 使用错误人数。
    """
    _debug("_on_start_game ENTER",
           nip=st.session_state.get("num_players_input"),
           np=st.session_state.get("num_players"),
           deal_method=st.session_state.get("deal_method"),
           phase=st.session_state.get("phase"))

    old_np = st.session_state.get("num_players")
    st.session_state.num_players = st.session_state.num_players_input
    _debug("_on_start_game AFTER SYNC",
           old_np=old_np,
           new_np=st.session_state.num_players,
           nip=st.session_state.get("num_players_input"))

    if st.session_state.deal_method == "config":
        _init_bidding_from_config(
            st.session_state.config_path,
            st.session_state.config_scene_id,
        )
    else:
        _init_bidding_random()

    _debug("_on_start_game AFTER init",
           bidding_hands_len=len(st.session_state.get("bidding_hands") or []),
           phase=st.session_state.get("phase"))

    if st.session_state.bidding_hands is not None:
        st.session_state.phase = "bid"

    _debug("_on_start_game EXIT",
           bidding_hands_len=len(st.session_state.get("bidding_hands") or []),
           phase=st.session_state.get("phase"))


def _init_bidding_random():
    """随机发牌 → 进入抢A选择阶段"""
    _debug("_init_bidding_random ENTER",
           nip=st.session_state.get("num_players_input"),
           np=st.session_state.get("num_players"))

    hands, da_owner = _deal_only()

    _debug("_init_bidding_random AFTER _deal_only",
           num_hands=len(hands), da_owner=da_owner,
           hand_sizes=[len(h) for h in hands])

    if da_owner is None:
        _debug("_init_bidding_random da_owner is None, ABORT")
        st.error("发牌错误：♦A 缺失")
        return

    _reset_game()

    _debug("_init_bidding_random AFTER _reset_game",
           nip=st.session_state.get("num_players_input"),
           np=st.session_state.get("num_players"))

    st.session_state.bidding_hands = hands

    _debug("_init_bidding_random SET bidding_hands",
           bidding_hands_len=len(hands),
           hand_sizes=[len(h) for h in hands])

    st.session_state.bidding_info = {"bidder_from_config": da_owner}
    st.session_state.bidder_selected = da_owner
    st.session_state.phase = "bid"

    _debug("_init_bidding_random EXIT",
           bidding_hands_len=len(st.session_state.bidding_hands),
           phase=st.session_state.phase)


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
    st.session_state.phase = "bid"


# ══════════════════════════════════════════════════════════════════════
# Phase: "bid" — 抢A选择界面
# ══════════════════════════════════════════════════════════════════════

def render_phase_bid():
    """抢A选择界面：显示所有玩家手牌，手动选择抢A玩家。"""
    hands = st.session_state.bidding_hands
    info = st.session_state.bidding_info or {}
    config_bidder = info.get("bidder_from_config")
    n = len(hands)

    _debug("render_phase_bid ENTER",
           hands_len=n,
           hand_sizes=[len(h) for h in hands],
           total_cards=sum(len(h) for h in hands),
           nip=st.session_state.get("num_players_input"),
           np=st.session_state.get("num_players"))

    st.subheader("🎯 抢A阶段 — 选择★玩家")
    st.caption("请查看所有玩家手牌，点击「选择」指定★玩家（抢A者）")

    st.caption(
        f"🐛 DEBUG: {n}玩家, {sum(len(h) for h in hands)}张牌, "
        f"nip={st.session_state.get('num_players_input')}, "
        f"np={st.session_state.get('num_players')}"
    )

    if config_bidder is not None:
        st.info(f"📋 配置文件中指定抢A玩家：玩家{config_bidder}")

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
            btn_label = "✓ 已选" if is_current else "选择"
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
    """确认抢A：完成换手、重排、创建 GameState、进入 phase="star_turn"。"""
    hands = st.session_state.bidding_hands
    bidder = st.session_state.bidder_selected
    n = len(hands)

    _debug("_finalize_bidder ENTER",
           n=n, bidder=bidder,
           hand_sizes=[len(h) for h in hands],
           nip=st.session_state.get("num_players_input"))

    # 使用 deck.py 纯函数完成换手
    _, updated_hands = take_bid_logic(hands, bidder)

    _debug("_finalize_bidder AFTER take_bid_logic",
           num_hands=len(updated_hands),
           hand_sizes=[len(h) for h in updated_hands])

    # 重排：★ → 索引 0
    reordered = [updated_hands[bidder]] + [
        updated_hands[i] for i in range(n) if i != bidder
    ]
    masks = hands_to_masks(reordered)

    _debug("_finalize_bidder AFTER reorder",
           masks_len=len(masks),
           mask_bits=[m.bit_count() for m in masks])

    state = GameState(masks=masks, trick=None, turn=0, starter=0)

    _debug("_finalize_bidder GameState CREATED",
           num_players=state.num_players,
           masks_len=len(state.masks))

    st.session_state.state = state
    st.session_state.phase = "star_turn"
    st.session_state.log = []
    st.session_state.trick_history = []
    st.session_state.all_trick_history = []
    st.session_state.current_round = 1
    st.session_state.selected_orders = []

    entry = log_event("🚀", f"游戏开始 ★=原玩家{bidder}", to_web=True)
    st.session_state.log.append(to_web_dict(entry))

    # 模式二：立即进行静态分析
    if st.session_state.training_mode == 2:
        st.session_state.mode2_da_verification = verify_all_da_moves(state)
        st.session_state.mode2_static_done = True
        has_star_win = any(
            seq is None
            for seq in st.session_state.mode2_da_verification.values()
        )
        if not has_star_win:
            seq = find_best_response(state)
            st.session_state.current_sequence = seq if seq else []
        else:
            st.session_state.current_sequence = []


# ══════════════════════════════════════════════════════════════════════
# Phase: 游戏阶段 — 5区域布局
# ══════════════════════════════════════════════════════════════════════

def render_game_phase():
    """根据 state.turn 和终局状态决定渲染内容（phase 仅用于区分 init/bid）。"""
    state = st.session_state.state

    _debug("render_game_phase ENTER",
           phase=st.session_state.get("phase"),
           state_np=state.num_players if state else None,
           masks_len=len(state.masks) if state else None,
           nip=st.session_state.get("num_players_input"))

    if state is None:
        st.info("等待游戏开始...")
        return

    # 终局检查
    winner, game_over = check_terminal(state)
    if game_over:
        st.session_state.phase = "game_over"
        _render_region_game_over()
        return

    # 根据 state.turn 决定★回合/对手回合
    is_star_turn = (state.turn == 0)

    _render_region_top_bar(is_star_turn)
    _render_region_trick_history()

    if is_star_turn:
        _render_region_star_hand()
    else:
        _render_region_opponent_interaction()

    _render_region_opponent_hands()
    _render_region_log()


# ── 区域A：顶部状态栏 ──

def _render_region_top_bar(is_star_turn: bool):
    """区域A：★回合/对手回合 · 局面胜负 · 训练模式"""
    state = st.session_state.state
    if state is None:
        return

    result = solve(state)
    emoji = "✅" if result else "❌"
    label = "★必胜" if result else "★必败"
    turn_str = "★ 回合" if is_star_turn else "对手回合"
    mode_str = f"训练模式{'一' if st.session_state.training_mode == 1 else '二'}"

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        st.markdown(f"### {turn_str}")
    with col2:
        st.markdown(f"局面：{emoji} {label}")
    with col3:
        st.markdown(f"{mode_str}")

    # 显示当前出牌人
    if state.turn == 0:
        st.caption("轮到 ★ 出牌")
    else:
        st.caption(f"轮到 玩家{state.turn} 出牌")


# ── 区域B：出牌区（历史平铺）──

def _render_region_trick_history():
    """区域B：出牌历史（本轮平铺，含桌上当前状态）。"""
    state = st.session_state.state
    if state is None:
        return

    with st.container():
        st.markdown('<div class="hand-label">🎴 出牌区</div>',
                    unsafe_allow_html=True)

        # 桌面上当前 trick 信息
        if state.trick:
            trick_type_cn = _TYPE_CN.get(state.trick.type, state.trick.type)
            rank_str = RANK_NAMES.get(state.trick.rank, str(state.trick.rank))
            st.caption(f"桌上：{trick_type_cn} {rank_str}（由玩家{state.starter}发起）")
        else:
            st.caption("桌上：无（首出）")

        # 历史出牌
        st.markdown(
            render_trick_history_html(st.session_state.all_trick_history),
            unsafe_allow_html=True,
        )


# ── 区域C：★手牌区（点击选牌 + 出牌控件）──

def _render_region_star_hand():
    """区域C：★手牌区 + 出牌/清空按钮（仅在★回合显示）。"""
    state = st.session_state.state
    if state is None:
        return

    winner, game_over = check_terminal(state)
    if game_over:
        return

    # ★ 手牌（点击选牌）
    st.markdown(
        '<div class="hand-label star">⭐ ★ 你的手牌（点击选牌）</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        render_hand(
            state.masks[0], face_up=True, clickable=True,
            selected_orders=st.session_state.selected_orders,
            toggle_callback=_toggle_card_order,
        ),
        unsafe_allow_html=True,
    )

    # ★ 出牌控件
    if state.turn == 0:
        if st.session_state.training_mode == 1:
            render_star_play(state)
        else:
            render_mode2_star_play(state)

    # 文字手牌（折叠）
    with st.expander("📝 ★ 手牌文字列表", expanded=False):
        st.write(format_hand_from_mask(state.masks[0]))


# ── 区域D：对手手牌区 ──

def _render_region_opponent_hands():
    """区域D：对手手牌区（明牌，每行一个玩家）。"""
    state = st.session_state.state
    if state is None:
        return

    _debug("_render_opponent_hands ENTER",
           num_players=state.num_players,
           masks_len=len(state.masks),
           nip=st.session_state.get("num_players_input"))

    st.markdown(
        '<div class="hand-label">👤 对手手牌</div>',
        unsafe_allow_html=True,
    )
    for i in range(1, state.num_players):
        icon = "🏁" if state.masks[i] == 0 else f"P{i}"
        st.markdown(
            f'<div class="hand-label" style="font-weight:400;">{icon} 玩家{i}</div>',
            unsafe_allow_html=True,
        )
        st.markdown(render_hand(state.masks[i], face_up=True),
                    unsafe_allow_html=True)

    _debug("_render_opponent_hands EXIT",
           rendered_players=state.num_players - 1)

    # ── 模式二静态分析（折叠）──
    if (st.session_state.training_mode == 2
            and st.session_state.mode2_static_done):
        st.divider()
        st.subheader("📋 静态分析：多♦A出牌分支验证")
        result_dict = st.session_state.mode2_da_verification
        if result_dict:
            formatted = format_multi_da_verification(result_dict)
            st.text(formatted)

        if st.session_state.current_sequence:
            st.divider()
            st.subheader("📋 同盟最优应对序列")
            formatted_seq = format_best_response(
                st.session_state.current_sequence
            )
            st.text(formatted_seq)
        elif not any(seq is None for seq in (result_dict or {}).values()):
            st.success("★ 必胜，同盟无应对策略。")


# ── 区域E：操作日志（可折叠）──

def _render_region_log():
    """区域E：操作日志（可折叠，最近10条，格式对齐 CLI 排版规范）。"""
    with st.expander("📜 操作日志", expanded=False):
        if not st.session_state.log or len(st.session_state.log) <= 1:
            st.caption("暂无操作记录")
            return

        # 显示最近10条
        recent = st.session_state.log[-10:]
        for entry in recent:
            etype = entry.get("type", "")
            if etype == "event":
                st.write(
                    f"  {entry.get('emoji', '')} {entry.get('message', '')}"
                )
            elif etype == "move":
                prefix = "🤖 " if entry.get("is_forced") else ""
                note = f" {entry.get('note', '')}" if entry.get("note") else ""
                st.write(
                    f"  {prefix}{entry['label']} 出: {entry['cards']} "
                    f"→ 剩余 {entry['remaining']}{note}"
                )
            elif etype == "pass":
                st.write(
                    f"  {entry['label']} Pass → 剩余 {entry['remaining']}"
                )
            elif etype == "setup":
                pass  # setup 信息在游戏主界面展示
            else:
                # 兼容旧格式
                action = entry.get("action", "")
                if action == "出牌":
                    st.write(
                        f"  {entry['label']} 出: {entry['cards']} "
                        f"→ 剩余 [{entry['remaining']}] {entry.get('note', '')}"
                    )
                elif action == "强制出牌":
                    st.write(
                        f"  🤖 {entry['label']} [强制] 出: {entry['cards']} "
                        f"→ 剩余 [{entry['remaining']}] {entry.get('note', '')}"
                    )
                elif action == "Pass":
                    st.write(
                        f"  {entry['label']} Pass → 剩余 [{entry['remaining']}]"
                    )


# ── 对手回合交互 ──

def _render_region_opponent_interaction():
    """对手回合：自动出牌按钮。game_over 已在上层 render_game_phase 处理。"""
    state = st.session_state.state
    if state is None:
        return

    # 对手回合控件
    if st.session_state.training_mode == 1:
        render_opponent_turn(state)
    else:
        render_mode2_opponent_turn(state)


# ── 终局画面 ──

def _render_region_game_over():
    """终局画面：显示胜负 + 再来一局按钮。"""
    state = st.session_state.state
    if state is None:
        return

    winner, _ = check_terminal(state)

    if winner == 0:
        st.balloons()
        st.success("🎉 ★ 获胜！")
    else:
        st.error(f"💀 玩家{winner}（对手）先出完，★失败！")

    st.divider()

    # 显示最终手牌
    st.subheader("📋 最终手牌")
    for i in range(state.num_players):
        prefix = "⭐ ★" if i == 0 else f"P{i}"
        cards_str = format_hand_from_mask(state.masks[i]) if state.masks[i] else "（已出完 ✓）"
        st.markdown(f"**{prefix}**: {cards_str}")

    st.divider()

    col1, col2, _ = st.columns([1, 1, 2])
    with col1:
        if st.button("🔄 再来一局", type="primary", use_container_width=True):
            _reset_game()
            st.rerun()
    with col2:
        if st.button("🔙 返回设置", use_container_width=True):
            _reset_game()
            st.rerun()


# ══════════════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════════════

def main():
    _debug("=" * 60)
    _debug("main() SCRIPT RUN START",
           phase=st.session_state.get("phase"),
           nip=st.session_state.get("num_players_input"),
           np=st.session_state.get("num_players"))

    st.title("♦ 夺A快跑 v0.13")
    st.caption("基于上帝视角的抢A牌局训练工具 — Streamlit Web 版")

    render_sidebar()

    phase = st.session_state.phase

    if phase == "init":
        st.info("👈 请在侧边栏设置游戏参数，然后点击「开始游戏」")
    elif phase == "bid":
        render_phase_bid()
    elif phase in ("star_turn", "opponent_turn", "game_over"):
        render_game_phase()
    else:
        st.warning(f"未知阶段: {phase}")
        if st.button("重置"):
            _reset_game()
            st.rerun()

    _debug("main() SCRIPT RUN END",
           phase=st.session_state.get("phase"),
           nip=st.session_state.get("num_players_input"),
           np=st.session_state.get("num_players"))


if __name__ == "__main__":
    main()
