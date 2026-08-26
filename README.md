# small_mo · Python 爬虫作品集

> 个人 Python 爬虫学习与实战作品库，按**技术能力**分类组织，突出反爬 / 逆向 / 自动化等硬核技术点。
> 所有代码均已脱敏（Cookie / 账号 / 密码替换为占位符），可安全公开。

## 仓库结构

```
small_mo/
├── 01-反爬与验证码破解/          ⭐ 验证码全场景破解（极验点选/滑块/图文）
├── 02-接口爬取与下载/            壁纸 / 小说 / 视频 / 音乐 接口抓取与下载
├── 03-浏览器自动化与社交平台/    DrissionPage 驱动的小红书 / 猪八戒 / 猿急送
├── 04-逆向算法与高阶反爬/        ⭐ 闲鱼 sign 算法逆向 + mtop 接口
├── 05-商品价格监控/             京东 / 淘宝 价格监控 + 定时任务
├── 06-数据分析与可视化/          考研 / 兼职 数据分析与动态可视化大屏
├── 07-反爬避坑实战/             demo1~demo4 渐进式反爬实战
├── 08-AI工程化与Agent/          ⭐ LangChain Agent + OJ 自动解题 + Tkinter GUI
└── 99-进阶整合-Scrapling三层引擎/ ⭐⭐ Scrapling 三层引擎 + B站 DASH 下载 GUI
```

## ⭐ 亮点作品

| 目录 | 文件 | 技术亮点 |
|------|------|----------|
| `01-反爬与验证码破解` | [captcha_solver.py](01-反爬与验证码破解/README.md) | 超级鹰 + CDP 三版点击 + 极验点选/滑块全场景 + 贝塞尔轨迹 |
| `08-AI工程化与Agent` | [OJ_AC助手_GUI.py](08-AI工程化与Agent/README.md) | LangChain create_agent + 爬虫工具封装 + 后台线程消息总线 GUI |
| `99-进阶整合-Scrapling三层引擎` | [哔哩哔哩强爬取.py](99-进阶整合-Scrapling三层引擎/README.md) | Fetcher→StealthyFetcher→Adaptive 三层降级 + DASH 并发下载 + Tkinter GUI |
| `04-逆向算法与高阶反爬` | [闲鱼数据获取.py](04-逆向算法与高阶反爬/README.md) | _m_h5_tk token 提取 + sign MD5 算法逆向 + mtop 接口 |

## 分类索引

### 01-反爬与验证码破解 ⭐
验证码自动破解模块，覆盖极验点选（文字/图标/语序）、极验滑块（拼图/缺口）、普通图文验证码。详见 [该目录 README](01-反爬与验证码破解/README.md)。

### 02-接口爬取与下载
- `壁纸下载/批量爬取壁纸.py`
- `小说下载/小说下载.py`
- `视频下载/b站视频下载.py` — B站视频下载 + moviepy 合并
- `音乐下载/音乐下载.py`

### 03-浏览器自动化与社交平台
基于 DrissionPage 的浏览器自动化采集：
- `小红书数据提取.py`
- `猪八戒数据获取.py`
- `猿急送数据获取.py`

### 04-逆向算法与高阶反爬 ⭐
闲鱼搜索接口 sign 算法逆向，提取 `_m_h5_tk` token 拼接时间戳与 appKey，MD5 生成签名。详见 [该目录 README](04-逆向算法与高阶反爬/README.md)。

### 05-商品价格监控
- `监控京东商品价格.py`
- `监控淘宝商品价格.py` — 淘宝/天猫商品价格监控 + Server酱微信推送
- `自动结束定时任务/` — 京东/淘宝定时监控 + 超时自动收尾

### 06-数据分析与可视化
- `兼职岗位数据分析/生成可视化大屏.py`
- `考研数据分析/` — AI院校分析 + 历年数据采集 + 数据分析服务
- `考研数据可视化/` — 动态图表 + 可视化绘图

### 07-反爬避坑实战
- `demo1贝壳二手房数据获取.py` — 静态页解析入门
- `demo2页面滚动.py` — 滚动加载 + 动态渲染
- `demo3验证码识别.py` — 验证码识别实战
- `demo4多页数据获取.py` — 多页翻页 + 鉴权

### 08-AI工程化与Agent ⭐
基于 LangChain 1.0+ 的 OJ 自动解题 Agent，输入题号即可自动爬取题目并给出解题思路 + Python 参考代码 + 复杂度分析。集成爬虫工具封装、超级鹰验证码识别、Tkinter GUI 与后台线程消息总线。详见 [该目录 README](08-AI工程化与Agent/README.md)。
- `OJ_AC助手_GUI.py` — GUI 主程序（Tkinter 多分区 + ThreadPoolExecutor + queue 消息总线）
- `OJ_AC助手_Agent.py` — Agent 核心（@tool 工具封装 + create_agent + CLI 交互）
- `OJ题单爬虫.py` — 爬虫引擎（SessionPage 三层爬取）

### 99-进阶整合-Scrapling三层引擎 ⭐⭐
基于 Scrapling 框架的 B站视频下载 GUI，集成三层引擎自动降级、DASH 音视频并发下载、ffmpeg 无损合并、Tkinter 图形界面。详见 [该目录 README](99-进阶整合-Scrapling三层引擎/README.md)。

## 技术栈

| 领域 | 库 / 工具 |
|------|-----------|
| HTTP 请求 | requests, curl_cffi, httpx |
| 浏览器自动化 | DrissionPage, Playwright, Patchright |
| 反爬框架 | Scrapling (Fetcher / StealthyFetcher / Adaptive) |
| 验证码 | 超级鹰 API, PIL 图像处理, CDP 鼠标事件 |
| 视频/音频 | ffmpeg, moviepy, imageio-ffmpeg |
| GUI | Tkinter / ttk |
| 数据分析 | pandas, pyecharts, jsonpath |
| 逆向 | hashlib (MD5), sign 算法还原 |
| AI Agent | LangChain 1.0+ (create_agent, @tool), 智谱 GLM-4-Flash |

## 使用说明

1. **代码已脱敏**：所有 Cookie / 账号 / 密码均为占位符，运行前需替换为你自己的凭证。
2. **依赖安装**：各目录文件头部注释标注了所需依赖，按需 `pip install`。
3. **合规使用**：仅用于学习交流，请遵守目标网站 robots.txt 与相关法律法规，勿用于商业或恶意用途。

## License

MIT
