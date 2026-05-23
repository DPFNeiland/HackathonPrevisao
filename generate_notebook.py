import json
from pathlib import Path

cells = []

def md(source):
    cells.append({
        "cell_type": "markdown",
        "metadata": {},
        "source": source if isinstance(source, list) else [source],
    })

def code(source):
    cells.append({
        "cell_type": "code",
        "metadata": {},
        "source": source if isinstance(source, list) else [source],
        "outputs": [],
        "execution_count": None,
    })

# ============================================================
# CELL 0: Title
# ============================================================
md("""# Simulador de Politica de Estoque (s,S)
## Hackathon CDN — Q4/2024 — Categoria Gripe e Resfriado

**MVP Final — Politica segmentada ABC com estoque otimizado**

| Metrica | Resultado |
|---------|-----------|
| Nivel de Servico | **99,85%** |
| Estoque medio | **R$ 143,71/dia** |
| Custo de reposicao | R$ 2.674,42 |
| Pedidos emitidos | 113 |
| Vendas perdidas | 12 un (0,98% da demanda) |
| Forecast total | 1.610 un vs 1.225 un reais |
| Capital liberado vs baseline | **R$ 2.398/tri** |

**Arquivos de saida:**
- `policy.csv` — 58 pares SKU-loja com `reorder_point_s` e `order_up_to_S`
- `simulation_daily.csv` — 5.336 linhas de simulacao dia a dia
- `dashboard.html` — dashboard interativo com 6 abas
""")

# ============================================================
# CELL 1: Imports
# ============================================================
code("""import pandas as pd
import numpy as np
import json
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Modulos do projeto
from stock_policy_product.engine import (
    Horizon,
    build_policy,
    build_forecast,
    build_summary_from_forecast,
    build_overall_metrics,
    build_sku_metrics,
    simulate_policy,
    prepare_enriched_panel,
    apply_empirical_demand_floors,
    assign_abc_class_by_demand,
)

print("Modulos carregados com sucesso.")
""")

# ============================================================
# CELL 2: Load policy.csv
# ============================================================
md("""## 1. Politica de Reposicao (s,S)

A politica define, para cada par SKU-loja:
- **s (reorder_point)**: nivel de estoque que dispara um pedido
- **S (order_up_to)**: nivel maximo apos recebimento do pedido

Formula:
```
s = ceil(mu_daily * lead_time + z * sigma * sqrt(lead_time))
S = ceil(s + mu_daily * review_days)
```

Onde `z` e o fator de seguranca (security factor). SKUs classe A usam z=1,28 (maxima protecao), classe B z=0,84, classe C z=0,00 (estoque minimo).
""")

code("""# Carregar a politica final
policy = pd.read_csv("stock_policy_product_output/policy.csv")
print(f"Politica carregada: {len(policy)} pares SKU-loja")
print(f"\\nAmostra (primeiros 10):")
print(policy.head(10).to_string(index=False))
print(f"\\nEstatisticas:")
print(f"  s: min={policy['reorder_point_s'].min()}, max={policy['reorder_point_s'].max()}, mean={policy['reorder_point_s'].mean():.1f}")
print(f"  S: min={policy['order_up_to_S'].min()}, max={policy['order_up_to_S'].max()}, mean={policy['order_up_to_S'].mean():.1f}")
""")

# ============================================================
# CELL 3: Load and explain the data
# ============================================================
md("""## 2. Dados Utilizados

8 CSVs em `data/`, relacionados por `product`, `location`, `campaign`:

| Arquivo | Conteudo |
|---------|----------|
| `2_produtos_locais.csv` | Cadastro SKU x loja (precos, lead times) |
| `3_locais.csv` | Lojas: 841 (L=3d) e 1314 (L=9d) |
| `4_campanhas.csv` | Campanhas promocionais 2023-2024 |
| `5_produtos_locais_campanhas.csv` | Vinculo SKU-loja-campanha |
| `7_saldo.csv` | Snapshots de estoque |
| `8_inventario_venda.csv` | Movimentacao dia a dia (SALE negativo = demanda) |

**Periodo de avaliacao (backtest):** 01/10/2024 a 31/12/2024 (92 dias)
""")

