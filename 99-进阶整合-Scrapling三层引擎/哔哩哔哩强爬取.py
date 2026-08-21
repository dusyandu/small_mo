# -*- coding: utf-8 -*-
"""
哔哩哔哩强爬取  ——  基于 Scrapling 三层引擎的 GUI 视频下载器
=============================================================

三层引擎（自动降级，用户也可手动强制选某一层）
---------------------------------------------------
  ⚡ 引擎 1 · Fetcher (纯 HTTP, curl_cffi/httpx)
        => 最快 (~150ms)，直接打 B 站 view / playurl 接口

  🥷 引擎 2 · StealthyFetcher (Patchright + Chromium 隐形浏览器)
        => 浏览器级别指纹 + 反爬四件套（block_ads / block_webrtc /
           hide_canvas / dns_over_https / allow_webgl / google_search）
        => 引擎 1 遇 403/风控/被封时自动降级到它拿首屏真实 Cookie 再打接口

  🧠 引擎 3 · Adaptive Parser
        => Fetcher/StealthyFetcher 解析 DOM 时启用 auto_save 保存签名；
           下次即使 CSS 选择器写错 / B 站改版，adaptive=True 也能自动找回。

DASH 下载
---------
  - 音视频流并发下载（线程池，带进度回调）
  - ffmpeg -c copy 无损秒级合并（自动找 ffmpeg / imageio-ffmpeg / %FFMPEG_PATH%）

GUI
---
  tkinter.ttk：①输入/引擎  ②引擎参数  ③视频详情+清晰度  ④下载控制  ⑤进度  ⑥日志

依赖安装
--------
    pip install scrapling curl_cffi httpx anyio patchright browserforge msgspec playwright requests
    patchright install chromium       # 首次需要，Patchright 自带 patched Chromium
    # (可选) pip install imageio-ffmpeg   # 不想单独装 ffmpeg 就装它自带二进制

运行
----
    python "哔哩哔哩强爬取.py"
"""

from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
import tkinter as tk
from typing import Any, Callable


# ========================= 常量 =========================
APP_TITLE = "哔哩哔哩强爬取 · Scrapling 三层引擎"

DEFAULT_BVID = "BV1GJ411x7h7"            # B 站官方宣传片，稳定不失效

API_VIEW    = "https://api.bilibili.com/x/web-interface/view"
API_PLAYURL = "https://api.bilibili.com/x/player/playurl"

QUALITY_MAP = {
    127: "8K 超高清", 126: "杜比视界", 120: "4K 超清", 116: "1080P 60帧",
    112: "1080P 高码率", 80: "1080P 高清", 74: "720P 60帧", 64: "720P 高清",
    32: "480P 清晰", 16: "360P 流畅",
}

CODEC_MAP = {
    7: "H.264/AVC", 12: "H.265/HEVC", 13: "AV1",
}

# GUI 里的 4 种引擎模式
ENGINE_OPTIONS = [
    "🎯 自动三层降级  (推荐：快速 → 隐形 → 自适应)",
    "⚡ 引擎 1 · 快速 (Fetcher HTTP)",
    "🥷 引擎 2 · 隐形浏览器 (StealthyFetcher)",
    "🧠 引擎 3 · 自适应 + 隐形 (auto_save/召回)",
]
ENGINE_VALUES = ("auto", "fast", "stealth", "adaptive")


# ========================= 工具 =========================
def extract_bvid(text: str) -> str:
    m = re.search(r"(BV[0-9A-Za-z]{10})", text)
    if not m:
        raise ValueError(f"无法从输入中提取 BV 号: {text!r}")
    return m.group(1)


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip()
    name = name.rstrip(". ")
    return name or "bilibili_video"


def find_ffmpeg() -> str:
    from shutil import which
    p = which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg
        p = imageio_ffmpeg.get_ffmpeg_exe()
        if p and os.path.exists(p):
            return p
    except Exception:
        pass
    p = os.environ.get("FFMPEG_PATH", "").strip()
    if p and os.path.exists(p):
        return p
    return ""


def merge_av(video_path: str, audio_path: str, out_path: str) -> None:
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError(
            "未找到 ffmpeg，任选其一：\n"
            "  1) 安装 ffmpeg 并加入 PATH\n"
            "  2) pip install imageio-ffmpeg（自带二进制）\n"
            "  3) 设置环境变量 FFMPEG_PATH 指向 ffmpeg.exe"
        )
    cmd = [ffmpeg, "-y", "-i", video_path, "-i", audio_path,
           "-c", "copy", "-movflags", "+faststart", out_path]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except FileNotFoundError:
        raise RuntimeError(f"ffmpeg 路径无效: {ffmpeg}")
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode("utf-8", "ignore")[-600:] if e.stderr else ""
        raise RuntimeError(f"ffmpeg 合并失败:\n{err}")


