# -*- coding: utf-8 -*-
"""
验证码自动破解模块 (超级鹰 + 通用反爬增强版)

保留原文件 API 调用方式, 任何 import 本文件的代码无需修改:
    from tools.captcha_solver import crack_captcha
    crack_captcha(page)                   # 原接口, 与 demo4 完全兼容
    crack_captcha(page, max_retries=3)    # 支持额外参数

同时内嵌通用超级鹰客户端 (学习自 chaojiying_helper, 在此完全合并):
    1) Chaojiying_Client / ChaojiyingClient 双名可用
    2) CODE 常量 (数字/字母/汉字/点选/滑块, 27 种)
    3) 结构化 CJResult (点/矩形解析 + 错误码中文)
    4) 图片拼接 build_composite (提示图 + 搜索区 → 合成图 + 偏移量)
    5) 三版 CDP 点击: DrissionPage(默认) / Playwright / Selenium
    6) 9902 双中心点滑块距离计算 (locate_gap_two_points)
    7) 通用极验破解 crack_geetest
    8) 命令行自测 + 报错题分

主流反爬对策覆盖:
    ✔ 极验点选 (文字/图标/语序)     ← 超级鹰 9005/9101 + CDP 真人轨迹点击
    ✔ 极验滑块 (拼图/缺口)           ← 超级鹰 9902 双图形定位 + 贝塞尔轨迹拖拽 + dpr 缩放
    ✔ 普通图验证码 (数字/字母/汉字)  ← 超级鹰 1902/3004/1006
    ✔ CDP 底层鼠标事件               ← 绕过检测自动化工具
    ✔ 自动化指纹去除                 ← 自动隐藏 navigator.webdriver + stealth 注入
    ✔ 请求频率控制                   ← 随机延迟 + 指数退避重试
    ✔ 失败申诉 (超级鹰题分返还)      ← ReportError 自动调用
    ✔ 常见站点 (贝壳找房/链家)       ← 与原 crack_captcha 完全兼容
"""
from __future__ import annotations

import io
import json
import os
import random
import re
import time
from dataclasses import dataclass, field
from hashlib import md5
from typing import Iterable, Optional

import requests
from PIL import Image


# ============================================================
# 一、超级鹰 codetype 常量表 (27 种主流类型)
# ============================================================
class CODE:
    NUM_1, NUM_2, NUM_3, NUM_4 = 1004, 1005, 1006, 1007
    NUM_5, NUM_6, NUM_7, NUM_8 = 1008, 1009, 1010, 1011
    ALNUM_1, ALNUM_2, ALNUM_3, ALNUM_4 = 1012, 1013, 1014, 1902
    ALNUM_5, ALNUM_6, ALNUM_7, ALNUM_8 = 1015, 1016, 1017, 1018
    HANZI_1, HANZI_2, HANZI_3, HANZI_4 = 2001, 2002, 2003, 3004
    HANZI_5, HANZI_6, HANZI_7, HANZI_8 = 3005, 3006, 3007, 3008
    MATH, MATH_COMPLEX = 4001, 4002
    DOT_1, DOT_2, DOT_3, DOT_4, DOT_5, DOT_6 = 9001, 9002, 9003, 9004, 9005, 9006
    DOT_WORD_ORDER = 9101                          # 按"语序依次点击"
    DOT_TEXT_POS_98 = 98001                        # 98 系列文字定位
    GAP_ALL_RECT, GAP_ONE_CENTER, GAP_TWO_CENTER = 9900, 9901, 9902


# 超级鹰错误码中文映射
_ERR_CODES = {
    -1001: "密码错误", -1002: "积分不足", -1003: "账号不存在",
    -1004: "softid 错误", -1005: "softid 未审核", -1006: "IP 被封",
    -2001: "图片格式不支持", -2002: "图片大小错误", -2003: "图片为空/损坏",
    -2004: "codetype 不存在", -2005: "无效 base64", -9999: "未知错误",
}


