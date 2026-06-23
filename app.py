"""夺A快跑 — Streamlit Web 应用入口

独立于 CLI 的 Web 交互层，不修改任何核心模块。
使用 st.session_state 管理所有游戏状态。
"""

import streamlit as st
import random as _random

from models import GameState, Trick, Card, _TYPE_CN, format_cards, SUIT_NAMES, RANK_NAMES
from deck import build_deck, shuffle_and_deal, hands_to_masks
from moves import get_legal_moves_free, get_legal_moves_response, is_global_max, get_max_single
from solver import solve, _apply_move, analyze_moves, check_terminal, advance_turn
from sequence import (
    find_winning_sequence, format_sequence,
    find_best_response, format_best_response,
    verify_all_da_moves, format_multi_da_verification,
)
from config_loader import load_yaml_config, validate_and_parse_scenario

# ══════════════════════════════════════════════════════════════════════
# 页面配置
# ══════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="夺A快跑",
    page_icon="♦",
    layout="wide",
)

# ══════════════════════════════════════════════════════════════════════
# CSS 样式（基于 ts.py 扩展）
# ══════════════════════════════════════════════════════════════════════

CSS_CODE = """
<style>
/* ── 基础卡片容器（复用 ts.py）── */
.poker-card {
    display: inline-flex;
    flex-direction: column;
    justify-content: space-between;
    width: 3.2rem;
    height: 4.8rem;
    padding: 0.3rem;
    margin: 0.2rem;
    background: #fff;
    border: 1px solid #ddd;
    border-radius: 0.4rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    font-family: system-ui, -apple-system, sans-serif;
    user-select: none;
    cursor: default;
    transition: transform 0.15s, box-shadow 0.15s, border-color 0.15s;
}
.poker-card .suit-bottom {
    transform: rotate(180deg);
    align-self: flex-end;
}
.poker-card .suit {
    font-size: 1.4rem;
    line-height: 1;
}
.poker-card .rank {
    font-size: 1.2rem;
    font-weight: 600;
    line-height: 1;
}

/* ── 花色颜色（复用 ts.py）── */
.suit-heart, .suit-diamond { color: #d92121; }
.suit-spade, .suit-club  { color: #000000; }

/* ── 选中态（prompt14: translateY(-8px) + scale(1.05)）── */
.poker-card.selected {
    transform: translateY(-8px) scale(1.05);
    border: 2px solid #2563eb !important;
    box-shadow: 0 4px 12px rgba(37,99,235,0.4) !important;
    transition: all 0.15s ease;
}
.poker-card.clickable { cursor: pointer; }
.poker-card.clickable:hover {
    transform: translateY(-3px);
    box-shadow: 0 3px 8px rgba(0,0,0,0.18);
}

/* ── 卡片手牌区：透明按钮（仅作用于手牌区内）── */
.card-hand-area div[data-testid="stButton"] > button {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
    box-shadow: none !important;
    min-height: 0 !important;
    height: 8px !important;
    overflow: hidden !important;
}

/* 手牌区内扑克牌固定大小（防止横向拉伸，与对手手牌一致） */
.card-hand-area .poker-card {
    width: 3.2rem !important;
    height: 4.8rem !important;
    flex-shrink: 0;
    margin-left: auto !important;
    margin-right: auto !important;
}

/* 历史出牌滚动容器 */
.trick-history-scroll {
    max-height: 360px;
    overflow-y: auto;
    scrollbar-width: thin;
    padding-right: 2px;
}
.trick-history-scroll::-webkit-scrollbar { width: 4px; }
.trick-history-scroll::-webkit-scrollbar-thumb {
    background: #c0c7cf;
    border-radius: 2px;
}

/* ── 牌背（对手手牌）── */
.poker-card.card-back {
    background: linear-gradient(135deg, #1a3a6b 0%, #2d5fa0 50%, #1a3a6b 100%);
    border-color: #0d2240;
    color: transparent;
}
.poker-card.card-back .rank,
.poker-card.card-back .suit,
.poker-card.card-back .suit-bottom { visibility: hidden; }

/* ── 出牌区容器 ── */
.trick-area {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-wrap: wrap;
    gap: 0.4rem;
    padding: 0.8rem 0.5rem;
    min-height: 6rem;
    background: #f5f7fa;
    border: 2px dashed #d0d5dd;
    border-radius: 0.6rem;
    margin-bottom: 0.8rem;
}

/* ── 当前出牌人高亮 ── */
.trick-player-active {
    font-weight: 700;
    color: #1a73e8;
    background: #e8f0fe;
    border-radius: 0.3rem;
    padding: 0.1rem 0.4rem;
}

/* ── 手牌区容器（横向滚动）── */
.hand-container {
    display: flex;
    align-items: flex-start;
    overflow-x: auto;
    overflow-y: visible;
    white-space: nowrap;
    padding: 0.5rem 0.2rem;
    min-height: 5.4rem;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: thin;
}
.hand-container::-webkit-scrollbar { height: 4px; }
.hand-container::-webkit-scrollbar-thumb {
    background: #c0c7cf;
    border-radius: 2px;
}

/* ── 手牌区标签 ── */
.hand-label {
    font-size: 0.85rem;
    font-weight: 600;
    margin: 0.5rem 0 0.1rem 0;
    color: #555;
}
.hand-label.star { color: #d92121; }

/* ── 操作按钮 ── */
.play-btn {
    min-height: 44px !important;
    font-size: 1rem !important;
}

/* ── 玩家信息行 ── */
.player-info-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.3rem 0;
}

/* ── 出牌区历史平铺（prompt14）── */
.trick-history {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    padding: 0.5rem;
    background: #f0f4f8;
    border-radius: 0.5rem;
    min-height: 3rem;
}
.trick-card-wrapper {
    border: 1px solid #cbd5e1;
    border-radius: 0.4rem;
    padding: 0.3rem;
    position: relative;
    background: white;
    display: inline-flex;
    gap: 0.1rem;
    overflow: visible;
    margin-top: 0.4rem;  /* 为 .trick-player-label(top:-0.5rem) 留空间 */
.trick-player-label {
    position: absolute;
    top: -0.5rem;
    left: 0.2rem;
    font-size: 0.7rem;
    font-weight: 600;
    color: #475569;
    background: white;
    padding: 0 0.2rem;
    z-index: 1;
}
.latest-card {
    transform: scale(1.15);
    border-color: #2563eb;
    box-shadow: 0 2px 8px rgba(37,99,235,0.3);
}

/* ── 移动端适配（复用 ts.py + 扩展）── */
@media (max-width: 480px) {
    .poker-card {
        width: 2.6rem;
        height: 3.9rem;
        padding: 0.2rem;
    }
    .poker-card .suit { font-size: 1.1rem; }
    .poker-card .rank { font-size: 0.95rem; }
    .trick-area { min-height: 4.5rem; padding: 0.4rem 0.3rem; }
    .hand-container { padding: 0.3rem 0.1rem; min-height: 4.4rem; }
}

/* ── 桌面端手牌区（允许换行）── */
@media (min-width: 769px) {
    .hand-container.desktop-wrap {
        flex-wrap: wrap;
        overflow-x: visible;
    }
}
</style>
"""