# ========================= 消息总线 (线程→UI) =========================
class UIMsg:
    """工作线程通过该对象把消息丢进 tkinter 主线程（queue + after 轮询）。"""

    LOG = "LOG"
    STATUS = "STATUS"
    INFO = "INFO"          # 更新视频详情 UI
    QUALITY = "QUALITY"    # 更新清晰度下拉
    PROGRESS = "PROGRESS"  # (label, done, total)
    DONE = "DONE"          # bool_ok, msg
    BTN = "BTN"            # button_name, state

    def __init__(self, q: queue.Queue):
        self.q = q

    def log(self, msg: str): self.q.put((self.LOG, msg))
    def status(self, text: str, color: str = "gray"): self.q.put((self.STATUS, (text, color)))
    def info(self, title: str, up: str, duration: int, extra: str = ""):
        self.q.put((self.INFO, (title, up, duration, extra)))
    def quality(self, options: list, current: int = 0): self.q.put((self.QUALITY, (options, current)))
    def progress(self, label: str, done: int, total: int):
        pct = (done * 100 / total) if total else 0
        self.q.put((self.PROGRESS, (label, done, total, pct)))
    def done(self, ok: bool, msg: str): self.q.put((self.DONE, (ok, msg)))
    def btn(self, name: str, state: str): self.q.put((self.BTN, (name, state)))


# ================================================================
#  引擎层：Fetcher / StealthyFetcher + 接口封装
# ================================================================
class EngineError(RuntimeError):
    pass


def _bili_api_headers(cookie: str | None) -> dict:
    h = {
        "Referer": "https://www.bilibili.com/",
        "Origin": "https://www.bilibili.com",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
    }
    if cookie:
        h["Cookie"] = cookie
    return h


def _parse_json_response(resp) -> dict:
    """容错：Scrapling Response.json 在 v0.4.14 是 method 必须加括号。"""
    if callable(resp.json):
        payload = resp.json()
    else:
        payload = resp.json
    if not isinstance(payload, dict):
        raise EngineError(f"响应非 JSON dict: status={resp.status}")
    code = payload.get("code")
    if code != 0:
        raise EngineError(f"接口 code={code!r} message={payload.get('message')!r}  status={resp.status}")
    return payload.get("data") or {}


def engine_fast_get_video_info(bvid: str, cookie: str | None, log: Callable[[str], None]) -> dict:
    """⚡ 引擎 1：Fetcher 纯 HTTP 打 view 接口。"""
    from scrapling.fetchers.requests import Fetcher
    Fetcher.configure(adaptive=True)
    r = Fetcher.get(
        API_VIEW,
        params={"bvid": bvid},
        extra_headers=_bili_api_headers(cookie),
        google_search=False,
        timeout=20_000,
        follow_redirects=True,
    )
    log(f"  [⚡ Fetcher] GET view status={r.status}")
    if r.status != 200:
        raise EngineError(f"Fetcher HTTP {r.status}")
    data = _parse_json_response(r)
    return {
        "bvid": bvid,
        "cid": data["cid"],
        "title": data["title"],
        "up": (data.get("owner") or {}).get("name", ""),
        "duration": data.get("duration", 0),
        "stat": data.get("stat", {}) or {},
        "_engine": "Fetcher",
    }


def engine_stealth_get_video_page(bvid: str, cookie: str | None, opts: dict, log: Callable[[str], None]):
    """🥷 引擎 2：StealthyFetcher 打开视频详情页（返回 page 响应对象，里面带真实 Cookie + DOM）。"""
    from scrapling.fetchers.stealth_chrome import StealthyFetcher
    StealthyFetcher.configure(adaptive=True)
    kw = dict(
        headless=not opts.get("headful", False),
        block_ads=opts.get("block_ads", True),
        block_webrtc=opts.get("block_webrtc", True),
        hide_canvas=opts.get("hide_canvas", True),
        dns_over_https=opts.get("dns_over_https", True),
        allow_webgl=True,
        disable_resources=False,
        google_search=True,
        network_idle=True,
        wait_selector="h1.video-title, .video-title, h1",
        wait_selector_state="visible",
        wait=opts.get("wait_ms", 2000),
        timeout=opts.get("timeout_ms", 90_000),
        retries=opts.get("retries", 2),
    )
    proxy = (opts.get("proxy") or "").strip()
    if proxy:
        kw["proxy"] = proxy
    if cookie:
        kw.setdefault("extra_headers", {})
        kw["extra_headers"]["Cookie"] = cookie

    page = StealthyFetcher.fetch(f"https://www.bilibili.com/video/{bvid}", **kw)
    log(f"  [🥷 StealthyFetcher] 页面加载完成 status={page.status}  headless={kw['headless']}")
    if page.status not in (200, 301, 302, 304):
        raise EngineError(f"StealthyFetcher HTTP {page.status}")
    return page