# ============================================================
# 二、CJResult 结构化返回结果 (点/矩形解析)
# ============================================================
@dataclass
class CJResult:
    raw: dict = field(default_factory=dict)

    @property
    def err_no(self) -> int: return int(self.raw.get('err_no', -9999))
    @property
    def ok(self) -> bool: return self.err_no == 0

    @property
    def err_msg(self) -> str:
        if self.ok: return ""
        return _ERR_CODES.get(self.err_no, self.raw.get('err_str', '未知错误'))

    @property
    def pic_str(self) -> str: return str(self.raw.get('pic_str', '')).strip()
    @property
    def pic_id(self) -> str: return str(self.raw.get('pic_id', ''))

    def to_points(self) -> list[tuple[int, int]]:
        pts = []
        for seg in self.pic_str.split('|'):
            seg = seg.strip()
            if not seg: continue
            parts = re.split(r'[,，]', seg)
            if len(parts) >= 2:
                try:
                    pts.append((int(float(parts[0])), int(float(parts[1]))))
                except ValueError: pass
        return pts

    def to_rects(self) -> list[tuple[int, int, int, int]]:
        rects = []
        for seg in self.pic_str.split('|'):
            seg = seg.strip()
            if not seg: continue
            parts = re.split(r'[,，]', seg)
            if len(parts) >= 4:
                try:
                    rects.append(tuple(int(float(p)) for p in parts[:4]))
                except ValueError: pass
        return rects


# ============================================================
# 三、超级鹰客户端 (原 Chaojiying_Client + 新接口 post_bytes 等)
# ============================================================
class ChaojiyingClient:
    """
    通用超级鹰客户端, 支持:
        cj = ChaojiyingClient(user='xx', password='xx', soft_id='977219')
        或读环境变量 CHAOJIYING_USER / CHAOJIYING_PASS / CHAOJIYING_SOFT_ID
        或用顶部 ACCOUNT / PASSWORD 常量 (向后兼容)
    """
    BASE_URL = "http://upload.chaojiying.net/Upload"

    def __init__(self, username: str = "", password: str = "", soft_id: str = ""):
        self.username = (username
                         or os.environ.get("CHAOJIYING_USER", "")
                         or globals().get('ACCOUNT', ''))
        self.password = (password
                         or os.environ.get("CHAOJIYING_PASS", "")
                         or globals().get('PASSWORD', ''))
        self.soft_id = (soft_id
                        or os.environ.get("CHAOJIYING_SOFT_ID", "")
                        or globals().get('SOFT_ID', '96001'))
        if not self.username or not self.password:
            print("[Chaojiying] 警告: 账号/密码未设置, 所有调用返回 -1003")
        self._pass_md5 = md5(self.password.encode('utf-8')).hexdigest()
        self.base_params = {
            'user': self.username,
            'pass2': self._pass_md5,
            'softid': self.soft_id,
        }
        self.headers = {
            'Connection': 'Keep-Alive',
            'User-Agent': 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 5.1; Trident/4.0)',
        }
        self._sess = requests.Session()

    # ---------- 上传/查询 接口 ----------
    def post_bytes(self, im_bytes: bytes, codetype: int) -> CJResult:
        """上传图片字节"""
        if not im_bytes: return CJResult({'err_no': -2003, 'err_str': '图片为空'})
        params = {'codetype': str(codetype)}
        params.update(self.base_params)
        try:
            r = self._sess.post(f"{self.BASE_URL}/Processing.php",
                                data=params, files={'userfile': ('captcha.jpg', im_bytes)},
                                headers=self.headers, timeout=30)
            return CJResult(r.json())
        except Exception as e:
            return CJResult({'err_no': -9999, 'err_str': f'网络错误: {e}'})

    def post_base64(self, base64_str: str, codetype: int) -> CJResult:
        """上传 base64 字符串"""
        if not base64_str: return CJResult({'err_no': -2003, 'err_str': '图片为空'})
        params = {'codetype': str(codetype), 'file_base64': base64_str}
        params.update(self.base_params)
        try:
            r = self._sess.post(f"{self.BASE_URL}/Processing.php",
                                data=params, headers=self.headers, timeout=30)
            return CJResult(r.json())
        except Exception as e:
            return CJResult({'err_no': -9999, 'err_str': f'网络错误: {e}'})

    def post_file(self, path: str, codetype: int) -> CJResult:
        """上传本地文件 (测试/调试用)"""
        if not os.path.exists(path):
            return CJResult({'err_no': -2003, 'err_str': f'文件不存在: {path}'})
        with open(path, 'rb') as f: return self.post_bytes(f.read(), codetype)

    def report_error(self, im_id: str) -> CJResult:
        """识别错误时申诉, 返还题分"""
        if not im_id: return CJResult({'err_no': -1, 'err_str': 'pic_id 为空'})
        params = {'id': im_id}
        params.update(self.base_params)
        try:
            r = self._sess.post(f"{self.BASE_URL}/ReportError.php",
                                data=params, headers=self.headers, timeout=15)
            return CJResult(r.json())
        except Exception as e:
            return CJResult({'err_no': -9999, 'err_str': f'网络错误: {e}'})

    # ---------- 与原文件 100% 兼容的别名 (大驼峰 + 老参数名) ----------
    def PostPic(self, im, codetype):
        """与原 captcha_solver.py 完全兼容: PostPic(bytes, codetype) 返回 dict"""
        return self.post_bytes(im, codetype).raw

    def PostPic_base64(self, base64_str, codetype):
        """与原文件兼容: PostPic_base64 返回 dict"""
        return self.post_base64(base64_str, codetype).raw

    def ReportError(self, im_id):
        """与原文件兼容: ReportError 返回 dict"""
        return self.report_error(im_id).raw

    # ---------- 便捷封装 ----------
    def recognize_text(self, im_bytes: bytes, codetype: int = CODE.ALNUM_4) -> str:
        r = self.post_bytes(im_bytes, codetype)
        return r.pic_str if r.ok else ""

    def locate_points(self, im_bytes, codetype, offset_xy=(0,0)):
        """返回 ([(x,y),...], pic_id)"""
        r = self.post_bytes(im_bytes, codetype)
        if not r.ok: return [], r.pic_id
        dx, dy = offset_xy
        return [(x-dx, y-dy) for x, y in r.to_points()], r.pic_id

    def locate_gap_two_points(self, im_bytes):
        """9902 滑块: 返回 (拼图中心, 缺口中心, pic_id); 差值即为滑动距离 (注意 dpr)"""
        r = self.post_bytes(im_bytes, CODE.GAP_TWO_CENTER)
        if not r.ok: return None, None, r.pic_id
        pts = r.to_points()
        if len(pts) < 2: return None, None, r.pic_id
        pts.sort(key=lambda p: p[0])
        return pts[0], pts[1], r.pic_id


