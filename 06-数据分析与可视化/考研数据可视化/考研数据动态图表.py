#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根据院校历年分数线 CSV 生成可离线打开的交互式数据看板。"""
# 下载指定版本的plotly库 pip install plotly==5.18

from __future__ import annotations

import argparse
import csv
import html
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence


BASE_DIR = Path(__file__).resolve().parent
VENDOR_DIR = BASE_DIR / ".vendor"
if VENDOR_DIR.exists():
    sys.path.insert(0, str(VENDOR_DIR))

try:
    import plotly.graph_objects as go
    import plotly.io as pio
except ModuleNotFoundError as exc:
    raise SystemExit(
        "缺少 Plotly。请运行：\n"
        "python -m pip install --target .vendor \"plotly>=5.18,<7\""
    ) from exc


FIELDS = {
    "school": "学校",
    "major": "专业",
    "code": "代码",
    "department": "招生院系",
    "total": "总分",
    "politics": "政治",
    "foreign": "外语",
    "major1": "专业课一",
    "major2": "专业课二",
    "year": "录取年份",
}

CATEGORY_NAMES = {
    "01": "哲学",
    "02": "经济学",
    "03": "法学",
    "04": "教育学",
    "05": "文学",
    "06": "历史学",
    "07": "理学",
    "08": "工学",
    "09": "农学",
    "10": "医学",
    "11": "军事学",
    "12": "管理学",
    "13": "艺术学",
    "14": "交叉学科",
}

PALETTE = [
    "#0E7C7B",
    "#E4572E",
    "#F3A712",
    "#3D5A80",
    "#8F5D5D",
    "#2A9D8F",
    "#D1495B",
    "#577590",
    "#6A994E",
    "#BC6C25",
]

PLOT_CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "scrollZoom": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d"],
    "toImageButtonOptions": {
        "format": "png",
        "filename": "考研数据图表",
        "scale": 2,
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成考研院校分数线交互式图表")
    parser.add_argument(
        "csv_file",
        nargs="?",
        type=Path,
        default=BASE_DIR / "各院校历年数据采集.csv",
        help="CSV 数据文件路径",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=BASE_DIR / "考研数据炫酷动态图表.html",
        help="输出 HTML 路径",
    )
    return parser.parse_args()


def to_number(value: object) -> Optional[float]:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def load_rows(path: Path) -> List[dict]:
    if not path.exists():
        raise FileNotFoundError(f"找不到数据文件：{path}")

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        missing = [name for name in FIELDS.values() if name not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"CSV 缺少字段：{', '.join(missing)}")

        rows = []
        for raw in reader:
            total = to_number(raw[FIELDS["total"]])
            year = str(raw[FIELDS["year"]]).strip()
            school = str(raw[FIELDS["school"]]).strip()
            if total is None or not year or not school:
                continue
            rows.append(
                {
                    "school": school,
                    "major": str(raw[FIELDS["major"]]).strip(),
                    "code": str(raw[FIELDS["code"]]).strip(),
                    "department": str(raw[FIELDS["department"]]).strip(),
                    "total": total,
                    "politics": to_number(raw[FIELDS["politics"]]),
                    "foreign": to_number(raw[FIELDS["foreign"]]),
                    "major1": to_number(raw[FIELDS["major1"]]),
                    "major2": to_number(raw[FIELDS["major2"]]),
                    "year": year,
                }
            )
    if not rows:
        raise ValueError("CSV 中没有可用的分数记录")
    return rows


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values)


def score_category(code: str) -> str:
    digits = "".join(char for char in code if char.isdigit())
    prefix = digits[:2]
    return CATEGORY_NAMES.get(prefix, "其他门类")