def _page_extract_meta(page) -> dict:
    """从 StealthyFetcher 的 page 响应里提取 title/up/desc (带 auto_save 写签名)。

    返回 {title, up, desc}，不保证每项都有。
    """
    def _text(sel: str, **kw) -> str:
        try:
            nodes = page.css(sel, **kw)
            if not nodes:
                return ""
            for n in nodes:
                t = (getattr(n, "text", None) or "").strip()
                if t:
                    return t
        except Exception:
            return ""
        return ""

    def _attr(sel: str, attr: str) -> str:
        try:
            nodes = page.css(sel)
            if not nodes:
                return ""
            for n in nodes:
                d = getattr(n, "attrib", None) or {}
                if d.get(attr):
                    return d[attr]
        except Exception:
            return ""
        return ""

    title = ""
    for sel, ident in (("h1.video-title", "title__h1video-title"),
                       (".video-title", "title__video-title"), ("h1", "title__h1")):
        t = _text(sel, auto_save=True, identifier=ident)
        if t:
            title = t
            break
    if not title:
        title = _attr('meta[property="og:title"]', "content")
    if not title:
        t = _text("title")
        if t:
            title = t.split("_哔哩哔哩_bilibili")[0].split("_bilibili")[0]

    up = ""
    for sel, ident in (('a[class*="up-name"]', "up__aupname"),
                       (".up-name__text", "up__upnametext"), (".username", "up__username")):
        u = _text(sel, auto_save=True, identifier=ident)
        if u:
            up = u
            break

    desc = ""
    t = _text('meta[property="og:description"]::attr(content)',
              auto_save=True, identifier="desc_og")
    if t:
        desc = t
    else:
        desc = _attr('meta[property="og:description"]', "content")
    if not desc:
        for sel, ident in ((".desc-info", "desc_descinfo"),
                           ("#v_desc", "desc_vdesc")):
            t = _text(sel, auto_save=True, identifier=ident)
            if t:
                desc = t
                break

    return {"title": title, "up": up, "desc": desc[:500]}


def engine_fast_get_playurl(bvid: str, cid: int, cookie: str | None, log: Callable[[str], None]) -> dict:
    """⚡ 快速引擎：打 playurl 接口，返回 DASH 的 {video: [...], audio: [...]}。"""
    from scrapling.fetchers.requests import Fetcher
    r = Fetcher.get(
        API_PLAYURL,
        params={"bvid": bvid, "cid": cid, "qn": 127, "fnval": 4048, "fnver": 0, "fourk": 1},
        extra_headers=_bili_api_headers(cookie),
        google_search=False,
        timeout=20_000,
        follow_redirects=True,
    )
    log(f"  [⚡ Fetcher] GET playurl status={r.status}")
    if r.status != 200:
        raise EngineError(f"Fetcher playurl HTTP {r.status}")
    data = _parse_json_response(r)
    if "dash" not in data:
        raise EngineError("该视频不支持 DASH 流 (老视频仅有 mp4 格式，暂未实现)")
    return data["dash"]


# ========================= 下载 =========================
def _pick_video_stream(video_streams: list, qn: int) -> dict:
    cands = [v for v in video_streams if v.get("id") == qn]
    if not cands:
        raise RuntimeError(f"未找到清晰度 qn={qn} 的视频流")
    # AVC 最兼容 → AV1 文件最小 → HEVC 画质好
    for codec in (7, 13, 12):
        for v in cands:
            if v.get("codecid", 0) == codec:
                return v
    return cands[0]


def _pick_audio_stream(audio_streams: list) -> dict:
    if not audio_streams:
        raise RuntimeError("无可用音频流")
    return max(audio_streams, key=lambda a: a.get("id", 0))


def _stream_base_url(stream: dict) -> str:
    return stream.get("baseUrl") or stream.get("base_url") or ""


def stream_download_with_requests(url: str, dst: str, label: str,
                                   cookie: str | None,
                                   progress_cb, stop_flag,
                                   log: Callable[[str], None]) -> None:
    """下载 DASH 分片到 dst，B 站 CDN 需要带 Referer + Range。

    这里直接用 requests.Session（与下载分片的行为最匹配、最稳）。
    """
    import requests as _requests
    s = _requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/150.0.0.0 Safari/537.36",
        "Referer": "https://www.bilibili.com/",
    })
    if cookie:
        s.headers["Cookie"] = cookie

    last_cb_ts = 0.0
    with s.get(url, stream=True, timeout=(10, 90)) as r:
        if r.status_code not in (200, 206):
            raise RuntimeError(f"下载 {label} 失败 HTTP {r.status_code}")
        total = int(r.headers.get("Content-Length", 0))
        done = 0
        log(f"  ↓ {label}: start  total={total/1024/1024:.2f}MB")
        with open(dst, "wb") as f:
            for chunk in r.iter_content(chunk_size=64 * 1024):
                if stop_flag and stop_flag.is_set():
                    raise RuntimeError("用户取消下载")
                if chunk:
                    f.write(chunk)
                    done += len(chunk)
                    now = time.time()
                    if progress_cb and (now - last_cb_ts > 0.15 or (total and done >= total)):
                        progress_cb(label, done, total)
                        last_cb_ts = now
        if progress_cb:
            progress_cb(label, done, total)


