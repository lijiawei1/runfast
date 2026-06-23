接上次"夺A快跑"的代码。当前 game.py 已实现：

- v0.5 全部规则（下家约束、全局最大接管、Pass机制）

- 训练模式二基础版（find_winning_sequence、verify_all_da_moves、find_best_response）

- 训练模式一完整交互

> 当前问题：

训练模式二能"计算"同盟必胜序列（find_best_response），但没有"强制执行"——对手AI在 _play_opponent_turn 中独立决策，没有使用预计算的序列。

> 结果：虽然数学上★必败，但实际出牌中同盟可能偏离必胜路径，★有可能翻盘。

> 请实现强制执行机制：

> ---

> ### Task 1：新增 execute_forced_move(state: GameState, forced_move: tuple) -> GameState

> 功能：强制玩家按指定的move出牌（用于训练模式二的强制执行）。

> 输入：

- state：当前GameState

- forced_move：预计算的出牌元组（兼容5-tuple和3-tuple）

> 输出：应用出牌后的新GameState

> 实现逻辑：

1. 获取当前玩家 player = state.turn

2. 调用 _apply_move(state, forced_move, player) 应用出牌

3. 处理全局最大接管（若 is_global_max(forced_move, state.masks) 为True）

4. 打印出牌信息和剩余手牌

5. 返回新状态

> ---

> ### Task 2：修改训练模式二主循环 mode2_game_loop(state)

> 修改内容：

> 1. 新增状态追踪：

   ```python

   current_sequence = []  # 当前同盟必胜序列

   ```

> 2. 静态分析阶段（抢A后）：

   - 调用 verify_all_da_moves(state)

   - 若所有含♦A出牌同盟均有必胜序列 → 进入强制执行模式

   - 否则提示"★有胜招"并退出

> 3. 动态分析阶段（游戏循环中）：

>    ★的回合：

   ```python

   if state.turn == 0:

       state = play_turn(state)  # ★正常交互

       # ★出牌后，重新计算同盟最优序列

       current_sequence = find_best_response(state)

       if current_sequence:

           print(format_best_response(current_sequence))

       else:

           print("✅ 此手仍在必胜域内，同盟暂无必胜策略")

   ```

>    对手的回合：

   ```python

   else:

       # 检查是否有强制出牌

       forced_move = None

       for player, move in current_sequence:

           if player == state.turn:

               forced_move = move

               break

>        if forced_move:

           # 强制执行

           state = execute_forced_move(state, forced_move)

           # 从序列中移除已执行的move

           current_sequence = [(p, m) for p, m in current_sequence if p != state.turn]

       else:

           # 无强制序列，正常走

           state = play_turn(state)

   ```

> 4. 全局最大接管处理：

   - 若★出全局最大牌 → 清空 current_sequence

   - 重新计算 current_sequence = find_best_response(state)

> ---

> ### Task 3：在 main.py 中集成新模式

> 修改模式选择逻辑，确保训练模式二使用新的 mode2_game_loop（带强制执行）。

> ---

> 要求：

- 不修改 _play_opponent_turn 的现有逻辑（保持训练模式一不受影响）

- 只在训练模式二中启用强制执行

- 处理边界情况（序列为空、全局最大接管等）

- 打印清晰的执行日志

> 验收条件：

1. 训练模式二中，同盟玩家严格按 find_best_response 返回的序列出牌

2. ★无论怎么出牌，同盟都按最优路径应对

3. 全局最大接管后序列正确重置

4. 训练模式一不受影响

> 测试用例：

```

★手牌：[♦A, ♣A, ♥A, ♠A, ♦2]

同盟必胜序列：[对子♦A♣A → 三条♥A♠A♦2]

★出单张♦A → 同盟强制出对子♣A♥A（序列第一步）

★出对子♦A♣A → 同盟强制出三条♥A♠A♦2（序列第二步）

★败

```

> 运行方式：

```bash

python main.py --mode 2

```

跑通后，训练模式二就从"纸上谈兵"升级为"真刀真枪"了 💪