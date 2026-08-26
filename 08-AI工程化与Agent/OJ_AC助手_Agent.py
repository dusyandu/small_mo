# -*- coding: utf-8 -*-
"""
OJ AC 助手 Agent
==================
模块功能：
    用户给题号 → Agent 自动爬取题目 → 给出解题思路 + Python 参考代码
    封装爬虫工具 + 超级鹰验证码工具，可扩展应对反爬

工具封装（本文件内）：
    1. get_problem_by_id: 爬取 OJ 题目详情（封装 OJ题单爬虫.py 的 OJCrawler）
    2. solve_captcha: 超级鹰验证码识别（应对未来反爬）

依赖安装：
    pip install langchain langchain-openai python-dotenv DrissionPage requests

运行方式：
    1. 确保 .env 含：
        ZHIPUAI_API_KEY=你的智谱key
        CHAOJIYING_USER=超级鹰账号（可选，无验证码时不用）
        CHAOJIYING_PWD=超级鹰密码（可选）
        CHAOJIYING_SOFTID=超级鹰软件ID（可选）
    2. python OJ_AC助手_Agent.py
    3. 输入题号（如 2098），Agent 自动解题

免责声明：仅供学习交流，解题代码请理解后再提交，勿直接抄袭
"""

import os
import base64
import json
from typing import Optional

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.tools import tool
from langchain.agents import create_agent

# 导入爬虫（同目录）
from OJ题单爬虫 import OJCrawler

load_dotenv()


# ============================================================
# 工具 1：爬虫 - 获取题目详情
# ============================================================
# 用模块级 crawler 实例（避免每次调用都重新初始化）
_crawler = OJCrawler()


@tool
def get_problem_by_id(problem_id: int) -> str:
    """根据题号获取 OJ 题目的完整详情（标题、描述、输入、输出）。

    Args:
        problem_id: OJ 题目编号，如 2098

    Returns:
        题目详情文本，包含标题/描述/输入/输出
    """
    try:
        detail = _crawler.get_problem_detail(problem_id)
        # 拼成给 LLM 看的文本
        text = (
            f"题号: {detail['id']}\n"
            f"标题: {detail['title']}\n"
            f"题目描述: {detail['description']}\n\n"
            f"输入描述: {detail['input']}\n\n"
            f"输出描述: {detail['output']}\n"
        )
        return text
    except Exception as e:
        return f"爬取题目 {problem_id} 失败: {e}"