# ================================================================
#  业务链路：三层引擎降级 → 解析 → 下载 → 合并
# ================================================================
def run_pipeline(bvid: str, cookie: str | None, engine_key: str,
                 engine_opts: dict, out_dir: str, qn_choice_cb,
                 ui: UIMsg, stop_flag: threading.Event) -> None:
    """在后台线程里执行完整链路。

    qn_choice_cb() 会在清晰度列表准备好之后调用，阻塞等待用户选完清晰度再下载。
    """
    log = ui.log
    log(f"▶ 开始处理 BV={bvid}  engine={engine_key!r}  out_dir={out_dir}")

    # -------- Step 1: 拿视频基础信息（三层降级） --------
    ui.status("正在解析（三层引擎降级）…", "blue")
    info: dict = {}
    page = None
    engines_tried = []

    engine_order = []
    if engine_key == "fast":
        engine_order = ["fast"]
    elif engine_key == "stealth":
        engine_order = ["stealth"]
    elif engine_key == "adaptive":
        engine_order = ["adaptive"]  # = stealth + auto_save 写签名
    else:  # auto
        engine_order = ["fast", "stealth"]

    for eng in engine_order:
        if stop_flag.is_set():
            ui.done(False, "已取消")
            return
        engines_tried.append(eng)
        try:
            if eng == "fast":
                info = engine_fast_get_video_info(bvid, cookie, log)
                break
            if eng in ("stealth", "adaptive"):
                page = engine_stealth_get_video_page(bvid, cookie, engine_opts, log)
                meta = _page_extract_meta(page)
                # 隐形浏览器已经拿到真实 HTML + Cookie，但 DASH 地址仍走 API 最快；
                # 从 page 上拼一份 info（cid/bvid 靠 API 拿，title/up 从页面拿）
                try:
                    info = engine_fast_get_video_info(bvid, cookie, log)
                except EngineError as e:
                    # 如果 API 拿不到，至少先给页面能读到的内容
                    log(f"  [!] Fetcher 仍失败 ({e})，退化为只用页面元数据")
                    info = {
                        "bvid": bvid,
                        "cid": 0,
                        "title": meta.get("title", ""),
                        "up": meta.get("up", ""),
                        "duration": 0,
                        "stat": {},
                        "_engine": "StealthyFetcher",
                    }
                # 用页面提取的字段覆盖（往往更可靠/更直观），同时保留 cid
                info["title"] = meta.get("title") or info.get("title", "")
                info["up"] = meta.get("up") or info.get("up", "")
                info["desc"] = meta.get("desc", "")
                info["_engine"] = "StealthyFetcher" + (" + Adaptive" if eng == "adaptive" else "")
                break
        except Exception as e:
            log(f"  [引擎 {eng!r}] 失败：{type(e).__name__}: {e}")
            info = {}
            page = None

    if not info or not info.get("title"):
        ui.done(False, f"全部引擎失败 (已试 {engines_tried})。请检查 Cookie / 网络 / 代理。")
        return

    # 展示视频信息到 UI
    ui.info(info.get("title", ""), info.get("up", ""), info.get("duration", 0),
            extra=f"引擎: {info.get('_engine','?')}  |  "
                  f"播放={(info.get('stat') or {}).get('view', 0):,}  "
                  f"点赞={(info.get('stat') or {}).get('like', 0):,}")

    # -------- Step 2: 拿 DASH 流列表（playurl） --------
    ui.status("正在获取清晰度列表…", "blue")
    dash = None
    if info.get("cid"):
        for eng in (["fast"] if engine_key == "fast"
                    else ["fast", "stealth_api"] if engine_key == "auto"
                    else ["fast"]):
            try:
                if eng == "fast":
                    dash = engine_fast_get_playurl(bvid, info["cid"], cookie, log)
                    break
            except Exception as e:
                log(f"  [playurl 引擎 {eng!r}] 失败: {type(e).__name__}: {e}")

    if not dash:
        ui.done(False, "无法获取 DASH 播放流（可能需要登录 Cookie 或视频不支持 DASH）")
        return

    videos = dash.get("video", [])
    audios = dash.get("audio", [])
    if not videos:
        ui.done(False, "DASH 返回无视频流")
        return

    qns = sorted({v.get("id", 0) for v in videos}, reverse=True)
    labels = [f"{qn}  {QUALITY_MAP.get(qn, '')}" for qn in qns]
    log(f"  可用清晰度 qn={qns}  labels={labels}")

    # 让主线程填充清晰度下拉，然后阻塞等待用户选择
    chosen_qn: dict = {}
    wait_evt = threading.Event()

    def _set_quality_options():
        ui.quality(labels, 0)
        # 标记 UI 侧"清晰度已就绪"，GUI 会在用户点「开始下载」时设置 chosen_qn["qn"] 并 set wait_evt
        ui.btn("download", tk.NORMAL)
        ui.status("已解析，请选清晰度后点【开始下载】", "green")
    ui.q.put((UIMsg.STATUS, ("已解析，请选清晰度后点【开始下载】", "green")))  # placeholder
    ui.quality(labels, 0)

    # 把 (chosen_qn, wait_evt, qns) 放进一个专用队列，GUI 读到后会接管
    ui.q.put(("_READY_QUALITY", (qns, chosen_qn, wait_evt, info, dash, out_dir)))
    log("  ✔ 清晰度列表已就绪，等待 GUI 用户操作…")

    # 阻塞直到 GUI 侧调用 wait_evt.set() 或停止
    while not wait_evt.is_set() and not stop_flag.is_set():
        time.sleep(0.1)

    if stop_flag.is_set():
        ui.done(False, "已取消")
        return

    qn = chosen_qn.get("qn")
    if qn is None:
        ui.done(False, "未选择清晰度")
        return

    log(f"  已选清晰度 qn={qn} {QUALITY_MAP.get(qn, '')}")

    # -------- Step 3: 选定音视频流 + 并行下载 --------
    v_stream = _pick_video_stream(videos, qn)
    a_stream = _pick_audio_stream(audios)
    v_url = _stream_base_url(v_stream)
    a_url = _stream_base_url(a_stream)
    if not v_url or not a_url:
        ui.done(False, "视频/音频流 URL 为空")
        return

    codec_name = CODEC_MAP.get(v_stream.get("codecid", 0), f"codecid={v_stream.get('codecid')}")
    log(f"  视频流编码: {codec_name}   size≈{int(v_stream.get('size', 0))/1024/1024:.2f}MB")

    os.makedirs(out_dir, exist_ok=True)
    safe_title = sanitize_filename(info["title"])
    out_path = os.path.join(out_dir, f"{safe_title}.mp4")
    tmp_v = out_path + ".video.m4s"
    tmp_a = out_path + ".audio.m4s"

    def _progress(label: str, done: int, total: int):
        ui.progress(label, done, total)

    ui.status("下载中…", "blue")
    ui.btn("fetch", tk.DISABLED)
    ui.btn("download", tk.DISABLED)
    ui.btn("stop", tk.NORMAL)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futs = {
                pool.submit(stream_download_with_requests,
                            v_url, tmp_v, "video", cookie, _progress, stop_flag, log),
                pool.submit(stream_download_with_requests,
                            a_url, tmp_a, "audio", cookie, _progress, stop_flag, log),
            }
            for fut in as_completed(futs):
                fut.result()
    except RuntimeError as e:
        # 清掉半成品
        for p in (tmp_v, tmp_a):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass
        if stop_flag.is_set():
            ui.done(False, f"已取消（{e}）")
        else:
            ui.done(False, f"下载失败：{e}")
        return

    if stop_flag.is_set():
        for p in (tmp_v, tmp_a):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass
        ui.done(False, "已取消")
        return

    # -------- Step 4: ffmpeg 合并 --------
    log("  🎞 ffmpeg -c copy 合并音视频（秒级完成）…")
    ui.status("ffmpeg 合并中…", "blue")
    try:
        merge_av(tmp_v, tmp_a, out_path)
    except Exception as e:
        ui.done(False, str(e))
        return
    finally:
        for p in (tmp_v, tmp_a):
            try:
                if os.path.exists(p):
                    os.remove(p)
            except OSError:
                pass

    log(f"  ✔ 完成: {out_path}")
    ui.status("完成", "green")
    ui.done(True, out_path)


