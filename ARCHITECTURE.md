# 夺A快跑 — 架构现状文档（ARCHITECTURE.md）

> **版本**: v0.11 | **审查日期**: 2026-06-23  
> **性质**: 代码审查 + 依赖梳理（不修改任何代码）  
> **更新**: R6 模块化拆分后刷新

---

## 一、模块职责与接口总览

### 1. `models.py` — 数据模型层

| 项目 | 内容 |
|------|------|
| **职责** | 定义核心数据结构（Card/Trick/GameState）、枚举常量、格式化工具 |
| **对外接口** | `Card`, `Trick`, `GameState`, `RANK_NAMES`, `SUIT_NAMES`, `_TYPE_CN`, `format_cards()`, `_format_hand()` |
| **输入** | 基本类型（int, str, dict） |
| **输出** | `Card` (class), `Trick` (frozen dataclass), `GameState` (frozen dataclass), 格式字符串 |
| **依赖** | `sys` (仅用于 Windows UTF-8 配置), `dataclasses` |
| **被依赖** | 被 **所有模块** 直接导入 |

> ⚠️ **副作用**: 模块级代码执行 `sys.stdout.reconfigure(encoding="utf-8")`，这是一个全局副作用 —— 任何 import models 的模块都会触发 Windows 控制台编码变更。

---

### 2. `deck.py` — 牌组与发牌

| 项目 | 内容 |
|------|------|
| **职责** | 构建25张牌组、洗牌发牌、手牌→mask转换、♦A定位、CLI抢A交互 |
| **对外接口** | `build_deck()`, `shuffle_and_deal()`, `hands_to_masks()`, `find_diamond_a_holder()`, `take_bid()` |
| **输入** | `list[Card]`, `int`（玩家数） |
| **输出** | `list[Card]`（牌组）、`list[list[Card]]`（手牌）、`tuple[int, int, int, int, int]`（5个mask）、`int`（♦A持有者索引） |
| **依赖** | `random`, `models.Card` |
| **被依赖** | `app.py`, `main.py`, `game.py`（聚合） |

> ⚠️ **隐式耦合**: `take_bid()` 使用 `input()` 直接做 CLI 交互，无法在 Web/自动化测试中复用。`app.py` 和测试代码各自实现了独立的抢A逻辑。

---

### 3. `moves.py` — 牌型识别与出牌枚举

| 项目 | 内容 |
|------|------|
| **职责** | 牌型统计（对子/三条/四条）、自由出牌枚举、接力压制枚举、全局最大判定 |
| **对外接口** | `get_counts()`, `find_pairs()`, `find_triples()`, `find_quads()`, `get_all_cards()`, `get_max_single()`, `get_legal_moves_free()`, `get_legal_moves_response()`, `is_global_max()` |
| **输入** | `int` (25-bit mask), `list[Card]`, `Trick`, `tuple` (all_masks), `int | None` (next_player_mask) |
| **输出** | `list[tuple]`（move 元组）、`bool`、`dict[int, int]` |
| **依赖** | `itertools.combinations`, `models.Card`, `models.Trick` |
| **被依赖** | `app.py`, `cli.py`, `solver.py`, `sequence.py`, `main.py`, `game.py` |

> ⚠️ **高耦合点**: `is_global_max()` 接收两种不同格式的 move（3-tuple / 5-tuple），通过 `len(move)` 分支判断 —— 这是典型的"多态通过长度区分"反模式。

---

### 4. `solver.py` — 核心求解器

| 项目 | 内容 |
|------|------|
| **职责** | memoized DFS 求解 ★ 是否必胜（solve）、局面分析（analyze_moves）、状态推进（advance_turn/check_terminal）、出牌应用（_apply_move） |
| **对外接口** | `solve()`, `analyze_moves()`, `advance_turn()`, `check_terminal()`, `_apply_move()` |
| **输入** | `GameState`, `tuple`（move） |
| **输出** | `bool`（solve）、`tuple[bool\|None, list, list]`（analyze_moves）、`GameState`（状态推进函数） |
| **依赖** | `functools.lru_cache`, `models.GameState/Trick/_TYPE_CN/format_cards`, `moves.get_legal_moves_free/get_legal_moves_response/is_global_max` |
| **被依赖** | `app.py`, `cli.py`, `sequence.py`, `main.py`, `game.py` |

