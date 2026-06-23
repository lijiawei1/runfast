接你提供的"夺A快跑"项目（v0.9，已完成核心逻辑模块化拆分：models.py/deck.py/moves.py/solver.py/sequence.py/cli.py/config_loader.py，支持两种训练模式、配置文件加载）。

> 当前需求：生成 Streamlit Web 应用骨架，支持部署到 Streamlit Cloud，不修改核心模块逻辑。

> ---

> ### 核心约束（必须严格遵守）

1. 不修改核心模块：models.py/deck.py/moves.py/solver.py/sequence.py/cli.py/config_loader.py/game.py 的逻辑完全不动（仅 main.py 做最小调整）。

2. UI 层独立：新增 app.py 作为 Streamlit 唯一入口，所有 Web 交互逻辑放在 app.py 中。

3. 状态管理：使用 st.session_state 保存 GameState、current_sequence（训练模式二）、log（操作日志），不依赖全局变量。

4. CLI 兼容性：保留 main.py 的原有 CLI 功能，新增 --web 参数启动 Streamlit（通过 subprocess.run(["streamlit", "run", "app.py"]) 实现）。

> ---

> ### 功能要求（严格对齐 SPEC.md v0.9）

> #### 1. 项目结构（输出时需遵循）

```
runfirst/
├── app.py              # Streamlit 入口（新增，核心输出）
├── game.py             # 核心逻辑聚合导出（不动）
├── models.py           # 数据模型（不动）
├── deck.py             # 牌组/抢A（不动）
├── moves.py            # 牌型识别/合法出牌（不动）
├── solver.py           # 求解器（不动）
├── sequence.py         # 同盟序列分析（不动）
├── cli.py              # CLI交互/强制执行（不动）
├── config_loader.py    # 配置加载（不动）
├── configs/
│   └── hands.yaml      # 预设场景（不动）
├── main.py             # CLI入口（调整：新增--web参数）
├── test_game.py        # 测试（不动）
├── requirements.txt    # 依赖（新增）
└── README.md           # 项目说明（不动）

```

> #### 2. app.py 功能（必须覆盖以下所有点）

- 页面布局：使用 st.columns([2, 1]) 分左右两栏：

  - 左栏（主区域）：显示当前局面（手牌、turn、trick、局面分析✅/❌）、操作日志（可折叠）。

  - 右栏（交互区域）：训练模式选择、配置加载、出牌交互、对手自动按钮。

- 启动逻辑：

  - 侧边栏单选：「训练模式一（实时交互）」/「训练模式二（同盟序列分析）」。

  - 侧边栏「加载配置」按钮：调用 config_loader.py 解析 YAML 文件，交互选择场景（支持 --scene 参数直接指定）。

  - 默认（不加载配置）：随机发牌（调用 deck.py 的发牌逻辑）。

- 训练模式一交互：

  - ★ 回合：显示手牌（格式化字符串），提供文本框输入 order（如 0 或 0 1），点击「出牌」按钮提交；输入非法时显示错误提示（如下家独张约束）。

  - 对手回合：显示「下一步（对手自动）」按钮，点击后调用 cli.py 的对手 AI 逻辑自动出牌。

- 训练模式二交互：

  - 静态分析阶段（★出牌前）：调用 sequence.py 的 verify_all_da_moves，显示多♦A分支验证结果（区分"同盟全必胜"与"★有胜招"两种输出，格式对齐 SPEC.md）。

  - 动态分析阶段（★出牌后）：显示 find_best_response 返回的同盟最优应对序列；对手回合强制执行 current_sequence 中的预计算出牌（调用 cli.py 的 execute_forced_move）。

- 状态管理：

  - st.session_state.state：保存当前 GameState（来自 models.py）。

  - st.session_state.current_sequence：保存训练模式二的强制执行序列（来自 sequence.py 的 find_best_response）。

  - st.session_state.log：保存操作日志（每条记录包含玩家、出牌、剩余手牌），用 st.expander("操作日志") 折叠显示。

- 终局处理：检测到 check_terminal(state) 为 True 时，显示胜利/失败信息（🎉 ★ 获胜！ 或 💀 ★ 失败！）。

> #### 3. main.py 调整（最小改动）

- 新增 --web 命令行参数：当传入时，调用 subprocess.run(["streamlit", "run", "app.py"]) 启动 Streamlit 应用。

- 不传 --web 时：保持原有 CLI 逻辑不变（随机发牌/加载配置/选择训练模式）。

> #### 4. requirements.txt（新增）

```

streamlit>=1.30

pyyaml>=6.0

```

> ---

> ### 验收条件（必须全部满足）

1. 核心逻辑未修改：git diff 显示 models.py/deck.py/moves.py/solver.py/sequence.py/cli.py/config_loader.py/game.py 无任何改动。

2. Streamlit 可运行：streamlit run app.py 启动无报错，页面显示正常。

3. 功能完整：

  - 随机发牌 / 加载 YAML 配置（交互选场景 / --scene 直接指定）均能初始化游戏。

  - 训练模式一切换正常：★输入 order 出牌、对手自动按钮执行 AI 出牌。

  - 训练模式二显示正确：静态阶段多♦A分支验证结果、动态阶段强制执行序列。

  - 下家独张约束、全局最大接管、Pass 逻辑在 Web 端正常触发。

4. 可部署：推送到 GitHub 后，Streamlit Cloud 部署成功（无依赖报错）。

5. 代码整洁：app.py 逻辑清晰，关键步骤有注释，便于后续扩展（如手牌按钮交互）。

> ---

> 请生成完整的 app.py、requirements.txt，并给出 main.py 的调整代码（仅新增 --web 参数部分）。