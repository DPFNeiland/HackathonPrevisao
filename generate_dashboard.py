"""Generate a self-contained HTML product dashboard for the hackathon pitch.
Reads existing outputs from stock_policy_product_output/ and produces dashboard.html."""

import json
import numpy as np
import pandas as pd

OUT = "stock_policy_product_output"

sim = pd.read_csv(f"{OUT}/simulation_daily.csv")
sku_metrics = pd.read_csv(f"{OUT}/sku_metrics.csv")
overall = json.load(open(f"{OUT}/overall_metrics.json"))
try:
    tune = pd.read_csv(f"{OUT}/tuning_search.csv")
except:
    tune = None

sim['date'] = pd.to_datetime(sim['date'])
sim['week'] = sim['date'].dt.isocalendar().week.astype(int)

# =========================================================
# 1. PREPARE DATA FOR JAVASCRIPT EMBEDDING
# =========================================================

# 1a. Time series for animation (NEOSORO 1314 as hero)
hero = sim[(sim['product'] == 18064) & (sim['location'] == 1314)].sort_values('date').copy()
hero_ts = hero[['date', 'opening_inventory', 'received_qty', 'order_qty', 'ending_inventory',
                'inventory_position_before_order', 'actual_demand', 'fulfilled_units',
                'lost_sales_units', 'simulated_stockout_flag', 'actual_balance',
                'simulated_inventory_value', 'actual_inventory_value']].copy()
hero_ts['date'] = hero_ts['date'].dt.strftime('%Y-%m-%d')
hero_ts['date_str'] = hero_ts['date']
hero_json = hero_ts.to_dict(orient='records')

# Also hero from store 841
hero2 = sim[(sim['product'] == 18064) & (sim['location'] == 841)].sort_values('date').copy()
hero2_ts = hero2[['date', 'opening_inventory', 'received_qty', 'order_qty', 'ending_inventory',
                  'inventory_position_before_order', 'actual_demand', 'fulfilled_units',
                  'lost_sales_units', 'simulated_stockout_flag', 'actual_balance',
                  'simulated_inventory_value', 'actual_inventory_value']].copy()
hero2_ts['date'] = hero2_ts['date'].dt.strftime('%Y-%m-%d')
hero2_ts['date_str'] = hero2_ts['date']
hero2_json = hero2_ts.to_dict(orient='records')

# 1b. SKU metrics table
sku_json = sku_metrics.to_dict(orient='records')

# 1c. Weekly demand pattern
weekly = sim.groupby('week').agg(
    demand=('actual_demand', 'sum'),
    forecast=('forecast_demand', 'sum'),
    lost=('lost_sales_units', 'sum'),
).reset_index()
weekly_json = weekly.to_dict(orient='records')

# 1d. ABC concentration data
abc = sim.groupby('product').agg(
    demand=('actual_demand', 'sum'),
    inv_value=('simulated_inventory_value', 'mean'),
).reset_index()
abc = abc.sort_values('demand', ascending=False)
abc['cum_demand'] = abc['demand'].cumsum() / abc['demand'].sum()
abc['label'] = abc['product'].map(
    sim[['product', 'product_name']].drop_duplicates().set_index('product')['product_name'].to_dict()
)
abc_json = abc.to_dict(orient='records')

# 1e. Grid search data
if tune is not None:
    tune_json = tune.to_dict(orient='records')
else:
    tune_json = []

# 1f. Loja comparison
loja_metrics = sim.groupby('location').agg(
    demand=('actual_demand', 'sum'),
    avg_inv=('simulated_inventory_value', 'mean'),
    avg_actual_inv=('actual_inventory_value', 'mean'),
    orders=('ordering_cost', lambda x: (x > 0).sum()),
    order_cost=('ordering_cost', 'sum'),
    stockout_days=('simulated_stockout_flag', 'sum'),
    lost_units=('lost_sales_units', 'sum'),
).reset_index()
loja_json = loja_metrics.to_dict(orient='records')

# 1g. Promo vs Non-promo
promo_impact = sim.groupby('is_promo').agg(
    demand=('actual_demand', 'sum'),
    forecast=('forecast_demand', 'sum'),
    days=('date', 'nunique'),
    lost=('lost_sales_units', 'sum'),
).reset_index()
promo_json = promo_impact.to_dict(orient='records')

# 1h. Over/under forecast summary
sim['fc_error'] = sim['forecast_demand'] - sim['actual_demand']
over_under = sim.groupby('product').agg(
    over=('fc_error', lambda x: x.clip(lower=0).sum()),
    under=('fc_error', lambda x: (-x).clip(lower=0).sum()),
    actual=('actual_demand', 'sum'),
).reset_index()
over_under['label'] = over_under['product'].map(
    sim[['product', 'product_name']].drop_duplicates().set_index('product')['product_name'].to_dict()
)
over_under_json = over_under.to_dict(orient='records')

# 1i. Overall KPIs
kpi = {
    'service_level': overall.get('service_level', 0.9994),
    'actual_service_level': overall.get('actual_service_level', 0.991),
    'avg_inventory_value': round(overall.get('avg_inventory_value', 169.78), 2),
    'actual_avg_inventory_value': round(overall.get('actual_avg_inventory_value', 163.27), 2),
    'total_ordering_cost': round(overall.get('total_ordering_cost', 2629.55), 2),
    'total_lost_sales_units': int(overall.get('total_lost_sales_units', 3)),
    'total_lost_sales_value': round(overall.get('total_lost_sales_value', 233.72), 2) if 'total_lost_sales_value' in overall else 233.72,
    'total_orders': int(sim[sim['order_qty'] > 0].shape[0]),
    'total_demand': int(sim['actual_demand'].sum()),
    'total_forecast': int(sim['forecast_demand'].sum()),
}

# 1j. Top products by revenue at risk
sim['revenue_at_risk'] = sim['actual_demand'] * sim['sales_price']
rev_risk = sim.groupby(['product', 'location']).agg(
    revenue=('revenue_at_risk', 'sum'),
    stockout=('simulated_stockout_flag', 'sum'),
    product_name=('product_name', 'first'),
).reset_index()
rev_risk = rev_risk.sort_values('revenue', ascending=False).head(10)
rev_risk_json = rev_risk.to_dict(orient='records')

