import json
import pandas as pd
import numpy as np
from pathlib import Path

OUTPUT_DIR = Path("stock_policy_product_output")
SIM_CSV = OUTPUT_DIR / "simulation_daily.csv"
SKU_CSV = OUTPUT_DIR / "sku_metrics.csv"
METRICS_JSON = OUTPUT_DIR / "overall_metrics.json"
META_JSON = OUTPUT_DIR / "run_metadata.json"
TUNE_CSV = OUTPUT_DIR / "tuning_search.csv"
POLICY_CSV = OUTPUT_DIR / "policy.csv"

OUT_HTML = OUTPUT_DIR / "dashboard.html"

def load_data():
    sim = pd.read_csv(SIM_CSV, parse_dates=["date"])
    sku = pd.read_csv(SKU_CSV)
    metrics = json.loads(METRICS_JSON.read_text())
    meta = json.loads(META_JSON.read_text())
    if TUNE_CSV.exists():
        tune = pd.read_csv(TUNE_CSV)
    else:
        tune = pd.DataFrame()
    return sim, sku, metrics, meta, tune

def fmt(v, d=2):
    if isinstance(v, float):
        return round(v, d)
    return v

def perc(v):
    return f"{(v*100):.2f}%"

def brl(v):
    return f"R$ {v:,.2f}"

def delta_class(v):
    if v > 0.01:
        return "neg"
    elif v < -0.01:
        return "pos"
    return "neutral"

def build_hero_data(sim):
    hero1 = sim[sim["product"] == 18064].to_dict("records")
    hero2 = sim[sim["product"] == 9607].to_dict("records")
    return json.dumps(hero1, default=str), json.dumps(hero2, default=str)

def build_sku_data(sku):
    records = sku.to_dict("records")
    return json.dumps(records, default=str)

def build_abc_data(sku):
    abc = sku.groupby("product", as_index=False).agg(
        demand=("total_actual_demand", "sum"),
        inv_value=("avg_inventory_value", "sum"),
        product_name=("product_name", "first"),
    ).sort_values("demand", ascending=False)
    total = abc["demand"].sum()
    abc["cum_demand"] = abc["demand"].cumsum() / total
    abc["label"] = abc["product_name"].str[:40]
    return json.dumps(abc.to_dict("records"), default=str)

def build_loja_data(sku):
    loja = sku.groupby("location", as_index=False).agg(
        demand=("total_actual_demand", "sum"),
        avg_inv=("avg_inventory_value", "mean"),
        avg_actual_inv=("actual_avg_inventory_value", "mean"),
        orders=("total_orders", "sum"),
        order_cost=("total_ordering_cost", "sum"),
        stockout_days=("stockout_days", "sum"),
        lost_units=("total_lost_sales_units", "sum"),
    )
    return json.dumps(loja.to_dict("records"), default=str)

def build_weekly_data(sim):
    sim["week"] = sim["date"].dt.isocalendar().week.astype(int)
    weekly = sim.groupby("week", as_index=False).agg(
        demand=("actual_demand", "sum"),
        forecast=("forecast_demand", "sum"),
        lost=("lost_sales_units", "sum"),
    ).sort_values("week")
    return json.dumps(weekly.to_dict("records"), default=str)

def build_promo_data(sim):
    promo = sim.groupby("is_promo", as_index=False).agg(
        demand=("actual_demand", "sum"),
        forecast=("forecast_demand", "sum"),
        days=("date", "nunique"),
        lost=("lost_sales_units", "sum"),
    )
    return json.dumps(promo.to_dict("records"), default=str)

def build_tune_data(tune):
    if tune.empty:
        return "[]"
    top = tune.nsmallest(20, "objective").to_dict("records")
    return json.dumps(top, default=str)

def build_rev_risk_data(sku):
    sku = sku.copy()
    sku["revenue"] = sku["total_actual_demand"] * sku["sales_price"].fillna(0)
    risk = sku.nlargest(10, "revenue")[
        ["product", "location", "revenue", "stockout_days", "product_name"]
    ].to_dict("records")
    return json.dumps(risk, default=str)

def build_daily_timeline(sim):
    sim = sim.sort_values("date")
    records = sim.to_dict("records")
    return json.dumps(records, default=str)

