---
name: storage-analyzer
description: "磁盘存储分析与安全清理工具。当用户提到磁盘空间不足、C盘满了、清理缓存、找大文件、删除重复文件、释放空间、磁盘清理、存储分析时触发。跨平台（Windows/macOS/Linux），零外部依赖。"
version: 8.1.0
license: MIT
language: Python 3.10+
dependencies: pydantic>=2.0, psutil (optional)
platforms: [windows, macos, linux]
user-invocable: true
disable-model-invocation: false
context: fork
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, AskUserQuestion
argument-hint: "[path] [--deep] [--dupes] [--report] [--execute]"
---

# Storage Analyzer Skill

> **任何 AI 助手读完此文件，即可端到端驱动磁盘清理。**

## 这是什么

一个本地磁盘分析+安全清理工具。扫描磁盘→分类文件→用户确认→安全删除。

**核心原则：默认不删任何东西。必须用户确认。**

## 自动检测上下文

工作目录: !`pwd`
Python 版本: !`python --version 2>/dev/null || python3 --version 2>/dev/null || echo "Python not found"`
平台: !`uname -s 2>/dev/null || echo Windows`
Storage Analyzer 路径: !`for d in "$(dirname "$0")" "." "$HOME/.claude/skills/storage-analyzer"; do [ -f "$d/run.py" ] && echo "$d" && break; done 2>/dev/null || echo "NOT FOUND"`

---

## 快速入口

```bash
# 分析（不删除，只报告）
python run.py --deep --json

# 执行删除（需要用户确认）
python run.py --deep --execute

# 找重复文件
python run.py --dupes

# 生成 HTML 报告
python run.py --deep --report

# 保存 JSON 到文件（用 shell 重定向）
python run.py --deep --json > scan.json

# 静默模式（不输出日志）
python run.py --deep --json --quiet

# 跳过缓存（强制全量扫描）
python run.py --deep --json --no-cache
```

---

## AI 工作流程（必须按顺序执行）

```
Step 1: 扫描      → python run.py --deep --json > scan.json
Step 2: 展示      → 把 scan.json 中的 actions[] 展示给用户（用大白话，不用技术路径）
Step 3: 等待确认  → 用户逐项确认 approve / skip / whitelist
Step 4: 执行      → python run.py --execute（仅执行用户确认的项）
Step 5: 汇报      → 展示清理结果和释放空间
```

**异常分支：**
- 扫描失败（ok=false）→ 展示错误信息，建议检查路径或权限
- 用户跳过所有项 → 记录跳过，不执行删除，提示"下次再来看看"
- 用户全部确认 → 二次确认总大小后执行
- 用户部分确认 → 仅执行 approve 的项，跳过的项记录到下次扫描
- 删除部分失败 → 汇报成功/失败数量，展示审计日志位置
- JSON 解析失败 → 展示原始 stderr，建议重试或缩小扫描范围
- 用户说"帮我清理"（模糊指令）→ 先扫描，只自动 approve `risk=none` 的 SAFE 项，其他项仍需确认
- 用户说"只清理 XX" → 扫描后只展示匹配项，其他项自动 skip

---

### Step 1: 扫描

```bash
cd /path/to/storage-analyzer
python run.py --deep --json > scan.json
```

输出 JSON 结构（stdout）：

```json
{
  "ok": true,
  "elapsed": 19.5,
  "dry_run": true,
  "disks": {
    "C": {"t": 299000000000, "u": 215000000000, "f": 84000000000, "p": 72.8}
  },
  "safe_h": "28GB",
  "actions": [
    {"act": "delete", "what": "系统崩溃转储", "path": "C:\\Windows\\MEMORY.DMP", "sz": "15GB", "risk": "none", "cat": "system"},
    {"act": "review", "what": "Docker 桌面数据", "path": "C:\\...\\Docker", "sz": "8GB", "risk": "med", "cat": "dev"},
    {"act": "keep",   "what": "Steam 游戏", "path": "D:\\Steam", "sz": "120GB", "risk": "high", "cat": "game"}
  ],
  "dupes": [...],
  "warnings": [...]
}
```