> 🔴 **高风险函数**:
> - `_apply_move()`: move 格式通过 `len(move)` 分支（3-tuple vs 5-tuple），与 `moves.py` 的枚举器格式强耦合。
> - `solve()`: 使用 `@lru_cache(maxsize=None)`，状态空间较大时可能耗尽内存。
> - `_solve_star_turn()` 和 `_solve_opponent_turn()`: 两段几乎相同的代码（50%+ 重复），修改一处容易遗漏另一处。

---

### 5. `sequence.py` — 同盟序列分析

| 项目 | 内容 |
|------|------|
| **职责** | 搜索同盟必胜序列、多♦A分支验证、同盟最优应对 |
| **对外接口** | `find_winning_sequence()`, `format_sequence()`, `find_best_response()`, `format_best_response()`, `enumerate_da_moves()`, `verify_all_da_moves()`, `format_multi_da_verification()` |
| **输入** | `GameState`, `int` (mask), `list`（序列）, `dict`（验证结果） |
| **输出** | `list | None`（序列）, `dict`（验证结果）, `str`（格式化） |
| **依赖** | `models.GameState/Trick/_TYPE_CN/format_cards`, `moves.get_legal_moves_free/get_legal_moves_response/is_global_max`, `solver.solve/_apply_move` |
| **被依赖** | `app.py`, `main.py`, `game.py` |

> 🔴 **高风险点**: `_dfs_win_seq()` 中 ★ 回合 "任选第一个 move" 的策略（第84行 `move = moves[0]`）会导致返回的序列不稳定（依赖枚举器的排序），每次运行可能返回不同序列。

---

### 6. `config_loader.py` — 配置加载

| 项目 | 内容 |
|------|------|
| **职责** | YAML 配置文件加载、场景选择、手牌验证、Card 解析 |
| **对外接口** | `SUIT_MAP`, `RANK_MAP`, `parse_card()`, `load_yaml_config()`, `validate_and_parse_scenario()` |
| **输入** | `str` (路径), `dict` (YAML数据), `int | None` (场景ID) |
| **输出** | `Card`, `dict`, `tuple[int, list[list[Card]], dict]`（bidder, hands, info） |
| **依赖** | `os`, `models.Card`, `yaml`（动态导入） |
| **被依赖** | `app.py`, `main.py`, `game.py` |

> ⚠️ **隐式耦合**: `_select_scenario()` 使用 `input()`/`print()` 做 CLI 交互选择场景 —— `app.py` 绕开了此函数，自己实现了场景选择逻辑。

---

### 7. `cli.py` — CLI 交互层

| 项目 | 内容 |
|------|------|
| **职责** | ★回合交互（局面显示、出牌选择、输入验证）、对手回合AI（最恶毒选牌）、强制执行出牌 |
| **对外接口** | `apply_move()`, `play_turn()`, `execute_forced_move()` |
| **输入** | `GameState`, `tuple`（move）, `int`（player） |
| **输出** | `GameState` |
| **依赖** | `models.Card/GameState/Trick/_TYPE_CN/format_cards/_format_hand`, `moves.get_legal_moves_free/get_legal_moves_response/is_global_max/get_max_single`, `solver.solve/_apply_move/analyze_moves/advance_turn` |
| **被依赖** | `game.py`, `main.py` |

> ⚠️ **隐式耦合**: `_play_star_turn()` 大量使用 `print()`/`input()` 做交互 —— 完全没法在 Web 环境复用。`app.py` 完全重写了所有交互逻辑。

---

### 8. `game_engine.py` — 纯规则引擎（🆕 R6 新增）

