# -*- coding: utf-8 -*-
"""
OJ 题单爬虫 - 可作为 LangChain Agent 工具调用
=================================================
模块功能：
    爬取 ACM-ICPC-OJ 训练营题单网站，分层获取 题单→题目→题目详情
    预留超级鹰验证码识别接口，应对反爬

依赖安装：
    pip install DrissionPage

运行方式：
    1. 直接运行：python OJ题单爬虫.py
    2. 作为工具调用：
        from OJ题单爬虫 import OJCrawler
        crawler = OJCrawler()
        lists = crawler.get_problem_lists()           # 第一层：题单列表
        probs = crawler.get_problems_in_list(1)       # 第二层：题单内题目
        detail = crawler.get_problem_detail(2098)     # 第三层：题目详情

网站结构说明（实测 2026-08-26）：
    第一层 题单列表页: problemlist.php
        xpath: //*[@id="problemset"]//div[@class="left"]//a
        链接格式: problemlist_view.php?id=X  （X = 题单ID）
    第二层 题单详情页: problemlist_view.php?id=X
        xpath: //strong/strong//a[contains(@href,"problem.php")]
        链接格式: problem.php?id=Y  （Y = 题目ID，这是中转页）
        ★ 注意：真正题目内容在 every_do_problem.php?id=Y
    第三层 题目详情页: every_do_problem.php?id=Y
        xpath: //div[@class="content"]
        顺序: [1]题目描述 [2]输入描述 [3]输出描述 [4]来源标签

反爬说明：
    本网站目前无强反爬，requests/SessionPage 可直接抓取
    预留超级鹰接口：若未来出现验证码，切换 WebPage 浏览器模式 + 超级鹰识别

免责声明：仅供学习交流使用，请勿用于商业用途或恶意爬取
"""

import json
import time
import os
from typing import List, Dict, Optional

from DrissionPage import SessionPage, WebPage