**如果 ok=false**：读 stderr，展示错误，建议用户检查路径或权限，终止流程。

---

### Step 2: 展示给用户

**用大白话展示，不要展示技术路径。**

格式：
```
找到以下可清理项目（共 XX GB）：

✅ 可安全删除（XX GB）：
  1. Windows 临时文件 — 2.3GB
  2. Chrome 浏览器缓存 — 800MB
  3. npm 依赖缓存 — 1.2GB

⚠️ 建议确认（XX GB）：
  4. JetBrains IDE 缓存 — 3.5GB（重新索引即可恢复）
  5. node_modules — 2.1GB（npm install 即可恢复）

🔴 需要你决定（XX GB）：
  6. 微信聊天数据 — 15GB（含聊天记录）
  7. Docker 桌面数据 — 8GB（容器和镜像会丢失）
```

---

### Step 3: 等待用户确认

**绝对不要跳过这一步。** 用户可以选择：
- **approve** — 确认删除（可逐项或批量）
- **skip** — 跳过（跳过 3 次后建议加入白名单）
- **whitelist** — 永久不再提示
- **approve all safe** — 批量确认所有 `risk=none` 项，其他项逐项确认

**部分确认流程**：用户可以只 approve 部分项。跳过的项不会被执行，下次扫描会重新出现。建议在用户连续 skip 同一项 3 次后提示加入白名单。

🛑 **CHECKPOINT: 确认前**
- IF 总大小 > 10GB THEN 额外警告："将删除 XX GB 数据，此操作不可逆"
- IF 包含 HIGH 风险项（`risk: "high"`）THEN 用红色警告并等待确认
- IF 用户犹豫 THEN 提示可以先只清理 SAFE 项（`risk: "none"`）
- IF 用户长时间未响应 THEN 保持等待，不自动执行（宁可不删也不误删）

---

### Step 4: 执行删除

只有用户确认的项才会被删除。`--execute` 模式下，引擎会自动跳过未确认的项。

```bash
python run.py --execute
```

**用户决策传递机制**：
- 使用 Python API 时：通过 `Orchestrator.run(cfg, user_decision=lambda e: "approve"/"skip")` 回调函数传递
- 使用 CLI 时：`--execute` 模式下，引擎根据 risk 级别自动路由（SAFE 项自动删除，REVIEW/HIGH 项需二次确认）

🛑 **CHECKPOINT: 执行前**
- 展示将删除的项目列表和总大小
- 要求用户最终确认："确认删除这 X 项？(y/n)"
- IF 包含 REVIEW 项 THEN 逐项等待用户确认
- IF 用户拒绝 THEN 终止，不执行任何删除

---

### Step 5: 汇报结果

```
清理完成：
  ✅ 已清理 12 项，释放 28.5GB
  ⏭️ 跳过 3 项
  🔒 保护 2 项
  📋 审计日志: ~/.cache/storage-analyzer/audit.jsonl
```

🛑 **CHECKPOINT: 执行后**
- IF 有失败项 THEN 展示失败原因和失败路径
- 提示审计日志位置：`~/.cache/storage-analyzer/audit.jsonl`
- IF 磁盘使用率仍 > 90% THEN 建议重启后再检查

---

## Python API（用于深度集成）

