
import requests
from lxml import etree # 提取标签的


# 提取十章，发10次请求，找到10个url
url = "https://www.diandingnnn.cc/ddk6500/" # 所有章节的请求网址
h = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36'
}
res = requests.get(url=url,headers=h)
# print(res.text) # 提取源码里面a标签的href网址
data = etree.HTML(res.text)
# data找xpath的a标签
# 目标内容没有名字，就逐层往上找，通过唯一的祖先来确定
aurl = data.xpath('//div[@class="listmain"]//dd/a/@href')
# 返回的前12章的最后12章，提取的从第一章开始，从列表中抽取真正从第一章开始的内容
# print(aurl[12:22]) #
count = 1 # 提示当前第几章
for i in aurl[0:1]: # 这里就是1-10章的内容
    print(f"当前提取第{count}章")
    # print(i) # i只有后半截，需要每个进行拼接
    #  https://www.diandingnnn.cc/ddk6500/4121230.html
    wzurl = "https://www.diandingnnn.cc"+i
    # 上面拿到了每个章节的完整网站，每个章节都要发请求
    detailres = requests.get(url=wzurl,headers=h)
    # print(detailres)
    # 每一章的响应内容
    dataildata = etree.HTML(detailres.text)
    # 提取每个章节标题 h1
    title = dataildata.xpath('//h1/text()')[0]
    # 提取正文
    zwdata = data.xpath('//div[@id="content"]/text()')
    zwdata = dataildata.xpath('//div[@id="content"]/text()')
    # print(zwdata)
    # 循环每个章节的列表文字，with  open
    for j in zwdata:
        # print(j) # j就是每一句话
        # with open 每一句话  每个文档的文件名，就用章节名
        with open(f"{title}.txt","a",encoding="utf-8") as f:
            f.write(j+"\n")
    count = count + 1 # 提示内容每循环一次就递增


# os自动创建文件夹的功能，后面再用
'''
总结：
1.多章先找多章url
2.循环每个url,拼接每个完整的网站
    每个章节发请求
    后面的代码就和第一章的提取方式一模一样
漫画网站可验证成果：http://whcybg.com/read/239/9064/1.html    
'''














