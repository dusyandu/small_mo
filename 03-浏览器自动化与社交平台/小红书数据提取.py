#小红书自动化爬取内容

from DrissionPage import ChromiumPage
import os,time,csv

#创建一个文件夹，如果文件夹存在，就不做任何事情；不存在就创建这个文件夹
filename = '大蓝书数据'
if os.path.exists(filename):
    pass #什么都不做，就是为了防止程序报错
else:
    os.makedirs(filename)

kw = input('请输入您要搜索的小红书内容:')
#创建浏览器对象
page = ChromiumPage()
#启动浏览器的时候就开启监听模式，开启之后，这个网页有什么变化都需要返回给我
page.listen.start("https://so.xiaohongshu.com/api/sns/web/v2/search/notes",method='POST')
#访问小红书
page.get(f"https://www.xiaohongshu.com/search_result_ai?keyword={kw}&source=web_explore_feed")

#先睡一会，等待网址加载完毕
time.sleep(3)
#定义一个空的列表，往里面去追加内容
allData = []
#访问里面的数据，需要不断的下拉，这个内容才会更多
for i in range(20):
    print(f'滚动的第{i+1}次')
    #让屏幕往下滑动
    page.scroll.to_bottom()
    time.sleep(1)
    #只要内容往后滑动，那么界面就会变化，就返回给我内容
    res = page.listen.wait()
    #我们看一看接受没接受到内容
    result = res.response.body
    #我们接受到的内容就是一个字典
    items = result['data']['items']
    #使用循环，提取里面的所有内容
    #items是帖子的列表  item是每一条帖子
    for item in items:
        try:
            #先取出id
            id = item['id']
            token = item['xsec_token']
            #取出标题
            title = item['note_card']['display_title']
            #取出作者昵称和头像
            name = item['note_card']['user']['nickname']
            avatar = item['note_card']['user']['avatar']

            #点赞、收藏、评论，分享数
            comment_count = item['note_card']['interact_info']['comment_count']
            shared_count = item['note_card']['interact_info']['shared_count']
            liked_count = item['note_card']['interact_info']['liked_count']
            collected_count = item['note_card']['interact_info']['collected_count']
            # print(comment_count,shared_count,liked_count,collected_count)

            #先增加一行标题
            allData.append([id,token,title,name,avatar,liked_count,collected_count,comment_count,shared_count])
        except Exception as e:
            print('程序报错了，错误的原因是', e)
# print(allData)

with open(f'{filename}/大蓝书数据.csv','w',newline="",encoding='utf-8') as f:
    #这行代码，直接复制粘贴，不需要修改
    cf = csv.writer(f)
    cf.writerow(['id','token','标题','name','头像','点赞','收藏','评论','分享'])
    cf.writerows(allData)