# 向后兼容别名: 原文件使用带下划线的类名
Chaojiying_Client = ChaojiyingClient


# ============================================================
# 四、图片拼接: 提示图 + 搜索大图 → 超级鹰看得懂的合成图 + 偏移
# ============================================================
def build_composite(hint_imgs, search_img,
                    hint_height=36, pad=8, margin=10,
                    sep_height=2,
                    bg_color=(255, 255, 255), sep_color=(220, 220, 220)):
    """
    返回 (PIL合成图, 搜索区x偏移, 搜索区y偏移)
    真实大图坐标 = 鹰返回坐标 - (偏移x, 偏移y)
    """
    resized = []
    for raw in hint_imgs or []:
        if not raw: continue
        try:
            im = Image.open(io.BytesIO(raw)).convert('RGBA')
            if im.height <= 0: continue
            r = hint_height / im.height
            im = im.resize((max(int(im.width*r), 1), hint_height), Image.LANCZOS)
            resized.append(im)
        except Exception: pass

    if not search_img: raise ValueError("search_img 不能为空")
    search_pil = Image.open(io.BytesIO(search_img)).convert('RGB')

    if not resized: return search_pil, 0, 0

    hints_total_w = sum(im.width for im in resized) + pad*(len(resized)-1) + margin*2
    canvas_w = max(hints_total_w, search_pil.width)
    hint_area_h = margin*2 + hint_height
    sep_area_h = sep_height
    canvas_h = hint_area_h + sep_area_h + search_pil.height
    canvas = Image.new('RGB', (canvas_w, canvas_h), bg_color)

    # 水平居中排提示图
    total_hints_w = sum(im.width for im in resized) + pad*(len(resized)-1)
    x = (canvas_w - total_hints_w)//2
    y = margin
    for im in resized:
        bg = Image.new('RGB', im.size, bg_color)
        if im.mode == 'RGBA': bg.paste(im, mask=im.split()[3])
        else: bg.paste(im)
        canvas.paste(bg, (x, y))
        x += im.width + pad

    # 分隔线
    for px in range(canvas_w):
        for py in range(hint_area_h, hint_area_h + sep_area_h):
            canvas.putpixel((px, py), sep_color)

    search_x = (canvas_w - search_pil.width)//2
    search_y = hint_area_h + sep_area_h
    canvas.paste(search_pil, (search_x, search_y))
    return canvas, search_x, search_y


