import os
import sys
import subprocess
import threading
from apscheduler.schedulers.blocking import BlockingScheduler
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
# 【修改运行的文件名】
TARGET_SCRIPT = "jd_spider.py"
# TARGET_SCRIPT = "tb_spider.py"

# 全局缓存调度器实例
scheduler = None

def crawl_once():
    stop_file = os.path.join(PROJECT_DIR, "stop_signal.txt")
    # 如果存在直接退出，不再执行爬虫
    if os.path.exists(stop_file):
        print("检测到降价标记，停止定时任务")
        os.remove(stop_file)
        threading.Thread(target=scheduler.shutdown, kwargs={'wait': False}).start()
        return

    # 没有标记，正常执行爬虫脚本
    cmd = [sys.executable, TARGET_SCRIPT]
    result = subprocess.run(
        cmd,
        cwd=PROJECT_DIR,
        stdout=sys.stdout,
        stderr=sys.stderr
    )

    # 【关键改动】子进程执行完成后立即检查标记文件，实现当次检测到降价后立即停止调度器
    if os.path.exists(stop_file):
        print("检测到降价标记，立即停止定时任务")
        os.remove(stop_file)
        threading.Thread(target=scheduler.shutdown, kwargs={'wait': False}).start()

if __name__ == '__main__':
    scheduler = BlockingScheduler(timezone='Asia/Shanghai')
    # 【修改定时时间】
    scheduler.add_job(
        crawl_once,
        trigger='cron',
        hour=20,
        minute=46
    )
    print('APScheduler 定点监控已启动，每日9:30运行，降价推送后自动停止定时')
    try:
        scheduler.start()
    except KeyboardInterrupt:
        print('手动终止程序')