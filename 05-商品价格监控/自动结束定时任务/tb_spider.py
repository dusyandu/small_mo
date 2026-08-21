from DrissionPage import ChromiumPage
from serverchan_sdk import sc_send
import os  # 新增导入

# ==================== 配置区 ====================
ideal_price = 4300
product_urls = [
    "https://item.taobao.com/item.htm?ali_refid=a3_430673_1006%3A1212710161%3AH%3Awl4GnmH6%2BlErhuLrKUs1UMTvP3gQW7cW%3Ae9255654dcdce3654b24e5b7d328b6d5&ali_trackid=282_e9255654dcdce3654b24e5b7d328b6d5&id=738537272613&loginBonus=1&mi_id=0000vMruWBF6MyDQup7i-8fVfV5nGGUoanZ6O_gVTeu77u0&mm_sceneid=1_0_114463150_0&priceTId=213e02f717846200017666682e112f&skuId=5267347978592&spm=a21n57.sem.item.43&utparam=%7B%22aplus_abtest%22%3A%221cc09168149304c0d33494430385433e%22%7D&xxc=ad_ztc",
    "https://item.taobao.com/item.htm?ali_refid=a3_430673_1006%3A1266540190%3AH%3AaSo91lutoG9Zcy5HYEMZGQ%3D%3D%3A6190d2121886fb78069a1372e83f68db&ali_trackid=282_6190d2121886fb78069a1372e83f68db&id=794325077017&loginBonus=1&mi_id=0000LYDSBAL1tMMnENgUYayqZd2pd0O3M-Ie-JD-8P3SBSs&mm_sceneid=1_0_742820162_0&priceTId=2150456a17846216647825137e0fb9&skuId=5420508404634&spm=a21n57.sem.item.85&utparam=%7B%22aplus_abtest%22%3A%222226255d7f5646df6f0ad820e940d67b%22%7D&xxc=ad_ztc",
    "https://detail.tmall.com/item.htm?ali_refid=a3_430673_1006%3A1699417437%3AH%3AZdGLOeauRTQnaemL8oW1Fg%3D%3D%3Ab61173d442d31d8ad8389a4e32e5e5a9&ali_trackid=282_b61173d442d31d8ad8389a4e32e5e5a9&fpChannel=101&fpChannelSig=d57f12dd1c31f7029650404639e16b218d6dc040&id=1008162228363&loginBonus=1&mi_id=0000Yo-6GMXnb9yV-dZNKU-tjCpfz82T_y_TeunIiuCFYzE&mm_sceneid=1_0_6364333054_0&priceTId=2150456a17846217078748890e0fb9&skuId=6115232953462&spm=a21n57.sem.item.86&u_channel=bybtqdyh&umpChannel=bybtqdyh&utparam=%7B%22aplus_abtest%22%3A%2265735bbbe2d8d5ad1dd57a62af06d3bd%22%7D&xxc=ad_ztc"
]
# ================================================
def run_price_check():
    page = ChromiumPage()
    alert_triggered = False  # 标记是否触发降价推送
    for p_url in product_urls:
        try:
            page.get(p_url)
            page.wait(10)
            # 获取产品标题
            title = page.ele('xpath://span[@class="mainTitle--R75fTcZL"]').text
            # 标题太长，取前几个字符
            title = title[:15]
            # 获取产品价格
            price = page.ele('xpath://div[@class="block2--MLcO9YdF"]//span[last()]').text
            print(f'你关注的{title}的价格是{price}')
            
            # 修复：去除¥符号转数字
            clean_price = float(price.replace("¥", ""))
            if clean_price < ideal_price:
                print(f"【降价达标】{title}低于心理价，推送微信！")
                # 推送微信消息
                sc_send(
                    "SCT382432TAFggbULHnql1ToaCuqAaoWab",
                    f"你关注的{title}已降价",
                    f"现价：{clean_price}元\n点击立即购买{p_url}"
                )
                alert_triggered = True
                # 新增：生成停止标记文件
                with open("stop_signal.txt", "w", encoding="utf-8") as f:
                    f.write("stop")
                break  # 跳出商品循环，不用再检测剩下商品
            else:
                print("价格高于理想价格，暂不提醒")
        except Exception as e:
            print(f"检测链接{p_url}出错：{str(e)}")
    page.quit()
    # 返回标记给定时程序，用来判断是否停止定时
    return alert_triggered

# 新增：程序入口，运行脚本自动执行检测函数
if __name__ == "__main__":
    run_price_check()