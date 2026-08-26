# 08-AI工程化与Agent ⭐

基于 **LangChain 1.0+** 的 OJ（Online Judge）自动解题 Agent，输入题号即可自动爬取题目并给出**解题思路 + Python 参考代码 + 复杂度分析**。集成爬虫工具封装、超级鹰验证码识别、Tkinter 图形界面与线程安全设计。

## ⭐ 核心文件：OJ_AC助手_GUI.py

### 工作流程

```
用户输入题号 (如 2098)
        │
        ▼
┌───────────────────────────────────┐
│  LangChain Agent (create_agent)   │
│  模型: 智谱 GLM-4-Flash           │
│  系统: ACM 算法解题助手            │
└───────────────┬───────────────────┘
                │ 自主决策调用工具
        ┌───────┴───────┐
        ▼               ▼
┌──────────────┐ ┌──────────────────┐
│ get_problem  │ │ solve_captcha    │
│ _by_id 工具  │ │ 超级鹰验证码识别 │
│ (爬虫)       │ │ (应对反爬)        │
└──────┬───────┘ └──────────────────┘
       │ SessionPage 纯 HTTP 爬取
       ▼
  OJ 题目详情 (标题/描述/输入/输出)
       │
       ▼ 回传给 Agent
┌───────────────────────────────────┐
│  LLM 推理生成回答                  │
│  1. 解题思路  2. 参考代码  3. 复杂度│
└───────────────────────────────────┘
```

### Agent 工具封装

Agent 自主决策调用两个 `@tool` 装饰的工具函数：

| 工具 | 功能 | 实现 |
|------|------|------|
| `get_problem_by_id` | 爬取 OJ 题目详情 | 封装 `OJ题单爬虫.py` 的 `OJCrawler.get_problem_detail()` |
| `solve_captcha` | 验证码识别 | 封装超级鹰 API（ChaojiyingSolver），应对未来反爬升级 |

工具函数内置**日志回调**：爬取/识别过程通过 `MessageBus` 实时推送到 GUI 日志区，用户可观察 Agent 的每一步操作。

### GUI 设计（Tkinter / ttk）

六大分区布局，配色区分功能：

| 分区 | 配色 | 功能 |
|------|------|------|
| 标题区 | - | 工具名 + 一句话说明 |
| 输入区 | - | 题号输入框 + 开始/清空按钮（回车快捷键） |
| 题目详情区 | `#fdfdfd` 浅白 | 显示爬取到的题目原文 |
| Agent 解答区 | `#f4fbf4` 浅绿 | 显示 LLM 生成的思路+代码+复杂度 |
| 运行日志区 | `#1e1e1e` 深色 | Consolas 字体，Agent 每步操作实时滚动 |
| 进度状态区 | - | 不确定进度条 + 状态标签 |

### 线程安全设计 ⭐

Tkinter 的 UI 操作**必须在主线程**执行，而 `agent.invoke()` 是耗时阻塞调用。采用 **后台线程 + 消息总线** 模式解决：

```
┌───────────── 主线程 ─────────────┐
│  Tkinter 事件循环               │
│  root.after(100) 轮询 queue     │
│         ▲                       │
│         │ queue.Queue 消息总线   │
└─────────┼───────────────────────┘
          │
┌─────────┼─────────── 后台线程 ──┴──────────┐
│  ThreadPoolExecutor(max_workers=1)         │
│  agent.invoke()  ← 阻塞调用，不影响 UI     │
│  bus.put("log"/"answer"/"done"/...)       │
└───────────────────────────────────────────┘
```

- **MessageBus**：自定义 `queue.Queue` 封装，支持 `log` / `problem` / `answer` / `status` / `done` / `error` 六种消息类型
- **主线程轮询**：`root.after(100, self._poll_messages)` 每 100ms 取队列消息更新 UI
- **后台线程只 put，不碰 UI**：`_run_agent()` 中所有 UI 交互都转为 `bus.put()` 消息
- **优雅关闭**：`on_close()` 调用 `executor.shutdown(cancel_futures=True)` 释放线程池

## 文件结构

```
08-AI工程化与Agent/
├── OJ_AC助手_GUI.py      ⭐ GUI 主程序（Tkinter + 后台线程 + 消息总线）
├── OJ_AC助手_Agent.py    Agent 核心（工具封装 + create_agent + CLI 交互）
├── OJ题单爬虫.py         爬虫引擎（SessionPage 三层爬取：题单列表→题单内题目→题目详情）
├── requirements.txt      依赖清单
└── .env.example          环境变量模板（脱敏，复制为 .env 填入真实凭证）
```

### OJ题单爬虫.py 三层爬取架构

| 层级 | 方法 | 说明 |
|------|------|------|
| 第一层 | `get_problem_lists()` | 爬取题单列表页所有题单 |
| 第二层 | `get_problems_in_list(list_id)` | 爬取指定题单内所有题目 |
| 第三层 | `get_problem_detail(problem_id)` | 爬取单题详情（标题/描述/输入/输出） |

使用 DrissionPage 的 `SessionPage`（纯 HTTP 无浏览器模式），轻量稳定。预留 `WebPage` 浏览器模式与超级鹰验证码接口，应对反爬升级。

## 依赖安装

```bash
pip install -r requirements.txt
```

## 配置

```bash
# 1. 复制环境变量模板
copy .env.example .env

# 2. 填入你的智谱 API Key（必填）
#    获取地址：https://open.bigmodel.cn/ → 控制台 → API Keys
ZHIPUAI_API_KEY=你的智谱key

# 3.（可选）超级鹰验证码凭证，仅当 OJ 出现验证码时需要
```

## 运行

### GUI 版（推荐）

```bash
python OJ_AC助手_GUI.py
```

界面操作：输入题号 → 点「开始解题」→ Agent 自动爬取并生成解答，全程日志可见。

### CLI 版

```bash
python OJ_AC助手_Agent.py
```

交互式命令行，输入题号（如 2098）即出结果，输入 q 退出。

## 技术栈

| 领域 | 库 / 工具 |
|------|-----------|
| Agent 框架 | LangChain 1.0+ (`create_agent`, `@tool`, `init_chat_model`) |
| LLM 模型 | 智谱 GLM-4-Flash（OpenAI 兼容接口） |
| 爬虫引擎 | DrissionPage (SessionPage 纯 HTTP 模式) |
| 验证码 | 超级鹰 API（base64 编码 + HTTP 上传） |
| GUI | Tkinter / ttk / scrolledtext |
| 并发 | concurrent.futures.ThreadPoolExecutor |
| 线程通信 | queue.Queue 消息总线 |

## 免责声明

仅供学习交流。Agent 生成的解题代码请**理解后再提交**，勿直接抄袭。爬取行为请遵守目标网站 robots.txt 与相关法律法规。
