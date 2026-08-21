# 整个项目25行爬vip
import requests
# 导入xpath工具
from lxml import etree
import json
# 网址  一级页面拿所有歌曲的a标签，网址，所有歌曲详情页的网址
url = "https://www.gequbao.com/s/%E5%91%A8%E6%9D%B0%E4%BC%A6"
# 请求头
# 定义请求头，模拟浏览器访问
headers = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
}
# 发请求
res = requests.get(url=url, headers=headers)
# print(res.text) 字符串类型转为html标签
data = etree.HTML(res.text)
# 找a标签xpath  类名叫col-9 col-md-8每个div就是每首歌
info = data.xpath('//div[@class="col-9 col-md-8"]') # [112]
# print(len(info)) # 每首歌都要提取歌名，歌手，a标签链接
#循环上面每首歌列表
for i in info[0:3]:
    # 提取歌名
    title = i.xpath('.//span/text()')[0]
    # 清除两边空格
    title = title.strip()
    print(f"正在下载{title}这首歌")
    # i就是当前每个div
    # 先找链接
    aurl = i.xpath('./a/@href')[0]
    # 详情页网址：https://www.gequbao.com/music/39466
    # a的半截网址：
    # 拼接完整详情页网址
    zwurl = "https://www.gequbao.com"+aurl
    '''
    # 找到真正这首歌的下载网址
    # 每首歌详情页 play-url就能找到返回的下载地址
    # post请求：更安全一点，携带数据发请求，数据，不会直接暴露在url上，
    # 下载歌曲的请求网址都一样，携带每首歌不同的id值
    # 找唯一id来源
    # 这一个就是id的来源 ： https://www.gequbao.com/music/8475848
    '''
    zwdata = requests.get(url=zwurl,headers=headers)
    # print(zwdata.text) # 提取id 源码里面替换为引号
    resdata = zwdata.text.replace('\\u0022','"')
    # 通过唯一性来分割两份
    news = resdata.split('"play_id":"')[1] # 所有源码分成两块，0和1的索引，id应该右边1的那块
    # 继续用"来分割，第一个内容索引为0就是最干净的id
    pid = news.split('"')[0]
    # print(pid)
    # playurl网址就是下载地址
    # 就可以携带这个唯一id去发请求下载了 发post请求
    # 使用id
    data = {
        "id":pid
    }
    u = "https://www.gequbao.com/api/play-url"
    gequ = requests.post(url=u,headers=headers,data=data)
    # print(gequ.text) # 看响应结果，里面有音乐的下载地址
    # 返回的json就用json库转为字典
    gequdata = json.loads(gequ.text)
    # 可以提取url了
    musicurl = gequdata["data"]["url"]
    # 请求并保存
    mures = requests.get(url=musicurl,headers=headers)
    # with  open保存
    with open(f"{title}.mp3","wb") as f:
        f.write(mures.content)



# 30行不到

















