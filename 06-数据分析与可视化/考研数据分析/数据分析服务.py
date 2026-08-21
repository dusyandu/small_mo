import csv
import requests
import os
import webbrowser
import re

# ---- ANSI 颜色代码 ----
os.system('')  # 启用 Windows 终端 ANSI 支持
R = '\033[91m'   # 红
G = '\033[92m'   # 绿
Y = '\033[93m'   # 黄
B = '\033[94m'   # 蓝
C = '\033[96m'   # 青
M = '\033[95m'   # 紫
W = '\033[97m'   # 白
E = '\033[0m'    # 重置

API_URL = 'https://spark-api-open.xf-yun.com/v1/chat/completions'
HEADERS = {
    "Authorization": "Bearer 442112d2740b79abe0df60a2ad82636c:Y2U3ZjY5MjEyNmM4NTk0YmIwOTg3N2Fh",
    'Content-Type': 'application/json'
}


def parse_history_table(linian_text):
    """将历年分数线文本解析为列表"""
    records = []
    for line in linian_text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split('|')]
        if len(parts) >= 7:
            records.append({
                'year': parts[0].replace('年', ''),
                'department': parts[1].replace('招生院系', ''),
                'total': parts[2].replace('总分', ''),
                'politics': parts[3].replace('政', ''),
                'foreign': parts[4].replace('外', ''),
                'major1': parts[5].replace('专一', ''),
                'major2': parts[6].replace('专二', ''),
            })
    return records


def parse_recommendation(text):
    """
    将推荐列表文本解析并合并：同一学校+同一专业的多条记录，
    按分数求均值后合并为一条，按均分从高到低排序。

    返回：
        list[dict]  每项包含 school / major / avg_score
    """
    groups = {}
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line or '...(省略其余)' in line:
            continue
        parts = [p.strip() for p in line.split('|')]
        if len(parts) < 4:
            continue
        school = parts[0]
        major = parts[1]
        try:
            score = float(parts[2].replace('分', ''))
        except ValueError:
            continue
        key = (school, major)
        if key not in groups:
            groups[key] = []
        groups[key].append(score)

    items = []
    for (school, major), scores in groups.items():
        avg_score = sum(scores) / len(scores)
        items.append({
            'school': school,
            'major': major,
            'avg_score': round(avg_score, 1),
        })

    # 按平均分从高到低排序
    items.sort(key=lambda x: x['avg_score'], reverse=True)
    return items


def parse_ai_sections(text):
    """解析 AI 返回的结构化文本"""
    sections = {
        'prediction': '',
        'chongci': '',
        'wentuo': '',
        'baodi': '',
        'advice': '',
    }
    clean = text.replace('---', '').strip()

    patterns = {
        'prediction': r'预测\s*(?:明年|\d{4})\s*线\s*[：:]\s*(.+?)(?=\n\s*(?:冲刺|稳妥|保底|建议|\Z))',
        'chongci': r'冲刺推荐\s*[：:]\s*(.+?)(?=\n\s*(?:稳妥|保底|建议|\Z))',
        'wentuo': r'稳妥推荐\s*[：:]\s*(.+?)(?=\n\s*(?:保底|建议|\Z))',
        'baodi': r'保底推荐\s*[：:]\s*(.+?)(?=\n\s*(?:建议|\Z))',
        'advice': r'建议\s*[：:]\s*(.+?)$',
    }

    for key, pattern in patterns.items():
        m = re.search(pattern, clean, re.DOTALL | re.MULTILINE)
        if m:
            sections[key] = m.group(1).strip()

    return sections


