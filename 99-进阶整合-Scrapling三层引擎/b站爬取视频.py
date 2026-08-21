# -*- coding: utf-8 -*-
"""
B站视频下载器 (DASH 流 + ffmpeg 无损合并) - GUI 版
- 图形界面 (tkinter), 操作简单
- 输入视频 URL 或 BV 号 → 获取信息 → 选清晰度 → 下载
- 音视频流并行下载 + 实时进度
- ffmpeg -c copy 无损秒级合并 (自动使用 imageio_ffmpeg 自带二进制)
- Cookie 在界面输入框填写 (不写进代码)

用法:
    python b站爬取视频.py
"""

import os
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from tkinter import filedialog, messagebox, scrolledtext, ttk
import tkinter as tk

import requests

# ===== 常量 =====
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0"
)

APP_TITLE = "B站视频下载器"

API_VIEW = "https://api.bilibili.com/x/web-interface/view"
API_PLAYURL = "https://api.bilibili.com/x/player/playurl"

# 清晰度 id -> 中文名
QUALITY_MAP = {
    127: "8K 超高清",
    126: "杜比视界",
    120: "4K 超清",
    116: "1080P 60帧",
    112: "1080P 高码率",
    80: "1080P 高清",
    74: "720P 60帧",
    64: "720P 高清",
    32: "480P 清晰",
    16: "360P 流畅",
    6: "240P",
    5: "144P",
}

# 编码 id -> 名称 (B 站 dash.video 的 codecid 字段, 实际取值为 7/12/13)
CODEC_MAP = {
    7: "H.264/AVC",
    12: "H.265/HEVC",
    13: "AV1",
}


# ===== 工具函数 =====
def extract_bvid(text: str) -> str:
    """从任意输入中提取 BV 号 (BV + 10位字母数字)"""
    m = re.search(r"(BV[0-9A-Za-z]{10})", text)
    if not m:
        raise ValueError(f"无法从输入中提取 BV 号: {text!r}")
    return m.group(1)


def sanitize_filename(name: str) -> str:
    """净化文件名: 去掉 Windows 非法字符"""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip()
    name = name.rstrip(". ")
    return name or "bilibili_video"


def build_session(cookie: str) -> requests.Session:
    """构建复用连接池的 Session"""
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Referer": "https://www.bilibili.com",
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    if cookie:
        s.headers["Cookie"] = cookie
    return s


# ===== 接口层 =====
def fetch_video_info(bvid: str, session: requests.Session) -> dict:
    """获取视频基本信息: cid / 标题 / UP 主 / 时长"""
    r = session.get(API_VIEW, params={"bvid": bvid}, timeout=(5, 10))
    r.raise_for_status()
    j = r.json()
    if j.get("code") != 0:
        raise RuntimeError(f"获取视频信息失败: {j.get('message')} (code={j.get('code')})")
    data = j["data"]
    return {
        "bvid": bvid,
        "cid": data["cid"],
        "title": data["title"],
        "up": data.get("owner", {}).get("name", ""),
        "duration": data.get("duration", 0),
    }


def fetch_playurl(bvid: str, cid: int, session: requests.Session) -> dict:
    """获取 DASH 播放流 (含视频/音频多路流)"""
    params = {
        "bvid": bvid,
        "cid": cid,
        "qn": 127,
        "fnval": 4048,
        "fnver": 0,
        "fourk": 1,
    }
    r = session.get(API_PLAYURL, params=params, timeout=(5, 10))
    r.raise_for_status()
    j = r.json()
    if j.get("code") != 0:
        raise RuntimeError(f"获取播放流失败: {j.get('message')} (code={j.get('code')})")
    data = j["data"]
    if "dash" not in data:
        raise RuntimeError("该视频不支持 DASH 流 (老视频仅有 mp4 格式, 暂不支持)")
    return data["dash"]


# ===== 选择层 =====
def select_video_stream(video_streams: list, qn: int) -> dict:
    """在指定清晰度下选视频流: 优先 AVC(codec=7) 兼容性最好, 再 AV1(13), 最后 HEVC(12)"""
    cands = [v for v in video_streams if v.get("id") == qn]
    if not cands:
        raise RuntimeError(f"未找到清晰度 qn={qn} 的视频流")
    for codec in (7, 13, 12):
        for v in cands:
            if v.get("codecid", 0) == codec:
                return v
    return cands[0]


def select_audio_stream(audio_streams: list) -> dict:
    """选音频流: 取最高码率 (id 最大)"""
    if not audio_streams:
        raise RuntimeError("无可用音频流")
    return max(audio_streams, key=lambda a: a.get("id", 0))


def stream_url(stream: dict) -> str:
    """兼容取 baseUrl / base_url"""
    return stream.get("baseUrl") or stream.get("base_url") or ""


