"""夺A快跑 — config_loader.py 测试 (P0-1)

覆盖: parse_card / load_yaml_config / validate_and_parse_scenario
"""

import os
import tempfile
import pytest
from config_loader import (
    parse_card,
    load_yaml_config,
    validate_and_parse_scenario,
)


# ═══════════════════════════════════════════════════════════════
# parse_card 测试
# ═══════════════════════════════════════════════════════════════


class TestParseCard:
    """parse_card() 单元测试"""

    @pytest.mark.parametrize("card_str, expected_rank, expected_suit", [
        ("D A", 0, 0),   # ♦A
        ("C A", 0, 1),   # ♣A
        ("H A", 0, 2),   # ♥A
        ("S A", 0, 3),   # ♠A
        ("D 2", 1, 0),   # ♦2
        ("H 2", 1, 2),   # ♥2
        ("S 6", 5, 3),   # ♠6 (order=23, 范围 0~24 内)
        ("D 7", 6, 0),   # ♦7 (order=24, 最大有效牌)
        ("H 5", 4, 2),   # ♥5 (order=18)
        ("S 3", 2, 3),   # ♠3
    ])
    def test_parse_card_valid(self, card_str, expected_rank, expected_suit):
        """正常解析各种牌面"""
        card = parse_card(card_str)
        assert card.rank == expected_rank, f"rank 应为 {expected_rank}，实际 {card.rank}"
        assert card.suit == expected_suit, f"suit 应为 {expected_suit}，实际 {card.suit}"

    @pytest.mark.parametrize("card_str, expected_rank, expected_suit", [
        ("d a", 0, 0),       # 小写花色+小写牌面 → ♦A
        ("D a", 0, 0),       # 大写花色+小写牌面 → ♦A
        ("d A", 0, 0),       # 小写花色+大写牌面 → ♦A
        ("c 6", 5, 1),       # 小写花色 c → ♣6 (order=21)
        ("s 5", 4, 3),       # 小写花色 s → ♠5 (order=19)
        ("  D A  ", 0, 0),   # 前后空格 → ♦A
    ])
    def test_parse_card_case_insensitive(self, card_str, expected_rank, expected_suit):
        """大小写不敏感 + 首尾空格处理"""
        card = parse_card(card_str)
        assert card.rank == expected_rank
        assert card.suit == expected_suit

    def test_parse_card_lowercase_c_club(self):
        """小写 c → ♣A"""
        card = parse_card("c A")
        assert card.rank == 0
        assert card.suit == 1

    def test_parse_card_lowercase_h_heart(self):
        """小写 h → ♥A"""
        card = parse_card("h A")
        assert card.rank == 0
        assert card.suit == 2

    def test_parse_card_lowercase_s_spade(self):
        """小写 s → ♠A"""
        card = parse_card("s A")
        assert card.rank == 0
        assert card.suit == 3

    @pytest.mark.parametrize("card_str", [
        "",           # 空字符串
        "X 1",        # 无效花色
        "D X",        # 无效牌面
        "D 99",       # 超出范围牌面
        "DA",         # 无空格
        "D A X",      # 多余部分
    ])
    def test_parse_card_invalid(self, card_str):
        """非法输入抛出 ValueError"""
        with pytest.raises(ValueError):
            parse_card(card_str)

    def test_parse_card_invalid_suit_message(self):
        """无效花色包含提示信息"""
        with pytest.raises(ValueError, match="无效花色"):
            parse_card("X 1")

    def test_parse_card_invalid_rank_message(self):
        """无效牌面包含提示信息"""
        with pytest.raises(ValueError, match="无效牌面"):
            parse_card("D X")


# ═══════════════════════════════════════════════════════════════
# load_yaml_config 测试
# ═══════════════════════════════════════════════════════════════


