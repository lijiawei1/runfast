"""夺A快跑 — 演示入口"""
import sys
from models import GameState, Trick, Card, _TYPE_CN, format_cards
from deck import build_deck, shuffle_and_deal, hands_to_masks, take_bid
from moves import get_legal_moves_free
from solver import solve, _apply_move, check_terminal
from sequence import (
    find_winning_sequence, format_sequence,
    find_best_response, format_best_response,
    verify_all_da_moves, format_multi_da_verification,
    enumerate_da_moves,
)
from cli import play_turn, execute_forced_move
from config_loader import load_yaml_config, validate_and_parse_scenario
from log_engine import (
    log_setup, log_event, log_section, log_star_win, log_star_lose,
    log_sequence, log_multi_da,
)


def setup_game(num_players: int = 5):
    """通用初始化：发牌 → 抢A → 重排手牌 → 返回初始 GameState。
    
    若无人抢A，返回 None。
    """
    deck = build_deck(num_players)
    hands = shuffle_and_deal(deck, num_players)

    lines = ["=== 发牌完成 ==="]
    for i, hand in enumerate(hands):
        lines.append(f"玩家{i}: {sorted(hand, key=lambda c: c.order)}")
    log_setup(lines)

    bidder, updated_hands = take_bid(hands, num_players)
    if bidder is None:
        print("\n无人抢A，退出训练模式")
        return None

    log_event("🎯", f"玩家{bidder} 抢到A！")
    lines = ["=== 换手后手牌 ==="]
    for i, hand in enumerate(updated_hands):
        prefix = "★ " if i == bidder else "  "
        lines.append(f"{prefix}玩家{i}: {sorted(hand, key=lambda c: c.order)}")
    log_setup(lines)

    # ── 重新排列手牌：★（bidder）移到索引 0 ──
    reordered = [updated_hands[bidder]]
    for i in range(num_players):
        if i != bidder:
            reordered.append(updated_hands[i])

    # 初始化 GameState
    masks = hands_to_masks(reordered)
    state = GameState(
        masks=masks,
        trick=None,
        turn=0,
        starter=0,
    )
    log_setup([f"初始状态：turn={state.turn} (★), ★手牌mask={bin(masks[0])}"])

    return state


def setup_game_from_config(config_path: str, scenario_id: int | None = None) -> GameState | None:
    """从配置文件加载预设手牌场景（替代随机发牌）。

    Args:
        config_path: YAML 配置文件路径
        scenario_id: 指定场景ID（None→交互选择）

    Returns:
        初始 GameState（★在索引0），加载失败返回 None
    """
    config_data = load_yaml_config(config_path)
    bidder, hands, info = validate_and_parse_scenario(config_data, scenario_id)
    num_players = len(hands)  # 从解析后的手牌数获取玩家数

    # ── 打印场景信息 ──
    lines = [
        f"📌 场景 [{info['id']}] {info['name']}",
        f"   {info['description']}",
        "",
        "=== 预设手牌 ===",
    ]
    for i, hand in enumerate(hands):
        lines.append(f"玩家{i}: {sorted(hand, key=lambda c: c.order)}")
    log_setup(lines)

    # ── 确定 bidder 并执行换手 ──
    if bidder is None:
        # bidder=null：自动检测 ♦A 持有者
        # 已在 validate_and_parse_scenario 中验证 ♦A 存在，此处不会为 None
        for i, hand in enumerate(hands):
            for c in hand:
                if c.rank == 0 and c.suit == 0:
                    bidder = i
                    break
            if bidder is not None:
                break

    # 检查是否需要换手（bidder 不是 ♦A 持有者时）
    da_owner = None
    for i, hand in enumerate(hands):
        for c in hand:
            if c.rank == 0 and c.suit == 0:
                da_owner = i
                break
        if da_owner is not None:
            break

    updated_hands = [list(h) for h in hands]  # deep copy

    if da_owner is not None and da_owner != bidder:
        # 执行换手：原主移除 ♦A，bidder 获得 ♦A
        updated_hands[da_owner] = [
            c for c in updated_hands[da_owner]
            if not (c.rank == 0 and c.suit == 0)
        ]
        updated_hands[bidder].append(Card(0, 0))
        # 重排序
        for hand in updated_hands:
            hand.sort(key=lambda c: c.order)

    log_event("🎯", f"玩家{bidder} 为★（抢A玩家）")
    lines = ["=== 换手后手牌 ==="]
    for i, hand in enumerate(updated_hands):
        prefix = "★ " if i == bidder else "  "
        lines.append(f"{prefix}玩家{i}: {sorted(hand, key=lambda c: c.order)}")
    log_setup(lines)

    # ── 重排：★ 移到索引 0 ──
    reordered = [updated_hands[bidder]]
    for i in range(num_players):
        if i != bidder:
            reordered.append(updated_hands[i])

    masks = hands_to_masks(reordered)
    state = GameState(
        masks=masks,
        trick=None,
        turn=0,
        starter=0,
    )
    log_setup([f"初始状态：turn={state.turn} (★), ★手牌mask={bin(masks[0])}"])

    return state