# ================================================================
#  GUI
# ================================================================
class App:
    PAD = {"padx": 8, "pady": 4}

    def __init__(self, root: tk.Tk):
        self.root = root
        root.title(APP_TITLE)
        root.geometry("860x820")
        root.minsize(780, 760)

        # ---- 后台线程相关 ----
        self.stop_flag = threading.Event()
        self.worker: threading.Thread | None = None
        self.msg_q: queue.Queue = queue.Queue()
        self.ui = UIMsg(self.msg_q)

        # ---- 清晰度下载流程 ----
        self._quality_qns: list[int] = []
        self._quality_chosen: dict = {}
        self._quality_wait: threading.Event | None = None
        self._pipeline_info: dict = {}
        self._pipeline_dash: dict = {}
        self._pipeline_out_dir: str = ""

        # ---- 视频详情字段 ----
        self.var_engine = tk.StringVar(value=ENGINE_OPTIONS[0])
        self.var_quality = tk.StringVar(value="")
        self.var_status = tk.StringVar(value="就绪")
        self.var_title = tk.StringVar(value="标题：(未获取)")
        self.var_meta = tk.StringVar(value="UP 主：-    时长：-")
        self.var_extra = tk.StringVar(value="")

        # ---- 引擎参数 Tk 变量 ----
        self.v_headful = tk.BooleanVar(value=False)
        self.v_block_ads = tk.BooleanVar(value=True)
        self.v_block_webrtc = tk.BooleanVar(value=True)
        self.v_hide_canvas = tk.BooleanVar(value=True)
        self.v_dns = tk.BooleanVar(value=True)
        self.v_timeout = tk.IntVar(value=90)       # 秒
        self.v_retries = tk.IntVar(value=2)
        self.v_proxy = tk.StringVar(value="")

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(120, self._drain_queue)

    # -------------------- UI --------------------
    def _build_ui(self):
        root = self.root
        frm = ttk.Frame(root, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        # ---- ① 输入 + 引擎 ----
        box1 = ttk.LabelFrame(frm, text="① 视频 / 引擎", padding=10)
        box1.pack(fill=tk.X, **self.PAD)

        ttk.Label(box1, text="BV 号 / 视频 URL：").grid(row=0, column=0, sticky="W", pady=4)
        self.ent_url = ttk.Entry(box1, width=52)
        self.ent_url.grid(row=0, column=1, columnspan=4, sticky="WE", padx=(6, 0), pady=4)
        self.ent_url.insert(0, DEFAULT_BVID)

        ttk.Label(box1, text="Cookie (选填，大会员清晰度)：").grid(row=1, column=0, sticky="NW", pady=4)
        self.txt_cookie = scrolledtext.ScrolledText(box1, width=52, height=3,
                                                     wrap=tk.WORD, font=("Consolas", 9))
        self.txt_cookie.grid(row=1, column=1, columnspan=4, sticky="WE", padx=(6, 0), pady=4)

        ttk.Label(box1, text="输出目录：").grid(row=2, column=0, sticky="W", pady=4)
        self.ent_outdir = ttk.Entry(box1, width=42)
        self.ent_outdir.insert(0, os.getcwd())
        self.ent_outdir.grid(row=2, column=1, columnspan=2, sticky="WE", padx=(6, 6), pady=4)
        ttk.Button(box1, text="浏览…", command=self._on_browse).grid(row=2, column=3, sticky="WE")
        self.btn_fetch = ttk.Button(box1, text="① 解析视频（三层引擎降级）", command=self._on_fetch)
        self.btn_fetch.grid(row=2, column=4, sticky="WE", padx=(6, 0))

        ttk.Label(box1, text="引擎模式：").grid(row=3, column=0, sticky="W", pady=6)
        self.cb_engine = ttk.Combobox(box1, values=ENGINE_OPTIONS, textvariable=self.var_engine,
                                      state="readonly", width=56)
        self.cb_engine.current(0)
        self.cb_engine.grid(row=3, column=1, columnspan=4, sticky="WE", padx=(6, 0), pady=6)

        box1.columnconfigure(1, weight=1)

        # ---- ② 引擎参数 ----
        box2 = ttk.LabelFrame(frm, text="② 🥷 引擎参数（隐形浏览器 / 自适应时生效）", padding=10)
        box2.pack(fill=tk.X, **self.PAD)

        r1 = ttk.Frame(box2); r1.pack(fill=tk.X, pady=2)
        ttk.Checkbutton(r1, text="有头模式（可见浏览器，方便观察）", variable=self.v_headful).pack(side=tk.LEFT)
        ttk.Checkbutton(r1, text="拦截广告/追踪域名 ~3500 条", variable=self.v_block_ads).pack(side=tk.LEFT, padx=14)
        ttk.Checkbutton(r1, text="Block WebRTC（防 IP 泄漏）", variable=self.v_block_webrtc).pack(side=tk.LEFT)

        r2 = ttk.Frame(box2); r2.pack(fill=tk.X, pady=2)
        ttk.Checkbutton(r2, text="Canvas 指纹加噪", variable=self.v_hide_canvas).pack(side=tk.LEFT)
        ttk.Checkbutton(r2, text="DNS over HTTPS (Cloudflare)", variable=self.v_dns).pack(side=tk.LEFT, padx=14)
        ttk.Label(r2, text="超时(秒)").pack(side=tk.LEFT)
        ttk.Spinbox(r2, from_=10, to=600, increment=5, width=5,
                    textvariable=self.v_timeout).pack(side=tk.LEFT, padx=(4, 14))
        ttk.Label(r2, text="重试次数").pack(side=tk.LEFT)
        ttk.Spinbox(r2, from_=0, to=10, increment=1, width=4,
                    textvariable=self.v_retries).pack(side=tk.LEFT, padx=(4, 14))
        ttk.Label(r2, text="代理 (http://u:p@ip:port)").pack(side=tk.LEFT)
        ttk.Entry(r2, textvariable=self.v_proxy, width=28).pack(side=tk.LEFT, padx=(4, 0))

        # ---- ③ 视频详情 + 清晰度 ----
        box3 = ttk.LabelFrame(frm, text="③ 视频详情", padding=10)
        box3.pack(fill=tk.X, **self.PAD)
        ttk.Label(box3, textvariable=self.var_title, foreground="#222").pack(anchor="w", pady=2)
        ttk.Label(box3, textvariable=self.var_meta, foreground="#555").pack(anchor="w", pady=2)
        ttk.Label(box3, textvariable=self.var_extra, foreground="#888",
                  font=("Segoe UI", 9)).pack(anchor="w", pady=2)

        qrow = ttk.Frame(box3); qrow.pack(fill=tk.X, pady=8)
        ttk.Label(qrow, text="清晰度：").pack(side=tk.LEFT)
        self.cb_quality = ttk.Combobox(qrow, textvariable=self.var_quality,
                                        values=[], width=26, state="readonly")
        self.cb_quality.pack(side=tk.LEFT, padx=(4, 14))
        self.lbl_codec = ttk.Label(qrow, text="编码：-", foreground="#555")
        self.lbl_codec.pack(side=tk.LEFT)
        self.cb_quality.bind("<<ComboboxSelected>>", lambda _e: self._update_codec_label())

        # ---- ④ 下载控制 ----
        ctrl = ttk.Frame(frm); ctrl.pack(fill=tk.X, **self.PAD)
        self.btn_download = ttk.Button(ctrl, text="② 开始下载", command=self._on_download,
                                       state=tk.DISABLED)
        self.btn_download.pack(side=tk.LEFT)
        self.btn_stop = ttk.Button(ctrl, text="停止", command=self._on_stop, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=8)
        ttk.Label(ctrl, textvariable=self.var_status, foreground="gray").pack(side=tk.LEFT, padx=14)

        # ---- ⑤ 进度条 ----
        prog = ttk.LabelFrame(frm, text="⑤ 进度", padding=8); prog.pack(fill=tk.X, **self.PAD)
        self._make_prog(prog, "视频")
        self._make_prog(prog, "音频")
        self._make_prog(prog, "合并")

        # ---- ⑥ 日志 ----
        logs = ttk.LabelFrame(frm, text="⑥ 日志", padding=4); logs.pack(fill=tk.BOTH, expand=True, **self.PAD)
        self.txt_log = scrolledtext.ScrolledText(logs, height=14, wrap=tk.WORD, font=("Consolas", 9))
        self.txt_log.pack(fill=tk.BOTH, expand=True)

    def _make_prog(self, parent, label):
        row = ttk.Frame(parent); row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text=label, width=6).pack(side=tk.LEFT)
        bar = ttk.Progressbar(row, length=480, mode="determinate")
        bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        lbl = ttk.Label(row, text="0%", width=28, anchor="w")
        lbl.pack(side=tk.LEFT)
        setattr(self, f"bar_{label}", bar)
        setattr(self, f"lbl_{label}", lbl)

    # -------------------- 事件 --------------------
    def _on_browse(self):
        d = filedialog.askdirectory(initialdir=self.ent_outdir.get() or os.getcwd())
        if d:
            self.ent_outdir.delete(0, tk.END); self.ent_outdir.insert(0, d)

    def _engine_key(self) -> str:
        idx = ENGINE_OPTIONS.index(self.var_engine.get()) if self.var_engine.get() in ENGINE_OPTIONS else 0
        return ENGINE_VALUES[idx]

    def _engine_opts(self) -> dict:
        return {
            "headful": bool(self.v_headful.get()),
            "block_ads": bool(self.v_block_ads.get()),
            "block_webrtc": bool(self.v_block_webrtc.get()),
            "hide_canvas": bool(self.v_hide_canvas.get()),
            "dns_over_https": bool(self.v_dns.get()),
            "timeout_ms": int(self.v_timeout.get()) * 1000,
            "retries": int(self.v_retries.get()),
            "proxy": self.v_proxy.get(),
            "wait_ms": 2000,
        }

    def _on_fetch(self):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("提示", "当前已有任务进行中")
            return
        url = self.ent_url.get().strip()
        if not url:
            messagebox.showwarning("提示", "请输入 BV 号或视频 URL"); return
        try:
            bvid = extract_bvid(url)
        except Exception as e:
            messagebox.showerror("错误", str(e)); return

        out_dir = self.ent_outdir.get().strip() or os.getcwd()
        cookie = self.txt_cookie.get("1.0", tk.END).strip() or None
        engine_key = self._engine_key()
        opts = self._engine_opts()

        # 重置 UI 状态
        self.var_title.set("标题：(解析中…)")
        self.var_meta.set("UP 主：-    时长：-")
        self.var_extra.set("")
        self.cb_quality["values"] = []; self.var_quality.set("")
        self.lbl_codec.config(text="编码：-")
        for k in ("视频", "音频", "合并"):
            getattr(self, f"bar_{k}")["value"] = 0
            getattr(self, f"lbl_{k}").config(text="0%")
        self.btn_download.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.stop_flag.clear()

        def _qn_choice_cb():
            # unused：我们通过 queue 发 _READY_QUALITY 消息让 GUI 接管
            pass

        self.worker = threading.Thread(
            target=run_pipeline,
            args=(bvid, cookie, engine_key, opts, out_dir, _qn_choice_cb, self.ui, self.stop_flag),
            daemon=True,
        )
        self.worker.start()

    def _on_download(self):
        sel = self.var_quality.get()
        if not sel:
            messagebox.showwarning("提示", "请先选择清晰度")
            return
        if not self._quality_qns or self._quality_wait is None:
            messagebox.showwarning("提示", "清晰度列表尚未就绪，请先点【① 解析视频】")
            return
        try:
            qn = int(sel.split()[0])
        except Exception:
            messagebox.showerror("错误", f"无法解析清晰度: {sel}")
            return
        self._quality_chosen["qn"] = qn
        self._quality_wait.set()

    def _on_stop(self):
        self.stop_flag.set()
        self.set_status("正在停止…", "orange")
        if self._quality_wait is not None:
            self._quality_wait.set()

    def _update_codec_label(self):
        sel = self.var_quality.get()
        if not sel or not self._pipeline_dash:
            return
        try:
            qn = int(sel.split()[0])
        except Exception:
            return
        vs = self._pipeline_dash.get("video", [])
        cands = [v for v in vs if v.get("id") == qn]
        if not cands:
            self.lbl_codec.config(text="编码：-")
            return
        for codec in (7, 13, 12):
            for v in cands:
                if v.get("codecid", 0) == codec:
                    self.lbl_codec.config(text=f"编码：{CODEC_MAP.get(codec, codec)}  "
                                                f"体积≈{int(v.get('size', 0))/1024/1024:.1f}MB")
                    return
        v = cands[0]
        self.lbl_codec.config(text=f"编码：codecid={v.get('codecid')}  "
                                    f"体积≈{int(v.get('size', 0))/1024/1024:.1f}MB")

    # -------------------- 主线程消息泵 --------------------
    def set_status(self, text, color="gray"):
        self.var_status.set(text)
        # ttk Label 没 foreground；我们在 frm 里用了常规 tk.Label 做显示，用 config 改
        # 但这里 ttk.Label 不支持 fg；所以换成遍历父的子控件找到它并统一改
        # 简便做法：给 status 单独用 tk.Label；上面 build_ui 里用了 ttk，实际 fg 不生效
        # 为了稳定：我们用 .txt_log 第一行之外，再在日志里输出即可
        self.txt_log.tag_configure("s", foreground=color)
        pass  # 真正生效的是 _drain_queue 里的 STATUS 分支（下面使用 tk.Label 替代）

    def _set_progress(self, label_key, done, total, pct):
        bar = getattr(self, f"bar_{label_key}")
        lbl = getattr(self, f"lbl_{label_key}")
        bar["value"] = pct
        if total:
            lbl.config(text=f"{pct:.0f}%   {done/1024/1024:.1f}/{total/1024/1024:.1f} MB")
        else:
            lbl.config(text=f"{done/1024/1024:.1f} MB")

    def _drain_queue(self):
        try:
            while True:
                try:
                    msg = self.msg_q.get_nowait()
                except queue.Empty:
                    break
                kind, payload = msg

                if kind == UIMsg.LOG:
                    ts = datetime.now().strftime("%H:%M:%S")
                    self.txt_log.insert(tk.END, f"[{ts}] {payload}\n")
                    self.txt_log.see(tk.END)

                elif kind == UIMsg.STATUS:
                    text, color = payload
                    self.var_status.set(text)
                    # ttk.Label 不支持 fg，所以把颜色写到状态栏下方的标签里
                    self._status_color_hint(color)

                elif kind == UIMsg.INFO:
                    title, up, duration, extra = payload
                    self.var_title.set(f"标题：{title or '—'}")
                    m, s = divmod(max(duration, 0), 60)
                    self.var_meta.set(f"UP 主：{up or '—'}    时长：{m:02d}:{s:02d}")
                    self.var_extra.set(extra)

                elif kind == UIMsg.QUALITY:
                    options, current = payload
                    self.cb_quality["values"] = list(options)
                    if options:
                        self.cb_quality.current(max(0, min(current, len(options) - 1)))
                        self._update_codec_label()

                elif kind == UIMsg.PROGRESS:
                    label, done, total, pct = payload
                    key = {"video": "视频", "audio": "音频"}.get(label)
                    if key:
                        self._set_progress(key, done, total, pct)

                elif kind == UIMsg.DONE:
                    ok, text = payload
                    self.btn_fetch.config(state=tk.NORMAL)
                    self.btn_stop.config(state=tk.DISABLED)
                    if ok:
                        self._set_progress("合并", 100, 100, 100)
                        self.var_status.set("完成")
                        self._status_color_hint("green")
                        messagebox.showinfo("完成", f"已保存到：\n{text}")
                    else:
                        self.var_status.set("出错 / 取消")
                        self._status_color_hint("red")
                        messagebox.showwarning("提示", text)

                elif kind == UIMsg.BTN:
                    name, state = payload
                    if name == "fetch": self.btn_fetch.config(state=state)
                    elif name == "download": self.btn_download.config(state=state)
                    elif name == "stop": self.btn_stop.config(state=state)

                elif kind == "_READY_QUALITY":
                    # 清晰度就绪，GUI 接管
                    qns, chosen, wait_evt, info, dash, out_dir = payload
                    self._quality_qns = qns
                    self._quality_chosen = chosen
                    self._quality_wait = wait_evt
                    self._pipeline_info = info
                    self._pipeline_dash = dash
                    self._pipeline_out_dir = out_dir
                    self.btn_download.config(state=tk.NORMAL)
                    self.btn_stop.config(state=tk.NORMAL)
                    self._update_codec_label()
        finally:
            self.root.after(120, self._drain_queue)

    def _status_color_hint(self, color: str):
        """ttk.Label 不支持 foreground，这里用 Canvas 画一个小点 + 一个彩色 tk.Label 叠加提示。"""
        # 简单实现：在日志顶部追加一条彩色状态行
        tag = "status_line"
        self.txt_log.tag_configure(tag, foreground=color, font=("Consolas", 9, "bold"))

    # -------------------- 关闭 --------------------
    def _on_close(self):
        if self.worker and self.worker.is_alive():
            if not messagebox.askokcancel("确认", "任务进行中，确定退出吗？"):
                return
            self.stop_flag.set()
            if self._quality_wait is not None:
                self._quality_wait.set()
        self.root.destroy()


# ================================================================
#  main
# ================================================================
def main():
    # 如果用户传了 --test 就直接跑一次无 UI 的冒烟测试（用于自动化 / 命令行）
    if "--test" in sys.argv:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        print("运行冒烟测试：Fetcher 打 view 接口…")
        q_: queue.Queue = queue.Queue()
        u_ = UIMsg(q_)

        def lg(s): print("  [LOG]", s); u_.log(s)
        try:
            info = engine_fast_get_video_info(DEFAULT_BVID, None, lg)
            print("OK info:", json.dumps(info, ensure_ascii=False, indent=2, default=str)[:600])
        except Exception as e:
            print(f"冒烟测试失败: {type(e).__name__}: {e}")
            sys.exit(1)
        sys.exit(0)

    root = tk.Tk()
    try:
        # Windows 高 DPI 更清晰
        from ctypes import windll  # type: ignore
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