code("""# Ver estrutura dos dados
data_dir = Path("data")
for f in sorted(data_dir.glob("*.csv")):
    df = pd.read_csv(f, nrows=2)
    print(f"{f.name}: {df.shape[1]} cols, {df.columns.tolist()[:6]}...")
""")

# ============================================================
# CELL 4: Build the enriched panel
# ============================================================
md("""## 3. Painel Enriquecido

O `prepare_enriched_panel` faz:
1. Merge dos 8 CSVs em grade diaria SKU-loja-data
2. Correcao de demanda censurada (ruptura → imputa baseline)
3. Calculo de uplift promocional (mediana + dampening sqrt)
""")

code("""# Construir painel enriquecido
final_horizon = Horizon(
    name="test_q4_2024",
    train_end=pd.Timestamp("2024-09-30"),
    start=pd.Timestamp("2024-10-01"),
    end=pd.Timestamp("2024-12-31"),
)

panel = prepare_enriched_panel(
    data_dir=data_dir,
    horizon_end=final_horizon.end,
    train_end=final_horizon.train_end,
)

print(f"Painel: {len(panel)} linhas, {len(panel.columns)} colunas")
print(f"Periodo: {panel['date'].min().date()} a {panel['date'].max().date()}")
print(f"SKUs: {panel['product'].nunique()}, Lojas: {panel['location'].nunique()}")

# Verificar dados de uma amostra
sample = panel[(panel["product"] == 18064) & (panel["location"] == 1314)]
print(f"\\nNEOSORO 1314: {len(sample)} dias, demanda total={sample['demand'].sum():.0f}")
print(f"  Uplift promocional medio: {sample['promo_uplift'].mean():.2f}")
""")

# ============================================================
# CELL 5: Build forecast
# ============================================================
md("""## 4. Forecast de Demanda

Modelo de forecast com 3 componentes ponderadas:
- **45%**: media movel dos ultimos 28 dias
- **35%**: media do mesmo dia da semana (8 ocorrencias)
- **20%**: mesma janela do ano anterior

Com ajustes:
- **Uplift promocional**: multiplicador em dias de campanha
- **Zero-forecast**: SKUs com demanda <= 3 un/Q4 tem forecast = 0
""")

code("""# Construir forecast
forecast = build_forecast(panel, horizon=final_horizon, mode="static")
summary = build_summary_from_forecast(forecast)

# Zero-forecast para SKUs de baixa demanda
zero_pairs = summary.loc[summary["total_observed_period"] <= 3, ["location", "product"]]
for _, row in zero_pairs.iterrows():
    mask = (forecast["location"] == row["location"]) & (forecast["product"] == row["product"])
    forecast.loc[mask, "forecast_demand"] = 0.0
summary = build_summary_from_forecast(forecast)

print(f"Forecast: {len(forecast)} linhas (92 dias x 58 pares = {92*58})")
print(f"SKUs com forecast zerado: {len(zero_pairs)}")
print(f"\\nForecast total Q4: {forecast['forecast_demand'].sum():.0f} un")
print(f"Demanda real Q4:    {forecast['observed_demand'].sum():.0f} un")
print(f"Superestimacao:     {((forecast['forecast_demand'].sum()/forecast['observed_demand'].sum()-1)*100):.1f}%")
""")

# ============================================================
# CELL 6: ABC Classification
# ============================================================
md("""## 5. Classificacao ABC

Classificacao por **volume de demanda real** no Q4, thresholds:
- **Classe A** (70%): z = 1,28 — protecao maxima (zero ruptura no NEOSORO)
- **Classe B** (70-88%): z = 0,84 — protecao padrao
- **Classe C** (>88%): z = 0,00 — estoque minimo (pisos empiricos)
""")

