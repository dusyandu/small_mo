from DrissionPage import ChromiumPage
from 滑块验证码识别 import drag_verify
from 文字定位验证 import text_verify

page = ChromiumPage()
page.get('https://www.zhihu.com/')
page.wait(3)  # 等待页面加载

# 2. 执行登录操作
page.ele('.SignFlow-tab').click()  # 点击“密码登录”标签
page.ele('xpath://input[@name="username"]').input('3920682002@qq.com')  # 输入手机号或邮箱
page.ele('xpath://input[@name="password"]').input('Aa123456789')  # 输入密码
page.ele('xpath://button[@type="submit"]').click()  # 点击登录按钮

max_count = 10
# 循环不断地尝试登录，如果出现问题，就跳过本次循环，继续下次循环
for count in range(1, max_count + 1):
    print(f'\n===== 第 {count} 次尝试 =====')

    try:
        # 先尝试滑块验证码
        bool_result = drag_verify(page)
        # 如果返回的布尔值为False, 就证明不是滑块验证
        # 尝试文字验证
        if not bool_result:
            text_verify(page)
        # 判断有没有登录成功(如果没有头像，点击头像会报错，则表示未登录)
        page.ele('.Avatar AppHeader-profileAvatar css-d9tvwx',timeout=3).click()
        break
    except:
        page.get('https://www.zhihu.com/')
        page.wait(3)  # 等待页面加载

        # 2. 执行登录操作
        page.ele('.SignFlow-tab').click()  # 点击“密码登录”标签
        page.ele('xpath://input[@name="username"]').input('3920682002@qq.com')  # 输入手机号或邮箱
        page.ele('xpath://input[@name="password"]').input('Aa123456789')  # 输入密码
        page.ele('xpath://button[@type="submit"]').click()  # 点击登录按钮
        continue