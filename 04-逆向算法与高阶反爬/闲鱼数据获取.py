import requests
import time
import jsonpath #需要安装  pip install jsonpath
import csv
import hashlib
import json

search = '篮球鞋'
# cookie = '此处置换为你自己的闲鱼cookie（登录 goofish.com 后从浏览器开发者工具复制）'
cookie = "此处置换为你自己的闲鱼cookie（必须包含 _m_h5_tk / sgcookie / tfstk 等字段，否则 sign 计算会失败）"
send_url="https://h5api.m.goofish.com/h5/mtop.taobao.idlemtopsearch.pc.search/1.0/"

#伪装请求头
send_h={
    "user-agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "referer":"https://www.goofish.com/",
    'cookie': cookie
}
# 先将搜索关键词放到字典中
payload = {
    "pageNumber":1,
    "keyword": search,
    "fromFilter":False,
    "rowsPerPage":30,
    "sortValue":"",
    "sortField":"",
    "customDistance":"",
    "gps":"",
    "propValueStr":{},
    "customGps":"",
    "searchReqFromPage":"pcSearch",
    "extraFilterValue":"{}",
    "userPositionJson":"{}"
}
# 将字典数据转为json格式
c_data = json.dumps(payload)

# 获取sign【直接使用或让AI写】
def get_sign(cookie_str, c_data):
    # 1. 提取最后一个 _m_h5_tk token
    pairs = cookie_str.split("; ")
    token_list = []
    for item in pairs:
        if item.startswith("_m_h5_tk="):
            value = item.split("=", 1)[1]
            tk = value.split("_")[0]
            token_list.append(tk)
    if not token_list:
        raise ValueError("Cookie 内未找到 _m_h5_tk 字段！")
    d_token = token_list[-1]

    # 2. 生成13位毫秒时间戳
    t = str(int(time.time() * 1000))
    h = "34839810"

    # 3. 拼接原始串
    raw_sign_str = f"{d_token}&{t}&{h}&{c_data}"

    # 4. MD5加密得到sign
    md5 = hashlib.md5()
    md5.update(raw_sign_str.encode("utf-8"))
    sign = md5.hexdigest()

    return t, sign

t,sign = get_sign(cookie, c_data)

# 【构建查询字符串参数】注意将t 和 sign 改为动态生成的
xy_params={
    'jsv': '2.7.2',
    'appKey': '34839810',
    't': t,#动态生成
    'sign':sign , #动态生成
    'v': '1.0',
    'type': 'originaljson',
    'accountSite': 'xianyu',
    'dataType': 'json',
    'timeout': '20000',
    'api': 'mtop.taobao.idlemtopsearch.pc.search',
    'sessionOption': 'AutoLoginOnly',
    'spm_cnt': 'a21ybx.search.0.0',
    'spm_pre': 'a21ybx.search.searchInput.0'
}


#【构建表单数据】
datas={
    "data": c_data
}

#发起post请求，携带参数
res=requests.post(url=send_url,headers=send_h,params=xy_params,data=datas)
print(res.text)

# 将json数据转换为python数据
resdata=res.json()

# 通过jsonpath---》跨层级找到excontent--->$..
exContent=jsonpath.jsonpath(resdata,'$..exContent')

#定义一个空列表用于存储数据
all_data=[]
for i in exContent:
    #提取地址
    try:
        area=i["area"]
        # 提取价格
        price=i["detailParams"]['soldPrice']
        # 提取标题
        title=i["detailParams"]['title'][:15]
    
        #每循环一次就添加一次
        all_data.append([title,area,price])
    except:
        pass
    
    
"""
【保存数据】
"""
with open('闲鱼数据_篮球鞋.csv', "w", newline="", encoding="utf-8") as f:
    cf = csv.writer(f)
    # 表头
    cf.writerow(["地址","价格"])
    # 要存的数据
    cf.writerows(all_data)


#注意事项：sign里面的token必须和请求头的cookie一致
#注意事项；sign里面用的data必须和请求上面的data一样
