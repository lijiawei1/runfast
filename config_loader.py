"""夺A快跑 — 配置文件加载与验证（YAML 预设手牌场景）"""

import os
from models import Card


# ── 花色与牌面映射 ──

SUIT_MAP: dict[str, int] = {"D": 0, "C": 1, "H": 2, "S": 3}

RANK_MAP: dict[str, int] = {
    "A": 0, "2": 1, "3": 2, "4": 3, "5": 4, "6": 5,
    "7": 6, "8": 7, "9": 8, "10": 9, "J": 10, "Q": 11, "K": 12,
}


# ── 牌面解析 ──

def parse_card(card_str: str) -> Card:
    """将字符串 "D A" 或 "h 10"（大小写不敏感）转为 Card 对象。

    Raises:
        ValueError: 格式错误、花色/牌面无效、order 超出 0~24
    """
    parts = card_str.strip().upper().split()
    if len(parts) != 2:
        raise ValueError(f"无效牌格式: '{card_str}'，应为'花色 牌面'（如 D A）")

    suit_char, rank_char = parts
    if suit_char not in SUIT_MAP:
        raise ValueError(f"无效花色: '{suit_char}'（有效: D/C/H/S）")
    if rank_char not in RANK_MAP:
        raise ValueError(f"无效牌面: '{rank_char}'（有效: A/2~10/J/Q/K）")

    suit = SUIT_MAP[suit_char]
    rank = RANK_MAP[rank_char]
    order = rank * 4 + suit
    if order > 24:
        raise ValueError(
            f"牌 '{card_str}' 的 globalOrder={order}，超出范围 0~24"
        )
    return Card(rank, suit)


# ── YAML 加载 ──

def load_yaml_config(path: str) -> dict:
    """加载 YAML 配置文件，含清晰的错误提示。

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: YAML 语法错误（含行号）
    """
    try:
        import yaml
    except ImportError:
        raise ImportError(
            "缺少 PyYAML 依赖，请执行: pip install pyyaml"
        )

    if not os.path.exists(path):
        raise FileNotFoundError(f"配置文件不存在: {path}")

    with open(path, "r", encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            if hasattr(e, "problem_mark") and e.problem_mark is not None:
                mark = e.problem_mark
                raise ValueError(
                    f"YAML 解析错误 (第{mark.line + 1}行, 第{mark.column + 1}列): {e.problem}"
                ) from e
            raise ValueError(f"YAML 解析错误: {e}") from e

    if data is None:
        raise ValueError("配置文件为空")
    return data


# ── 场景选择 ──

def select_scenario_logic(scenarios: list[dict], scenario_id: int) -> dict:
    """纯逻辑：按 scenario_id 直接定位场景。

    Args:
        scenarios: 场景列表
        scenario_id: 场景 ID

    Returns:
        匹配的场景 dict

    Raises:
        ValueError: 场景不存在
    """
    for s in scenarios:
        if s.get("id") == scenario_id:
            return s
    ids = [s.get("id") for s in scenarios]
    raise ValueError(f"场景 {scenario_id} 不存在，可用场景: {ids}")


def select_scenario_cli(scenarios: list[dict]) -> dict:
    """CLI 交互式场景选择（含 print/input）。

    Args:
        scenarios: 场景列表

    Returns:
        用户选择的场景 dict
    """
    print(f"\n📋 配置文件中共 {len(scenarios)} 个场景：")
    for s in scenarios:
        sid = s.get("id", "?")
        name = s.get("name", "未命名")
        desc = s.get("description", "")
        print(f"  [{sid}] {name} — {desc}")

    while True:
        choice = input("\n请输入场景ID: ").strip()
        try:
            sid = int(choice)
        except ValueError:
            print("❌ 请输入有效数字")
            continue
        for s in scenarios:
            if s.get("id") == sid:
                return s
        print(f"❌ 场景 {sid} 不存在")


def _select_scenario(scenarios: list[dict], scenario_id: int | None) -> dict:
    """从场景列表中选取一个场景（向后兼容包装器）。

    - scenario_id 非 None → 调用 select_scenario_logic
    - scenario_id 为 None → 调用 select_scenario_cli
    """
    if scenario_id is not None:
        return select_scenario_logic(scenarios, scenario_id)
    return select_scenario_cli(scenarios)


# ── 场景验证与解析 ──

def validate_and_parse_scenario(
    config_data: dict, scenario_id: int | None = None
) -> tuple[int, list[list[Card]], dict]:
    """验证配置文件并解析指定场景的手牌。

    Args:
        config_data: YAML 加载后的字典
        scenario_id: 指定场景ID（None→交互选择）

    Returns:
        (bidder, hands, scenario_info)
        - bidder: ★ 玩家在原顺序中的索引 (0~4)
        - hands: 5 个玩家的 Card 列表（按 order 排序）
        - scenario_info: {id, name, description}

    Raises:
        ValueError: 手牌数≠25、重复牌、♦A缺失、玩家数≠5、bidder无效等
    """
    scenarios = config_data.get("scenarios", [])
    if not scenarios:
        raise ValueError("配置文件中无场景定义 (scenarios 为空)")

    selected = _select_scenario(scenarios, scenario_id)
    name = selected.get("name", "未命名")

    # ── 玩家数量验证 ──
    players_data = selected.get("players", {})
    if len(players_data) != 5:
        raise ValueError(
            f"场景'{name}'玩家数不为5（实际: {len(players_data)}）"
        )
    for i in range(5):
        if i not in players_data:
            raise ValueError(f"场景'{name}'缺少玩家{i}的手牌")
        cards = players_data[i]
        if len(cards) != 5:
            raise ValueError(
                f"场景'{name}'玩家{i}手牌数不为5（实际: {len(cards)}）"
            )

    # ── 解析所有手牌 ──
    hands: list[list[Card]] = [[] for _ in range(5)]
    all_orders: list[int] = []

    for i in range(5):
        for cs in players_data[i]:
            card = parse_card(str(cs))
            if card.order in all_orders:
                raise ValueError(
                    f"场景'{name}'包含重复牌: {cs}（order={card.order}）"
                )
            all_orders.append(card.order)
            hands[i].append(card)

    # 手牌总数 = 25
    if len(all_orders) != 25:
        raise ValueError(
            f"场景'{name}'手牌总数不为25（实际: {len(all_orders)}）"
        )

    # ── ♦A 存在性检查 ──
    has_da = 0 in all_orders  # ♦A order = 0

    # ── bidder 确定 ──
    raw_bidder = selected.get("bidder")

    if raw_bidder is None:
        # 自动检测 ♦A 持有者
        if not has_da:
            raise ValueError(
                f"场景'{name}'bidder=null 但♦A不存在"
            )
        bidder = None
        for i, hand in enumerate(hands):
            for c in hand:
                if c.order == 0:
                    bidder = i
                    break
            if bidder is not None:
                break
    else:
        bidder = int(raw_bidder)
        if bidder not in (0, 1, 2, 3, 4):
            raise ValueError(
                f"场景'{name}'bidder={bidder} 无效，必须为 0~4 或 null"
            )

    # ── 每副手牌按 order 排序 ──
    for hand in hands:
        hand.sort(key=lambda c: c.order)

    scenario_info = {
        "id": selected.get("id"),
        "name": name,
        "description": selected.get("description", ""),
    }

    return bidder, hands, scenario_info