# ===== 下载 / 合并 =====
def stream_download(session, url, dst, label, progress_cb=None, stop_flag=None):
    """流式分块下载, 可选进度回调 (label, done, total, pct), 可选 stop_flag 中断"""
    last_cb = 0.0
    with session.get(url, stream=True, timeout=(5, 60)) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        done = 0
        with open(dst, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if stop_flag and stop_flag.is_set():
                    raise RuntimeError("用户取消下载")
                if chunk:
                    f.write(chunk)
                    done += len(chunk)
                    now = time.time()
                    if progress_cb and (now - last_cb > 0.15 or (total and done >= total)):
                        pct = done * 100 / total if total else 0
                        progress_cb(label, done, total, pct)
                        last_cb = now
        if progress_cb:
            progress_cb(label, done, total, 100.0 if total else 0)


def find_ffmpeg() -> str:
    """查找可用的 ffmpeg: 1) PATH 2) imageio_ffmpeg 自带 3) 环境变量 FFMPEG_PATH"""
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


def merge_av(video_path, audio_path, out_path):
    """用 ffmpeg 无损合并 (-c copy, 不重编码, 秒级完成)"""
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError(
            "未找到 ffmpeg, 请任选其一:\n"
            "  1) 安装 ffmpeg 并加入 PATH\n"
            "  2) pip install imageio-ffmpeg (自带二进制)\n"
            "  3) 设置环境变量 FFMPEG_PATH 指向 ffmpeg.exe"
        )
    cmd = [ffmpeg, "-y", "-i", video_path, "-i", audio_path,
           "-c", "copy", "-movflags", "+faststart", out_path]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except FileNotFoundError:
        raise RuntimeError(f"ffmpeg 路径无效: {ffmpeg}")
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode("utf-8", "ignore")[-500:] if e.stderr else ""
        raise RuntimeError(f"ffmpeg 合并失败:\n{err}")


# ===== GUI =====
class BiliDownloaderApp:
    def __init__(self, root):
        self.root = root
        root.title(APP_TITLE)
        root.geometry("760x720")
        root.minsize(720, 680)

        self.stop_flag = threading.Event()
        self.info = None         # 视频信息 dict
        self.dash = None         # 播放流
        self.v_stream = None
        self.a_stream = None
        self.worker = None       # 后台工作线程

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- UI ----------
    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}
        frm = ttk.Frame(self.root, padding=10)
        frm.pack(fill=tk.BOTH, expand=True)

        # --- 输入区 ---
        in_frame = ttk.LabelFrame(frm, text="① 视频信息", padding=10)
        in_frame.pack(fill=tk.X, **pad)

        ttk.Label(in_frame, text="视频 URL/BV 号:").grid(row=0, column=0, sticky="W", pady=4)
        self.ent_url = ttk.Entry(in_frame, width=46)
        self.ent_url.grid(row=0, column=1, columnspan=3, sticky="WE", pady=4, padx=(4, 0))

        ttk.Label(in_frame, text="Cookie (选填):").grid(row=1, column=0, sticky="NW", pady=4)
        self.txt_cookie = scrolledtext.ScrolledText(in_frame, width=46, height=3, wrap=tk.WORD, font=("Consolas", 9))
        self.txt_cookie.grid(row=1, column=1, columnspan=3, sticky="WE", pady=4, padx=(4, 0))

        ttk.Label(in_frame, text="输出目录:").grid(row=2, column=0, sticky="W", pady=4)
        self.ent_outdir = ttk.Entry(in_frame, width=40)
        self.ent_outdir.grid(row=2, column=1, sticky="W", pady=4, padx=(4, 0))
        self.ent_outdir.insert(0, os.getcwd())
        self.btn_browse = ttk.Button(in_frame, text="浏览...", command=self.on_browse)
        self.btn_browse.grid(row=2, column=2, sticky="W", pady=4)

        self.btn_fetch = ttk.Button(in_frame, text="获取视频信息", command=self.on_fetch)
        self.btn_fetch.grid(row=2, column=3, sticky="W", pady=4, padx=(8, 0))

        in_frame.columnconfigure(1, weight=1)

        # --- 视频信息展示 ---
        info_frame = ttk.LabelFrame(frm, text="② 视频详情", padding=10)
        info_frame.pack(fill=tk.X, **pad)
        self.lbl_title = ttk.Label(info_frame, text="标题: (未获取)", foreground="#333")
        self.lbl_title.pack(anchor="w", pady=2)
        self.lbl_meta = ttk.Label(info_frame, text="UP 主: -    时长: -", foreground="#666")
        self.lbl_meta.pack(anchor="w", pady=2)

        sel_row = ttk.Frame(info_frame)
        sel_row.pack(fill=tk.X, pady=6)
        ttk.Label(sel_row, text="清晰度:").pack(side=tk.LEFT)
        self.cb_quality = ttk.Combobox(sel_row, values=[], width=20, state="readonly")
        self.cb_quality.pack(side=tk.LEFT, padx=(4, 12))
        self.lbl_codec = ttk.Label(sel_row, text="编码: -", foreground="#666")
        self.lbl_codec.pack(side=tk.LEFT)

        # --- 控制按钮 ---
        ctrl = ttk.Frame(frm)
        ctrl.pack(fill=tk.X, **pad)
        self.btn_download = ttk.Button(ctrl, text="③ 开始下载", command=self.on_download, state=tk.DISABLED)
        self.btn_download.pack(side=tk.LEFT)
        self.btn_stop = ttk.Button(ctrl, text="停止", command=self.on_stop, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=8)
        self.lbl_status = ttk.Label(ctrl, text="就绪", foreground="gray")
        self.lbl_status.pack(side=tk.LEFT, padx=12)

        # --- 进度条 ---
        prog_frame = ttk.LabelFrame(frm, text="进度", padding=8)
        prog_frame.pack(fill=tk.X, **pad)
        self._make_prog_row(prog_frame, "video")
        self._make_prog_row(prog_frame, "audio")

        # --- 日志 ---
        log_frame = ttk.LabelFrame(frm, text="日志", padding=4)
        log_frame.pack(fill=tk.BOTH, expand=True, **pad)
        self.txt_log = scrolledtext.ScrolledText(log_frame, height=12, wrap=tk.WORD, font=("Consolas", 9))
        self.txt_log.pack(fill=tk.BOTH, expand=True)

    def _make_prog_row(self, parent, label):
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=2)
        ttk.Label(row, text=label, width=8).pack(side=tk.LEFT)
        bar = ttk.Progressbar(row, length=400, mode="determinate")
        bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        lbl = ttk.Label(row, text="0%", width=8)
        lbl.pack(side=tk.LEFT)
        if label == "video":
            self.bar_video, self.lbl_video = bar, lbl
        else:
            self.bar_audio, self.lbl_audio = bar, lbl

    # ---------- 线程安全日志 ----------
    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        def append():
            self.txt_log.insert(tk.END, line)
            self.txt_log.see(tk.END)
        self.root.after(0, append)

    def set_status(self, text, color="gray"):
        self.root.after(0, lambda: self.lbl_status.config(text=text, foreground=color))

    # ---------- 事件 ----------
    def on_browse(self):
        d = filedialog.askdirectory(initialdir=self.ent_outdir.get() or os.getcwd())
        if d:
            self.ent_outdir.delete(0, tk.END)
            self.ent_outdir.insert(0, d)

    def on_fetch(self):
        url = self.ent_url.get().strip()
        if not url:
            messagebox.showwarning("提示", "请输入视频 URL 或 BV 号")
            return
        self.btn_fetch.config(state=tk.DISABLED)
        self.btn_download.config(state=tk.DISABLED)
        self.set_status("获取中...", "blue")
        self.stop_flag.clear()
        self.worker = threading.Thread(target=self._fetch_worker, args=(url,), daemon=True)
        self.worker.start()

    def _fetch_worker(self, url):
        try:
            bvid = extract_bvid(url)
            self.log(f"BV 号: {bvid}")
            cookie = self.txt_cookie.get("1.0", tk.END).strip()
            if not cookie:
                self.log("[!] 未填写 Cookie, 仅能下载低清晰度 (480P/360P)")
            session = build_session(cookie)
            info = fetch_video_info(bvid, session)
            self.info = info
            self.log(f"标题: {info['title']}")
            self.log(f"UP 主: {info['up']}    时长: {info['duration']}秒    CID: {info['cid']}")
            dash = fetch_playurl(bvid, info["cid"], session)
            self.dash = dash
            videos = dash.get("video", [])
            audios = dash.get("audio", [])
            if not videos:
                raise RuntimeError("无可用视频流")
            qns = sorted({v["id"] for v in videos}, reverse=True)
            labels = [f"{qn} {QUALITY_MAP.get(qn, '')}" for qn in qns]

            def update_ui():
                self.lbl_title.config(text=f"标题: {info['title']}")
                mins, secs = divmod(info["duration"], 60)
                self.lbl_meta.config(text=f"UP 主: {info['up']}    时长: {mins:02d}:{secs:02d}")
                self.cb_quality["values"] = labels
                if labels:
                    self.cb_quality.current(0)
                    self._on_quality_change()
                self.btn_download.config(state=tk.NORMAL)
                self.set_status("已就绪, 可下载", "green")
            self.root.after(0, update_ui)
            self.log(f"可用清晰度: {labels}")
        except Exception as e:
            self.log(f"✘ 获取失败: {e}")
            self.set_status("获取失败", "red")
        finally:
            self.root.after(0, lambda: self.btn_fetch.config(state=tk.NORMAL))

    def _on_quality_change(self, event=None):
        if not self.dash:
            return
        try:
            sel = self.cb_quality.get()
            qn = int(sel.split()[0]) if sel else 0
            v = select_video_stream(self.dash.get("video", []), qn)
            codec_name = CODEC_MAP.get(v.get("codecid", 0), f"codec={v.get('codecid')}")
            self.lbl_codec.config(text=f"编码: {codec_name}")
        except Exception:
            self.lbl_codec.config(text="编码: -")

    def on_download(self):
        if not self.info or not self.dash:
            messagebox.showwarning("提示", "请先获取视频信息")
            return
        sel = self.cb_quality.get()
        if not sel:
            messagebox.showwarning("提示", "请选择清晰度")
            return
        out_dir = self.ent_outdir.get().strip() or os.getcwd()
        if not os.path.isdir(out_dir):
            messagebox.showerror("错误", f"输出目录不存在: {out_dir}")
            return

        self.stop_flag.clear()
        self.btn_download.config(state=tk.DISABLED)
        self.btn_fetch.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.set_status("下载中...", "blue")
        # 重置进度条
        self.bar_video["value"] = 0
        self.bar_audio["value"] = 0
        self.lbl_video.config(text="0%")
        self.lbl_audio.config(text="0%")

        qn = int(sel.split()[0])
        self.worker = threading.Thread(target=self._download_worker, args=(qn, out_dir), daemon=True)
        self.worker.start()

    def _progress_cb(self, label, done, total, pct):
        def update():
            bar = self.bar_video if label == "video" else self.bar_audio
            lbl = self.lbl_video if label == "video" else self.lbl_audio
            bar["value"] = pct
            if total:
                lbl.config(text=f"{pct:.0f}%  {done/1024/1024:.1f}/{total/1024/1024:.1f}MB")
            else:
                lbl.config(text=f"{done/1024/1024:.1f}MB")
        self.root.after(0, update)

    def _download_worker(self, qn, out_dir):
        try:
            v_stream = select_video_stream(self.dash["video"], qn)
            a_stream = select_audio_stream(self.dash.get("audio", []))
            v_url = stream_url(v_stream)
            a_url = stream_url(a_stream)
            if not v_url or not a_url:
                raise RuntimeError("无法获取视频/音频流 URL")

            codec_name = CODEC_MAP.get(v_stream.get("codecid", 0), "?")
            self.log(f"选定: {QUALITY_MAP.get(qn, str(qn))} [{codec_name}]")

            safe_title = sanitize_filename(self.info["title"])
            out_path = os.path.join(out_dir, f"{safe_title}.mp4")
            tmp_v = out_path + ".video.m4s"
            tmp_a = out_path + ".audio.m4s"

            cookie = self.txt_cookie.get("1.0", tk.END).strip()
            session = build_session(cookie)

            self.log("开始下载...")
            with ThreadPoolExecutor(max_workers=2) as pool:
                futs = {
                    pool.submit(stream_download, session, v_url, tmp_v, "video",
                                self._progress_cb, self.stop_flag),
                    pool.submit(stream_download, session, a_url, tmp_a, "audio",
                                self._progress_cb, self.stop_flag),
                }
                for fut in as_completed(futs):
                    fut.result()

            if self.stop_flag.is_set():
                self.log("已取消, 清理临时文件")
                for p in (tmp_v, tmp_a):
                    try: os.remove(p)
                    except OSError: pass
                self.set_status("已取消", "gray")
                return

            self.log("ffmpeg 合并中...")
            merge_av(tmp_v, tmp_a, out_path)
            for p in (tmp_v, tmp_a):
                try: os.remove(p)
                except OSError: pass
            self.log(f"✔ 完成: {out_path}")
            self.set_status("完成", "green")
            self.root.after(0, lambda: messagebox.showinfo("完成", f"已保存到:\n{out_path}"))
        except Exception as e:
            self.log(f"✘ 出错: {e}")
            self.set_status("出错", "red")
            self.root.after(0, lambda: messagebox.showerror("出错", str(e)))
        finally:
            self.root.after(0, lambda: (
                self.btn_download.config(state=tk.NORMAL),
                self.btn_fetch.config(state=tk.NORMAL),
                self.btn_stop.config(state=tk.DISABLED),
            ))

    def on_stop(self):
        self.stop_flag.set()
        self.set_status("正在停止...", "orange")

    def _on_close(self):
        if self.worker and self.worker.is_alive():
            if not messagebox.askokcancel("确认", "任务进行中, 确定退出吗？"):
                return
            self.stop_flag.set()
        self.root.destroy()


def main():
    root = tk.Tk()
    BiliDownloaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
