---
name: storage-analyzer
description: 工业级磁盘存储分析与安全清理工具，跨平台（Windows/macOS/Linux），零外部依赖
version: 8.1.0
license: MIT
language: Python 3.10+
dependencies: pydantic>=2.0, psutil (optional)
platforms: [windows, macos, linux]
---

# Storage Analyzer Skill

> **任何 AI 助手读完此文件，即可端到端驱动磁盘清理。**

## 这是什么

一个本地磁盘分析+安全清理工具。扫描磁盘→分类文件→用户确认→安全删除。

**核心原则：默认不删任何东西。必须用户确认。**

---

## 快速入口

```bash
# 分析（不删除，只报告）
python run.py --deep --json -o scan.json

# 执行删除（需要用户确认）
python run.py --deep --execute

# 找重复文件
python run.py --dupes

# 生成 HTML 报告
python run.py --deep --report
```

---

## AI 工作流程（必须按顺序执行）

```
Step 1: 扫描      → python run.py --deep --json -o scan.json
Step 2: 展示      → 把 scan.json 中的 actions[] 展示给用户
Step 3: 等待确认  → 用户逐项确认 approve / skip / whitelist
Step 4: 执行      → python run.py --execute（仅执行用户确认的项）
Step 5: 汇报      → 展示清理结果和释放空间
```

**异常分支：**
- 扫描失败（ok=false）→ 展示错误信息，建议检查路径或权限
- 用户跳过所有项 → 记录跳过，不执行删除，提示"下次再来看看"
- 用户全部确认 → 二次确认总大小后执行
- 删除部分失败 → 汇报成功/失败数量，展示审计日志位置

### Step 1: 扫描

```bash
cd /path/to/storage-analyzer
python run.py --deep --json -o scan.json
```

输出 JSON 结构：

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

### Step 3: 等待用户确认

**绝对不要跳过这一步。** 用户可以选择：
- **approve** — 确认删除
- **skip** — 跳过（跳过 3 次后建议加入白名单）
- **whitelist** — 永久不再提示

### Step 4: 执行删除

只有用户确认的项才会被删除。

```bash
python run.py --execute -o actions.json
```

### Step 5: 汇报结果

```
清理完成：
  ✅ 已清理 12 项，释放 28.5GB
  ⏭️ 跳过 3 项
  🔒 保护 2 项
```

---

## Python API（用于深度集成）

```python
from v8 import AIBrain, FunnelScanner, Orchestrator, ScanConfig
from pathlib import Path

# 方式 1：用 Orchestrator（推荐，全流程编排）
orch = Orchestrator()
cfg = ScanConfig(
    target_paths=[Path("C:\\"), Path("D:\\"), Path("E:\\")],
    deletion_mode=DeletionMode.DRY_RUN,  # 默认 dry-run
    min_size_mb=50,
)
result = orch.run(cfg, user_decision=lambda e: "approve" if e.risk_level == RiskLevel.NONE else "skip")
print(result.summary())

# 方式 2：分步控制
brain = AIBrain()
cfg = brain.parse_intent("清理C盘，保留原神")
scanner = FunnelScanner(cfg)
summaries = scanner.scan()
entries = brain.label_all(summaries)

for entry in entries:
    print(entry.user_facing_prompt)  # 用户看到的文字
    print(f"  风险: {entry.risk_level}")
    print(f"  路径: {entry.label.technical_path}")  # 仅日志用

# 方式 3：带错误处理
try:
    cfg = brain.parse_intent("清理C盘")
    summaries = scanner.scan()
except FileNotFoundError as e:
    print(f"路径不存在: {e}")
except PermissionError as e:
    print(f"权限不足，请以管理员身份运行: {e}")
except Exception as e:
    print(f"扫描失败: {e}")
```

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
| Linux | /, /bin, /sbin, /etc, /boot, /lib, /usr, /var |

**检查方式**：`os.path.realpath()` 解析符号链接 + 大小写归一化（Windows）

### 第 3 层：三级删除路由

| 条件 | 路由 | 说明 |
|------|------|------|
| 文件 < 100MB | 回收站 | 可恢复 |
| 文件 ≥ 100MB | 隔离区 | 30 天后自动清理 |
| HIGH 风险 | 彻底删除 | 需要显式同意 + 审计日志 |

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