```python
from v8 import AIBrain, FunnelScanner, Orchestrator, ScanConfig, DeletionMode, RiskLevel
from pathlib import Path

# 方式 1：用 Orchestrator（推荐，全流程编排）
orch = Orchestrator()
cfg = ScanConfig(
    target_paths=[Path("C:\\"), Path("D:\\"), Path("E:\\")],
    deletion_mode=DeletionMode.DRY_RUN,  # 默认 dry-run
    min_size_mb=50,
)
result = orch.run(
    cfg,
    user_decision=lambda e: "approve" if e.risk_level == RiskLevel.NONE else "skip",
    use_cache=True,        # 使用增量缓存
    record_history=True,   # 记录历史快照
)
print(result.summary())

# 方式 2：分步控制
brain = AIBrain()
intent = brain.parse_intent("清理C盘，保留原神")  # 返回 ScanConfig
scanner = FunnelScanner(intent)
summaries = scanner.scan()
entries = brain.label_all(summaries)

for entry in entries:
    print(entry.user_facing_prompt)  # 用户看到的文字
    print(f"  风险: {entry.risk_level}")
    print(f"  路径: {entry.label.technical_path}")  # 仅日志用

# 方式 3：带错误处理
try:
    brain = AIBrain()
    cfg = brain.parse_intent("清理C盘")
    scanner = FunnelScanner(cfg)
    summaries = scanner.scan()
except FileNotFoundError as e:
    print(f"路径不存在: {e}")
except PermissionError as e:
    print(f"权限不足，请以管理员身份运行: {e}")
except Exception as e:
    print(f"扫描失败: {e}")
```

---

## CLI 完整参考

```text
python run.py [options]

Options:
  --execute         Actually delete files (default: dry-run)
  --quiet           Suppress stderr logs
  --deep            Include system scan
  --dupes           Find duplicate files (>= 50MB)
  --full            --deep + --dupes
  --include-vm      Surface VMware / VM items in the deep scan
  --legacy-scanner  Use the legacy hand-coded scan_sys() instead of the plugin pipeline
  --no-cache        Skip incremental cache
  --json            Print JSON to stdout (default)
  --report          Generate HTML report + open in browser
```

**注意：没有 `-o` 参数。** 保存到文件请用 shell 重定向：`python run.py --deep --json > scan.json`

---

## 安全机制（5 层防线）

### 第 1 层：Dry-run 默认

- 默认只分析，不删除
- 必须显式传 `--execute` 才会真正删除
- ScanConfig 默认 `deletion_mode=DRY_RUN`

### 第 2 层：ProtectedPaths（硬编码，不可绕过）

以下路径**无论任何配置/AI/用户输入都不能删除**：

| 平台 | 受保护路径 |
|------|-----------|
| Windows | C:\Windows, C:\Windows\System32, C:\Program Files, C:\Program Files (x86), C:\Boot, C:\EFI |
| macOS | /System, /Applications, /usr, /bin, /sbin |
| Linux | /, /bin, /sbin, /etc, /boot, /lib, /lib64, /usr, /var |

**检查方式**：`os.path.realpath()` 解析符号链接 + 大小写归一化（Windows）

### 第 3 层：三级删除路由

| 条件 | 路由 | 说明 |
|------|------|------|
| 文件 < 100MB | 回收站 | 可恢复 |
| 文件 ≥ 100MB | 隔离区 | 30 天后自动清理 |
| HIGH 风险 | WIPE | 需要 `DeletionMode.HARD` + 显式同意 + 审计日志。`SOFT` 模式下拒绝执行 |

### 第 4 层：审计日志链

- 位置：`~/.cache/storage-analyzer/audit.jsonl`
- 格式：每行一个 JSON，含 SHA-256 链式哈希
- 可验证完整性：`audit.verify_chain()` 返回断裂点

### 第 5 层：白名单健康检查

- 白名单规则每 30 天自动提醒重新审视
- 超过 5GB 或膨胀 2 倍的白名单项会触发警告
- 跳过 3 次的项目会建议加入白名单（而非反复打扰）

---

## 认知标签系统（3 层）

AI Brain 用三层机制给每个目录打标签：

| 层级 | 方法 | 准确率 | 示例 |
|------|------|--------|------|
| Level 1 指纹 | 路径/后缀精确匹配 | 95% | `\npm-cache` → "npm 依赖缓存" |
| Level 2 AI | LLM 推理（可选） | 60-80% | feature_files 分析 |
| Level 3 兜底 | 大小+路径启发式 | 30% | "未知的大型应用数据" |