st.markdown(CSS_CODE, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════
# Session State 初始化
# ══════════════════════════════════════════════════════════════════════

DEFAULTS = {
    "state": None,           # GameState | None
    "mode": 1,               # 1 = 实时交互, 2 = 同盟序列分析
    "log": [],               # list[dict]: {player, action, cards, remaining, note}
    "current_sequence": [],  # 模式二的强制执行序列
    "game_started": False,
    "mode2_static_done": False,
    "mode2_da_verification": None,  # dict | None — 静态分析结果
    "star_move_input": "",   # ★ 输入框内容
    "selected_orders": [],   # ★ 点击选中的 order 列表
    # ── prompt14 新增 ──
    "bidder_selected": None,       # int | None — 抢A阶段选中的玩家 (0~4)
    "bidding_hands": None,         # list[list[Card]] | None — 发牌后、确认抢A前的手牌
    "bidding_info": None,          # dict | None — {bidder_from_config, scene_info} 配置信息
    "trick_history": [],           # list[dict] — 本轮出牌历史 {player_id, label, orders, type_cn}
    "all_trick_history": [],       # list[dict] — 全部出牌历史（跨轮不清空）
    "current_round": 1,            # int — 当前轮次编号
}

for key, val in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = val


# ══════════════════════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════════════════════

def _format_hand_from_mask(mask: int) -> str:
    """从 mask 生成可读手牌，如 '♦A, ♣2, ♥3'"""
    cards = [Card(o // 4, o % 4) for o in range(25) if mask & (1 << o)]
    return ", ".join(str(c) for c in cards)


def _format_player_hands(state: GameState) -> list[str]:
    """返回5个玩家的手牌字符串列表"""
    return [_format_hand_from_mask(state.masks[i]) for i in range(5)]


def _add_log(player: int, action: str, cards: str, remaining: str, note: str = ""):
    """添加操作日志"""
    st.session_state.log.append({
        "player": player,
        "label": "★" if player == 0 else f"玩家{player}",
        "action": action,
        "cards": cards,
        "remaining": remaining,
        "note": note,
    })


def _reset_game():
    """重置游戏状态"""
    for key in DEFAULTS:
        st.session_state[key] = DEFAULTS[key]


# ══════════════════════════════════════════════════════════════════════
# 发牌工具（不创建 GameState，只发牌）
# ══════════════════════════════════════════════════════════════════════

def _deal_only():
    """随机发牌 → 返回 (hands_5, da_owner)。
    hands_5: list[list[Card]]，5个玩家各5张牌，未重排。
    """
    deck = build_deck()
    hands = shuffle_and_deal(deck)

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
# 需求 0：抢A阶段手动选择界面
# ══════════════════════════════════════════════════════════════════════

def show_bid_selection():
    """抢A选择界面：显示所有玩家手牌，测试人员手动选择抢A玩家。"""
    hands = st.session_state.bidding_hands
    info = st.session_state.bidding_info or {}
    config_bidder = info.get("bidder_from_config")

    st.subheader("🎯 抢A阶段 — 选择★玩家")
    st.caption("请查看所有玩家手牌，点击「选择」指定★玩家（抢A者）")

    if config_bidder is not None:
        st.info(f"📋 配置文件中指定抢A玩家：玩家{config_bidder}")

    # 为每个玩家生成选择按钮列
    for i in range(5):
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

    # 确认按钮
    col_btn, _ = st.columns([1, 3])
    with col_btn:
        disabled = st.session_state.bidder_selected is None
        if st.button("✅ 确认抢A", type="primary", use_container_width=True,
                     disabled=disabled, key="confirm_bid"):
            _finalize_bidder()
            st.rerun()


def _finalize_bidder():
    """确认抢A：完成换手(若需要)、重排、创建 GameState、进入游戏。"""
    hands = st.session_state.bidding_hands
    bidder = st.session_state.bidder_selected

    # 找到 ♦A 原始持有者
    da_owner = None
    for i, hand in enumerate(hands):
        for c in hand:
            if c.rank == 0 and c.suit == 0:
                da_owner = i
                break
        if da_owner is not None:
            break

    updated_hands = [list(h) for h in hands]
    # 换手：若 bidder ≠ da_owner，♦A 移给 bidder
    if da_owner is not None and da_owner != bidder:
        updated_hands[da_owner] = [
            c for c in updated_hands[da_owner]
            if not (c.rank == 0 and c.suit == 0)
        ]
        updated_hands[bidder].append(Card(0, 0))
        for hand in updated_hands:
            hand.sort(key=lambda c: c.order)

    # 重排：★ → 索引 0
    reordered = [updated_hands[bidder]] + [
        updated_hands[i] for i in range(5) if i != bidder
    ]
    masks = hands_to_masks(reordered)

    state = GameState(masks=masks, trick=None, turn=0, starter=0)
    st.session_state.state = state
    st.session_state.game_started = True
    st.session_state.log = []
    st.session_state.trick_history = []
    st.session_state.all_trick_history = []
    st.session_state.current_round = 1
    _add_log(-1, "游戏开始", "", "", f"★=原玩家{bidder}")

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
# 需求 3：出牌区历史平铺
# ══════════════════════════════════════════════════════════════════════

def render_trick_history() -> str:
    """渲染全部出牌历史 HTML（跨轮保留，可滚动）。

    遍历 st.session_state.all_trick_history，按轮次分组展示。
    """
    history = st.session_state.all_trick_history
    if not history:
        return (
            '<div class="trick-history">'
            '<span style="color:#888;font-size:0.85rem;">暂无出牌记录</span>'
            '</div>'
        )

    # 按轮次分组
    rounds: dict[int, list[dict]] = {}
    for entry in history:
        r = entry.get("round", 1)
        rounds.setdefault(r, []).append(entry)

    wrappers = []
    for rnd in sorted(rounds.keys()):
        entries = rounds[rnd]
        wrappers.append(
            f'<div style="font-size:0.75rem;color:#64748b;margin:6px 0 2px 0;">'
            f'━━ 第{rnd}轮 ━━</div>'
        )
        for entry in entries:
            player_label = entry.get("label", f"P{entry['player_id']}")
            card_htmls = []
            for o in entry["orders"]:
                card_htmls.append(
                    f'<div class="poker-card" style="margin:0.1rem;">'
                    f'{_card_inner_html(o)}'
                    f'</div>'
                )
            wrappers.append(
                f'<div class="trick-card-wrapper">'
                f'<div class="trick-player-label">{player_label}</div>'
                f'{"".join(card_htmls)}'
                f'</div>'
            )

    return (
        f'<div class="trick-history-scroll">'
        f'<div class="trick-history">{"".join(wrappers)}</div>'
        f'</div>'
    )


def _card_inner_html(order: int) -> str:
    """单张牌的 inner HTML（不含外层 div.poker-card）"""
    rank = order // 4
    suit = order % 4
    rank_str = RANK_NAMES.get(rank, str(rank))
    suit_cls = _SUIT_CLS.get(suit, "")
    suit_html = _SUIT_HTML.get(suit, "")
    return (
        f'<div><div class="rank">{rank_str}</div>'
        f'<div class="suit {suit_cls}">{suit_html}</div></div>'
        f'<div class="suit {suit_cls} suit-bottom">{suit_html}</div>'
    )


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
# 扑克牌可视化渲染函数
# ══════════════════════════════════════════════════════════════════════

# suit 索引 → CSS类名 / HTML实体 映射
_SUIT_CLS = {0: "suit-diamond", 1: "suit-club", 2: "suit-heart", 3: "suit-spade"}
_SUIT_HTML = {0: "&diams;", 1: "&clubs;", 2: "&hearts;", 3: "&spades;"}


def render_card(order: int, selected: bool = False, face_up: bool = True) -> str:
    """渲染单张扑克牌 HTML。

    Args:
        order: 牌的全局序号 (0~24)
        selected: 是否选中态（蓝色边框+阴影）
        face_up: True=明牌, False=牌背

    Returns:
        单张牌的 HTML 字符串
    """
    if not face_up:
        return '<div class="poker-card card-back"><div><div class="rank">?</div></div><div class="suit suit-bottom">?</div></div>'

    rank = order // 4
    suit = order % 4
    rank_str = RANK_NAMES.get(rank, str(rank))
    suit_cls = _SUIT_CLS.get(suit, "")
    suit_html = _SUIT_HTML.get(suit, "")

    cls = "poker-card"
    if selected:
        cls += " selected"

    return (
        f'<div class="{cls}">'
        f'<div><div class="rank">{rank_str}</div>'
        f'<div class="suit {suit_cls}">{suit_html}</div></div>'
        f'<div class="suit {suit_cls} suit-bottom">{suit_html}</div>'
        f'</div>'
    )


def render_hand(mask: int, face_up: bool = True, clickable: bool = False) -> str:
    """渲染一手牌（多张卡片横向排列）。

    Args:
        mask: 25-bit 手牌掩码
        face_up: True=明牌, False=牌背
        clickable: True=卡片可点击（用 st.button 渲染，无跳转）

    Returns:
        clickable=True 时直接渲染并返回空字符串；
        clickable=False 时返回 HTML 字符串。
    """
    if mask == 0:
        return '<div class="hand-container" style="align-items:center;justify-content:center;"><span style="color:#999;font-size:0.9rem;">（无手牌）</span></div>'

    orders = sorted(o for o in range(25) if mask & (1 << o))
    selected_set = set(st.session_state.get("selected_orders", []))

    # ── clickable：透明按钮 + 卡片覆盖（inline style 实现选中上移+放大）──
    if clickable:
        # 外层包裹 div 触发按钮透明 CSS
        st.markdown('<div class="card-hand-area">', unsafe_allow_html=True)
        container = st.container()
        with container:
            cols = st.columns(len(orders), gap="small")
            for idx, o in enumerate(orders):
                with cols[idx]:
                    rank = o // 4
                    suit = o % 4
                    rank_str = RANK_NAMES.get(rank, str(rank))
                    suit_cls = _SUIT_CLS.get(suit, "")
                    suit_html = _SUIT_HTML.get(suit, "")
                    is_sel = o in selected_set

                    # 透明迷你按钮（仅用于捕获点击事件）
                    st.button(
                        label=" ",
                        key=f"card_{o}",
                        on_click=_toggle_card_order,
                        args=(o,),
                        use_container_width=True,
                    )

                    # 卡片覆盖层：负 margin 拉上来盖住按钮
                    # 选中态 → 上移 + 放大 + 蓝框 + 阴影
                    if is_sel:
                        overlay_style = (
                            "margin:-22px auto -6px auto; "
                            "transform:translateY(-8px) scale(1.08); "
                            "border:2px solid #2563eb; "
                            "box-shadow:0 6px 18px rgba(37,99,235,0.45); "
                            "z-index:10; position:relative;"
                        )
                    else:
                        overlay_style = "margin:-22px auto 0 auto; z-index:1; position:relative;"

                    card_html = (
                        f'<div class="poker-card" '
                        f'style="pointer-events:none; box-sizing:border-box; '
                        f'transition:all 0.15s ease; {overlay_style}">'
                        f'<div><div class="rank">{rank_str}</div>'
                        f'<div class="suit {suit_cls}">{suit_html}</div></div>'
                        f'<div class="suit {suit_cls} suit-bottom">{suit_html}</div>'
                        f'</div>'
                    )
                    st.markdown(card_html, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        return ""  # clickable 部分直接渲染，无需返回 HTML

    # ── 非 clickable：保持原有 HTML 渲染 ──
    cards_html = []
    for o in orders:
        card_cls = "poker-card"
        if not face_up:
            card_cls += " card-back"

        if not face_up:
            cards_html.append(
                f'<div class="{card_cls}">'
                f'<div><div class="rank">?</div></div>'
                f'<div class="suit suit-bottom">?</div></div>'
            )
        else:
            rank = o // 4
            suit = o % 4
            rank_str = RANK_NAMES.get(rank, str(rank))
            suit_cls = _SUIT_CLS.get(suit, "")
            suit_html = _SUIT_HTML.get(suit, "")

            cards_html.append(
                f'<div class="{card_cls}">'
                f'<div><div class="rank">{rank_str}</div>'
                f'<div class="suit {suit_cls}">{suit_html}</div></div>'
                f'<div class="suit {suit_cls} suit-bottom">{suit_html}</div>'
                f'</div>'
            )

    wrap_cls = "hand-container desktop-wrap" if face_up else "hand-container"
    return f'<div class="{wrap_cls}">{"".join(cards_html)}</div>'


def render_trick(trick, current_turn: int) -> str:
    """渲染出牌区 HTML。

    Args:
        trick: Trick 对象或 None
        current_turn: 当前出牌人索引 (0~4)

    Returns:
        出牌区 HTML 字符串
    """
    if trick is None:
        return (
            '<div class="trick-area">'
            '<span style="color:#888;font-size:0.95rem;">桌上：无（首出）</span>'
            '</div>'
        )

    trick_type_cn = _TYPE_CN.get(trick.type, trick.type)
    rank_str = RANK_NAMES.get(trick.rank, str(trick.rank))
    suit_cls = _SUIT_CLS.get(trick.top_suit, "")
    suit_html = _SUIT_HTML.get(trick.top_suit, "")

    turn_label = "★" if current_turn == 0 else f"玩家{current_turn}"
    k = {"single": 1, "pair": 2, "triple": 3, "quad": 4}.get(trick.type, 1)

    # 生成 trick 中的 n 张牌（同花色）
    card_htmls = []
    for _ in range(k):
        card_htmls.append(
            f'<div class="poker-card" style="margin:0.15rem;">'
            f'<div><div class="rank">{rank_str}</div>'
            f'<div class="suit {suit_cls}">{suit_html}</div></div>'
            f'<div class="suit {suit_cls} suit-bottom">{suit_html}</div>'
            f'</div>'
        )

    return (
        f'<div class="trick-area">'
        f'<div style="text-align:center;width:100%;">'
        f'<span style="color:#666;font-size:0.85rem;">'
        f'桌上：{trick_type_cn}（由 <span class="trick-player-active">{turn_label}</span> 发起）'
        f'</span>'
        f'</div>'
        f'<div style="display:flex;justify-content:center;flex-wrap:wrap;">'
        f'{"".join(card_htmls)}'
        f'</div>'
        f'</div>'
    )


# ══════════════════════════════════════════════════════════════════════
# 游戏初始化
# ══════════════════════════════════════════════════════════════════════

def init_game_random():
    """随机发牌 + 抢A → GameState（保留向后兼容）"""
    deck = build_deck()
    hands = shuffle_and_deal(deck)

    # 查找 ♦A 持有者
    da_owner = None
    for i, hand in enumerate(hands):
        for c in hand:
            if c.rank == 0 and c.suit == 0:
                da_owner = i
                break
        if da_owner is not None:
            break

    if da_owner is None:
        st.error("发牌错误：♦A 缺失")
        return None

    # 简化：自动让 ♦A 持有者成为★（CLI 需要交互抢A，Web 端自动分配）
    bidder = da_owner
    # 重排：★ → 索引 0
    reordered = [hands[bidder]] + [hands[i] for i in range(5) if i != bidder]
    masks = hands_to_masks(reordered)
    return GameState(masks=masks, trick=None, turn=0, starter=0)


def init_game_from_config(config_path: str, scene_id: int | None) -> GameState | None:
    """从 YAML 配置加载场景（保留向后兼容）"""
    try:
        config_data = load_yaml_config(config_path)
        bidder, hands, info = validate_and_parse_scenario(config_data, scene_id)
    except Exception as e:
        st.error(f"配置加载失败: {e}")
        return None

    # 确定 bidder
    if bidder is None:
        for i, hand in enumerate(hands):
            for c in hand:
                if c.rank == 0 and c.suit == 0:
                    bidder = i
                    break
            if bidder is not None:
                break

    # 换手（若需要）
    da_owner = None
    for i, hand in enumerate(hands):
        for c in hand:
            if c.rank == 0 and c.suit == 0:
                da_owner = i
                break
        if da_owner is not None:
            break

    updated_hands = [list(h) for h in hands]
    if da_owner is not None and da_owner != bidder:
        updated_hands[da_owner] = [
            c for c in updated_hands[da_owner]
            if not (c.rank == 0 and c.suit == 0)
        ]
        updated_hands[bidder].append(Card(0, 0))
        for hand in updated_hands:
            hand.sort(key=lambda c: c.order)

    # 重排：★ → 索引 0
    reordered = [updated_hands[bidder]] + [
        updated_hands[i] for i in range(5) if i != bidder
    ]
    masks = hands_to_masks(reordered)
    return GameState(masks=masks, trick=None, turn=0, starter=0)


# ══════════════════════════════════════════════════════════════════════
# 抢A阶段初始化（prompt14 新增：发牌 → 抢A选择 → 确认 → 创建 GameState）
# ══════════════════════════════════════════════════════════════════════

def _init_bidding_random():
    """随机发牌 → 存入 bidding_hands，进入抢A选择阶段"""
    hands, da_owner = _deal_only()
    if da_owner is None:
        st.error("发牌错误：♦A 缺失")
        return
    _reset_game()
    st.session_state.bidding_hands = hands
    st.session_state.bidding_info = {"bidder_from_config": da_owner}
    st.session_state.bidder_selected = da_owner  # 默认选中 ♦A 持有者


def _init_bidding_from_config(config_path: str, scene_id: int | None):
    """从 YAML 配置加载 → 存入 bidding_hands，进入抢A选择阶段"""
    try:
        config_data = load_yaml_config(config_path)
        bidder, hands, info = validate_and_parse_scenario(config_data, scene_id)
    except Exception as e:
        st.error(f"配置加载失败: {e}")
        return

    # 确定自动 bidder
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
    st.session_state.bidder_selected = auto_bidder  # 默认选中配置指定的


# ══════════════════════════════════════════════════════════════════════
# 模式一：对手 AI 出牌（不依赖 CLI 的 print/input）
# ══════════════════════════════════════════════════════════════════════

def _opponent_play(state: GameState) -> tuple[GameState, str]:
    """对手自动选择最恶毒出牌。返回 (新状态, 日志描述)"""
    player = state.turn
    mask = state.masks[player]
    next_mask = state.masks[(player + 1) % 5]

    if state.trick is None:
        moves = get_legal_moves_free(mask, next_mask)
    else:
        moves = get_legal_moves_response(mask, state.trick, next_mask)

    if not moves:
        ns = advance_turn(state)
        log_str = f"玩家{player} Pass（无牌可出）"
        return ns, log_str

    best_move = None
    for move in moves:
        ns = _apply_move(state, move, player)
        if not solve(ns):
            best_move = move
            break
    if best_move is None:
        best_move = moves[0]

    if len(best_move) == 5:
        _nm, ttype, _rank, _ts, orders = best_move
    else:
        _nm, trick_obj, orders = best_move
        ttype = trick_obj.type

    type_cn = _TYPE_CN.get(ttype, ttype)
    cards_str = format_cards(orders)

    old_trick_existed = state.trick is not None

    ns = _apply_move(state, best_move, player)
    gm = is_global_max(best_move, state.masks)
    if gm:
        ns = GameState(ns.masks, None, player, player)

    # 新轮开始 → 清空本轮历史
    if old_trick_existed and ns.trick is None:
        _start_new_round()

    # 记录出牌历史
    _record_trick_entry(player, orders, type_cn)

    remaining = _format_hand_from_mask(ns.masks[player])
    glob = " 🎯全局最大" if gm else ""
    log_str = f"玩家{player} 出 {cards_str}（{type_cn}）{glob}"

    _add_log(player, "出牌", cards_str, remaining, "全局最大接管" if gm else "")
    return ns, log_str


# ══════════════════════════════════════════════════════════════════════
# 模式二：强制执行对手出牌（不依赖 CLI 的 print）
# ══════════════════════════════════════════════════════════════════════

def _execute_forced_move_web(
    state: GameState, forced_move: tuple
) -> tuple[GameState, str]:
    """强制执行指定 move。返回 (新状态, 日志描述)"""
    player = state.turn

    if len(forced_move) == 5:
        _nm, ttype, _rank, _ts, orders = forced_move
    else:
        _nm, trick_obj, orders = forced_move
        ttype = trick_obj.type

    type_cn = _TYPE_CN.get(ttype, ttype)
    cards_str = format_cards(orders)

    old_trick_existed = state.trick is not None

    ns = _apply_move(state, forced_move, player)
    gm = is_global_max(forced_move, state.masks)
    if gm:
        ns = GameState(ns.masks, None, player, player)

    # 新轮开始 → 清空本轮历史
    if old_trick_existed and ns.trick is None:
        _start_new_round()

    _record_trick_entry(player, orders, type_cn)

    remaining = _format_hand_from_mask(ns.masks[player])
    glob = " 🎯全局最大" if gm else ""
    log_str = f"[强制] 玩家{player} 出 {cards_str}（{type_cn}）{glob}"

    _add_log(player, "强制出牌", cards_str, remaining, "全局最大接管" if gm else "")
    return ns, log_str


# ══════════════════════════════════════════════════════════════════════
# ★ 出牌处理
# ══════════════════════════════════════════════════════════════════════

def _apply_star_move(state: GameState, move: tuple) -> tuple[GameState, str]:
    """★ 打出一手牌。返回 (新状态, 错误信息（空=成功）)"""
    # 兼容两种 move 格式：
    #   自由出牌: (new_mask, type_str, rank, top_suit, [orders])  5-tuple
    #   接力压制: (new_mask, trick_obj, [orders])                 3-tuple
    if len(move) == 5:
        _, ttype, _rank, _top_suit, orders = move
    else:
        _, trick_obj, orders = move
        ttype = trick_obj.type
    cards_str = format_cards(orders)
    type_cn = _TYPE_CN.get(ttype, ttype)

    # 首出 ♦A 验证
    first_play_requires_da = (
        state.trick is None and (state.masks[0] & 1) != 0
    )
    if first_play_requires_da and 0 not in orders:
        return state, "首出必须包含 ♦A（order=0），请重新选择。"

    # 下家独张约束
    next_mask = state.masks[(state.turn + 1) % 5]
    star_mask = state.masks[0]
    if next_mask.bit_count() == 1 and len(orders) == 1:
        max_order = get_max_single(star_mask)
        if orders[0] != max_order:
            rejected_card = Card(orders[0] // 4, orders[0] % 4)
            return state, (
                f"下家只剩一张牌，你必须出最大的单张 "
                f"{format_cards([max_order])}（而非 {rejected_card}）"
            )

    # 判断是否新轮（trick 将被清空 → 新一轮开始，清除历史）
    old_trick_existed = state.trick is not None

    ns = _apply_move(state, move, 0)
    gm = is_global_max(move, state.masks)
    if gm:
        ns = GameState(ns.masks, None, 0, 0)

    # 若旧 trick 存在但新 trick 为 None（全局最大 or 一轮结束）→ 新轮
    if old_trick_existed and ns.trick is None:
        _start_new_round()

    remaining = _format_hand_from_mask(ns.masks[0])
    glob = " 🎯全局最大接管" if gm else ""
    _add_log(0, "出牌", cards_str, remaining, "全局最大接管" if gm else "")

    return ns, ""


# ══════════════════════════════════════════════════════════════════════
# UI 组件
# ══════════════════════════════════════════════════════════════════════

def render_sidebar():
    """侧边栏：模式选择 + 配置加载"""
    with st.sidebar:
        st.header("🎮 夺A快跑")
        st.caption("基于上帝视角的抢A训练工具")

        st.divider()

        # 模式选择
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

        # 配置加载
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

        # 开始按钮
        if not st.session_state.game_started:
            if st.button("🚀 开始游戏", type="primary", use_container_width=True):
                if use_config and config_file:
                    _init_bidding_from_config(config_file, scene_id_input)
                else:
                    _init_bidding_random()
                st.rerun()

        # 重新开始
        if st.session_state.game_started:
            if st.button("🔄 重新开始", use_container_width=True):
                _reset_game()
                st.rerun()


def _on_mode_change():
    st.session_state.mode = st.session_state.mode_selector


def render_game_area():
    """主区域：手机优先 — 垂直堆叠；桌面端 columns 并排"""
    # 抢A选择阶段
    if st.session_state.bidding_hands is not None and not st.session_state.game_started:
        show_bid_selection()
        return

    # 正常游戏
    render_game_state()
    render_interaction()
    render_log()


def render_game_state():
    """主区域：可视化局面（卡片 + 出牌区 + 所有玩家手牌）"""
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

    # ── 出牌区：历史出牌（可滚动）──
    with st.expander("🎴 历史出牌", expanded=True):
        # 当前 trick 简述
        if state.trick:
            trick_type_cn = _TYPE_CN.get(state.trick.type, state.trick.type)
            rank_str = RANK_NAMES.get(state.trick.rank, str(state.trick.rank))
            st.caption(f"桌上：{trick_type_cn} {rank_str}")
        else:
            st.caption("桌上：无（首出）")
        # 全部历史（跨轮保留，可滚动）
        st.markdown(render_trick_history(), unsafe_allow_html=True)

    # ── ★ 出牌控件（放在历史出牌下方、手牌上方）──
    if state.turn == 0:
        winner, game_over = check_terminal(state)
        if not game_over:
            if st.session_state.mode == 1:
                render_star_play(state)
            else:
                render_mode2_star_play(state)

    # ── ★手牌区（可点击选牌）──
    st.markdown('<div class="hand-label star">⭐ ★ 你的手牌（点击选牌）</div>',
                unsafe_allow_html=True)
    st.markdown(render_hand(state.masks[0], face_up=True, clickable=True),
                unsafe_allow_html=True)

    # ── 对手手牌区（训练模式全可见）──
    st.markdown('<div class="hand-label">👤 对手手牌</div>', unsafe_allow_html=True)
    for i in range(1, 5):
        icon = "🏁" if state.masks[i] == 0 else f"P{i}"
        st.markdown(
            f'<div class="hand-label" style="font-weight:400;">{icon} 玩家{i}</div>',
            unsafe_allow_html=True,
        )
        # 训练模式：对手手牌明牌显示
        st.markdown(render_hand(state.masks[i], face_up=True), unsafe_allow_html=True)

    # ── ★ 文字手牌（辅助查看）──
    with st.expander("📝 ★ 手牌文字列表", expanded=False):
        st.write(_format_hand_from_mask(state.masks[0]))

    # ── 模式二静态分析结果 ──
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
            if entry["player"] == -1:
                st.write("--- 🚀 游戏开始 ---")
            elif entry["action"] == "出牌":
                st.write(f"{entry['label']} 出: {entry['cards']} → 剩余 [{entry['remaining']}] {entry['note']}")
            elif entry["action"] == "强制出牌":
                st.write(f"🤖 {entry['label']} [强制] 出: {entry['cards']} → 剩余 [{entry['remaining']}] {entry['note']}")
            elif entry["action"] == "Pass":
                st.write(f"{entry['label']} Pass → 剩余 [{entry['remaining']}]")


def render_interaction():
    """对手交互控件（★ 出牌控件已在 render_game_state 中）"""
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

    # ★ 回合 → 控件已在历史出牌下方
    if state.turn == 0:
        return

    # 对手回合
    if st.session_state.mode == 1:
        _render_opponent_turn(state)
    else:
        _render_mode2_opponent_turn(state)


def _render_opponent_turn(state: GameState):
    """模式一：对手自动出牌按钮"""
    st.write(f"👤 当前：玩家{state.turn} 的回合")
    if st.button("▶ 对手自动出牌", type="primary", use_container_width=True):
        new_state, log_msg = _opponent_play(state)
        st.session_state.state = new_state
        _process_opponent_chain()


def _render_mode2_opponent_turn(state: GameState):
    """模式二：对手强制执行按钮"""
    st.write(f"👤 当前：玩家{state.turn} 的回合（模式二）")

    # 检查是否有★胜招
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
            new_state, _ = _execute_forced_move_web(state, forced_move)
            st.session_state.state = new_state
            st.session_state.current_sequence = [
                (p, m) for p, m in st.session_state.current_sequence
                if not (p == player and m == forced_move)
            ]
            _process_forced_chain()
            st.rerun()
    else:
        st.write(f"玩家{player} 回合（无强制序列）")
        if st.button("▶ 自动出牌", use_container_width=True):
            new_state, _ = _opponent_play(state)
            st.session_state.state = new_state
            _process_opponent_chain()
            st.rerun()


def _process_opponent_chain():
    """处理对手连续出牌链（全局最大接力）"""
    max_chain = 20
    count = 0
    while count < max_chain:
        state = st.session_state.state
        winner, game_over = check_terminal(state)
        if game_over or state.turn == 0:
            break
        new_state, _ = _opponent_play(state)
        st.session_state.state = new_state
        count += 1
    if count >= max_chain:
        st.warning("对手出牌链过长，已截断")


def render_star_play(state: GameState):
    """★ 出牌交互 — 欢乐斗地主式：点击手牌选牌 → 点出牌"""
    st.write("⭐ 你的回合，请选择出牌")

    star_mask = state.masks[0]
    overall, winning_moves_info, losing_moves_info = analyze_moves(state)
    next_mask = state.masks[(state.turn + 1) % 5]

    if state.trick is None:
        all_moves = get_legal_moves_free(star_mask, next_mask)
    else:
        all_moves = get_legal_moves_response(star_mask, state.trick, next_mask)

    if not all_moves:
        st.warning("无牌可出，将自动 Pass")
        if st.button("确认 Pass", key="pass_btn", type="primary", use_container_width=True):
            old_trick = state.trick
            ns = advance_turn(state)
            if old_trick is not None and ns.trick is None:
                _start_new_round()
            st.session_state.state = ns
            remaining = _format_hand_from_mask(ns.masks[0])
            _add_log(0, "Pass", "—", remaining)
            _process_opponent_chain()
            st.rerun()
        return

    # ── 构建合法出牌映射（orders_key → move）──
    winning_set = {tuple(sorted(wm[2])) for wm in winning_moves_info}
    losing_set = {tuple(sorted(lm[2])) for lm in losing_moves_info}
    move_order_map: dict[str, tuple] = {}
    legal_hints = []  # 选牌提示

    for move in all_moves:
        if len(move) == 5:
            _nm, ttype, _rank, _ts, orders = move
        else:
            _nm, trick_obj, orders = move
            ttype = trick_obj.type
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

    # ── 出牌 + 清空按钮（斗地主式：直接点牌+点出牌）──
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        disabled = not can_play_selected
        if st.button("🃏 出牌", type="primary", key="play_btn_main",
                     use_container_width=True, disabled=disabled):
            if can_play_selected:
                move = move_order_map[selected_key]
                _execute_star_play(state, move)
                st.rerun()
            else:
                st.error("请先选择合法出牌组合")
                st.stop()
    with col2:
        if st.button("✕ 清空", key="clear_sel", use_container_width=True):
            st.session_state.selected_orders = []
            st.rerun()
    with col3:
        # Pass 按钮（非首出时可用）
        if st.button("⏭ Pass", key="pass_btn2", use_container_width=True):
            old_trick = state.trick
            ns = advance_turn(state)
            if old_trick is not None and ns.trick is None:
                _start_new_round()
            st.session_state.state = ns
            st.session_state.selected_orders = []
            remaining = _format_hand_from_mask(ns.masks[0])
            _add_log(0, "Pass", "—", remaining)
            _process_opponent_chain()
            st.rerun()

    # ── 出牌选项提示（折叠）──
    with st.expander("📋 合法出牌列表", expanded=False):
        st.write(f"**{overall}**")
        for hint in legal_hints:
            st.write(hint)


def _toggle_card_order(order: int):
    """切换单张牌的选中状态"""
    selected = list(st.session_state.selected_orders)
    if order in selected:
        selected.remove(order)
    else:
        selected.append(order)
    st.session_state.selected_orders = selected
    st.rerun()


def _execute_star_play(state: GameState, move: tuple):
    """执行★出牌 + 记录 trick_history + 对手链"""
    # 提取信息用于记录
    if len(move) == 5:
        _nm, ttype, _rank, _ts, orders = move
    else:
        _nm, trick_obj, orders = move
        ttype = trick_obj.type
    type_cn = _TYPE_CN.get(ttype, ttype)

    new_state, error = _apply_star_move(state, move)
    if error:
        st.error(error)
        st.stop()

    st.session_state.state = new_state
    # 记录出牌历史
    _record_trick_entry(0, orders, type_cn)
    # 清空选牌
    st.session_state.selected_orders = []

    if st.session_state.mode == 2:
        _update_mode2_sequence(new_state)
    _process_opponent_chain()


def _process_forced_chain():
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
            new_state, _ = _execute_forced_move_web(state, forced_move)
            st.session_state.state = new_state
            st.session_state.current_sequence = [
                (p, m) for p, m in st.session_state.current_sequence
                if not (p == player and m == forced_move)
            ]
        else:
            new_state, _ = _opponent_play(state)
            st.session_state.state = new_state
        count += 1
    if count >= max_chain:
        st.warning("链条过长，已截断")


def render_mode2_star_play(state: GameState):
    """模式二的★出牌 — 斗地主式选牌 + 序列分析专用界面"""
    st.write("⭐ 你的回合（模式二·同盟序列分析），请选择出牌")

    star_mask = state.masks[0]
    next_mask = state.masks[(state.turn + 1) % 5]

    if state.trick is None:
        all_moves = get_legal_moves_free(star_mask, next_mask)
    else:
        all_moves = get_legal_moves_response(star_mask, state.trick, next_mask)

    if not all_moves:
        st.warning("无牌可出，将自动 Pass")
        if st.button("确认 Pass", key="pass_btn", type="primary", use_container_width=True):
            old_trick = state.trick
            ns = advance_turn(state)
            if old_trick is not None and ns.trick is None:
                _start_new_round()
            st.session_state.state = ns
            st.session_state.selected_orders = []
            remaining = _format_hand_from_mask(ns.masks[0])
            _add_log(0, "Pass", "—", remaining)
            _process_opponent_chain()
            st.rerun()
        return

    # ── 构建出牌映射 ──
    move_order_map: dict[str, tuple] = {}
    hints = []
    for move in all_moves:
        if len(move) == 5:
            _nm, ttype, _rank, _ts, orders = move
        else:
            _nm, trick_obj, orders = move
            ttype = trick_obj.type
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
                _execute_star_play(state, move)
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
            remaining = _format_hand_from_mask(ns.masks[0])
            _add_log(0, "Pass", "—", remaining)
            _process_opponent_chain()
            st.rerun()

    # ── 出牌选项提示 ──
    with st.expander("📋 合法出牌列表", expanded=False):
        for hint in hints:
            st.write(hint)


def _update_mode2_sequence(state: GameState):
    """模式二：★出牌后更新同盟最优序列"""
    seq = find_best_response(state)
    if seq:
        st.session_state.current_sequence = seq
    else:
        st.session_state.current_sequence = []
        # 检查是否全局最大
        if state.turn != 0:
            pass  # 已被全局最大接管后的状态


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