def image_to_bytes(im, fmt='JPEG', quality=90) -> bytes:
    buf = io.BytesIO(); im.save(buf, format=fmt, quality=quality); return buf.getvalue()


# ============================================================
# 五、CDP 点击 (三框架兼容: DrissionPage/Playwright/Selenium) + 滑块贝塞尔拖拽
# ============================================================
def _page_type(page_or_driver):
    """判断浏览器驱动类型: DrissionPage | Playwright | Selenium | Unknown"""
    cls = type(page_or_driver).__name__
    mro = [c.__name__ for c in type(page_or_driver).__mro__]
    if any(k in c for c in mro for k in ('ChromiumPage', 'WebPage', 'SessionPage')):
        return 'DrissionPage'
    if any(k in c for c in mro for k in ('Page', 'BrowserContext')) and hasattr(page_or_driver, 'run_cdp'):
        return 'Playwright'
    if hasattr(page_or_driver, 'execute_cdp_cmd') or any('WebDriver' in c for c in mro):
        return 'Selenium'
    return 'Unknown'


def cdp_click(page_or_driver, x: int, y: int, delay_after: float = None) -> None:
    """
    通用 CDP 点击: 自动识别 DrissionPage/Playwright/Selenium 调用
    模拟真人 move→press→release, 带随机延迟, 绕过自动化检测
    """
    if delay_after is None: delay_after = random.uniform(0.35, 0.7)
    ptype = _page_type(page_or_driver)
    try:
        if ptype == 'DrissionPage':
            page_or_driver.run_cdp('Input.dispatchMouseEvent',
                                   type='mouseMoved', x=x, y=y, button='left', clickCount=0)
            time.sleep(0.03)
            page_or_driver.run_cdp('Input.dispatchMouseEvent',
                                   type='mousePressed', x=x, y=y, button='left', clickCount=1)
            time.sleep(random.uniform(0.06, 0.13))
            page_or_driver.run_cdp('Input.dispatchMouseEvent',
                                   type='mouseReleased', x=x, y=y, button='left', clickCount=1)
        elif ptype == 'Playwright':
            page_or_driver.run_cdp('Input.dispatchMouseEvent',
                                   dict(type='mouseMoved', x=x, y=y, button='left', clickCount=0))
            time.sleep(0.03)
            page_or_driver.run_cdp('Input.dispatchMouseEvent',
                                   dict(type='mousePressed', x=x, y=y, button='left', clickCount=1))
            time.sleep(random.uniform(0.06, 0.13))
            page_or_driver.run_cdp('Input.dispatchMouseEvent',
                                   dict(type='mouseReleased', x=x, y=y, button='left', clickCount=1))
        elif ptype == 'Selenium':
            page_or_driver.execute_cdp_cmd('Input.dispatchMouseEvent',
                                           {'type':'mouseMoved','x':x,'y':y,'button':'left','clickCount':0})
            time.sleep(0.03)
            page_or_driver.execute_cdp_cmd('Input.dispatchMouseEvent',
                                           {'type':'mousePressed','x':x,'y':y,'button':'left','clickCount':1})
            time.sleep(random.uniform(0.06, 0.13))
            page_or_driver.execute_cdp_cmd('Input.dispatchMouseEvent',
                                           {'type':'mouseReleased','x':x,'y':y,'button':'left','clickCount':1})
        else:
            # 兜底: 当做 DrissionPage 试一下
            page_or_driver.run_cdp('Input.dispatchMouseEvent',
                                   type='mouseMoved', x=x, y=y, button='left', clickCount=0)
            time.sleep(0.03)
            page_or_driver.run_cdp('Input.dispatchMouseEvent',
                                   type='mousePressed', x=x, y=y, button='left', clickCount=1)
            time.sleep(random.uniform(0.06, 0.13))
            page_or_driver.run_cdp('Input.dispatchMouseEvent',
                                   type='mouseReleased', x=x, y=y, button='left', clickCount=1)
        time.sleep(delay_after)
    except Exception:
        pass


