# -*- coding: utf-8 -*-
"""
超级鹰通用验证码识别模块 —— 学习自 captcha_solver.py 并增强通用化

功能:
    1) ChaojiyingClient 客户端 (支持环境变量读取账号/密码, 不写进代码)
    2) 常见 codetype 常量表 (数字/字母/汉字/点选坐标/滑块定位)
    3) 图片拼接工具 (提示图 + 搜索区 → 超级鹰可识别的合成图, 返回偏移量)
    4) Playwright + Selenium 双版本 CDP 点击 (绕过自动化检测)
    5) 本地图片快速测试 (无需浏览器)

用法 1: 直接调用超级鹰 API
    from chaojiying_helper import ChaojiyingClient, CODE
    cj = ChaojiyingClient('账号', '密码', 'soft_id')
    result = cj.post_bytes(open('code.png', 'rb').read(), CODE.ALNUM_4)
    if result.ok:
        print('识别结果:', result.pic_str)

用法 2: 极验点选 (Playwright)
    from chaojiying_helper import crack_geetest
    crack_geetest(page)

参考:
    超级鹰 codetype 定价 https://www.chaojiying.com/price.html
    错误码表 https://www.chaojiying.com/api-23.html
"""
from __future__ import annotations

import io
import os
import random
import re
import time
from dataclasses import dataclass, field
from hashlib import md5
from typing import Iterable, Optional

import requests
from PIL import Image


# ==========================================
# 一、常见 codetype 常量 (参考官方文档整理)
# ==========================================
class CODE:
    """codetype 常量, 命名: 类型_位数 或 类型_说明"""
    # ---- 数字 ----
    NUM_1 = 1004             # 1 位纯数字
    NUM_2 = 1005             # 2 位纯数字
    NUM_3 = 1006             # 3 位纯数字
    NUM_4 = 1007             # 4 位纯数字
    NUM_5 = 1008             # 5 位纯数字
    NUM_6 = 1009             # 6 位纯数字
    NUM_7 = 1010             # 7 位纯数字
    NUM_8 = 1011             # 8 位纯数字
    # ---- 数字 + 字母 ----
    ALNUM_1 = 1012           # 1 位数字字母
    ALNUM_2 = 1013           # 2 位数字字母
    ALNUM_3 = 1014           # 3 位数字字母
    ALNUM_4 = 1902           # 4 位数字字母 (最常用, 官方推荐)
    ALNUM_5 = 1015           # 5 位数字字母
    ALNUM_6 = 1016           # 6 位数字字母
    ALNUM_7 = 1017           # 7 位数字字母
    ALNUM_8 = 1018           # 8 位数字字母
    # ---- 汉字 ----
    HANZI_1 = 2001           # 1 位汉字
    HANZI_2 = 2002           # 2 位汉字
    HANZI_3 = 2003           # 3 位汉字
    HANZI_4 = 3004           # 4 位汉字 (常用)
    HANZI_5 = 3005           # 5 位汉字
    HANZI_6 = 3006           # 6 位汉字
    HANZI_7 = 3007           # 7 位汉字
    HANZI_8 = 3008           # 8 位汉字
    # ---- 计算题 (2+3=? 这种) ----
    MATH = 4001              # 普通计算题, 返回数字
    MATH_COMPLEX = 4002      # 带加减乘除的复杂计算
    # ---- 坐标点选 (pic_str 格式 x,y|x,y|...) ----
    DOT_1 = 9001             # 1 个点
    DOT_2 = 9002             # 2 个点
    DOT_3 = 9003             # 3 个点
    DOT_4 = 9004             # 4 个点
    DOT_5 = 9005             # 5 个点 (贝壳极验用)
    DOT_6 = 9006             # 6 个点
    DOT_WORD_ORDER = 9101    # 按语序/顺序点选 (贝壳"依次点击"用)
    DOT_TEXT_POS_98 = 98001  # 98 系列文字定位, 返回 x,y,x,y...
    # ---- 滑块缺口定位 ----
    GAP_ALL_RECT = 9900      # 所有图形块矩形 x1,y1,x2,y2|... (可信度排序)
    GAP_ONE_CENTER = 9901    # 单个图形块的中心点 (x,y)
    GAP_TWO_CENTER = 9902    # 两个图形块的中心点 (x1,y1|x2,y2)


