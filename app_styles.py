"""夺A快跑 — Streamlit CSS 样式

纯字符串常量，无副作用。
"""

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

/* ── 手牌区：st.button(type="tertiary") 塑形成 poker-card ── */

button[kind="tertiary"] {
    /* ── 卡牌尺寸与形状 ── */
    width: 3.2rem !important;
    height: 4.8rem !important;
    min-height: 0 !important;
    padding: 5px 6px !important;
    margin: 3px !important;
    border-radius: 5px !important;

    /* ── 卡牌底色：米白仿纸质纹理 ── */
    background:
        linear-gradient(145deg, #fffef5 0%, #fcf9f0 40%, #f7f3e8 100%) !important;
    border: 1px solid #c4bfb4 !important;
    box-shadow:
        0 2px 4px rgba(0,0,0,0.08),
        0 1px 0 rgba(255,255,255,0.6) inset,
        0 -1px 0 rgba(0,0,0,0.04) inset !important;

    /* ── 内边框（卡牌装饰线）── */
    outline: 1px solid rgba(180,170,155,0.25) !important;
    outline-offset: -4px !important;

    /* ── 排版 ── */
    font-family: "Georgia", "Noto Serif", "Times New Roman", serif !important;
    font-size: 1.22rem !important;
    font-weight: 700 !important;
    line-height: 1.15 !important;
    white-space: pre-line !important;
    color: #1a1a1a !important;

    /* ── 布局：文字靠左上，模仿真牌 rank+suit 布局 ── */
    display: inline-flex !important;
    flex-direction: column !important;
    justify-content: flex-start !important;
    align-items: flex-start !important;

    /* ── 交互 ── */
    cursor: pointer !important;
    user-select: none !important;
    position: relative !important;
    transition: all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1) !important;
}

/* ── 按钮内层 div / p 标签排版 ── */
button[kind="tertiary"] div,
button[kind="tertiary"] p {
    margin: 0 !important;
    padding: 0 !important;
    font-family: inherit !important;
    font-weight: inherit !important;
    line-height: 1.15 !important;
    text-align: left !important;
    width: 100% !important;
    overflow: visible !important;
}

/* 第一行（rank）略大 */
button[kind="tertiary"] p {
    font-size: 1.22rem !important;
    letter-spacing: -0.02em !important;
}

/* ── 悬停：微上浮 + 加深阴影 ── */
button[kind="tertiary"]:hover:not(:disabled) {
    transform: translateY(-3px) !important;
    box-shadow:
        0 6px 16px rgba(0,0,0,0.12),
        0 1px 0 rgba(255,255,255,0.6) inset !important;
    border-color: #b0a99c !important;
}

/* ── 按下：微缩回 ── */
button[kind="tertiary"]:active:not(:disabled) {
    transform: translateY(-1px) scale(0.97) !important;
    box-shadow: 0 1px 2px rgba(0,0,0,0.1) !important;
    transition: all 0.1s ease !important;
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
    margin-top: 0.4rem;
}
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

/* ── 移动端适配（6寸屏为主，不再为超小屏缩尺寸）── */
@media (max-width: 640px) {
    .poker-card {
        width: 2.6rem;
        height: 3.9rem;
        padding: 0.2rem;
    }
    .poker-card .suit { font-size: 1.1rem; }
    .poker-card .rank { font-size: 0.95rem; }
    button[kind="tertiary"] {
        width: 2.6rem !important;
        height: 3.9rem !important;
        font-size: 1.0rem !important;
        padding: 3px 4px !important;
        outline-offset: -3px !important;
    }
    button[kind="tertiary"] p { font-size: 1.0rem !important; }
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


def inject_styles():
    """向当前 Streamlit 页面注入 CSS 样式。"""
    import streamlit as st
    st.markdown(CSS_CODE, unsafe_allow_html=True)
