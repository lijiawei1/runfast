"""夺A快跑 — 核心游戏逻辑（向后兼容重导出模块）

⚠️ 此文件已拆分，新代码请直接从子模块导入：
    - models.py    — 数据模型、常量、格式化
    - deck.py      — 牌组构建、发牌、抢A
    - moves.py     — 牌型识别、合法出牌枚举器、全局最大判断
    - solver.py    — 核心求解器、局面分析、状态推进
    - sequence.py  — 同盟必胜序列分析、最优应对
    - cli.py       — CLI 交互层、强制执行机制
"""

# ── 模型与常量 ──
from models import (
    Card, Trick, GameState, Move,
    RANK_NAMES, SUIT_NAMES, _TYPE_CN,
    format_cards, _format_hand,
)

# ── 牌组与抢A ──
from deck import (
    build_deck, shuffle_and_deal,
    hands_to_masks, find_diamond_a_holder, take_bid, take_bid_logic,
)

# ── 牌型识别 ──
from moves import (
    get_counts, find_pairs, find_triples, find_quads,
    get_all_cards,
)

# ── 合法出牌枚举器 ──
from moves import (
    get_legal_moves_free, get_legal_moves_response,
    get_max_single,
)

# ── 全局最大 ──
from moves import is_global_max

# ── 求解器 ──
from solver import (
    _apply_move, solve,
    analyze_moves, advance_turn, check_terminal,
)

# ── CLI 交互层 ──
from cli import play_turn, apply_move, execute_forced_move

# ── 同盟序列分析 ──
from sequence import (
    find_winning_sequence, format_sequence,
    find_best_response, format_best_response,
    enumerate_da_moves, verify_all_da_moves,
    format_multi_da_verification,
)
