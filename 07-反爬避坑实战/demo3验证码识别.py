'''
谈价格阶段：
1、数据量多少条？？
2、有没有具体的搜索内容要求
3、要不要图片
4、网页的复杂程度--多层网址结构，也得加钱
5、有没有反爬


详细沟通--防止踩坑的阶段：
1、一定问清楚具体的条数
2、沟通图片的保存形式
3、一定先发截图和列名是否符合要求，给了钱之后，再交付全部的数据文件
4、是否提供账号？？？？能提供最好，不提供，可以谈一谈能不能加点钱(大多数情况用自己的)
闲鱼个人商家---挂链接挂低价---这个是定金---后续看了数据是否符合标准以后--结尾款发文件

'''
import time

#爬贝壳找房---大厂还是小厂？用什么方式 rq  dr

from DrissionPage import ChromiumPage
import pandas

from tools.add_image import add_images_to_excel
from tools.captcha_solver import crack_captcha

page = ChromiumPage()
#打开网页
page.get('https://bj.ke.com/ershoufang/pg5/')

#把这个网页放入我们的人机验证板块：文字顺序，按照图片点击顺序，单一滑块不能用
#一定要用自己的用户名和密码
crack_captcha(page)

#打开网址先睡一会
page.wait(2)

#页面滚动 学会调整参数即可
for i in range(30):
    #这里可以设置横向和纵向滚动，1是纵向滚动
    height = page.rect.scroll_position[1]
    #向下每次滚动500个像素
    page.scroll.down(500)
    #给点时间让页面加载图片
    time.sleep(0.3)
    #如果滚动前后的位置相同。说明页面达到的底部
    if height == page.rect.scroll_position[1]:
        break


#定义一个存储列表
all_data = []
#找用户需要的所有数据
lis = page.eles('xpath://ul[@class="sellListContent"]/li[@class="clear"]')
for li in lis:
    info = {
        "标题": li.ele('xpath:.//div[@class="title"]/a').text,
        "地址": li.ele('xpath:.//div[@class="positionInfo"]/a').text,
        "描述": li.ele('xpath:.//div[@class="houseInfo"]').text,
        "总价": li.ele('xpath:.//div[@class="totalPrice totalPrice2"]/span').text,
        "单价": li.ele('xpath:.//div[@class="unitPrice"]/span').text,
        "关注度":li.ele('xpath:.//div[@class="followInfo"]').text,
        "详情网址": li.ele('xpath:./a').attr('href'),
        #找属性，用.attr来获取
        "图片网址": li.ele('xpath:.//img[@class="lj-lazy"]').attr('src')
    }
    all_data.append(info)

#还要保存下来，给用户去看一眼，是不是这样的格式  xlsx   .csv
df = pandas.DataFrame(all_data)
df.to_excel('给用户看一眼的基本数据格式.xlsx',index=False)
#传入excel表格，并取出图片链接这一列内容
add_images_to_excel('给用户看一眼的基本数据格式.xlsx',pandas.DataFrame(all_data)['图片网址'],'H')
#老板看看这种样式是否符合你的基本需求呢？图片后续我会更改保存在excel里
