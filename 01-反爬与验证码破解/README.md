# 01-反爬与验证码破解 ⭐

验证码自动破解模块，覆盖主流反爬验证码场景。

## ⭐ 亮点文件：captcha_solver.py

通用验证码破解模块，**保留原 demo4 调用接口完全兼容**（`from tools.captcha_solver import crack_captcha`），同时内嵌完整超级鹰客户端。

### 核心能力

| 能力 | 实现方式 |
|------|----------|
| 极验点选（文字/图标/语序） | 超级鹰 9005/9101 + CDP 真人轨迹点击 |
| 极验滑块（拼图/缺口） | 超级鹰 9902 双图形定位 + 贝塞尔轨迹拖拽 + dpr 缩放 |
| 普通图文验证码（数字/字母/汉字） | 超级鹰 1902/3004/1006 |
| CDP 底层鼠标事件 | mouseMoved → mousePressed → mouseReleased 三阶段 + 随机延迟，绕过自动化检测 |
| 自动化指纹去除 | 自动隐藏 navigator.webdriver + stealth 注入 |
| 请求频率控制 | 随机延迟 + 指数退避重试 |
| 失败申诉 | 超级鹰 ReportError 题分自动返还 |

### 技术亮点

1. **三版 CDP 点击兼容**：DrissionPage（默认）/ Playwright / Selenium 三套实现，按运行环境自动切换。
2. **9902 双中心点滑块距离计算**（`locate_gap_two_points`）：处理带两个定位点的滑块图。
3. **图片拼接 `build_composite`**：提示图 + 搜索区合成 + 偏移量，提升超级鹰识别准确率。
4. **结构化 `CJResult`**：点/矩形解析 + 错误码中文映射，调用方无需关心超级鹰返回格式。
5. **27 种 codetype 常量表**（`CODE` 类）：覆盖超级鹰全部主流验证码类型。
6. **向后兼容**：`Chaojiying_Client` / `ChaojiyingClient` 双名可用，支持环境变量与常量两种凭证读取方式。

### 调用示例

```python
from tools.captcha_solver import crack_captcha

# 原接口，与 demo4 完全兼容
crack_captcha(page)

# 支持额外参数
crack_captcha(page, max_retries=3)
```

### 超级鹰凭证配置

凭证读取优先级：文件常量 → 环境变量（`CHAOJIYING_USER` / `CHAOJIYING_PASS` / `CHAOJIYING_SOFT_ID`）。

> ⚠️ 代码中的账号密码均为占位符，运行前需替换为你自己的超级鹰凭证。

## 其他文件

| 文件 | 说明 |
|------|------|
| `chaojiying.py` | 超级鹰客户端基础版 |
| `chaojiying_helper_max.py` | 超级鹰增强版客户端（含 build_composite / locate_gap_two_points） |
| `图片验证码识别.py` | 图文验证码识别示例 |
| `文字定位验证.py` | 点选文字定位示例 |
| `滑块验证码识别.py` | 滑块缺口识别示例 |
| `滑块验证码识别_tools.py` | 滑块工具集 |
| `运行展示知乎登录验证.py` | 知乎登录验证码实战 |
| `add_image.py` | 图片拼接辅助工具 |
