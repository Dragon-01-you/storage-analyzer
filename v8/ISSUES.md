# Storage Analyzer v8 -- 深度审计报告

**审计日期**: 2026-06-04
**审计范围**: memory_optimizer.py, performance_optimizer.py, iterative_scanner.py, scanner_v3.py

---

## 1. 安全问题

| 编号 | 文件 | 行号 | 问题 | 严重性 | 修复建议 |
|------|------|------|------|--------|----------|
| S-01 | memory_optimizer.py | 144-148 | `OpenProcess` 使用 `PROCESS_ALL_ACCESS` (0x1F0FFF) 权限过大，仅为调用 `EmptyWorkingSet` 只需 `PROCESS_SET_QUOTA` (0x100) | 高 | 改为 `0x100`，遵循最小权限原则 |
| S-02 | memory_optimizer.py | 161-195 | `optimize_windows_settings()` 直接修改注册表和系统内存策略，无用户确认 | 高 | 添加确认提示或 dry-run 模式 |
| S-03 | memory_optimizer.py | 197-217 | `stop_unnecessary_services()` 直接停止 Windows 服务（含 WSearch），无用户确认 | 高 | 添加确认提示，记录原始服务状态以便恢复 |
| S-04 | memory_optimizer.py | 219-239 | `disable_startup_programs()` 直接删除注册表启动项，无用户确认，且无法恢复 | 高 | 添加确认提示，先备份注册表项再删除 |
| S-05 | performance_optimizer.py | 236 | 注册表路径使用未转义的反斜杠 `HKCU\Software\...`，在 f-string 中可能产生意外的转义序列 | 中 | 使用原始字符串 `r"HKCU\Software\..."` 或双反斜杠 |
| S-06 | performance_optimizer.py | 217-264 | `_disable_startup`, `_stop_service`, `_disable_task`, `_stop_app` 四个方法直接执行破坏性操作，无确认机制 | 高 | 添加用户确认层，`apply_optimization` 调用前需二次确认 |
| S-07 | scanner_v3.py | 290-301 | `CleanupEngine.delete_item()` 直接调用 `shutil.rmtree`，无确认、无回收站、无回滚 | 高 | 删除前显示详细信息，先移至回收站而非直接删除 |
| S-08 | scanner_v3.py | 303-312 | `delete_safe_items()` 批量删除所有 SAFE 分类文件，但分类逻辑过于粗糙（小文件默认 SAFE） | 高 | 降低自动删除的信任级别，批量删除前需用户确认完整列表 |
| S-09 | scanner_v3.py | 240 | 未知小文件默认分类为 `SAFE`，可能误删重要配置文件 | 高 | 默认改为 `UNKNOWN`，需用户审查 |
| S-10 | scanner_v3.py | 42-58 | SAFE_PATTERNS 过于宽泛，`'build'` 和 `'dist'` 可能匹配到有用的构建输出 | 中 | 改为路径级别匹配（如 `.next/cache` 而非单纯 `build`），增加白名单机制 |

---

## 2. 代码质量问题

### 2.1 裸 `except:` 子句（吞没所有异常）