def ai_fenxi(xuexiao, zhuanye, fenshu):
    # 1. 读取CSV数据
    rows = []
    f = open('./各院校历年数据采集.csv', 'r', encoding='utf-8-sig')
    reader = csv.DictReader(f)
    for r in reader:
        rows.append(r)
    f.close()

    # 2. 查找该学校该专业的历年分数线
    linian = ''
    for r in rows:
        if xuexiao in r['学校'] and zhuanye in r['专业']:
            linian += '  ' + r['录取年份'] + '年 | 招生院系' + r['招生院系']
            linian += ' | 总分' + r['总分'] + ' | 政' + r['政治'] + ' | 外' + r['外语']
            linian += ' | 专一' + r['专业课一'] + ' | 专二' + r['专业课二'] + '\n'

    # 3. 查找同专业的不同学校，按该专业分数线分冲刺/稳妥/保底
    chongci = ''
    wentuo = ''
    baodi = ''
    for r in rows:
        # 只保留同行专业的其他学校
        if zhuanye not in r['专业']:
            continue
        try:
            xian = float(r['总分'])
        except:
            continue
        info = r['学校'] + ' | ' + r['专业'] + ' | ' + str(int(xian)) + '分 | ' + r['录取年份'] + '年'
        if xian > fenshu + 10:
            chongci += '  ' + info + '\n'
        elif xian >= fenshu - 10:
            wentuo += '  ' + info + '\n'
        else:
            baodi += '  ' + info + '\n'

    # 截断过长的列表
    if len(chongci) > 1200:
        chongci = chongci[:1200] + '  ...(省略其余)\n'
    if len(wentuo) > 1200:
        wentuo = wentuo[:1200] + '  ...(省略其余)\n'
    if len(baodi) > 1200:
        baodi = baodi[:1200] + '  ...(省略其余)\n'

    # 4. 构建提示词 -- 要求简洁
    prompt = '你是考研数据分析专家，请用简洁的语言回答，总共不超过300字：\n\n'
    prompt += '1. 以下是"' + xuexiao + '-' + zhuanye + '"历年分数线，预测明年总分（只需给数字+一句话理由）\n'
    prompt += linian + '\n'
    prompt += '2. 考生' + str(int(fenshu)) + '分，匹配结果如下：\n'
    prompt += '【冲刺】\n' + chongci + '\n'
    prompt += '【稳妥】\n' + wentuo + '\n'
    prompt += '【保底】\n' + baodi + '\n'
    prompt += '请用以下格式输出（每项写简洁，不要展开）：\n'
    prompt += '---\n'
    prompt += '预测明年线：XX分（理由：一句话）\n'
    prompt += '\n'
    prompt += '冲刺推荐：2个（学校-专业，分数线，理由一句话）\n'
    prompt += '稳妥推荐：2个（同上）\n'
    prompt += '保底推荐：2个（同上）\n'
    prompt += '\n'
    prompt += '建议：1条\n'

    # 5. 调用AI
    print(Y + '\n  [AI 分析中，请稍候...]' + E)
    data = {'model': 'generalv3.5', 'messages': [{'role': 'user', 'content': prompt}]}
    resp = requests.post(API_URL, headers=HEADERS, json=data, timeout=90)
    resp_json = resp.json()

    if 'choices' not in resp_json:
        print(R + '  [错误] ' + str(resp_json) + E)
        return {
            'result': 'AI调用失败',
            'linian': linian,
            'chongci': chongci,
            'wentuo': wentuo,
            'baodi': baodi,
        }

    result = resp_json['choices'][0]['message']['content']
    return {
        'result': result,
        'linian': linian,
        'chongci': chongci,
        'wentuo': wentuo,
        'baodi': baodi,
    }


