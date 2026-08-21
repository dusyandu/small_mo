from DrissionPage import ChromiumPage
import csv

# 定义空列表，用于存储所有爬取到的任务数据
# 列表中的每个元素是一个字典，对应一条任务记录
all_datas = []

# 创建浏览器对象，会启动一个真实的Chromium浏览器窗口
page = ChromiumPage()

# 设置每个关键词要爬取的最大页数
page_count = 5

# ==================== 1. 翻页爬取循环 ====================
# 从第1页到第page_count页循环，每页提取任务数据
# range(1, page_count + 1) 生成包含1到page_count的整数序列
for p in range(1, page_count + 1):
    # 打开猿急送网站的后端工程师分类页面
    # URL格式：https://www.yuanjisong.com/job/allcity/houduan/page{p}
    # {p} 表示当前页码，从1开始
    page.get(f'https://www.yuanjisong.com/job/allcity/houduan/page{p}')

    # 等待10秒，确保页面完全加载
    page.wait(10)

    # ==================== 2.获取当前页任务列表 ====================
    # 定位所有任务卡片元素，返回一个元素列表
    # 【注意】标签名最后有空格，这是网站HTML结构的特点
    # 列表中每个元素对应一个任务卡片
    items = page.eles('xpath://div[@class="div_bg_color_fff div_padding_1 hover1 margin_bottom_1 "]')

    # 循环遍历每个任务卡片，提取详细信息
    for i in items:  # i 代表当前遍历的任务卡片元素
        # 提取任务标题
        title = i.ele('xpath:.//b').text
        # 提取任务价格
        price = i.ele('xpath:.//span[@class="rixin-text-jobs font-size-8 margin-r-2"]').text
        # 提取需求分类
        classify = i.ele('xpath:.//div[@class="consultant_title margin_top_15"]/p[1]/span[3]').text
        # 提取任务描述
        content = i.ele('xpath:.//p[@class="margin_bottom_10"]').text
        # 提取任务状态文本
        status = i.ele('xpath:.//div[@class="weui_panel_bd margin_top_10"]').text
        # 提取任务详情页面的URL链接
        url = i.ele('xpath:.//div[@class="consultant_title margin_top_15"]/a/@href')

        # 将当前任务的数据字典添加到全局数据列表中
        # 每循环一次，all_datas列表就增加一条任务记录
        all_datas.append(['后端工程师',title,status,price,classify,content,url])

# 爬取完成后，关闭浏览器窗口
page.quit()

# ==================== 3.保存数据到CSV文件（数据追加模式） ====================
with open("猿急送网站数据.csv","w",newline="",encoding="utf-8") as f:
    cf = csv.writer(f)
    # 表头
    cf.writerow(["关键词","标题","状态","价格","需求分类","描述","详情链接"])
    # 要存的数据
    cf.writerows(all_datas)

print(f"数据爬取完成！共获取 {len(all_datas)} 条任务数据，已保存到猿急送网站数据.csv")