class TestLoadYamlConfig:
    """load_yaml_config() 单元测试"""

    def test_load_valid_yaml(self):
        """正常加载 valid YAML 文件"""
        configs_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "configs"
        )
        path = os.path.join(configs_dir, "hands.yaml")
        if not os.path.exists(path):
            pytest.skip("配置文件 hands.yaml 不存在")
        data = load_yaml_config(path)
        assert isinstance(data, dict)
        assert "scenarios" in data

    def test_load_file_not_found(self):
        """文件不存在抛出 FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            load_yaml_config("/nonexistent/path/config.yaml")

    def test_load_yaml_syntax_error(self):
        """YAML 语法错误抛出 ValueError"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write("key: [invalid: yaml: [\n")
            bad_path = f.name
        try:
            with pytest.raises(ValueError):
                load_yaml_config(bad_path)
        finally:
            os.unlink(bad_path)

    def test_load_empty_yaml(self):
        """空 YAML 文件（safe_load 返回 None）抛出 ValueError"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write("")
            empty_path = f.name
        try:
            with pytest.raises(ValueError, match="配置.*为空"):
                load_yaml_config(empty_path)
        finally:
            os.unlink(empty_path)


# ═══════════════════════════════════════════════════════════════
# validate_and_parse_scenario 测试
# ═══════════════════════════════════════════════════════════════


VALID_CONFIG_5_PLAYERS = {
    "scenarios": [
        {
            "id": 1,
            "name": "正常场景",
            "bidder": None,
            "players": {
                0: ["D A", "D 2", "D 3", "D 4", "D 5"],
                1: ["S A", "S 2", "S 3", "S 4", "S 5"],
                2: ["C A", "C 2", "C 3", "C 4", "C 5"],
                3: ["H A", "H 2", "H 3", "H 4", "H 5"],
                4: ["D 6", "C 6", "H 6", "S 6", "D 7"],
            },
        },
    ]
}


class TestValidateAndParseScenario:
    """validate_and_parse_scenario() 单元测试"""

    def test_normal_scenario_with_da(self):
        """正常场景（bidder=null，含♦A → 自动检测♦A持有者为bidder）"""
        bidder, hands, info = validate_and_parse_scenario(
            VALID_CONFIG_5_PLAYERS, scenario_id=1
        )
        # bidder=null 时自动检测 ♦A 持有者（玩家0持有 ♦A）
        assert bidder == 0
        assert len(hands) == 5
        for h in hands:
            assert len(h) == 5
        assert info["name"] == "正常场景"

    def test_normal_scenario_explicit_bidder(self):
        """正常场景（bidder=0，显式指定）"""
        config = {
            "scenarios": [
                {
                    "id": 2,
                    "name": "显式bidder",
                    "bidder": 0,
                    "players": {
                        0: ["D A", "D 2", "D 3", "D 4", "D 5"],
                        1: ["S A", "S 2", "S 3", "S 4", "S 5"],
                        2: ["C A", "C 2", "C 3", "C 4", "C 5"],
                        3: ["H A", "H 2", "H 3", "H 4", "H 5"],
                        4: ["D 6", "C 6", "H 6", "S 6", "D 7"],
                    },
                },
            ]
        }
        bidder, hands, info = validate_and_parse_scenario(config, scenario_id=2)
        assert bidder == 0

    def test_total_cards_not_equal_25(self):
        """某玩家手牌数 ≠ 5 先触发（校验顺序：玩家手牌数 → 总牌数）"""
        config = {
            "scenarios": [
                {
                    "id": 1,
                    "name": "少牌",
                    "bidder": None,
                    "players": {
                        0: ["D A"],
                        1: ["S A"],
                        2: ["C A"],
                        3: ["H A"],
                        4: ["D 2"],
                    },
                },
            ]
        }
        with pytest.raises(ValueError, match="手牌数不为5"):
            validate_and_parse_scenario(config, scenario_id=1)

    def test_duplicate_card(self):
        """重复牌抛出 ValueError"""
        config = {
            "scenarios": [
                {
                    "id": 1,
                    "name": "重复牌",
                    "bidder": None,
                    "players": {
                        0: ["D A", "D A", "D 2", "D 3", "D 4"],  # ♦A 重复
                        1: ["S A", "S 2", "S 3", "S 4", "S 5"],
                        2: ["C A", "C 2", "C 3", "C 4", "C 5"],
                        3: ["H A", "H 2", "H 3", "H 4", "H 5"],
                        4: ["D 5", "C 6", "H 6", "S 6", "D 7"],
                    },
                },
            ]
        }
        with pytest.raises(ValueError, match="重复"):
            validate_and_parse_scenario(config, scenario_id=1)

    def test_missing_da_with_null_bidder(self):
        """bidder=null 且 ♦A 不存在 → ValueError（需所有牌 order 在 0~24 内）"""
        # 注：25张有效牌(0~24)必然含♦A(0)，此场景用无效牌"S 7"模拟
        # parse_card 先报超出范围（order=27 > 24），不会到达 ♦A 缺失检查
        config = {
            "scenarios": [
                {
                    "id": 1,
                    "name": "含无效牌",
                    "bidder": None,
                    "players": {
                        0: ["D 2", "D 3", "D 4", "D 5", "D 6"],
                        1: ["S A", "S 2", "S 3", "S 4", "S 5"],
                        2: ["C A", "C 2", "C 3", "C 4", "C 5"],
                        3: ["H A", "H 2", "H 3", "H 4", "H 5"],
                        4: ["C 6", "H 6", "S 6", "D 7", "S 7"],
                    },
                },
            ]
        }
        with pytest.raises(ValueError, match="超出范围"):
            validate_and_parse_scenario(config, scenario_id=1)

    def test_player_count_not_5(self):
        """玩家数量不为 5 → ValueError"""
        config = {
            "scenarios": [
                {
                    "id": 1,
                    "name": "4玩家",
                    "bidder": None,
                    "players": {
                        0: ["D A", "D 2", "D 3", "D 4", "D 5"],
                        1: ["S A", "S 2", "S 3", "S 4", "S 5"],
                        2: ["C A", "C 2", "C 3", "C 4", "C 5"],
                        3: ["H A", "H 2", "H 3", "H 4", "H 5"],
                    },
                },
            ]
        }
        with pytest.raises(ValueError, match="玩家数不为5"):
            validate_and_parse_scenario(config, scenario_id=1)

    def test_player_hand_count_not_5(self):
        """某玩家手牌数不为 5 → ValueError"""
        config = {
            "scenarios": [
                {
                    "id": 1,
                    "name": "少牌玩家",
                    "bidder": None,
                    "players": {
                        0: ["D A", "D 2", "D 3", "D 4"],  # 只有4张
                        1: ["S A", "S 2", "S 3", "S 4", "S 5"],
                        2: ["C A", "C 2", "C 3", "C 4", "C 5"],
                        3: ["H A", "H 2", "H 3", "H 4", "H 5"],
                        4: ["D 5", "D 6", "C 6", "H 6", "S 6"],
                    },
                },
            ]
        }
        with pytest.raises(ValueError, match="不为5"):
            validate_and_parse_scenario(config, scenario_id=1)

    def test_invalid_bidder_value(self):
        """bidder 不在 0~4 → ValueError"""
        config = {
            "scenarios": [
                {
                    "id": 1,
                    "name": "无效bidder",
                    "bidder": 5,
                    "players": {
                        0: ["D A", "D 2", "D 3", "D 4", "D 5"],
                        1: ["S A", "S 2", "S 3", "S 4", "S 5"],
                        2: ["C A", "C 2", "C 3", "C 4", "C 5"],
                        3: ["H A", "H 2", "H 3", "H 4", "H 5"],
                        4: ["D 6", "C 6", "H 6", "S 6", "D 7"],
                    },
                },
            ]
        }
        with pytest.raises(ValueError, match="无效"):
            validate_and_parse_scenario(config, scenario_id=1)

    def test_scenarios_empty(self):
        """scenarios 为空抛出 ValueError"""
        config = {"scenarios": []}
        with pytest.raises(ValueError, match="无场景"):
            validate_and_parse_scenario(config, scenario_id=1)

    def test_player_index_missing(self):
        """玩家数 ≠5 → ValueError（校验顺序：玩家总数 → 具体索引）"""
        config = {
            "scenarios": [
                {
                    "id": 1,
                    "name": "缺玩家",
                    "bidder": None,
                    "players": {
                        0: ["D A", "D 2", "D 3", "D 4", "D 5"],
                        1: ["S A", "S 2", "S 3", "S 4", "S 5"],
                        2: ["C A", "C 2", "C 3", "C 4", "C 5"],
                        3: ["H A", "H 2", "H 3", "H 4", "H 5"],
                        # 缺少玩家 4
                    },
                },
            ]
        }
        with pytest.raises(ValueError, match="玩家数不为5"):
            validate_and_parse_scenario(config, scenario_id=1)

    def test_scenario_not_found(self):
        """场景ID不存在 → ValueError"""
        config = {"scenarios": [{"id": 1, "name": "only", "bidder": None, "players": {
            0: ["D A", "D 2", "D 3", "D 4", "D 5"],
            1: ["S A", "S 2", "S 3", "S 4", "S 5"],
            2: ["C A", "C 2", "C 3", "C 4", "C 5"],
            3: ["H A", "H 2", "H 3", "H 4", "H 5"],
            4: ["D 6", "C 6", "H 6", "S 6", "D 7"],
        }}]}
        with pytest.raises(ValueError, match="不存在"):
            validate_and_parse_scenario(config, scenario_id=99)