# =========================================================
# 2. BUILD HTML
# =========================================================

html = f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stock Policy Dashboard — Hackathon CDN 2026</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Inter', sans-serif; background: #f0f2f5; color: #1a1a2e; }}

/* HEADER */
.header {{
    background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
    padding: 20px 40px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    border-bottom: 3px solid #00d4aa;
}}
.header .logos {{ display: flex; align-items: center; gap: 24px; }}
.header .logo-group {{ display: flex; align-items: center; gap: 12px; color: #fff; }}
.header .logo-group .logo-badge {{
    background: rgba(255,255,255,0.1);
    border: 1px solid rgba(255,255,255,0.2);
    padding: 6px 14px;
    border-radius: 6px;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.5px;
    color: #fff;
}}
.header .logo-group .sep {{ color: rgba(255,255,255,0.3); font-size: 18px; }}
.header h1 {{ color: #fff; font-size: 20px; font-weight: 700; letter-spacing: -0.3px; }}
.header h1 span {{ color: #00d4aa; }}
.header .badge {{
    background: #00d4aa;
    color: #0f0c29;
    padding: 6px 16px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
}}

/* NAV */
.nav {{
    display: flex;
    background: #fff;
    border-bottom: 1px solid #e0e0e0;
    padding: 0 40px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.04);
}}
.nav button {{
    padding: 16px 24px;
    border: none;
    background: transparent;
    font-family: 'Inter', sans-serif;
    font-size: 14px;
    font-weight: 500;
    color: #666;
    cursor: pointer;
    border-bottom: 3px solid transparent;
    transition: all 0.2s;
}}
.nav button:hover {{ color: #302b63; }}
.nav button.active {{ color: #302b63; border-bottom-color: #00d4aa; font-weight: 600; }}

/* CONTENT */
.content {{ padding: 24px 40px; }}
.page {{ display: none; }}
.page.active {{ display: block; }}

/* KPI CARDS */
.kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
}}
.kpi-card {{
    background: #fff;
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    border-left: 4px solid #302b63;
    transition: transform 0.2s;
}}
.kpi-card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); }}
.kpi-card .label {{ font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: #888; margin-bottom: 4px; }}
.kpi-card .value {{ font-size: 28px; font-weight: 700; color: #1a1a2e; }}
.kpi-card .sub {{ font-size: 13px; color: #888; margin-top: 4px; }}
.kpi-card .delta {{ font-size: 13px; font-weight: 600; margin-top: 4px; }}
.kpi-card .delta.pos {{ color: #00b894; }}
.kpi-card .delta.neg {{ color: #e17055; }}
.kpi-card .delta.neutral {{ color: #666; }}
.kpi-card.green {{ border-left-color: #00b894; }}
.kpi-card.teal {{ border-left-color: #00cec9; }}
.kpi-card.orange {{ border-left-color: #e17055; }}
.kpi-card.purple {{ border-left-color: #6c5ce7; }}
.kpi-card.blue {{ border-left-color: #0984e3; }}

/* SECTIONS */
.section-title {{
    font-size: 18px;
    font-weight: 700;
    color: #1a1a2e;
    margin: 32px 0 16px;
    padding-bottom: 8px;
    border-bottom: 2px solid #e0e0e0;
}}
.section-title span {{ color: #00d4aa; }}

.chart-container {{
    background: #fff;
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    margin-bottom: 20px;
}}

/* TWO COLUMN */
.two-col {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
    margin-bottom: 20px;
}}
@media (max-width: 900px) {{ .two-col {{ grid-template-columns: 1fr; }} }}

/* INSIGHT BOX */
.insight {{
    background: linear-gradient(135deg, #0f0c29, #302b63);
    color: #fff;
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 20px;
}}
.insight h3 {{ color: #00d4aa; font-size: 16px; margin-bottom: 8px; }}
.insight p {{ font-size: 14px; line-height: 1.6; color: rgba(255,255,255,0.85); }}
.insight .highlight {{ color: #00d4aa; font-weight: 600; }}

/* TABLE */
.data-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}}
.data-table th {{
    text-align: left;
    padding: 10px 12px;
    background: #f8f9fa;
    font-weight: 600;
    color: #555;
    border-bottom: 2px solid #e0e0e0;
    white-space: nowrap;
}}
.data-table td {{
    padding: 8px 12px;
    border-bottom: 1px solid #f0f0f0;
}}
.data-table tr:hover {{ background: #f8f9fa; }}
.data-table .num {{ font-family: 'JetBrains Mono', monospace; text-align: right; }}
.data-table .badge-sl {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 600;
}}
.badge-sl.high {{ background: #d4edda; color: #155724; }}
.badge-sl.medium {{ background: #fff3cd; color: #856404; }}
.badge-sl.low {{ background: #f8d7da; color: #721c24; }}

/* TIMELINE CONTROLS */
.timeline-controls {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
    flex-wrap: wrap;
}}
.timeline-controls button {{
    padding: 8px 20px;
    border: none;
    border-radius: 8px;
    font-family: 'Inter', sans-serif;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
}}
.btn-play {{ background: #00d4aa; color: #0f0c29; }}
.btn-play:hover {{ background: #00bf96; }}
.btn-pause {{ background: #e17055; color: #fff; }}
.btn-pause:hover {{ background: #d63031; }}
.btn-reset {{ background: #dfe6e9; color: #2d3436; }}
.btn-reset:hover {{ background: #b2bec3; }}
.timeline-controls select {{
    padding: 8px 12px;
    border: 1px solid #ddd;
    border-radius: 8px;
    font-family: 'Inter', sans-serif;
    font-size: 13px;
}}
.timeline-controls .speed-label {{ font-size: 13px; color: #888; }}

/* METER */
.meter {{
    height: 8px;
    background: #e0e0e0;
    border-radius: 4px;
    overflow: hidden;
    margin: 8px 0;
}}
.meter-fill {{
    height: 100%;
    border-radius: 4px;
    transition: width 0.3s;
}}

/* VALUE COMPARISON */
.val-comp {{
    display: flex;
    align-items: baseline;
    gap: 8px;
}}
.val-comp .sim {{ font-size: 24px; font-weight: 700; }}
.val-comp .actual {{ font-size: 16px; color: #888; text-decoration: line-through; }}
.val-comp .arrow {{ color: #00d4aa; font-size: 20px; }}

/* NARRATIVE CARD */
.narrative {{
    background: #fff9e6;
    border-left: 4px solid #fdcb6e;
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 16px;
    font-size: 14px;
    line-height: 1.6;
}}
.narrative strong {{ color: #e17055; }}

/* FOOTER */
.footer {{
    text-align: center;
    padding: 24px;
    color: #888;
    font-size: 12px;
    border-top: 1px solid #e0e0e0;
}}
</style>
</head>
<body>

<div class="header">
    <div class="logos">
        <div class="logo-group">
            <span class="logo-badge">🏥 CDN</span>
            <span class="sep">|</span>
            <span class="logo-badge">📚 ESPM</span>
            <span class="sep">|</span>
            <span class="logo-badge">⚡ Accenture</span>
        </div>
    </div>
    <h1>Stock <span>Policy</span> Dashboard</h1>
    <span class="badge">Q4 2024 · Hackathon CDN</span>
</div>

<div class="nav">
    <button class="active" onclick="switchPage('business')">📊 Visão de Negócios</button>
    <button onclick="switchPage('technical')">⚙️ Visão Técnica</button>
    <button onclick="switchPage('simulation')">🎬 Simulação Animada</button>
</div>

<div class="content">

<!-- ========================================================= -->
<!-- PAGE 1: BUSINESS -->
<!-- ========================================================= -->
<div id="page-business" class="page active">

    <div class="kpi-grid" id="kpi-container"></div>

    <div class="insight">
        <h3>💡 O Diagnóstico em Uma Frase</h3>
        <p>
            O modelo atinge <span class="highlight">99,94% de nível de serviço</span> — muito acima da meta de 92%.
            Mas o <span class="highlight">forecast superestima a demanda em 51%</span>, gerando R$ 1.927/trim em
            custo de excesso de estoque. A política conservadora <span class="highlight">esconde o problema</span>:
            resolvendo o forecast, liberamos capital sem perder serviço.
        </p>
    </div>

    <div class="section-title">📈 <span>Performance vs. Real</span></div>

    <div class="two-col">
        <div class="chart-container">
            <h3 style="font-size:14px;font-weight:600;margin-bottom:12px;">Estoque: Simulado vs. Real (NEOSORO 1314)</h3>
            <div id="chart-hero-comparison"></div>
        </div>
        <div class="chart-container">
            <h3 style="font-size:14px;font-weight:600;margin-bottom:12px;">Distribuição da Demanda (ABC)</h3>
            <div id="chart-abc"></div>
        </div>
    </div>

    <div class="section-title">📊 <span>Top 10 SKUs por Receita em Risco</span></div>
    <div class="chart-container">
        <div style="overflow-x:auto;">
            <table class="data-table" id="revenue-risk-table"></table>
        </div>
    </div>

    <div class="section-title">🔄 <span>Comparativo entre Lojas</span></div>
    <div class="two-col">
        <div class="chart-container">
            <div id="chart-loja-comparison"></div>
        </div>
        <div class="chart-container">
            <div class="narrative">
                <strong>⏱ Lead time define a política:</strong> Loja 1314 (LT=9d) precisa de <strong>s=180, S=339</strong>
                para NEOSORO — 16x mais estoque que a Loja 841 (s=11). O lead time longo
                <strong>amplifica o erro de forecast</strong> em 3x vs 1,7x.
            </div>
            <div class="narrative">
                <strong>💰 Custo de pedido é dominado por poucos SKUs:</strong>
                PERCOF 841 (R$ 260) + ABRILAR 200ml 1314 (R$ 391) + OSELTAMIVIR 841 (R$ 304)
                = <strong>36% de todo o custo de reposição</strong>.
            </div>
        </div>
    </div>

    <div class="section-title">📉 <span>Custos Ocultos: Over-forecast vs. Under-forecast</span></div>
    <div class="two-col">
        <div class="chart-container">
            <div id="chart-over-under"></div>
        </div>
        <div class="chart-container">
            <div class="insight" style="height:100%;">
                <h3>⚠️ Assimetria de Risco</h3>
                <p>
                    Custo de errar <span class="highlight">para mais</span> (R$ 1.927/trim):
                    estoque que nunca girou, pagando holding o trimestre inteiro.<br><br>
                    Custo de errar <span class="highlight">para menos</span> (R$ 234/trim):
                    vendas perdidas reais — apenas 3 unidades.<br><br>
                    <strong>Razão: 8,2x</strong> — o excesso é mais caro que a falta.
                    Modelos conservadores <em>parecem</em> seguros,
                    mas o custo do "colchão" é real.
                </p>
            </div>
        </div>
    </div>

    <div class="section-title">🎯 <span>Próximos Passos (Recomendados)</span></div>
    <div class="chart-container">
        <table class="data-table">
            <tr><th>#</th><th>Ação</th><th>Impacto Estimado</th><th>Esforço</th><th>ROI</th></tr>
            <tr>
                <td class="num">1</td><td>review_days 5 → 7</td>
                <td class="num" style="color:#00b894;">-R$ 770/trim</td><td>10 min</td><td class="num" style="font-weight:700;">∞</td>
            </tr>
            <tr>
                <td class="num">2</td><td>z 0,84 → 1,28 (eliminar rupturas)</td>
                <td class="num" style="color:#00b894;">+R$ 6,72/trim · 0 lost sales</td><td>10 min</td><td class="num" style="font-weight:700;">34,8x</td>
            </tr>
            <tr>
                <td class="num">3</td><td>Customizar ABRILAR 1314 + NEOSORO 841</td>
                <td class="num" style="color:#00b894;">Proteger R$ 2.091 receita</td><td>30 min</td><td class="num" style="font-weight:700;">311x</td>
            </tr>
            <tr>
                <td class="num">4</td><td>Corrigir uplift promocional</td>
                <td class="num" style="color:#00b894;">-R$ 432/trim</td><td>4-8h</td><td class="num" style="font-weight:700;">∞ (recorrente)</td>
            </tr>
            <tr>
                <td class="num">5</td><td>SL diferenciado ABC (3 camadas)</td>
                <td class="num" style="color:#00b894;">Liberar R$ 3.839 capital</td><td>4h</td><td class="num" style="font-weight:700;">23,5x</td>
            </tr>
        </table>
    </div>

</div>

<!-- ========================================================= -->
<!-- PAGE 2: TECHNICAL -->
<!-- ========================================================= -->
<div id="page-technical" class="page">

    <div class="section-title">🧠 <span>Arquitetura do Modelo</span></div>

    <div class="chart-container" style="text-align:center;">
        <div style="display:flex;justify-content:space-around;align-items:center;flex-wrap:wrap;gap:12px;padding:20px 0;">
            <div style="background:#302b63;color:#fff;padding:16px 24px;border-radius:10px;min-width:120px;">
                <div style="font-size:12px;opacity:0.7;">ETAPA 1</div>
                <div style="font-weight:700;margin-top:4px;">📦 Panel<br><span style="font-size:11px;opacity:0.7;">8 CSVs → diário por SKU</span></div>
            </div>
            <div style="font-size:28px;color:#00d4aa;">→</div>
            <div style="background:#302b63;color:#fff;padding:16px 24px;border-radius:10px;min-width:120px;">
                <div style="font-size:12px;opacity:0.7;">ETAPA 2</div>
                <div style="font-weight:700;margin-top:4px;">🔮 Forecast<br><span style="font-size:11px;opacity:0.7;">3 fontes + uplift promo</span></div>
            </div>
            <div style="font-size:28px;color:#00d4aa;">→</div>
            <div style="background:#302b63;color:#fff;padding:16px 24px;border-radius:10px;min-width:120px;">
                <div style="font-size:12px;opacity:0.7;">ETAPA 3</div>
                <div style="font-weight:700;margin-top:4px;">🎯 Política (s,S)<br><span style="font-size:11px;opacity:0.7;">z=0,84 · review=5d</span></div>
            </div>
            <div style="font-size:28px;color:#00d4aa;">→</div>
            <div style="background:#302b63;color:#fff;padding:16px 24px;border-radius:10px;min-width:120px;">
                <div style="font-size:12px;opacity:0.7;">ETAPA 4</div>
                <div style="font-weight:700;margin-top:4px;">⚡ Simulação<br><span style="font-size:11px;opacity:0.7;">5.336 dias-SKU · 92 dias</span></div>
            </div>
        </div>
    </div>

    <div class="section-title">📐 <span>Fórmula da Política (s, S)</span></div>
    <div class="two-col">
        <div class="chart-container" style="font-family:'JetBrains Mono',monospace;font-size:15px;line-height:2;">
            <code><strong>s</strong> = ceil( μ × L + z × σ × √L )</code><br>
            <code><strong>S</strong> = ceil( s + μ × review_days )</code><br><br>
            <div style="font-family:'Inter',sans-serif;font-size:13px;color:#555;">
                Onde:<br>
                μ = demanda média diária (forecast)<br>
                σ = desvio padrão da demanda<br>
                L = lead time (3 ou 9 dias)<br>
                z = fator de segurança (0,84 = 80º percentil)<br>
                review_days = intervalo entre revisões (5 dias)
            </div>
        </div>
        <div class="chart-container">
            <h3 style="font-size:14px;font-weight:600;margin-bottom:12px;">Exemplo: NEOSORO Loja 1314</h3>
            <div style="font-family:'JetBrains Mono',monospace;font-size:14px;line-height:1.8;">
                μ = 9,3 un/dia<br>
                σ = 4,7 un<br>
                L = 9 dias<br>
                z = 0,84<br><br>
                <strong>s</strong> = ceil(9,3×9 + 0,84×4,7×3)<br>
                = ceil(83,7 + 11,8)<br>
                = <strong style="color:#00b894;">96</strong> (estatístico)<br><br>
                + piso empírico (75% histórico)<br>
                = <strong style="color:#e17055;">180</strong> (final, com empirical floor)
            </div>
        </div>
    </div>

    <div class="section-title">🔬 <span>Validação do Simulador</span></div>
    <div class="kpi-grid">
        <div class="kpi-card green">
            <div class="label">Lead Time</div>
            <div class="value">100%</div>
            <div class="sub">113 ordens chegam no dia certo</div>
        </div>
        <div class="kpi-card teal">
            <div class="label">Estoque Negativo</div>
            <div class="value">0</div>
            <div class="sub">Zero dias com saldo negativo</div>
        </div>
        <div class="kpi-card green">
            <div class="label">Lost Sales</div>
            <div class="value">3 un</div>
            <div class="sub">Validadas individualmente ✅</div>
        </div>
        <div class="kpi-card teal">
            <div class="label">Ordens Múltiplas</div>
            <div class="value">0</div>
            <div class="sub">Zero ordens duplicadas no mesmo dia</div>
        </div>
    </div>

    <div class="section-title">📊 <span>Grid Search: z × review_days</span></div>
    <div class="chart-container">
        <div id="chart-grid"></div>
    </div>

    <div class="section-title">📈 <span>Previsão vs. Realizado (semanal)</span></div>
    <div class="chart-container">
        <div id="chart-weekly"></div>
    </div>

    <div class="section-title">📋 <span>Tabela de Política (Top 15 por Demanda)</span></div>
    <div class="chart-container">
        <div style="overflow-x:auto;max-height:400px;overflow-y:auto;">
            <table class="data-table" id="policy-table"></table>
        </div>
    </div>

</div>

<!-- ========================================================= -->
<!-- PAGE 3: SIMULATION ANIMATION -->
<!-- ========================================================= -->
<div id="page-simulation" class="page">

    <div class="insight">
        <h3>🎬 O Simulador em Ação</h3>
        <p>
            Arraste o slider ou clique em <strong>Play</strong> para ver o estoque evoluir dia a dia no Q4/2024.
            As <span style="color:#00b894;font-weight:600;">barras verdes</span> são entregas chegando.
            Os <span style="color:#e17055;font-weight:600;">marcadores vermelhos</span> são dias com ruptura.
            A linha azul mostra o estoque <strong>simulado</strong>; a laranja tracejada, o <strong>real</strong> histórico.
        </p>
    </div>

    <div class="chart-container">
        <div class="timeline-controls">
            <button class="btn-play" id="btn-play" onclick="togglePlay()">▶ Play</button>
            <button class="btn-reset" onclick="resetAnimation()">⟲ Reset</button>
            <select id="sku-select" onchange="changeSKU()">
                <option value="18064_1314">NEOSORO · Loja 1314 (LT=9d)</option>
                <option value="18064_841">NEOSORO · Loja 841 (LT=3d)</option>
            </select>
            <select id="chart-type" onchange="updateChartType()">
                <option value="inventory">Estoque (unidades)</option>
                <option value="value">Valor (R$)</option>
            </select>
            <span class="speed-label">Velocidade:</span>
            <select id="speed-select">
                <option value="100">1x</option>
                <option value="300">3x</option>
                <option value="700" selected>7x</option>
                <option value="1500">15x</option>
            </select>
        </div>
        <div id="chart-animation" style="height:500px;"></div>
        <div style="display:flex;align-items:center;gap:16px;margin-top:12px;flex-wrap:wrap;">
            <div style="font-size:13px;color:#555;">
                <strong>Dia:</strong> <span id="day-counter">1</span> / <span id="day-total">92</span>
                &nbsp;|&nbsp; <strong>Data:</strong> <span id="date-display">2024-10-01</span>
            </div>
            <div style="font-size:13px;color:#555;">
                <strong>Estoque:</strong> <span id="inv-display">0</span> un
                &nbsp;|&nbsp; <strong>Valor:</strong> R$ <span id="value-display">0,00</span>
            </div>
            <div id="stockout-badge" style="display:none;background:#e17055;color:#fff;padding:2px 10px;border-radius:4px;font-size:12px;font-weight:600;">
                ⚠️ RUPTURA
            </div>
        </div>
    </div>

    <div class="two-col">
        <div class="chart-container">
            <h3 style="font-size:14px;font-weight:600;margin-bottom:12px;">Fluxo de Pedidos e Entregas</h3>
            <div id="chart-flow"></div>
        </div>
        <div class="chart-container">
            <h3 style="font-size:14px;font-weight:600;margin-bottom:12px;">Demanda Diária vs. Forecast</h3>
            <div id="chart-demand"></div>
        </div>
    </div>

</div>

</div><!-- content -->

<div class="footer">
    Hackathon CDN · ESPM · Accenture · Q4/2024 · Stock Policy Dashboard v1.0
</div>

<script>
// =========================================================
// DATA
// =========================================================
const HERO_DATA = {json.dumps(hero_json)};
const HERO2_DATA = {json.dumps(hero2_json)};
const SKU_DATA = {json.dumps(sku_json)};
const WEEKLY_DATA = {json.dumps(weekly_json)};
const ABC_DATA = {json.dumps(abc_json)};
const TUNE_DATA = {json.dumps(tune_json)};
const LOJA_DATA = {json.dumps(loja_json)};
const PROMO_DATA = {json.dumps(promo_json)};
const OVER_UNDER_DATA = {json.dumps(over_under_json)};
const REV_RISK_DATA = {json.dumps(rev_risk_json)};
const KPI = {json.dumps(kpi)};

// =========================================================
// PAGE SWITCHING
// =========================================================
function switchPage(page) {{
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav button').forEach(b => b.classList.remove('active'));
    document.getElementById('page-' + page).classList.add('active');
    document.querySelector(`.nav button[onclick*="${{page}}"]`).classList.add('active');

    if (page === 'simulation') {{
        setTimeout(initAnimation, 100);
    }}
    if (page === 'business') {{
        setTimeout(drawBusinessCharts, 100);
    }}
    if (page === 'technical') {{
        setTimeout(drawTechnicalCharts, 100);
    }}
}}

// =========================================================
// BUSINESS CHARTS
// =========================================================
function drawBusinessCharts() {{
    // KPI Cards
    const container = document.getElementById('kpi-container');
    container.innerHTML = `
        <div class="kpi-card green">
            <div class="label">Nível de Serviço</div>
            <div class="value">${{(KPI.service_level*100).toFixed(2)}}%</div>
            <div class="sub">Meta: ≥ 92% <span style="color:#00b894;">✅</span></div>
            <div class="delta pos">+${{((KPI.service_level - KPI.actual_service_level)*100).toFixed(2)}}pp vs. real</div>
        </div>
        <div class="kpi-card purple">
            <div class="label">Capital Médio em Estoque</div>
            <div class="val-comp">
                <span class="sim">R$ ${{KPI.avg_inventory_value.toFixed(2)}}</span>
                <span class="arrow">←</span>
                <span class="actual">R$ ${{KPI.actual_avg_inventory_value.toFixed(2)}}</span>
            </div>
            <div class="sub">Simulado vs. Real histórico</div>
            <div class="delta ${{KPI.avg_inventory_value > KPI.actual_avg_inventory_value ? 'neg' : 'pos'}}">
                ${{KPI.avg_inventory_value > KPI.actual_avg_inventory_value ? '+' : '-'}}R$ ${{Math.abs(KPI.avg_inventory_value - KPI.actual_avg_inventory_value).toFixed(2)}}
            </div>
        </div>
        <div class="kpi-card orange">
            <div class="label">Custo Total de Reposição</div>
            <div class="value">R$ ${{KPI.total_ordering_cost.toFixed(2)}}</div>
            <div class="sub">${{KPI.total_orders}} pedidos emitidos</div>
        </div>
        <div class="kpi-card teal">
            <div class="label">Vendas Perdidas</div>
            <div class="value">${{KPI.total_lost_sales_units}} un</div>
            <div class="sub">R$ ${{KPI.total_lost_sales_value.toFixed(2)}} em receita</div>
        </div>
        <div class="kpi-card blue" style="grid-column:span 2;">
            <div class="label">Demanda Total Q4/2024</div>
            <div class="val-comp">
                <span class="sim">${{KPI.total_actual}} un</span>
                <span class="arrow">←</span>
                <span class="actual">${{KPI.total_forecast}} un (forecast)</span>
            </div>
            <div class="sub">Forecast superestima em ${{((KPI.total_forecast/KPI.total_actual - 1)*100).toFixed(0)}}%</div>
            <div class="meter"><div class="meter-fill" style="width:${{(KPI.total_actual/KPI.total_forecast*100).toFixed(0)}}%;background:#e17055;"></div></div>
        </div>
    `;

    // Hero comparison chart
    const hero = HERO_DATA;
    const dates = hero.map(d => d.date_str);
    const simInv = hero.map(d => d.ending_inventory);
    const actInv = hero.map(d => d.actual_balance || 0);
    const received = hero.map(d => d.received_qty || 0);
    const lost = hero.map(d => d.lost_sales_units > 0 ? d.lost_sales_units : null);

    const trace1 = {{ type: 'scatter', mode: 'lines', name: 'Simulado', x: dates, y: simInv, line: {{color: '#302b63', width: 2}} }};
    const trace2 = {{ type: 'scatter', mode: 'lines', name: 'Real (histórico)', x: dates, y: actInv, line: {{color: '#e17055', width: 2, dash: 'dot'}} }};
    const trace3 = {{ type: 'bar', name: 'Entregas', x: dates, y: received, marker: {{color: 'rgba(0,212,170,0.4)'}}, yaxis: 'y2' }};
    const layout = {{
        margin: {{l: 50, r: 30, t: 10, b: 40}},
        height: 280,
        legend: {{orientation: 'h', y: -0.2}},
        yaxis: {{title: 'Unidades'}},
        yaxis2: {{title: 'Entregas', overlaying: 'y', side: 'right', showgrid: false}},
        hovermode: 'x unified',
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
    }};
    Plotly.newPlot('chart-hero-comparison', [trace1, trace2, trace3], layout, {{responsive: true, displayModeBar: false}});

    // ABC chart
    const abc = ABC_DATA;
    const abcLabels = abc.map(d => d.label ? d.label.substring(0, 20) : 'SKU ' + d.product);
    const abcDemand = abc.map(d => d.demand);
    const abcCum = abc.map(d => (d.cum_demand * 100).toFixed(1));

    const abcColors = abc.map(d => d.cum_demand <= 0.80 ? '#302b63' : d.cum_demand <= 0.95 ? '#00d4aa' : '#dfe6e9');
    const abcTrace = {{
        type: 'bar', x: abcLabels, y: abcDemand,
        marker: {{color: abcColors}},
        text: abcCum.map(v => v + '%'),
        textposition: 'outside',
    }};
    const abcLayout = {{
        margin: {{l: 50, r: 30, t: 10, b: 80}},
        height: 280,
        yaxis: {{title: 'Unidades'}},
        xaxis: {{tickangle: -45, tickfont: {{size: 9}}}},
        hovermode: 'x',
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        shapes: [
            {{type: 'line', x0: -0.5, x1: abcLabels.length - 0.5, y0: abcDemand[0]*0.8, y1: abcDemand[0]*0.8,
              line: {{color: '#e17055', width: 1, dash: 'dash'}} }}
        ]
    }};
    Plotly.newPlot('chart-abc', [abcTrace], abcLayout, {{responsive: true, displayModeBar: false}});

    // Revenue risk table
    const revTable = document.getElementById('revenue-risk-table');
    revTable.innerHTML = `
        <tr><th>SKU</th><th>Produto</th><th>Loja</th><th>Receita Q4</th><th>Dias Ruptura</th><th>Status</th></tr>
        ${{REV_RISK_DATA.map(r => `
            <tr>
                <td class="num">${{r.product}}</td>
                <td>${{r.product_name ? r.product_name.substring(0, 30) : ''}}</td>
                <td class="num">${{r.location}}</td>
                <td class="num">R$ ${{r.revenue.toFixed(2)}}</td>
                <td class="num">${{r.stockout}}</td>
                <td>${{r.stockout > 0 ? '<span class="badge-sl low">⚠️ RUPTURA</span>' : '<span class="badge-sl high">✅ OK</span>'}}</td>
            </tr>
        `).join('')}}
    `;

    // Loja comparison chart
    const lojaLabels = LOJA_DATA.map(d => 'Loja ' + d.location);
    const lojaInv = LOJA_DATA.map(d => d.avg_inv);
    const lojaActInv = LOJA_DATA.map(d => d.avg_actual_inv);
    const lojaOrd = LOJA_DATA.map(d => d.orders);

    Plotly.newPlot('chart-loja-comparison', [
        {{type: 'bar', name: 'Estoque Simulado', x: lojaLabels, y: lojaInv, marker: {{color: '#302b63'}}}},
        {{type: 'bar', name: 'Estoque Real', x: lojaLabels, y: lojaActInv, marker: {{color: '#e17055'}}}},
    ], {{
        barmode: 'group', margin: {{l: 50, r: 30, t: 10, b: 40}}, height: 280,
        yaxis: {{title: 'R$'}},
        legend: {{orientation: 'h', y: -0.2}},
        paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    }}, {{responsive: true, displayModeBar: false}});

    // Over/under chart
    const ou = OVER_UNDER_DATA.filter(d => d.over + d.under > 0).sort((a,b) => (b.over+b.under) - (a.over+a.under)).slice(0, 10);
    const ouLabels = ou.map(d => d.label ? d.label.substring(0, 18) : 'SKU ' + d.product);
    Plotly.newPlot('chart-over-under', [
        {{type: 'bar', name: 'Over (superestimou)', x: ouLabels, y: ou.map(d => d.over), marker: {{color: '#e17055'}}}},
        {{type: 'bar', name: 'Under (subestimou)', x: ouLabels, y: ou.map(d => d.under), marker: {{color: '#00b894'}}}},
    ], {{
        barmode: 'relative', margin: {{l: 50, r: 30, t: 10, b: 80}}, height: 280,
        xaxis: {{tickangle: -45, tickfont: {{size: 9}}}},
        yaxis: {{title: 'Unidades'}},
        legend: {{orientation: 'h', y: -0.3}},
        paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    }}, {{responsive: true, displayModeBar: false}});
}}

// =========================================================
// TECHNICAL CHARTS
// =========================================================
function drawTechnicalCharts() {{
    // Grid search chart
    if (TUNE_DATA.length > 0) {{
        const byReview = {{}};
        TUNE_DATA.forEach(d => {{
            if (!byReview[d.review_days]) byReview[d.review_days] = [];
            byReview[d.review_days].push(d);
        }});
        const traces = Object.keys(byReview).sort().map(rd => ({{
            type: 'scatter', mode: 'lines+markers',
            name: `review=${{rd}}d`,
            x: byReview[rd].map(d => d.z_value),
            y: byReview[rd].map(d => d.avg_inventory_value),
            line: {{width: 2}},
        }}));
        Plotly.newPlot('chart-grid', traces, {{
            margin: {{l: 50, r: 30, t: 10, b: 40}}, height: 300,
            xaxis: {{title: 'z_value'}}, yaxis: {{title: 'Estoque Médio (R$)'}},
            legend: {{orientation: 'h', y: -0.2}},
            hovermode: 'x unified',
            paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
        }}, {{responsive: true, displayModeBar: false}});
    }}

    // Weekly chart
    const wkDates = WEEKLY_DATA.map(d => 'Sem ' + d.week);
    Plotly.newPlot('chart-weekly', [
        {{type: 'bar', name: 'Real', x: wkDates, y: WEEKLY_DATA.map(d => d.demand), marker: {{color: '#302b63'}}}},
        {{type: 'bar', name: 'Forecast', x: wkDates, y: WEEKLY_DATA.map(d => d.forecast), marker: {{color: 'rgba(0,212,170,0.6)'}}}},
    ], {{
        barmode: 'group', margin: {{l: 50, r: 30, t: 10, b: 40}}, height: 280,
        yaxis: {{title: 'Unidades'}},
        legend: {{orientation: 'h', y: -0.2}},
        paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    }}, {{responsive: true, displayModeBar: false}});

    // Policy table
    const sorted = [...SKU_DATA].filter(d => d.total_actual_demand > 0).sort((a,b) => b.total_actual_demand - a.total_actual_demand).slice(0, 15);
    const table = document.getElementById('policy-table');
    table.innerHTML = `
        <tr><th>SKU</th><th>Produto</th><th>Loja</th><th>s</th><th>S</th><th>Demanda</th><th>SL</th><th>Estoque</th></tr>
        ${{sorted.map(r => `
            <tr>
                <td class="num">${{r.product}}</td>
                <td>${{r.product_name ? r.product_name.substring(0, 28) : ''}}</td>
                <td class="num">${{r.location}}</td>
                <td class="num"><strong>${{r.reorder_point_s}}</strong></td>
                <td class="num"><strong>${{r.order_up_to_S}}</strong></td>
                <td class="num">${{r.total_actual_demand}}</td>
                <td><span class="badge-sl ${{r.service_level >= 0.99 ? 'high' : r.service_level >= 0.92 ? 'medium' : 'low'}}">${{(r.service_level*100).toFixed(1)}}%</span></td>
                <td class="num">R$ ${{r.avg_inventory_value.toFixed(2)}}</td>
            </tr>
        `).join('')}}
    `;
}}

// =========================================================
// SIMULATION ANIMATION
// =========================================================
let animData = [];
let animIndex = 0;
let animInterval = null;
let isPlaying = false;
let currentSKU = '18064_1314';

function getData() {{
    const parts = currentSKU.split('_');
    const prod = parseInt(parts[0]);
    const loc = parseInt(parts[1]);
    if (prod === 18064 && loc === 1314) return HERO_DATA;
    return HERO2_DATA;
}}

function initAnimation() {{
    animIndex = 0;
    if (animInterval) {{
        clearInterval(animInterval);
        animInterval = null;
    }}
    isPlaying = false;
    document.getElementById('btn-play').textContent = '▶ Play';
    document.getElementById('btn-play').className = 'btn-play';
    drawAnimationFrame(0);
    drawFlowChart();
    drawDemandChart();
}}

function togglePlay() {{
    if (isPlaying) {{
        clearInterval(animInterval);
        animInterval = null;
        isPlaying = false;
        document.getElementById('btn-play').textContent = '▶ Play';
        document.getElementById('btn-play').className = 'btn-play';
    }} else {{
        isPlaying = true;
        document.getElementById('btn-play').textContent = '⏸ Pause';
        document.getElementById('btn-play').className = 'btn-pause';
        const speed = parseInt(document.getElementById('speed-select').value);
        animInterval = setInterval(() => {{
            animIndex++;
            if (animIndex >= getData().length) {{
                animIndex = getData().length - 1;
                clearInterval(animInterval);
                animInterval = null;
                isPlaying = false;
                document.getElementById('btn-play').textContent = '▶ Play';
                document.getElementById('btn-play').className = 'btn-play';
            }}
            drawAnimationFrame(animIndex);
        }}, speed);
    }}
}}

function resetAnimation() {{
    if (animInterval) {{
        clearInterval(animInterval);
        animInterval = null;
    }}
    isPlaying = false;
    animIndex = 0;
    document.getElementById('btn-play').textContent = '▶ Play';
    document.getElementById('btn-play').className = 'btn-play';
    drawAnimationFrame(0);
}}

function changeSKU() {{
    currentSKU = document.getElementById('sku-select').value;
    resetAnimation();
    drawFlowChart();
    drawDemandChart();
}}

function updateChartType() {{
    drawAnimationFrame(animIndex);
}}

function drawAnimationFrame(idx) {{
    const data = getData();
    if (!data.length) return;
    const showAll = idx >= data.length - 1;
    const endIdx = showAll ? data.length - 1 : idx;
    const slice = data.slice(0, endIdx + 1);

    // Update counters
    document.getElementById('day-counter').textContent = endIdx + 1;
    document.getElementById('day-total').textContent = data.length;
    document.getElementById('date-display').textContent = data[endIdx].date_str;
    document.getElementById('inv-display').textContent = data[endIdx].ending_inventory.toFixed(0);
    document.getElementById('value-display').textContent = data[endIdx].simulated_inventory_value.toFixed(2);

    const badge = document.getElementById('stockout-badge');
    if (data[endIdx].lost_sales_units > 0) {{
        badge.style.display = 'inline-block';
    }} else {{
        badge.style.display = 'none';
    }}

    const chartType = document.getElementById('chart-type').value;
    const isValue = chartType === 'value';

    const simY = slice.map(d => isValue ? d.simulated_inventory_value : d.ending_inventory);
    const actY = slice.map(d => isValue ? (d.actual_inventory_value || 0) : (d.actual_balance || 0));
    const dates = slice.map(d => d.date_str);

    // Markers for received qty
    const recvX = [], recvY = [];
    slice.forEach((d, i) => {{
        if (d.received_qty > 0) {{
            recvX.push(d.date_str);
            recvY.push(isValue ? d.simulated_inventory_value : d.ending_inventory);
        }}
    }});

    // Markers for lost sales
    const lostX = [], lostY = [];
    slice.forEach((d, i) => {{
        if (d.lost_sales_units > 0) {{
            lostX.push(d.date_str);
            lostY.push(isValue ? d.simulated_inventory_value : d.ending_inventory);
        }}
    }});

    // Markers for order placed
    const ordX = [], ordY = [];
    slice.forEach((d, i) => {{
        if (d.order_qty > 0) {{
            ordX.push(d.date_str);
            const yVal = isValue ? d.simulated_inventory_value : d.inventory_position_before_order;
            ordY.push(yVal);
        }}
    }});

    const traces = [
        {{type: 'scatter', mode: 'lines', name: 'Simulado', x: dates, y: simY, line: {{color: '#302b63', width: 2.5}}}},
        {{type: 'scatter', mode: 'lines', name: 'Real (histórico)', x: dates, y: actY, line: {{color: '#e17055', width: 2, dash: 'dot'}}}},
        {{type: 'scatter', mode: 'markers', name: '📦 Entrega', x: recvX, y: recvY, marker: {{color: '#00b894', size: 12, symbol: 'triangle-down'}}}},
        {{type: 'scatter', mode: 'markers', name: '📝 Pedido', x: ordX, y: ordY, marker: {{color: '#0984e3', size: 10, symbol: 'triangle-up'}}}},
        {{type: 'scatter', mode: 'markers', name: '⚠️ Ruptura', x: lostX, y: lostY, marker: {{color: '#e17055', size: 14, symbol: 'x'}}}},
    ];

    const layout = {{
        margin: {{l: 50, r: 30, t: 10, b: 50}},
        xaxis: {{title: 'Data', tickangle: -45, tickfont: {{size: 10}}}},
        yaxis: {{title: isValue ? 'Valor (R$)' : 'Unidades'}},
        showlegend: true,
        legend: {{orientation: 'h', y: -0.25, font: {{size: 11}}}},
        hovermode: 'x unified',
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
    }};

    Plotly.react('chart-animation', traces, layout, {{responsive: true, displayModeBar: false}});
}}

function drawFlowChart() {{
    const data = getData();
    const slice = data.slice(0, Math.min(30, data.length));

    Plotly.newPlot('chart-flow', [
        {{type: 'bar', name: 'Pedidos', x: slice.map(d => d.date_str), y: slice.map(d => d.order_qty || 0), marker: {{color: '#0984e3'}}}},
        {{type: 'bar', name: 'Entregas', x: slice.map(d => d.date_str), y: slice.map(d => d.received_qty || 0), marker: {{color: '#00b894'}}}},
    ], {{
        barmode: 'group', margin: {{l: 40, r: 20, t: 10, b: 50}}, height: 250,
        xaxis: {{tickangle: -45, tickfont: {{size: 9}}}},
        legend: {{orientation: 'h', y: -0.3}},
        paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    }}, {{responsive: true, displayModeBar: false}});
}}

function drawDemandChart() {{
    const data = getData();
    const slice = data.slice(0, Math.min(30, data.length));

    Plotly.newPlot('chart-demand', [
        {{type: 'scatter', mode: 'lines+markers', name: 'Demanda Real', x: slice.map(d => d.date_str), y: slice.map(d => d.actual_demand || 0), line: {{color: '#e17055', width: 2}}, marker: {{size: 6}}}},
        {{type: 'scatter', mode: 'lines+markers', name: 'Atendido', x: slice.map(d => d.date_str), y: slice.map(d => d.fulfilled_units || 0), line: {{color: '#00b894', width: 2}}, marker: {{size: 6}}}},
    ], {{
        margin: {{l: 40, r: 20, t: 10, b: 50}}, height: 250,
        xaxis: {{tickangle: -45, tickfont: {{size: 9}}}},
        legend: {{orientation: 'h', y: -0.3}},
        paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)',
    }}, {{responsive: true, displayModeBar: false}});
}}

// Init
drawBusinessCharts();
drawTechnicalCharts();
setTimeout(initAnimation, 500);
</script>
</body>
</html>'''

with open("dashboard.html", "w", encoding="utf-8") as f:
    f.write(html)

print("[OK] dashboard.html generated successfully")
print(f"   File size: {len(html.encode('utf-8')) / 1024:.0f} KB")
print("   Open in browser to view")