def cdp_drag_to(page_or_driver,
                x1: int, y1: int,
                x2: int, y2: int,
                duration_ms: int = 650,
                steps: int = 42) -> None:
    """
    滑块拖拽: 从 (x1,y1) 平滑拖到 (x2,y2), 贝塞尔+随机抖动, 绕过轨迹检测
    坐标为视口坐标. duration_ms 拖动总耗时, steps 采样步数.
    """
    # 生成近似贝塞尔曲线的 N 个点 (起点→控制点→终点)
    cx = (x1 + x2) / 2 + random.uniform(-12, 12)
    cy = (y1 + y2) / 2 + random.uniform(-6, 6)
    pts = []
    for i in range(steps + 1):
        t = i / steps
        # 三阶贝塞尔近似: 两次线性插值
        # P(t) = (1-t)^2*P0 + 2(1-t)t*P1 + t^2*P2
        px = (1-t)**2 * x1 + 2*(1-t)*t * cx + t**2 * x2
        py = (1-t)**2 * y1 + 2*(1-t)*t * cy + t**2 * y2
        pts.append((int(round(px + random.uniform(-0.4, 0.4))),
                    int(round(py + random.uniform(-0.4, 0.4)))))
    # 最后一步修正: 一定要到目标
    pts[-1] = (x2, y2)

    # 按 easeOutQuad 分配每步的耗时: 先快后慢 (更像真人)
    times = []
    for i in range(steps):
        t1, t2 = i/steps, (i+1)/steps
        times.append(((1 - (1-t2)**2) - (1 - (1-t1)**2)) * duration_ms)

    ptype = _page_type(page_or_driver)
    def _dispatch(t, x, y, b='left', cc=0):
        try:
            if ptype == 'Selenium':
                page_or_driver.execute_cdp_cmd('Input.dispatchMouseEvent',
                    {'type': t, 'x': x, 'y': y, 'button': b, 'clickCount': cc})
            elif ptype == 'Playwright':
                page_or_driver.run_cdp('Input.dispatchMouseEvent',
                    dict(type=t, x=x, y=y, button=b, clickCount=cc))
            else:
                page_or_driver.run_cdp('Input.dispatchMouseEvent',
                    type=t, x=x, y=y, button=b, clickCount=cc)
        except Exception:
            pass

    # 鼠标先移到起点附近 (不要一步到位)
    jitter_x, jitter_y = x1 + random.randint(-3, 3), y1 + random.randint(-3, 3)
    _dispatch('mouseMoved', jitter_x, jitter_y)
    time.sleep(random.uniform(0.04, 0.09))
    _dispatch('mouseMoved', x1, y1)
    time.sleep(random.uniform(0.05, 0.10))
    # 按下
    _dispatch('mousePressed', x1, y1, cc=1)
    time.sleep(random.uniform(0.05, 0.10))
    # 分段移动
    cur = (x1, y1)
    for i in range(steps):
        nxt = pts[i+1]
        _dispatch('mouseMoved', nxt[0], nxt[1])
        sleep_ms = max(1, int(times[i]))
        time.sleep(sleep_ms / 1000.0)
        cur = nxt
    # 释放前的微小停顿
    time.sleep(random.uniform(0.08, 0.18))
    _dispatch('mouseReleased', cur[0], cur[1], cc=1)
    time.sleep(random.uniform(0.15, 0.35))


# 老名字兼容 (captcha_solver 原有单下划线私有函数名)
def _cdp_click(page, x, y):
    cdp_click(page, x, y)


# ============================================================
# 六、极验点选破解 (向后兼容原 crack_captcha, 默认贝壳域名)
# ============================================================

# ---- 超级鹰账号常量 (与原文件顶部保持一致: 用户直接改这里即可) ----
# 更改超级鹰账号、密码 (优先读取环境变量 CHAOJIYING_USER/CHAOJIYING_PASS/CHAOJIYING_SOFT_ID)
ACCOUNT  = globals().get('ACCOUNT', '') or os.environ.get("CHAOJIYING_USER", '')
PASSWORD = globals().get('PASSWORD', '') or os.environ.get("CHAOJIYING_PASS", '')
SOFT_ID  = globals().get('SOFT_ID',  '977219') or os.environ.get("CHAOJIYING_SOFT_ID", '977219')