def annual_school_stats(rows: Sequence[dict]) -> Dict[str, Dict[str, dict]]:
    grouped: Dict[str, Dict[str, List[dict]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[row["year"]][row["school"]].append(row)

    result: Dict[str, Dict[str, dict]] = {}
    for year, schools in grouped.items():
        result[year] = {}
        for school, items in schools.items():
            scores = [item["total"] for item in items]
            result[year][school] = {
                "average": mean(scores),
                "median": statistics.median(scores),
                "minimum": min(scores),
                "maximum": max(scores),
                "count": len(items),
                "major_count": len({item["major"] for item in items}),
            }
    return result


def year_sort_key(value: str) -> tuple:
    return (0, int(value)) if value.isdigit() else (1, value)


def base_layout(fig: go.Figure, *, height: int, margin: Optional[dict] = None) -> None:
    fig.update_layout(
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,0)",
        font={
            "family": "Microsoft YaHei, PingFang SC, Arial, sans-serif",
            "color": "#27313A",
            "size": 13,
        },
        hoverlabel={
            "bgcolor": "#FFFFFF",
            "bordercolor": "#D7DEDC",
            "font": {"color": "#27313A", "size": 13},
        },
        margin=margin or {"l": 65, "r": 35, "t": 55, "b": 65},
        transition={"duration": 500, "easing": "cubic-in-out"},
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor="#E4E9E7",
        zeroline=False,
        linecolor="#C9D2CF",
        tickfont={"color": "#5A6864"},
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="#E4E9E7",
        zeroline=False,
        linecolor="#C9D2CF",
        tickfont={"color": "#5A6864"},
    )


def build_rank_chart(stats: Dict[str, Dict[str, dict]], years: Sequence[str]) -> go.Figure:
    max_average = max(
        item["average"] for year in years for item in stats[year].values()
    )

    def trace(year: str) -> go.Bar:
        ranking = sorted(
            stats[year].items(), key=lambda item: item[1]["average"], reverse=True
        )[:12]
        ranking.reverse()
        values = [item[1]["average"] for item in ranking]
        colors = [
            f"rgba(14,124,123,{0.46 + 0.5 * (index + 1) / len(ranking):.2f})"
            for index in range(len(ranking))
        ]
        return go.Bar(
            x=values,
            y=[item[0] for item in ranking],
            orientation="h",
            marker={"color": colors, "line": {"color": "#FFFFFF", "width": 0.5}},
            text=[f"{value:.1f}" for value in values],
            textposition="outside",
            cliponaxis=False,
            customdata=[
                [item[1]["count"], item[1]["minimum"], item[1]["maximum"]]
                for item in ranking
            ],
            hovertemplate=(
                "<b>%{y}</b><br>平均分：%{x:.1f}<br>"
                "记录数：%{customdata[0]}<br>分数范围："
                "%{customdata[1]:.0f}–%{customdata[2]:.0f}<extra></extra>"
            ),
        )

    fig = go.Figure(
        data=[trace(years[-1])],
        frames=[go.Frame(name=year, data=[trace(year)]) for year in years],
    )
    base_layout(fig, height=580, margin={"l": 175, "r": 65, "t": 35, "b": 55})
    fig.update_layout(
        xaxis={"title": "院校平均总分", "range": [0, max_average + 35]},
        yaxis={"title": "", "automargin": True},
        showlegend=False,
    )
    return fig


def build_bubble_chart(stats: Dict[str, Dict[str, dict]], years: Sequence[str]) -> go.Figure:
    all_counts = [item["count"] for year in years for item in stats[year].values()]
    all_averages = [item["average"] for year in years for item in stats[year].values()]
    max_count = max(all_counts)
    size_ref = 2.0 * max_count / (52.0**2)

    def trace(year: str) -> go.Scatter:
        school_items = sorted(stats[year].items(), key=lambda item: item[1]["count"], reverse=True)
        labels = {name for name, _ in school_items[:7]}
        return go.Scatter(
            x=[item[1]["average"] for item in school_items],
            y=[item[1]["major_count"] for item in school_items],
            mode="markers+text",
            text=[name if name in labels else "" for name, _ in school_items],
            textposition="top center",
            textfont={"size": 11, "color": "#46534F"},
            marker={
                "size": [item[1]["count"] for item in school_items],
                "sizemode": "area",
                "sizeref": size_ref,
                "sizemin": 9,
                "color": [item[1]["average"] for item in school_items],
                "cmin": min(all_averages),
                "cmax": max(all_averages),
                "colorscale": [
                    [0.0, "#3D5A80"],
                    [0.45, "#2A9D8F"],
                    [0.75, "#F3A712"],
                    [1.0, "#E4572E"],
                ],
                "showscale": True,
                "colorbar": {"title": "平均分", "thickness": 12, "len": 0.72},
                "line": {"color": "rgba(255,255,255,0.9)", "width": 1.5},
                "opacity": 0.88,
            },
            customdata=[
                [name, item["count"], item["minimum"], item["maximum"], item["median"]]
                for name, item in school_items
            ],
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>平均总分：%{x:.1f}<br>"
                "专业方向：%{y}<br>记录数：%{customdata[1]}<br>"
                "中位数：%{customdata[4]:.1f}<br>分数范围："
                "%{customdata[2]:.0f}–%{customdata[3]:.0f}<extra></extra>"
            ),
        )

    fig = go.Figure(
        data=[trace(years[-1])],
        frames=[go.Frame(name=year, data=[trace(year)]) for year in years],
    )
    base_layout(fig, height=530, margin={"l": 70, "r": 90, "t": 40, "b": 65})
    fig.update_layout(
        xaxis={"title": "院校平均总分", "range": [min(all_averages) - 15, max(all_averages) + 15]},
        yaxis={"title": "当年专业方向数量", "rangemode": "tozero"},
        showlegend=False,
    )
    return fig