## 指纹规则覆盖（40+ 条）

### 安全删除（RiskLevel.NONE）
npm-cache, pip-cache, cargo-registry, gradle-caches, maven-repo, nuget-packages, playwright, yarn-cache, pnpm-store, bun-cache, uv-cache, __pycache__, .next, Chrome/Edge/Brave Cache, CrashDumps, Windows Temp, WER Report, Discord Cache, Slack Cache, Steam shader/html cache, OneDrive Cache

### 需要确认（RiskLevel.LOW/MEDIUM）
JetBrains/VS/Android Studio 缓存, node_modules, Rust 构建产物, Windows 更新缓存, setup.exe/ISO/DMG 安装包

### 必须询问用户（RiskLevel.HIGH）
Firefox 浏览器数据, Chrome/Edge 用户数据, 微信/QQ/Telegram 聊天数据, VMware 虚拟机, WSL 磁盘, Docker 数据, Steam/Epic 游戏, OneDrive 同步数据

---

## 失败模式与回退

| 场景 | 症状 | 回退方案 |
|------|------|----------|
| 路径不存在 | OSError / FileNotFoundError | 跳过该路径，记录警告 |
| 权限不足 | PermissionError | 跳过，提示用户用管理员权限重试 |
| 文件被锁定 | WinError 32 | 记录为"被占用"，建议重启后重试 |
| 磁盘已满 | 无法写入审计日志 | 输出到 stderr，不中断流程 |
| Pydantic 版本不兼容 | ImportError / ValidationError | 提示 `pip install pydantic>=2.0` |
| psutil 未安装 | ImportError（仅 memory_optimizer） | 跳过内存优化功能 |
| 扫描超时 | 默认 30 秒 | 调整 config.json 的 scan.timeout |
| DISM 失败 | WinSxS 清理报错 | 跳过，提示手动运行 DISM |
| JSON 输出异常 | ok=false 或格式错误 | 展示原始 stderr，建议重试 |
| 并发扫描冲突 | SQLite 锁定 | 等待 2 秒后重试，最多 3 次 |

---

## 检查点（STOP 标记）

### 🛑 CHECKPOINT 1: 扫描前确认
- 确认用户知道要扫描哪个磁盘
- 如果用户说"清理C盘"，确认 C:\ 是目标
- 如果磁盘使用率 < 50%，提示"磁盘空间充足，是否继续？"

### 🛑 CHECKPOINT 2: 删除前确认
- 展示将删除的项目列表和总大小
- 如果总大小 > 10GB，额外警告
- 如果包含 REVIEW 项，逐项等待用户确认
- 如果包含 HIGH 风险项，用红色警告并等待确认

### 🛑 CHECKPOINT 3: 执行后汇报
- 展示实际释放空间
- 展示失败项（如果有）
- 提示审计日志位置

---

## 反模式（不要做的事）

1. **不要跳过用户确认直接删除** — 即使是 "安全删除" 项，也要展示给用户
2. **不要向用户展示技术路径** — 用 `human_readable_label`，不用 `technical_path`
3. **不要用 `SafeCleanup.delete_approved_items()`** — 它绕过 v8 安全层，用 `SafeDeleter.delete_entry()` 代替
4. **不要在没有 `--execute` 的情况下告诉用户"已清理"** — 默认是 dry-run
5. **不要调用 `MemoryOptimizer.optimize_windows_settings()`** — 它直接改注册表
6. **不要调用 `PerformanceOptimizer._stop_app()`** — `taskkill /f` 会强杀进程
7. **不要信任 `safety_guard.py` 的字符串匹配** — 用 `safeguard.py` 的 `ProtectedPaths` 代替
8. **不要在扫描结果中包含 < min_size_mb 的文件** — 会产生噪音

---

## 已知技术债

| 编号 | 问题 | 影响 | 状态 |
|------|------|------|------|
| T1 | `safe_cleanup.py` 绕过 v8 安全层 | 可能误删受保护文件 | ✅ 已修复 |
| T2 | `safety_guard.py` 与 `safeguard.py` 职责重叠 | 维护成本高 | ⚠️ 待合并 |
| T3 | `memory_optimizer.py` 直接改注册表 | 无法回滚 | ✅ 已加 dry_run |
| T4 | `_human_bytes` 函数重复 4 次 | 维护成本 | ⚠️ 待提取 |
| T5 | 裸 `except:` 吞错误 | 隐藏 bug | ✅ 已全部替换 |
| T6 | 缺少删除逻辑测试 | 回归风险 | ✅ 已补 29 个测试 |
| T7 | CleanupReporter 百分比计算用近似值 | 报告不准 | ✅ 已修复 |