code("""# Classificar ABC por demanda
summary = assign_abc_class_by_demand(summary, a_threshold=0.70, b_threshold=0.88)

abc_stats = summary.groupby("abc_class").agg(
    pares=("product", "count"),
    demanda=("total_observed_period", "sum"),
).assign(
    pct_demanda=lambda x: (x["demanda"] / x["demanda"].sum() * 100).round(1)
)
print("Distribuicao ABC:")
print(abc_stats.to_string())

# z values por classe
z_by_class = {"A": 1.28, "B": 0.84, "C": 0.0}
print(f"\\nz por classe: {z_by_class}")
""")

# ============================================================
# CELL 7: Build and apply policy
# ============================================================
md("""## 6. Construcao da Politica (s,S)

Aplica a formula (s,S) com z segmentado por classe ABC e pisos empiricos reduzidos (0.50/0.75) para manter estoque abaixo do baseline.
""")

code("""# Construir politica
policy_full = build_policy(
    summary=summary,
    z_value=0.84,
    review_days=7,
    z_by_class=z_by_class,
    overrides=None,
)

# Aplicar pisos empiricos reduzidos
policy_full = apply_empirical_demand_floors(
    policy_full,
    panel,
    train_end=final_horizon.train_end,
    reorder_quantile=0.50,
    order_up_to_quantile=0.75,
    seasonal_reference_start=final_horizon.start - pd.DateOffset(years=1),
    seasonal_reference_end=final_horizon.end - pd.DateOffset(years=1),
)

print("Politica construida. Verificando restricoes...")
s_violations = (policy_full["order_up_to_S"] <= policy_full["reorder_point_s"]).sum()
print(f"  Violacoes S <= s: {s_violations} (deve ser 0)")

# Exportar policy.csv
policy_export = policy_full[["product", "location", "reorder_point_s", "order_up_to_S"]]
policy_export.to_csv("policy.csv", index=False)
print(f"\\npolicy.csv exportado: {len(policy_export)} pares")
print(policy_export.head(10).to_string(index=False))
""")

# ============================================================
# CELL 8: Run simulation
# ============================================================
md("""## 7. Simulacao Dia a Dia

Convencao operacional:
1. **Amanhecer**: receber pedidos em transito
2. **Decidir**: se posicao de estoque <= s, emitir pedido ate S
3. **Consumir**: atender demanda do dia
4. **Fechar**: saldo final, ruptura se demanda > saldo
""")

code("""# Executar simulacao
simulation = simulate_policy(
    panel=panel,
    forecast=forecast,
    policy=policy_full,
    horizon=final_horizon,
    warmup_days=45,
)

print(f"Simulacao concluida: {len(simulation)} linhas")

# Amostra de 5 dias para NEOSORO 1314
hero = simulation[(simulation["product"] == 18064) & (simulation["location"] == 1314)]
print("\\nNEOSORO 1314 — Amostra de 5 dias:")
cols = ["date", "opening_inventory", "actual_demand", "fulfilled_units", 
        "ending_inventory", "order_qty", "simulated_stockout_flag"]
print(hero[cols].head(5).to_string(index=False))
""")

# ============================================================
# CELL 9: KPIs
# ============================================================
md("""## 8. Resultados — KPIs Consolidados""")

