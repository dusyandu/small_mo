# -*- coding: utf-8 -*-
"""
OJ AC 助手 Agent - GUI 版
==========================
模块功能：
    给 Agent 工具加可视化界面，输入题号即可自动解题
    Tkinter + ttk 多分区布局，后台线程 + queue 消息总线（线程安全）

依赖安装：
    pip install langchain langchain-openai python-dotenv DrissionPage

运行方式：
    python OJ_AC助手_GUI.py

界面分区：
    标题区 / 输入区 / 题目详情区 / Agent解答区 / 运行日志区 / 进度状态区

线程模型：
    - 主线程：Tkinter 事件循环（所有 UI 操作必须在主线程）
    - 后台线程：ThreadPoolExecutor 跑 agent.invoke
    - 消息总线：queue.Queue 传日志和结果到主线程
    - 主线程 root.after(100) 轮询 queue 更新 UI

免责声明：仅供学习交流，解题代码请理解后再提交
"""

import os
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from dotenv import load_dotenv
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

from langchain.chat_models import init_chat_model
from langchain_core.tools import tool
from langchain.agents import create_agent

from OJ题单爬虫 import OJCrawler

load_dotenv()


# ============================================================
# 消息总线（线程安全）
# ============================================================
class MessageBus:
    """线程间消息队列，后台线程往里 put，主线程轮询 get"""
    def __init__(self):
        self._q = queue.Queue()

    def put(self, msg_type: str, data: str):
        """后台线程调用：推消息。msg_type: log/result/status/done"""
        self._q.put((msg_type, data))

    def get_nowait(self):
        """主线程调用：非阻塞取消息"""
        try:
            return self._q.get_nowait()
        except queue.Empty:
            return None


bus = MessageBus()


# ============================================================
# 工具封装（带日志回调）
# ============================================================
_crawler = OJCrawler()


@tool
def get_problem_by_id(problem_id: int) -> str:
    """根据题号获取 OJ 题目的完整详情（标题、描述、输入、输出）。

    Args:
        problem_id: OJ 题目编号，如 2098
    """
    bus.put("log", f"[{datetime.now():%H:%M:%S}] 开始爬取题目 {problem_id}...")
    bus.put("status", "正在爬取题目...")
    try:
        detail = _crawler.get_problem_detail(problem_id)
        # 拼成给 LLM 看的文本（含样例输入/输出，提升生成代码正确率）
        parts = [
            f"题号: {detail['id']}\n"
            f"标题: {detail['title']}\n\n"
            f"【题目描述】\n{detail['description']}\n\n"
            f"【输入描述】\n{detail['input']}\n\n"
            f"【输出描述】\n{detail['output']}",
        ]
        # 样例非空才加入（避免空样例占位）
        if detail.get("sample_input"):
            parts.append(f"【样例输入】\n{detail['sample_input']}")
        if detail.get("sample_output"):
            parts.append(f"【样例输出】\n{detail['sample_output']}")
        text = "\n\n".join(parts) + "\n"
        bus.put("log", f"[{datetime.now():%H:%M:%S}] ✓ 爬取成功：{detail['title']}")
        bus.put("problem", text)
        return text
    except Exception as e:
        bus.put("log", f"[{datetime.now():%H:%M:%S}] ✗ 爬取失败: {e}")
        return f"爬取失败: {e}"


@tool
def solve_captcha(image_path: str, code_type: str = "1902") -> str:
    """识别图片验证码（调用超级鹰 API）。

    Args:
        image_path: 验证码图片路径
        code_type: 验证码类型，默认 1902
    """
    bus.put("log", f"[{datetime.now():%H:%M:%S}] 调用超级鹰识别验证码...")
    # 复用 agent 文件的封装逻辑（简化版）
    if not os.path.exists(image_path):
        return f"图片不存在: {image_path}"
    try:
        from OJ_AC助手_Agent import _captcha_solver
        with open(image_path, "rb") as f:
            result = _captcha_solver.solve(f.read(), code_type)
        if result["success"]:
            bus.put("log", f"[{datetime.now():%H:%M:%S}] ✓ 识别成功: {result['result']}")
            return f"识别成功: {result['result']}"
        bus.put("log", f"[{datetime.now():%H:%M:%S}] ✗ 识别失败: {result.get('error')}")
        return f"识别失败: {result.get('error')}"
    except Exception as e:
        return f"识别异常: {e}"