# 错误码表 (常见)
ERR_CODES = {
    -1001: "密码错误",
    -1002: "余额不足 (超级鹰账号积分没了)",
    -1003: "账号不存在",
    -1004: "软件 ID (softid) 错误或不存在",
    -1005: "软件 ID 未审核",
    -1006: "IP 被封 (超过频率)",
    -2001: "图片格式不支持",
    -2002: "图片大小错误 (<1KB 或 >10MB)",
    -2003: "图片为空 / 损坏",
    -2004: "无此 codetype",
    -2005: "无效的 base64 字符串",
    -2006: "codetype 数量和结果不一致",
    -9999: "未知错误",
}


# ==========================================
# 二、结构化返回结果
# ==========================================
@dataclass
class CJResult:
    raw: dict = field(default_factory=dict)

    @property
    def err_no(self) -> int:
        return int(self.raw.get('err_no', -9999))

    @property
    def ok(self) -> bool:
        return self.err_no == 0

    @property
    def err_msg(self) -> str:
        if self.ok:
            return ""
        return ERR_CODES.get(self.err_no, self.raw.get('err_str', '未知错误'))

    @property
    def pic_str(self) -> str:
        return str(self.raw.get('pic_str', '')).strip()

    @property
    def pic_id(self) -> str:
        return str(self.raw.get('pic_id', ''))

    def to_points(self) -> list[tuple[int, int]]:
        """把 pic_str="x1,y1|x2,y2|..." 解析为点列表"""
        pts = []
        if not self.pic_str:
            return pts
        for seg in self.pic_str.split('|'):
            seg = seg.strip()
            if not seg:
                continue
            parts = re.split(r'[,，]', seg)
            if len(parts) >= 2:
                try:
                    pts.append((int(float(parts[0])), int(float(parts[1]))))
                except ValueError:
                    continue
        return pts

    def to_rects(self) -> list[tuple[int, int, int, int]]:
        """9900 类型: pic_str="x1,y1,x2,y2|..." → 矩形列表"""
        rects = []
        if not self.pic_str:
            return rects
        for seg in self.pic_str.split('|'):
            seg = seg.strip()
            if not seg:
                continue
            parts = re.split(r'[,，]', seg)
            if len(parts) >= 4:
                try:
                    rects.append(tuple(int(float(p)) for p in parts[:4]))
                except ValueError:
                    continue
        return rects