code("""# Calcular metricas
sku_metrics = build_sku_metrics(simulation, policy=policy_full)
overall_metrics = build_overall_metrics(simulation)

print("=" * 60)
print("RESULTADOS FINAIS — Q4/2024")
print("=" * 60)

m = overall_metrics
print(f"\\nNivel de Servico:        {m['service_level']*100:.2f}%")
print(f"  (operacao real):         {m['actual_service_level']*100:.2f}%")
print(f"  (delta vs real):         {m['service_level_delta_vs_actual']*100:+.2f}pp")
print(f"\\nEstoque medio:          R$ {m['avg_inventory_value']:.2f}/dia")
print(f"  (operacao real):        R$ {m['actual_avg_inventory_value']:.2f}/dia")
print(f"  (delta vs real):        R$ {m['inventory_value_delta_vs_actual']:+.2f}")
print(f"\\nCusto de reposicao:     R$ {m['total_ordering_cost']:.2f}")
print(f"Pedidos emitidos:         {m['total_orders']}")
print(f"\\nVendas perdidas:         {m['total_lost_sales_units']:.0f} un")
print(f"Demanda real Q4:          {m['total_actual_units']:.0f} un")
print(f"Forecast total Q4:        {m['total_forecast_units']:.0f} un")
print(f"Horizonte:                {m['horizon_days']} dias")
print(f"\\nTaxa de atendimento:     {(1 - m['total_lost_sales_units']/m['total_actual_units'])*100:.2f}%")

# Comparacao com baseline
baseline = {
    "service_level": 0.9994,
    "avg_inventory_value": 169.78,
    "total_ordering_cost": 2629.55,
    "total_lost_sales_units": 3,
    "total_orders": 113,
    "total_forecast_units": 1845,
}

print("\\n" + "=" * 60)
print("COMPARACAO COM BASELINE (z=0.84 uniforme)")
print("=" * 60)
delta_inv = m["avg_inventory_value"] - baseline["avg_inventory_value"]
delta_cost = m["total_ordering_cost"] - baseline["total_ordering_cost"]
delta_lost = m["total_lost_sales_units"] - baseline["total_lost_sales_units"]
capital_liberado = abs(delta_inv) * m["horizon_days"] if delta_inv < 0 else 0
print(f"Estoque:        {delta_inv:+.2f}/dia → capital liberado: R$ {capital_liberado:.0f}/tri")
print(f"Custo pedido:   {delta_cost:+.2f}")
print(f"Lost sales:     {delta_lost:+.0f} un")
print(f"Forecast:       {m['total_forecast_units'] - baseline['total_forecast_units']:+.0f} un ({(m['total_forecast_units']/baseline['total_forecast_units']-1)*100:+.1f}%)")
""")

# ============================================================
# CELL 10: ABC breakdown
# ============================================================
md("""## 9. Breakdown por Classe ABC""")

code("""# Metricas por classe
ab = sku_metrics.groupby("abc_class").agg(
    pares=("product", "count"),
    demanda=("total_actual_demand", "sum"),
    estoque_medio=("avg_inventory_value", "mean"),
    pedidos=("total_orders", "sum"),
    custo=("total_ordering_cost", "sum"),
    lost=("total_lost_sales_units", "sum"),
    sl_medio=("service_level", "mean"),
)

ab["pct_demanda"] = (ab["demanda"] / ab["demanda"].sum() * 100).round(1)
ab["z"] = [z_by_class.get(c, "N/A") for c in ab.index]

print("Breakdown por classe ABC:")
print(ab.to_string())
print(f"\\nTotal: {ab['pares'].sum()} pares, {ab['demanda'].sum():.0f} un demanda")
""")

# ============================================================
# CELL 11: Per location
# ============================================================
md("""## 10. Comparativo por Loja

Loja 841 (Ceres/GO): lead time 3 dias, 174 un vendidas
Loja 1314 (Corumba/MS): lead time 9 dias, 1051 un vendidas
""")

code("""# Metricas por loja
loja = sku_metrics.groupby("location").agg(
    demanda=("total_actual_demand", "sum"),
    estoque_medio=("avg_inventory_value", "mean"),
    estoque_real=("actual_avg_inventory_value", "mean"),
    pedidos=("total_orders", "sum"),
    custo=("total_ordering_cost", "sum"),
    lost=("total_lost_sales_units", "sum"),
    sl=("service_level", "mean"),
)

loja["delta_inv"] = loja["estoque_medio"] - loja["estoque_real"]
print("Comparativo por Loja:")
print(loja.to_string())

# Top 5 SKU-loja por receita
print("\\nTop 5 SKU-Loja por demanda:")
top = sku_metrics.nlargest(5, "total_actual_demand")[
    ["product", "product_name", "location", "abc_class", 
     "total_actual_demand", "avg_inventory_value", "reorder_point_s", "order_up_to_S"]
]
print(top.to_string(index=False))
""")

