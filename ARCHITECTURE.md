# 夺A快跑 — 架构现状文档（ARCHITECTURE.md）

> **版本**: v0.10 | **审查日期**: 2026-06-23  
> **性质**: 代码审查 + 依赖梳理（不修改任何代码）

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

### 8. `app.py` — Streamlit Web 应用

| 项目 | 内容 |
|------|------|
| **职责** | Web UI：可视化手牌、出牌交互、模式一/二流程、历史出牌展示、抢A阶段界面 |
| **对外接口** | `main()` (Streamlit 入口) |
| **依赖** | `streamlit`, `random`, `models.*`, `deck.*`, `moves.*`, `solver.*`, `sequence.*`, `config_loader.*` |
| **被依赖** | 无（顶层入口） |

> 🔴 **高风险模块**:
> - 代码量 1560 行（项目最长文件），与 `cli.py` 存在大量逻辑重复：
>   - 对手AI出牌逻辑：`_opponent_play()` (app.py 第853行) ≈ `_play_opponent_turn()` (cli.py 第192行)
>   - 全局最大接管：多处出现 `GameState(ns.masks, None, player, player)` 硬编码
>   - 首出♦A验证：`app.py` 第967行 与 `cli.py` 第122行 逻辑重复
>   - 下家独张约束：`app.py` 第976行 与 `cli.py` 第174行 逻辑重复
>   - move 格式解析：`if len(move) == 5` 分支在 app.py 中出现 **8次以上**，在 cli.py 中出现 **4次以上**
> - `_finalize_bidder()` (app.py) 完全重实现了 `deck.py` 的 `take_bid()` 逻辑（换手/排序/重排），且 `build_deck()`/`shuffle_and_deal()`/`hands_to_masks()` 在 app.py 内有自己的副本

---

### 9. `game.py` — 聚合导出模块

| 项目 | 内容 |
|------|------|
| **职责** | 向后兼容的 re-export 接口，从子模块导入所有公共 API |
| **依赖** | 所有子模块 (models, deck, moves, solver, cli, sequence) |
| **被依赖** | `test_game.py` |

> `test_game.py` 从 `game` 导入（而非直接从子模块），说明测试仍在用旧接口。

---

### 10. `main.py` — CLI 入口

| 项目 | 内容 |
|------|------|
| **职责** | 命令行参数解析、模式选择、整体流程调度 |
| **依赖** | 几乎所有子模块 + `argparse` |
| **被依赖** | 无（顶层入口） |

> `main.py` 内嵌两个手动测试函数 `test_best_response()` 和 `test_multi_da_verification()`（共170行），占文件约40%，这些测试应该迁移到 `test_game.py`。

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
                app.py ------> config_loader.py