| 项目 | 内容 |
|------|------|
| **职责** | 无 UI 依赖的纯规则引擎：Move 格式统一、合法出牌过滤、对手最优选牌、全局最大接管 |
| **对外接口** | `get_valid_moves_for_player()`, `get_opponent_best_move()`, `apply_move_with_global_max()`, `first_play_requires_da()` |
| **输入** | `GameState`, `int` (player), `list[Move]` |
| **输出** | `list[Move]`, `Move | None`, `GameState`, `bool` |
| **依赖** | `models.Move/GameState/Trick`, `moves.*`, `solver.solve` |
| **被依赖** | `app_play.py`, `cli.py` |

> ✅ **R6 解决**: 从 `cli.py` 和 `app.py` 提取公共规则逻辑，消除 C2 耦合。

---

### 9. `app_styles.py` — Web UI 样式层（🆕 R6 新增）

| 项目 | 内容 |
|------|------|
| **职责** | Streamlit CSS 注入：手牌卡片样式、出牌按钮、历史出牌区、响应式布局 |
| **对外接口** | `inject_styles()` |
| **依赖** | `streamlit` |
| **被依赖** | `app.py` |

---

### 10. `app_render.py` — Web UI 渲染层（🆕 R6 新增）

| 项目 | 内容 |
|------|------|
| **职责** | 手牌 HTML 渲染、出牌历史格式化、mask→手牌列表转换 |
| **对外接口** | `render_hand()`, `render_trick_history_html()`, `format_hand_from_mask()` |
| **依赖** | `streamlit`, `models.Card/_format_hand`, `moves.get_counts` |
| **被依赖** | `app.py`, `app_play.py` |

---

### 11. `app_play.py` — Web UI 出牌交互层（🆕 R6 新增）

| 项目 | 内容 |
|------|------|
| **职责** | ★ 出牌交互组件、对手回合处理、对手出牌链、卡片排序切换 |
| **对外接口** | `render_star_play()`, `render_opponent_turn()`, `process_opponent_chain()`, `_toggle_card_order()` |
| **依赖** | `streamlit`, `game_engine.*`, `app_render.*`, `models.*`, `moves.*`, `solver.*`, `sequence.*` |
| **被依赖** | `app.py` |

---

### 12. `app.py` — Streamlit Web 应用（R6 精简）

| 项目 | 内容 |
|------|------|
| **职责** | Web UI 编排层：页面布局、会话管理、模式一/二流程调度 |
| **对外接口** | `main()` (Streamlit 入口) |
| **行数** | ~468 行（R6 前 1560 行） |
| **依赖** | `streamlit`, `random`, `models.*`, `deck.*`, `moves.*`, `solver.*`, `sequence.*`, `config_loader.*`, `app_styles.*`, `app_render.*`, `app_play.*`, `game_engine.*` |
| **被依赖** | 无（顶层入口） |

> ✅ **R6 解决**: 拆分为 4 个子模块（styles/render/play/engine），消除与 cli.py 的逻辑重复。

---

### 9. `game.py` — 聚合导出模块

| 项目 | 内容 |
|------|------|
| **职责** | 向后兼容的 re-export 接口，从子模块导入所有公共 API |
| **依赖** | 所有子模块 (models, deck, moves, solver, cli, sequence) |
| **被依赖** | `test_game.py`（旧测试） |

---

### 10. `main.py` — CLI 入口

| 项目 | 内容 |
|------|------|
| **职责** | 命令行参数解析、模式选择、整体流程调度 |
| **依赖** | 几乎所有子模块 + `argparse` |
| **被依赖** | 无（顶层入口） |

> `main.py` 内嵌两个手动测试函数 `test_best_response()` 和 `test_multi_da_verification()`（共170行），占文件约40%，这些测试已迁移到 `tests/test_sequence.py`。

---

### 11. `tests/` — 测试目录（🆕 R6 新增）

| 文件 | 覆盖模块 | 测试数 |
|------|----------|:------:|
| `tests/conftest.py` | 共享 fixture（Card/Trick/GameState 工厂） | — |
| `tests/test_solver.py` | solver.py | ~15 |
| `tests/test_cli.py` | cli.py | ~20 |
| `tests/test_sequence.py` | sequence.py | ~20 |
| `tests/test_config_loader.py` | config_loader.py | ~20 |
| `tests/test_game.py` (根目录) | models/deck/moves/solver | ~41 |

