import pandas
from 数据分析服务 import ai_fenxi_and_report

#要分析爬下来的结果，先要读取csv文件
df = pandas.read_csv('各大院校历年分数线采集.csv')
#需要按照学校分组获取内容
xuexiao = df.groupby('学校')
#[(北京大学，北京大学),(清华大学，清华大学)]
for i in xuexiao:
    print(i[0])

#让用户输入想要选择的学校
xxname = input('请输入您想选择的院校:')

#列出该学校的所有专业，get_group就是获取你输入的学校名称的分组

zhuanye_list = xuexiao.get_group(xxname)['专业'].tolist()

for i in zhuanye_list:
    print(i)

zyname = input('请输入专业名称:')

#计算并展示目标院校的历年平均分数线，辅助用户合理评分
xuesheng_data = xuexiao.get_group(xxname)
#筛选专业的列值                       专业 == 管理学
zhuanye_data = xuesheng_data[xuesheng_data['专业']==zyname]
#取该专业的平均分  350+350+345+340/4
pingjunfen = zhuanye_data['总分'].mean()
#pingjunfen:.1f  保留一位小数
print(f'{xxname}的{zyname}历年平均分数线：{pingjunfen:.1f}分')

fenshu = float(input('请您输入您的预估分数:'))

#调用AI分析，控制台输出结果，生成HTML报告，自动打开浏览器
jieguo = ai_fenxi_and_report(xxname,zyname,fenshu)