**关键规则**：
- 用户看到的永远是中文标签，不是技术路径
- 未识别的项目默认标记为 REVIEW，不标记为可删除
- 技术路径（technical_path）仅用于审计日志

---

## 指纹规则覆盖（58 条）

### 安全删除（RiskLevel.NONE）
npm-cache, pip-cache, cargo-registry, gradle-caches, maven-repo, nuget-packages, playwright, yarn-cache, pnpm-store, bun-cache, uv-cache, __pycache__, .next, Chrome/Edge/Brave Cache, CrashDumps, Windows Temp, WER Report, Discord Cache, Slack Cache, Steam shader/html cache, OneDrive Cache

### 需要确认（RiskLevel.LOW/MEDIUM）
JetBrains/VS/Android Studio 缓存, node_modules, Rust 构建产物, Windows 更新缓存, setup.exe/ISO/DMG 安装包

### 必须询问用户（RiskLevel.HIGH）
Firefox 浏览器数据, Chrome/Edge 用户数据, 微信/QQ/Telegram 聊天数据, VMware 虚拟机, WSL 磁盘, Docker 数据, Steam/Epic 游戏, OneDrive 同步数据

完整规则定义：`v8/ai_brain.py` 的 `_FINGERPRINTS` 列表（58 条）

---

## 失败模式与回退

| 场景 | 症状 | 第一修复 | 仍失败则 |
|------|------|----------|----------|
| 路径不存在 | OSError / FileNotFoundError | 跳过该路径，记录警告 | 提示用户检查路径拼写 |
| 权限不足 | PermissionError | 跳过，提示用管理员权限 | 提示关闭占用进程后重试 |
| 文件被锁定 | WinError 32 | 记录为"被占用" | 建议重启后重试 |
| 磁盘已满 | 无法写入审计日志 | 输出到 stderr | 不中断流程，继续清理 |
| Pydantic 版本不兼容 | ImportError / ValidationError | `pip install pydantic>=2.0` | 提示升级 Python 到 3.10+ |
| psutil 未安装 | ImportError（仅 memory_optimizer） | 跳过内存优化功能 | 安装：`pip install psutil` |
| 扫描超时 | 默认 30 秒 | 调整 config.json 的 scan.timeout | 缩小扫描范围（减少 --depth） |
| DISM 失败 | WinSxS 清理报错 | 跳过 | 提示手动运行 DISM /StartComponentCleanup |
| JSON 输出异常 | ok=false 或格式错误 | 展示原始 stderr | 建议重试或报告 issue |
| 并发扫描冲突 | SQLite 锁定 | 等待 2 秒后重试，最多 3 次 | 提示关闭其他扫描实例 |
| 非 Windows 平台 | macOS/Linux 功能受限 | 跳过 Windows 专用清理器 | 仅执行跨平台清理器（browsers/dev） |

---

## 反模式（不要做的事）

| # | 错误做法 | 正确做法 |
|---|----------|----------|
| 1 | 直接执行 --execute | 先扫描 → 展示 → 确认 → 再执行 |
| 2 | 展示技术路径 | 用中文标签（"Windows 临时文件"） |
| 3 | safe_cleanup.delete_approved_items | SafeDeleter().delete_entry() |
| 4 | dry-run 说"已清理" | 说"发现可清理 XX GB" |
| 5 | 直接改注册表 | 传 dry_run=True |
| 6 | taskkill /f 强杀 | 提示用户手动关闭 |
| 7 | safety_guard 字符串匹配 | ProtectedPaths.is_protected() |
| 8 | 包含小文件噪音 | 设置 min_size_mb 过滤 |

### ❌ 反模式 1：跳过用户确认
```
❌ 错误：直接执行 python run.py --execute
✅ 正确：
  1. 先扫描：python run.py --deep --json > scan.json
  2. 展示结果给用户
  3. 等待用户逐项确认
  4. 再执行：python run.py --execute
```