| 编号 | 文件 | 行号 | 问题 | 严重性 | 修复建议 |
|------|------|------|------|--------|----------|
| Q-01 | memory_optimizer.py | 154 | `except:` 裸子句，吞没 `OpenProcess`/`EmptyWorkingSet` 中所有异常（含 `KeyboardInterrupt`） | 中 | 改为 `except (OSError, WindowsError):` |
| Q-02 | memory_optimizer.py | 172 | `except:` 裸子句，吞没 `Disable-MMAgent` 执行失败 | 中 | 改为 `except (subprocess.SubprocessError, OSError):` |
| Q-03 | memory_optimizer.py | 181 | `except:` 裸子句，吞没注册表写入失败 | 中 | 改为 `except (subprocess.SubprocessError, OSError):` |
| Q-04 | memory_optimizer.py | 192 | `except:` 裸子句，吞没注册表写入失败 | 中 | 改为 `except (subprocess.SubprocessError, OSError):` |
| Q-05 | memory_optimizer.py | 214 | `except:` 裸子句，吞没 `net stop` 服务停止失败 | 中 | 改为 `except (subprocess.SubprocessError, OSError):` |
| Q-06 | memory_optimizer.py | 236 | `except:` 裸子句，吞没注册表删除失败 | 中 | 改为 `except (subprocess.SubprocessError, OSError):` |
| Q-07 | performance_optimizer.py | 118 | `_analyze_startup` 中 `except:` 裸子句 | 中 | 改为 `except (subprocess.SubprocessError, OSError):` |
| Q-08 | performance_optimizer.py | 148 | `_analyze_services` 中 `except:` 裸子句 | 中 | 改为 `except (subprocess.SubprocessError, OSError):` |
| Q-09 | performance_optimizer.py | 175 | `_analyze_tasks` 中 `except:` 裸子句 | 中 | 改为 `except (subprocess.SubprocessError, OSError):` |
| Q-10 | performance_optimizer.py | 213 | `_analyze_apps` 中 `except:` 裸子句 | 中 | 改为 `except (subprocess.SubprocessError, OSError):` |
| Q-11 | performance_optimizer.py | 239 | `_disable_startup` 中 `except:` 裸子句 | 中 | 改为 `except (subprocess.SubprocessError, OSError):` |
| Q-12 | performance_optimizer.py | 247 | `_stop_service` 中 `except:` 裸子句 | 中 | 改为 `except (subprocess.SubprocessError, OSError):` |
| Q-13 | performance_optimizer.py | 253 | `_disable_task` 中 `except:` 裸子句 | 中 | 改为 `except (subprocess.SubprocessError, OSError):` |
| Q-14 | performance_optimizer.py | 264 | `_stop_app` 中 `except:` 裸子句 | 中 | 改为 `except (subprocess.SubprocessError, OSError):` |
| Q-15 | iterative_scanner.py | 47 | `load_history` 中 `except:` 裸子句，吞没 JSON 解析错误和文件读取错误 | 中 | 改为 `except (json.JSONDecodeError, OSError):` 并记录日志 |
| Q-16 | iterative_scanner.py | 163 | `interactive_drill` 中 `except:` 裸子句，吞没 `input()` 异常 | 低 | 改为 `except (ValueError, IndexError):` |
| Q-17 | scanner_v3.py | 145 | `_scan_item` 中 `except:` 裸子句，吞没 `mtime` 获取失败 | 低 | 改为 `except OSError:` |
| Q-18 | scanner_v3.py | 209 | `_quick_dir_size` 内层 `except:` 裸子句 | 低 | 改为 `except OSError:` |
| Q-19 | scanner_v3.py | 211 | `_quick_dir_size` 外层 `except:` 裸子句 | 低 | 改为 `except OSError:` |
| Q-20 | scanner_v3.py | 362 | `interactive_cleanup` 中 `except:` 裸子句，吞没用户输入解析错误 | 低 | 改为 `except (ValueError, IndexError):` |

### 2.2 其他代码质量问题

| 编号 | 文件 | 行号 | 问题 | 严重性 | 修复建议 |
|------|------|------|------|--------|----------|
| Q-21 | performance_optimizer.py | 217-228 | `apply_optimization` 缺少 `else` 分支，未知 category 返回 `None` 而非 `False` | 中 | 添加 `else: return False` |
| Q-22 | memory_optimizer.py | 167-169 | `subprocess.run` 使用 `shell=True` 执行 PowerShell 命令，存在命令注入风险 | 中 | 使用列表参数避免 `shell=True`，或对输入做白名单校验 |
| Q-23 | iterative_scanner.py | 52-55 | `save_history` 无错误处理，文件写入失败会崩溃 | 中 | 包裹 `try/except OSError` |
| Q-24 | scanner_v3.py | 341 | `input()` 读取用户选择无超时保护，可阻塞 | 低 | 添加超时机制或 Ctrl+C 处理 |
| Q-25 | performance_optimizer.py | 228-229 | `apply_optimization` 失败时仅 `print` 错误，无日志记录 | 低 | 使用 `logging` 模块替代 `print` |
| Q-26 | memory_optimizer.py | 157 | 错误信息通过 `print` 输出，无日志级别控制 | 低 | 统一使用 `logging` 模块 |
| Q-27 | scanner_v3.py | 290-301 | `delete_item` 失败时仅增加 `self.errors` 计数，不记录具体错误信息 | 中 | 记录失败的路径和异常详情 |

---

## 3. 测试缺口

