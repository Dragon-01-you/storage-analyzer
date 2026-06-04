"""Cleanup Reporter - Generates detailed cleanup reports.

This module ensures users always know what was cleaned.
"""
from __future__ import annotations
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from .types import _human_bytes


@dataclass
class CleanupItem:
    """A single cleaned item."""
    path: str
    original_size: int
    cleaned_size: int
    category: str  # SAFE, REVIEW, KEEP
    reason: str
    deleted: bool
    timestamp: str


@dataclass
class CleanupReport:
    """Complete cleanup report."""
    drive: str
    before_used: int
    after_used: int
    before_pct: float
    after_pct: float
    items: list[CleanupItem] = field(default_factory=list)
    summary: str = ""
    recommendations: list[str] = field(default_factory=list)


class CleanupReporter:
    """Generates detailed cleanup reports."""
    
    REPORT_DIR = Path.home() / '.cache' / 'storage-analyzer' / 'reports'
    
    def __init__(self):
        self.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    
    def create_report(
        self,
        drive: str,
        before_used: int,
        after_used: int,
        items: list[CleanupItem],
        total_bytes: int = 0,
    ) -> CleanupReport:
        """Create a cleanup report.

        Args:
            total_bytes: Total disk capacity in bytes. Used for accurate
                percentage calculations. If 0, falls back to the old
                approximation (before_used + freed).
        """
        # Calculate percentages
        if total_bytes > 0:
            total = total_bytes
        else:
            total = before_used + (before_used - after_used)  # Fallback approximation
        before_pct = (before_used / total) * 100 if total > 0 else 0
        after_pct = (after_used / total) * 100 if total > 0 else 0
        
        # Generate summary
        freed = before_used - after_used
        summary = f"释放了 {_human_bytes(freed)}，使用率从 {before_pct:.1f}% 降到 {after_pct:.1f}%"
        
        # Generate recommendations
        recommendations = []
        if after_pct > 90:
            recommendations.append("磁盘使用率仍超过90%，建议继续清理")
        elif after_pct > 80:
            recommendations.append("磁盘使用率超过80%，建议定期清理")
        else:
            recommendations.append("磁盘状态健康")
        
        return CleanupReport(
            drive=drive,
            before_used=before_used,
            after_used=after_used,
            before_pct=before_pct,
            after_pct=after_pct,
            items=items,
            summary=summary,
            recommendations=recommendations,
        )
    
    def print_report(self, report: CleanupReport):
        """Print report to console."""
        print('\n' + '=' * 70)
        print(' 🧹 清理汇报')
        print('=' * 70)
        
        # Summary
        print(f'\n📊 清理总结:')
        print(f'   {report.summary}')
        
        # Before/After
        print(f'\n📈 前后对比:')
        print(f'   清理前: {_human_bytes(report.before_used)} ({report.before_pct:.1f}%)')
        print(f'   清理后: {_human_bytes(report.after_used)} ({report.after_pct:.1f}%)')
        print(f'   释放: {_human_bytes(report.before_used - report.after_used)}')
        
        # Cleaned items
        cleaned = [i for i in report.items if i.deleted]
        if cleaned:
            print(f'\n✅ 已清理 ({len(cleaned)} 项):')
            for item in cleaned:
                print(f'   - {item.path}')
                print(f'     大小: {_human_bytes(item.cleaned_size)} | 原因: {item.reason}')
        
        # Kept items
        kept = [i for i in report.items if not i.deleted]
        if kept:
            print(f'\n🔒 已保留 ({len(kept)} 项):')
            for item in kept:
                print(f'   - {item.path}')
                print(f'     大小: {_human_bytes(item.original_size)} | 原因: {item.reason}')
        
        # Recommendations
        if report.recommendations:
            print(f'\n💡 建议:')
            for rec in report.recommendations:
                print(f'   - {rec}')
        
        print('\n' + '=' * 70)
    
    def save_report(self, report: CleanupReport, filename: Optional[str] = None):
        """Save report to file."""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'cleanup_report_{timestamp}.md'
        
        filepath = self.REPORT_DIR / filename
        
        # Generate markdown
        md = self._generate_markdown(report)
        filepath.write_text(md, encoding='utf-8')
        
        print(f'\n📄 报告已保存: {filepath}')
        return filepath
    
    def _generate_markdown(self, report: CleanupReport) -> str:
        """Generate markdown report."""
        lines = [
            '# 🧹 清理汇报',
            '',
            '## 📊 清理总结',
            '',
            f'- **{report.summary}**',
            '',
            '## 📈 前后对比',
            '',
            '| 指标 | 清理前 | 清理后 |',
            '|------|--------|--------|',
            f'| 使用率 | {report.before_pct:.1f}% | {report.after_pct:.1f}% |',
            f'| 已用空间 | {_human_bytes(report.before_used)} | {_human_bytes(report.after_used)} |',
            f'| 释放空间 | - | {_human_bytes(report.before_used - report.after_used)} |',
            '',
        ]
        
        # Cleaned items
        cleaned = [i for i in report.items if i.deleted]
        if cleaned:
            lines.append('## ✅ 已清理项目')
            lines.append('')
            lines.append('| 文件 | 大小 | 原因 |')
            lines.append('|------|------|------|')
            for item in cleaned:
                lines.append(f'| {item.path} | {_human_bytes(item.cleaned_size)} | {item.reason} |')
            lines.append('')
        
        # Kept items
        kept = [i for i in report.items if not i.deleted]
        if kept:
            lines.append('## 🔒 保留项目')
            lines.append('')
            lines.append('| 文件 | 大小 | 原因 |')
            lines.append('|------|------|------|')
            for item in kept:
                lines.append(f'| {item.path} | {_human_bytes(item.original_size)} | {item.reason} |')
            lines.append('')
        
        # Recommendations
        if report.recommendations:
            lines.append('## 💡 建议')
            lines.append('')
            for rec in report.recommendations:
                lines.append(f'- {rec}')
            lines.append('')
        
        lines.append('---')
        lines.append(f'*报告生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*')
        
        return '\n'.join(lines)
