# Python 可视化 + BI 工具对接

> 选图决策表 + 4 大库实战模板 + BI 工具对接

## 1. 选图决策表(给 agent 用)

| 你想看什么 | 库 + 图 |
|---|---|
| 时间趋势 | matplotlib/seaborn `lineplot` / plotly `Scatter(mode='lines')` |
| 分布 | seaborn `histplot`/`kdeplot` / plotly `Histogram` |
| 类别对比 | seaborn `barplot` / plotly `Bar` |
| 相关 | seaborn `heatmap` / `pairplot` / plotly `Scatter matrix` |
| 占比 | plotly `Pie` / `Sunburst` / `Treemap` |
| 流程/转化 | plotly `Sankey` / `Funnel` |
| 地理 | plotly `Choropleth` / `Scatter geo` |
| 关系网络 | plotly `Scatter` + 自定义边 / networkx + plotly |
| 维度拆解 | plotly `Sunburst` / `Treemap` / `Icicle` |
| 异常 | seaborn `boxplot` / `violinplot` / plotly `Box` |
| 时序日历 | calmap / plotly `Heatmap`(x=week, y=weekday) |

## 2. matplotlib(基础,出版级)

```python
import matplotlib.pyplot as plt
import duckdb

# 1. 准备数据
df = duckdb.sql("""
    SELECT order_date, sum(amount) AS gmv
    FROM 'analytics.duckdb'.orders
    GROUP BY order_date
    ORDER BY order_date
""").df()

# 2. 画图
fig, ax = plt.subplots(figsize=(12, 5), dpi=100)
ax.plot(df['order_date'], df['gmv'], color='#d4a574', linewidth=1.5)
ax.fill_between(df['order_date'], df['gmv'], alpha=0.2, color='#d4a574')
ax.set_title('Daily GMV', fontsize=14, weight='bold')
ax.set_xlabel('Date')
ax.set_ylabel('GMV (¥)')
ax.grid(alpha=0.3)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

# 3. 保存(报告用,300dpi 出图清晰)
plt.tight_layout()
plt.savefig('/tmp/figures/gmv_trend.png', dpi=300, bbox_inches='tight')
plt.savefig('/tmp/figures/gmv_trend.pdf', bbox_inches='tight')  # 矢量,出版用
plt.show()
```

**字号/留白/配色 3 大细节**:
- 字号 14+ 标题,12+ 坐标
- 留白用 `tight_layout()` 或 `subplots_adjust()`
- 配色避免默认红蓝,**用 seaborn 调色板或自定义**

## 3. seaborn(统计图,快)

```python
import seaborn as sns
import matplotlib.pyplot as plt
import duckdb

df = duckdb.sql("""
    SELECT user_segment, plan, count(*) AS n
    FROM 'analytics.duckdb'.users
    GROUP BY ALL
""").df()

# 风格
sns.set_style("whitegrid")
sns.set_palette("muted")  # 或 "Set2" / "husl" / 自定义 list

# 分类柱状
fig, ax = plt.subplots(figsize=(10, 6))
sns.barplot(data=df, x='user_segment', y='n', hue='plan', ax=ax)
ax.set_title('User Distribution by Segment × Plan')
plt.tight_layout()
plt.savefig('/tmp/figures/users.png', dpi=300)

# 数值分布(直方图 + KDE)
sns.histplot(data=df, x='gmv', kde=True, bins=30)
# 回归
sns.regplot(data=df, x='age', y='gmv', scatter_kws={'alpha':0.3})
# 相关矩阵
sns.heatmap(df[['age', 'gmv', 'orders']].corr(), annot=True, cmap='coolwarm')
# 双变量分布
sns.jointplot(data=df, x='age', y='gmv', kind='hex')
# 类别内分布
sns.boxplot(data=df, x='plan', y='gmv')
sns.violinplot(data=df, x='plan', y='gmv')
```

## 4. plotly(交互,推荐内部探索 + 老板看板)

