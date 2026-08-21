from tools.chaojiying import Chaojiying_Client
from DrissionPage import ChromiumPage
from DrissionPage.common import Actions

def drag_verify(page):
    # # 1. 初始化浏览器并访问知乎
    # page = ChromiumPage()
    # page.get('https://www.zhihu.com/')
    # page.wait(3)  # 等待页面加载
    #
    # # 2. 执行登录操作
    # page.ele('.SignFlow-tab').click()  # 点击“密码登录”标签
    # page.ele('xpath://input[@name="username"]').input('3920682002@qq.com')  # 输入手机号或邮箱
    # page.ele('xpath://input[@name="password"]').input('Aa123456789')  # 输入密码
    # page.ele('xpath://button[@type="submit"]').click()  # 点击登录按钮
    #
    # # 3. 获取验证码背景图并保存(背景图上有缺口，需要保存之后使用超级鹰的方法来识别缺口位置, 这样才能直到要将滑块滑到哪个位置)
    bg_img = page.ele('.yidun_bg-img')  # 定位背景图元素
    # 将背景图保存为本地文件, 并重新命名
    bg_img.save(name='bg.png', rename=False)


    # 4. 【计算拖动距离】找到要拖动的滑块，将滑块移动到缺口位置
    # 4.1 找到要拖动的滑块
    slider = page.ele('.yidun_jigsaw')

    # 4.2 使用超级鹰的方法,识别缺口在图片内的坐标
    # 换成自己的超级鹰账号和密码, 96001可不改
    chaojiying = Chaojiying_Client('tiantian991', '8nvz3u4t', '96001')
    # 读取刚刚保存的背景图
    with open('bg.png', 'rb') as f:
        # 使用超级鹰的chaojiying.PostPic方法识别滑块缺口位置，
        # f.read()是在传入读取到的图片数据,9901是专门用来识别滑块图的模式
        # result中的pic_str就是缺口的位置
        result = chaojiying.PostPic(f.read(), 9901)
        # print(result) {'err_no': 0, 'err_str': 'OK', 'pic_id': '2330620092252970036', 'pic_str': '261,60', 'md5': 'b9af18240aaebce8981e0f8bd2b51506'}

    # 解析识别结果，获取缺口相对于保存的背景图的X坐标
    # 得到的result是个字典，需要的数据在字典的pic_str中, result['pic_str']获取对应的值，得到'261,60'
    # '261,60', 261是缺口在背景图中x轴的位置, .split(',')表示将'261,60'从,分割成两部分，得到的结果是[261,60]
    # [0]就是取列表的第一个，获取缺口的位置
    blank_x = int(result['pic_str'].split(',')[0])
    print(f'识别缺口X坐标: {blank_x}')

    # 滑动滑块函数【直接使用】
    # 【参数说明】
    # drag_ele：要拖动的滑块位置
    # blank_distance：缺口x坐标
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
        # 使用函数，滑动滑块
        drag_slider(slider, blank_x)
        return True
    except:
        return False


if __name__ == "__main__":
    drag_verify()