# ==========================================
# 三、超级鹰客户端 (支持 bytes / base64 / 文件路径 三种输入)
# ==========================================
class ChaojiyingClient:
    """
    超级鹰 API 客户端
    用法:
        cj = ChaojiyingClient(user='xxx', password='xxx', soft_id='977219')
        或设置环境变量: CHAOJIYING_USER / CHAOJIYING_PASS / CHAOJIYING_SOFT_ID
    """
    BASE_URL = "http://upload.chaojiying.net/Upload"

    def __init__(self, user: str = "", password: str = "", soft_id: str = ""):
        self.user = user or os.environ.get("CHAOJIYING_USER", "")
        self.password = password or os.environ.get("CHAOJIYING_PASS", "")
        self.soft_id = soft_id or os.environ.get("CHAOJIYING_SOFT_ID", "96001")
        if not self.user or not self.password:
            print("[Chaojiying] 警告: 账号/密码未设置, 所有调用都会返回 -1003 错误")
        self._pass_md5 = md5(self.password.encode('utf-8')).hexdigest()
        self.base_params = {
            'user': self.user,
            'pass2': self._pass_md5,
            'softid': self.soft_id,
        }
        self.headers = {
            'Connection': 'Keep-Alive',
            'User-Agent': 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 5.1; Trident/4.0)',
        }
        self._session = requests.Session()

    # ---------- 主接口 ----------
    def post_bytes(self, im_bytes: bytes, codetype: int) -> CJResult:
        """上传图片字节, 返回结构化结果"""
        if not im_bytes:
            return CJResult({'err_no': -2003, 'err_str': '图片为空'})
        params = {'codetype': str(codetype)}
        params.update(self.base_params)
        files = {'userfile': ('captcha.jpg', im_bytes)}
        try:
            r = self._session.post(
                f"{self.BASE_URL}/Processing.php",
                data=params, files=files, headers=self.headers, timeout=30,
            )
            return CJResult(r.json())
        except Exception as e:
            return CJResult({'err_no': -9999, 'err_str': f'网络错误: {e}'})

    def post_base64(self, base64_str: str, codetype: int) -> CJResult:
        """上传 base64 编码图片 (某些截图 API 直接返回 base64)"""
        if not base64_str:
            return CJResult({'err_no': -2003, 'err_str': '图片为空'})
        params = {
            'codetype': str(codetype),
            'file_base64': base64_str,
        }
        params.update(self.base_params)
        try:
            r = self._session.post(
                f"{self.BASE_URL}/Processing.php",
                data=params, headers=self.headers, timeout=30,
            )
            return CJResult(r.json())
        except Exception as e:
            return CJResult({'err_no': -9999, 'err_str': f'网络错误: {e}'})

    def post_file(self, path: str, codetype: int) -> CJResult:
        """从本地文件上传 (方便测试)"""
        if not os.path.exists(path):
            return CJResult({'err_no': -2003, 'err_str': f'文件不存在: {path}'})
        with open(path, 'rb') as f:
            return self.post_bytes(f.read(), codetype)

    def report_error(self, pic_id: str) -> CJResult:
        """识别错误时申诉, 成功后返还题分"""
        if not pic_id:
            return CJResult({'err_no': -1, 'err_str': 'pic_id 为空'})
        params = {'id': pic_id}
        params.update(self.base_params)
        try:
            r = self._session.post(
                f"{self.BASE_URL}/ReportError.php",
                data=params, headers=self.headers, timeout=15,
            )
            return CJResult(r.json())
        except Exception as e:
            return CJResult({'err_no': -9999, 'err_str': f'网络错误: {e}'})

    # ---------- 便捷封装 ----------
    def recognize_text(self, im_bytes: bytes, codetype: int = CODE.ALNUM_4) -> str:
        """简单文本识别 (数字/字母/汉字), 识别失败返回空串"""
        r = self.post_bytes(im_bytes, codetype)
        return r.pic_str if r.ok else ""

    def locate_points(self, im_bytes: bytes, codetype: int,
                      offset_xy: tuple[int, int] = (0, 0)
                      ) -> list[tuple[int, int]]:
        """
        坐标定位型识别, 返回已减去偏移量的真实坐标
        :param offset_xy: 合成图中搜索区左上角相对于合成图原点的 (dx, dy), 来自 build_composite
        """
        r = self.post_bytes(im_bytes, codetype)
        if not r.ok:
            return []
        dx, dy = offset_xy
        return [(x - dx, y - dy) for x, y in r.to_points()], r.pic_id  # 兼容返回 pic_id

    def locate_gap_two_points(self, im_bytes: bytes) -> tuple[Optional[tuple[int, int]],
                                                              Optional[tuple[int, int]],
                                                              str]:
        """
        滑块专用: 识别一张图里两个图形块 (拼图 + 缺口), 返回 (拼图中心, 缺口中心, pic_id)
        差值 x2-x1 就是滑块需要拖的距离 (注意 dpr 缩放)
        """
        r = self.post_bytes(im_bytes, CODE.GAP_TWO_CENTER)
        if not r.ok:
            return None, None, r.pic_id
        pts = r.to_points()
        if len(pts) < 2:
            return None, None, r.pic_id
        # 按 x 从小到大排: 第一个是拼图块, 第二个是缺口
        pts.sort(key=lambda p: p[0])
        return pts[0], pts[1], r.pic_id