def build_agent():
    """构建 AC 助手 Agent"""
    model = init_chat_model(
        model="openai:glm-4-flash",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        api_key=os.getenv("ZHIPUAI_API_KEY"),
    )
    return create_agent(
        model=model,
        tools=[get_problem_by_id, solve_captcha],
        system_prompt=(
            "你是一个 ACM 算法解题助手。用户给你题号，你调用 get_problem_by_id 爬取题目，"
            "然后给出三部分：\n"
            "1. 解题思路（简洁说明算法）\n"
            "2. Python 参考代码（带注释，用 input() 读入，print() 输出，可直接提交）\n"
            "3. 复杂度分析（时间 + 空间）\n"
            "优先给最简单的解法，不要炫技。"
        ),
    )


# ============================================================
# GUI 主窗口
# ============================================================
class OJAgentGUI:
    def __init__(self, root):
        self.root = root
        self.agent = None
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.running = False

        self._setup_window()
        self._build_styles()
        self._build_layout()
        self._poll_messages()

    # -------- 窗口设置 --------
    def _setup_window(self):
        self.root.title("OJ AC 助手 Agent")
        self.root.geometry("900x780")
        self.root.minsize(700, 600)

    def _build_styles(self):
        style = ttk.Style()
        style.configure("Title.TLabel", font=("微软雅黑", 16, "bold"), foreground="#2c3e50")
        style.configure("Hint.TLabel", font=("微软雅黑", 9), foreground="#7f8c8d")
        style.configure("Start.TButton", font=("微软雅黑", 10, "bold"))
        style.configure("Region.TLabel", font=("微软雅黑", 10, "bold"), foreground="#34495e")

    # -------- 布局 --------
    def _build_layout(self):
        # 主容器
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        # ===== 标题区 =====
        ttk.Label(main, text="🎯 OJ AC 助手 Agent", style="Title.TLabel").pack(anchor=tk.W, pady=(0, 5))
        ttk.Label(main, text="输入题号，Agent 自动爬取题目并给出解题思路 + 参考代码", style="Hint.TLabel").pack(anchor=tk.W, pady=(0, 10))

        # ===== 输入区 =====
        input_frame = ttk.LabelFrame(main, text="输入区", padding=8)
        input_frame.pack(fill=tk.X, pady=(0, 8))

        row = ttk.Frame(input_frame)
        row.pack(fill=tk.X)
        ttk.Label(row, text="题号:").pack(side=tk.LEFT)
        self.id_entry = ttk.Entry(row, width=15, font=("Consolas", 11))
        self.id_entry.pack(side=tk.LEFT, padx=(5, 15))
        self.id_entry.insert(0, "2098")
        self.id_entry.bind("<Return>", lambda e: self.start_solve())

        self.start_btn = ttk.Button(row, text="开始解题", style="Start.TButton", command=self.start_solve)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(row, text="清空", command=self.clear_all).pack(side=tk.LEFT)

        # ===== 题目详情区 =====
        detail_frame = ttk.LabelFrame(main, text="题目详情", padding=4)
        detail_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        self.detail_text = scrolledtext.ScrolledText(detail_frame, height=8, font=("微软雅黑", 10), wrap=tk.WORD, state=tk.DISABLED, bg="#fdfdfd")
        self.detail_text.pack(fill=tk.BOTH, expand=True)

        # ===== Agent 解答区 =====
        answer_frame = ttk.LabelFrame(main, text="Agent 解答", padding=4)
        answer_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))
        self.answer_text = scrolledtext.ScrolledText(answer_frame, height=10, font=("微软雅黑", 10), wrap=tk.WORD, state=tk.DISABLED, bg="#f4fbf4")
        self.answer_text.pack(fill=tk.BOTH, expand=True)

        # ===== 运行日志区 =====
        log_frame = ttk.LabelFrame(main, text="运行日志", padding=4)
        log_frame.pack(fill=tk.X, pady=(0, 8))
        self.log_text = scrolledtext.ScrolledText(log_frame, height=6, font=("Consolas", 9), wrap=tk.WORD, state=tk.DISABLED, bg="#1e1e1e", fg="#d4d4d4")
        self.log_text.pack(fill=tk.X)

        # ===== 进度状态区 =====
        status_frame = ttk.Frame(main)
        status_frame.pack(fill=tk.X)
        self.progress = ttk.Progressbar(status_frame, mode="indeterminate")
        self.progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        self.status_label = ttk.Label(status_frame, text="就绪", style="Hint.TLabel")
        self.status_label.pack(side=tk.RIGHT)

    # -------- 消息轮询（主线程） --------
    def _poll_messages(self):
        """主线程轮询 queue，更新 UI（必须在主线程操作 UI）"""
        while True:
            msg = bus.get_nowait()
            if msg is None:
                break
            msg_type, data = msg
            if msg_type == "log":
                self._append_log(data)
            elif msg_type == "problem":
                self._set_detail(data)
            elif msg_type == "answer":
                self._set_answer(data)
            elif msg_type == "status":
                self.status_label.config(text=data)
            elif msg_type == "done":
                self._on_done(data)
            elif msg_type == "error":
                self._on_error(data)
        self.root.after(100, self._poll_messages)

    # -------- UI 更新方法（主线程调用） --------
    def _append_log(self, text):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _set_detail(self, text):
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert("1.0", text)
        self.detail_text.config(state=tk.DISABLED)

    def _set_answer(self, text):
        self.answer_text.config(state=tk.NORMAL)
        self.answer_text.delete("1.0", tk.END)
        self.answer_text.insert("1.0", text)
        self.answer_text.config(state=tk.DISABLED)

    # -------- 操作 --------
    def start_solve(self):
        if self.running:
            return
        pid = self.id_entry.get().strip()
        if not pid.isdigit():
            messagebox.showwarning("提示", "请输入纯数字题号")
            return
        if not os.getenv("ZHIPUAI_API_KEY"):
            messagebox.showerror("错误", "未配置 ZHIPUAI_API_KEY，请检查 .env")
            return

        # 初始化 agent（懒加载）
        if self.agent is None:
            self.status_label.config(text="初始化 Agent...")
            try:
                self.agent = build_agent()
            except Exception as e:
                messagebox.showerror("初始化失败", str(e))
                return

        # 清空结果区
        self._set_detail("")
        self._set_answer("")
        self._append_log(f"[{datetime.now():%H:%M:%S}] 开始处理题目 {pid}")

        # 切换 UI 状态
        self.running = True
        self.start_btn.config(state=tk.DISABLED)
        self.progress.start(10)
        self.status_label.config(text="处理中...")

        # 提交后台任务
        self.executor.submit(self._run_agent, int(pid))

    def _run_agent(self, problem_id):
        """后台线程：跑 agent（不能在这里操作 UI，只能 put 消息）"""
        try:
            bus.put("status", "Agent 思考中...")
            result = self.agent.invoke({
                "messages": [{"role": "user", "content": f"帮我完成题目 {problem_id}"}]
            })
            reply = result["messages"][-1].content
            bus.put("answer", reply)
            bus.put("done", "完成")
        except Exception as e:
            bus.put("error", str(e))

    def _on_done(self, msg):
        self._reset_ui()
        self._append_log(f"[{datetime.now():%H:%M:%S}] ✓ {msg}")

    def _on_error(self, err):
        self._reset_ui()
        self._append_log(f"[{datetime.now():%H:%M:%S}] ✗ 错误: {err}")
        messagebox.showerror("运行错误", err)

    def _reset_ui(self):
        self.running = False
        self.start_btn.config(state=tk.NORMAL)
        self.progress.stop()
        self.status_label.config(text="就绪")

    def clear_all(self):
        if self.running:
            return
        self._set_detail("")
        self._set_answer("")
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)

    def on_close(self):
        if self.running:
            if not messagebox.askyesno("确认", "Agent 正在运行，确定退出？"):
                return
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


# ============================================================
# 主入口
# ============================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = OJAgentGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()
