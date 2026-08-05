# Storage Analyzer - Windows 磁盘清理工具 | 免费开源 C盘清理

[![GitHub Stars](https://img.shields.io/github/stars/Dragon-01-you/storage-analyzer?style=flat-square&color=00E8FF)](https://github.com/Dragon-01-you/storage-analyzer/stargazers)
[![GitHub Downloads](https://img.shields.io/github/downloads/Dragon-01-you/storage-analyzer/total?style=flat-square&color=FF1AE5)](https://github.com/Dragon-01-you/storage-analyzer/releases)
[![License](https://img.shields.io/github/license/Dragon-01-you/storage-analyzer?style=flat-square&color=FFB400)](https://github.com/Dragon-01-you/storage-analyzer/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20|%20macOS%20|%20Linux-green?style=flat-square)]()

> **C盘满了怎么办？** 这个工具帮你找出哪些文件可以安全删除，释放磁盘空间。

## 为什么用 Storage Analyzer？

| 痛点 | 解决方案 |
|------|----------|
| C盘空间不足，不知道删什么 | 智能扫描，告诉你哪些可以安全删除 |
| 怕误删重要文件 | 5层安全保护，只删你确认的文件 |
| 不懂技术术语 | 通俗易懂的解释，告诉你每个文件是什么 |
| 手动清理太麻烦 | 一键扫描，自动识别垃圾文件 |

## 核心功能

### 🧹 96个内置清理器

覆盖主流应用，自动识别垃圾文件：

| 类型 | 应用 |
|------|------|
| 系统垃圾 | Windows 临时文件、崩溃转储、缩略图缓存、回收站 |
| 浏览器 | Chrome/Edge/Firefox/Opera/360/QQ 浏览器缓存 |
| 开发工具 | npm/pip/cargo/yarn/uv/go/ruby/java 缓存 |
| 聊天软件 | 微信/QQ/钉钉/Discord/Slack/Telegram 缓存 |
| 游戏平台 | Steam/Epic/GOG/EA/Ubisoft 着色器缓存 |
| 办公软件 | Microsoft Office/LibreOffice/Outlook 缓存 |
| 媒体工具 | VLC/Spotify/爱奇艺/腾讯视频/B站缓存 |

### 🛡️ 4层置信度系统

```
[SAFE]     可以放心删除（临时文件、缓存、日志）
[REVIEW]   需要你想一想（可能有重要数据）
[SUGGESTED] 建议检查一下（旧文件、备份）
[ASK]      只有你知道（用户数据、应用程序）
```

### 📊 相似文件检测

- 重复文件查找（3阶段：大小→部分哈希→完整哈希）
- 损坏文件检测
- 错误扩展名检测

### 📦 数据迁移

分析哪些数据可以从 C盘 迁移到 D盘，生成迁移脚本。

### 🎮 交互式界面

终端界面，可视化选择要清理的文件。

## 30秒上手

```bash
# 1. 下载项目
git clone https://github.com/Dragon-01-you/storage-analyzer.git
cd storage-analyzer

# 2. 扫描看看有什么垃圾（不删除，只报告）
python run.py --friendly

# 3. 真的要清理了（会先问你确认）
python run.py --deep --execute
```

## 完整命令

```bash
# 基本扫描
python run.py                    # 快速扫描
python run.py --deep             # 深度扫描（含系统垃圾）
python run.py --friendly         # 通俗易懂版（推荐新手）

# 高级功能
python run.py --confidence       # 4层置信度分析
python run.py --similar          # 重复文件检测
python run.py --corrupted        # 损坏文件检测
python run.py --piracy           # 盗版检测
python run.py --migrate          # 数据迁移分析
python run.py --tui              # 交互式界面
python run.py --plan             # 管理清理计划

# 执行清理
python run.py --deep --execute   # 清理安全项
python run.py --deep --json      # 输出 JSON（给程序用）
python run.py --deep --report    # 生成 HTML 报告
```

## 安全保障

**5层安全保护，确保不会误删：**

1. **默认不删任何东西** — 只扫描，不执行
2. **系统目录硬保护** — C:\Windows、/usr、/bin 永远不碰
3. **4层置信度** — SAFE/REVIEW/SUGGESTED/ASK 分级
4. **所有操作记日志** — 删了什么、什么时候删的，全有记录
5. **白名单** — 你说不删的东西，以后再也不问

## 性能

| 操作 | 时间 | 说明 |
|------|------|------|
| 首次扫描 | ~20秒 | Windows 10，~70万文件 |
| 缓存扫描 | ~0.3秒 | 用缓存就飞快 |
| 重复文件检测 | ~60秒 | 全盘扫描，比较慢 |

## 给 AI 助手用

这个项目包含一个 `SKILL.md` 文件。任何 AI 助手（Claude Code、Cursor、Continue 等）读完这个文件，就能自动帮你清理磁盘。

你只需要跟 AI 说："帮我看看 C盘有什么可以清理的"，它就知道怎么做了。

## 参考项目

本项目参考了以下顶尖项目：

| 项目 | Stars | 参考内容 |
|------|-------|----------|
| [Czkawka](https://github.com/qarmin/czkawka) | 32K | 相似文件检测 |
| [BleachBit](https://github.com/bleachbit/bleachbit) | 6.5K | 清理器覆盖 |
| [gdu](https://github.com/dundee/gdu) | 5.8K | 交互式界面 |
| [fclones](https://github.com/pkolaczk/fclones) | 2.8K | 并行处理 |
| [DiskPilot](https://github.com/tehgee42/DiskPilot) | 1 | 置信度系统 |

## 许可证

MIT — 随便用，随便改，随便分发。

---

**关键词：** Windows 磁盘清理, C盘清理, 垃圾文件清理, 磁盘空间不足, 重复文件删除, 系统清理工具, 免费清理软件, 开源清理工具
