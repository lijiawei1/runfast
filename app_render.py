"""夺A快跑 — Streamlit 牌面可视化渲染

所有 HTML 渲染函数（含 Streamlit 组件渲染），从 app.py 分离。
"""

from __future__ import annotations

import streamlit as st
from models import Card, GameState, Trick, RANK_NAMES, _TYPE_CN, format_cards

# suit 索引 → CSS类名 / HTML实体 映射
_SUIT_CLS = {0: "suit-diamond", 1: "suit-club", 2: "suit-heart", 3: "suit-spade"}
_SUIT_HTML = {0: "&diams;", 1: "&clubs;", 2: "&hearts;", 3: "&spades;"}


# ══════════════════════════════════════════════════════════════════════
# 文本格式化
# ══════════════════════════════════════════════════════════════════════

def format_hand_from_mask(mask: int) -> str:
    """从 mask 生成可读手牌，如 '♦A, ♣2, ♥3'"""
    cards = [Card(o // 4, o % 4) for o in range(52) if mask & (1 << o)]
    return ", ".join(str(c) for c in cards)


def format_player_hands(state: GameState) -> list[str]:
    """返回所有玩家的手牌字符串列表"""
    return [format_hand_from_mask(state.masks[i]) for i in range(state.num_players)]


# ══════════════════════════════════════════════════════════════════════
# 单张牌 HTML 片段
# ══════════════════════════════════════════════════════════════════════

def card_inner_html(order: int) -> str:
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
        return (
            '<div class="poker-card card-back">'
            '<div><div class="rank">?</div></div>'
            '<div class="suit suit-bottom">?</div></div>'
        )

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


# ══════════════════════════════════════════════════════════════════════
# 手牌渲染
# ══════════════════════════════════════════════════════════════════════

def render_hand(
    mask: int,
    face_up: bool = True,
    clickable: bool = False,
    selected_orders: list[int] | None = None,
    toggle_callback: callable | None = None,
) -> str:
    """渲染一手牌（多张卡片横向排列）。

    Args:
        mask: 25-bit 手牌掩码
        face_up: True=明牌, False=牌背
        clickable: True=使用 st.button 渲染可点击卡片
        selected_orders: 已选中的 order 列表（clickable=True 时生效）
        toggle_callback: 点击回调函数（clickable=True 时生效）

    Returns:
        clickable=True 时直接渲染并返回空字符串；
        clickable=False 时返回 HTML 字符串。
    """
    if mask == 0:
        return (
            '<div class="hand-container" style="align-items:center;justify-content:center;">'
            '<span style="color:#999;font-size:0.9rem;">（无手牌）</span></div>'
        )

    orders = sorted(o for o in range(52) if mask & (1 << o))
    selected_set = set(selected_orders or [])

    # ── clickable：st.button(type="tertiary") → 扑克牌样式 + 选中态 ──
    if clickable:
        # 逐卡 CSS：红色花色 + 选中蓝框发光上浮
        extra_css = ""
        for o in orders:
            suit = o % 4
            if suit in (0, 2):  # 红心/方片
                extra_css += (
                    f'button[kind="tertiary"][id*="card_{o}"],'
                    f'button[kind="tertiary"][id*="card_{o}"] p{{'
                    f'color:#d92121!important}}'
                )
        for o in selected_set:
            extra_css += (
                f'button[kind="tertiary"][id*="card_{o}"]{{'
                f'border:2.5px solid #2563eb!important;'
                f'outline-color:rgba(37,99,235,0.4)!important;'
                f'box-shadow:0 0 0 4px rgba(37,99,235,0.15),0 8px 24px rgba(37,99,235,0.4)!important;'
                f'transform:translateY(-10px) scale(1.15)!important;z-index:30!important}}'
            )
        if extra_css:
            st.markdown(f"<style>{extra_css}</style>", unsafe_allow_html=True)

        # 用 columns 横向排卡，紧凑布局
        cols = st.columns(len(orders), gap="small")
        for idx, o in enumerate(orders):
            with cols[idx]:
                rank = o // 4
                suit = o % 4
                rank_str = RANK_NAMES.get(rank, str(rank))
                suit_sym = {0: "♦", 1: "♣", 2: "♥", 3: "♠"}[suit]
                is_sel = o in selected_set
                # 选中时标签加 ✓ 后缀（CSS 选中态失效时的兜底）
                suffix = "\n✓" if is_sel else ""
                st.button(
                    label=f"{rank_str}\n{suit_sym}{suffix}",
                    key=f"card_{o}",
                    on_click=toggle_callback,
                    args=(o,),
                    type="tertiary",
                )
        return ""

    # ── 非 clickable：纯 HTML 渲染 ──
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


# ══════════════════════════════════════════════════════════════════════
# 出牌区渲染
# ══════════════════════════════════════════════════════════════════════

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
# 出牌历史渲染
# ══════════════════════════════════════════════════════════════════════

def render_trick_history_html(history: list[dict]) -> str:
    """渲染全部出牌历史 HTML（跨轮保留，可滚动）。

    遍历传入的 all_trick_history，按轮次分组展示。
    """
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
                    f'{card_inner_html(o)}'
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