---

## 配置文件（config.json）

```json
{
  "scan": {
    "timeout": 30,        // 扫描超时（秒）
    "max_depth": 4,       // 最大递归深度
    "min_kb": 51200,      // 最小文件大小（KB），低于此值忽略
    "workers": 6          // 预留的并发数（当前未使用）
  },
  "protected_paths": [    // 额外保护路径（除了硬编码的）
    "C:\\Windows",
    "C:\\Program Files",
    "/bin", "/etc", "/usr"
  ],
  "classify": {
    "green": [...],       // 可安全删除的路径模式（正则）
    "red": [...],         // 绝对不能删除的路径模式
    "known_apps": {...}   // 已知应用分类
  }
}
```

---

## 跨平台支持

| 平台 | 状态 | 说明 |
|------|------|------|
| Windows 10/11 | ✅ 完整 | 主要目标平台，所有功能可用 |
| macOS | ⚠️ 部分 | PlatformPaths 已定义，未充分测试 |
| Linux | ⚠️ 部分 | 基本路径已定义，未充分测试 |

---

## 测试

```bash
# 运行 v8 测试套件（75 个用例，73 通过，2 跳过）
python -m pytest tests/test_v8.py -v

# 运行全部测试
python -m pytest tests/ -v
```

测试覆盖：types, ai_brain, safeguard, evolution, platform_paths, scan_cache, audit, duplicates, history, orchestrator, scanner_v3, cleanup_engine, memory_optimizer, performance_optimizer, iterative_scanner

**跳过的 2 个测试**：POSIX 路径测试（Windows 不适用）、符号链接测试（需管理员权限）

**未覆盖**：DISM 集成、回收站 SHFileOperation（需 Windows API mock）

---

## 文件结构

```
storage-analyzer/
├── v8/                          # 核心模块（18 个文件）
│   ├── __init__.py              # 模块导出
│   ├── types.py                 # Pydantic v2 数据契约
│   ├── ai_brain.py              # AI 意图解析 + 3 层认知标签
│   ├── engine_core.py           # 漏斗扫描器 + 插件注册
│   ├── evolution.py             # 防呆提案 + 白名单健康检查
│   ├── safeguard.py             # 安全删除（5 层防线的核心）
│   ├── orchestrator.py          # 全模块编排
│   ├── platform_paths.py        # 跨平台路径解析
│   ├── scan_cache.py            # SQLite 增量缓存
│   ├── audit.py                 # JSON Lines 审计日志链
│   ├── duplicates.py            # 3 阶段重复检测
│   ├── history.py               # 历史趋势 + 线性回归预测
│   ├── scanner_v3.py            # 深度扫描
│   ├── iterative_scanner.py     # 迭代扫描
│   ├── memory_optimizer.py      # 内存优化（dry_run 默认，logging）
│   ├── performance_optimizer.py # 性能优化（dry_run 默认，logging）
│   ├── safety_guard.py          # 安全机制（与 safeguard.py 重叠）
│   ├── safe_cleanup.py          # 安全清理（已接入 SafeDeleter）
│   └── cleanup_reporter.py      # 清理报告生成
├── tests/
│   └── test_v8.py               # 75 个测试用例
├── config.json                  # 规则 + 受保护路径
├── run.py                       # CLI 入口
├── SKILL.md                     # 本文件（AI Agent 可执行手册）
├── README.md                    # 项目说明
├── ARCHITECTURE.md              # 架构设计文档
└── storage-analyzer.pyz         # 单文件分发包
```

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 8.1.0 | 2026-06-04 | 当前版本：Pydantic v2 契约，40+ 指纹规则，审计链 |
| 7.1 | — | 插件管线，默认启用 |
| 6 | — | 修复 --execute 非功能性 bug |
| 5 | — | 初始版本 |

---

*本文件遵循 [Anthropic Skill Spec](https://docs.anthropic.com/claude-code/skills) 规范，同时兼容 Cursor Rules、Continue Config、OpenAI Codex Instructions。*
