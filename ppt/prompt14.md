接你提供的"夺A快跑"项目 app.py 代码和当前界面截图。

> 当前问题：render_hand(mask, face_up=True, clickable=True) 用 st.button 渲染可点击手牌时，按钮的原生样式覆盖了 .poker-card 的 CSS，导致：

1. 卡牌不像对手手牌区域（P1/P2）那样清晰显示为扑克牌

2. 选中态（translateY + scale）视觉效果不明显

3. 界面截图显示★手牌区只有一张类似按钮的元素，而非扑克牌卡片

> ---

> ### 修复目标

让 clickable=True 的手牌视觉上和对手手牌区（P1/P2 的 render_hand(..., clickable=False)）完全一致，同时保留 st.button 的点击交互能力。

> 具体要求：

1. 卡片外观：和对手手牌区一模一样（白底、圆角、点数在上、花色在下、横向排列）

2. 选中态：点击后卡片 向上平移 8px + 放大 1.05 倍 + 蓝色边框 + 阴影

3. 取消选中：再次点击恢复原状

4. 旁边有出牌按钮：选中卡片后，旁边出现"出牌"按钮，点击后执行出牌

> ---

> ### 实现方案

> #### Step 1：添加按钮重置 CSS（关键！）

在现有 <style> 中追加：

```css

/ 让 st.button 变成"透明壳"，内部显示扑克卡片 /

div[data-testid="stButton"] button {

    background: transparent !important;

    border: none !important;

    padding: 0 !important;

    box-shadow: none !important;

    min-height: 0 !important;

    width: 100% !important;

}

div[data-testid="stButton"] button p {

    margin: 0 !important;

    font-size: inherit !important;

    color: inherit !important;

}

/ 按钮内的卡片容器 /

div[data-testid="stButton"] .poker-card {

    width: 100% !important;

    height: 100% !important;

}

```

> #### Step 2：修改 render_hand 的 clickable 分支

用 st.button，label 传入纯空格（让按钮不可见），但按钮内部通过 unsafe_allow_html=True 的兄弟元素显示卡片。

> 更好的方案：用 st.button 的 label 直接传扑克牌的 HTML 字符串（包含完整的 .poker-card DOM），配合 Step 1 的 CSS 让按钮透明。

> 具体实现：

```python

if clickable:

    container = st.container()

    with container:

        cols = st.columns(len(orders))

        for idx, o in enumerate(orders):

            with cols[idx]:

                rank = o // 4

                suit = o % 4

                rank_str = RANK_NAMES.get(rank, str(rank))

                suit_cls = _SUIT_CLS.get(suit, "")

                suit_html = _SUIT_HTML.get(suit, "")

                is_sel = o in selected_set

                btn_type = "primary" if is_sel else "secondary"

>                 # label 用空格（不可见），真正的内容靠 CSS 让卡片显示

                # 用 key 区分，on_click 回调

                st.button(

                    label=" ",

                    key=f"card_{o}",

                    type=btn_type,

                    on_click=_toggle_card_order,

                    args=(o,),

                    use_container_width=True,

                )

                # 在按钮下方用 markdown 叠加卡片（绝对定位 or 负 margin 覆盖）

                card_html = f'''

                <div class="poker-card {"selected" if is_sel else ""}" style="

                    margin: -44px 0 0 0;

                    pointer-events: none;

                ">

                    <div><div class="rank">{rank_str}</div>

                    <div class="suit {suit_cls}">{suit_html}</div></div>

                    <div class="suit {suit_cls} suit-bottom">{suit_html}</div>

                </div>

                '''

                st.markdown(card_html, unsafe_allow_html=True)

    return ""

```

> 注意：上面用负 margin 让卡片覆盖在透明按钮上方，pointer-events: none 让点击穿透到按钮。

> #### Step 3：确保选中态 CSS 生效

确认 .poker-card.selected 已有：

```css

.poker-card.selected {

    transform: translateY(-8px) scale(1.05);

    border: 2px solid #2563eb !important;

    box-shadow: 0 4px 12px rgba(37,99,235,0.4) !important;

    transition: all 0.15s ease;

}

```

> 由于按钮是透明的，.selected 的样式会直接作用到可见的卡片上。

> #### Step 4：出牌按钮放在手牌区下方（独立，不跟卡片混在一起）

在 render_star_play 中，卡片区域下方放置"出牌"按钮：

```python

if selected_set:

    col1, col2 = st.columns([1, 1])

    with col1:

        if st.button("🃏 出牌", type="primary", key="play_cards", use_container_width=True):

            # 用 selected_orders 执行出牌

            ...

    with col2:

        if st.button("✕ 清空", key="clear_sel", use_container_width=True):

            st.session_state.selected_orders = []

            st.rerun()

```

> ---

> ### 验收条件

1. 视觉一致性：★手牌区和对手手牌区（P1/P2）的卡片外观完全一致（白底、圆角、点数、花色）

2. 选中效果明显：点击后卡片上移 + 放大 + 蓝色边框，肉眼清晰可见

3. 取消选中：再次点击恢复原状

4. 出牌按钮独立：不在卡片上，在手牌区下方，点击后正确执行出牌

5. 不修改核心模块：git diff 验证

6. 手机端测试：Chrome DevTools 模拟，交互正常

这个方案的核心技巧是 "按钮透明化 + 卡片叠加"——既保留了 st.button 的点击事件（不走 query_params，不会跳转），又让视觉上呈现完整的扑克牌样式。你跑通后截图给我看 🫡