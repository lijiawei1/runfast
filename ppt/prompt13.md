接你提供的"夺A快跑"项目（v0.9，核心模块已拆分完成）和现有 ts.py（包含基础扑克牌CSS样式和动态卡片生成逻辑）。

> 当前需求：参考 ts.py 的基础，补充完善扑克牌可视化方案，集成到 Streamlit app.py 中，不修改任何核心模块。

> ---

> ### 核心约束（必须严格遵守）

1. 不修改核心模块：models.py/deck.py/moves.py/solver.py/sequence.py/cli.py/config_loader.py/game.py 逻辑完全不动。

2. 基于现有 ts.py 扩展：复用已有的 .poker-card CSS 变量和卡片生成逻辑，只新增/补充缺失的部分。

3. 使用 st.markdown(..., unsafe_allow_html=True) 渲染：不引入第三方组件库。

4. 手机优先布局：默认垂直堆叠，桌面端（宽度>768px）使用 st.columns 并排。

5. 状态管理：选牌状态用 st.session_state.selected_orders 存储（order列表），点击手牌toggle选中。

> ---

> ### 现有 ts.py 基础（你已提供）

- 包含 .poker-card 基础CSS（尺寸、颜色、suit样式）

- 包含 @media (max-width: 480px) 移动端适配

- 包含动态生成卡片的Python函数（基础版）

> ### 需要你补充的内容（在 ts.py 基础上新增）

> #### 1. 新增CSS（追加到现有 <style> 中）

必须包含以下样式类：

```css

/ 选中态 /

.poker-card.selected { ... }

/ 牌背（对手手牌） /

.poker-card.card-back { ... }

/ 出牌区容器 /

.trick-area { ... }

/ 当前出牌人高亮 /

.trick-player-active { ... }

/ 手牌区容器（横向滚动） /

.hand-container { ... }

/ 操作按钮 /

.play-btn { ... }

```

具体样式参考之前讨论的尺寸、颜色、交互效果（选中蓝色边框+阴影、牌背渐变蓝、手牌横向滚动等）。

> #### 2. 封装3个核心渲染函数（在 app.py 中实现）

函数签名和职责必须严格对齐：

> ##### render_card(order, selected=False, face_up=True) -> str

- 输入：order（0~24）、selected（是否选中）、face_up（是否明牌）

- 输出：单张扑克牌HTML字符串

- 逻辑：

  - face_up=False → 返回牌背HTML（.card-back）

  - face_up=True → 从order解析rank/suit，生成带点数和花色符号的卡片

  - 根据 selected 添加 .selected 类

  - 复用现有 ts.py 的suit颜色类名（.suit-diamond等）

> ##### render_hand(mask, face_up=True, clickable=False) -> str

- 输入：mask（25-bit手牌）、face_up（是否明牌）、clickable（是否可点击选牌）

- 输出：整手牌的HTML字符串

- 逻辑：

  - 遍历mask中所有牌（0~24位）

  - 对每张牌调用 render_card

  - 用 .hand-container 包裹所有卡片

  - 空手牌显示"（无手牌）"

> ##### render_trick(trick, current_turn) -> str

- 输入：trick（Trick对象或None）、current_turn（当前出牌人）

- 输出：出牌区HTML字符串

- 逻辑：

  - trick is None → 显示"桌上：无（首出）"

  - 否则显示本轮出牌（用 .trick-area 包裹）

  - 当前出牌人添加 .trick-player-active 高亮

> #### 3. 选牌交互逻辑（在 app.py 中实现）

- 初始化：st.session_state.selected_orders = []（如果不存在）

- ★手牌区：调用 render_hand(mask, face_up=True, clickable=True)

- 选牌方式：通过文本输入框输入order（如"0"或"0 1"），点击"出牌"按钮提交

- 出牌后：清空 st.session_state.selected_orders

> #### 4. 手机端布局结构（在 app.py 中实现）

```

顶部栏：当前回合 · 局面分析（✅/❌）

出牌区：st.expander("本轮出牌", expanded=True) → render_trick()

★手牌区：render_hand()（横向滚动）

交互区：order输入框 + "出牌"按钮 + "下一步（对手自动）"按钮

对手手牌区：4个玩家，各调用 render_hand(mask, face_up=False)

```

> ---

> ### 功能要求

1. CSS兼容现有 ts.py：不重写已有样式，只追加新增类。

2. 函数可复用：render_card/render_hand/render_trick 可被多次调用。

3. 交互正确：

  - 选牌状态正确保存/清除

  - 出牌后界面刷新（st.rerun()）

  - 对手自动按钮调用现有 cli.py 的对手逻辑

4. 手机端适配：

  - 手牌横向滚动（overflow-x: auto）

  - 按钮高度≥44px

  - 垂直堆叠布局（手机），columns并排（桌面）

> ---

> ### 验收条件

1. CSS不冲突：新增样式追加到现有 ts.py，不覆盖原有类。

2. 可视化正确：

  - ★手牌显示明牌，可点击选中（蓝色边框）

  - 对手手牌显示牌背（🂠）

  - 出牌区显示正确

3. 交互正常：

  - 输入order出牌，界面更新

  - 点击"下一步"对手自动出牌

  - 训练模式二强制执行序列正常显示

4. 手机端测试：Chrome DevTools 模拟手机端，布局正常、可滚动、按钮可点击。

5. 核心模块未修改：git diff 验证所有核心模块无改动。

> ---

> 请参考 ts.py 基础，生成完整的补充CSS代码、以及 app.py 中新增的渲染函数和交互逻辑（不包含核心模块修改）。