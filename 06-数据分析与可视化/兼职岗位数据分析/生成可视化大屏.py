# -*- coding: utf-8 -*-
"""
基于 复合型岗位对比分析报告.md 生成科技感 HTML 可视化大屏
图表: 1)薪资维度柱状图  2)成长潜力雷达图  + 顶部 KPI 概览条 + 持续动态动画
使用占位符替换避免 f-string 转义问题
"""
import pandas as pd
import json

CSV = r'c:\Users\EDY\Desktop\python正式课\day21未来职业规划行业薪资分析\02课程代码\兼职岗位数据.csv'
OUT = r'c:\Users\EDY\Desktop\python正式课\day21未来职业规划行业薪资分析\02课程代码\复合型岗位可视化大屏.html'

df = pd.read_csv(CSV, encoding='utf-8-sig')
comp = df[df['技能方向'] == 'Python+AIGC']
base = df[df['技能方向'] == '基础服务']

# ---------- 计算指标 ----------
comp_hour = round(comp['时薪_元'].mean(), 1)
base_hour = round(base['时薪_元'].mean(), 1)
comp_month = round(comp['预计月收入_元'].mean(), 1)
base_month = round(base['预计月收入_元'].mean(), 1)
premium_rate = round((comp_month - base_month) / base_month * 100, 1)
slope = 503.6
remote_rate = round((comp['远程办公']=='是').mean()*100, 1)
growth_mean = round(comp['成长潜力_1至5'].mean(), 2)
heat_idx = round(comp['岗位热度指数'].mean(), 1)

comp_day = round(comp['参考日薪_元'].mean(), 1)
base_day = round(base['参考日薪_元'].mean(), 1)

salary_data = {
    "categories": ["时薪(元)", "参考日薪(元)", "预计月收入(元)"],
    "comp": [comp_hour, comp_day, comp_month],
    "base": [base_hour, base_day, base_month],
}

def s5(v):
    return round(v/5*100, 1)

radar_indicators = [
    {"name": "成长潜力", "max": 100},
    {"name": "技能门槛", "max": 100},
    {"name": "岗位热度", "max": 100},
    {"name": "远程办公率", "max": 100},
    {"name": "培训可胜任率", "max": 100},
    {"name": "高考生适配率", "max": 100},
]
comp_radar = [
    s5(comp['成长潜力_1至5'].mean()),
    s5(comp['技能门槛_1至5'].mean()),
    round(comp['岗位热度指数'].mean(), 1),
    round((comp['远程办公']=='是').mean()*100, 1),
    round((comp['培训后可胜任']=='是').mean()*100, 1),
    round((comp['高考毕业生适配']=='是').mean()*100, 1),
]
base_radar = [
    s5(base['成长潜力_1至5'].mean()),
    s5(base['技能门槛_1至5'].mean()),
    round(base['岗位热度指数'].mean(), 1),
    round((base['远程办公']=='是').mean()*100, 1),
    round((base['培训后可胜任']=='是').mean()*100, 1),
    round((base['高考毕业生适配']=='是').mean()*100, 1),
]

# JSON 数据
SALARY_JSON = json.dumps(salary_data, ensure_ascii=False)
RADAR_IND_JSON = json.dumps(radar_indicators, ensure_ascii=False)
COMP_RADAR_JSON = json.dumps(comp_radar)
BASE_RADAR_JSON = json.dumps(base_radar)