```python
import plotly.express as px
import plotly.graph_objects as go
import duckdb

df = duckdb.sql("""
    SELECT user_id, r_score, f_score, m_score, segment
    FROM 'analytics.duckdb'.rfm_segments
""").df()

# 4.1 一行出图(散点 + 4 维)
fig = px.scatter(
    df, x='r_score', y='f_score', size='m_score', color='segment',
    hover_data=['user_id'], title='RFM Segments',
    size_max=30
)
fig.update_layout(template='plotly_dark')  # 暗色 / 'plotly_white'
fig.write_html('/tmp/figures/rfm.html')
fig.write_image('/tmp/figures/rfm.png', width=1200, height=600)  # 需 kaleido

# 4.2 Sankey(流程/转化)
fig = go.Figure(go.Sankey(
    node=dict(label=['Visit', 'Sign Up', 'Active', 'Pay', 'Churn'],
              color=['#d4a574', '#e8c79c', '#c08a4e', '#8b5a2b', '#666']),
    link=dict(source=[0, 1, 2, 2, 3],
              target=[1, 2, 3, 4, 4],
              value=[10000, 3000, 500, 2500, 250])
))
fig.write_html('/tmp/figures/sankey.html')

# 4.3 Sunburst(层级)
fig = px.sunburst(df, path=['country', 'plan', 'segment'], values='gmv')
fig.write_html('/tmp/figures/sunburst.html')

# 4.4 带时间轴的动态图(动画)
fig = px.scatter(df, x='gdpPercap', y='lifeExp', animation_frame='year',
                 size='pop', color='continent', hover_name='country',
                 log_x=True, size_max=55, range_y=[25, 90])
fig.write_html('/tmp/figures/bubble_anim.html')

# 4.5 地图
fig = px.choropleth(df, locations='iso_alpha', color='gmv',
                    hover_name='country', range_color=(0, 100000))
fig.write_html('/tmp/figures/world_map.html')
```

**保存静态图**:`fig.write_image('x.png')` 需要 `pip install kaleido`(首次会装 chromium)

## 5. 多图组合(subplot)

```python
import matplotlib.pyplot as plt
import seaborn as sns

fig, axes = plt.subplots(2, 2, figsize=(14, 10))

sns.lineplot(data=df, x='date', y='gmv', ax=axes[0, 0])
axes[0, 0].set_title('Daily GMV')

sns.barplot(data=country_df, x='country', y='n', ax=axes[0, 1])
axes[0, 1].set_title('Users by Country')
axes[0, 1].tick_params(axis='x', rotation=45)

sns.histplot(data=df, x='amount', kde=True, ax=axes[1, 0])
axes[1, 0].set_title('Order Amount Distribution')

sns.heatmap(pivot, annot=True, fmt='.0f', cmap='YlGnBu', ax=axes[1, 1])
axes[1, 1].set_title('GMV Heatmap')

plt.tight_layout()
plt.savefig('/tmp/figures/dashboard.png', dpi=300)
```

**plotly 多图**:
```python
from plotly.subplots import make_subplots
fig = make_subplots(rows=2, cols=2, subplot_titles=('GMV', 'Users', 'Dist', 'Heatmap'))
fig.add_trace(go.Scatter(x=df['date'], y=df['gmv'], name='GMV'), row=1, col=1)
fig.add_trace(go.Bar(x=country_df['country'], y=country_df['n'], name='Users'), row=1, col=2)
# ...
fig.write_html('/tmp/figures/dashboard.html')
```

## 6. 拼图 / 报告排版

```python
from PIL import Image, ImageDraw, ImageFont

# 4 张图拼成 2x2 网格 + 标题
imgs = [Image.open(f'/tmp/figures/{n}') for n in ['a', 'b', 'c', 'd']]
w, h = imgs[0].size
LABEL_H = 28
canvas = Image.new('RGB', (w * 2 + 30, h * 2 + LABEL_H * 2 + 30), 'white')

# 拼
positions = [(0, 0), (w + 30, 0), (0, h + LABEL_H + 30), (w + 30, h + LABEL_H + 30)]
for img, pos in zip(imgs, positions):
    canvas.paste(img, pos)

# 标题
draw = ImageDraw.Draw(canvas)
draw.text((20, 5), 'Daily Analytics Report — 2026-06-20', fill='black')

canvas.save('/tmp/figures/report_20260620.png')
```

## 7. BI 工具对接(架构图右边那一块)

### 7.1 PowerBI 接 DuckDB(2 种方式)

**方式 A:DuckDB ODBC 驱动**(推荐)
```bash
# Linux 装 ODBC
sudo apt install unixodbc
# 装 DuckDB ODBC(从 duckdb.org 下载)
# 配置 /etc/odbcinst.ini:
[duckdb]
Driver = /usr/local/lib/duckdb_odbc.so
```

PowerBI Desktop → Get Data → ODBC → DSN=`duckdb` → Database=`/path/analytics.duckdb` → 选表

**方式 B:导出 Parquet**(零配置)
```python
import duckdb
duckdb.sql("""
    COPY (SELECT * FROM analytics.daily_metrics)
    TO '/mnt/powerbi/daily_metrics.parquet' (FORMAT PARQUET, COMPRESSION zstd)
""")
```
PowerBI Get Data → Parquet → 选文件 → 自动识别 schema

**方式 C:架构图里的 SQLite 中转**(老 PowerBI 兼容)
```bash
ingestr ingest \
  --source-uri "duckdb:///./analytics.duckdb" \
  --source-table "daily_metrics" \
  --dest-uri "sqlite:///./report.db"
```
PowerBI → Get Data → SQLite(可能要 ODBC 桥接)→ 选表