# ============================================================
# 工具 2：超级鹰 - 验证码识别（应对反爬）
# ============================================================
class ChaojiyingSolver:
    """超级鹰验证码识别封装（从环境变量读凭证）"""

    def __init__(self):
        self.user = os.getenv("CHAOJIYING_USER", "")
        self.pwd = os.getenv("CHAOJIYING_PWD", "")
        self.softid = os.getenv("CHAOJIYING_SOFTID", "")
        # 超级鹰 API 地址
        self.api_url = "http://api.chaojiying.net/UploadAndProcess.ashx"

    def is_configured(self) -> bool:
        """是否已配置凭证"""
        return bool(self.user and self.pwd and self.softid)

    def solve(self, image_bytes: bytes, code_type: str = "1902") -> dict:
        """
        识别验证码

        Args:
            image_bytes: 验证码图片二进制
            code_type: 验证码类型（1902=4-6位英文数字，见超级鹰文档）

        Returns:
            {"success": bool, "result": str, "error": str}
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "超级鹰未配置：请在 .env 设置 CHAOJIYING_USER/PWD/SOFTID",
            }
        try:
            b64 = base64.b64encode(image_bytes).decode()
            data = {
                "user": self.user,
                "pass": self.pwd,
                "softid": self.softid,
                "codetype": code_type,
                "userfile": b64,
            }
            import requests
            r = requests.post(self.api_url, data=data, timeout=30)
            result = r.json()
            # 超级鹰返回格式: {"pic_str": "abcd", "err_str": "", "err_no": 0, ...}
            if result.get("err_no") == 0:
                return {"success": True, "result": result.get("pic_str", "")}
            return {"success": False, "error": result.get("err_str", "未知错误")}
        except Exception as e:
            return {"success": False, "error": str(e)}


_captcha_solver = ChaojiyingSolver()


@tool
def solve_captcha(image_path: str, code_type: str = "1902") -> str:
    """识别图片验证码（调用超级鹰 API）。

    当遇到网站验证码拦截时使用此工具。

    Args:
        image_path: 验证码图片的本地路径，如 ./captcha.png
        code_type: 验证码类型，默认 1902（4-6位英文数字），
                   其他类型见超级鹰文档（如 9101=纯4位数字）

    Returns:
        识别结果文本，或失败原因
    """
    if not os.path.exists(image_path):
        return f"图片不存在: {image_path}"
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    result = _captcha_solver.solve(image_bytes, code_type)
    if result["success"]:
        return f"验证码识别成功: {result['result']}"
    return f"验证码识别失败: {result.get('error')}"


# ============================================================
# 构建 Agent
# ============================================================
def build_agent():
    """构建 AC 助手 Agent"""
    # 初始化模型（智谱 GLM-4-Flash，OpenAI 兼容接口）
    model = init_chat_model(
        model="openai:glm-4-flash",
        base_url="https://open.bigmodel.cn/api/paas/v4/",
        api_key=os.getenv("ZHIPUAI_API_KEY"),
    )

    # ★ 关键：create_agent 的 model 参数传【实例】不是字符串
    # 原因：传字符串时内部 init_chat_model 不带 base_url/api_key，会 Missing credentials
    agent = create_agent(
        model=model,
        tools=[get_problem_by_id, solve_captcha],
        system_prompt=(
            "你是一个 ACM 算法解题助手，专门帮用户分析 OJ 题目并给出参考解法。\n\n"
            "【工作流程】\n"
            "1. 用户给你一个题号（如 2098）\n"
            "2. 你调用 get_problem_by_id 工具爬取题目详情\n"
            "3. 分析题目类型（模拟/数学/字符串/贪心/DP/图论等）\n"
            "4. 给出三部分回答：\n"
            "   - 解题思路（简洁说明算法）\n"
            "   - Python 参考代码（带注释，Python 3 语法）\n"
            "   - 复杂度分析（时间 + 空间）\n\n"
            "【注意事项】\n"
            "- 代码必须能直接复制到 OJ 提交（用 input() 读入，print() 输出）\n"
            "- 优先给最简单的解法，不要炫技\n"
            "- 如果题目描述不完整，说明缺什么信息\n"
            "- 当爬取失败时，提示用户检查题号或网站是否可访问\n"
        ),
    )
    return agent


# ============================================================
# 主入口：交互式对话
# ============================================================
def main():
    print("=" * 60)
    print("OJ AC 助手 Agent")
    print("给题号，自动爬取并给出解题思路 + 参考代码")
    print("=" * 60)

    # 检查配置
    if not os.getenv("ZHIPUAI_API_KEY"):
        print("❌ 未配置 ZHIPUAI_API_KEY，请在 .env 设置")
        return

    # 检查超级鹰（可选，不影响主功能）
    if _captcha_solver.is_configured():
        print("✅ 超级鹰已配置（验证码场景可用）")
    else:
        print("ℹ️ 超级鹰未配置（当前网站无验证码，不影响使用）")

    agent = build_agent()
    print("\n💡 输入题号开始（如 2098），输入 q 退出\n")

    while True:
        user_input = input("👉 题号: ").strip()
        if user_input.lower() in ("q", "quit", "exit"):
            print("再见！")
            break
        if not user_input.isdigit():
            print("请输入纯数字题号")
            continue

        problem_id = int(user_input)
        print(f"\n🤖 正在处理题目 {problem_id}...\n")

        # 调用 Agent
        result = agent.invoke({
            "messages": [{"role": "user", "content": f"帮我完成题目 {problem_id}"}]
        })

        # 打印 Agent 的最终回复
        reply = result["messages"][-1].content
        print("=" * 60)
        print(reply)
        print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
