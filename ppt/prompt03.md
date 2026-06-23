接上次"夺A快跑"的代码。当前 `game.py` 和 `main.py` 已实现：
- v0.5 全部规则（下家约束、全局最大接管、Pass机制）
- 训练模式一（实时交互）
- 训练模式二基础版（`find_winning_sequence`、`find_best_response`）

**当前 SPEC.md 已更新到 v0.5，但训练模式二存在一个展示层面的缺口：**

当★手牌中有多个A时，可以选择：
- 单张♦A
- 对子（含♦A）
- 三条（含♦A）
- 四条（含♦A）

虽然 `solve(state)` 在数学层面已经穷举了所有含♦A出牌（确保★必败），但 `find_winning_sequence` **只返回一条路径**（moves[0]），没有分别验证和展示★不同含♦A出牌对应的同盟必胜序列。

**请实现以下增强功能：**

---

### Task 1：新增 `enumerate_da_moves(mask) -List[tuple]`

**功能**：枚举★手牌中所有包含♦A（order=0）的合法出牌。

**输入**：★的手牌mask（25-bit）
**输出**：`List[move]`，每个move是合法出牌元组（兼容自由出牌的5-tuple格式）

**实现逻辑**：
1. 调用 `get_legal_moves_free(mask)` 获取所有合法出牌
2. 筛选出包含 order=0（♦A）的move
3. 返回筛选后的列表

**注意**：
- 不修改 `get_legal_moves_free`，只做筛选
- 返回的move格式必须与 `get_legal_moves_free` 一致（5-tuple）

---

### Task 2：新增 `verify_all_da_moves(state) -Dict[str, List[Action]|None]`

**功能**：验证★的每一种含♦A出牌，同盟是否都有必胜序列。

**输入**：GameState（初始状态，turn=0，trick=None）
**输出**：`Dict[str, List[Action]|None]`
- key：出牌描述字符串，如 `"单张: ♦A"`、`"对子: ♦A ♣A"`
- value：同盟必胜序列（List[Action]）或 None（无必胜序列）

**实现逻辑**：
1. 调用 `enumerate_da_moves(state.masks[0])` 获取所有含♦A出牌
2. 对每种出牌：
   - 应用出牌得到新状态 `ns = _apply_move(state, move, 0)`
   - 处理全局最大接管（如果适用）
   - 调用 `find_winning_sequence(ns)` 获取同盟必胜序列
   - 记录结果
3. 返回字典

**边界处理**：
- 如果★只有单张♦A（没有其他含♦A牌型），返回只有一个元素的字典
- 如果某种出牌后同盟无必胜序列，value为None

---

### Task 3：新增 `format_multi_da_verification(result_dict) -str`

**功能**：将多分支验证结果格式化为可读字符串。

**输入**：`verify_all_da_moves` 返回的字典
**输出**：格式化字符串

**输出格式示例**：
```
⚠️ 当前局面同盟有必胜策略！

★ 可选择以下含♦A出牌，同盟均有必胜应对：

【出法1】单张: ♦A
同盟必胜序列：
玩家1 → 出 ♣A（单张）
玩家2 → Pass
...

【出法2】对子: ♦A ♣A
同盟必胜序列：
玩家1 → 出 ♥A+♠A（对子）
...
```

如果存在某种出牌同盟无必胜序列：
```
⚠️ ★ 有胜招！

【出法1】单张: ♦A → 同盟必胜 ✅
【出法2】对子: ♦A ♣A → 同盟无必胜序列 ❌

建议：出对子 ♦A ♣A 可破局！
```

---

### Task 4：修改训练模式二的静态分析阶段

在 `mode2_game_loop(state)` 中：

1. **替换**原来的 `find_winning_sequence` 调用
2. **改为**调用 `verify_all_da_moves(state)`
3. **使用** `format_multi_da_verification` 输出结果
4. **如果**任何含♦A出牌同盟无必胜序列 → 不进入交互验证，直接提示"★有胜招"并退出
5. **只有**所有含♦A出牌同盟都有必胜序列 → 询问是否进入交互验证

---

### Task 5：测试代码

在 `main.py` 中添加一个测试函数 `test_multi_da_verification()`：

**测试场景1**：★手牌有多个A
```
★: [♦A, ♣A, ♥A, ♠A, ♦2]
P1: [♣2, ♥2, ♠2]
P2: [♦3, ♣3, ♥3]
P3: [♦4, ♣4, ♥4]
P4: [♦5, ♣5, ♥5]
```
预期：三种含♦A出牌（单张、对子、三条）都有同盟必胜序列

**测试场景2**：★有胜招
```
★: [♦A, ♣A, ♥2]
P1: [♠A]  # 只有一张A，压制不了对子
...
```
预期：单张♦A → 同盟必胜；对子♦A+♣A → 同盟无必胜序列

---

**要求**：
- 不修改 `solve()`、`find_winning_sequence()`、`find_best_response()` 等现有函数
- 只新增函数，不修改现有逻辑（除了 `mode2_game_loop` 的调用替换）
- 在 `game.py` 中新增函数，在 `main.py` 中添加测试
- 处理全局最大接管（在 Task 2 中）

**验收条件**：
1. `enumerate_da_moves` 正确枚举所有含♦A出牌
2. `verify_all_da_moves` 对每种出牌验证同盟必胜序列
3. 格式化输出清晰，区分不同出牌对应的同盟应对
4. 如果存在★胜招，正确识别和提示
5. 测试场景通过

**运行方式**：
```bash
python main.py --test-multi-da
```