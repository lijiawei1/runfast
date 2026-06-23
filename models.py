"""夺A快跑 — 数据模型与常量"""

import sys
from dataclasses import dataclass

# ── Windows 控制台 UTF-8 编码 ──
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# ── 常量 ──

RANK_NAMES: dict[int, str] = {
    0: "A", 1: "2", 2: "3", 3: "4", 4: "5", 5: "6",
    6: "7", 7: "8", 8: "9", 9: "10", 10: "J", 11: "Q", 12: "K",
}

SUIT_NAMES: dict[int, str] = {0: "♦", 1: "♣", 2: "♥", 3: "♠"}

_TYPE_CN = {"single": "单张", "pair": "对子", "triple": "三条", "quad": "四条"}


# ── 数据模型 ──

class Card:
    """扑克牌"""

    def __init__(self, rank: int, suit: int):
        """
        rank: A=0, 2=1, 3=2, ..., 10=9, J=10, Q=11, K=12
        suit: ♦=0, ♣=1, ♥=2, ♠=3
        """
        self.rank = rank
        self.suit = suit
        self.order = rank * 4 + suit

    def __repr__(self):
        return f"{SUIT_NAMES[self.suit]}{RANK_NAMES[self.rank]}"


@dataclass(frozen=True)
class Trick:
    """一手出牌（桌上的牌型），frozen 以便可哈希用于 memoization"""

    type: str       # "single" / "pair" / "triple" / "quad"
    rank: int       # 牌型对应的 rank（0=A, 1=2, ..., 12=K）
    top_suit: int   # 最高花色（♦=0 < ♣=1 < ♥=2 < ♠=3）

    def __repr__(self):
        return f"Trick({self.type}, {RANK_NAMES[self.rank]}, {SUIT_NAMES[self.top_suit]})"


@dataclass(frozen=True)
class GameState:
    """游戏状态（frozen → 可哈希，用于 memoization）"""
    masks: tuple[int, int, int, int, int]  # 5人手牌 mask（0=★, 1~4=对手）
    trick: Trick | None                     # 桌上那手牌（None = 自由出牌）
    turn: int                               # 0~4，当前该谁出
    starter: int                            # 当前 trick 的发起者（trick=None时设为turn）


# ── 格式化工具 ──

def format_cards(card_orders: list[int]) -> str:
    """将 order 列表转换为可读字符串，如 "♦A ♣A" """
    cards = [Card(o // 4, o % 4) for o in card_orders]
    return " ".join(str(c) for c in cards)


def _format_hand(mask: int) -> str:
    """将 bitmask 转为可读手牌字符串，如 '♦A, ♣2, ♥3'"""
    cards = [Card(o // 4, o % 4) for o in range(25) if mask & (1 << o)]
    return ', '.join(str(c) for c in cards)
