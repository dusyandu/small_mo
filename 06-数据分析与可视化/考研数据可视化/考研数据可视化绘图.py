#Bar柱形图，Line线形图，Pie饼状图，
from pyecharts.charts import Bar,Line,Pie,Page
import pandas
# options：pyecharts的配置模块，用于设置标题、坐标轴、标签等图表样式
from pyecharts import options as opts

"""
==================================================
读取数据并清洗
==================================================
"""
# 读取CSV数据文件
# read_csv：读取CSV文件，将表格数据转换为DataFrame对象
# DataFrame：pandas核心数据结构，用于保存二维表格数据
df = pandas.read_csv("各院校历年数据采集.csv")

# 删除总分缺失的数据，避免无效数据影响后续统计
# 条件筛选：通过布尔索引筛选满足条件的数据
# != 表示不等于，保留总分有效的数据
newdf = df[df["总分"] != "--"]
# 筛选2023年的招生数据，让所有图表保持同一年份的数据口径
newdf = newdf[newdf["录取年份"] == 2023]
# 将总分字段转换成整数类型，方便后续进行最大值、平均值等计算
# astype：数据类型转换方法
# 将字符串类型的分数转换为整数，方便后续计算最大值、平均值等
newdf["总分"] = newdf["总分"].astype(int)

"""
==================================================
图4：招生人数排行TOP10学校

分析目的：查看哪些学校招生规模最大。
==================================================
"""
# 按学校统计招生记录数量，并获取招生人数最多的10所学校
school_count = newdf.groupby("学校").size().sort_values(ascending=False).head(10).reset_index(name="招生人数")
#把学校名称变成x轴的列表
school_x = school_count['学校'].tolist()
#把人数作为y轴的列表
school_y = school_count['招生人数'].tolist()

#开始作画
#柱形图
bar = Bar()
bar.add_xaxis(school_x)
bar.add_yaxis('招生人数',school_y,color_by='data')
#设置显示的标题，和下面x轴展示效果的
bar.set_global_opts(title_opts=opts.TitleOpts(title="招生人数Top10"),xaxis_opts=opts.AxisOpts(axislabel_opts={"rotate":30}))
#柱状图有横着的，有竖着的
bar.reversal_axis()
bar.render('招生人数Top10.html')

#折线图
"""
==================================================
图2：金融专业各学校分数线

分析目的：比较不同学校金融专业录取分数差异。
==================================================
"""
# 筛选金融专业数据
major = newdf[newdf["专业"] == "金融"]
# 按学校分组，同时计算金融专业最低分和最高分
majorschool = major.groupby("学校").agg(最低分数=("总分","min"),最高分数=("总分","max")).reset_index()
# 按最低分排序，选择10个学校
resultdata = majorschool.sort_values(by="最低分数").head(10)
# 获取学校名称
line_x = resultdata["学校"].tolist()
# 获取最低分数据
line_y = resultdata["最低分数"].tolist()

line = Line()
line.add_xaxis(line_x)
line.add_yaxis('金融专业最低分',line_y)
bar.set_global_opts(title_opts=opts.TitleOpts(title="各学校金融专业分数线"),xaxis_opts=opts.AxisOpts(axislabel_opts={"rotate":30}))
line.render('金融专业最低分.html')


"""
==================================================
图3：专业招生数量占比

分析目的：观察哪些专业数据量最多。
==================================================
"""
# 按专业统计数量，并获取数量最多的10个专业
zycount = newdf.groupby("专业").size().sort_values(ascending=False).head(10).reset_index(name="数量")
# 转换成饼图需要的数据格式
# zip：将多个列表按位置组合成元组
# list：将组合结果转换成列表，满足pyecharts饼图数据格式要求
pie_data = list(zip(zycount["专业"].tolist(),zycount["数量"].tolist()))

# 创建饼图对象 饼状图没有x和y
pie = Pie()
pie.add('专业数量',pie_data)
#饼状图有很多显示的标签内容
pie.set_series_opts(label_opts=opts.LabelOpts(formatter="{b}:{c} ({d}%)"))
pie.render('专业招生数量占比.html')


"""
==================================================
图4：专业招生数量+平均分组合图
分析目的：同时分析专业招生规模和录取难度。

柱状图：表示招生数量
折线图：表示平均录取分
==================================================
"""
# 按专业统计招生数量和平均录取分
zy_data = newdf.groupby("专业").agg(
    招生数量=("专业","count"),
    平均分=("总分","mean")
).sort_values(by="招生数量",ascending=False).head(10).reset_index()
# 将平均分保留一位小数，方便图表展示
zy_data["平均分"] = zy_data["平均分"].round(1)
# 获取专业名称
mix_x = zy_data["专业"].tolist()
# 获取招生数量
count_y = zy_data["招生数量"].tolist()
# 获取平均分
avg_y = zy_data["平均分"].tolist()

#想要设置两组数据展示上去，可以设置两个图形
mix_bar = Bar()
mix_bar.add_xaxis(mix_x)
mix_bar.add_yaxis('招生数量',count_y)

mix_line = Line()
mix_line.add_xaxis(mix_x)
mix_line.add_yaxis('平均分',avg_y)
# 设置组合图标题
mix_bar.set_global_opts(title_opts=opts.TitleOpts(title="专业招生数量与平均分分析"),xaxis_opts=opts.AxisOpts(axislabel_opts={"rotate":30}))
#要让两个图形都显示出来,基本都使用一个x轴
mix_bar.overlap(mix_line)
mix_bar.render('专业招生数量与平均分分析.html')


#把所有的图放在一个网址中
#简单的排列多个图表
page = Page(layout=Page.SimplePageLayout)
page.add(bar,line,pie,mix_bar)
page.render('综合考研数据可视化分析图表.html')