def build_heatmap(rows: Sequence[dict], years: Sequence[str]) -> go.Figure:
    score_columns = [
        ("总分", "total"),
        ("政治", "politics"),
        ("外语", "foreign"),
        ("专业课一", "major1"),
        ("专业课二", "major2"),
    ]
    grouped: Dict[str, Dict[str, List[dict]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[row["year"]][row["school"]].append(row)

    schools = sorted(
        {row["school"] for row in rows},
        key=lambda school: mean(row["total"] for row in rows if row["school"] == school),
        reverse=True,
    )

    def trace(year: str) -> go.Heatmap:
        raw_matrix: List[List[Optional[float]]] = []
        for school in schools:
            school_rows = grouped[year].get(school, [])
            row_values: List[Optional[float]] = []
            for _, field in score_columns:
                values = [
                    item[field]
                    for item in school_rows
                    if item[field] is not None and (field == "total" or item[field] > 0)
                ]
                row_values.append(round(mean(values), 1) if values else None)
            raw_matrix.append(row_values)

        normalized = [[None for _ in score_columns] for _ in schools]
        for column_index in range(len(score_columns)):
            column_values = [
                row[column_index] for row in raw_matrix if row[column_index] is not None
            ]
            low = min(column_values) if column_values else 0
            high = max(column_values) if column_values else 1
            spread = high - low or 1
            for row_index, row_values in enumerate(raw_matrix):
                value = row_values[column_index]
                if value is not None:
                    normalized[row_index][column_index] = (value - low) / spread

        return go.Heatmap(
            z=normalized,
            x=[label for label, _ in score_columns],
            y=schools,
            text=raw_matrix,
            customdata=raw_matrix,
            texttemplate="%{text:.0f}",
            textfont={"size": 10},
            zmin=0,
            zmax=1,
            colorscale=[
                [0.0, "#3D5A80"],
                [0.35, "#78B7B1"],
                [0.55, "#F3E9C7"],
                [0.78, "#F3A712"],
                [1.0, "#D1495B"],
            ],
            colorbar={
                "title": "同科目相对位置",
                "thickness": 13,
                "tickvals": [0, 0.5, 1],
                "ticktext": ["低", "中", "高"],
            },
            xgap=3,
            ygap=3,
            hovertemplate="<b>%{y}</b><br>%{x}平均线：%{customdata:.1f}<extra></extra>",
        )

    fig = go.Figure(
        data=[trace(years[-1])],
        frames=[go.Frame(name=year, data=[trace(year)]) for year in years],
    )
    base_layout(fig, height=700, margin={"l": 190, "r": 80, "t": 35, "b": 55})
    fig.update_layout(xaxis={"title": "科目", "side": "top"}, yaxis={"title": ""})
    return fig


def build_distribution_chart(rows: Sequence[dict], years: Sequence[str]) -> go.Figure:
    lower = int(min(row["total"] for row in rows) // 20 * 20)
    upper = int(math.ceil(max(row["total"] for row in rows) / 20) * 20)
    bin_size = 15
    starts = list(range(lower, upper, bin_size))
    centers = [start + bin_size / 2 for start in starts]

    def counts_for(year: str) -> List[int]:
        counts = [0] * len(starts)
        for row in rows:
            if row["year"] != year:
                continue
            index = min(int((row["total"] - lower) // bin_size), len(counts) - 1)
            if index >= 0:
                counts[index] += 1
        return counts

    def trace(year: str) -> go.Bar:
        return go.Bar(
            x=centers,
            y=counts_for(year),
            width=bin_size * 0.86,
            marker={
                "color": centers,
                "colorscale": [[0, "#3D5A80"], [0.5, "#2A9D8F"], [1, "#E4572E"]],
                "cmin": lower,
                "cmax": upper,
                "line": {"color": "rgba(255,255,255,0.8)", "width": 0.7},
            },
            customdata=[[start, start + bin_size] for start in starts],
            hovertemplate="%{customdata[0]:.0f}–%{customdata[1]:.0f} 分<br>记录数：%{y}<extra></extra>",
        )

    fig = go.Figure(
        data=[trace(years[-1])],
        frames=[go.Frame(name=year, data=[trace(year)]) for year in years],
    )
    base_layout(fig, height=445, margin={"l": 65, "r": 35, "t": 35, "b": 65})
    fig.update_layout(
        xaxis={"title": "总分区间", "range": [lower - 5, upper + 5]},
        yaxis={"title": "记录数", "rangemode": "tozero"},
        bargap=0.04,
        showlegend=False,
    )
    return fig


def build_trend_chart(stats: Dict[str, Dict[str, dict]], years: Sequence[str]) -> go.Figure:
    total_counts = Counter()
    for year in years:
        for school, item in stats[year].items():
            total_counts[school] += item["count"]
    schools = [school for school, _ in total_counts.most_common(10)]
    all_averages = [
        stats[year][school]["average"]
        for year in years
        for school in schools
        if school in stats[year]
    ]

    def traces_until(selected_year: str) -> List[go.Scatter]:
        selected_index = years.index(selected_year)
        visible_years = years[: selected_index + 1]
        traces = []
        for index, school in enumerate(schools):
            points = [
                (year, stats[year][school]["average"], stats[year][school]["count"])
                for year in visible_years
                if school in stats[year]
            ]
            traces.append(
                go.Scatter(
                    x=[point[0] for point in points],
                    y=[point[1] for point in points],
                    mode="lines+markers",
                    name=school,
                    line={"color": PALETTE[index % len(PALETTE)], "width": 2.7},
                    marker={"size": 7, "line": {"color": "#FFFFFF", "width": 1}},
                    customdata=[[point[2]] for point in points],
                    hovertemplate=(
                        f"<b>{html.escape(school)}</b><br>%{{x}} 年：%{{y:.1f}} 分"
                        "<br>记录数：%{customdata[0]}<extra></extra>"
                    ),
                )
            )
        return traces

    fig = go.Figure(
        data=traces_until(years[-1]),
        frames=[go.Frame(name=year, data=traces_until(year)) for year in years],
    )
    base_layout(fig, height=540, margin={"l": 65, "r": 35, "t": 35, "b": 120})
    fig.update_layout(
        xaxis={
            "title": "录取年份",
            "type": "category",
            "categoryorder": "array",
            "categoryarray": list(years),
            "range": [-0.25, len(years) - 0.75],
        },
        yaxis={
            "title": "院校平均总分",
            "range": [min(all_averages) - 15, max(all_averages) + 15],
        },
        hovermode="x unified",
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.22,
            "xanchor": "center",
            "x": 0.5,
            "font": {"size": 11},
        },
    )
    return fig


def build_sunburst(rows: Sequence[dict], years: Sequence[str]) -> go.Figure:
    rows_by_year = {
        year: [row for row in rows if row["year"] == year]
        for year in years
    }
    color_min = min(row["total"] for row in rows)
    color_max = max(row["total"] for row in rows)

    def trace(year: str) -> go.Sunburst:
        year_rows = rows_by_year[year]
        category_rows: Dict[str, List[dict]] = defaultdict(list)
        category_school_rows: Dict[tuple, List[dict]] = defaultdict(list)
        for row in year_rows:
            category = score_category(row["code"])
            category_rows[category].append(row)
            category_school_rows[(category, row["school"])].append(row)

        ids = ["root"]
        labels = ["全部学科门类"]
        parents = [""]
        values = [len(year_rows)]
        colors = [mean(row["total"] for row in year_rows)]
        custom = [[len(year_rows), colors[0]]]

        for category in sorted(category_rows, key=lambda key: len(category_rows[key]), reverse=True):
            items = category_rows[category]
            category_id = f"category::{category}"
            ids.append(category_id)
            labels.append(category)
            parents.append("root")
            values.append(len(items))
            average = mean(item["total"] for item in items)
            colors.append(average)
            custom.append([len(items), average])

            school_groups = [
                (school, group)
                for (item_category, school), group in category_school_rows.items()
                if item_category == category
            ]
            for school, group in sorted(school_groups, key=lambda item: len(item[1]), reverse=True):
                average = mean(item["total"] for item in group)
                ids.append(f"{category_id}::{school}")
                labels.append(school)
                parents.append(category_id)
                values.append(len(group))
                colors.append(average)
                custom.append([len(group), average])

        return go.Sunburst(
            ids=ids,
            labels=labels,
            parents=parents,
            values=values,
            branchvalues="total",
            maxdepth=2,
            insidetextorientation="radial",
            marker={
                "colors": colors,
                "colorscale": [
                    [0, "#3D5A80"],
                    [0.42, "#2A9D8F"],
                    [0.72, "#F3A712"],
                    [1, "#E4572E"],
                ],
                "line": {"color": "#FFFFFF", "width": 1.4},
                "colorbar": {"title": "平均总分", "thickness": 13},
                "cmin": color_min,
                "cmax": color_max,
            },
            customdata=custom,
            hovertemplate=(
                "<b>%{label}</b><br>记录数：%{customdata[0]}<br>"
                "平均总分：%{customdata[1]:.1f}<extra></extra>"
            ),
        )

    fig = go.Figure(
        data=[trace(years[-1])],
        frames=[go.Frame(name=year, data=[trace(year)]) for year in years],
    )
    base_layout(fig, height=680, margin={"l": 20, "r": 20, "t": 25, "b": 20})
    return fig


def figure_html(fig: go.Figure, div_id: str, include_js: bool = False) -> str:
    return pio.to_html(
        fig,
        full_html=False,
        include_plotlyjs="inline" if include_js else False,
        config=PLOT_CONFIG,
        div_id=div_id,
    )


def build_report(rows: Sequence[dict], source_path: Path) -> str:
    years = sorted({row["year"] for row in rows}, key=year_sort_key)
    schools = sorted({row["school"] for row in rows})
    majors = {row["major"] for row in rows}
    scores = [row["total"] for row in rows]
    stats = annual_school_stats(rows)
    latest_year = years[-1]
    latest_leader, latest_leader_stats = max(
        stats[latest_year].items(), key=lambda item: item[1]["average"]
    )

    figures = [
        ("rank-chart", build_rank_chart(stats, years)),
        ("bubble-chart", build_bubble_chart(stats, years)),
        ("heatmap-chart", build_heatmap(rows, years)),
        ("distribution-chart", build_distribution_chart(rows, years)),
        ("trend-chart", build_trend_chart(stats, years)),
        ("sunburst-chart", build_sunburst(rows, years)),
    ]
    chart_html = {
        div_id: figure_html(fig, div_id, include_js=index == 0)
        for index, (div_id, fig) in enumerate(figures)
    }
    def make_year_picker(chart_id: str) -> str:
        buttons = "\n".join(
            f'<button type="button" class="year-chip{" active" if year == latest_year else ""}" '
            f'data-year="{html.escape(year)}" aria-label="切换到 {html.escape(year)} 年">'
            f'{html.escape(year)}</button>'
            for year in years
        )
        return (
            f'<div class="panel-year-picker" data-chart-target="{chart_id}">'
            f'<span class="picker-label">年份</span><div class="year-track">{buttons}</div></div>'
        )

    year_pickers = {
        chart_id: make_year_picker(chart_id)
        for chart_id in (
            "rank-chart",
            "bubble-chart",
            "heatmap-chart",
            "distribution-chart",
            "trend-chart",
            "sunburst-chart",
        )
    }

    source_label = html.escape(source_path.name)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>考研院校分数线动态看板</title>
  <style>
    :root {{
      --canvas: #F3F6F4;
      --surface: #FFFFFF;
      --ink: #27313A;
      --muted: #687672;
      --line: #DCE3E0;
      --teal: #0E7C7B;
      --coral: #E4572E;
      --gold: #F3A712;
      --navy: #3D5A80;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background: var(--canvas);
      font-family: "Microsoft YaHei", "PingFang SC", Arial, sans-serif;
      letter-spacing: 0;
    }}
    header {{
      background: #20312F;
      color: #FFFFFF;
      padding: 34px 5vw 30px;
      border-bottom: 5px solid var(--coral);
    }}
    .header-inner, main, footer {{ max-width: 1440px; margin: 0 auto; }}
    .eyebrow {{ color: #9FD4CF; font-size: 13px; font-weight: 700; }}
    h1 {{ margin: 8px 0 6px; font-size: clamp(28px, 4vw, 46px); line-height: 1.15; }}
    .subtitle {{ margin: 0; color: #C7D7D4; font-size: 14px; }}
    main {{ padding: 24px 24px 48px; }}
    .kpis {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 24px;
    }}
    .kpi {{
      min-width: 0;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px 17px;
      box-shadow: 0 2px 12px rgba(39,49,58,0.05);
    }}
    .kpi span {{ display: block; color: var(--muted); font-size: 12px; margin-bottom: 7px; }}
    .kpi strong {{ display: block; font-size: 24px; line-height: 1.2; overflow-wrap: anywhere; }}
    .kpi:nth-child(1) strong {{ color: var(--teal); }}
    .kpi:nth-child(2) strong {{ color: var(--coral); }}
    .kpi:nth-child(3) strong {{ color: var(--navy); }}
    .kpi:nth-child(4) strong {{ color: #B77800; }}
    .kpi:nth-child(5) strong {{ color: var(--teal); font-size: 19px; }}
    .panel-topline {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 18px;
    }}
    .panel-title-block {{ min-width: 0; }}
    .panel-year-picker {{
      display: flex;
      align-items: center;
      gap: 9px;
      flex: 0 0 auto;
      padding: 5px 6px 5px 10px;
      background: #E7EFEC;
      border-left: 3px solid var(--teal);
    }}
    .picker-label {{ color: var(--muted); font-size: 12px; font-weight: 700; }}
    .year-track {{ display: flex; align-items: center; gap: 5px; }}
    .year-chip {{
      appearance: none;
      border: 1px solid #B8C9C4;
      border-radius: 5px;
      background: #FFFFFF;
      color: #44534F;
      min-width: 58px;
      padding: 7px 9px;
      font: inherit;
      font-size: 13px;
      font-weight: 700;
      cursor: default;
      transition: background-color 180ms ease, color 180ms ease, border-color 180ms ease, transform 180ms ease;
    }}
    .year-chip:hover, .year-chip:focus-visible, .year-chip.active {{
      border-color: var(--coral);
      background: var(--coral);
      color: #FFFFFF;
      outline: none;
      transform: translateY(-1px);
    }}
    [data-year-label] {{ color: var(--coral); }}
    .chart-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }}
    .chart-panel {{
      min-width: 0;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      box-shadow: 0 3px 16px rgba(39,49,58,0.055);
    }}
    .chart-panel.wide {{ grid-column: 1 / -1; }}
    .panel-heading {{ padding: 18px 21px 0; }}
    .panel-heading h2 {{ margin: 0; font-size: 18px; line-height: 1.35; }}
    .panel-heading p {{ margin: 6px 0 0; color: var(--muted); font-size: 12px; }}
    .chart {{ width: 100%; min-height: 420px; }}
    footer {{ padding: 0 24px 32px; color: var(--muted); font-size: 12px; line-height: 1.7; }}
    @media (max-width: 980px) {{
      .kpis {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .panel-topline {{ flex-direction: column; gap: 12px; }}
      .chart-grid {{ grid-template-columns: 1fr; }}
      .chart-panel.wide {{ grid-column: auto; }}
    }}
    @media (max-width: 600px) {{
      header {{ padding: 26px 18px 24px; }}
      main {{ padding: 16px 10px 32px; }}
      .kpis {{ grid-template-columns: 1fr 1fr; gap: 8px; }}
      .kpi {{ padding: 13px 12px; }}
      .kpi strong {{ font-size: 20px; }}
      .kpi:last-child {{ grid-column: 1 / -1; }}
      .panel-year-picker {{ width: 100%; overflow-x: auto; }}
      .year-track {{ overflow-x: auto; padding-bottom: 2px; }}
      .year-chip {{ min-width: 58px; padding: 7px 9px; }}
      .panel-heading {{ padding: 16px 15px 0; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="header-inner">
      <div class="eyebrow">POSTGRADUATE ADMISSION DATA</div>
      <h1>考研院校分数线动态看板</h1>
      <p class="subtitle">{years[0]}–{years[-1]} 年 · 院校与专业录取线多维分析</p>
    </div>
  </header>
  <main>
    <section class="kpis">
      <div class="kpi"><span>有效记录</span><strong>{len(rows):,}</strong></div>
      <div class="kpi"><span>覆盖院校</span><strong>{len(schools)}</strong></div>
      <div class="kpi"><span>专业名称</span><strong>{len(majors)}</strong></div>
      <div class="kpi"><span>全量平均总分</span><strong>{mean(scores):.1f}</strong></div>
      <div class="kpi"><span>{latest_year} 平均分最高院校</span><strong>{html.escape(latest_leader)} · {latest_leader_stats['average']:.1f}</strong></div>
    </section>

    <section class="chart-grid">
      <article class="chart-panel wide">
        <div class="panel-heading"><div class="panel-topline"><div class="panel-title-block"><h2><span data-year-label="rank-chart">{latest_year}</span> 年院校平均分排名</h2><p>当年平均总分最高的 12 所院校</p></div>{year_pickers['rank-chart']}</div></div>
        <div class="chart">{chart_html['rank-chart']}</div>
      </article>

      <article class="chart-panel wide">
        <div class="panel-heading"><div class="panel-topline"><div class="panel-title-block"><h2><span data-year-label="bubble-chart">{latest_year}</span> 年院校竞争度与专业覆盖</h2><p>横轴为平均总分，纵轴为专业方向数量，气泡大小代表记录量</p></div>{year_pickers['bubble-chart']}</div></div>
        <div class="chart">{chart_html['bubble-chart']}</div>
      </article>

      <article class="chart-panel">
        <div class="panel-heading"><div class="panel-topline"><div class="panel-title-block"><h2><span data-year-label="heatmap-chart">{latest_year}</span> 年院校分数结构热力图</h2><p>数字为科目平均线，颜色表示院校在同科目中的相对位置</p></div>{year_pickers['heatmap-chart']}</div></div>
        <div class="chart">{chart_html['heatmap-chart']}</div>
      </article>

      <article class="chart-panel">
        <div class="panel-heading"><div class="panel-topline"><div class="panel-title-block"><h2><span data-year-label="distribution-chart">{latest_year}</span> 年总分分布</h2><p>观察不同分数段的记录密度变化</p></div>{year_pickers['distribution-chart']}</div></div>
        <div class="chart">{chart_html['distribution-chart']}</div>
      </article>

      <article class="chart-panel wide">
        <div class="panel-heading"><div class="panel-topline"><div class="panel-title-block"><h2>截至 <span data-year-label="trend-chart">{latest_year}</span> 年的重点院校平均分趋势</h2><p>按数据记录量选取前 10 所院校，年份切换会逐步展开趋势</p></div>{year_pickers['trend-chart']}</div></div>
        <div class="chart">{chart_html['trend-chart']}</div>
      </article>

      <article class="chart-panel wide">
        <div class="panel-heading"><div class="panel-topline"><div class="panel-title-block"><h2><span data-year-label="sunburst-chart">{latest_year}</span> 年学科门类与院校结构</h2><p>扇区面积代表当年记录量，颜色代表平均总分</p></div>{year_pickers['sunburst-chart']}</div></div>
        <div class="chart">{chart_html['sunburst-chart']}</div>
      </article>
    </section>
  </main>
  <footer>
    数据来源：{source_label}。图中平均值按 CSV 有效记录计算；不同专业的考试科目结构存在差异，跨专业比较时应结合具体招生目录理解。
  </footer>
  <script>
    (function () {{
      const pickers = Array.from(document.querySelectorAll('.panel-year-picker'));

      pickers.forEach(function (picker) {{
        const chartId = picker.dataset.chartTarget;
        const chips = Array.from(picker.querySelectorAll('.year-chip'));
        const yearLabel = document.querySelector('[data-year-label="' + chartId + '"]');
        let activeYear = '{latest_year}';

        function showYear(year) {{
          if (!window.Plotly || year === activeYear) return;
          activeYear = year;
          chips.forEach(function (chip) {{
            chip.classList.toggle('active', chip.dataset.year === year);
          }});
          if (yearLabel) yearLabel.textContent = year;
          Plotly.animate(chartId, [year], {{
            frame: {{duration: 320, redraw: true}},
            transition: {{duration: 260, easing: 'cubic-in-out'}},
            fromcurrent: true,
            mode: 'immediate'
          }});
        }}

        chips.forEach(function (chip) {{
          chip.addEventListener('pointerenter', function () {{ showYear(chip.dataset.year); }});
          chip.addEventListener('focus', function () {{ showYear(chip.dataset.year); }});
          chip.addEventListener('click', function () {{ showYear(chip.dataset.year); }});
        }});
      }});
    }})();
  </script>
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    csv_path = args.csv_file.resolve()
    output_path = args.output.resolve()
    rows = load_rows(csv_path)
    report = build_report(rows, csv_path)
    output_path.write_text(report, encoding="utf-8")
    print(f"已读取 {len(rows):,} 条有效记录")
    print(f"动态图表已生成：{output_path}")


if __name__ == "__main__":
    main()
