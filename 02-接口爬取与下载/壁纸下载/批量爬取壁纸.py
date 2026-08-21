'''
需求：爬取批量壁纸
'''
#
from lxml import etree
import requests
# 定义请求网址
url = "https://bizhi1.com/"
# 定义请求头
h = {
    "user-agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
}
# 发请求
res = requests.get(url=url,headers=h)
# print(type(res.text)) # 返回的是整个页面的完整内容，需要从中提取目标的图片的内容
# 完整的html源码，
# 将返回的所有html转为html节点类型
htmldata = etree.HTML(res.text)
# 提取网页上所有的img标签
imgs = htmldata.xpath('//img[@class="attachment-post-thumbnail size-post-thumbnail spc wp-post-image"]')
# print(imgs) # 更加精确重要中间的图片
# 循环上面的每个img
for i in imgs:
    # 继续提取网址，提取图片名称  [url1]  [url2] [url3]
    imgurl = i.xpath('./@src')[0] # src对应的就是网址
    imgname = i.xpath('./@alt')[0] # 对应的就是名字
    # 通过网址下载图片
    # print(imgurl) # 需要再次发送请求，再with open()
    resimg = requests.get(url=imgurl,headers=h)
    # with open保存了  imgs文件夹就叫这个名字自己创好
    with open(f"imgs/{imgname}.png","wb") as f:
        f.write(resimg.content)
print("下载完毕")
'''
1.用xpath定位目标的img标签，返回的标签在一个列表里 ，[很多个img]
2.循环列表，找到每张图
    提取每个图的名字 网址
3.根据网站发请求，
4.with open()保存    
'''