# ---------- HTML 模板 (使用 __ 占位符) ----------
HTML_TEMPLATE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>复合型岗位对比分析可视化大屏</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  :root{
    --bg:#050a18; --bg2:#0a1430; --cyan:#00f0ff; --magenta:#ff2bd6;
    --green:#00ff9d; --orange:#ffae00; --purple:#8a5cff; --blue:#3d7fff;
    --text:#d6e4ff; --dim:#6b88c4;
  }
  html,body { width:100%; min-height:100vh; background:var(--bg); color:var(--text);
    font-family:"Microsoft YaHei","Segoe UI",sans-serif; overflow-x:hidden; }

  .grid-bg { position:fixed; inset:0; z-index:0; pointer-events:none;
    background-image:
      linear-gradient(rgba(0,240,255,0.06) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0,240,255,0.06) 1px, transparent 1px);
    background-size:50px 50px; animation:gridMove 20s linear infinite; }
  @keyframes gridMove { from{background-position:0 0;} to{background-position:50px 50px;} }
  .glow-orb { position:fixed; border-radius:50%; filter:blur(80px); opacity:.35; z-index:0; pointer-events:none;
    animation:float 12s ease-in-out infinite; }
  .orb1 { width:400px;height:400px; background:var(--cyan); top:-100px; left:-100px; }
  .orb2 { width:500px;height:500px; background:var(--magenta); bottom:-150px; right:-150px; animation-delay:-6s; }
  .orb3 { width:300px;height:300px; background:var(--purple); top:40%; left:50%; animation-delay:-3s; }
  @keyframes float { 0%,100%{transform:translate(0,0);} 50%{transform:translate(40px,-30px);} }

  .wrap { position:relative; z-index:2; padding:24px 32px 40px; max-width:1920px; margin:0 auto; }

  header { text-align:center; margin-bottom:22px; }
  header h1 { font-size:38px; font-weight:800; letter-spacing:4px;
    background:linear-gradient(90deg,var(--cyan),var(--magenta),var(--cyan));
    background-size:200% auto; -webkit-background-clip:text; background-clip:text; color:transparent;
    animation:shine 4s linear infinite; text-shadow:0 0 30px rgba(0,240,255,.4); }
  header p { color:var(--dim); font-size:13px; margin-top:6px; letter-spacing:2px; }
  @keyframes shine { from{background-position:0% center;} to{background-position:200% center;} }
  .scan-line { height:2px; margin:14px auto 0; width:60%;
    background:linear-gradient(90deg,transparent,var(--cyan),var(--magenta),transparent);
    animation:scan 3s ease-in-out infinite; }
  @keyframes scan { 0%,100%{opacity:.3; width:40%;} 50%{opacity:1; width:80%;} }

  .kpi-bar { display:grid; grid-template-columns:repeat(6,1fr); gap:14px; margin-bottom:26px; }
  .kpi { position:relative; background:linear-gradient(135deg,rgba(10,20,48,.85),rgba(20,40,90,.6));
    border:1px solid rgba(0,240,255,.25); border-radius:10px; padding:16px 18px; overflow:hidden;
    backdrop-filter:blur(8px); transition:.4s; }
  .kpi:hover { transform:translateY(-4px); border-color:var(--cyan); box-shadow:0 8px 30px rgba(0,240,255,.25); }
  .kpi::before { content:''; position:absolute; top:0; left:0; width:3px; height:100%;
    background:var(--accent,var(--cyan)); box-shadow:0 0 12px var(--accent,var(--cyan)); }
  .kpi::after { content:''; position:absolute; bottom:0; left:-100%; width:100%; height:2px;
    background:linear-gradient(90deg,transparent,var(--accent,var(--cyan)),transparent);
    animation:slide 3s linear infinite; }
  @keyframes slide { to { left:100%; } }
  .kpi .label { font-size:12px; color:var(--dim); letter-spacing:1px; }
  .kpi .val { font-size:30px; font-weight:800; margin-top:6px; color:var(--accent,var(--cyan));
    font-family:"Consolas",monospace; text-shadow:0 0 14px var(--accent,var(--cyan)); }
  .kpi .unit { font-size:13px; color:var(--dim); margin-left:4px; font-weight:400; }
  .kpi .sub { font-size:11px; color:var(--dim); margin-top:4px; }

  .charts { display:grid; grid-template-columns:1.1fr 1fr; gap:24px; }
  .card { position:relative; background:linear-gradient(135deg,rgba(10,20,48,.85),rgba(15,28,62,.7));
    border:1px solid rgba(0,240,255,.2); border-radius:14px; padding:22px; backdrop-filter:blur(10px);
    box-shadow:0 8px 40px rgba(0,0,0,.4); overflow:hidden; }
  .card::before { content:''; position:absolute; top:0; left:0; right:0; height:1px;
    background:linear-gradient(90deg,transparent,var(--cyan),transparent); }
  .card-head { display:flex; align-items:center; gap:10px; margin-bottom:8px; }
  .card-head .dot { width:10px; height:10px; border-radius:50%; background:var(--cyan);
    box-shadow:0 0 10px var(--cyan); animation:pulse 1.5s ease-in-out infinite; }
  @keyframes pulse { 0%,100%{opacity:1; transform:scale(1);} 50%{opacity:.4; transform:scale(.7);} }
  .card-head h2 { font-size:19px; font-weight:700; color:var(--text); letter-spacing:1px; }
  .card-head .tag { margin-left:auto; font-size:11px; color:var(--cyan); border:1px solid rgba(0,240,255,.4);
    padding:2px 10px; border-radius:20px; background:rgba(0,240,255,.08); }
  .chart { width:100%; height:420px; }
  .analysis { margin-top:14px; padding:14px 16px; background:rgba(0,240,255,.04);
    border-left:3px solid var(--cyan); border-radius:6px; font-size:13.5px; line-height:1.8; color:var(--text); }
  .analysis b { color:var(--cyan); } .analysis .hi { color:var(--green); font-weight:700; }

  .legend-row { display:flex; gap:24px; margin:6px 0 4px; font-size:13px; }
  .legend-row span { display:flex; align-items:center; gap:8px; }
  .legend-row i { width:14px; height:14px; border-radius:3px; display:inline-block; }

  footer { text-align:center; margin-top:30px; color:var(--dim); font-size:12px; letter-spacing:2px; }
  @media(max-width:1100px){ .charts{grid-template-columns:1fr;} .kpi-bar{grid-template-columns:repeat(3,1fr);} }