# ==========================================
# 四、图片拼接工具 (从 captcha_solver._build_composite 提炼为纯函数, 通用)
# ==========================================
def build_composite(hint_imgs: Iterable[bytes],
                    search_img: bytes,
                    hint_height: int = 36,
                    pad: int = 8,
                    margin: int = 10,
                    sep_height: int = 2,
                    bg_color: tuple[int, int, int] = (255, 255, 255),
                    sep_color: tuple[int, int, int] = (220, 220, 220),
                    ) -> tuple[Image.Image, int, int]:
    """
    把"提示图标"和"搜索大图"拼成一张超级鹰能看懂的图。
    布局:
        [margin 边距]
        [  提示图 1] [pad] [提示图 2] [pad] ...    ← 全部缩放到 hint_height, 水平居中
        [margin 边距]
        [---- sep_height 像素分隔线 (sep_color) ----]
        [           搜索大图 (水平居中)            ]

    :returns (合成PIL图, 搜索区左上角偏移x, 搜索区左上角偏移y)
             后两个数字用于: 真实坐标 = 超级鹰返回坐标 - (x, y)
    """
    resized_hints = []
    for raw in hint_imgs:
        if not raw:
            continue
        try:
            im = Image.open(io.BytesIO(raw)).convert('RGBA')
            if im.height <= 0:
                continue
            ratio = hint_height / im.height
            new_w = max(int(im.width * ratio), 1)
            im = im.resize((new_w, hint_height), Image.LANCZOS)
            resized_hints.append(im)
        except Exception:
            continue

    if not search_img:
        raise ValueError("search_img 不能为空")

    search_pil = Image.open(io.BytesIO(search_img)).convert('RGB')

    if not resized_hints:
        # 没有提示图, 直接返回原图 + 偏移量 0
        return search_pil, 0, 0

    # 画布宽 = max(提示总宽 + 边距, 搜索区宽)
    hints_total_w = sum(im.width for im in resized_hints) + pad * (len(resized_hints) - 1) + margin * 2
    canvas_w = max(hints_total_w, search_pil.width)
    hint_area_h = margin * 2 + hint_height   # 上下各 margin
    sep_area_h = sep_height
    canvas_h = hint_area_h + sep_area_h + search_pil.height

    canvas = Image.new('RGB', (canvas_w, canvas_h), bg_color)

    # 粘贴提示图 (水平居中)
    total_hints_w = sum(im.width for im in resized_hints) + pad * (len(resized_hints) - 1)
    x = (canvas_w - total_hints_w) // 2
    y = margin
    for im in resized_hints:
        bg = Image.new('RGB', im.size, bg_color)
        if im.mode == 'RGBA':
            bg.paste(im, mask=im.split()[3])
        else:
            bg.paste(im)
        canvas.paste(bg, (x, y))
        x += im.width + pad

    # 分隔线 (逐像素写兼容所有 PIL 版本)
    sep_y0 = hint_area_h
    for px in range(canvas_w):
        for py in range(sep_y0, sep_y0 + sep_height):
            canvas.putpixel((px, py), sep_color)

    # 粘贴搜索大图 (水平居中)
    search_x = (canvas_w - search_pil.width) // 2
    search_y = hint_area_h + sep_height
    canvas.paste(search_pil, (search_x, search_y))
    return canvas, search_x, search_y


def image_to_bytes(im: Image.Image, fmt: str = 'JPEG', quality: int = 90) -> bytes:
    """PIL 图转 bytes, 方便传给超级鹰"""
    buf = io.BytesIO()
    im.save(buf, format=fmt, quality=quality)
    return buf.getvalue()


# ==========================================
# 五、CDP 点击工具 (Playwright + Selenium 双版本)
# ==========================================
def cdp_click_playwright(page, x: int, y: int, delay_after: float = None) -> None:
    """
    Playwright 版 CDP 底层点击 (模拟真人 move→press→release, 带随机延迟)
    传入 playwright sync/async page 对象即可, page.run_cdp 是其内部 API
    """
    if delay_after is None:
        delay_after = random.uniform(0.35, 0.7)
    try:
        # 移动 → 按下 → 释放, 三段式, 每段都有小延迟
        page.run_cdp('Input.dispatchMouseEvent',
                     type='mouseMoved', x=x, y=y, button='left', clickCount=0)
        time.sleep(0.03)
        page.run_cdp('Input.dispatchMouseEvent',
                     type='mousePressed', x=x, y=y, button='left', clickCount=1)
        time.sleep(random.uniform(0.06, 0.13))
        page.run_cdp('Input.dispatchMouseEvent',
                     type='mouseReleased', x=x, y=y, button='left', clickCount=1)
        time.sleep(delay_after)
    except Exception:
        pass


