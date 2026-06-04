"""Memory Optimizer - Clean and optimize system memory.

This module:
1. Analyzes memory usage by process
2. Identifies memory hogs
3. Cleans working sets
4. Optimizes Windows memory settings
"""
from __future__ import annotations
import os
import sys
import subprocess
import psutil
from dataclasses import dataclass
from typing import Optional

import logging
from .types import _human_bytes

log = logging.getLogger(__name__)


@dataclass
class MemoryProcess:
    """Process memory information."""
    pid: int
    name: str
    memory_mb: float
    cpu_percent: float
    handles: int
    threads: int
    category: str  # SYSTEM, APP, BROWSER, IDE, AI


class MemoryOptimizer:
    """Optimizes system memory usage."""
    
    # Category patterns
    CATEGORIES = {
        'SYSTEM': ['svchost', 'csrss', 'smss', 'wininit', 'services', 'lsass', 'dwm', 'taskhostw'],
        'BROWSER': ['chrome', 'msedge', 'firefox', 'brave', 'qqbrowser'],
        'IDE': ['code', 'cursor', 'trae', 'opencode', 'codex', 'pycharm'],
        'AI': ['python', 'ollama', 'qianwen', 'claude', 'minimax'],
        'SECURITY': ['QQPCTray', 'MsMpEng', 'SecurityHealthService', 'QQPCRTP'],
        'APP': ['explorer', 'audiodg', 'SearchIndexer', 'OneDrive', 'Weixin', 'BaiduNetdisk'],
    }
    
    def __init__(self):
        self.processes: list[MemoryProcess] = []
        self.total_memory = psutil.virtual_memory().total
        self.used_memory = psutil.virtual_memory().used
    
    def analyze(self) -> list[MemoryProcess]:
        """Analyze all processes and categorize them."""
        self.processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent', 'num_handles', 'num_threads']):
            try:
                info = proc.info
                name = info['name'] or 'Unknown'
                memory_mb = info['memory_info'].rss / (1024 * 1024) if info['memory_info'] else 0
                cpu = info['cpu_percent'] or 0
                handles = info['num_handles'] or 0
                threads = info['num_threads'] or 0
                
                # Categorize
                category = self._categorize(name)
                
                self.processes.append(MemoryProcess(
                    pid=info['pid'],
                    name=name,
                    memory_mb=memory_mb,
                    cpu_percent=cpu,
                    handles=handles,
                    threads=threads,
                    category=category,
                ))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Sort by memory usage
        self.processes.sort(key=lambda x: -x.memory_mb)
        return self.processes
    
    def _categorize(self, name: str) -> str:
        """Categorize a process by name."""
        name_lower = name.lower()
        
        for category, patterns in self.CATEGORIES.items():
            for pattern in patterns:
                if pattern.lower() in name_lower:
                    return category
        
        return 'OTHER'
    
    def get_summary(self) -> dict:
        """Get memory usage summary by category."""
        summary = {}
        
        for proc in self.processes:
            if proc.category not in summary:
                summary[proc.category] = {
                    'count': 0,
                    'total_mb': 0,
                    'processes': [],
                }
            
            summary[proc.category]['count'] += 1
            summary[proc.category]['total_mb'] += proc.memory_mb
            summary[proc.category]['processes'].append(proc)
        
        return summary
    
    def get_memory_hogs(self, threshold_mb: float = 50) -> list[MemoryProcess]:
        """Get processes using more than threshold_mb."""
        return [p for p in self.processes if p.memory_mb > threshold_mb]
    
    def clean_working_sets(self) -> int:
        """Clean working sets of all processes (Windows only)."""
        if sys.platform != 'win32':
            return 0
        
        cleaned = 0
        try:
            # Use EmptyWorkingSet API
            import ctypes
            from ctypes import wintypes
            
            # Get all process IDs
            process_ids = (wintypes.DWORD * 1024)()
            bytes_returned = wintypes.DWORD()
            
            ctypes.windll.psapi.EnumProcesses(
                ctypes.byref(process_ids),
                ctypes.sizeof(process_ids),
                ctypes.byref(bytes_returned)
            )
            
            num_processes = bytes_returned.value // ctypes.sizeof(wintypes.DWORD)
            
            for i in range(num_processes):
                pid = process_ids[i]
                if pid == 0:
                    continue
                
                try:
                    handle = ctypes.windll.kernel32.OpenProcess(
                        0x100,  # PROCESS_SET_QUOTA (only what EmptyWorkingSet needs)
                        False,
                        pid
                    )
                    
                    if handle:
                        ctypes.windll.psapi.EmptyWorkingSet(handle)
                        ctypes.windll.kernel32.CloseHandle(handle)
                        cleaned += 1
                except Exception:
                    pass
        except Exception as e:
            log.error("Error cleaning working sets: %s", e)
        
        return cleaned
    
    def optimize_windows_settings(self, dry_run: bool = True) -> list[str]:
        """Optimize Windows memory settings.

        Args:
            dry_run: If True (default), only print what would be done.
                     If False, actually execute the changes.
        """
        reg_key = r'HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management'
        actions = [
            # shell=True required for PowerShell pipeline
            (['powershell', 'Disable-MMAgent -MemoryCompression'],
             'Disable memory compression', True),
            (['reg', 'add', reg_key,
              '/v', 'ClearPageFileAtShutdown', '/t', 'REG_DWORD', '/d', '1', '/f'],
             'Enable page file clearing on shutdown', False),
            (['reg', 'add', reg_key,
              '/v', 'LargeSystemCache', '/t', 'REG_DWORD', '/d', '1', '/f'],
             'Optimize large system cache', False),
        ]

        applied = []
        for cmd, desc, use_shell in actions:
            if dry_run:
                log.info("[DRY RUN] Would execute: %s", desc)
                applied.append(f'[DRY RUN] {desc}')
            else:
                try:
                    subprocess.run(cmd, shell=use_shell, capture_output=True, timeout=10)
                    applied.append(desc)
                except (subprocess.SubprocessError, OSError):
                    pass

        return applied
    
    def stop_unnecessary_services(self, dry_run: bool = True) -> list[str]:
        """Stop unnecessary services to free memory.

        Args:
            dry_run: If True (default), only print what would be stopped.
                     If False, actually stop the services.
        """
        services_to_stop = [
            ('SysMain', 'Superfetch (预加载)'),
            ('DiagTrack', '遥测数据收集'),
            ('dmwappushservice', '推送服务'),
            ('WSearch', 'Windows Search索引'),
        ]

        stopped = []
        for svc_name, desc in services_to_stop:
            if dry_run:
                log.info("[DRY RUN] Would stop service: %s (%s)", desc, svc_name)
                stopped.append(f'[DRY RUN] {desc}')
            else:
                try:
                    subprocess.run(
                        ['net', 'stop', svc_name],
                        capture_output=True, timeout=10
                    )
                    stopped.append(desc)
                except (subprocess.SubprocessError, OSError):
                    pass

        return stopped
    
    def disable_startup_programs(self, dry_run: bool = True) -> list[str]:
        """Disable unnecessary startup programs.

        Args:
            dry_run: If True (default), only print what would be disabled.
                     If False, actually delete the registry entries.
        """
        programs_to_disable = [
            'QQPCTray',
            'FlClash',
            'kaiatray',
            'BaiduNetdisk',
        ]

        disabled = []
        for prog in programs_to_disable:
            if dry_run:
                log.info("[DRY RUN] Would disable startup program: %s", prog)
                disabled.append(f'[DRY RUN] {prog}')
            else:
                try:
                    subprocess.run(
                        ['reg', 'delete',
                         r'HKCU\Software\Microsoft\Windows\CurrentVersion\Run',
                         '/v', prog, '/f'],
                        capture_output=True, timeout=5
                    )
                    disabled.append(prog)
                except (subprocess.SubprocessError, OSError):
                    pass

        return disabled
    
    def generate_report(self) -> str:
        """Generate memory optimization report."""
        summary = self.get_summary()
        
        lines = [
            "=" * 60,
            " MEMORY OPTIMIZATION REPORT",
            "=" * 60,
            "",
            f"Total Memory: {_human_bytes(self.total_memory)}",
            f"Used Memory: {_human_bytes(self.used_memory)}",
            f"Free Memory: {_human_bytes(self.total_memory - self.used_memory)}",
            f"Usage: {self.used_memory / self.total_memory * 100:.1f}%",
            "",
            "Memory by Category:",
            "-" * 40,
        ]
        
        for category, data in sorted(summary.items(), key=lambda x: -x[1]['total_mb']):
            lines.append(f"  {category:15s}: {data['total_mb']:8.1f}MB ({data['count']} processes)")
        
        lines.append("")
        lines.append("Top 10 Memory Hogs:")
        lines.append("-" * 40)
        
        for proc in self.processes[:10]:
            lines.append(f"  {proc.name:20s}: {proc.memory_mb:8.1f}MB (PID: {proc.pid})")
        
        return "\n".join(lines)