</style>
</head>
<body>
<div class="grid-bg"></div>
<div class="glow-orb orb1"></div>
<div class="glow-orb orb2"></div>
<div class="glow-orb orb3"></div>

<div class="wrap">
  <header>
    <h1>复合型岗位对比分析可视化大屏</h1>
    <p>Python + AIGC 复合技能 · 市场溢价与增长优势洞察  |  数据周期 2025.01 - 2026.06  |  样本 30,000 条</p>
    <div class="scan-line"></div>
  </header>

  <!-- KPI 概览条 -->
  <div class="kpi-bar">
    <div class="kpi" style="--accent:var(--cyan)">
      <div class="label">复合型月薪均值</div>
      <div class="val" data-target="__COMP_MONTH__" data-suffix="元">0</div>
      <div class="sub">基础岗仅 __BASE_MONTH__ 元</div>
    </div>
    <div class="kpi" style="--accent:var(--magenta)">
      <div class="label">月薪溢价率</div>
      <div class="val" data-target="__PREMIUM__" data-suffix="%">0</div>
      <div class="sub">复合型 vs 基础服务</div>
    </div>
    <div class="kpi" style="--accent:var(--green)">
      <div class="label">月薪增长斜率</div>
      <div class="val" data-target="__SLOPE__" data-suffix="元/季">0</div>
      <div class="sub">基础岗 +7.6 元/季(停滞)</div>
    </div>
    <div class="kpi" style="--accent:var(--orange)">
      <div class="label">岗位热度指数</div>
      <div class="val" data-target="__HEAT__">0</div>
      <div class="sub">基础岗 62.8</div>
    </div>
    <div class="kpi" style="--accent:var(--purple)">
      <div class="label">成长潜力均值</div>
      <div class="val" data-target="__GROWTH__" data-suffix="/5">0</div>
      <div class="sub">基础岗 2.00/5</div>
    </div>
    <div class="kpi" style="--accent:var(--blue)">
      <div class="label">远程办公率</div>
      <div class="val" data-target="__REMOTE__" data-suffix="%">0</div>
      <div class="sub">基础岗 0%</div>
    </div>
  </div>

  <!-- 图表区 -->
  <div class="charts">
    <!-- 图表1: 薪资三指标对比柱状图 -->
    <div class="card">
      <div class="card-head">
        <div class="dot"></div>
        <h2>薪资三指标对比图</h2>
        <div class="tag">薪资维度</div>
      </div>
      <div class="legend-row">
        <span><i style="background:var(--cyan)"></i>复合型岗位(Python+AIGC)</span>
        <span><i style="background:var(--orange)"></i>纯基础类岗位(基础服务)</span>
      </div>
      <div id="salaryChart" class="chart"></div>
      <div class="analysis">
        <b>▎图表总结分析：</b>三类薪资指标上复合型岗位呈<span class="hi">断崖式领先</span>。
        时薪 <b>195.4 元</b> 对 <b>29.4 元</b>（溢价 <span class="hi">+564.2%</span>）、参考日薪 <b>1,160.7 元</b> 对 <b>176.6 元</b>（+557.3%）、
        预计月收入 <b>14,081 元</b> 对 <b>2,809 元</b>（<span class="hi">+401.2%</span>，5.0 倍）。
        值得注意的是，时薪溢价率高于月薪溢价率，因基础岗周均工时（22.1h）多于复合型（16.6h）——
        复合技能以<b>更短工时创造数倍收入</b>，单位时间价值显著领先，这正是"技能溢价"最直观的体现。
      </div>
    </div>

    <!-- 图表2: 成长潜力雷达图 -->
    <div class="card">
      <div class="card-head">
        <div class="dot" style="background:var(--magenta);box-shadow:0 0 10px var(--magenta)"></div>
        <h2>成长潜力多维雷达图</h2>
        <div class="tag" style="color:var(--magenta);border-color:rgba(255,43,214,.4);background:rgba(255,43,214,.08)">成长潜力</div>
      </div>
      <div class="legend-row">
        <span><i style="background:var(--cyan)"></i>复合型岗位</span>
        <span><i style="background:var(--orange)"></i>纯基础类岗位</span>
      </div>
      <div id="radarChart" class="chart"></div>
      <div class="analysis" style="border-color:var(--magenta)">
        <b>▎图表总结分析：</b>雷达图清晰呈现"门槛—天花板"权衡的<b>两端分化</b>。
        复合型在<span class="hi">成长潜力(90.3)、技能门槛(90.0)、岗位热度(91.6)、远程办公率(77.1)</span>四维全面外扩，
        包络面积远超基础岗；而基础岗仅在<b>培训可胜任率(100%)与高考生适配率(100%)</b>两维突出——
        意味其<b>低门槛、人人可入但天花板封顶</b>。复合型虽高考生适配率仅 17.9%，但<b>培训后可胜任率达 88.6%</b>，
        说明通过系统培训打通编程与 AIGC 工具链，即可从低适配跃迁至高成长区间，是技能教育的黄金切入点。
      </div>
    </div>
  </div>

  <footer>· 复合型岗位对比分析可视化大屏 · 基于 ECharts 5.4 · 数据来源:兼职岗位数据.csv ·</footer>