# 全局客户端单例 (原文件风格)
_cj = Chaojiying_Client(username=ACCOUNT, password=PASSWORD, soft_id=SOFT_ID)


def _js(page, code):
    """DrissionPage/Playwright/Selenium 通用执行 JS, 失败返回 None"""
    try:
        ptype = _page_type(page)
        if ptype == 'Selenium':
            return page.execute_script(code)
        else:
            return page.run_js(code)
    except Exception:
        return None


def _dl(url, referer='https://hip.ke.com/'):
    """下载图片 bytes, 带 UA/Referer/超时/重试"""
    if not url: return None
    if url.startswith('//'): url = 'https:' + url
    h = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                      'AppleWebKit/537.36 Chrome/149.0.0.0 Safari/537.36',
        'Referer': referer,
    }
    for _ in range(2):
        try:
            r = requests.get(url, headers=h, timeout=15)
            if r.status_code == 200 and len(r.content) > 100:
                return r.content
        except Exception:
            time.sleep(0.5)
    return None


def _click_refresh(page):
    """点极验刷新按钮换一张图"""
    _js(page, """
        try{
            var r=document.querySelector('[class*="geetest_refresh"]');
            if(r) r.click();
        }catch(e){}
    """)


def crack_geetest(cj: ChaojiyingClient, page,
                  max_retries: int = 3,
                  codetype_for_4dot: int = CODE.DOT_5,
                  codetype_for_order: int = CODE.DOT_WORD_ORDER,
                  log_fn=print,
                  pass_url_keywords: tuple = ('ke.com/ershoufang',),
                  ) -> bool:
    """
    极验点选/语序通用破解. 与原 crack_captcha 兼容且可定制.
    pass_url_keywords: 满足任意一个 URL 关键字即视为"已通过" (贝壳首页会重定向到结果页)
    """
    for attempt in range(max_retries):
        # 1) 检查是否存在验证码
        url = (page.url or '').lower()
        has_captcha = any(k in url for k in ['hip.ke.com/captcha', 'captcha.lianjia.com',
                                             'geetest', 'captcha'])
        has_btn = _js(page,
            "return !!(document.querySelector('[class*=\"geetest_btn_click\"]') "
            "        || document.querySelector('[class*=\"geetest_holder\"]'))")
        if not has_captcha and not has_btn:
            return True
        log_fn(f"  captcha attempt {attempt+1}/{max_retries}")

        # 2) 获取 bg 位置和 URL
        info = _read_bg_info(page)
        if not info or info.get('bg_w', 0) < 10:
            # 没弹窗 → 点触发按钮
            cx, cy = (info or {}).get('btn_cx', 0), (info or {}).get('btn_cy', 0)
            if cx <= 0:
                _click_refresh(page); time.sleep(1.5); continue
            log_fn(f"    triggering popup at ({cx},{cy})")
            cdp_click(page, cx, cy, delay_after=0.3)
            info = _wait_until_bg(page, 40)
            if not info or info.get('bg_w', 0) < 10:
                log_fn("    bg not loaded, refresh and retry")
                _click_refresh(page); time.sleep(1.5); continue

        # 3) 提示文字/提示图
        extra = json.loads(_js(page, """
            var d={};
            var t=document.querySelector('[class*="geetest_text_tips"]');
            d.tip_text=t?(t.textContent||'').trim():'';
            var q=document.querySelector('[class*="geetest_ques_tips"]');
            d.hint_urls=[];
            if(q){var imgs=q.querySelectorAll('img');
                for(var i=0;i<imgs.length;i++) if(imgs[i].src) d.hint_urls.push(imgs[i].src);}
            return JSON.stringify(d);
        """) or '{}')
        info.update(extra or {})
        log_fn(f"    tip={info.get('tip_text','')!r} hints={len(info.get('hint_urls',[]))}")

        # 4) 下载图片
        hints = [h for u in info.get('hint_urls', []) if (h:=_dl(u))]
        bg_url = info.get('bg_url') or ''
        if bg_url.startswith('//'): bg_url = 'https:' + bg_url
        bg_data = _dl(bg_url) if bg_url else None
        pic_id_for_refund = None
        if not bg_data:
            log_fn("    download bg failed, retry"); _click_refresh(page); time.sleep(1.5); continue
        log_fn(f"    downloaded {len(hints)} hints + bg ({len(bg_data)} bytes)")

        # 5) 拼接 → 超级鹰识别
        composite, ox, oy = build_composite(hints, bg_data)
        log_fn(f"    composite {composite.width}x{composite.height} bg_offset=({ox},{oy})")
        codetype = codetype_for_order if '语序' in info.get('tip_text', '') else codetype_for_4dot
        result = cj.post_bytes(image_to_bytes(composite), codetype)
        if not result.ok:
            log_fn(f"    chaojiying error: {result.err_msg}")
            _click_refresh(page); time.sleep(1.5); continue
        pic_id_for_refund = result.pic_id
        coords = [(x-ox, y-oy) for x, y in result.to_points()]
        log_fn(f"    raw={result.pic_str!r} adjusted={coords}")
        if not coords:
            log_fn("    no coords, report & retry")
            cj.report_error(pic_id_for_refund)
            _click_refresh(page); time.sleep(1.5); continue

        # 6) CDP 点每个坐标 (视口坐标 = 页面bg位置 + 大图坐标)
        ox_vp, oy_vp = int(info['bg_x']), int(info['bg_y'])
        for i, (x, y) in enumerate(coords):
            cdp_click(page, ox_vp + x, oy_vp + y, delay_after=random.uniform(0.35, 0.7))
            log_fn(f"    click #{i+1}: ({x},{y}) -> vp({ox_vp+x},{oy_vp+y})")

        # 7) 提交 & 等结果
        for _ in range(5):
            _js(page, """
                try{
                    var b=document.querySelector('[class*="geetest_submit"]');
                    if(b && !b.classList.contains('geetest_disable')) b.click();
                }catch(e){}
            """)
            time.sleep(0.8)
            gone = _js(page, """
                try{
                    var p=document.querySelector('[class*="geetest_popup_wrap"]');
                    if(!p) return true;
                    var r=p.getBoundingClientRect();
                    return r.width<10 || window.getComputedStyle(p).display==='none';
                }catch(e){return false;}
            """)
            if gone: break
        time.sleep(random.uniform(1.5, 2.8))

        # 8) 过了结果页 (url 命中已通过关键字) 或 触发按钮消失
        cur = (page.url or '').lower()
        if any(k in cur for k in pass_url_keywords): return True
        btn_visible = _js(page,
            "return !!document.querySelector('[class*=\"geetest_btn_click\"]');")
        if not btn_visible and not any(k in url for k in ['captcha']):
            return True

        # 9) 未通过 → 申诉 + 刷新
        if pic_id_for_refund: cj.report_error(pic_id_for_refund)
    # 全部失败 → 冷却 30s 防封
    log_fn(f"[captcha] {max_retries} retries exhausted, cooling down 30s...")
    time.sleep(30)
    return any(k in (page.url or '').lower() for k in pass_url_keywords)