class OJCrawler:
    """OJ 题单爬虫，支持分层爬取 + 超级鹰验证码整合"""

    BASE_URL = "http://39.106.228.241"

    def __init__(
        self,
        base_url: str = BASE_URL,
        use_browser: bool = False,
        captcha_solver=None,
    ):
        """
        初始化爬虫

        Args:
            base_url: 网站根地址
            use_browser: 是否使用浏览器模式（应对反爬时开启）
            captcha_solver: 超级鹰验证码识别器（预留接口，传入后遇到验证码自动调用）
        """
        self.base_url = base_url.rstrip("/")
        self.use_browser = use_browser
        self.captcha_solver = captcha_solver  # 超级鹰接口预留
        # SessionPage: 纯 HTTP 模式，轻量稳定（DrissionPage 的无浏览器模式）
        self.session = SessionPage()
        # DrissionPage 4.x: SessionPage 用 set.timeout（单数），WebPage 用 set.timeouts
        try:
            self.session.set.timeout(base=15)
        except Exception:
            pass  # 用默认 timeout 也行
        # WebPage: 浏览器模式，按需启用（验证码场景）
        self._browser = None

    # ============================================================
    # 第一层：获取题单列表
    # ============================================================
    def get_problem_lists(self) -> List[Dict]:
        """
        获取题单列表页所有题单

        Returns:
            [{"id": 1, "title": "【ACM算法攻关部】新生选拔赛训练题单",
              "url": "http://39.106.228.241/problemlist_view.php?id=1"}, ...]
        """
        url = f"{self.base_url}/problemlist.php"
        print(f"[第一层] 正在获取题单列表: {url}")

        self.session.get(url)
        time.sleep(1)

        # xpath: //*[@id="problemset"]//div[@class="left"]//a
        links = self.session.eles('xpath://*[@id="problemset"]//div[@class="left"]//a')
        print(f"  发现 {len(links)} 个题单")

        result = []
        seen_ids = set()  # 去重（同一题单可能多次出现）
        for a in links:
            href = a.attr('href') or ''
            title = (a.text or '').strip()
            if not href or 'problemlist_view.php' not in href:
                continue
            # 提取 id 参数
            pid = self._extract_id(href, 'id')
            if pid is None or pid in seen_ids:
                continue
            seen_ids.add(pid)
            full_url = href if href.startswith('http') else f"{self.base_url}/{href}"
            result.append({"id": pid, "title": title, "url": full_url})

        print(f"  去重后题单数: {len(result)}")
        return result

    # ============================================================
    # 第二层：获取题单内所有题目
    # ============================================================
    def get_problems_in_list(self, list_id: int) -> List[Dict]:
        """
        获取指定题单内的所有题目

        Args:
            list_id: 题单ID（如 1）

        Returns:
            [{"id": 2098, "title": "跟奥巴马一起画方块",
              "url": "http://39.106.228.241/problem.php?id=2098",
              "detail_url": "http://39.106.228.241/every_do_problem.php?id=2098"}, ...]
        """
        url = f"{self.base_url}/problemlist_view.php?id={list_id}"
        print(f"[第二层] 正在获取题单 {list_id} 的题目: {url}")

        self.session.get(url)
        time.sleep(1)

        # ★ 注意：用户原始 xpath //strong/strong//a 在 lxml 解析下匹配不到
        #   原因：<strong>Level-1<strong></strong></strong> 是嵌套空 strong，题目链接不在 strong 里
        #   修正：直接用 //a[contains(@href,"problem.php")] 拿所有题目链接，靠 problem.php?id= 过滤
        links = self.session.eles('xpath://a[contains(@href,"problem.php")]')
        print(f"  发现 {len(links)} 个题目链接")

        result = []
        seen_ids = set()
        for a in links:
            href = a.attr('href') or ''
            title = (a.attr('title') or a.text or '').strip()
            if 'problem.php?id=' not in href:
                continue
            pid = self._extract_id(href, 'id')
            if pid is None or pid in seen_ids:
                continue
            seen_ids.add(pid)
            full_url = href if href.startswith('http') else f"{self.base_url}/{href}"
            # ★ 关键：problem.php 是中转页，真正内容在 every_do_problem.php
            detail_url = f"{self.base_url}/every_do_problem.php?id={pid}"
            result.append({
                "id": pid,
                "title": title,
                "url": full_url,
                "detail_url": detail_url,
            })

        print(f"  去重后题目数: {len(result)}")
        return result

    # ============================================================
    # 第三层：获取题目详情
    # ============================================================
    def get_problem_detail(self, problem_id: int) -> Dict:
        """
        获取单道题目的详情（描述/输入/输出）

        Args:
            problem_id: 题目ID（如 2098）

        Returns:
            {
                "id": 2098,
                "title": "跟奥巴马一起画方块",
                "description": "美国总统奥巴马...",
                "input": "输入在一行中给出...",
                "output": "输出由给定字符C...",
                "url": "http://39.106.228.241/every_do_problem.php?id=2098"
            }
        """
        # ★ 关键：用 every_do_problem.php 而不是 problem.php（后者是中转页）
        url = f"{self.base_url}/every_do_problem.php?id={problem_id}"
        print(f"[第三层] 正在获取题目 {problem_id} 详情: {url}")

        self.session.get(url)
        time.sleep(0.5)

        # 拿题目标题（在 center/h2，不是 jumbotron/h2 后者是"题目描述"章节标题）
        title = ""
        title_el = self.session.ele('xpath://center/h2', timeout=3)
        if title_el:
            title = title_el.text.strip()
        else:
            # 备选：title 标签
            title_el = self.session.ele('xpath://title', timeout=2)
            if title_el:
                title = title_el.text.strip().replace('问题 ', '')

        # xpath: //div[@class="content"] 顺序: [1]描述 [2]输入 [3]输出 [4]来源
        contents = self.session.eles('xpath://div[@class="content"]')
        description = contents[0].text.strip() if len(contents) > 0 else ""
        input_desc = contents[1].text.strip() if len(contents) > 1 else ""
        output_desc = contents[2].text.strip() if len(contents) > 2 else ""

        result = {
            "id": problem_id,
            "title": title,
            "description": description,
            "input": input_desc,
            "output": output_desc,
            "url": url,
        }
        print(f"  标题: {title}")
        print(f"  描述: {description[:50]}...")
        return result

    # ============================================================
    # 整合：爬取全部（可选指定题单）
    # ============================================================
    def crawl_all(
        self,
        list_ids: Optional[List[int]] = None,
        output_file: str = "oj_problems.json",
        max_problems: Optional[int] = None,
    ) -> List[Dict]:
        """
        爬取所有题单的所有题目详情

        Args:
            list_ids: 指定题单ID列表（None = 全部）
            output_file: 输出 JSON 文件名
            max_problems: 最大题目数（None = 不限，测试时建议设小值）

        Returns:
            题目详情列表
        """
        all_problems = []
        try:
            # 第一层：题单列表
            lists = self.get_problem_lists()
            if list_ids:
                lists = [l for l in lists if l["id"] in list_ids]
                print(f"\n筛选后题单: {len(lists)} 个")

            count = 0
            for lst in lists:
                print(f"\n--- 题单 {lst['id']}: {lst['title']} ---")
                # 第二层：题单内题目
                problems = self.get_problems_in_list(lst["id"])
                for prob in problems:
                    count += 1
                    # 第三层：题目详情
                    detail = self.get_problem_detail(prob["id"])
                    detail["list_id"] = lst["id"]
                    detail["list_title"] = lst["title"]
                    all_problems.append(detail)

                    # 增量保存（防中断丢失）
                    self._save(all_problems, output_file)

                    if max_problems and count >= max_problems:
                        print(f"\n达到最大题目数 {max_problems}，停止")
                        return all_problems

                    time.sleep(0.3)  # 限速，防封

        except KeyboardInterrupt:
            print(f"\n用户中断，已保存 {len(all_problems)} 条到 {output_file}")
        except Exception as e:
            print(f"\n出错: {e}，已保存 {len(all_problems)} 条到 {output_file}")
            raise

        print(f"\n✅ 完成！共爬取 {len(all_problems)} 道题目，保存到 {output_file}")
        return all_problems

    # ============================================================
    # 超级鹰验证码整合接口（预留）
    # ============================================================
    def _handle_captcha(self) -> bool:
        """
        验证码处理（预留接口）
        当检测到验证码时，调用 captcha_solver 识别

        Returns:
            True = 识别成功，False = 识别失败
        """
        if not self.captcha_solver:
            print("⚠️ 遇到验证码但未配置 captcha_solver，跳过")
            return False

        # 切换到浏览器模式（验证码需要截图）
        if not self._browser:
            print("切换到浏览器模式处理验证码...")
            self._browser = WebPage()
            self._browser.set.timeouts(base=20)

        # 截图验证码区域
        captcha_img = self._browser.ele('xpath://img[contains(@src,"captcha")]', timeout=5)
        if not captcha_img:
            print("未找到验证码图片")
            return False

        # 调用超级鹰识别
        img_bytes = captcha_img.get_screenshot()  # 截图
        result = self.captcha_solver.solve(img_bytes)

        if result and result.get("success"):
            # 填入验证码
            input_el = self._browser.ele('xpath://input[@name="captcha"]', timeout=3)
            if input_el:
                input_el.input(result["result"])
                # 点击提交
                submit = self._browser.ele('xpath://button[@type="submit"]', timeout=3)
                if submit:
                    submit.click()
                    time.sleep(2)
                    return True
        return False

    # ============================================================
    # 辅助方法
    # ============================================================
    def _extract_id(self, url: str, param: str = 'id') -> Optional[int]:
        """从 URL 提取参数值"""
        import re
        m = re.search(rf'[?&]{param}=(\d+)', url)
        return int(m.group(1)) if m else None

    def _save(self, data, filename: str):
        """增量保存到 JSON"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# ============================================================
# 主入口
# ============================================================
if __name__ == "__main__":
    crawler = OJCrawler()

    # ===== 测试模式：只爬 1 个题单的前 3 道题 =====
    print("=" * 60)
    print("OJ 题单爬虫 - 测试模式（1个题单前3题）")
    print("=" * 60)

    # 单独测试每一层
    print("\n【测试第一层】获取题单列表:")
    lists = crawler.get_problem_lists()
    print(f"前 3 个题单:")
    for l in lists[:3]:
        print(f"  ID={l['id']}, 标题={l['title']}")

    print("\n【测试第二层】获取题单 1 的题目:")
    problems = crawler.get_problems_in_list(1)
    print(f"前 3 道题:")
    for p in problems[:3]:
        print(f"  ID={p['id']}, 标题={p['title']}")

    print("\n【测试第三层】获取题目 2098 详情:")
    detail = crawler.get_problem_detail(2098)
    print(f"\n完整详情:")
    print(f"  标题: {detail['title']}")
    print(f"  描述: {detail['description'][:100]}...")
    print(f"  输入: {detail['input'][:100]}...")
    print(f"  输出: {detail['output'][:100]}...")

    # ===== 完整爬取（取消注释即可运行）=====
    # print("\n" + "=" * 60)
    # print("完整爬取所有题单")
    # print("=" * 60)
    # crawler.crawl_all(output_file="oj_problems.json", max_problems=5)  # 测试先爬5题

    print("\n✅ 测试完成！")
    print("如需完整爬取，取消注释 crawl_all() 调用")
