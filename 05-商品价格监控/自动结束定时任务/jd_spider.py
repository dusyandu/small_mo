from DrissionPage import ChromiumPage
from serverchan_sdk import sc_send
import os  # 新增导入

# ==================== 配置区 ====================
ideal_price = 4300
product_urls = [
    "https://item.jd.com/100359969926.html",
    "https://item.jd.com/100105522236.html",
    "https://item.jd.com/100257373973.html"
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
            title = page.ele('xpath://span[@class="sku-title-name"]').text
            # 获取产品价格
            price_text = page.ele('xpath://span[@class="product-price--value"]').text
            print(f'你关注的{title}的价格是{price_text}')
            
            # 修复：去除¥符号转数字
            clean_price = float(price_text.replace("¥", ""))
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