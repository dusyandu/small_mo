import os
from tools.chaojiying import Chaojiying_Client
from DrissionPage import ChromiumPage
from DrissionPage.common import Actions

page = ChromiumPage()

page.get('https://www.zhihu.com')
page.wait(3)

#执行输入用户名和密码的操作
page.ele('.SignFlow-tab').click() #先点击一下密码登录
page.ele('xpath://input[@name="username"]').input('3920682002@qq.com')
page.ele('xpath://input[@name="password"]').input('Aa123456789')
page.ele('xpath://button[@type="submit"]').click()

#开始进入到滑块环节
bg_img = page.ele('.yidun_bg-img') #背景图片
bg_img.save(name='bg.png',rename=False)
#再找滑块
huakuai = page.ele('.yidun_jigsaw')

chaojiying = Chaojiying_Client('超级鹰账号', '超级鹰密码', '96001')

#读取刚才的背景图片
with open('bg.png','rb') as f:
    #这个功能会把滑块的缺口坐标识别出来
    result = chaojiying.PostPic(f.read(),9901)
    # print(result['pic_str'])  #'247,74'
    blank_x = result['pic_str'].split(',')[0]
    print(blank_x)
#只需要传入对应的滑块，和缺口的x坐标，就可以直接使用老登的函数了
def drag_slider(drag_ele, blank_distance):
    # offset_x 为微调值，用于补偿识别误差
    # 三目运算符，如果缺口的x小于150的话, 微调值为10，否则，微调值为8
    offset_x = 10 if blank_distance < 150 else 8
    axis_x = blank_distance - offset_x
    print(f'计算得出的实际滑动距离: {axis_x}')

    # 模拟鼠标拖动滑块完成验证
    page.wait(3)  # 等待验证码加载完成
    ac = Actions(page)
    drag_ele.hover()  # 鼠标悬停在滑块上
    ac.hold(drag_ele)  # 按下鼠标
    ac.move(axis_x, 0)  # 水平移动计算出的距离(只需要横向移动)
    ac.release(drag_ele)  # 松开鼠标
try:
    drag_slider(huakuai,int(blank_x))
    #判断有没有登录成功
    page.ele('.Avatar AppHeader-profileAvatar css-d9tvwx',timeout=3).click()
except:
    print('出错了')