def cdp_click_selenium(driver, x: int, y: int, delay_after: float = None) -> None:
    """
    Selenium 版 CDP 底层点击 (driver.execute_cdp_cmd 是 Selenium 4 自带接口)
    坐标为 viewport 坐标 (相对于浏览器可视区左上角, 非页面坐标)
    """
    if delay_after is None:
        delay_after = random.uniform(0.35, 0.7)
    try:
        driver.execute_cdp_cmd('Input.dispatchMouseEvent', {
            'type': 'mouseMoved', 'x': x, 'y': y, 'button': 'left', 'clickCount': 0,
        })
        time.sleep(0.03)
        driver.execute_cdp_cmd('Input.dispatchMouseEvent', {
            'type': 'mousePressed', 'x': x, 'y': y, 'button': 'left', 'clickCount': 1,
        })
        time.sleep(random.uniform(0.06, 0.13))
        driver.execute_cdp_cmd('Input.dispatchMouseEvent', {
            'type': 'mouseReleased', 'x': x, 'y': y, 'button': 'left', 'clickCount': 1,
        })
        time.sleep(delay_after)
    except Exception:
        pass


# ==========================================
# 六、极验点选破解 (通用版, 用 Playwright, 从你的 captcha_solver 提炼并解耦)
# ==========================================
def crack_geetest(cj: ChaojiyingClient,
                  page,
                  max_retries: int = 3,
                  codetype_for_4dot: int = CODE.DOT_5,
                  codetype_for_order: int = CODE.DOT_WORD_ORDER,
                  log_fn=print,
                  ) -> bool:
    """
    极验点选破解通用版 (贝壳/链家等复用了极验的都能用)
    注意: 浏览器中了反爬后弹窗才会出现, 请确保调用时浏览器已经停在弹窗页或验证按钮可见

    :param cj: 已经初始化好的 ChaojiyingClient
    :param page: Playwright page 对象 (必须支持 run_js / run_cdp)
    :return: True=通过, False=失败
    """
    for attempt in range(max_retries):
        # 1) 检查验证码是否存在
        url = (page.url or '').lower()
        has_captcha = any(k in url for k in ['hip.ke.com/captcha', 'captcha.lianjia.com',
                                             'geetest', 'captcha'])
        has_btn = _js(page, "return !!document.querySelector('[class*=\"geetest_btn_click\"]');"
                            " || !!document.querySelector('[class*=\"geetest_holder\"]');")
        if not has_captcha and not has_btn:
            return True
        log_fn(f"[Geetest] 第 {attempt + 1}/{max_retries} 次尝试")

        # 2) 检查弹窗 / 触发按钮
        info = json.loads(_js(page, """
            var d = {};
            var bg = document.querySelector('[class*="geetest_bg"]');
            if(bg){
                var r = bg.getBoundingClientRect();
                d.bg_x=Math.round(r.x); d.bg_y=Math.round(r.y);
                d.bg_w=Math.round(r.width); d.bg_h=Math.round(r.height);
                var s = (bg.getAttribute('style')||'').replace(/&quot;/g,'\"');
                var m = s.match(/url\\([\"']?([^\"')]+)[\"']?\\)/);
                d.bg_url = m?m[1]:'';
            } else { d.bg_w=0; d.bg_h=0; d.bg_url=''; d.bg_x=0; d.bg_y=0; }
            var btn = document.querySelector('[class*="geetest_btn_click"]');
            if(!btn) btn = document.querySelector('[class*="geetest_holder"]');
            if(btn){ var r=btn.getBoundingClientRect();
                d.btn_cx=Math.round(r.x+r.width/2); d.btn_cy=Math.round(r.y+r.height/2); }
            return JSON.stringify(d);
        """)) if _js(page, "return 1") else {'bg_w': 0, 'bg_h': 0, 'bg_url': '', 'bg_x': 0, 'bg_y': 0}

        # 3) 弹窗没出就触发按钮
        if info.get('bg_w', 0) < 10:
            cx, cy = info.get('btn_cx', 0), info.get('btn_cy', 0)
            if cx <= 0:
                _refresh(page)
                time.sleep(1.5)
                continue
            log_fn(f"  触发验证弹窗, 点击 ({cx},{cy})")
            cdp_click_playwright(page, cx, cy, delay_after=0.3)
            # 等 bg 出尺寸
            for _ in range(40):
                time.sleep(0.5)
                info = json.loads(_js(page, """
                    var bg = document.querySelector('[class*="geetest_bg"]');
                    if(!bg) return '{}';
                    var r=bg.getBoundingClientRect();
                    var s=(bg.getAttribute('style')||'').replace(/&quot;/g,'\"');
                    var m=s.match(/url\\([\"']?([^\"')]+)[\"']?\\)/);
                    return JSON.stringify({bg_x:Math.round(r.x),bg_y:Math.round(r.y),
                        bg_w:Math.round(r.width),bg_h:Math.round(r.height),bg_url:m?m[1]:''});
                """))
                if info.get('bg_w', 0) > 10:
                    break
            if info.get('bg_w', 0) < 10:
                log_fn("  弹窗无法加载, 刷新重试")
                _refresh(page)
                time.sleep(1.5)
                continue

        # 4) 抓取提示文字 / 提示图
        extra = json.loads(_js(page, """
            var d = {};
            var tip = document.querySelector('[class*="geetest_text_tips"]');
            d.tip_text = tip ? (tip.textContent||'').trim() : '';
            var ques = document.querySelector('[class*="geetest_ques_tips"]');
            d.hint_urls = [];
            if(ques){
                var imgs = ques.querySelectorAll('img');
                for(var i=0;i<imgs.length;i++) if(imgs[i].src) d.hint_urls.push(imgs[i].src);
            }
            return JSON.stringify(d);
        """))
        info.update(extra or {})
        log_fn(f"  提示: {info.get('tip_text','')!r}, 提示图 {len(info.get('hint_urls',[]))} 张")

        # 5) 下载提示图 + 大图
        hints, bg_data = [], None
        for u in info.get('hint_urls', []):
            d = _dl(u)
            if d: hints.append(d)
        bg_url = info.get('bg_url') or ''
        if bg_url.startswith('//'):
            bg_url = 'https:' + bg_url
        bg_data = _dl(bg_url) if bg_url else None
        if not bg_data:
            log_fn("  下载大图失败, 刷新重试")
            _refresh(page)
            time.sleep(1.5)
            continue
        log_fn(f"  下载完成: {len(hints)} 提示图 + 大图 {len(bg_data)}B")

        # 6) 拼接 → 超级鹰识别
        composite, ox, oy = build_composite(hints, bg_data)
        codetype = codetype_for_order if '语序' in info.get('tip_text', '') else codetype_for_4dot
        result = cj.post_bytes(image_to_bytes(composite), codetype)
        if not result.ok:
            log_fn(f"  超级鹰返回错误: {result.err_msg}")
            _refresh(page)
            time.sleep(1.5)
            continue
        points = [(x - ox, y - oy) for x, y in result.to_points()]
        log_fn(f"  原始: {result.pic_str}  偏移修正后: {points}")
        if not points:
            log_fn("  解析坐标为空, 刷新重试")
            cj.report_error(result.pic_id)
            _refresh(page)
            time.sleep(1.5)
            continue

        # 7) 依次点击
        vp_x, vp_y = int(info['bg_x']), int(info['bg_y'])
        for i, (x, y) in enumerate(points):
            cdp_click_playwright(page, vp_x + x, vp_y + y,
                                 delay_after=random.uniform(0.35, 0.7))
            log_fn(f"  点击 #{i+1}: 大图({x},{y}) → 视口({vp_x+x},{vp_y+y})")

        # 8) 提交
        passed = False
        for _ in range(5):
            _js(page, """
                var b = document.querySelector('[class*="geetest_submit"]');
                if (b && !b.classList.contains('geetest_disable')) b.click();
            """)
            time.sleep(0.8)
            gone = _js(page, """
                var p = document.querySelector('[class*="geetest_popup_wrap"]');
                if(!p) return true;
                var r = p.getBoundingClientRect();
                return r.width<10 || window.getComputedStyle(p).display==='none';
            """)
            if gone:
                passed = True
                break
        if not passed:
            cj.report_error(result.pic_id)
            log_fn("  未通过, 申诉退费并刷新重试")
            continue
        time.sleep(random.uniform(1.5, 2.5))
        return True
    # 重试耗尽
    log_fn(f"[Geetest] {max_retries} 次全部失败")
    time.sleep(30)
    return False


