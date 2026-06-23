需求列表

### 问题:

- 问题：抢A玩家首轮出牌的可选出牌列表应该是只包含方片A的牌型，前面的符号没有正确反映能出与不能出

```
📊 静态分析：分析同盟必胜序列...
✅ ★ 必胜，同盟无必胜序列。
进入交互出牌模式...

当前回合：★
📊 局面分析：✅ ★必胜
> ★ 手牌：[♦A, ♠A, ♦4, ♣4, ♥5, ♠5]
桌上：无（首出）

> 可选出牌：
  ❌ 单张: ♦A  [0]
  ❌ 单张: ♠A  [3]
  ✅ 对子: ♦A ♠A  [0, 3]
  ❌ 单张: ♦4  [12]
  ❌ 单张: ♣4  [13]
  ❌ 对子: ♦4 ♣4  [12, 13]
  ❌ 单张: ♥5  [18]
  ❌ 单张: ♠5  [19]
  ❌ 对子: ♥5 ♠5  [18, 19]
```

### 优化1:

小优化：对于含♦A出牌，[【出法2】对子: ♦A ♣A] 与 [【出法3】对子: ♦A ♥A] 是一种等价情况，以为同点数已经没有同牌型可出了，可以合并
```
📊 静态分析：分析每种含♦A出牌的同盟必胜序列...
⚠️ 当前局面同盟有必胜策略！

★ 可选择以下含♦A出牌，同盟均有必胜应对：

【出法1】单张: ♦A
同盟必胜序列：
  玩家1 → 出 ♠A（单张）
  玩家2 → 出 ♦2（单张）
  玩家3 → 出 ♣2（单张）
  玩家4 → 出 ♥3（单张）
  ★ → 出 ♦4（单张）
  玩家1 → 出 ♣5（单张）
  玩家2 → 出 ♦7（单张）
  玩家2 → 出 ♥2（单张）
  ....
  ★ 最终无法出牌/最后出完

【出法2】对子: ♦A ♣A
同盟必胜序列：
  玩家1 → 出 ♣5 ♥5（对子）
  玩家1 → 出 ♠A（单张）
  玩家2 → 出 ♦2（单张）
  玩家3 → 出 ♣2（单张）
  ...
  玩家1 → 出 ♣6（单张）
  ★ 最终无法出牌/最后出完

【出法3】对子: ♦A ♥A
同盟必胜序列：
  玩家1 → 出 ♣5 ♥5（对子）
  玩家1 → 出 ♠A（单张）
  玩家2 → 出 ♦2（单张）
  ...
  ★ 最终无法出牌/最后出完

【出法4】三条: ♦A ♣A ♥A
同盟必胜序列：
  ★ → 出 ♠2（单张）
  玩家1 → 出 ♣5（单张）
  玩家2 → 出 ♦7（单张）
  玩家2 → 出 ♦2（单张）
  玩家3 → 出 ♣2（单张）
  ...
```

### 优化2:

- 问题：因为是训练模式，不做询问，直接让测试人员输入玩家编号，从0-N

```shell
=== 发牌完成 ===
玩家0: [♦A, ♣3, ♦4, ♠5, ♦7]
玩家1: [♣A, ♠3, ♦5, ♣6, ♠6]
玩家2: [♠A, ♣2, ♠2, ♣4, ♣5]
玩家3: [♦2, ♦3, ♥3, ♦6, ♥6]
玩家4: [♥A, ♥2, ♥4, ♠4, ♥5]
玩家0 是否抢A？(y/n):
```

### 优化3:

先出了一对A，然后出对6管上的时候报错了

```shell

2026-06-23 10:13:37.859 Uncaught app execution
Traceback (most recent call last):
  File "F:\anaconda\envs\runfirst\Lib\site-packages\streamlit\runtime\scriptrunner\exec_code.py", line 129, in exec_func_with_error_handling
    result = func()
  File "F:\anaconda\envs\runfirst\Lib\site-packages\streamlit\runtime\scriptrunner\script_runner.py", line 789, in code_to_exec
    exec(code, module.__dict__)  # noqa: S102
    ~~~~^^^^^^^^^^^^^^^^^^^^^^^
  File "D:\stock\runfirst\app.py", line 691, in <module>
    main()
    ~~~~^^
  File "D:\stock\runfirst\app.py", line 687, in main
    render_game_area()
    ~~~~~~~~~~~~~~~~^^
  File "D:\stock\runfirst\app.py", line 380, in render_game_area
    render_interaction()
    ~~~~~~~~~~~~~~~~~~^^
  File "D:\stock\runfirst\app.py", line 480, in render_interaction
    render_mode1_interaction(state)
    ~~~~~~~~~~~~~~~~~~~~~~~~^^^^^^^
  File "D:\stock\runfirst\app.py", line 490, in render_mode1_interaction
    render_star_play(state)
    ~~~~~~~~~~~~~~~~^^^^^^^
  File "D:\stock\runfirst\app.py", line 573, in render_star_play
    new_state, error = _apply_star_move(state, move)
                       ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^
  File "D:\stock\runfirst\app.py", line 251, in _apply_star_move
    orders = move[4]
             ~~~~^^^
IndexError: tuple index out of range

```
