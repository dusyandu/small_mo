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

#爬贝壳找房---大厂还是小厂？用什么方式 rq  dr

from DrissionPage import ChromiumPage
import pandas

page = ChromiumPage()
#打开网页
page.get('https://bj.ke.com/ershoufang/')
#打开网址先睡一会
page.wait(2)
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


#老板看看这种样式是否符合你的基本需求呢？图片后续我会更改保存在excel里