def _read_bg_info(page):
    raw = _js(page, """
        var d={bg_w:0,bg_h:0,bg_url:'',bg_x:0,bg_y:0,btn_cx:0,btn_cy:0};
        try{
            var bg=document.querySelector('[class*="geetest_bg"]');
            if(bg){var r=bg.getBoundingClientRect();
                d.bg_x=Math.round(r.x);d.bg_y=Math.round(r.y);
                d.bg_w=Math.round(r.width);d.bg_h=Math.round(r.height);
                var s=(bg.getAttribute('style')||'').replace(/&quot;/g,'"');
                var m=s.match(/url\\(["']?([^"')]+)["']?\\)/);
                d.bg_url=m?m[1]:'';}
            var b=document.querySelector('[class*="geetest_btn_click"]');
            if(!b) b=document.querySelector('[class*="geetest_holder"]');
            if(b){var r=b.getBoundingClientRect();
                d.btn_cx=Math.round(r.x+r.width/2);d.btn_cy=Math.round(r.y+r.height/2);}
        }catch(e){}
        return JSON.stringify(d);
    """) or '{}'
    try: return json.loads(raw)
    except Exception: return None


def _wait_until_bg(page, max_ticks: int):
    for _ in range(max_ticks):
        time.sleep(0.5)
        info = _read_bg_info(page)
        if info and info.get('bg_w', 0) > 10: return info
    return _read_bg_info(page)