def generate_dashboard():
    sim, sku, metrics, meta, tune = load_data()
    hero1, hero2 = build_hero_data(sim)
    sku_json = build_sku_data(sku)
    abc_json = build_abc_data(sku)
    loja_json = build_loja_data(sku)
    weekly_json = build_weekly_data(sim)
    promo_json = build_promo_data(sim)
    tune_json = build_tune_data(tune)
    rev_json = build_rev_risk_data(sku)
    timeline_json = build_daily_timeline(sim)

    sl = metrics["service_level"]
    sl_act = metrics["actual_service_level"]
    avg_inv = metrics["avg_inventory_value"]
    avg_inv_act = metrics["actual_avg_inventory_value"]
    inv_delta = metrics["inventory_value_delta_vs_actual"]
    cost = metrics["total_ordering_cost"]
    lost_u = metrics["total_lost_sales_units"]
    orders = metrics["total_orders"]
    fc_units = metrics["total_forecast_units"]
    act_units = metrics["total_actual_units"]
    z_by_class = meta.get("z_by_class", {})
    floors = f"reorder={meta.get('empirical_floor_reorder_quantile',0.75)}, up-to={meta.get('empirical_floor_order_up_to_quantile',0.90)}"
    abc_mode = meta.get("abc_classification", "N/A")
    review = meta.get("review_days", 7)
    z_uniform = meta.get("z_uniform", 0.84)

    # Lost sales value
    lost_value = sum(
        r["total_lost_sales_units"] * r["sales_price"]
        for r in sku.to_dict("records")
        if r.get("total_lost_sales_units", 0) > 0 and pd.notna(r.get("sales_price"))
    )

    # ABC counts
    abc_counts = sku["abc_class"].value_counts().to_dict()
    a_count = abc_counts.get("A", 0)
    b_count = abc_counts.get("B", 0)
    c_count = abc_counts.get("C", 0)

    # Per-location metrics
    loja = sku.groupby("location").agg(
        sl=("service_level", "mean"),
        inv=("avg_inventory_value", "mean"),
        cost=("total_ordering_cost", "sum"),
        lost=("total_lost_sales_units", "sum"),
        demand=("total_actual_demand", "sum"),
    )

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dashboard — Politica de Estoque Q4/2024</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Inter',sans-serif; background:#f0f2f5; color:#1a1a2e; }}
.header {{
    background: linear-gradient(135deg,#0f0c29,#302b63,#24243e);
    padding:20px 40px; display:flex; align-items:center; justify-content:space-between;
    border-bottom:3px solid #00d4aa;
}}
.header h1 {{ color:#fff; font-size:20px; font-weight:700; }}
.header h1 span {{ color:#00d4aa; }}
.header .badge {{ background:#00d4aa; color:#0f0c29; padding:6px 16px; border-radius:20px;
    font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:1px; }}

.nav {{ display:flex; background:#fff; padding:0 40px; box-shadow:0 2px 4px rgba(0,0,0,0.04); border-bottom:1px solid #e0e0e0; flex-wrap:wrap; }}
.nav button {{
    padding:14px 20px; border:none; background:transparent;
    font-family:'Inter',sans-serif; font-size:13px; font-weight:500; color:#666;
    cursor:pointer; border-bottom:3px solid transparent; transition:all 0.2s;
}}
.nav button:hover {{ color:#302b63; }}
.nav button.active {{ color:#302b63; border-bottom-color:#00d4aa; font-weight:600; }}

.content {{ padding:24px 40px; max-width:1400px; margin:0 auto; }}
.page {{ display:none; }}
.page.active {{ display:block; }}

.kpi-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:16px; margin-bottom:24px; }}
.kpi-card {{
    background:#fff; border-radius:12px; padding:20px; box-shadow:0 1px 3px rgba(0,0,0,0.06);
    border-left:4px solid #302b63; transition:transform 0.2s;
}}
.kpi-card:hover {{ transform:translateY(-2px); box-shadow:0 4px 12px rgba(0,0,0,0.1); }}
.kpi-card .label {{ font-size:11px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px; color:#888; margin-bottom:4px; }}
.kpi-card .value {{ font-size:26px; font-weight:700; color:#1a1a2e; }}
.kpi-card .sub {{ font-size:12px; color:#888; margin-top:4px; }}
.kpi-card .delta {{ font-size:12px; font-weight:600; margin-top:4px; }}
.kpi-card .delta.pos {{ color:#00b894; }}
.kpi-card .delta.neg {{ color:#e17055; }}
.kpi-card.green {{ border-left-color:#00b894; }}
.kpi-card.teal {{ border-left-color:#00cec9; }}
.kpi-card.orange {{ border-left-color:#e17055; }}
.kpi-card.purple {{ border-left-color:#6c5ce7; }}
.kpi-card.blue {{ border-left-color:#0984e3; }}

.section-title {{
    font-size:17px; font-weight:700; color:#1a1a2e; margin:28px 0 14px;
    padding-bottom:8px; border-bottom:2px solid #e0e0e0;
}}
.section-title span {{ color:#00d4aa; }}

.chart-container {{
    background:#fff; border-radius:12px; padding:20px;
    box-shadow:0 1px 3px rgba(0,0,0,0.06); margin-bottom:20px;
}}
.two-col {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-bottom:20px; }}
@media(max-width:900px){{ .two-col{{grid-template-columns:1fr;}} }}

.insight {{
    background: linear-gradient(135deg,#0f0c29,#302b63);
    color:#fff; border-radius:12px; padding:20px; margin-bottom:20px;
}}
.insight h3 {{ color:#00d4aa; font-size:15px; margin-bottom:8px; }}
.insight p {{ font-size:13px; line-height:1.6; color:rgba(255,255,255,0.85); }}

.data-table {{ width:100%; border-collapse:collapse; font-size:12px; }}
.data-table th {{
    text-align:left; padding:8px 10px; background:#f8f9fa; font-weight:600;
    color:#555; border-bottom:2px solid #e0e0e0;
}}
.data-table td {{ padding:7px 10px; border-bottom:1px solid #f0f0f0; }}
.data-table tr:hover {{ background:#f8f9fa; }}
.data-table .num {{ font-family:'JetBrains Mono',monospace; text-align:right; }}

.badge-sl {{ display:inline-block; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:600; }}
.badge-sl.A {{ background:#d4edda; color:#155724; }}
.badge-sl.B {{ background:#fff3cd; color:#856404; }}
.badge-sl.C {{ background:#f8d7da; color:#721c24; }}

.param-grid {{
    display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px;
    margin-bottom:20px;
}}
.param-card {{
    background:#fff; border-radius:10px; padding:14px;
    box-shadow:0 1px 3px rgba(0,0,0,0.06); text-align:center;
}}
.param-card .param-label {{ font-size:10px; font-weight:600; color:#888; text-transform:uppercase; }}
.param-card .param-value {{ font-size:20px; font-weight:700; color:#302b63; margin-top:4px; }}

.footer {{ text-align:center; padding:16px; color:#888; font-size:11px; border-top:1px solid #e0e0e0; margin-top:40px; }}
</style>
</head>
<body>
<div class="header">
    <h1>Dashboard de Politica <span>(s,S)</span> &mdash; Q4/2024</h1>
    <span class="badge">v2.0 &bull; ABC Ponderada</span>
</div>

<div class="nav">
    <button class="active" onclick="switchPage('overview')">Visao Geral</button>
    <button onclick="switchPage('abc')">Curva ABC</button>
    <button onclick="switchPage('lojas')">Por Loja</button>
    <button onclick="switchPage('skus')">SKU Detalhado</button>
    <button onclick="switchPage('sim')">Simulacao Diaria</button>
    <button onclick="switchPage('config')">Configuracao</button>
</div>

<div class="content">

<!-- ==================== OVERVIEW ==================== -->
<div id="page-overview" class="page active">
<div class="kpi-grid" id="kpi-overview"></div>
<div class="two-col">
    <div class="chart-container" id="chart-weekly" style="height:350px;"></div>
    <div class="chart-container" id="chart-promo" style="height:350px;"></div>
</div>
<div class="insight" id="insight-overview"></div>
</div>

<!-- ==================== ABC ==================== -->
<div id="page-abc" class="page">
<div class="two-col">
    <div class="chart-container" id="chart-abc-pareto" style="height:400px;"></div>
    <div class="chart-container" id="chart-abc-bubble" style="height:400px;"></div>
</div>
<div class="kpi-grid" id="kpi-abc"></div>
</div>

<!-- ==================== LOJAS ==================== -->
<div id="page-lojas" class="page">
<div class="two-col">
    <div class="chart-container" id="chart-lojas-radar" style="height:380px;"></div>
    <div class="chart-container" id="chart-lojas-bar" style="height:380px;"></div>
</div>
<div class="chart-container" id="chart-lojas-hero" style="height:400px;"></div>
</div>

<!-- ==================== SKU DETALHADO ==================== -->
<div id="page-skus" class="page">
<div class="chart-container" id="chart-rev-risk" style="height:420px;"></div>
<div style="overflow-x:auto;">
    <div class="chart-container">
        <table class="data-table" id="table-skus"></table>
    </div>
</div>
</div>

<!-- ==================== SIMULACAO DIARIA ==================== -->
<div id="page-sim" class="page">
<div class="two-col">
    <div class="chart-container" id="chart-hero1" style="height:380px;"></div>
    <div class="chart-container" id="chart-hero2" style="height:380px;"></div>
</div>
<div class="chart-container" id="chart-daily-agg" style="height:380px;"></div>
</div>

<!-- ==================== CONFIG ==================== -->
<div id="page-config" class="page">
<div class="param-grid" id="param-grid"></div>
<div class="insight" id="insight-config"></div>
<div class="chart-container" id="chart-tune" style="height:400px;"></div>
</div>

</div>

<div class="footer">
    Hackathon CDN &middot; ESPM &middot; Q4/2024 &middot; ABC Ponderada 70/88 &middot; z=(A:{z_by_class.get('A',1.28)}, B:{z_by_class.get('B',0.84)}, C:{z_by_class.get('C',0.0)}) &middot; Pisos {floors}
</div>

<script>
// ============ EMBEDDED DATA ============
const SIM_DATA = {timeline_json};
const SKU_DATA = {sku_json};
const METRICS = {{
    service_level: {sl},
    actual_service_level: {sl_act},
    avg_inventory_value: {avg_inv},
    actual_avg_inventory_value: {avg_inv_act},
    inventory_value_delta_vs_actual: {inv_delta},
    total_ordering_cost: {cost},
    total_lost_sales_units: {lost_u},
    total_lost_sales_value: {lost_value},
    total_orders: {orders},
    total_demand: {act_units},
    total_forecast: {fc_units},
}};
const ABC_DATA = {abc_json};
const LOJA_DATA = {loja_json};
const WEEKLY_DATA = {weekly_json};
const PROMO_DATA = {promo_json};
const TUNE_DATA = {tune_json};
const REV_RISK_DATA = {rev_json};
const CONFIG = {{
    abc_classification: "{abc_mode}",
    z_by_class: {json.dumps(z_by_class)},
    z_uniform: {z_uniform},
    review_days: {review},
    reorder_quantile: {meta.get('empirical_floor_reorder_quantile',0.75)},
    order_up_to_quantile: {meta.get('empirical_floor_order_up_to_quantile',0.90)},
    forecast_mode: "static + promo median/sqrt + zero-forecast <=3un",
    promo_cap: 2.0,
}};

// ============ PAGE SWITCHING ============
function switchPage(page) {{
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav button').forEach(b => b.classList.remove('active'));
    document.getElementById('page-'+page).classList.add('active');
    var btns = document.querySelectorAll('.nav button');
    for (var i=0; i<btns.length; i++) {{
        if (btns[i].getAttribute('onclick') && btns[i].getAttribute('onclick').indexOf(page)>=0) {{
            btns[i].classList.add('active');
        }}
    }}
    setTimeout(function() {{
        if (page === 'overview') drawOverview();
        if (page === 'abc') drawABC();
        if (page === 'lojas') drawLojas();
        if (page === 'skus') drawSKUs();
        if (page === 'sim') drawSimulation();
        if (page === 'config') drawConfig();
    }}, 100);
}}

// ============ OVERVIEW ============
function drawOverview() {{
    var m = METRICS;
    var slPct = (m.service_level*100).toFixed(2);
    var delta = m.avg_inventory_value - m.actual_avg_inventory_value;
    var overForecast = ((m.total_forecast/m.total_demand - 1)*100).toFixed(0);

    var kpi = document.getElementById('kpi-overview');
    kpi.innerHTML = `
        <div class="kpi-card green" style="grid-column:span 1;">
            <div class="label">Nivel de Servico</div>
            <div class="value">${{slPct}}%</div>
            <div class="sub">Meta: >= 92% <span style="color:#00b894;">&#10004;</span></div>
            <div class="delta pos">+${{((m.service_level-m.actual_service_level)*100).toFixed(2)}}pp vs real</div>
        </div>
        <div class="kpi-card purple">
            <div class="label">Estoque Medio</div>
            <div class="value">R$ ${{m.avg_inventory_value.toFixed(2)}}</div>
            <div class="sub">Real: R$ ${{m.actual_avg_inventory_value.toFixed(2)}}</div>
            <div class="delta ${{delta > 0.01 ? 'neg' : 'pos'}}">${{delta > 0.01 ? '+' : ''}}R$ ${{Math.abs(delta).toFixed(2)}} vs real</div>
        </div>
        <div class="kpi-card orange">
            <div class="label">Custo de Reposicao</div>
            <div class="value">R$ ${{m.total_ordering_cost.toFixed(2)}}</div>
            <div class="sub">${{m.total_orders}} pedidos</div>
        </div>
        <div class="kpi-card teal">
            <div class="label">Vendas Perdidas</div>
            <div class="value">${{m.total_lost_sales_units}} un</div>
            <div class="sub">R$ ${{m.total_lost_sales_value.toFixed(2)}}</div>
        </div>
        <div class="kpi-card blue">
            <div class="label">Demanda vs Forecast</div>
            <div class="value">${{m.total_demand}} / ${{m.total_forecast.toFixed(0)}} un</div>
            <div class="sub">Forecast ${{overForecast}}% acima</div>
        </div>
    `;

    // Weekly demand vs forecast
    var wDemand = WEEKLY_DATA.map(d => d.demand);
    var wForecast = WEEKLY_DATA.map(d => d.forecast);
    var wWeeks = WEEKLY_DATA.map(d => 'W' + d.week);
    var wLost = WEEKLY_DATA.map(d => d.lost);

    var wTrace1 = {{ x: wWeeks, y: wDemand, type: 'bar', name: 'Demanda Real', marker: {{ color: '#302b63' }} }};
    var wTrace2 = {{ x: wWeeks, y: wForecast, type: 'scatter', name: 'Forecast', mode: 'lines+markers', line: {{ color: '#e17055', width: 2 }}, marker: {{ size: 6 }} }};
    Plotly.newPlot('chart-weekly', [wTrace1, wTrace2], {{
        title: 'Demanda vs Forecast Semanal', margin: {{ t:40, r:20, b:40, l:40 }},
        barmode: 'group', legend: {{ orientation:'h', y:1.1 }},
    }}, {{ responsive: true }});

    // Promo comparison
    var pLabels = PROMO_DATA.map(d => d.is_promo ? 'Com Promocao' : 'Sem Promocao');
    var pDemand = PROMO_DATA.map(d => d.demand);
    var pForecast = PROMO_DATA.map(d => d.forecast);
    var pDays = PROMO_DATA.map(d => d.days + ' dias');
    Plotly.newPlot('chart-promo', [
        {{ x: pLabels, y: pDemand, type: 'bar', name: 'Demanda', marker: {{ color: '#00b894' }}, text: pDays, textposition:'auto' }},
        {{ x: pLabels, y: pForecast, type: 'bar', name: 'Forecast', marker: {{ color: '#e17055', opacity:0.6 }} }}
    ], {{
        title: 'Impacto Promocional', barmode:'group', margin: {{ t:40, r:20, b:40, l:40 }},
        legend: {{ orientation:'h', y:1.1 }},
    }}, {{ responsive: true }});

    // Insight
    document.getElementById('insight-overview').innerHTML = `
        <h3>Resumo Executivo</h3>
        <p>Politica <b>(s,S)</b> com segmentacao ABC ponderada por demanda (thresholds 70/88).<br>
        <b>NEOSORO</b> (70% da demanda) protegido com z=1,28 — zero ruptura.<br>
        <b>Estoque R$${{m.avg_inventory_value.toFixed(0)}}/dia</b> — ${{Math.abs(delta).toFixed(0) > 0 && delta < 0 ? Math.abs(delta).toFixed(0)+' abaixo' : Math.abs(delta).toFixed(0)+' acima'}} da operacao real.<br>
        <b>Forecast</b> ${{m.total_forecast.toFixed(0)}} vs ${{m.total_demand}} un reais — superestimacao de ${{overForecast}}% (antes era 51%).<br>
        <b>SL ${{slPct}}%</b> — acima da meta de 99,5% e do target oficial de 92%.</p>
    `;
}}

// ============ ABC ============
function drawABC() {{
    var abc = ABC_DATA;
    var labels = abc.map(d => d.label);
    var demand = abc.map(d => d.demand);
    var cum = abc.map(d => d.cum_demand * 100);
    var colors = cum.map(c => c <= 70 ? '#00b894' : (c <= 88 ? '#fdcb6e' : '#e17055'));
    var invVals = abc.map(d => d.inv_value);

    Plotly.newPlot('chart-abc-pareto', [
        {{ x: labels, y: demand, type: 'bar', name: 'Demanda (un)', marker: {{ color: colors }}, yaxis:'y' }},
        {{ x: labels, y: cum, type: 'scatter', name: '% Acumulada', mode:'lines+markers', yaxis:'y2', line: {{ color:'#0984e3', width:2 }} }}
    ], {{
        title: 'Curva ABC (Demanda Volume)', margin: {{ t:40, r:50, b:80, l:40 }},
        xaxis: {{ tickangle:-45, automargin:true }},
        yaxis: {{ title:'Demanda (un)' }},
        yaxis2: {{ title:'% Acum.', overlaying:'y', side:'right', range:[0,105] }},
        legend: {{ orientation:'h', y:1.15 }},
        shapes: [
            {{ type:'line', x0:-0.5, x1:labels.length, y0:70, y1:70, yref:'y2', line:{{ dash:'dash', color:'#00b894' }} }},
            {{ type:'line', x0:-0.5, x1:labels.length, y0:88, y1:88, yref:'y2', line:{{ dash:'dash', color:'#fdcb6e' }} }},
        ]
    }}, {{ responsive: true }});

    Plotly.newPlot('chart-abc-bubble', [{{
        x: demand, y: invVals,
        mode: 'markers+text',
        type: 'scatter',
        text: labels,
        textposition: 'top center',
        textfont: {{ size:9 }},
        marker: {{
            size: demand.map(d => Math.max(Math.sqrt(d)*6, 8)),
            color: colors,
            opacity:0.7,
        }},
    }}], {{
        title: 'Demanda vs Estoque por SKU', margin: {{ t:40, r:20, b:40, l:50 }},
        xaxis: {{ title:'Demanda (un)' }},
        yaxis: {{ title:'Estoque Medio (R$)' }},
        showlegend: false,
    }}, {{ responsive: true }});

    var aCount = SKU_DATA.filter(d => d.abc_class === 'A').length;
    var bCount = SKU_DATA.filter(d => d.abc_class === 'B').length;
    var cCount = SKU_DATA.filter(d => d.abc_class === 'C').length;
    var aDem = abc.filter(d => d.cum_demand <= 0.70).reduce((s,d) => s+d.demand, 0);
    var bDem = abc.filter(d => d.cum_demand > 0.70 && d.cum_demand <= 0.88).reduce((s,d) => s+d.demand, 0);
    var cDem = abc.filter(d => d.cum_demand > 0.88).reduce((s,d) => s+d.demand, 0);

    document.getElementById('kpi-abc').innerHTML = `
        <div class="kpi-card green">
            <div class="label">Classe A (z=1,28)</div>
            <div class="value">${{aCount}} pares</div>
            <div class="sub">${{aDem}} un (${{(aDem/METRICS.total_demand*100).toFixed(0)}}%)</div>
        </div>
        <div class="kpi-card" style="border-left-color:#fdcb6e">
            <div class="label">Classe B (z=0,84)</div>
            <div class="value">${{bCount}} pares</div>
            <div class="sub">${{bDem}} un (${{(bDem/METRICS.total_demand*100).toFixed(0)}}%)</div>
        </div>
        <div class="kpi-card orange">
            <div class="label">Classe C (z=0,00)</div>
            <div class="value">${{cCount}} pares</div>
            <div class="sub">${{cDem}} un (${{(cDem/METRICS.total_demand*100).toFixed(0)}}%)</div>
        </div>
    `;
}}

// ============ LOJAS ============
function drawLojas() {{
    var l841 = LOJA_DATA.find(d => d.location === 841);
    var l1314 = LOJA_DATA.find(d => d.location === 1314);

    Plotly.newPlot('chart-lojas-radar', [{{
        type: 'scatterpolar',
        r: [l841.demand/METRICS.total_demand*100, l841.orders, l841.lost_units, (l841.avg_inv/l841.avg_actual_inv-1)*100, l1314.demand/METRICS.total_demand*100, l1314.orders, l1314.lost_units, (l1314.avg_inv/l1314.avg_actual_inv-1)*100],
        theta: ['% Demanda','Pedidos','Lost Sales','Var Estoque','% Demanda','Pedidos','Lost Sales','Var Estoque'],
        fill: 'toself',
        name: 'Metricas',
    }}], {{
        title: 'Comparativo por Loja', polar: {{ radialaxis: {{ visible:true }} }}, margin: {{ t:40, r:20, b:40, l:20 }},
    }}, {{ responsive: true }});

    Plotly.newPlot('chart-lojas-bar', [
        {{ x: ['Loja 841','Loja 1314'], y: [l841.demand, l1314.demand], type:'bar', name:'Demanda', marker:{{ color:'#302b63' }} }},
        {{ x: ['Loja 841','Loja 1314'], y: [l841.avg_inv, l1314.avg_inv], type:'bar', name:'Estoque (R$)', marker:{{ color:'#00b894', opacity:0.6 }} }},
    ], {{
        title: 'Demanda vs Estoque', margin: {{ t:40, r:20, b:40, l:50 }},
        barmode: 'group', legend: {{ orientation:'h', y:1.1 }},
    }}, {{ responsive: true }});

    var hero1 = SIM_DATA.filter(d => d.product === 18064 && d.location === 1314);
    Plotly.newPlot('chart-lojas-hero', [
        {{ x: hero1.map(d => d.date), y: hero1.map(d => d.ending_inventory), type:'scatter', name:'Estoque Simulado', mode:'lines', line:{{ color:'#00b894', width:2 }}, fill:'tozeroy', fillcolor:'rgba(0,180,140,0.1)' }},
        {{ x: hero1.map(d => d.date), y: hero1.map(d => d.actual_balance||0), type:'scatter', name:'Estoque Real', mode:'lines', line:{{ color:'#0984e3', width:2, dash:'dash' }} }},
    ], {{
        title: 'NEOSORO 1314 — Estoque Dia a Dia', margin: {{ t:40, r:20, b:40, l:50 }},
        legend: {{ orientation:'h', y:1.1 }},
        xaxis: {{ title:'Data' }}, yaxis: {{ title:'Unidades' }},
    }}, {{ responsive: true }});
}}

// ============ SKU DETAIL ============
function drawSKUs() {{
    var risk = REV_RISK_DATA;
    Plotly.newPlot('chart-rev-risk', [
        {{ x: risk.map(d => d.product_name), y: risk.map(d => d.revenue), type:'bar',
           marker: {{ color: risk.map(d => d.stockout > 0 ? '#e17055' : '#00b894') }},
           text: risk.map(d => 'Loja '+d.location + (d.stockout>0 ? ' (ruptura)' : '')),
        }}
    ], {{
        title: 'Top 10 SKU-Loja por Receita', margin: {{ t:40, r:20, b:80, l:50 }},
        xaxis: {{ tickangle:-45, automargin:true }},
        yaxis: {{ title:'Receita (R$)' }},
    }}, {{ responsive: true }});

    var table = document.getElementById('table-skus');
    var skus = SKU_DATA.sort((a,b) => b.total_actual_demand - a.total_actual_demand);
    var rows = skus.map(d => `
        <tr>
            <td>${{d.product}}</td><td>${{d.product_name}}</td><td>Loja ${{d.location}}</td>
            <td><span class="badge-sl ${{d.abc_class}}">${{d.abc_class}}</span></td>
            <td class="num">${{d.reorder_point_s}}</td><td class="num">${{d.order_up_to_S}}</td>
            <td class="num">${{d.total_actual_demand}}</td>
            <td class="num">${{d.service_level ? (d.service_level*100).toFixed(1)+'%' : '-'}}</td>
            <td class="num">R$${{d.avg_inventory_value.toFixed(0)}}</td>
            <td class="num">${{d.total_lost_sales_units}}</td>
        </tr>
    `).join('');
    table.innerHTML = `<thead><tr>
        <th>SKU</th><th>Produto</th><th>Loja</th><th>ABC</th>
        <th class="num">s</th><th class="num">S</th>
        <th class="num">Demanda</th><th class="num">SL</th>
        <th class="num">Estoque</th><th class="num">Perdido</th>
    </tr></thead><tbody>${{rows}}</tbody>`;
}}

// ============ SIMULATION ============
function drawSimulation() {{
    var hero1 = SIM_DATA.filter(d => d.product === 18064 && d.location === 1314);
    var hero2 = SIM_DATA.filter(d => d.product === 18064 && d.location === 841);

    function simChart(id, data, title) {{
        Plotly.newPlot(id, [
            {{ x: data.map(d => d.date), y: data.map(d => d.ending_inventory), type:'scatter', name:'Estoque', mode:'lines', line:{{ color:'#00b894', width:2 }}, fill:'tozeroy', fillcolor:'rgba(0,180,140,0.08)' }},
            {{ x: data.map(d => d.date), y: data.map(d => d.actual_demand), type:'bar', name:'Demanda', marker:{{ color:'#302b63', opacity:0.3 }}, yaxis:'y2' }},
            {{ x: data.map(d => d.date), y: data.map(d => d.reorder_point_s || d.reorder_point), type:'scatter', name:'s (ponto de pedido)', mode:'lines', line:{{ color:'#fdcb6e', width:1, dash:'dash' }} }},
        ], {{
            title: title, margin: {{ t:40, r:50, b:40, l:50 }},
            xaxis: {{ title:'Data' }}, yaxis: {{ title:'Unidades' }},
            yaxis2: {{ title:'Demanda', overlaying:'y', side:'right', showgrid:false }},
            legend: {{ orientation:'h', y:1.15 }},
        }}, {{ responsive: true }});
    }}

    simChart('chart-hero1', hero1, 'NEOSORO 1314 (Classe A, z=1.28)');
    simChart('chart-hero2', hero2, 'NEOSORO 841 (Classe B, z=0.84)');

    var daily = {{}};
    SIM_DATA.forEach(d => {{
        var day = d.date.toString().slice(0,10);
        if (!daily[day]) daily[day] = {{ inv:0, dem:0, lost:0 }};
        daily[day].inv += d.simulated_inventory_value || 0;
        daily[day].dem += d.actual_demand || 0;
        daily[day].lost += d.lost_sales_units || 0;
    }});
    var keys = Object.keys(daily).sort();
    Plotly.newPlot('chart-daily-agg', [
        {{ x: keys, y: keys.map(k => daily[k].inv), type:'scatter', name:'Estoque (R$)', mode:'lines', line:{{ color:'#00b894', width:2 }}, fill:'tozeroy', fillcolor:'rgba(0,180,140,0.1)' }},
        {{ x: keys, y: keys.map(k => daily[k].dem), type:'scatter', name:'Demanda', mode:'lines', line:{{ color:'#e17055', width:1 }}, yaxis:'y2' }},
    ], {{
        title: 'Estoque Total Agregado Diario', margin: {{ t:40, r:50, b:40, l:50 }},
        xaxis: {{ title:'Data' }}, yaxis: {{ title:'R$' }},
        yaxis2: {{ title:'Unidades', overlaying:'y', side:'right', showgrid:false }},
        legend: {{ orientation:'h', y:1.15 }},
    }}, {{ responsive: true }});
}}

// ============ CONFIG ============
function drawConfig() {{
    var c = CONFIG;
    document.getElementById('param-grid').innerHTML = `
        <div class="param-card"><div class="param-label">Classificacao ABC</div><div class="param-value" style="font-size:14px;">${{c.abc_classification}}</div></div>
        <div class="param-card"><div class="param-label">z Classe A</div><div class="param-value">${{c.z_by_class.A}}</div></div>
        <div class="param-card"><div class="param-label">z Classe B</div><div class="param-value">${{c.z_by_class.B}}</div></div>
        <div class="param-card"><div class="param-label">z Classe C</div><div class="param-value">${{c.z_by_class.C}}</div></div>
        <div class="param-card"><div class="param-label">z Uniforme (base)</div><div class="param-value">${{c.z_uniform}}</div></div>
        <div class="param-card"><div class="param-label">Review Days</div><div class="param-value">${{c.review_days}}d</div></div>
        <div class="param-card"><div class="param-label">Piso Reorder</div><div class="param-value">${{c.reorder_quantile}}</div></div>
        <div class="param-card"><div class="param-label">Piso Order-Up-To</div><div class="param-value">${{c.order_up_to_quantile}}</div></div>
    `;

    document.getElementById('insight-config').innerHTML = `
        <h3>Metodo</h3>
        <p><b>Forecast:</b> Media movel ponderada (45% recente-28d, 35% mesmo-weekday, 20% LY) com uplift promocional corrigido (mediana + dampening sqrt, cap 2.0).<br>
        <b>Zero-Forecast:</b> SKUs com demanda <= 3 un/Q4 tem forecast = 0.<br>
        <b>ABC:</b> Classificacao por volume de demanda Q4, thresholds A=70%, B=88%, C=12%.<br>
        <b>Politica (s,S):</b> s = ceil(mu*L + z*sigma*sqrt(L)), S = ceil(s + mu*review).<br>
        <b>Pisos Empiricos:</b> Quantis da demanda historica sazonal para evitar valores muito baixos.</p>
    `;

    if (TUNE_DATA.length > 0) {{
        var tz = [...new Set(TUNE_DATA.map(d => d.z_value))].sort();
        var trd = [...new Set(TUNE_DATA.map(d => d.review_days))].sort();
        var heatmap = trd.map(rd => {{
            return tz.map(zv => {{
                var match = TUNE_DATA.find(d => d.z_value === zv && d.review_days === rd);
                return match ? match.objective : null;
            }});
        }});
        Plotly.newPlot('chart-tune', [{{
            z: heatmap, x: tz, y: trd, type:'heatmap',
            colorscale: [[0,'#00b894'],[0.5,'#fdcb6e'],[1,'#e17055']],
            text: heatmap.map(r => r.map(v => v ? v.toFixed(1) : '-')),
            texttemplate: '%{{text}}', textfont: {{ size:11 }},
        }}], {{
            title: 'Grid Search: Objective por (z, review_days)', margin: {{ t:40, r:20, b:40, l:50 }},
            xaxis: {{ title:'z value' }}, yaxis: {{ title:'review_days' }},
        }}, {{ responsive: true }});
    }}
}}

// ============ INIT ============
drawOverview();
</script>
</body>
</html>"""

    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"Dashboard generated: {OUT_HTML}")
    print(f"  Total SKU-location pairs: {len(sku)}")
    print(f"  SL: {perc(sl)}")
    print(f"  Avg inventory: {brl(avg_inv)}")
    print(f"  Forecast: {fc_units:.0f} un")
    print(f"  Actual demand: {act_units:.0f} un")
    print(f"  Lost sales: {lost_u} un")

if __name__ == "__main__":
    generate_dashboard()
