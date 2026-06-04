"""Performance Optimizer - Speed up slow computers.

This module adds optimization features to the cleanup system:
1. Disable unnecessary startup programs
2. Stop unnecessary services
3. Clean scheduled tasks
4. Optimize memory usage
5. Disable background apps
"""
from __future__ import annotations
import os
import sys
import subprocess
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

import logging
from .types import _human_bytes

log = logging.getLogger(__name__)


@dataclass
class OptimizationItem:
    """A single optimization action."""
    name: str
    category: str  # STARTUP, SERVICE, TASK, APP
    impact: str  # HIGH, MEDIUM, LOW
    description: str
    action: str
    enabled: bool
    safe_to_disable: bool


@dataclass
class OptimizationReport:
    """Report of optimizations performed."""
    items: list[OptimizationItem] = field(default_factory=list)
    cpu_saved: float = 0
    memory_saved: int = 0
    summary: str = ""


class PerformanceOptimizer:
    """Optimizes system performance."""
    
    # Safe to disable startup programs
    SAFE_STARTUP = {
        'QQPCTray': '腾讯电脑管家',
        'FlClash': '代理工具',
        'kaiatray': 'ASUS AI助手',
    }
    
    # Safe to stop services
    SAFE_SERVICES = {
        'SysMain': 'Superfetch (预加载)',
        'WSearch': 'Windows Search索引',
        'DiagTrack': '遥测数据收集',
        'dmwappushservice': '推送服务',
    }
    
    # Safe to disable scheduled tasks
    SAFE_TASKS = [
        'MicrosoftEdgeUpdateTask',
        'GoogleUpdateTask',
        'AdobeARM',
        'CCleaner',
    ]
    
    def __init__(self):
        self.items = []
        self.freed_memory = 0
    
    def analyze(self) -> list[OptimizationItem]:
        """Analyze system and find optimization opportunities."""
        items = []
        
        # 1. Startup programs
        items.extend(self._analyze_startup())
        
        # 2. Services
        items.extend(self._analyze_services())
        
        # 3. Scheduled tasks
        items.extend(self._analyze_tasks())
        
        # 4. Background apps
        items.extend(self._analyze_apps())
        
        self.items = items
        return items
    
    def _analyze_startup(self) -> list[OptimizationItem]:
        """Analyze startup programs."""
        items = []
        
        try:
            # shell=True required for wmic
            result = subprocess.run(
                'wmic startup get caption,command',
                shell=True, capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line or 'Caption' in line:
                    continue
                
                for name, desc in self.SAFE_STARTUP.items():
                    if name.lower() in line.lower():
                        items.append(OptimizationItem(
                            name=name,
                            category='STARTUP',
                            impact='MEDIUM',
                            description=f'禁用启动项: {desc}',
                            action=f'disable_startup("{name}")',
                            enabled=True,
                            safe_to_disable=True,
                        ))
        except (subprocess.SubprocessError, OSError):
            pass

        return items

    def _analyze_services(self) -> list[OptimizationItem]:
        """Analyze running services."""
        items = []
        
        try:
            # shell=True required for PowerShell pipeline
            result = subprocess.run(
                'powershell "Get-Service | Where-Object {$_.Status -eq \'Running\'} | Select-Object Name"',
                shell=True, capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line or 'Name' in line:
                    continue
                
                for name, desc in self.SAFE_SERVICES.items():
                    if name.lower() == line.lower():
                        items.append(OptimizationItem(
                            name=name,
                            category='SERVICE',
                            impact='HIGH',
                            description=f'停止服务: {desc}',
                            action=f'stop_service("{name}")',
                            enabled=True,
                            safe_to_disable=True,
                        ))
        except (subprocess.SubprocessError, OSError):
            pass

        return items

    def _analyze_tasks(self) -> list[OptimizationItem]:
        """Analyze scheduled tasks."""
        items = []
        
        try:
            result = subprocess.run(
                'schtasks /query /fo csv',
                shell=True, capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.splitlines():
                for task in self.SAFE_TASKS:
                    if task.lower() in line.lower():
                        items.append(OptimizationItem(
                            name=task,
                            category='TASK',
                            impact='LOW',
                            description=f'禁用计划任务: {task}',
                            action=f'disable_task("{task}")',
                            enabled=True,
                            safe_to_disable=True,
                        ))
        except (subprocess.SubprocessError, OSError):
            pass

        return items

    def _analyze_apps(self) -> list[OptimizationItem]:
        """Analyze background apps."""
        items = []
        
        # Check for heavy background apps
        heavy_apps = {
            'qianwen': ('通义千问AI', 'HIGH'),
            'QQPCTray': ('腾讯电脑管家', 'MEDIUM'),
            'FlClash': ('代理工具', 'LOW'),
            'kaiatray': ('ASUS AI助手', 'MEDIUM'),
        }
        
        try:
            # shell=True required for PowerShell pipeline
            result = subprocess.run(
                'powershell "Get-Process | Select-Object Name"',
                shell=True, capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line or 'Name' in line:
                    continue
                
                for name, (desc, impact) in heavy_apps.items():
                    if name.lower() == line.lower():
                        items.append(OptimizationItem(
                            name=name,
                            category='APP',
                            impact=impact,
                            description=f'关闭后台应用: {desc}',
                            action=f'stop_app("{name}")',
                            enabled=True,
                            safe_to_disable=True if impact != 'HIGH' else False,
                        ))
        except (subprocess.SubprocessError, OSError):
            pass

        return items

    def apply_optimization(self, item: OptimizationItem, dry_run: bool = True) -> bool:
        """Apply a single optimization."""
        try:
            if item.category == 'STARTUP':
                if dry_run:
                    log.info('[DRY RUN] Would disable startup: %s', item.name)
                    return True
                return self._disable_startup(item.name)
            elif item.category == 'SERVICE':
                if dry_run:
                    log.info('[DRY RUN] Would stop service: %s', item.name)
                    return True
                return self._stop_service(item.name)
            elif item.category == 'TASK':
                if dry_run:
                    log.info('[DRY RUN] Would disable task: %s', item.name)
                    return True
                return self._disable_task(item.name)
            elif item.category == 'APP':
                if dry_run:
                    log.info('[DRY RUN] Would stop app: %s', item.name)
                    return True
                return self._stop_app(item.name)
            else:
                log.warning('Unknown category: %s', item.category)
                return False
        except Exception as e:
            log.error('Error: %s', e)
            return False
    
    def _disable_startup(self, name: str) -> bool:
        """Disable a startup program."""
        try:
            # Use registry to disable
            subprocess.run(
                ['reg', 'delete',
                 r'HKCU\Software\Microsoft\Windows\CurrentVersion\Run',
                 '/v', name, '/f'],
                capture_output=True, timeout=5
            )
            return True
        except (subprocess.SubprocessError, OSError):
            return False

    def _stop_service(self, name: str) -> bool:
        """Stop a service."""
        try:
            subprocess.run(['net', 'stop', name], capture_output=True, timeout=10)
            return True
        except (subprocess.SubprocessError, OSError):
            return False

    def _disable_task(self, name: str) -> bool:
        """Disable a scheduled task."""
        try:
            subprocess.run(['schtasks', '/change', '/tn', name, '/disable'], capture_output=True, timeout=5)
            return True
        except (subprocess.SubprocessError, OSError):
            return False

    def _stop_app(self, name: str) -> bool:
        """Stop an application."""
        try:
            subprocess.run(['taskkill', '/f', '/im', f'{name}.exe'], capture_output=True, timeout=5)
            return True
        except (subprocess.SubprocessError, OSError):
            return False
    
    def generate_report(self) -> OptimizationReport:
        """Generate optimization report."""
        if not self.items:
            self.analyze()
        
        summary_lines = []
        for item in self.items:
            if item.safe_to_disable:
                summary_lines.append(f'✅ {item.description} (影响: {item.impact})')
            else:
                summary_lines.append(f'⚠️ {item.description} (需要确认)')
        
        return OptimizationReport(
            items=self.items,
            summary='\n'.join(summary_lines),
        )
    
    def print_report(self, report: OptimizationReport):
        """Print optimization report."""
        print('\n' + '=' * 70)
        print(' ⚡ 性能优化建议')
        print('=' * 70)
        
        # Group by category
        categories = {}
        for item in report.items:
            categories.setdefault(item.category, []).append(item)
        
        for cat, items in categories.items():
            print(f'\n📋 {cat}:')
            for item in items:
                icon = '✅' if item.safe_to_disable else '⚠️'
                print(f'  {icon} {item.description}')
                print(f'     影响: {item.impact} | 可禁用: {"是" if item.safe_to_disable else "否"}')
        
        print('\n' + '=' * 70)
