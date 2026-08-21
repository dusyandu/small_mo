#识别平台 https://www.chaojiying.com/

from tools.chaojiying import Chaojiying_Client

#我们先来简单识别一张图片测试一下子 96001就是识别图片的编号
chaojiying = Chaojiying_Client('超级鹰账号','超级鹰密码','96001')

#我们就打开一张图片，然后去识别验证码
im = open('yzm.png','rb').read()
#超级鹰来帮我，识别内容
result = chaojiying.PostPic(im,1004) #1004就是识别图片的方法

print(result['pic_str'])