> ✅ **总计 116 个测试，全部通过**（2026-06-23）。所有 core 模块均有测试覆盖。

---

## 二、模块调用关系图

```
                         main.py
                        /   |   \
                       /    |    \
                 deck.py  cli.py  config_loader.py
                  |       / | \        |
                  |      /  |  \       |
                  v     v   v   v      v
                 models.py  moves.py  (YAML)
                   ^   ^    ^   ^
                   |   |    |   |
              solver.py |  sequence.py
                   \    |    /
                    \   |   /
                  game_engine.py ─────────────────┐
                        |                          |
                   ┌────┴─────┐                    |
                   v          v                    |
                cli.py     app_play.py             |
                   |          |  \                 |
                   v          v   v                |
                main.py    app_render.py           |
                              |                    |
                              v                    |
                          app_styles.py            |
                              |                    |
                              v                    v
                           app.py ───> config_loader.py
```

**依赖矩阵**（→ 表示 import）:

| 模块 | models | deck | moves | solver | sequence | cli | config_loader | game_engine | app_* |
|------|:------:|:----:|:-----:|:------:|:--------:|:---:|:-------------:|:-----------:|:-----:|
| `app.py` | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ | ✓ |
| `app_play.py` | ✓ | — | ✓ | ✓ | ✓ | — | — | ✓ | ✓ |
| `app_render.py` | ✓ | — | ✓ | — | — | — | — | — | — |
| `app_styles.py` | — | — | — | — | — | — | — | — | — |
| `game_engine.py` | ✓ | — | ✓ | ✓ | — | — | — | — | — |
| `game.py` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | — |
| `main.py` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | — |
| `cli.py` | ✓ | — | ✓ | ✓ | — | — | — | ✓ | — |
| `sequence.py` | ✓ | — | ✓ | ✓ | — | — | — | — | — |
| `solver.py` | ✓ | — | ✓ | — | — | — | — | — | — |
| `moves.py` | ✓ | — | — | — | — | — | — | — | — |
| `deck.py` | ✓ | — | — | — | — | — | — | — | — |
| `config_loader.py` | ✓ | — | — | — | — | — | — | — | — |

**依赖深度**（层数）:

| 层 | 模块 |
|----|------|
| 0 (叶子) | `models.py` |
| 1 | `deck.py`, `moves.py`, `config_loader.py` |
| 2 | `solver.py` |
| 3 | `game_engine.py`, `sequence.py`, `game.py` |
| 4 | `cli.py`, `app_render.py`, `app_styles.py` |
| 5 (顶层) | `main.py`, `app_play.py`, `app.py` |

---

## 三、隐式耦合点清单（重点！）

### 🔴 高危

| # | 位置 | 问题描述 |
|---|------|----------|
| C1 | `moves.py` ↔ `solver.py` ↔ `cli.py` ↔ `app.py` ↔ `sequence.py` | **move 元组格式耦合**：move 有两种格式（5-tuple 自由出牌 / 3-tuple 接力压制），所有消费方通过 `len(move) == 5` 做分支。~~这种"隐式多态"分散在 6 个文件中~~ → 🟡 **R6 部分缓解**：`models.Move` 类已创建，`cli.py`/`sequence.py`/`game_engine.py` 已迁移，`solver.py` 和 `moves.py` 仍用旧格式。 |
| C3 | `sequence.py:84` | `_dfs_win_seq()` ★ 回合直接取 `moves[0]` 作为序列节点。这不依赖全局状态，但依赖 `get_legal_moves_*` 的内部排序 —— 排序一变，序列结果就变。 |
| C4 | `models.py:7-8` | 模块级全局副作用：`sys.stdout.reconfigure(encoding="utf-8")`。任何 import models 的模块都会触发。如果测试框架或 Web 服务器重定向了 stdout，可能导致异常。 |
| C5 | `solver.py:93-98` / `solver.py:36` | `lru_cache(maxsize=None)` 无上限缓存。在 Web 环境长时间运行且状态空间大时可能 OOM。 |

### 🟡 中危

