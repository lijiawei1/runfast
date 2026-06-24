"""夺A快跑 — MVC 分层日志引擎

分层设计：
  Model  — 结构化日志事件（纯数据 dataclass，零 IO 依赖）
  View   — CLI 终端渲染 + Web Streamlit 字典转换
  Bridge — 便捷函数（供 CLI/Web 统一调用，产生事件 + 渲染）

CLI 和 Web 共享同一套 Model，各自使用不同的 View 渲染。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional, Any


# ══════════════════════════════════════════════════════════════════════
# Model Layer  —  结构化日志事件（纯数据，零 IO）
# ══════════════════════════════════════════════════════════════════════

@dataclass
class LogEntry:
    """所有日志事件的基类（标记类型）"""
    pass


@dataclass
class Section(LogEntry):
    """分节符 —— ★回合 / 对手回合 / 游戏结束 / 阶段切换"""
    title: str                           # 标题文字
    style: Literal["double", "single"]   # double = ═══, single = ───


@dataclass
class MoveLog(LogEntry):
    """出牌动作 —— ★出牌 / 对手出牌 / 强制执行"""
    player_id: int              # 0=★, 1~4=对手
    player_label: str           # "★" / "玩家1"
    move_desc: str              # "♦A（单张）"
    remaining: str              # "[♥3, ♣5, ♥5, ♦6, ♠6]"
    is_forced: bool = False     # 是否强制执行（模式二）
    is_star: bool = False       # 是否★出牌
    global_max: bool = False    # 是否触发全局最大接管


@dataclass
class PassLog(LogEntry):
    """不出 / Pass"""
    player_id: int
    player_label: str
    remaining: str


@dataclass
class AnalysisLog(LogEntry):
    """局面分析 —— 📊 局面分析：✅ ★必胜 / ❌ ★必败"""
    is_win: bool                # ★是否必胜
    hand_str: str               # 手牌文字列表
    trick_str: str              # 桌上描述


@dataclass
class MovesListLog(LogEntry):
    """可选出牌列表"""
    entries: list   # [(is_win: bool, type_cn: str, cards_str: str, orders_str: str), ...]


@dataclass
class SeqLine:
    """序列中的一行"""
    player_label: str      # "★" / "玩家1"
    action: str            # "出 ♦A（单张）"
    is_final: bool = False


@dataclass
class SequenceLog(LogEntry):
    """同盟序列 —— 必胜序列 / 最优应对序列"""
    title: str                          # "同盟必胜序列" / "同盟最优应对序列"
    lines: list     = field(default_factory=list)   # list[SeqLine]
    footer: str     = ""                            # "★ 最终失败！"
    has_star_winning: bool = False


@dataclass
class EventLog(LogEntry):
    """关键事件 —— 全局最大 / 终局获胜 / 抢A成功 等"""
    emoji: str
    message: str


@dataclass
class SetupLog(LogEntry):
    """初始化信息 —— 发牌 / 抢A / 换手 / 初始状态"""
    lines: list = field(default_factory=list)   # 多行文本


@dataclass
class MultiDaLog(LogEntry):
    """多♦A出牌分支验证结果"""
    lines: list = field(default_factory=list)   # 多行格式化文本
    has_star_winning: bool = False


# ══════════════════════════════════════════════════════════════════════
# View Layer  CLI  —  终端渲染
# ══════════════════════════════════════════════════════════════════════

BOX_WIDTH = 42


def _visible_len(s: str) -> int:
    """计算字符串的可见宽度（中文/emoji 宽字符计 2）。"""
    w = 0
    for ch in s:
        if '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f' or '\uff00' <= ch <= '\uffef':
            w += 2
        elif ord(ch) > 127:
            w += 1
        else:
            w += 1
    return w


def print_box_top() -> None:
    """打印双线框顶部"""
    print(f"╔{'═' * (BOX_WIDTH - 2)}╗")


def print_box_bottom() -> None:
    """打印双线框底部"""
    print(f"╚{'═' * (BOX_WIDTH - 2)}╝")


def print_box_sep() -> None:
    """打印双线框分隔线"""
    print(f"╠{'═' * (BOX_WIDTH - 2)}╣")


def print_box_line(content: str = "", align: str = "left") -> None:
    """打印框内行。align: 'left' / 'center'"""
    visible = _visible_len(content)
    pad_total = max(0, BOX_WIDTH - 2 - visible)
    if align == "center":
        left = pad_total // 2
        right = pad_total - left
        text = " " * left + content + " " * right
    else:
        text = content + " " * pad_total
    print(f"║{text}║")


def print_section_star() -> None:
    """打印 ★ 回合分隔框头部"""
    print()
    print_box_top()
    print_box_line("★ 回合", align="center")
    print_box_sep()


def print_section_opponent(is_forced: bool = False) -> None:
    """打印对手回合分隔框头部"""
    print()
    print_box_top()
    title = "对手回合（强制执行）" if is_forced else "对手回合"
    print_box_line(title, align="center")
    print_box_sep()


def print_section_static() -> None:
    """打印静态分析分隔框头部"""
    print()
    print_box_top()
    print_box_line("📈 静态分析：多♦A分支验证", align="center")
    print_box_sep()


def print_section_game_end() -> None:
    """打印终局分隔框头部"""
    print()
    print_box_top()
    print_box_line("🎉 游戏结束", align="center")
    print_box_sep()


# ── 内部渲染函数（统一缩进规范）──

def _print_section_cli(entry: Section) -> None:
    """渲染分节符到终端（非框内场景使用）"""
    if entry.style == "double":
        line = "═" * 6
        print(f"\n{line} {entry.title} {line}")
    else:
        line = "─" * 4
        print(f"\n{line} {entry.title} {line}")


def _print_move_cli(entry: MoveLog) -> None:
    """渲染出牌到终端"""
    if entry.is_star:
        prefix = ""
    elif entry.is_forced:
        prefix = "🤖 "
    else:
        prefix = "🤖 "

    print(f"  {prefix}{entry.player_label} 出: {entry.move_desc}")
    print(f"    剩余: {entry.remaining}")
    if entry.global_max:
        print("  🎯 全局最大！直接继续出牌")


def _print_pass_cli(entry: PassLog) -> None:
    """渲染Pass到终端"""
    if entry.player_id == 0:
        print(f"  😔 {entry.player_label} 选择不出(Pass)")
    else:
        print(f"  ⏭ 🤖 {entry.player_label} 选择不出(Pass)")
    print(f"    剩余: {entry.remaining}")


def _print_analysis_cli(entry: AnalysisLog) -> None:
    """渲染局面分析到终端"""
    emoji = "✅" if entry.is_win else "❌"
    result = "★必胜" if entry.is_win else "★必败"
    print(f"  📊 局面：{emoji} {result}")


def _print_moves_list_cli(entry: MovesListLog) -> None:
    """渲染可选出牌列表到终端"""
    print("  📋 可选出牌：")
    for is_win, type_cn, cards_str, orders_str in entry.entries:
        emoji = "✅" if is_win else "❌"
        print(f"     {emoji} {type_cn}: {cards_str}  [{orders_str}]")


def _print_sequence_cli(entry: SequenceLog) -> None:
    """渲染同盟序列到终端"""
    print(f"📋 {entry.title}：")
    for line in entry.lines:
        if line.is_final:
            print(f"   {line.player_label} {line.action}")
        else:
            print(f"   → {line.player_label} → {line.action}")


def _print_event_cli(entry: EventLog) -> None:
    """渲染关键事件到终端"""
    print(f"  {entry.emoji} {entry.message}")


def _print_setup_cli(entry: SetupLog) -> None:
    """渲染初始化信息到终端"""
    for line in entry.lines:
        if line.startswith("=== "):
            print(f"  {line}")
        else:
            print(line)


def _print_multi_da_cli(entry: MultiDaLog) -> None:
    """渲染多♦A分支验证到终端（使用框内格式）"""
    for line in entry.lines:
        if line.strip():
            print_box_line(f"  {line}")
        else:
            print_box_line()


def render_entry_cli(entry: LogEntry) -> None:
    """根据入口类型派发到对应的 CLI 渲染函数"""
    if isinstance(entry, Section):
        _print_section_cli(entry)
    elif isinstance(entry, MoveLog):
        _print_move_cli(entry)
    elif isinstance(entry, PassLog):
        _print_pass_cli(entry)
    elif isinstance(entry, AnalysisLog):
        _print_analysis_cli(entry)
    elif isinstance(entry, MovesListLog):
        _print_moves_list_cli(entry)
    elif isinstance(entry, SequenceLog):
        _print_sequence_cli(entry)
    elif isinstance(entry, EventLog):
        _print_event_cli(entry)
    elif isinstance(entry, SetupLog):
        _print_setup_cli(entry)
    elif isinstance(entry, MultiDaLog):
        _print_multi_da_cli(entry)
    else:
        # 未知类型 → 安全降级：尝试 str
        print(f"[?] {entry!r}")


# ══════════════════════════════════════════════════════════════════════
# View Layer  Web  —  Streamlit 字典转化
# ══════════════════════════════════════════════════════════════════════

def to_web_dict(entry: LogEntry) -> dict[str, Any]:
    """将日志事件转换为 Web 端可用的字典（兼容现有 app.py 的 _add_log 格式）

    返回字典包含：
      - "type": 事件类型字符串
      - "data": 结构化字段
      - 保留旧字段: "player", "label", "action", "cards", "remaining", "note"
    """
    if isinstance(entry, Section):
        return {
            "type": "section",
            "title": entry.title,
            "style": entry.style,
        }
    elif isinstance(entry, MoveLog):
        action = "强制出牌" if entry.is_forced else "出牌"
        note_parts = []
        if entry.global_max:
            note_parts.append("全局最大接管")
        return {
            "type": "move",
            "player": entry.player_id,
            "label": entry.player_label,
            "action": action,
            "cards": entry.move_desc,
            "remaining": entry.remaining,
            "note": ", ".join(note_parts),
            "is_forced": entry.is_forced,
            "global_max": entry.global_max,
        }
    elif isinstance(entry, PassLog):
        return {
            "type": "pass",
            "player": entry.player_id,
            "label": entry.player_label,
            "action": "Pass",
            "cards": "—",
            "remaining": entry.remaining,
            "note": "",
        }
    elif isinstance(entry, AnalysisLog):
        emoji = "✅" if entry.is_win else "❌"
        result = "★必胜" if entry.is_win else "★必败"
        return {
            "type": "analysis",
            "is_win": entry.is_win,
            "result": result,
            "text": f"{emoji} {result}",
            "hand_str": entry.hand_str,
            "trick_str": entry.trick_str,
        }
    elif isinstance(entry, MovesListLog):
        return {
            "type": "moves_list",
            "entries": entry.entries,
        }
    elif isinstance(entry, SequenceLog):
        return {
            "type": "sequence",
            "title": entry.title,
            "lines": [{"label": l.player_label, "action": l.action, "is_final": l.is_final}
                       for l in entry.lines],
            "footer": entry.footer,
            "has_star_winning": entry.has_star_winning,
        }
    elif isinstance(entry, EventLog):
        return {
            "type": "event",
            "emoji": entry.emoji,
            "message": entry.message,
            "player": -2,
            "label": "",
            "action": entry.emoji,
            "cards": entry.message,
            "remaining": "",
            "note": "",
        }
    elif isinstance(entry, SetupLog):
        return {
            "type": "setup",
            "lines": entry.lines,
            "player": -1,
            "label": "",
            "action": "游戏开始",
            "cards": "",
            "remaining": "",
            "note": "",
        }
    elif isinstance(entry, MultiDaLog):
        text = "\n".join(entry.lines)
        return {
            "type": "multi_da",
            "text": text,
            "has_star_winning": entry.has_star_winning,
        }
    else:
        return {"type": "unknown", "raw": repr(entry)}


# ══════════════════════════════════════════════════════════════════════
# Bridge Layer  —  便捷函数（产生 LogEntry + 渲染/转换）
# ══════════════════════════════════════════════════════════════════════

# ── 分段快捷函数 ──

def log_section(title: str, style: Literal["double", "single"] = "double",
                to_web: bool = False) -> LogEntry:
    """打印分节符。style: 'double'(═══) 或 'single'(───)"""
    entry = Section(title=title, style=style)
    if not to_web:
        _print_section_cli(entry)
    return entry


def log_star_turn(title: str = "★ 回合") -> Section:
    """快捷：★回合分隔线"""
    return log_section(title, style="double")


def log_opponent_turn(title: str = "对手回合") -> Section:
    """快捷：对手回合分隔线"""
    return log_section(title, style="single")


def log_game_end(title: str = "游戏结束") -> Section:
    """快捷：游戏结束分隔线"""
    return log_section(title, style="double")


# ── 出牌动作 ──

def log_move(player_id: int, player_label: str, move_desc: str,
             remaining: str, *, is_forced: bool = False,
             global_max: bool = False, to_web: bool = False) -> MoveLog:
    """记录并打印出牌动作"""
    entry = MoveLog(
        player_id=player_id,
        player_label=player_label,
        move_desc=move_desc,
        remaining=remaining,
        is_forced=is_forced,
        is_star=(player_id == 0),
        global_max=global_max,
    )
    if not to_web:
        _print_move_cli(entry)
    return entry


def log_star_move(remaining: str, move_desc: str, *,
                  global_max: bool = False,
                  to_web: bool = False) -> MoveLog:
    """快捷：★出牌"""
    return log_move(0, "★", move_desc, remaining,
                    is_forced=False, global_max=global_max,
                    to_web=to_web)


def log_opponent_move(player_id: int, remaining: str, move_desc: str, *,
                      is_forced: bool = False,
                      global_max: bool = False,
                      to_web: bool = False) -> MoveLog:
    """快捷：对手出牌"""
    return log_move(player_id, f"玩家{player_id}", move_desc, remaining,
                    is_forced=is_forced, global_max=global_max,
                    to_web=to_web)


# ── Pass ──

def log_pass(player_id: int, player_label: str, remaining: str,
             to_web: bool = False) -> PassLog:
    """记录并打印Pass"""
    entry = PassLog(
        player_id=player_id,
        player_label=player_label,
        remaining=remaining,
    )
    if not to_web:
        _print_pass_cli(entry)
    return entry


# ── 局面分析 ──

def log_analysis(is_win: bool, hand_str: str, trick_str: str,
                 to_web: bool = False) -> AnalysisLog:
    """记录并打印局面分析"""
    entry = AnalysisLog(
        is_win=is_win,
        hand_str=hand_str,
        trick_str=trick_str,
    )
    if not to_web:
        _print_analysis_cli(entry)
    return entry


# ── 可选出牌列表 ──

def log_moves_list(entries: list, to_web: bool = False) -> MovesListLog:
    """记录并打印可选出牌列表。
    entries: [(is_win: bool, type_cn: str, cards_str: str, orders_str: str), ...]
    """
    entry = MovesListLog(entries=entries)
    if not to_web:
        _print_moves_list_cli(entry)
    return entry


# ── 同盟序列 ──

def log_sequence(title: str, lines: list, footer: str = "",
                 has_star_winning: bool = False,
                 to_web: bool = False) -> SequenceLog:
    """记录并打印同盟序列。
    lines: [(player_label, action_str, is_final), ...]
    """
    seq_lines = [SeqLine(player_label=pl, action=act, is_final=isf)
                 for pl, act, isf in lines]
    entry = SequenceLog(
        title=title,
        lines=seq_lines,
        footer=footer,
        has_star_winning=has_star_winning,
    )
    if not to_web:
        _print_sequence_cli(entry)
    return entry


# ── 关键事件 ──

def log_event(emoji: str, message: str, to_web: bool = False) -> EventLog:
    """记录并打印关键事件"""
    entry = EventLog(emoji=emoji, message=message)
    if not to_web:
        _print_event_cli(entry)
    return entry


def log_global_max() -> EventLog:
    """快捷：全局最大"""
    return log_event("🎯", "全局最大！直接继续出牌")


def log_star_win() -> EventLog:
    """快捷：★获胜"""
    return log_event("🎉", "★ 获胜！")


def log_star_lose(winner_id: int) -> EventLog:
    """快捷：对手获胜"""
    return log_event("💀", f"玩家{winner_id}先出完，★失败！")


# ── 初始化信息 ──

def log_setup(lines: list[str], to_web: bool = False) -> SetupLog:
    """记录并打印初始化信息"""
    entry = SetupLog(lines=lines)
    if not to_web:
        _print_setup_cli(entry)
    return entry


# ── 多♦A分支验证 ──

def log_multi_da(lines: list[str], has_star_winning: bool = False,
                 to_web: bool = False) -> MultiDaLog:
    """记录并打印多♦A分支验证结果"""
    entry = MultiDaLog(lines=lines, has_star_winning=has_star_winning)
    if not to_web:
        _print_multi_da_cli(entry)
    return entry
