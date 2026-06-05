# Storage Analyzer

> 你的电脑是不是越来越慢了？C 盘是不是快满了？别慌，这个工具帮你看看到底什么在占空间。

## 这玩意儿是干嘛的？

简单说：**扫描你的磁盘，告诉你哪些东西可以删，然后帮你安全地删掉。**

不会上来就乱删。默认只是看看，不会动任何文件。你说删哪个才删哪个。

```
✅ 30 多种垃圾文件，自动识别
✅ 默认只扫描不删除，你说删才删
✅ 认 Windows、Mac、Linux
✅ 零依赖，下载就能用
```

## 30 秒上手

```bash
# 扫描一下看看（不删除，只报告）
python run.py

# 深度扫描（包括系统垃圾）
python run.py --deep

# 找重复文件
python run.py --dupes

# 生成好看的 HTML 报告
python run.py --deep --report

# 真的要清理了（会先问你确认）
python run.py --deep --execute
```

## 它能清理什么？

| 类型 | 举几个例子 |
|------|-----------|
| 🗑️ 系统垃圾 | Windows 临时文件、崩溃转储、缩略图缓存、Windows.old |
| 🌐 浏览器 | Chrome/Edge/Firefox/Brave 的缓存（不是书签密码那些重要数据） |
| 💻 开发工具 | npm/pip/cargo/yarn 缓存、node_modules、Gradle 缓存 |
| 🖥️ IDE | VSCode/JetBrains 的缓存和日志 |
| 💬 聊天软件 | 微信/QQ/钉钉/Teams 的缓存文件 |
| ☁️ 云盘 | OneDrive 本地缓存 |
| 🎮 游戏 | Steam 着色器缓存（不是游戏本体） |
| 🖼️ GPU | NVIDIA/AMD/Intel 着色器缓存 |

**放心：游戏本体、聊天记录、重要文件不会被删。** 只清理缓存和临时文件。

## 安全吗？

**非常安全。** 5 层保护：

1. **默认不删任何东西** — 只扫描，不执行
2. **系统目录硬保护** — C:\Windows、/usr、/bin 这些地方永远不碰
3. **小文件进回收站** — 误删了还能恢复
4. **所有操作记日志** — 删了什么、什么时候删的，全有记录
5. **白名单** — 你说不删的东西，以后再也不问

## 命令大全

```bash
python run.py                    # 基本扫描
python run.py --deep             # 深度扫描（含系统垃圾）
python run.py --dupes            # 找重复文件
python run.py --full             # 深度扫描 + 找重复
python run.py --deep --report    # 生成 HTML 报告
python run.py --deep --execute   # 真正清理（会问你确认）
python run.py --deep --json      # 输出 JSON（给程序用）
python run.py --deep --json > result.json   # 保存到文件
python run.py --quiet            # 安静模式
python run.py --no-cache         # 跳过缓存，强制全量扫描
```

## 安装

**方式 1：下载就能用（推荐）**

下载 `storage-analyzer.pyz`，直接运行：
```bash
python storage-analyzer.pyz --deep
```

**方式 2：开发者模式**

```bash
git clone https://github.com/Dragon-01-you/storage-analyzer.git
cd storage-analyzer
pip install -e .
sa --deep
```

## 给 AI 助手用

这个项目包含一个 `SKILL.md` 文件。任何 AI 助手（Claude Code、Cursor、Continue 等）读完这个文件，就能自动帮你清理磁盘。

你只需要跟 AI 说："帮我看看 C 盘有什么可以清理的"，它就知道怎么做了。

## 配置文件

`config.json` 可以自定义：
- 扫描超时时间
- 最小文件大小（太小的不报告）
- 额外保护的路径
- 自定义分类规则

## 性能

| 操作 | 时间 | 说明 |
|------|------|------|
| 首次扫描 | ~20 秒 | Windows 10，~70 万文件 |
| 缓存扫描 | ~0.3 秒 | 用缓存就飞快 |
| 重复文件检测 | ~60 秒 | 全盘扫描，比较慢 |

## 开发者

想加新的清理规则？很简单：

1. 在 `cleaners/` 目录下创建一个 Python 文件
2. 写一个清理器类
3. 注册到 `cleaners/__init__.py`

详见 [`DEVELOPING.md`](DEVELOPING.md)

## 许可证

MIT — 随便用，随便改，随便分发。
