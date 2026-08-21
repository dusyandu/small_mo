from DrissionPage import ChromiumPage
import time
# 微信推送工具：通过Server酱实现消息推送
# 安装方式：pip install serverchan_sdk
# 使用前需在 https://sct.ftqq.com/ 注册账号获取sendkey

# from serverchan_sdk import sc_send

# 理想价格阈值：当商品价格低于此值时触发推送通知
ideal_price = 4000

# 待监控的淘宝/天猫商品链接列表
# 支持同时监控淘宝（item.taobao.com）和天猫（detail.tmall.com）商品
product_urls = [
    # 淘宝商品链接示例
    "https://item.taobao.com/item.htm?ali_refid=a3_430673_1006%3A1212710161%3AH%3Awl4GnmH6%2BlErhuLrKUs1UMTvP3gQW7cW%3Ae9255654dcdce3654b24e5b7d328b6d5&ali_trackid=282_e9255654dcdce3654b24e5b7d328b6d5&id=738537272613&loginBonus=1&mi_id=0000vMruWBF6MyDQup7i-8fVfV5nGGUoanZ6O_gVTeu77u0&mm_sceneid=1_0_114463150_0&priceTId=213e02f717846200017666682e112f&skuId=5267347978592&spm=a21n57.sem.item.43&utparam=%7B%22aplus_abtest%22%3A%221cc09168149304c0d33494430385433e%22%7D&xxc=ad_ztc",
    "https://item.taobao.com/item.htm?ali_refid=a3_430673_1006%3A1266540190%3AH%3AaSo91lutoG9Zcy5HYEMZGQ%3D%3D%3A6190d2121886fb78069a1372e83f68db&ali_trackid=282_6190d2121886fb78069a1372e83f68db&id=794325077017&loginBonus=1&mi_id=0000LYDSBAL1tMMnENgUYayqZd2pd0O3M-Ie-JD-8P3SBSs&mm_sceneid=1_0_742820162_0&priceTId=2150456a17846216647825137e0fb9&skuId=5420508404634&spm=a21n57.sem.item.85&utparam=%7B%22aplus_abtest%22%3A%222226255d7f5646df6f0ad820e940d67b%22%7D&xxc=ad_ztc",
    # 天猫商品链接示例
    "https://detail.tmall.com/item.htm?ali_refid=a3_430673_1006%3A1699417437%3AH%3AZdGLOeauRTQnaemL8oW1Fg%3D%3D%3Ab61173d442d31d8ad8389a4e32e5e5a9&ali_trackid=282_b61173d442d31d8ad8389a4e32e5e5a9&fpChannel=101&fpChannelSig=d57f12dd1c31f7029650404639e16b218d6dc040&id=1008162228363&loginBonus=1&mi_id=0000Yo-6GMXnb9yV-dZNKU-tjCpfz82T_y_TeunIiuCFYzE&mm_sceneid=1_0_6364333054_0&priceTId=2150456a17846217078748890e0fb9&skuId=6115232953462&spm=a21n57.sem.item.86&u_channel=bybtqdyh&umpChannel=bybtqdyh&utparam=%7B%22aplus_abtest%22%3A%2265735bbbe2d8d5ad1dd57a62af06d3bd%22%7D&xxc=ad_ztc"
]


# 创建Chromium浏览器实例
page = ChromiumPage()

# 遍历所有商品链接，逐个获取商品数据
for p_url in product_urls:
    # 添加cookie后，重新访问商品页面
    page.get(p_url)
    time.sleep(2) # 这儿第一次登录也可以选择用input()来等待程序
    # 定位商品标题元素
    title = page.ele('xpath://span[@class="mainTitle--R75fTcZL"]').text
    # 截取标题前15个字符
    title = title[:15]
    # 定位商品价格元素
    price = page.ele('xpath://div[@class="block2--MLcO9YdF"]//span[last()]').text
    print(f'你关注的{title}的价格是{price}')
    # 判断价格是否低于理想价格
    # price为字符串类型，需要转换为浮点数进行数值比较
    if float(price) < ideal_price:
        print("价格低于理想价格，立即购买")
        # 价格低于理想价格，通过Server酱推送微信消息
        # sc_send(
        #     # sendkey：在 https://sct.ftqq.com/ 登录后获取
        #     "SCT382432TAFggbULHnql1ToaCuqAaoWab",
        #     # 推送消息的标题
        #     f"你关注的{title}已降价",
        #     # 推送消息的描述信息，包含商品链接
        #     f"点击立即购买{p_url}"
        # )
    else:
        # 价格高于理想价格，仅输出提示信息
        print("价格高于理想价格，暂不购买")

    # 等待5秒，防止淘宝反爬虫机制
    page.wait(5)
# 关闭浏览器窗口
page.quit()