### 7.2 Tableau 接 DuckDB

Tableau 自 2024.2 支持 DuckDB 驱动(部分版本)。或走 Parquet 中转:
```python
duckdb.sql("COPY (SELECT * FROM ...) TO 'x.parquet' (FORMAT PARQUET)")
```

### 7.3 Excel 接 DuckDB

**方法 1:DuckDB CLI 导 CSV**
```bash
duckdb ./analytics.duckdb "COPY (SELECT * FROM daily_gmv) TO 'gmv.csv' (HEADER)"
# Excel 打开 gmv.csv
```

**方法 2:Power Query + ODBC**(Win/Mac)
- Excel → Data → Get Data → From Other Sources → ODBC
- 配 DuckDB ODBC 驱动(同 7.1 方式 A)
- 选表 → 加载 → 数据透视表

### 7.4 用 DuckDB 写 PowerBI DAX 友好的"星型模型"

```sql
-- 事实表
CREATE OR REPLACE TABLE fact_orders AS
SELECT * FROM raw_orders;

-- 维度表
CREATE OR REPLACE TABLE dim_users AS
SELECT user_id, country, plan, register_date FROM raw_users;

CREATE OR REPLACE TABLE dim_products AS
SELECT product_id, category, price FROM raw_products;

-- 时间维度(PowerBI 友好)
CREATE OR REPLACE TABLE dim_date AS
SELECT DISTINCT
    order_date,
    date_trunc('month', order_date) AS year_month,
    date_trunc('week', order_date) AS year_week,
    extract('dow' FROM order_date) AS weekday
FROM raw_orders;
```

BI 工具只认星型模型,这样切好维度和事实表,接上去最顺。

## 8. 看板工具(plotly 完整版)

**Streamlit**(5 分钟出 web app):
```python
import streamlit as st
import duckdb
import plotly.express as px

st.set_page_config(layout='wide')
st.title('Sales Dashboard')

con = duckdb.connect('analytics.duckdb', read_only=True)

col1, col2, col3 = st.columns(3)
with col1:
    gmv = con.sql("SELECT sum(amount) FROM orders").fetchone()[0]
    st.metric("Total GMV", f"¥{gmv:,.0f}")
# ... 更多 metric

df = con.sql("SELECT * FROM daily_metrics ORDER BY order_date").df()
fig = px.line(df, x='order_date', y='gmv', title='Daily GMV')
st.plotly_chart(fig, use_container_width=True)
```

**Dash**(更专业的 plotly 看板):
```python
import dash
from dash import dcc, html
import plotly.express as px
import duckdb

app = dash.Dash(__name__)
con = duckdb.connect('analytics.duckdb', read_only=True)
df = con.sql("SELECT * FROM daily_metrics").df()

app.layout = html.Div([
    html.H1('GMV Dashboard'),
    dcc.Graph(figure=px.line(df, x='order_date', y='gmv'))
])

if __name__ == '__main__':
    app.run_server(debug=True, port=8050)
```

## 9. 配色与排版(给报告提质感)

| 场景 | 推荐 |
|---|---|
| 商务报告 | seaborn `whitegrid` + 自定义企业色 |
| 暗色看板 | plotly `template='plotly_dark'` |
| 出版 | matplotlib + Nature/Science 配色 |
| 品牌色 | 查公司 VI,自定义 hex list |
| 配色参考 | https://coolors.co / https://colorbrewer2.org |

**基础配色**(中性):
```python
# 金/琥珀(dark luxury 风)
GOLD = ['#d4a574', '#e8c79c', '#c08a4e', '#8b5a2b', '#a07142']

# 蓝绿灰(专业)
BLUE = ['#1f77b4', '#17becf', '#2ca02c', '#bcbd22']

# 柔和(muted)
sns.set_palette("muted")
```

## 10. 输出物清单(给 agent 自检)

每跑完一个分析,**应该有以下产物**:

```
/tmp/analysis_2026-06-20/
├── analytics.duckdb              # 数据源(可复用)
├── queries.sql                   # 用过的 SQL(审计 + 重现)
├── notebook.ipynb                # 探索过程(可选)
├── figures/                      # 图表
│   ├── gmv_trend.png             # matplotlib 静态
│   ├── gmv_trend.html            # plotly 交互
│   ├── rfm_scatter.html          # 高级图
│   ├── dashboard.png             # 拼图
│   └── *.parquet                 # 给 PowerBI 读
├── report.md                     # 业务结论
└── streamlit_app.py              # 或 dash app(可选)
```

**只给一张图没 SQL 记录 = 不可重现**,下次业务问"这个数怎么算的"答不上来。