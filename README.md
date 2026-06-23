# 夺A快跑

基于上帝视角的抢A牌局训练工具，帮助 ★（星玩家）通过两种训练模式理解胜败路径。

## 游戏简介

- **5人局**，截断牌堆 25 张（order 0~24），每人初始 5 张
- **4种牌型**：单张 / 对子 / 三条 / 四条，按牌型层级 + rank + suit 比大小
- **抢A规则**：亮♦A后顺时针抢，★先出完即胜
- **特殊机制**：下家独张约束、全局最大牌型接管、Pass 环绕

## 两种训练模式

| | 模式一 | 模式二 |
|---|---|---|
| 目标 | 学"怎么出能赢" | 学"怎么出会输 + 对手怎么打" |
| 交互 | 每步出牌，实时标注 ✅/❌ | 赛前多分支分析 + 赛中对手强制执行 |
| 对手行为 | AI 自主选"最恶毒"出牌 | 严格按预计算的最优路径出牌 |

## 快速开始

```bash
# 进入训练（选择模式一或二）
python main.py

# 运行测试
python -m pytest test_game.py -v

# 专项测试
python main.py --test-best-response
python main.py --test-multi-da

# 加载配置文件
python main.py --load configs/hands.yaml          # 交互选场景
python main.py --load configs/hands.yaml --scene 1 # 直接指定场景
python main.py                                      # 随机发牌（不变）

# Web 界面
python main.py --web

# 或直接
streamlit run app.py

# CLI 模式（不受影响）
python main.py                           # 随机发牌
python main.py --load configs/hands.yaml # 加载预设场景



```

## 项目结构

```
runfirst/
├── models.py         # 数据模型、常量、格式化
├── deck.py           # 牌组构建、发牌、抢A
├── moves.py          # 牌型识别、合法出牌枚举、全局最大判定
├── solver.py         # 求解器（DFS + memo）、局面推进、终局判定
├── sequence.py       # 同盟必胜序列分析（多♦A分支验证、最优应对）
├── cli.py            # CLI 交互、对手AI出牌、强制执行
├── config_loader.py  # YAML 配置加载、手牌验证与解析
├── configs/          # 预设手牌场景（YAML）
│   └── hands.yaml    #   示例场景集
├── game.py           # 聚合导出（向后兼容）
├── main.py           # 入口：模式选择 + 命令行参数
├── test_game.py      # 单元测试
└── SPEC.md           # 详细规格文档
```

## 命令行参数

| 参数 | 说明 |
|------|------|
| （无） | 启动交互式训练（随机发牌），选择模式一或二 |
| `--load PATH` | 从 YAML 配置文件加载预设手牌场景 |
| `--scene ID` | 配合 `--load` 直接指定场景ID（跳过交互选择） |
| `--test-best-response` | 测试同盟最优应对序列搜索 |
| `--test-multi-da` | 测试多♦A出牌分支验证 |

## 许可证

MIT
