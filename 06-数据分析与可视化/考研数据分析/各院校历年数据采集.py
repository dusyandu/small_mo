import requests
import time
import random
import pandas as pd #导入pandas 取个别名叫做pd

"""【第一请求】
1. 打开官网：https://www.kaoyan.cn/school-list/0-0-0
2. 从网络中分析学校列表来源
"""
#【确定目标地址】
send_url="https://api.kaoyan.cn/pc/school/schoolList"

# 【请求头】
send_h={
    "user-agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "referer":"https://www.kaoyan.cn/",
}

#【post请求携带的参数】
send_data={
    "page": 1,
    "limit": 20,
    "province_id": "11",
    "type": "",
    "feature": "",
    "school_name": ""
}
# 【发post请求】
res=requests.post(url=send_url,headers=send_h,data=send_data)

"""【直接使用json()】
print(res.text) #返回的格式---》json字符串格式---》转为字典格式
"""
resdata=res.json()


#【提取目标数据】 提取存放所有学校信息的列表
xxlist=resdata["data"]["data"]


# 【定义空列表】用于存放下面构建好的学校数据
all_data=[]

# 【循环学校信息】
for xx in  xxlist:
    # 【学校名字】
    xname=xx["school_name"]

    # 【学校id】从第一个请求中提取学校id
    xid = xx["school_id"]


    for i in range(2023,2027):
    # 获取学校更详细信息
        url = "https://api.kaoyan.cn/pc/school/schoolScore"
        data = {
            "degree_type": "",
            "school_id": xid,
            "year":i
        }
        res = requests.post(url=url, headers=send_h, data=data)
        resdata = res.json()

        # 提取数据
        for x in resdata["data"]:
            data = {
                "学校": xname,
                "专业": x["name"],
                "代码": x["code"],
                "招生院系": x["depart_name"],
                "总分": x["total"],
                "政治": x["english"],
                "外语": x["politics"],
                "专业课一": x["special_one"],
                "专业课二": x["special_two"],
                "录取年份": x["year"]
            }
            print(data)
            all_data.append(data)

    time.sleep(random.randint(1,3))

# 【保存数据为csv】
df=pd.DataFrame(all_data)
df.to_csv("各院校历年数据采集.csv",index=False)