def mode1_game_loop(state: GameState) -> None:
    """训练模式一：实时交互训练（原 main() 的游戏循环）"""
    while True:
        winner, game_over = check_terminal(state)
        if game_over:
            log_section("游戏结束", "double")
            if winner == 0:
                log_star_win()
            else:
                log_star_lose(winner)
            break
        state = play_turn(state)


def mode2_game_loop(state: GameState) -> None:
    """训练模式二：同盟必胜序列分析（强制执行版）

    同盟对手严格按 find_best_response 返回的序列出牌，
    ★无论怎么出牌，同盟都按最优路径应对。
    """
    # ── 静态分析阶段 ──
    log_section("静态分析：多♦A分支验证", "single")
    log_event("📊", "分析每种含♦A出牌的同盟必胜序列...")
    result_dict = verify_all_da_moves(state)
    da_text = format_multi_da_verification(result_dict)
    has_star_winning = any(seq is None for seq in result_dict.values())
    log_multi_da(da_text.split("\n"), has_star_winning=has_star_winning)

    # 检查是否有★胜招（任意含♦A出牌同盟无必胜序列）
    if has_star_winning:
        log_event("★", "有胜招，退出训练模式二")
        return

    # 所有含♦A出牌同盟都有必胜序列 → 进入强制执行模式
    log_event("🚨", "进入强制执行模式：同盟将严格按最优路径出牌！")

    # 初始化强制序列（★还未出牌，从初始状态计算同盟最优应对）
    current_sequence: list = find_best_response(state)
    if current_sequence:
        seq_text = format_best_response(current_sequence)
        lines = []
        for l in seq_text.split("\n"):
            l = l.strip()
            if l:
                lines.append(("", l, False))
        log_sequence("初始同盟最优序列", lines)

    # ── 动态分析阶段（强制执行）──
    while True:
        winner, game_over = check_terminal(state)
        if game_over:
            log_section("游戏结束", "double")
            if winner == 0:
                log_star_win()
            else:
                log_star_lose(winner)
            break

        if state.turn == 0:
            # ★ 的回合：正常交互
            state = play_turn(state)

            # 终局后不再计算
            if check_terminal(state)[1]:
                continue

            # ★ 出牌后，重新计算同盟最优序列
            # 全局最大接管：若★出全局最大，state.turn 仍为 0
            if state.turn == 0:
                # 全局最大接管，清空序列并重置
                current_sequence = find_best_response(state)
                if current_sequence:
                    seq_text = format_best_response(current_sequence)
                    lines = []
                    for l in seq_text.split("\n"):
                        l = l.strip()
                        if l:
                            lines.append(("", l, False))
                    log_sequence("全局最大接管，重新计算同盟最优序列", lines)
                continue

            current_sequence = find_best_response(state)
            if current_sequence:
                seq_text = format_best_response(current_sequence)
                log_setup(seq_text.split("\n"))
            else:
                log_event("✅", "此手仍在必胜域内，同盟暂无必胜策略")
        else:
            # 对手的回合：检查是否有强制出牌
            forced_move = None
            for player, move in current_sequence:
                if player == state.turn:
                    forced_move = move
                    break

            if forced_move:
                # 强制执行预计算的出牌
                executed_player = state.turn
                state = execute_forced_move(state, forced_move)
                # 从序列中移除已执行的 move
                current_sequence = [
                    (p, m) for p, m in current_sequence
                    if not (p == executed_player and m == forced_move)
                ]
            else:
                # 无强制序列（如 Pass 场景），正常走
                state = play_turn(state)