</div>

<script>
// ===== KPI 数字滚动动画 =====
function animateKPI(){
  document.querySelectorAll('.kpi .val').forEach(function(el){
    var target=parseFloat(el.dataset.target);
    var suffix=el.dataset.suffix||'';
    var dur=1600; var start=performance.now();
    function tick(now){
      var p=Math.min((now-start)/dur,1);
      var e=1-Math.pow(1-p,3);
      var cur=target*e;
      el.textContent=(Number.isInteger(target)?Math.round(cur):cur.toFixed(1))+suffix;
      if(p<1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  });
}
animateKPI();

var C_CYAN='#00f0ff', C_MAG='#ff2bd6', C_GRN='#00ff9d', C_ORG='#ffae00', C_PUR='#8a5cff';

// ===== 图表1: 薪资三指标柱状图 =====
var salaryChart=echarts.init(document.getElementById('salaryChart'));
var salaryData=__SALARY_JSON__;
var sIdx=0;
function salaryOption(idx){
  return {
    backgroundColor:'transparent',
    grid:{left:70,right:40,top:50,bottom:50},
    tooltip:{trigger:'axis',axisPointer:{type:'shadow'},
      backgroundColor:'rgba(10,20,48,.92)',borderColor:'rgba(0,240,255,.5)',textStyle:{color:'#d6e4ff'},
      formatter:function(p){return p.map(function(s){return '<span style="color:'+s.color+'">●</span> '+s.seriesName+': <b>'+s.value.toLocaleString()+'</b> 元';}).join('<br>');}},
    legend:{show:false},
    xAxis:{type:'category',data:salaryData.categories,
      axisLine:{lineStyle:{color:'#3d5a8a'}},
      axisLabel:{color:'#9bb5e8',fontSize:13,fontWeight:600},
      axisTick:{show:false}},
    yAxis:{type:'value',name:'金额(元)',nameTextStyle:{color:'#6b88c4'},
      axisLine:{show:false},splitLine:{lineStyle:{color:'rgba(61,90,138,.25)',type:'dashed'}},
      axisLabel:{color:'#6b88c4',formatter:function(v){return v>=1000?(v/1000)+'k':v;}}},
    series:[
      {name:'复合型岗位(Python+AIGC)',type:'bar',barWidth:'28%',
        itemStyle:{borderRadius:[6,6,0,0],
          color:new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:C_CYAN},{offset:1,color:'rgba(0,240,255,.2)'}])},
        emphasis:{itemStyle:{shadowBlur:20,shadowColor:C_CYAN}},
        label:{show:true,position:'top',color:C_CYAN,fontWeight:700,formatter:function(p){return p.value.toLocaleString();}},
        data:salaryData.comp.map(function(v,i){return {value:v,itemStyle:{opacity:i===idx?1:0.82}};})},
      {name:'纯基础类岗位(基础服务)',type:'bar',barWidth:'28%',
        itemStyle:{borderRadius:[6,6,0,0],
          color:new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:C_ORG},{offset:1,color:'rgba(255,174,0,.2)'}])},
        label:{show:true,position:'top',color:C_ORG,fontWeight:600,formatter:function(p){return p.value.toLocaleString();}},
        data:salaryData.base},
      {name:'溢价倍数',type:'line',symbol:'diamond',symbolSize:11,
        lineStyle:{color:C_MAG,type:'dashed',width:2},
        itemStyle:{color:C_MAG},
        label:{show:true,position:'top',color:C_MAG,fontWeight:700,formatter:function(p){return p.value.toFixed(1)+'×';},
          backgroundColor:'rgba(255,43,214,.12)',padding:[2,6],borderRadius:8},
        data:salaryData.comp.map(function(v,i){return v/salaryData.base[i];})}
    ]
  };
}
salaryChart.setOption(salaryOption(sIdx));
// 持续动画: 轮播高亮 + 重绘动效
setInterval(function(){ sIdx=(sIdx+1)%salaryData.comp.length; salaryChart.setOption(salaryOption(sIdx)); }, 2200);