# ============================================================
# HTML 模板（内嵌多行字符串）
# ============================================================
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>考研数据智能分析报告</title>
<style>
  :root {
    --bg: #F6F8FB;
    --card-bg: #FFFFFF;
    --text: #1E293B;
    --text-secondary: #64748B;
    --text-muted: #94A3B8;
    --primary: #4F46E5;
    --primary-light: #EEF2FF;
    --chongci: #EA580C;
    --chongci-bg: #FFF7ED;
    --chongci-border: #FED7AA;
    --wentuo: #2563EB;
    --wentuo-bg: #EFF6FF;
    --wentuo-border: #BFDBFE;
    --baodi: #059669;
    --baodi-bg: #ECFDF5;
    --baodi-border: #A7F3D0;
    --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
    --shadow: 0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04);
    --shadow-md: 0 4px 6px rgba(0,0,0,0.06), 0 2px 4px rgba(0,0,0,0.04);
    --radius: 12px;
    --radius-sm: 8px;
  }

  * { margin:0; padding:0; box-sizing:border-box; }

  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
      "Microsoft YaHei", "Helvetica Neue", sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
  }

  /* ---- Header ---- */
  .header {
    background: linear-gradient(135deg, #312E81 0%, #4F46E5 50%, #6366F1 100%);
    color: #fff;
    padding: 36px 32px 32px;
    text-align: center;
  }
  .header-icon { font-size: 40px; margin-bottom: 8px; }
  .header h1 { font-size: 26px; font-weight: 700; letter-spacing: 0.5px; }
  .header .subtitle { font-size: 13px; opacity: 0.7; margin-top: 6px; }

  /* ---- Container ---- */
  .container { max-width: 960px; margin: 0 auto; padding: 28px 20px 48px; }

  /* ---- Overview Cards ---- */
  .overview {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-top: -20px;
    position: relative;
    z-index: 1;
  }
  .ov-card {
    background: var(--card-bg);
    border-radius: var(--radius);
    padding: 22px 20px;
    text-align: center;
    box-shadow: var(--shadow-md);
  }
  .ov-card .label {
    font-size: 12px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 6px;
  }
  .ov-card .value {
    font-size: 22px;
    font-weight: 700;
    color: var(--text);
  }
  .ov-card .value.score { color: var(--primary); font-size: 28px; }

  /* ---- Section ---- */
  .section { margin-top: 28px; }

  .section-title {
    font-size: 17px;
    font-weight: 700;
    color: var(--text);
    margin-bottom: 14px;
    padding-left: 14px;
    border-left: 3px solid var(--primary);
  }

  /* ---- Card ---- */
  .card {
    background: var(--card-bg);
    border-radius: var(--radius);
    padding: 24px;
    box-shadow: var(--shadow);
  }

  /* ---- Prediction Card ---- */
  .prediction-card {
    background: linear-gradient(135deg, #EEF2FF 0%, #E0E7FF 100%);
    border-radius: var(--radius);
    padding: 28px 24px;
    text-align: center;
    border: 1px solid #C7D2FE;
  }
  .prediction-card .year-tag {
    display: inline-block;
    background: var(--primary);
    color: #fff;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 20px;
    letter-spacing: 1px;
    margin-bottom: 12px;
  }
  .prediction-card .pred-score {
    font-size: 48px;
    font-weight: 800;
    color: #312E81;
    line-height: 1;
  }
  .prediction-card .pred-reason {
    font-size: 14px;
    color: #4338CA;
    margin-top: 10px;
    font-weight: 500;
  }

  /* ---- History Table ---- */
  .table-wrap { overflow-x: auto; }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
  }
  table th {
    background: #F1F5F9;
    color: var(--text-secondary);
    font-weight: 600;
    padding: 10px 14px;
    text-align: center;
    font-size: 12px;
    letter-spacing: 0.5px;
    white-space: nowrap;
  }
  table td {
    padding: 10px 14px;
    text-align: center;
    border-bottom: 1px solid #F1F5F9;
    white-space: nowrap;
  }
  table tbody tr:hover { background: #FAFBFC; }

  /* ---- Recommend Row ---- */
  .rec-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
  }
  .rec-card {
    border-radius: var(--radius);
    padding: 20px;
    border: 1px solid transparent;
  }
  .rec-card.chongci {
    background: var(--chongci-bg);
    border-color: var(--chongci-border);
  }
  .rec-card.wentuo {
    background: var(--wentuo-bg);
    border-color: var(--wentuo-border);
  }
  .rec-card.baodi {
    background: var(--baodi-bg);
    border-color: var(--baodi-border);
  }
  .rec-card .rec-tag {
    display: inline-block;
    font-size: 11px;
    font-weight: 700;
    padding: 3px 10px;
    border-radius: 20px;
    letter-spacing: 0.5px;
    margin-bottom: 14px;
  }
  .rec-card.chongci .rec-tag {
    background: var(--chongci);
    color: #fff;
  }
  .rec-card.wentuo .rec-tag {
    background: var(--wentuo);
    color: #fff;
  }
  .rec-card.baodi .rec-tag {
    background: var(--baodi);
    color: #fff;
  }
  .rec-item {
    padding: 10px 0;
    border-bottom: 1px solid rgba(0,0,0,0.06);
    font-size: 13px;
    line-height: 1.6;
  }
  .rec-item:last-child { border-bottom: none; padding-bottom: 0; }
  .rec-item .ri-school { font-weight: 600; color: var(--text); }
  .rec-item .ri-major { color: var(--text-secondary); font-size: 12px; }
  .rec-item .ri-score { font-weight: 600; font-size: 13px; }
  .rec-item .ri-year  { color: var(--text-muted); font-size: 11px; }
  .rec-card.chongci .ri-score { color: var(--chongci); }
  .rec-card.wentuo .ri-score { color: var(--wentuo); }
  .rec-card.baodi .ri-score { color: var(--baodi); }

  /* ---- Advice Card ---- */
  .advice-card {
    background: #FFFBEB;
    border: 1px solid #FDE68A;
    border-radius: var(--radius);
    padding: 22px 24px;
    display: flex;
    align-items: flex-start;
    gap: 12px;
  }
  .advice-card .advice-icon { font-size: 22px; flex-shrink: 0; }
  .advice-card .advice-text { font-size: 15px; color: #92400E; line-height: 1.7; }

  /* ---- Empty State ---- */
  .empty-state {
    text-align: center;
    color: var(--text-muted);
    padding: 32px 16px;
    font-size: 14px;
  }

  /* ---- Footer ---- */
  .footer {
    text-align: center;
    padding: 32px 20px;
    color: var(--text-muted);
    font-size: 12px;
  }

  /* ---- Responsive ---- */
  @media (max-width: 700px) {
    .overview { grid-template-columns: 1fr; }
    .rec-grid { grid-template-columns: 1fr; }
    .header h1 { font-size: 20px; }
    .prediction-card .pred-score { font-size: 36px; }
  }

  /* ---- Print ---- */
  @media print {
    body { background: #fff; }
    .header { background: #4F46E5 !important; -webkit-print-color-adjust: exact; }
    .card, .rec-card, .prediction-card, .advice-card, .ov-card {
      box-shadow: none; break-inside: avoid;
    }
  }
</style>
</head>
<body>

<!-- ====== Header ====== -->
<div class="header">
  <div class="header-icon">🎓</div>
  <h1>考研数据智能分析报告</h1>
</div>

<div class="container">

  <!-- ====== 概览卡片 ====== -->
  <div class="overview">
    <div class="ov-card">
      <div class="label">目标院校</div>
      <div class="value">{school}</div>
    </div>
    <div class="ov-card">
      <div class="label">目标专业</div>
      <div class="value">{major}</div>
    </div>
    <div class="ov-card">
      <div class="label">预估分数</div>
      <div class="value score">{score} 分</div>
    </div>
  </div>

  <!-- ====== AI 预测 ====== -->
  <div class="section">
    <div class="section-title">🤖 AI 预测结果</div>
    {prediction_html}
  </div>

  <!-- ====== 历年分数线 ====== -->
  <div class="section">
    <div class="section-title">📊 {school} · {major} 历年分数线</div>
    {history_html}
  </div>

  <!-- ====== 院校推荐 ====== -->
  <div class="section">
    <div class="section-title">🏫 院校匹配推荐</div>
    <div class="rec-grid">
      {chongci_html}
      {wentuo_html}
      {baodi_html}
    </div>
  </div>

  <!-- ====== AI 建议 ====== -->
  {advice_html}

</div>

<div class="footer">
  考研数据智能分析系统 · 数据仅供参考，请以官方发布为准
</div>

</body>
</html>"""


def build_prediction_html(sections):
    """构建 AI 预测卡片 HTML"""
    pred = sections.get('prediction', '')
    if not pred:
        return '<div class="card"><div class="empty-state">暂无预测数据</div></div>'

    # 尝试提取分数数字
    score_match = re.search(r'(\d{3})', pred)
    score_num = score_match.group(1) if score_match else '—'
    reason = pred
    if score_match:
        reason = pred[pred.find(str(score_match.group(1))) + 3:].strip().lstrip('分）。)')

    return f'''<div class="prediction-card">
      <div class="year-tag">明年预测</div>
      <div class="pred-score">{score_num}<span style="font-size:20px;font-weight:500;"> 分</span></div>
      <div class="pred-reason">{reason}</div>
    </div>'''


def build_history_html(linian_text):
    """构建历年分数线表格 HTML"""
    records = parse_history_table(linian_text)
    if not records:
        return '<div class="card"><div class="empty-state">暂无历年数据</div></div>'

    rows_html = ''
    for r in records:
        rows_html += f'''<tr>
          <td><strong>{r['year']}</strong></td>
          <td>{r['department']}</td>
          <td style="font-weight:700;color:#4F46E5;">{r['total']}</td>
          <td>{r['politics']}</td>
          <td>{r['foreign']}</td>
          <td>{r['major1']}</td>
          <td>{r['major2']}</td>
        </tr>'''

    return f'''<div class="card">
      <div class="table-wrap">
        <table>
          <thead><tr>
            <th>年份</th><th>招生院系</th><th>总分</th><th>政治</th><th>外语</th><th>专业课一</th><th>专业课二</th>
          </tr></thead>
          <tbody>{rows_html}</tbody>
        </table>
      </div>
    </div>'''


def build_rec_card_html(category, title, text, sections):
    """构建单个推荐卡片 HTML"""
    # 优先使用 AI 解析结果
    ai_text = sections.get(category, '')
    items = parse_recommendation(text)
    ai_items = parse_recommendation(ai_text) if ai_text else []

    # AI 推荐项
    ai_html = ''
    if ai_items:
        for it in ai_items[:3]:
            ai_html += f'''<div class="rec-item">
            <div class="ri-school">⭐ {it['school']} <span class="ri-major">| {it['major']}</span></div>
            <div><span class="ri-score">{it['avg_score']}分</span> <span class="ri-year">（历年平均）</span></div>
          </div>'''

    # 全部匹配项（取前5条）
    all_html = ''
    if items:
        shown = items[:5] if len(items) > 5 else items
        for it in shown:
            all_html += f'''<div class="rec-item" style="opacity:0.8;">
            <div class="ri-school">{it['school']} <span class="ri-major">| {it['major']}</span></div>
            <div><span class="ri-score">{it['avg_score']}分</span> <span class="ri-year">（历年平均）</span></div>
          </div>'''
        if len(items) > 5:
            all_html += f'<div class="rec-item"><span style="color:#94A3B8;font-size:12px;">… 还有 {len(items) - 5} 所</span></div>'

    body = ai_html or all_html or '<div class="empty-state">暂无匹配</div>'

    tag_names = {'chongci': '🔥 冲刺', 'wentuo': '📌 稳妥', 'baodi': '✅ 保底'}
    return f'''<div class="rec-card {category}">
      <div class="rec-tag">{tag_names.get(category, title)}</div>
      {body}
    </div>'''


def build_advice_html(sections):
    """构建建议卡片 HTML"""
    advice = sections.get('advice', '')
    if not advice:
        return ''
    return f'''<div class="section">
      <div class="section-title">💡 AI 备考建议</div>
      <div class="advice-card">
        <span class="advice-icon">📋</span>
        <span class="advice-text">{advice}</span>
      </div>
    </div>'''


def generate_html(school, major, score, data):
    """生成完整 HTML 报告"""
    sections = parse_ai_sections(data['result'])

    html = HTML_TEMPLATE
    html = html.replace('{school}', school)
    html = html.replace('{major}', major)
    html = html.replace('{score}', str(int(score)))

    html = html.replace('{prediction_html}', build_prediction_html(sections))
    html = html.replace('{history_html}', build_history_html(data['linian']))
    html = html.replace('{chongci_html}', build_rec_card_html('chongci', '冲刺', data['chongci'], sections))
    html = html.replace('{wentuo_html}', build_rec_card_html('wentuo', '稳妥', data['wentuo'], sections))
    html = html.replace('{baodi_html}', build_rec_card_html('baodi', '保底', data['baodi'], sections))
    html = html.replace('{advice_html}', build_advice_html(sections))

    return html


def ai_fenxi_and_report(school, major, score):
    """
    一站式分析入口：调用 AI 分析 → 控制台打印 → 生成 HTML 报告 → 自动打开浏览器。

    参数：
        school : str  目标院校名称
        major  : str  目标专业名称
        score  : int  考生预估分数

    返回：
        dict  AI 分析原始数据（result / linian / chongci / wentuo / baodi）
    """
    # 1. AI 分析
    data = ai_fenxi(school, major, score)

    # 2. 控制台输出结果
    print('')
    print('  ' + G + '-' * 44 + E)
    print('  ' + G + '        [分析结果]' + E)
    print('  ' + G + '-' * 44 + E)
    print('')
    print(W + data['result'] + E)

    # 3. 生成 HTML 报告
    print('')
    print('  ' + Y + '[正在生成 HTML 报告...]' + E)
    html_content = generate_html(school, major, score, data)

    html_path = os.path.abspath('./考研数据分析报告.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print('  ' + G + '[报告已生成] ' + html_path + E)

    # 4. 自动打开浏览器
    webbrowser.open('file://' + html_path)
    print('  ' + G + '[已在浏览器中打开报告]' + E)

    return data


# ---- 主程序 ----
if __name__ == '__main__':
    school = '北京大学'
    major = '金融'
    score = 370

    print('')
    print('  ' + C + '=' * 44 + E)
    print('  ' + C + '      考研数据智能分析系统' + E)
    print('  ' + C + '=' * 44 + E)
    print('')
    print('  ' + B + '目标院校：' + E + W + school + E)
    print('  ' + B + '目标专业：' + E + W + major + E)
    print('  ' + B + '预估分数：' + E + Y + str(score) + ' 分' + E)

    ai_fenxi_and_report(school, major, score)

    print('')
    print('  ' + C + '=' * 44 + E)
    print('  ' + C + '       分析结束' + E)
    print('  ' + C + '=' * 44 + E)
    print('')
