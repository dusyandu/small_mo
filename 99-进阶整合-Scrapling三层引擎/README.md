# 99-进阶整合-Scrapling三层引擎 ⭐⭐

基于 [Scrapling](https://github.com/D4Vinci/Scrapling) 框架的 B站视频下载器，集成**三层引擎自动降级**、**DASH 音视频并发下载**、**ffmpeg 无损合并**与 **Tkinter 图形界面**。

## ⭐ 核心文件：哔哩哔哩强爬取.py

### 三层引擎架构（自动降级）

```
⚡ 引擎 1 · Fetcher (纯 HTTP, curl_cffi/httpx)
      => 最快 (~150ms)，直接打 B 站 view / playurl 接口
      │ 遇 403 / 风控 / 被封时自动降级 ↓
      ▼
🥷 引擎 2 · StealthyFetcher (Patchright + Chromium 隐形浏览器)
      => 浏览器级指纹 + 反爬四件套（block_ads / block_webrtc /
         hide_canvas / dns_over_https / allow_webgl / google_search）
      => 拿首屏真实 Cookie 再打接口
      │ CSS 选择器失效 / B 站改版时降级 ↓
      ▼
🧠 引擎 3 · Adaptive Parser (自适应解析)
      => Fetcher/StealthyFetcher 解析 DOM 时启用 auto_save 保存签名；
         下次即使选择器写错或网站改版，adaptive=True 也能自动找回。
```

用户也可在 GUI 下拉框手动强制指定某一层引擎。

### DASH 视频下载

- B站 DASH 流：视频流与音频流分离，**ThreadPoolExecutor 并发下载**，0.15s 进度回调。
- **ffmpeg `-c copy -movflags +faststart`** 无损秒级合并（不重编码）。
- 自动定位 ffmpeg：`PATH` → `imageio-ffmpeg` 二进制 → `%FFMPEG_PATH%` 环境变量。

### GUI 设计（Tkinter / ttk）

六大区块布局：

1. **输入区**：BV 号 / URL、Cookie、输出目录
2. **引擎参数**：headful 模式、广告屏蔽、WebRTC 屏蔽
3. **视频详情**：标题、UP 主、时长、清晰度下拉（用户选择清晰度后才开始下载）
4. **下载控制**：开始 / 取消按钮
5. **进度区**：双进度条（视频流 / 音频流）+ 百分比
6. **实时日志**：scrolledtext，线程安全输出

### 线程安全

- 工作线程通过 `queue.Queue` 消息总线向主线程传递进度与日志。
- 所有 UI 操作在 Tkinter 主线程执行（`root.after` 调度），避免跨线程崩溃。

### 清晰度支持

```
8K 超高清 / 杜比视界 / 4K 超清 / 1080P 60帧 / 1080P 高码率 /
1080P 高清 / 720P 60帧 / 720P 高清 / 480P 清晰 / 360P 流畅
```

编码识别：H.264/AVC、H.265/HEVC、AV1。

### 依赖安装

```bash
pip install scrapling curl_cffi httpx anyio patchright browserforge msgspec playwright requests
patchright install chromium       # 首次需要，Patchright 自带 patched Chromium
# (可选) pip install imageio-ffmpeg   # 不想单独装 ffmpeg 就装它自带二进制
```

### 运行

```bash
python "哔哩哔哩强爬取.py"
```

## 其他文件

| 文件 | 说明 |
|------|------|
| `b站爬取视频.py` | B站视频下载基础版（moviepy 合并），强爬取的迭代前身 |