```

**依赖矩阵**（→ 表示 import）:

| 模块 | models | deck | moves | solver | sequence | cli | config_loader | game |
|------|:------:|:----:|:-----:|:------:|:--------:|:---:|:-------------:|:----:|
| `game.py` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | — |
| `main.py` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| `app.py` | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | — |
| `cli.py` | ✓ | — | ✓ | ✓ | — | — | — | — |
| `sequence.py` | ✓ | — | ✓ | ✓ | — | — | — | — |
| `solver.py` | ✓ | — | ✓ | — | — | — | — | — |
| `moves.py` | ✓ | — | — | — | — | — | — | — |
| `deck.py` | ✓ | — | — | — | — | — | — | — |
| `config_loader.py` | ✓ | — | — | — | — | — | — | — |

**依赖深度**（层数）:

| 层 | 模块 |
|----|------|
| 0 (叶子) | `models.py` |
| 1 | `deck.py`, `moves.py`, `config_loader.py` |
| 2 | `solver.py` |
| 3 | `cli.py`, `sequence.py`, `game.py` |
| 4 (顶层) | `main.py`, `app.py` |

---

## 三、隐式耦合点清单（重点！）

### 🔴 高危

| # | 位置 | 问题描述 |
|---|------|----------|
| C1 | `moves.py` ↔ `solver.py` ↔ `cli.py` ↔ `app.py` ↔ `sequence.py` | **move 元组格式耦合**：move 有两种格式（5-tuple 自由出牌 / 3-tuple 接力压制），所有消费方通过 `len(move) == 5` 做分支。这种"隐式多态"分散在 6 个文件中，若需要新增第三种格式，将导致连锁修改。 |
| C2 | `cli.py` ↔ `app.py` | **交互逻辑重复**：对手AI出牌、首出♦A验证、下家独张约束、全局最大接管处理，这些逻辑在 `cli.py` 和 `app.py` 中各实现了一遍，真正的"改一处牵全身"。修改下家约束规则时需要同时改两处。 |
| C3 | `sequence.py:84` | `_dfs_win_seq()` ★ 回合直接取 `moves[0]` 作为序列节点。这不依赖全局状态，但依赖 `get_legal_moves_*` 的内部排序 —— 排序一变，序列结果就变。 |
| C4 | `models.py:7-8` | 模块级全局副作用：`sys.stdout.reconfigure(encoding="utf-8")`。任何 import models 的模块都会触发。如果测试框架或 Web 服务器重定向了 stdout，可能导致异常。 |
| C5 | `solver.py:93-98` / `solver.py:36` | `lru_cache(maxsize=None)` 无上限缓存。在 Web 环境长时间运行且状态空间大时可能 OOM。 |

### 🟡 中危

| # | 位置 | 问题描述 |
|---|------|----------|
| C6 | `deck.py:49` | `take_bid()` 使用全局 `input()` —— CLI 专用，无法在 Web/自动化中复用。 |
| C7 | `config_loader.py:82` | `_select_scenario()` 使用 `input()`/`print()` —— 同样 CLI 专用。 |
| C8 | `app.py` 多处 | `_finalize_bidder()` 重复了 `deck.py` `take_bid()` 的换手/排序/重排逻辑，且 `_init_bidding_random()` / `_init_bidding_from_config()` 内部各自重复了发牌/配置加载逻辑。 |
| C9 | `app.py` 多处 | `is_global_max()` 调用后手动 `GameState(ns.masks, None, player, player)` —— 这个"全局最大接管"状态构造分散在 app.py 中至少 6 处，cli.py 中 2 处。应封装为 `solver.py` 的一个函数（或 Strategy 模式）。 |

### 🟢 低危

| # | 位置 | 问题描述 |
|---|------|----------|
| C10 | `main.py:259-453` | 内嵌测试函数（`test_best_response()`, `test_multi_da_verification()`）在入口文件中，不应属于 `main.py` 的职责。 |
| C11 | `test_game.py` 全部 | 通过 `game` 模块导入（而非直接从子模块），如果 `game.py` 做了不当的 re-export，测试可能测到错误的对象。 |
| C12 | `moves.py` 多处 | `_mask_to_cards()` 在 `is_global_max()` 内部被重复调用（对每个 mask 都调用一次），且与 `solver.py` 中的 mask→cards 逻辑隐式重复。 |

---

## 四、代码坏味道总结

### 4.1 重复代码（DRY 违反）

| 代码片段 | 出现位置 | 出现次数 |
|----------|----------|:--------:|
| `if len(move) == 5: ... else: ...` | app.py, cli.py, solver.py, sequence.py, moves.py | **20+** |
| `GameState(ns.masks, None, player, player)` | app.py, cli.py, sequence.py, main.py | **10+** |
| 首出♦A验证逻辑 (`state.trick is None and (mask & 1)`) | app.py, cli.py | 2 |
| 下家独张约束检查 | app.py, cli.py | 2 |
| 对手AI最恶毒选牌 (`for move in moves: ns=..., if not solve(ns): best=move`) | app.py, cli.py, main.py | 3 |
| move 信息提取后格式化 (`type_cn + cards_str`) | app.py, cli.py, sequence.py | **8+** |
| `_mask_to_cards()` 或等价逻辑 | moves.py, app.py, solver.py, cli.py | **5+** |

### 4.2 违反单一职责

- **`app.py`** (1560行): 同时包含 UI 渲染、CSS、对手AI、抢A逻辑、出牌验证、操作日志 —— 应拆分为 UI 组件、游戏逻辑、CSS 三个模块。
- **`moves.py`** (300行): 混合了牌型识别、出牌枚举、全局最大判定 —— 三者关联但可拆分。
- **`solver.py`** (184行): `_solve_star_turn()` 和 `_solve_opponent_turn()` 高度相似，可提取公共部分。

### 4.3 魔法数字与硬编码

- move 格式通过 len(move) 区分（3 vs 5）
- `order 0 = ♦A` 硬编码在多处
- `_MAX_SEQ_DEPTH = 200` 硬编码在 sequence.py
- `max_chain = 20` 硬编码在 app.py（对手链截断）

---

## 五、测试覆盖评估

### 5.1 已有测试覆盖

| 模块/功能 | 测试函数 | 覆盖质量 |
|-----------|----------|:--------:|
| 牌型识别 (moves.py) | `test_hand_analysis()` | 🟢 良好 |
| 自由出牌枚举 (moves.py) | `test_free_moves()` | 🟢 良好（含断言） |
| 接力压制枚举 (moves.py) | `test_response_moves()` | 🟢 良好（3子场景） |
| 求解器 (solver.py) | `test_solver()` | 🟢 良好（3场景，含cache检查） |
| 抢A (deck.py) | `test_bid_case0/1/2()` | 🟢 良好 |
| Pass 机制 | `test_pass_scenario()` | 🟡 一般（1个场景） |
| 牌权传递 | `test_card_power_transfer()`, `test_card_power_via_solver()` | 🟢 良好 |
| 下家独张约束 (moves.py) | `test_next_player_single_card()` | 🟢 良好（4子场景） |
| 全局最大判定 (moves.py) | `test_global_max_direct()` | 🟢 良好（5子场景） |
| 全局最大 trick 清空 | `test_global_max_trick_cleared()` | 🟢 良好（3子场景） |
| 同盟必胜序列 (sequence.py) | `test_find_winning_sequence()` | 🟢 良好（4子场景） |
| 同盟最优应对 (sequence.py) | `test_find_best_response()` | 🟢 良好（5子场景） |
| 边界条件 | `test_boundary_cases()` | 🟢 良好（7子场景） |

### 5.2 零测试覆盖（🔴 高风险模块）

| 模块/功能 | 当前状态 | 风险 |
|-----------|----------|:----:|
| **`app.py` (Web UI)** | ❌ 零覆盖 | 🔴🔴🔴 |
| **`config_loader.py`** | ❌ 零覆盖 | 🔴🔴 |
| **`cli.py` (CLI 交互)** | ❌ 零覆盖 | 🔴🔴 |
| **回合调度 `play_turn()`** | ❌ 零覆盖（仅在 main.py 循环中调用） | 🔴 |
| **`analyze_moves()`** | ❌ 零覆盖（仅 CLI/Web 调用） | 🟡 |
| **`advance_turn()` 独立测试** | ❌ 零覆盖（仅在 Pass 测试中间接调用） | 🟡 |
| **`check_terminal()` 独立测试** | ❌ 零覆盖（仅在 Web 端调用） | 🟡 |
| **多♦A分支验证 (sequence.py)** | ❌ 零覆盖在 test_game.py | 🟡 |
| **format_* 函数族** | ⚠️ 间接覆盖（通过序列测试验证格式输出） | 🟢 |

### 5.3 覆盖盲区摘要

```
已覆盖模块: models.py, deck.py, moves.py, solver.py (核心逻辑)
部分覆盖:   sequence.py (序列搜索已测，format/verify 函数间接覆盖)
零覆盖:     config_loader.py, cli.py, app.py
```

---

## 六、高风险标注（🔥 优先修复）

| 优先级 | 问题编号 | 问题简述 | 影响范围 |
|:------:|----------|----------|----------|
| 🔴 P0 | C1 | move 元组格式耦合（3-tuple vs 5-tuple） | **全局**，6个文件 |
| 🔴 P0 | C2 | `cli.py` 与 `app.py` 游戏逻辑重复 | 2个文件，修一处忘一处 |
| 🔴 P1 | C5 | `lru_cache(maxsize=None)` 无上限 | solver.py，OOM风险 |
| 🔴 P1 | C9 | 全局最大接管逻辑分散 | 至少 6 处 |
| 🟡 P2 | C8 | app.py 重实现 deck.py 的抢A/发牌逻辑 | app.py |
| 🟡 P2 | C6/C7 | `input()` 调用在库模块中 | deck.py, config_loader.py |
| 🟡 P2 | — | `app.py` 1560行单文件 | 可维护性 |
| 🟢 P3 | C10 | `main.py` 内嵌测试函数 | 入口清晰度 |
| 🟢 P3 | C11 | `test_game.py` 通过 game 模块导入 | 测试可靠性 |

---

## 七、为对话B（补测试）的优先级建议

按风险和收益排序：

1. **P0: 为 `config_loader.py` 补测试**  
   — 涉及 YAML 解析、场景验证、Card 解析，是功能正确性的基础。

2. **P0: 为 `cli.py` 核心函数补测试**  
   — `play_turn()` 中的 `_play_star_turn()` 和 `_play_opponent_turn()` 可通过 mock `input()`/`print()` 测试（参考 test_game.py 中 `_simulate_bid()` 的做法）。

3. **P1: 新增 `analyze_moves()` 复用验证**  
   — `analyze_moves()` 被 CLI 和 Web 双重调用，但它本身无直接测试。补上后能同时保护两端。

4. **P1: 新增 move 格式转换的 unit test**  
   — 覆盖两种 move 格式（free/response）在 `_apply_move()`、`is_global_max()`、`format_*()` 中的正确性。

5. **P1: 为 `advance_turn()` 和 `check_terminal()` 补独立测试**  
   — 目前仅在其他测试中附带调用。

6. **P2: 为 `sequence.py` 的 format 函数和 verify 函数补独立测试**  
   — `enumerate_da_moves()` / `verify_all_da_moves()` 目前仅在 `main.py` 内嵌测试中覆盖。

7. **P3: 为 `find_best_response()` 的空列表/None 边界补测试**  
   — 当前已有基本覆盖，补充极端手牌分布场景。

---

## 八、附录：关键技术债

| 技术债 | 说明 | 建议解法 |
|--------|------|----------|
| Move 格式多态 | 3-tuple/5-tuple 通过 len 区分 | 封装为 `Move` dataclass 或 NamedTuple，提供统一接口 |
| app.py / cli.py 重复 | 游戏规则逻辑在 UI 层重复实现 | 抽取 `game_engine.py`，将规则判断函数化 |
| 全局最大接管分散 | `is_global_max()` + 手动构造 `GameState` | 在 `solver.py` 新增 `apply_move_with_global_max()` 封装 |
| CLI 函数与核心逻辑混用 | `take_bid()` / `_select_scenario()` 含 `input()` | 分离纯逻辑和 IO：`take_bid_logic()` + `take_bid_cli()` |
| 内存风险 | solver 的 `lru_cache(maxsize=None)` | 加上限 `maxsize=500000` 或在特定时机 `cache_clear()` |
| `main.py` 含测试代码 | 170行测试函数在入口文件中 | 迁移到 `test_game.py` |
| `models.py` 模块级副作用 | `sys.stdout.reconfigure()` 全局生效 | 移入 `cli.py` 的 `if __name__` 或 `main()` |
