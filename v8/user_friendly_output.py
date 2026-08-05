"""用户友好的输出格式

用通俗易懂的语言解释每个垃圾是什么，清理后有什么后果，为什么会积累。
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class CleanupItem:
    """清理项目"""
    name: str
    size: str
    what_is_it: str  # 这是什么
    why_exists: str  # 为什么会积累
    what_happens_if_clean: str  # 清理后会怎样
    risk: str  # safe/review/high
    can_undo: bool  # 能否撤销


# 垃圾类型解释库
GARBAGE_EXPLANATIONS = {
    "System memory dump": {
        "name": "系统崩溃转储",
        "what_is_it": "当 Windows 蓝屏死机时，系统会把当时的内存信息保存下来，方便技术人员分析问题。",
        "why_exists": "每次蓝屏都会生成一个，时间长了就积累很多。",
        "what_happens_if_clean": "删除后不影响正常使用。下次蓝屏时会重新生成。",
        "risk": "safe",
        "can_undo": False,
    },
    "Windows component store": {
        "name": "Windows 更新残留",
        "what_is_it": "Windows 更新时下载的安装包和备份文件，更新完成后就没用了。",
        "why_exists": "每次 Windows 更新都会留下这些文件，方便回滚。",
        "what_happens_if_clean": "删除后无法回滚到旧版本，但可以释放大量空间。",
        "risk": "safe",
        "can_undo": False,
    },
    "Recycle Bin": {
        "name": "回收站",
        "what_is_it": "你删除的文件其实没有真正删除，都放在回收站里。",
        "why_exists": "防止误删文件，可以随时恢复。",
        "what_happens_if_clean": "永久删除，无法恢复。请确认回收站里没有重要文件。",
        "risk": "safe",
        "can_undo": False,
    },
    "Crash dumps": {
        "name": "程序崩溃记录",
        "what_is_it": "程序崩溃时保存的错误信息，用于调试。",
        "why_exists": "每次程序崩溃都会生成一个。",
        "what_happens_if_clean": "删除后不影响程序运行，只是丢失了崩溃记录。",
        "risk": "safe",
        "can_undo": False,
    },
    "Explorer thumbnail": {
        "name": "缩略图缓存",
        "what_is_it": "文件管理器里显示的图片、视频预览图。",
        "why_exists": "每次打开文件夹都会生成预览图，方便快速查看。",
        "what_happens_if_clean": "删除后打开文件夹会重新生成预览图，稍慢一点。",
        "risk": "safe",
        "can_undo": False,
    },
    "GPU shader cache": {
        "name": "显卡着色器缓存",
        "what_is_it": "游戏和图形程序的渲染缓存，让画面加载更快。",
        "why_exists": "每次运行游戏/图形程序都会生成。",
        "what_happens_if_clean": "删除后下次打开游戏会重新编译着色器，首次加载稍慢。",
        "risk": "safe",
        "can_undo": False,
    },
    "npm Cache": {
        "name": "npm 依赖缓存",
        "what_is_it": "Node.js 项目用的第三方库的下载缓存。",
        "why_exists": "每次 npm install 都会下载并缓存。",
        "what_happens_if_clean": "删除后下次 npm install 会重新下载，不影响项目。",
        "risk": "safe",
        "can_undo": False,
    },
    "uv package cache": {
        "name": "Python 包缓存",
        "what_is_it": "Python 包管理器 uv 的下载缓存。",
        "why_exists": "每次安装 Python 包都会缓存。",
        "what_happens_if_clean": "删除后下次安装包会重新下载，不影响项目。",
        "risk": "safe",
        "can_undo": False,
    },
    "pip Cache": {
        "name": "pip 包缓存",
        "what_is_it": "Python pip 的下载缓存。",
        "why_exists": "每次 pip install 都会缓存。",
        "what_happens_if_clean": "删除后下次 pip install 会重新下载，不影响项目。",
        "risk": "safe",
        "can_undo": False,
    },
    "Docker Data": {
        "name": "Docker 数据",
        "what_is_it": "Docker 容器、镜像、卷的数据。",
        "why_exists": "运行 Docker 容器时产生的数据。",
        "what_happens_if_clean": "删除后需要重新拉取镜像，容器数据会丢失。",
        "risk": "review",
        "can_undo": False,
    },
    "System temporary files": {
        "name": "系统临时文件",
        "what_is_it": "各种程序运行时产生的临时文件。",
        "why_exists": "程序运行时需要临时存储数据，用完应该删除但有时没删。",
        "what_happens_if_clean": "删除后不影响系统运行，程序会自动重建需要的临时文件。",
        "risk": "safe",
        "can_undo": False,
    },
    "Component-Based Servicing logs": {
        "name": "Windows 组件日志",
        "what_is_it": "Windows 更新和服务包的安装日志。",
        "why_exists": "每次 Windows 更新都会记录日志。",
        "what_happens_if_clean": "删除后不影响系统运行，只是丢失了安装记录。",
        "risk": "safe",
        "can_undo": False,
    },
    "NuGet Cache": {
        "name": "NuGet 包缓存",
        "what_is_it": ".NET 项目的第三方库缓存。",
        "why_exists": "每次 NuGet restore 都会缓存。",
        "what_happens_if_clean": "删除后下次 restore 会重新下载，不影响项目。",
        "risk": "safe",
        "can_undo": False,
    },
    "Cargo Cache": {
        "name": "Rust 依赖缓存",
        "what_is_it": "Rust 项目的依赖库缓存。",
        "why_exists": "每次 cargo build 都会下载并缓存。",
        "what_happens_if_clean": "删除后下次 cargo build 会重新下载，不影响项目。",
        "risk": "safe",
        "can_undo": False,
    },
    "Chrome browser cache": {
        "name": "Chrome 浏览器缓存",
        "what_is_it": "网页的临时文件，让下次访问更快。",
        "why_exists": "每次访问网页都会缓存图片、脚本等。",
        "what_happens_if_clean": "删除后下次访问网页会稍慢，但网页内容不受影响。",
        "risk": "safe",
        "can_undo": False,
    },
    "Edge browser cache": {
        "name": "Edge 浏览器缓存",
        "what_is_it": "Edge 浏览器的临时文件。",
        "why_exists": "每次访问网页都会缓存。",
        "what_happens_if_clean": "删除后下次访问网页会稍慢。",
        "risk": "safe",
        "can_undo": False,
    },
    "Playwright browser cache": {
        "name": "Playwright 浏览器缓存",
        "what_is_it": "自动化测试工具 Playwright 下载的浏览器。",
        "why_exists": "运行自动化测试时需要。",
        "what_happens_if_clean": "删除后下次运行测试会重新下载浏览器。",
        "risk": "safe",
        "can_undo": False,
    },
    "WSL data": {
        "name": "WSL 子系统数据",
        "what_is_it": "Windows 子系统 Linux 的数据，包括安装的系统和文件。",
        "why_exists": "使用 WSL 时产生的数据。",
        "what_happens_if_clean": "删除后 WSL 系统和文件都会丢失，需要重新安装。",
        "risk": "high",
        "can_undo": False,
    },
    "VMware data": {
        "name": "VMware 虚拟机数据",
        "what_is_it": "VMware 虚拟机的磁盘文件和快照。",
        "why_exists": "创建和运行虚拟机时产生。",
        "what_happens_if_clean": "删除后虚拟机和快照都会丢失。",
        "risk": "high",
        "can_undo": False,
    },
    "QQ/TIM data": {
        "name": "QQ 聊天数据",
        "what_is_it": "QQ 的聊天记录、图片、文件缓存。",
        "why_exists": "使用 QQ 时自动下载和缓存。",
        "what_happens_if_clean": "删除后聊天记录和文件会丢失，但可以重新登录。",
        "risk": "review",
        "can_undo": False,
    },
}


def explain_item(item_name: str, size: str) -> CleanupItem:
    """用通俗易懂的语言解释清理项目"""
    # 查找匹配的解释
    for key, explanation in GARBAGE_EXPLANATIONS.items():
        if key.lower() in item_name.lower():
            return CleanupItem(
                name=explanation["name"],
                size=size,
                what_is_it=explanation["what_is_it"],
                why_exists=explanation["why_exists"],
                what_happens_if_clean=explanation["what_happens_if_clean"],
                risk=explanation["risk"],
                can_undo=explanation["can_undo"],
            )

    # 默认解释
    return CleanupItem(
        name=item_name,
        size=size,
        what_is_it="程序运行时产生的临时文件或缓存。",
        why_exists="程序运行时需要临时存储数据。",
        what_happens_if_clean="删除后程序会自动重建需要的文件。",
        risk="review",
        can_undo=False,
    )


def format_user_friendly(items: List[Dict[str, Any]]) -> str:
    """格式化用户友好的输出"""
    lines = []
    lines.append("=" * 60)
    lines.append("垃圾清理 - 通俗易懂版")
    lines.append("=" * 60)
    lines.append("")

    # 按风险分组
    safe_items = [i for i in items if i.get("risk") == "none"]
    review_items = [i for i in items if i.get("risk") == "med"]
    high_items = [i for i in items if i.get("risk") == "high"]

    if safe_items:
        lines.append("✅ 可以放心删除（不影响使用）")
        lines.append("-" * 40)
        for i, item in enumerate(safe_items, 1):
            name = item.get("what", "未知")
            size = item.get("sz", "未知")
            explanation = explain_item(name, size)

            lines.append(f"{i}. {explanation.name} ({size})")
            lines.append(f"   这是什么：{explanation.what_is_it}")
            lines.append(f"   为什么有：{explanation.why_exists}")
            lines.append(f"   删除后果：{explanation.what_happens_if_clean}")
            lines.append("")

    if review_items:
        lines.append("⚠️ 需要你想一想（可能有重要数据）")
        lines.append("-" * 40)
        for i, item in enumerate(review_items, 1):
            name = item.get("what", "未知")
            size = item.get("sz", "未知")
            explanation = explain_item(name, size)

            lines.append(f"{i}. {explanation.name} ({size})")
            lines.append(f"   这是什么：{explanation.what_is_it}")
            lines.append(f"   为什么有：{explanation.why_exists}")
            lines.append(f"   删除后果：{explanation.what_happens_if_clean}")
            lines.append("")

    if high_items:
        lines.append("🔴 谨慎操作（删除后可能无法恢复）")
        lines.append("-" * 40)
        for i, item in enumerate(high_items, 1):
            name = item.get("what", "未知")
            size = item.get("sz", "未知")
            explanation = explain_item(name, size)

            lines.append(f"{i}. {explanation.name} ({size})")
            lines.append(f"   这是什么：{explanation.what_is_it}")
            lines.append(f"   为什么有：{explanation.why_exists}")
            lines.append(f"   删除后果：{explanation.what_happens_if_clean}")
            lines.append("")

    return "\n".join(lines)


def format_drive_selector() -> str:
    """格式化驱动器选择界面"""
    lines = []
    lines.append("=" * 60)
    lines.append("选择要清理的磁盘")
    lines.append("=" * 60)
    lines.append("")
    lines.append("请选择要扫描的磁盘：")
    lines.append("")
    lines.append("  [1] C: 盘 - 系统盘（通常垃圾最多）")
    lines.append("  [2] D: 盘 - 数据盘")
    lines.append("  [3] E: 盘 - 数据盘")
    lines.append("  [4] 所有磁盘 - 全面扫描")
    lines.append("")
    lines.append("请选择 (1-4): ")
    return "\n".join(lines)


def format_cleanup_mode() -> str:
    """格式化清理方式选择"""
    lines = []
    lines.append("=" * 60)
    lines.append("选择清理方式")
    lines.append("=" * 60)
    lines.append("")
    lines.append("请选择清理方式：")
    lines.append("")
    lines.append("  [1] 快速清理 - 只清理安全项（推荐新手）")
    lines.append("  [2] 标准清理 - 清理安全项 + 需要确认的项")
    lines.append("  [3] 深度清理 - 清理所有项（包括高风险）")
    lines.append("  [4] 自定义 - 逐项选择要清理的内容")
    lines.append("")
    lines.append("请选择 (1-4): ")
    return "\n".join(lines)
