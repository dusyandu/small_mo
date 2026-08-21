from DrissionPage import ChromiumPage
import csv
import time

# 定义空列表，用于存储所有爬取到的任务数据
# 列表中的每个元素是一个字典，对应一条任务记录
all_datas = []

# 定义要搜索的关键词列表
input_works = ["爬虫", "python开发"]

# ==================== 多关键词循环爬取 ====================
# 遍历每个关键词进行爬取
for keyword in input_works:
    # 为每个关键词创建独立的浏览器对象
    page = ChromiumPage()

    # 设置每个关键词要爬取的最大页数
    page_count = 2

    # ==================== 1. 搜索数据流程 ====================
    # 打开猪八戒网首页，进入搜索入口
    page.get('https://www.zbj.com/')

    # 定位搜索框，输入当前关键词
    page.ele('xpath://input[@class="j-header-kw"]').input(keyword)

    # 点击搜索按钮
    page.ele('xpath://button[@class="btn-search"]').click()

    # 等待5秒，确保搜索结果页面完全加载
    page.wait(5)

    # 搜索结果会在新标签页打开,切换到搜索结果新开的标签页
    new_page = page.latest_tab

    # ==================== 2. 筛选需求 ====================
    # 点击"任务"分类标签，筛选出任务类型的需求
    new_page.ele('xpath://div[@class="tabs"]/a[3]').click()

    # ==================== 3.翻页爬取循环 ====================
    # 从第1页到第page_count页循环，每页提取任务数据
    # range(1, page_count + 1) 生成包含1到page_count的整数序列
    for p in range(1, page_count + 1):
        # 等待10秒，确保页面完全加载
        new_page.wait(10)

        # ==================== 4.获取当前页任务列表 ====================
        # 定位所有任务卡片元素，返回一个元素列表
        items = new_page.eles('xpath://div[@class="card-item-single"]')

        # 循环遍历每个任务卡片，提取详细信息
        for i in items:  # i 代表当前遍历的任务卡片元素
            # 提取任务标题
            title = i.ele('xpath:.//span[@class="task-names"]').text
            # 提取任务价格
            price = i.ele('xpath:.//div[@class="total-money"]').text
            # 提取需求分类
            classify = i.ele('xpath:.//span[@class="depict-refer"]').text
            # 提取任务描述
            content = i.ele('xpath:.//div[@class="contents-text"]').text
            # 提取任务状态（进行中/已完结）
            # 状态标签有两种不同的类名，用try-except处理
            try:
                # 先尝试查找"进行中"状态的标签
                # .status-box 是进行中状态的CSS类名
                status = i.ele('xpath:.//span[@class="status-box"]').text
            except:
                # 如果找不到进行中标签，说明是已完结状态
                # .status-box orange 是已完结状态的CSS类名
                status = i.ele('xpath:.//span[@class="status-box orange"]').text
            # 提取任务详情页面的URL链接
            url = i.ele('xpath:./a/@href')

            # 将当前任务的数据字典添加到全局数据列表中
            # 每循环一次，all_datas列表就增加一条任务记录
            all_datas.append([keyword, title, status, price, classify, content, url])


        # 等待1秒后再打开下一页
        time.sleep(1)

    # 关闭浏览器窗口
    page.quit()

# ==================== 5.保存数据到CSV文件 ====================
with open("猪八戒网站数据.csv","w",newline="",encoding="utf-8") as f:
    cf = csv.writer(f)
    # 表头
    cf.writerow(["关键词","标题","状态","价格","需求分类","描述","详情链接"])
    # 要存的数据
    cf.writerows(all_datas)

print(f"数据爬取完成！共获取 {len(all_datas)} 条任务数据，已保存到 csv文件")
