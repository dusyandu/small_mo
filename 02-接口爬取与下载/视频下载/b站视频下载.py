# 寻找url
import requests
import re # 正则的库，作用，匹配符合的字符串内容
from moviepy import VideoFileClip # 合并的库安装 pip  install moviepy
import os # 操作文件路径，删除文件
import datetime

# url = "https://www.bilibili.com/video/BV1RwdhBmE3M/?spm_id_from=333.337.search-card.all.click&vd_source=130df2be2bfd553a06c2aa0aac175c92"

# 请求头,继续加权重伪装，
h = {
    "user-agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
    "cookie":"此处置换为你自己的B站cookie（需含 SESSDATA / bili_jct / DedeUserID，登录 bilibili.com 后从浏览器复制）",
    "referer":"https://search.bilibili.com/all?"
}
# 找多个视频的规律
# 多招几个url，来拼接
urllist = [
    "BV1RwdhBmE3M",
    "BV1UXv1eoEr2",
    "BV1vuRbB3Evd",
]
# 自动创建文件夹
dirpath = "B站下载视频"
f = os.path.exists(dirpath)
if f:
    print("文件夹有了")
else:
    os.makedirs(dirpath)

# 循环拼接
count = 1
for i in urllist[0:2]:
    print(f"开始下载第{count}个视频")
    count = count+1
    u = f'https://www.bilibili.com/video/{i}/?spm_id_from=333.337.search-card.all.click&vd_source=130df2be2bfd553a06c2aa0aac175c92'
    # print(u) # 就是每一个不同的完整链接
    res = requests.get(url=u, headers=h)
    # .任意一个数据  +?多个数据  .?任意多个 ()提取出来的意思
    rule = r'"baseUrl":"(.+?)"'
    result = re.findall(rule, res.text)
    videourl = result[0]  # [里面有画面和音频的所有url] 画面的url就是第一个
    # 画面就提取第一个，音频就提取最后一个,通过索引为-1统一提取最后一个
    audiourl = result[-1]
    # 请求下载  合并
    # 下载画面的
    resvideo = requests.get(url=videourl, headers=h)
    # print(resvideo)
    with open("demo.mp4", "wb") as f:
        f.write(resvideo.content)
    # 下载音乐
    resaudio = requests.get(url=audiourl, headers=h)
    with open("demo.mp3", "wb") as f:
        f.write(resaudio.content)

    # 合并
    # 1. 加载视频文件和音频文件
    video = VideoFileClip("demo.mp4")  # 先加载视频
    # 2.音频合并在一起
    # 生成唯一时间
    now1 = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    # 手动拼接一个完整的存放路径
    filepath = f"{dirpath}/{now1}.mp4"
    video.write_videofile(filepath, audio="demo.mp3")
    # 就把此次的辅助文件删了
    # os把辅助文件删了
    os.remove("demo.mp4")
    os.remove("demo.mp3")
    # 每循环一次，就先创建，再合并一次，使用完了就删了