def main(config_path: str | None = None, scene_id: int | None = None,
         num_players: int = 5):
    """主入口：模式选择 → 进入对应训练流程。

    Args:
        config_path: 配置文件路径（None→随机发牌）
        scene_id: 场景ID（None→交互选择）
        num_players: 玩家人数（5/6/7/8，默认5）
    """
    if config_path:
        state = setup_game_from_config(config_path, scene_id)
    else:
        state = setup_game(num_players)
    if state is None:
        return

    # ── 模式选择 ──
    log_section("训练模式选择", "single")
    log_setup(["请选择训练模式：", "1 - 训练模式一（实时交互）", "2 - 训练模式二（同盟序列分析）"])
    choice = input("请输入: ").strip()

    if choice == "2":
        mode2_game_loop(state)
    else:
        # 默认（包括输入 1 或其他）进入训练模式一
        mode1_game_loop(state)


def test_best_response():
    """测试 find_best_response：★出牌后，搜索同盟最优应对"""
    log_section("测试：find_best_response — 同盟最优应对（最恶毒路径）", "double")

    # ── 构造场景：★必败状态 ──
    masks = (
        (1 << 0) | (1 << 4),  # ★: ♦A + ♦2
        1 << 1,               # P1: ♣A
        1 << 2,               # P2: ♥A
        1 << 3,               # P3: ♠A
        1 << 5,               # P4: ♣2
    )
    state0 = GameState(masks=masks, trick=None, turn=0, starter=0)

    # 先检查整体局面
    solved = solve(state0)
    log_setup([f"📊 初始局面：turn=0(★), ★手牌={format_cards([0, 4])}",
               f"   solve 结果: {solved} ({'★必胜' if solved else '★必败'})"])

    # 搜索整体必胜序列
    seq_full = find_winning_sequence(state0)
    if seq_full:
        formatted = format_sequence(seq_full)
        log_setup([f"🔍 同盟有必胜序列（find_winning_sequence），共 {len(seq_full)} 步："] +
                  formatted.split("\n"))
    else:
        log_event("★", "必胜")

    # ── ★出♦A（order=0）──
    moves = get_legal_moves_free(masks[0])
    move_da = None
    for m in moves:
        if 0 in m.orders:
            move_da = m
            break

    if move_da is None:
        log_event("❌", "错误：找不到 ♦A 出牌")
        return

    state1 = _apply_move(state0, move_da, 0)
    solved1 = solve(state1)
    log_setup([f"── ★ 打出 ♦A 后 ──",
               f"   新状态：turn={state1.turn}(玩家{state1.turn}), trick={state1.trick}",
               f"   ★ 剩余手牌：{format_cards([4])}  (♦2)",
               f"   solve 结果: {solved1} ({'★必胜' if solved1 else '★必败'})"])

    # ★ 出牌后搜索同盟最优应对
    resp = find_best_response(state1)
    resp_text = format_best_response(resp)
    log_setup(["🔍 find_best_response 结果："] + resp_text.split("\n"))

    log_section("find_best_response 测试完成", "double")