| # | 位置 | 问题描述 |
|---|------|----------|
| C6 | `deck.py:49` | `take_bid()` 使用全局 `input()` —— CLI 专用，无法在 Web/自动化中复用。 |
| C7 | `config_loader.py:82` | `_select_scenario()` 使用 `input()`/`print()` —— 同样 CLI 专用。 |
| C11 | `test_game.py` 全部 | 通过 `game` 模块导入（而非直接从子模块），如果 `game.py` 做了不当的 re-export，测试可能测到错误的对象。 |
| C12 | `moves.py` 多处 | `_mask_to_cards()` 在 `is_global_max()` 内部被重复调用（对每个 mask 都调用一次），且与 `solver.py` 中的 mask→cards 逻辑隐式重复。 |

### ✅ 已解决（R6）

| # | 位置 | 解法 |
|---|------|------|
| ~~C2~~ | `cli.py` ↔ `app.py` 交互逻辑重复 | → `game_engine.py` 统一封装（`get_opponent_best_move`, `apply_move_with_global_max`, `first_play_requires_da`, `get_valid_moves_for_player`） |
| ~~C8~~ | `app.py` 重实现 deck.py 抢A逻辑 | → `deck.take_bid_logic()` 纯函数，对 CLI 和 Web 复用 |
| ~~C9~~ | 全局最大接管状态构造分散 | → `game_engine.apply_move_with_global_max()` 封装 |
| ~~C10~~ | `main.py` 内嵌测试函数 | → 迁移到 `tests/test_sequence.py` |

---

## 四、代码坏味道总结

### 4.1 重复代码（DRY 违反）

| 代码片段 | 出现位置 | 出现次数 |
|----------|----------|:--------:|
| `if len(move) == 5: ... else: ...` | solver.py, moves.py (残留) | **~10** (R6 大幅减少) |
| ~~`GameState(ns.masks, None, player, player)`~~ | → `game_engine.apply_move_with_global_max()` | ✅ 已消除 |
| ~~首出♦A验证逻辑~~ | → `game_engine.first_play_requires_da()` | ✅ 已消除 |
| ~~下家独张约束检查~~ | → `game_engine.get_valid_moves_for_player()` | ✅ 已消除 |
| ~~对手AI最恶毒选牌~~ | → `game_engine.get_opponent_best_move()` | ✅ 已消除 |
| `_mask_to_cards()` 或等价逻辑 | moves.py, app.py, solver.py | **3+** (减少) |

### 4.2 违反单一职责

- ~~**`app.py`** (1560行)~~ → ✅ **R6 拆分**: `app.py`(468) + `app_styles.py`(230) + `app_render.py`(299) + `app_play.py`(492) + `game_engine.py`(91)
- **`moves.py`** (300行): 混合了牌型识别、出牌枚举、全局最大判定 —— 三者关联但可拆分。
- **`solver.py`** (184行): `_solve_star_turn()` 和 `_solve_opponent_turn()` 高度相似，可提取公共部分。

### 4.3 魔法数字与硬编码

- move 格式通过 len(move) 区分（3 vs 5） — solver.py/moves.py 残留
- `order 0 = ♦A` 硬编码在多处
- `_MAX_SEQ_DEPTH = 200` 硬编码在 sequence.py
- `max_chain = 20` 硬编码在 app_play.py（对手链截断）

---

## 五、测试覆盖评估

### 5.1 已有测试覆盖（R6 后）

| 模块/功能 | 测试文件 | 测试数 | 覆盖质量 |
|-----------|----------|:------:|:--------:|
| 牌型识别/枚举 (moves.py) | `test_game.py` | ~10 | 🟢 良好 |
| 求解器 (solver.py) | `test_game.py` + `tests/test_solver.py` | ~18 | 🟢 良好 |
| 抢A (deck.py) | `test_game.py` | ~3 | 🟢 良好 |
| Pass/牌权/下家约束/全局最大 | `test_game.py` | ~10 | 🟢 良好 |
| 同盟序列 (sequence.py) | `test_game.py` + `tests/test_sequence.py` | ~24 | 🟢 良好 |
| CLI 交互 (cli.py) | `tests/test_cli.py` | ~20 | 🟢 良好 |
| 配置加载 (config_loader.py) | `tests/test_config_loader.py` | ~20 | 🟢 良好 |