### ❌ 反模式 2：展示技术路径
```
❌ 错误："删除 C:\Users\user\AppData\Local\Temp 吗？"
✅ 正确："删除 Windows 临时文件（2.3GB）？"
```

### ❌ 反模式 3：绕过安全层
```
❌ 错误：safe_cleanup.delete_approved_items(items)
   → 为什么错：绕过 ProtectedPaths 检查，可能删除系统文件
✅ 正确：from v8.safeguard import SafeDeleter
         deleter = SafeDeleter()
         deleter.delete_entry(entry, DeletionMode.DRY_RUN)
   → 为什么对：SafeDeleter 内置 ProtectedPaths 检查 + 审计日志
```

### ❌ 反模式 4：误报清理完成
```
❌ 错误：在 dry-run 模式下说"已清理 28GB"
✅ 正确："扫描完成，发现可清理 28GB。执行 --execute 才会真正删除。"
```

### ❌ 反模式 5：直接改注册表
```
❌ 错误：MemoryOptimizer.optimize_windows_settings()
   → 为什么错：注册表修改无法回滚，可能导致系统不稳定
✅ 正确：传 dry_run=True，让用户确认后再执行
```

### ❌ 反模式 6：强杀进程
```
❌ 错误：PerformanceOptimizer._stop_app("chrome.exe")
   → 为什么错：taskkill /f 会丢失未保存数据，可能导致数据损坏
✅ 正确：提示用户手动关闭应用
```

### ❌ 反模式 7：信任字符串匹配
```
❌ 错误：safety_guard.is_protected(path)
   → 为什么错：字符串匹配不解析符号链接，攻击者可通过 symlink 绕过保护
✅ 正确：from v8.safeguard import ProtectedPaths
         ProtectedPaths().is_protected(path)
   → 为什么对：os.path.realpath() 解析符号链接 + 大小写归一化
```

### ❌ 反模式 8：包含小文件噪音
```
❌ 错误：扫描结果包含 < min_size_mb 的文件
✅ 正确：设置 min_size_mb 过滤小文件
```

---

## 已知技术债

| 编号 | 问题 | 影响 | 状态 |
|------|------|------|------|
| T1 | `safe_cleanup.py` 绕过 v8 安全层 | 可能误删受保护文件 | ✅ 已修复，接入 SafeDeleter |
| T2 | `safety_guard.py` 与 `safeguard.py` 职责重叠 | 维护成本高 | ⚠️ 待合并（风险已降低，safe_cleanup.py 已接入 SafeDeleter） |
| T3 | `memory_optimizer.py` 直接改注册表 | 无法回滚 | ✅ 已加 dry_run |
| T4 | `_human_bytes` 函数重复 4 次 | 维护成本 | ⚠️ 待提取（types.py + evolution.py + audit.py + orchestrator.py） |
| T5 | 裸 `except:` 吞错误 | 隐藏 bug | ✅ 已全部替换为具体异常类型 |
| T6 | 缺少删除逻辑测试 | 回归风险 | ✅ 已补删除逻辑测试 |
| T7 | CleanupReporter 百分比计算用近似值 | 报告不准 | ✅ 已修复，支持 total_bytes 参数 |

---

## 跨平台支持

| 平台 | 状态 | 退化策略 |
|------|------|----------|
| Windows 10/11 | ✅ 完整 | 所有功能可用 |
| macOS | ⚠️ 部分 | 跳过 Windows 专用清理器（WinSxS/CBS/Prefetch），仅执行浏览器+开发工具清理 |
| Linux | ⚠️ 部分 | 跳过 Windows 专用清理器，仅执行浏览器+开发工具清理 |

**AI 遇到非 Windows 平台时**：先运行扫描（`python run.py --deep --json`），如果 actions 为空或只有少量项，提示用户"当前平台功能有限，仅支持浏览器缓存和开发工具清理"。