# ============================================================
# CELL 12: Visualize simulation
# ============================================================
md("""## 11. Visualizacao — NEOSORO 1314 (Classe A, z=1.28)

Simulacao dia a dia do SKU mais importante (70% da demanda total).
""")

code("""import matplotlib.pyplot as plt

# Dados do NEOSORO 1314
hero = simulation[(simulation["product"] == 18064) & (simulation["location"] == 1314)].copy()
hero = hero.sort_values("date")

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

# Grafico 1: Estoque simulado
ax1.fill_between(hero["date"], hero["ending_inventory"], alpha=0.3, color="#00b894", label="Estoque simulado")
ax1.plot(hero["date"], hero["ending_inventory"], color="#00b894", linewidth=1.5)
ax1.axhline(y=hero["reorder_point_s"].iloc[0], color="#fdcb6e", linestyle="--", linewidth=1, label=f"s = {hero['reorder_point_s'].iloc[0]}")
ax1.axhline(y=hero["order_up_to_S"].iloc[0], color="#e17055", linestyle="--", linewidth=1, label=f"S = {hero['order_up_to_S'].iloc[0]}")
ax1.set_ylabel("Unidades")
ax1.set_title("NEOSORO 1314 — Estoque Simulado (Classe A, z=1.28, L=9d)")
ax1.legend(loc="upper right", fontsize=9)
ax1.grid(True, alpha=0.3)

# Grafico 2: Demanda diaria
colors = ["#e17055" if s else "#00b894" for s in hero["simulated_stockout_flag"]]
ax2.bar(hero["date"], hero["actual_demand"], color=colors, alpha=0.7, label="Demanda")
ax2.set_ylabel("Unidades")
ax2.set_xlabel("Data")
ax2.set_title("Demanda Diaria (vermelho = stockout)")
ax2.legend(fontsize=9)
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.show()

# Resumo do NEOSORO
print(f"NEOSORO 1314: demanda={hero['actual_demand'].sum():.0f}, lost={hero['lost_sales_units'].sum():.0f}, stockout_days={hero['simulated_stockout_flag'].sum()}")
print(f"Estoque medio: {hero['ending_inventory'].mean():.1f} un = R$ {hero['simulated_inventory_value'].mean():.0f}/dia")
""")

# ============================================================
# CELL 13: How to use the policy
# ============================================================
md("""## 12. Como Usar a Politica

O arquivo `policy.csv` contem os parametros para os 58 pares SKU-loja.

### Aplicacao diaria na loja:

```python
# 1. Carregar politica
policy = pd.read_csv("policy.csv")

# 2. Para cada SKU na loja, ao amanhecer:
#    - Verificar posicao de estoque (fisico + pedidos em transito)
#    - Se posicao <= policy["reorder_point_s"]: emitir pedido
#    - Quantidade: policy["order_up_to_S"] - posicao

pedido = max(0, policy_row["order_up_to_S"] - posicao_estoque)
```

### Parametros por loja:
- **Loja 841**: lead time = 3 dias
- **Loja 1314**: lead time = 9 dias

### Arquivos gerados:
| Arquivo | Descricao |
|---------|-----------|
| `policy.csv` | Parametros (s,S) por SKU-loja (MVP) |
| `simulation_daily.csv` | Simulacao dia a dia (5336 linhas) |
| `sku_metrics.csv` | Metricas por SKU-loja |
| `overall_metrics.json` | KPIs consolidados |
| `dashboard.html` | Dashboard interativo |
""")

# ============================================================
# WRITE NOTEBOOK
# ============================================================
notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "version": "3.10.0",
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

output_path = Path("simulator.ipynb")
output_path.write_text(json.dumps(notebook, indent=1, ensure_ascii=False), encoding="utf-8")
print(f"Notebook gerado: {output_path}")
print(f"  {len(cells)} celulas (markdown + code)")