### 5.2 ~~零~~ 低测试覆盖

| 模块/功能 | 当前状态 | 风险 |
|-----------|----------|:----:|
| **`app.py` (Web UI)** | ❌ 零覆盖 | 🔴🔴🔴 |
| **`app_play.py`** | ❌ 零覆盖 | 🔴🔴 |
| **`app_render.py`** | ❌ 零覆盖 | 🔴🔴 |
| **`game_engine.py`** | ⚠️ 间接覆盖（通过 cli 测试） | 🟡 |
| **`app_styles.py`** | ❌ 纯 CSS，无需测试 | 🟢 |

### 5.3 覆盖盲区摘要

```
已覆盖模块: models.py, deck.py, moves.py, solver.py, sequence.py, cli.py, config_loader.py
部分覆盖:   game_engine.py（间接通过 cli 测试验证）
零覆盖:     app.py, app_play.py, app_render.py（Web UI 层）
```

---

## 六、高风险标注（🔥 优先修复）

| 优先级 | 问题编号 | 问题简述 | 影响范围 |
|:------:|----------|----------|----------|
| 🔴 P0 | C1 | move 元组格式耦合（solver.py/moves.py 残留） | solver.py, moves.py |
| 🔴 P1 | C5 | `lru_cache(maxsize=None)` 无上限 | solver.py，OOM风险 |
| 🔴 P1 | — | `app.py`/`app_play.py`/`app_render.py` Web UI 零测试 | 3个文件 |
| 🟡 P2 | C6/C7 | `input()` 调用在库模块中 | deck.py, config_loader.py |
| 🟡 P2 | C3 | `_dfs_win_seq()` ★ 回合取 `moves[0]` 不稳定 | sequence.py |
| 🟢 P3 | C11 | `test_game.py` 通过 game 模块导入 | 测试可靠性 |
| 🟢 P3 | C4 | `models.py` 模块级 stdout 副作用 | 全局 |

> ~~P2 `app.py` 1560行单文件~~ ✅ R6 已解决 → 拆分为 5 个模块

---

## 七、下一步建议

1. **P0: 将 solver.py/moves.py 迁移到 Move 类** — 彻底消除 3-tuple/5-tuple 分支
2. **P0: 为 game_engine.py 补独立测试** — 目前仅间接通过 cli 测试覆盖
3. **P1: 为 app_play.py 核心逻辑补测试** — mock streamlit 以测试出牌交互逻辑
4. **P2: 分离 deck.py/config_loader.py 的纯逻辑与 IO** — 消除 `input()` 在库模块中
5. **P2: solver.py 缓存加限** — `lru_cache(maxsize=500000)` 防 OOM
6. **P3: _dfs_win_seq() 确定性排序** — 让序列结果稳定可复现

---

## 八、附录：关键技术债

| 技术债 | 说明 | 建议解法 |
|--------|------|----------|
| ~~Move 格式多态~~ | ~~3-tuple/5-tuple 通过 len 区分~~ | → ✅ `Move` dataclass 已创建，solver/moves 待迁移 |
| ~~app.py / cli.py 重复~~ | ~~游戏规则逻辑在 UI 层重复实现~~ | → ✅ `game_engine.py` 已创建，规则函数化完成 |
| ~~全局最大接管分散~~ | ~~is_global_max() + 手动构造 GameState~~ | → ✅ `game_engine.apply_move_with_global_max()` |
| ~~CLI 函数与核心逻辑混用~~ | ~~take_bid() / _select_scenario() 含 input()~~ | → ✅ `deck.take_bid_logic()` 纯函数分离 |
| 内存风险 | solver 的 `lru_cache(maxsize=None)` | 加上限 `maxsize=500000` 或在特定时机 `cache_clear()` |
| `main.py` 含测试代码 | 170行测试函数在入口文件中 | → ✅ 已迁移到 `tests/test_sequence.py` |
| `models.py` 模块级副作用 | `sys.stdout.reconfigure()` 全局生效 | 移入 `cli.py` 的 `if __name__` 或 `main()` |