# ---------- 内部辅助 (仅极验破解用) ----------
import json as _json_mod
json = _json_mod  # 给上面的 crack_geetest 用


def _js(page, code):
    """Playwright 版 run_js, 失败返回 None"""
    try:
        return page.run_js(code)
    except Exception:
        return None


def _refresh(page):
    """点验证码刷新按钮 (换一张图)"""
    try:
        page.run_js("""
            var r = document.querySelector('[class*="geetest_refresh"]');
            if (r) r.click();
        """)
    except Exception:
        pass


def _dl(url, referer='https://www.bilibili.com/'):
    """通用图片下载 (带重试/超时/UA), 返回 bytes 或 None"""
    if not url:
        return None
    if url.startswith('//'):
        url = 'https:' + url
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


# ==========================================
# 七、命令行自测: python chaojiying_helper.py 本地图片.jpg 1902
# ==========================================
if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("用法:")
        print("  测试文本识别:   python chaojiying_helper.py <图片路径> [codetype 默认1902]")
        print("  测试滑块定位:   python chaojiying_helper.py <图片路径> 9902")
        print("  测 build_composite: python chaojiying_helper.py --demo-composite <hint1> <hint2> <search>")
        print("\n请先设置环境变量:")
        print("  $env:CHAOJIYING_USER = '你的账号'")
        print("  $env:CHAOJIYING_PASS = '你的密码'")
        print("  $env:CHAOJIYING_SOFT_ID = '96001'")
        sys.exit(0)

    if sys.argv[1] == '--demo-composite':
        # 测试 build_composite: 用三张图拼接
        paths = sys.argv[2:]
        if len(paths) < 2:
            print("需至少 2 张图: hint1 hint2 ... search_bg")
            sys.exit(1)
        hint_paths, search_path = paths[:-1], paths[-1]
        hints_b = [open(p, 'rb').read() for p in hint_paths]
        search_b = open(search_path, 'rb').read()
        composite, ox, oy = build_composite(hints_b, search_b)
        composite.save('_composite_demo.jpg', quality=90)
        print(f"合成图已保存 _composite_demo.jpg ({composite.width}x{composite.height})")
        print(f"搜索区偏移量: offset = ({ox}, {oy})")
        print("后续超级鹰返回 (x, y) 时, 真实坐标 = ({x-ox}, {y-oy})")
        sys.exit(0)

    path = sys.argv[1]
    codetype = int(sys.argv[2]) if len(sys.argv) > 2 else CODE.ALNUM_4
    cj = ChaojiyingClient()
    print(f"上传 {path}  codetype={codetype}")
    r = cj.post_file(path, codetype)
    print(f"返回: {r.raw}")
    if r.ok:
        print(f"✔ 识别成功: pic_str = {r.pic_str!r}")
        pts = r.to_points()
        if pts:
            print(f"  解析点坐标: {pts}")
        rects = r.to_rects()
        if rects:
            print(f"  解析矩形: {rects}")
    else:
        print(f"✘ 失败 err_no={r.err_no}: {r.err_msg}")