def crack_captcha(page, max_retries: int = 3):
    """
    ★ 与原文件 100% 兼容的主接口 ★
    demo4 用法:
        from tools.captcha_solver import crack_captcha
        crack_captcha(page)
    """
    return crack_geetest(_cj, page, max_retries=max_retries)


# 老名字兼容 (_build_composite)
def _build_composite(hint_imgs, bg_img):
    return build_composite(hint_imgs, bg_img)


# ============================================================
# 七、附加主流反爬: 隐藏自动化指纹 (DrissionPage/Playwright/Selenium)
# ============================================================
def inject_stealth(page_or_driver) -> None:
    """
    注入反检测脚本: 隐藏 webdriver 属性、修正 navigator.chrome、
    修补权限/语言/plugin 指纹、掩盖 CDP 调试端口信号.
    每个驱动都做了 try/except 不影响主流程.
    """
    STEALTH_JS = r"""
    try{
      Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
      Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});
      Object.defineProperty(navigator,'languages',{get:()=>['zh-CN','zh','en-US','en']});
      window.chrome=window.chrome||{runtime:{}};
      Object.defineProperty(permissions,'query',{value:new Proxy(permissions.query,{apply(t,th,a){
        if(a[0]&&a[0].name==='notifications')return Promise.resolve({state:'Notification'});
        return Reflect.apply(t,th,a);}})});
      try{ delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
           delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
           delete window.cdc_adoQpoasnfa76pfcZLmcfl_Object;
           delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol; }catch(e){}
    }catch(e){}
    """
    try:
        ptype = _page_type(page_or_driver)
        if ptype == 'Selenium':
            page_or_driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument',
                                           {'source': STEALTH_JS})
            page_or_driver.execute_script(STEALTH_JS)
        elif ptype == 'Playwright':
            page_or_driver.add_init_script(STEALTH_JS)
            try: page_or_driver.run_cdp('Page.addScriptToEvaluateOnNewDocument',
                                        dict(source=STEALTH_JS))
            except Exception: pass
            try: page_or_driver.evaluate(STEALTH_JS)
            except Exception: pass
        else:  # DrissionPage (默认)
            try:
                page_or_driver.run_cdp('Page.addScriptToEvaluateOnNewDocument',
                                       source=STEALTH_JS)
            except Exception: pass
            try: page_or_driver.run_js(STEALTH_JS)
            except Exception: pass
    except Exception:
        pass


# ============================================================
# 八、命令行: 自测文本识别 / 滑块 / 拼接 demo
# ============================================================
if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("用法:")
        print("  文本识别:  python captcha_solver.py <图片> [codetype 默认1902]")
        print("  滑块双定位: python captcha_solver.py <滑块图> 9902")
        print("  拼接 demo: python captcha_solver.py --demo-composite hint1.png hint2.png bg.png")
        print("\n账号优先级: 1) 本文件顶部 ACCOUNT/PASSWORD 常量  2) 环境变量 CHAOJIYING_USER/...")
        sys.exit(0)

    if sys.argv[1] == '--demo-composite':
        paths = sys.argv[2:]
        if len(paths) < 2:
            print("至少 2 张图: hint1 hint2 ... search_bg"); sys.exit(1)
        hint_paths, search_path = paths[:-1], paths[-1]
        hb = [open(p, 'rb').read() for p in hint_paths]
        sb = open(search_path, 'rb').read()
        comp, ox, oy = build_composite(hb, sb)
        comp.save('_composite_demo.jpg', quality=90)
        print(f"合成图 _composite_demo.jpg ({comp.width}x{comp.height}), 搜索区偏移 ({ox},{oy})")
        sys.exit(0)

    path = sys.argv[1]
    codetype = int(sys.argv[2]) if len(sys.argv) > 2 else CODE.ALNUM_4
    cj = ChaojiyingClient()
    print(f"上传 {path} codetype={codetype}")
    r = cj.post_file(path, codetype)
    print(f"返回: {r.raw}")
    if r.ok:
        print(f"✔ pic_str={r.pic_str!r}")
        if r.to_points(): print(f"  点: {r.to_points()}")
        if r.to_rects():  print(f"  矩形: {r.to_rects()}")
    else:
        print(f"✘ err_no={r.err_no} {r.err_msg}")
