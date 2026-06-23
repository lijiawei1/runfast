# 开发约定

所有新功能开发顺序：

1. **CLI 验证**：先在命令行下完成核心逻辑 + CLI 交互
2. **单元测试**：在 `tests/` 目录下覆盖核心逻辑（`test_game.py` 保留向后兼容）
3. **UI 对接**：最后在 `app.py` 中调用已验证的接口

## 模块化规范（R6 后）

- **规则引擎**：纯逻辑放 `game_engine.py`（无 UI/IO 依赖），CLI 和 Web 都从这里调用
- **Web UI**：`app.py` 为编排层，样式/渲染/交互分别放 `app_styles.py` / `app_render.py` / `app_play.py`
- **Move 格式**：新代码使用 `models.Move` 类（`from_free()` / `from_response()` 工厂方法），旧代码（solver.py/moves.py）待逐步迁移
- **测试**：新测试放 `tests/` 目录，每个模块一个 test 文件
- **CLI 逻辑分离**：库模块中的 `input()`/`print()` 应分离为 `*_logic()` 纯函数 + CLI 包装函数
- **求解器缓存**：`solve()` 使用 `lru_cache(maxsize=500000)`，长时 Web 运行可调用 `clear_solve_cache()` 释放内存
- **IO 分离已完成**：`deck.take_bid_logic()` / `config_loader.select_scenario_logic()` 已纯函数化，`sys.stdout.reconfigure` 已移至 `main.py`