| 模块 | 缺少的测试 | 优先级 |
|------|-----------|--------|
| memory_optimizer.py | `MemoryOptimizer.analyze()` -- 进程枚举和分类 | 高 |
| memory_optimizer.py | `MemoryOptimizer._categorize()` -- 分类逻辑（边界情况：大小写、部分匹配） | 中 |
| memory_optimizer.py | `MemoryOptimizer.get_summary()` -- 分类汇总计算 | 中 |
| memory_optimizer.py | `MemoryOptimizer.get_memory_hogs()` -- 阈值过滤 | 低 |
| memory_optimizer.py | `MemoryOptimizer.clean_working_sets()` -- Windows API 调用 mock | 高 |
| memory_optimizer.py | `MemoryOptimizer.optimize_windows_settings()` -- 注册表操作 mock | 高 |
| memory_optimizer.py | `MemoryOptimizer.stop_unnecessary_services()` -- 服务停止 mock | 高 |
| memory_optimizer.py | `MemoryOptimizer.disable_startup_programs()` -- 注册表删除 mock | 高 |
| memory_optimizer.py | `MemoryOptimizer.generate_report()` -- 报告格式化 | 低 |
| performance_optimizer.py | `PerformanceOptimizer.analyze()` -- 整合分析流程 | 高 |
| performance_optimizer.py | `PerformanceOptimizer._analyze_startup()` -- 启动项解析 | 中 |
| performance_optimizer.py | `PerformanceOptimizer._analyze_services()` -- 服务解析 | 中 |
| performance_optimizer.py | `PerformanceOptimizer._analyze_tasks()` -- 计划任务解析 | 中 |
| performance_optimizer.py | `PerformanceOptimizer._analyze_apps()` -- 后台应用解析 | 中 |
| performance_optimizer.py | `PerformanceOptimizer.apply_optimization()` -- 分发逻辑和错误处理 | 高 |
| performance_optimizer.py | `_disable_startup` / `_stop_service` / `_disable_task` / `_stop_app` -- 命令执行 mock | 高 |
| performance_optimizer.py | `generate_report()` / `print_report()` -- 报告输出 | 低 |
| iterative_scanner.py | `IterativeScanner.load_history()` -- JSON 解析、文件不存在、格式错误 | 中 |
| iterative_scanner.py | `IterativeScanner.save_history()` -- 文件写入和目录创建 | 中 |
| iterative_scanner.py | `IterativeScanner.record_cleanup()` -- 历史记录追加 | 中 |
| iterative_scanner.py | `IterativeScanner.scan_with_learning()` -- 深度/大小递进逻辑 | 高 |
| iterative_scanner.py | `IterativeScanner._mark_deleted()` -- 历史标记递归 | 中 |
| iterative_scanner.py | `IterativeScanner.get_suggestions()` -- 建议生成逻辑 | 中 |
| scanner_v3.py | `DeepScanner.scan()` -- 路径不存在异常 | 中 |
| scanner_v3.py | `DeepScanner._scan_item()` -- 权限拒绝处理 | 中 |
| scanner_v3.py | `DeepScanner._scan_dir()` -- 深度限制和递归 | 高 |
| scanner_v3.py | `DeepScanner._quick_dir_size()` -- 大目录快速统计 | 中 |
| scanner_v3.py | `DeepScanner._categorize()` -- 模式匹配逻辑（所有三类模式 + 默认） | 高 |
| scanner_v3.py | `DeepScanner.collect_by_category()` -- 递归收集 | 中 |
| scanner_v3.py | `CleanupEngine.delete_item()` -- 删除成功/失败 | 高 |
| scanner_v3.py | `CleanupEngine.delete_safe_items()` -- 批量删除 | 高 |
| scanner_v3.py | `CleanupEngine.interactive_cleanup()` -- 用户交互流程 | 低 |

---

## 4. 建议的修复顺序

### P0 -- 立即修复（安全隐患）

1. **S-07/S-08** (scanner_v3.py): `delete_item` 和 `delete_safe_items` 应先移入回收站而非直接删除，批量删除前需用户确认
2. **S-09** (scanner_v3.py): 未知小文件不应默认分类为 SAFE，改为 UNKNOWN
3. **S-03** (memory_optimizer.py): `stop_unnecessary_services` 不应在无确认情况下停止 WSearch 等用户可能依赖的服务
4. **S-04** (memory_optimizer.py): `disable_startup_programs` 不应无确认删除注册表启动项
5. **S-02** (memory_optimizer.py): `optimize_windows_settings` 不应无确认修改系统注册表

### P1 -- 尽快修复（代码健壮性）

6. **S-01** (memory_optimizer.py): 降低 `OpenProcess` 权限至 `PROCESS_SET_QUOTA`
7. **S-10** (scanner_v3.py): 收窄 SAFE_PATTERNS，避免 `build`/`dist` 误匹配
8. **Q-01 到 Q-20**: 所有裸 `except:` 子句替换为具体异常类型（批量处理，可用搜索替换）
9. **Q-21** (performance_optimizer.py): `apply_optimization` 添加 `else` 分支
10. **Q-23** (iterative_scanner.py): `save_history` 添加错误处理

### P2 -- 计划修复（测试覆盖）

11. 为 `scanner_v3.py` 的 `DeepScanner._categorize()` 和 `CleanupEngine` 编写单元测试（高风险逻辑）
12. 为 `memory_optimizer.py` 的系统操作方法编写 mock 测试
13. 为 `iterative_scanner.py` 的历史记录读写和扫描递进逻辑编写测试
14. 为 `performance_optimizer.py` 的分析和优化方法编写 mock 测试

### P3 -- 持续改进（代码质量）

15. **Q-25/Q-26**: 统一使用 `logging` 模块替代 `print`
16. **Q-22**: 审查所有 `shell=True` 调用，改用列表参数
17. **Q-24**: 为交互式输入添加超时保护
18. **Q-27**: `delete_item` 记录详细错误信息

---

## 统计摘要

| 类别 | 数量 |
|------|------|
| 安全问题 | 10 |
| 裸 except 子句 | 20 |
| 其他代码质量问题 | 7 |
| 缺少测试的函数/方法 | 33 |
| **总计** | **70** |

**裸 except 子句分布**: memory_optimizer.py (6处), performance_optimizer.py (8处), iterative_scanner.py (2处), scanner_v3.py (4处)

**最高风险模块**: `memory_optimizer.py` 和 `scanner_v3.py` -- 包含最多破坏性操作且缺少用户确认机制。