---

## 配置文件（config.json）

```json
{
  "scan": {
    "timeout": 30,
    "max_depth": 4,
    "min_kb": 51200,
    "workers": 6
  },
  "protected_paths": [
    "C:\\Windows",
    "C:\\Windows\\System32",
    "C:\\Program Files",
    "C:\\Program Files (x86)",
    "/bin", "/sbin", "/etc", "/usr", "/System", "/Applications", "/lib", "/lib64", "/boot"
  ],
  "classify": {
    "green": [{"pat": "(?i)\\\\Temp\\\\?", "reason": "Windows temp", "conf": "hi"}],
    "red":   [{"pat": "(?i)\\\\Windows\\\\", "reason": "System files", "conf": "hi"}],
    "known_apps": {"docker": ["yellow", "Docker data"]}
  }
}
```

---

## 测试

```bash
# 运行 v8 测试套件（75 个用例，73-74 通过，1-2 跳过取决于权限）
python -m pytest tests/test_v8.py -v

# 运行全部测试
python -m pytest tests/ -v
```

测试输出示例（实际运行结果）：
```
tests/test_v8.py::test_scan_config_creation PASSED
tests/test_v8.py::test_human_bytes PASSED
tests/test_v8.py::test_protected_paths_blocks_system_dirs PASSED
tests/test_v8.py::test_protected_posix SKIPPED (Windows 不适用)
tests/test_v8.py::test_safe_deleter_recycle_small_file PASSED
tests/test_v8.py::test_safe_deleter_quarantine_large_file PASSED
tests/test_v8.py::test_safe_deleter_wipe_requires_hard_mode PASSED
tests/test_v8.py::test_protected_paths_symlink_resolution SKIPPED (需管理员权限)
...
=================== 73 passed, 2 skipped in 1.05s ===================
```

测试覆盖：types, ai_brain, safeguard, evolution, platform_paths, scan_cache, audit, duplicates, history, orchestrator, scanner_v3, cleanup_engine, memory_optimizer, performance_optimizer, iterative_scanner

**跳过的测试**：POSIX 路径测试（Windows 不适用）、符号链接测试（需管理员权限）

**未覆盖**：DISM 集成、回收站 SHFileOperation（需 Windows API mock）

---

## 数据流

```
run.py
  └→ engine.main.run()
       ├→ Orchestrator.run(cfg, user_decision)
       │    ├→ AIBrain.parse_intent(query) → ScanConfig
       │    ├→ FunnelScanner(cfg).scan() → summaries
       │    ├→ cleaners/ (plugin pipeline) → CleanEntry[]
       │    ├→ AIBrain.label_all(entries) → cognitive labels
       │    ├→ ProtectedPaths.is_protected() → hard block check
       │    ├→ user_decision(entry) → approve/skip/whitelist
       │    ├→ SafeDeleter.delete_entry(entry, mode) → actual delete
       │    ├→ AuditLogger.log(entry, result) → audit.jsonl
       │    └→ HistoryStore.record(snapshot) → trend tracking
       └→ CleanupReporter.generate(result) → HTML/text report
```

---

## 文件结构

