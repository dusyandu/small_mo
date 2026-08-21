import time
from pathlib import Path

from chaojiying import Chaojiying_Client
from DrissionPage import ChromiumPage
from PIL import Image

BG_PATH = Path(__file__).with_name('bg.png')
CLICK_MOVE_SECONDS = 0.5
CLICK_INTERVAL_SECONDS = 1


def get_image_size(image_path):
    """按文件真实内容读取尺寸，不依赖文件扩展名。"""
    try:
        with Image.open(image_path) as image:
            print(f'验证码实际图片格式: {image.format}')
            return image.size
    except (OSError, ValueError) as error:
        raise ValueError(f'无法读取验证码图片: {error}') from error


def parse_points(pic_str):
    """把“x,y|x,y”格式的图片坐标转换为数值坐标。"""
    points = []
    for point_text in pic_str.split('|'):
        x_text, y_text = point_text.split(',', 1)
        points.append((float(x_text), float(y_text)))
    return points


def click_captcha_points(page, captcha_element, points, image_size):
    """将图片坐标缩放为验证码元素内部偏移后依次点击。"""
    image_width, image_height = image_size
    display_width, display_height = captcha_element.rect.size
    if image_width <= 0 or image_height <= 0:
        raise ValueError('验证码图片尺寸无效')

    scale_x = display_width / image_width
    scale_y = display_height / image_height
    element_x, element_y = captcha_element.rect.location
    print(
        f'验证码图片尺寸: {image_width}x{image_height}，'
        f'页面显示尺寸: {display_width:.1f}x{display_height:.1f}'
    )

    for index, (image_x, image_y) in enumerate(points, start=1):
        offset_x = image_x * scale_x
        offset_y = image_y * scale_y
        if not (0 <= offset_x <= display_width and 0 <= offset_y <= display_height):
            raise ValueError(f'第 {index} 个识别坐标超出验证码范围: {image_x},{image_y}')

        absolute_x = element_x + offset_x
        absolute_y = element_y + offset_y
        print(
            f'第 {index} 个坐标: 图片({image_x:.1f}, {image_y:.1f}) -> '
            f'元素偏移({offset_x:.1f}, {offset_y:.1f}) -> '
            f'页面坐标({absolute_x:.1f}, {absolute_y:.1f})'
        )

        # 传入元素及内部偏移，DrissionPage 会自动处理页面滚动和视口坐标。
        page.actions.move_to(
            captcha_element,
            offset_x=offset_x,
            offset_y=offset_y,
            duration=CLICK_MOVE_SECONDS,
        ).click()
        time.sleep(CLICK_INTERVAL_SECONDS)


def text_verify(page=None):
    # # 1. 初始化浏览器并访问知乎
    if page is None:
        page = ChromiumPage()
        page.get('https://www.zhihu.com/')
        page.wait(3)  # 等待页面加载

        # 2. 执行登录操作
        page.ele('.SignFlow-tab').click()  # 点击“密码登录”标签
        page.ele('xpath://input[@name="username"]').input('3920682002@qq.com')  # 输入手机号或邮箱
        page.ele('xpath://input[@name="password"]').input('Aa123456789')  # 输入密码
        page.ele('xpath://button[@type="submit"]').click()  # 点击登录按钮

    # return
    # 3. 获取验证码图片并保存
    bg_img = page.ele('.yidun_bg-img')  # 定位背景图元素
    # 将背景图保存为本地文件, 并重新命名
    BG_PATH.unlink(missing_ok=True)
    bg_img.save(path=str(BG_PATH.parent), name=BG_PATH.name, rename=False)

    text = page.ele('.yidun_tips__point').text
    text = text.replace(' ', ',').replace('"', "")
    print(text)

    chaojiying = Chaojiying_Client('tiantian991', '8nvz3u4t', '96001')
    # 读取刚刚保存的文字验证码
    with BG_PATH.open('rb') as f:
        # 使用超级鹰的chaojiying.PostPic方法识别滑块缺口位置，
        # f.read()是在传入读取到的图片数据,9901是专门用来识别滑块图的模式
        # result中的pic_str就是缺口的位置
        result = chaojiying.PostPic(f.read(), 9801, f'{{8a:{text}/8a}}')

    try:
        pic_str = result.get('pic_str', '')
        if not pic_str:
            raise ValueError(f'文字验证码识别失败: {result!r}')

        points = parse_points(pic_str)
        image_size = get_image_size(BG_PATH)
        click_captcha_points(page, bg_img, points, image_size)
        return True
    except (KeyError, TypeError, ValueError, OSError) as error:
        print(f'文字验证码点击失败: {error}')
        return False
    finally:
        BG_PATH.unlink(missing_ok=True)


if __name__ == "__main__":
    text_verify()