def test_multi_da_verification():
    """测试 enumerate_da_moves, verify_all_da_moves, format_multi_da_verification"""
    log_section("测试：多♦A出牌分支验证", "double")

    # ── 测试场景1 ──
    log_section("场景1：★手牌有多个A", "single")
    star_mask1 = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 3) | (1 << 4)
    masks1 = (
        star_mask1,
        (1 << 5) | (1 << 6) | (1 << 7),
        (1 << 8) | (1 << 9) | (1 << 10),
        (1 << 12) | (1 << 13) | (1 << 14),
        (1 << 16) | (1 << 17) | (1 << 18),
    )
    state1 = GameState(masks=masks1, trick=None, turn=0, starter=0)

    da_moves1 = enumerate_da_moves(star_mask1)
    lines1 = [f"enumerate_da_moves 返回 {len(da_moves1)} 种含♦A出牌："]
    for i, m in enumerate(da_moves1):
        type_cn = _TYPE_CN.get(m.type, m.type)
        lines1.append(f"  {i + 1}. {type_cn}: {format_cards(m.orders)}")
    log_setup(lines1)

    result1 = verify_all_da_moves(state1)
    status_lines = ["verify_all_da_moves 结果："]
    all_have_seq = True
    for desc, seq in result1.items():
        status = "同盟必胜 ✅" if seq is not None else "同盟无必胜序列 ❌"
        seq_len = f"({len(seq)}步)" if seq else ""
        status_lines.append(f"  {desc} → {status} {seq_len}")
        if seq is None:
            all_have_seq = False
    log_setup(status_lines)
    da_text1 = format_multi_da_verification(result1)
    log_setup(["format_multi_da_verification 输出："] + da_text1.split("\n"))
    log_event("📊", f"场景1结论：所有含♦A出牌都有同盟必胜序列 = {all_have_seq}")

    # ── 测试场景2 ──
    log_section("场景2：★有胜招（对子可破局）", "single")
    star_mask2 = (1 << 0) | (1 << 1) | (1 << 6)
    masks2 = (
        star_mask2,
        (1 << 3) | (1 << 8),
        (1 << 4) | (1 << 13),
        (1 << 5) | (1 << 10),
        (1 << 7) | (1 << 11) | (1 << 12),
    )
    state2 = GameState(masks=masks2, trick=None, turn=0, starter=0)

    da_moves2 = enumerate_da_moves(star_mask2)
    lines2 = [f"enumerate_da_moves 返回 {len(da_moves2)} 种含♦A出牌："]
    for i, m in enumerate(da_moves2):
        type_cn = _TYPE_CN.get(m.type, m.type)
        lines2.append(f"  {i + 1}. {type_cn}: {format_cards(m.orders)}")
    log_setup(lines2)

    solved2 = solve(state2)
    log_event("📊", f"初始状态 solve 结果: {solved2} ({'★必胜' if solved2 else '★必败'})")

    result2 = verify_all_da_moves(state2)
    has_star_win = any(seq is None for seq in result2.values())
    status_lines2 = ["verify_all_da_moves 结果："]
    for desc, seq in result2.items():
        status = "同盟必胜 ✅" if seq is not None else "同盟无必胜序列 ❌"
        seq_len = f"({len(seq)}步)" if seq else ""
        status_lines2.append(f"  {desc} → {status} {seq_len}")
    log_setup(status_lines2)
    da_text2 = format_multi_da_verification(result2)
    log_setup(["format_multi_da_verification 输出："] + da_text2.split("\n"))
    log_event("📊", f"场景2结论：存在★胜招 = {has_star_win}")

    log_section("多♦A出牌分支验证测试完成！", "double")


if __name__ == "__main__":
    # ── Windows 控制台 UTF-8 编码 ──
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
    import argparse

    parser = argparse.ArgumentParser(description="夺A快跑 — 训练工具")
    parser.add_argument("--test-best-response", action="store_true",
                        help="运行 find_best_response 测试")
    parser.add_argument("--test-multi-da", action="store_true",
                        help="运行多♦A分支验证测试")
    parser.add_argument("--load", type=str, default=None, metavar="PATH",
                        help="从 YAML 配置文件加载预设手牌场景")
    parser.add_argument("--scene", type=int, default=None, metavar="ID",
                        help="指定场景ID（需配合 --load 使用）")
    parser.add_argument("--web", action="store_true",
                        help="启动 Streamlit Web 界面")
    parser.add_argument(
        "--players", type=int, choices=[5, 6, 7, 8], default=5,
        help="玩家人数（5/6/7/8），默认5人局"
    )
    args = parser.parse_args()

    if args.web:
        import subprocess
        subprocess.run(["streamlit", "run", "app.py"])
    elif args.test_best_response:
        test_best_response()
    elif args.test_multi_da:
        test_multi_da_verification()
    else:
        main(config_path=args.load, scene_id=args.scene,
             num_players=args.players)