```
storage-analyzer/
├── v8/                          # 核心模块（19 个文件）
│   ├── __init__.py              # 模块导出
│   ├── types.py                 # Pydantic v2 数据契约
│   ├── ai_brain.py              # AI 意图解析 + 3 层认知标签（58 条指纹规则）
│   ├── engine_core.py           # 漏斗扫描器 + 插件注册
│   ├── evolution.py             # 防呆提案 + 白名单健康检查
│   ├── safeguard.py             # 安全删除（ProtectedPaths + SafeDeleter）
│   ├── orchestrator.py          # 全模块编排
│   ├── platform_paths.py        # 跨平台路径解析
│   ├── scan_cache.py            # SQLite 增量缓存
│   ├── audit.py                 # JSON Lines 审计日志链（SHA-256）
│   ├── duplicates.py            # 3 阶段重复检测（size→hash→content）
│   ├── history.py               # 历史趋势 + 线性回归预测
│   ├── scanner_v3.py            # 深度扫描（插件管线）
│   ├── iterative_scanner.py     # 迭代扫描
│   ├── memory_optimizer.py      # 内存优化（dry_run 默认，logging）
│   ├── performance_optimizer.py # 性能优化（dry_run 默认，logging）
│   ├── safety_guard.py          # 安全机制（与 safeguard.py 重叠，待合并）
│   ├── safe_cleanup.py          # 安全清理（已接入 SafeDeleter）
│   ├── cleanup_reporter.py      # 清理报告生成
│   └── ISSUES.md                # 模块级问题追踪
├── engine/                      # 旧版引擎（run.py 实际导入）
│   ├── __init__.py              # 包初始化
│   ├── main.py                  # CLI 入口（run.py 调用）
│   ├── scanner.py               # 扫描器
│   ├── scanner_v2.py            # v2 扫描器
│   ├── deleter.py               # 删除器
│   ├── forecaster.py            # 预测器
│   ├── utils.py                 # 工具函数
│   └── classify/                # 分类子系统
├── cleaners/                    # 插件清理器（10 个模块）
│   ├── __init__.py              # 清理器注册表
│   ├── _base.py                 # 基类
│   ├── _system.py               # 系统清理器（Temp/CBS/WinSxS/Prefetch）
│   ├── _browsers.py             # 浏览器清理器（Chrome/Edge/Firefox/Brave）
│   ├── _dev.py                  # 开发工具清理器（npm/pip/cargo/gradle）
│   ├── _ide.py                  # IDE 清理器（VSCode/JetBrains）
│   ├── _cloud_chat.py           # 云+聊天清理器（OneDrive/Teams/WeChat）
│   ├── _extras.py               # 附加清理器
│   ├── _vmware.py               # VMware 清理器（advisory）
│   └── _legacy_adapter.py       # 旧版适配器
├── scripts/                     # 工具脚本（20+）
│   ├── build_report.py          # 报告生成
│   ├── compare.py               # 扫描器对比
│   ├── server.py                # HTTP 服务器
│   ├── build_zipapp.py          # .pyz 打包
│   ├── snapshot.py              # 快照工具
│   └── test.py                  # 旧版测试
├── tests/
│   ├── test_v8.py               # v8 测试套件（75 个用例）
│   └── test_cleaners.py         # 清理器测试
├── dist/                        # 分发包
│   ├── storage-analyzer-v8.1.0.pyz
│   ├── storage-analyzer-v8.1.0.zip
│   └── storage_analyzer-8.1.0-py3-none-any.whl
├── assets/                      # HTML 报告模板
├── config.json                  # 规则 + 受保护路径
├── __main__.py                  # python -m storage-analyzer 入口
├── run.py                       # CLI 入口（调用 engine.main.run）
├── pyproject.toml               # PEP 517 构建配置
├── SKILL.md                     # 本文件（AI Agent 可执行手册）
├── README.md                    # 项目说明
├── DEVELOPING.md                # 开发者指南
├── ARCHITECTURE.md              # 架构设计文档
├── install.py                   # 一键安装脚本
└── storage-analyzer.pyz         # 单文件分发包
```

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 8.1.0 | 2026-06-04 | 当前版本：Pydantic v2 契约，58 条指纹规则，审计链，安全层统一 |
| 7.1 | — | 插件管线，默认启用 |
| 6 | — | 修复 --execute 非功能性 bug |
| 5 | — | 初始版本 |

---

*本文件遵循 [Anthropic Skill Spec](https://docs.anthropic.com/claude-code/skills) 规范，兼容 Claude Code、Cursor Rules、Continue Config、OpenSquilla、OpenAI Codex Instructions 等所有支持 SKILL.md 的 AI Agent 平台。*