// ===== 图表2: 成长潜力雷达图 =====
var radarChart=echarts.init(document.getElementById('radarChart'));
var radarIndicators=__RADAR_IND_JSON__;
var compRadar=__COMP_RADAR_JSON__;
var baseRadar=__BASE_RADAR_JSON__;
var radarPhase=0;
function radarOption(){
  var breath=0.85+0.15*Math.sin(radarPhase);
  return {
    backgroundColor:'transparent',
    tooltip:{backgroundColor:'rgba(10,20,48,.92)',borderColor:'rgba(255,43,214,.5)',textStyle:{color:'#d6e4ff'}},
    radar:{
      indicator:radarIndicators,
      center:['50%','54%'], radius:'66%',
      axisName:{color:'#9bb5e8',fontSize:12,fontWeight:600},
      splitLine:{lineStyle:{color:'rgba(61,90,138,.4)'}},
      splitArea:{areaStyle:{color:['rgba(0,240,255,.03)','rgba(255,43,214,.03)']}},
      axisLine:{lineStyle:{color:'rgba(61,90,138,.5)'}}
    },
    series:[{
      type:'radar',
      data:[
        {value:compRadar,name:'复合型岗位(Python+AIGC)',
          areaStyle:{color:new echarts.graphic.RadialGradient(0.5,0.5,1,[
            {offset:0,color:'rgba(0,240,255,'+(breath*0.6).toFixed(3)+')'},
            {offset:1,color:'rgba(0,240,255,0.05)'}])},
          lineStyle:{color:C_CYAN,width:2,shadowBlur:15,shadowColor:C_CYAN},
          itemStyle:{color:C_CYAN},
          symbol:'circle',symbolSize:7},
        {value:baseRadar,name:'纯基础类岗位(基础服务)',
          areaStyle:{color:'rgba(255,174,0,'+(breath*0.4).toFixed(3)+')'},
          lineStyle:{color:C_ORG,width:2},
          itemStyle:{color:C_ORG},
          symbol:'circle',symbolSize:6}
      ]
    }]
  };
}
radarChart.setOption(radarOption());
// 持续呼吸动画
setInterval(function(){ radarPhase+=0.15; radarChart.setOption(radarOption()); }, 80);

// 响应式
window.addEventListener('resize',function(){ salaryChart.resize(); radarChart.resize(); });
</script>
</body>
</html>'''

# 替换占位符
html = HTML_TEMPLATE
html = html.replace('__COMP_MONTH__', str(comp_month))
html = html.replace('__BASE_MONTH__', str(base_month))
html = html.replace('__PREMIUM__', str(premium_rate))
html = html.replace('__SLOPE__', str(slope))
html = html.replace('__HEAT__', str(heat_idx))
html = html.replace('__GROWTH__', str(growth_mean))
html = html.replace('__REMOTE__', str(remote_rate))
html = html.replace('__SALARY_JSON__', SALARY_JSON)
html = html.replace('__RADAR_IND_JSON__', RADAR_IND_JSON)
html = html.replace('__COMP_RADAR_JSON__', COMP_RADAR_JSON)
html = html.replace('__BASE_RADAR_JSON__', BASE_RADAR_JSON)

with open(OUT, 'w', encoding='utf-8') as f:
    f.write(html)
print('已生成:', OUT)
print('KPI:', comp_month, premium_rate, slope, heat_idx, growth_mean, remote_rate)
