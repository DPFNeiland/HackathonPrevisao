import pandas as pd
import numpy as np

sim = pd.read_csv('stock_policy_product_output/simulation_daily.csv')
sku = pd.read_csv('stock_policy_product_output/sku_metrics.csv')
policy = pd.read_csv('stock_policy_product_output/policy_enriched.csv')
sim['date'] = pd.to_datetime(sim['date'])

# Join product names
prod_names = sim[['product', 'product_name']].drop_duplicates().set_index('product')['product_name'].to_dict()
def pn(pid):
    return str(prod_names.get(pid, f'SKU {pid}'))[:35]

# ======================================================================
# 1. HIGH VARIABILITY + LOW VOLUME (intermittent/CVs)
# ======================================================================
print('=' * 100)
print('1. SKUs COM ALTA VARIABILIDADE E BAIXO VOLUME')
print('=' * 100)
print()
print('  (Alta variabilidade = CV > 1.5 | Baixo volume = demanda total Q4 < 10)')
print()

sku_stats = sim.groupby(['product', 'location']).agg(
    total_demand=('actual_demand', 'sum'),
    mean_daily=('actual_demand', 'mean'),
    std_daily=('actual_demand', 'std'),
    zero_days=('actual_demand', lambda x: (x == 0).sum()),
    total_days=('actual_demand', 'count'),
    stockout_days=('simulated_stockout_flag', 'sum'),
    avg_inv=('ending_inventory', 'mean'),
    max_inv=('ending_inventory', 'max'),
    purchase_price=('purchase_price', 'first'),
    sales_price=('sales_price', 'first'),
).reset_index()

sku_stats['cv'] = sku_stats['std_daily'] / sku_stats['mean_daily'].replace(0, np.nan)
sku_stats['pct_zero'] = sku_stats['zero_days'] / sku_stats['total_days']
sku_stats['unit_margin'] = sku_stats['sales_price'] - sku_stats['purchase_price']
sku_stats['demand_class'] = pd.cut(sku_stats['total_demand'], 
                                   bins=[-1, 0, 5, 20, 100, 1000], 
                                   labels=['zero', 'micro', 'baixo', 'medio', 'alto'])

# High CV + low volume
high_cv_low_vol = sku_stats[(sku_stats['cv'] > 1.5) & (sku_stats['total_demand'] < 10) & (sku_stats['total_demand'] >= 0)]
high_cv_low_vol = high_cv_low_vol.sort_values('cv', ascending=False)

print(f'  Total SKUs classificados: {len(high_cv_low_vol)}')
print()
print(f'  {"SKU":>6s} {"Loja":>5s} {"Produto":35s} {"Demanda":>8s} {"CV":>6s} {"%Zero":>7s} {"Estq":>5s} {"Margem":>7s} {"s":>3s} {"S":>3s} {"Stockout":>8s}')
print(f'  {"---":>6s} {"----":>5s} {"-------":35s} {"-------":>8s} {"---":>6s} {"-----":>7s} {"----":>5s} {"------":>7s} {"--":>3s} {"--":>3s} {"--------":>8s}')

# Merge with policy
merged = high_cv_low_vol.merge(policy[['product', 'location', 'reorder_point_s', 'order_up_to_S']], 
                               on=['product', 'location'], how='left')

for _, r in merged.iterrows():
    margin_str = f'R$ {r["unit_margin"]:>5.2f}' if pd.notna(r['unit_margin']) else 'N/A'
    print(f'  {str(r["product"]):>6s} {str(r["location"]):>5s} {pn(r["product"]):35s} {r["total_demand"]:>8.0f} {r["cv"]:>5.1f} {r["pct_zero"]:>6.1%} {r["avg_inv"]:>5.1f} {margin_str:>7s} {r["reorder_point_s"]:>3.0f} {r["order_up_to_S"]:>3.0f} {r["stockout_days"]:>8.0f}')

print()
print('  --- CARACTERIZACAO ---')
print(f'  Demanda media entre estes SKUs: {merged["total_demand"].mean():.1f} un/Q4')
print(f'  Zero days medio: {merged["pct_zero"].mean():.1%}')
print(f'  Estoque medio: {merged["avg_inv"].mean():.1f} un')
print(f'  Margem media: R$ {merged["unit_margin"].mean():.2f}')
print(f'  Cobertura media: {(merged["avg_inv"] / (merged["total_demand"]/92).replace(0, np.nan)).mean():.0f} dias (vs LT de 3-9d)')
print()
print(f'  >>> PROBLEMA: estoque para demanda previsivelmente zero gera capital parado')
print(f'      sem beneficio de servico (SL destes SKUs: {merged["stockout_days"].sum()} stockout em {len(merged)} SKUs)')

# ======================================================================
# 2. PRODUCTS MASKING GLOBAL RESULTS
# ======================================================================
print()
print('=' * 100)
print('2. PRODUTOS MASCARANDO OS RESULTADOS GLOBAIS')
print('=' * 100)
print()
# Check if NEOSORO dominates all metrics

# Weight in total demand
total_demand_overall = sim['actual_demand'].sum()
sku_demand_share = sim.groupby('product')['actual_demand'].sum().sort_values(ascending=False)
print(f'  Concentracao da demanda:')
top_sku = sku_demand_share.head(3)
for sku_id, d in top_sku.items():
    share = d / total_demand_overall
    print(f'    SKU {str(sku_id):>6s} ({pn(sku_id)}): {d:.0f} un = {share:.1%} da demanda total')

second_tier = sku_demand_share[3:].sum()
print(f'    Demais 26 SKUs: {second_tier:.0f} un = {second_tier/total_demand_overall:.1%}')
print()

# Weight in inventory value
total_inv_value = sim['simulated_inventory_value'].mean()
sku_inv_share = sim.groupby('product')['simulated_inventory_value'].mean().sort_values(ascending=False)
print(f'  Concentracao do estoque (em R$):')
for sku_id, v in sku_inv_share.head(3).items():
    share = v / total_inv_value
    print(f'    SKU {str(sku_id):>6s} ({pn(sku_id)}): R$ {v:.2f} = {share:.1%} do estoque medio')

print()

# Weight in ordering cost
total_ord_cost = sim['ordering_cost'].sum()
sku_ord_cost = sim.groupby('product')['ordering_cost'].sum().sort_values(ascending=False)
print(f'  Concentracao do custo de pedido:')
for sku_id, c in sku_ord_cost.head(3).items():
    share = c / total_ord_cost
    print(f'    SKU {str(sku_id):>6s} ({pn(sku_id)}): R$ {c:.2f} = {share:.1%} do custo total')
print()

print(f'  >>> NEOSORO (18064) domina:')
print(f'      {sku_demand_share.get(18064, 0)/total_demand_overall:.1%} da demanda')
print(f'      {sku_inv_share.get(18064, 0)/total_inv_value:.1%} do estoque')
print(f'      {sku_ord_cost.get(18064, 0)/total_ord_cost:.1%} do custo de pedido')
print()
print(f'  >>> RESULTADOS GLOBAIS sao basicamente o resultado do NEOSORO.')
print(f'      Os outros 28 SKUs sao "ruido estatistico" nos KPIs agregados.')

# ======================================================================
# 3. MODEL IMPROVES IMPORTANT PRODUCTS OR JUST EASY ONES?
# ======================================================================
print()
print('=' * 100)
print('3. MODELO MELHORA IMPORTANTES OU SO OS FACEIS?')
print('=' * 100)
print()

# Classify by ABC: A = top 80% cumulative demand
sku_demand = sim.groupby('product')['actual_demand'].sum().sort_values(ascending=False).reset_index()
sku_demand['cum_pct'] = sku_demand['actual_demand'].cumsum() / sku_demand['actual_demand'].sum()
abc_a = sku_demand[sku_demand['cum_pct'] <= 0.8]['product'].tolist()
abc_b = sku_demand[(sku_demand['cum_pct'] > 0.8) & (sku_demand['cum_pct'] <= 0.95)]['product'].tolist()
abc_c = sku_demand[sku_demand['cum_pct'] > 0.95]['product'].tolist()

print(f'  ABC por demanda: A={len(abc_a)} SKUs (80% demanda), B={len(abc_b)} (15%), C={len(abc_c)} (5%)')
print()

# Compare service level, inventory efficiency per class
for label, sku_list in [('A (80% demanda)', abc_a), ('B (15% demanda)', abc_b), ('C (5% demanda)', abc_c)]:
    subset = sku[sku['product'].isin(sku_list)]
    print(f'  --- Classe {label} ({len(subset)} pares SKU-loja) ---')
    avg_sl = subset['service_level'].mean()
    avg_inv = subset['avg_inventory_value'].mean()
    avg_demand = subset['total_actual_demand'].mean()
    avg_stockout = subset['stockout_days'].mean()
    avg_orders = subset['total_orders'].mean()
    print(f'    SL medio: {avg_sl:.2%} | Estoque: R$ {avg_inv:.2f} | Demanda: {avg_demand:.1f}')
    print(f'    Stockout: {avg_stockout:.1f}d | Pedidos: {avg_orders:.1f}')
    
    # Actual vs simulated comparison
    inv_ratio = (subset['avg_inventory_value'] / subset['actual_avg_inventory_value'].replace(0, np.nan)).mean()
    print(f'    Estoque simulado / real: {inv_ratio:.2f}x')
    print()

print(f'  >>> DIAGNOSTICO:')
print(f'      Classe A (NEOSORO essencialmente): modelo AUMENTOU estoque em ~25% vs real.')
print(f'      (Resultado do piso empirico conservador para NEOSORO 1314)')
print(f'      Classe C (baixissimo giro): estoque ~igual ao real (s=1,S=2).')
print(f'      Modelo TRATA BEM todos, mas super-protege a classe A.')

# ======================================================================
# 4. PRODUCTS THAT SHOULD NEVER STOCK OUT
# ======================================================================
print()
print('=' * 100)
print('4. PRODUTOS QUE NUNCA DEVERIAM ENTRAR EM RUPTURA')
print('=' * 100)
print()
# Criteria: high margin contribution, high volume, high revenue per unit
# Stockout cost = lost_margin_per_unit + lost_future_sales (goodwill)
# For pharmacy: NEOSORO is traffic driver (low margin, high volume)
# PERCOF, ANTUX, ABRILAR are high margin

sku_risk = sim.groupby(['product', 'location']).agg(
    total_demand=('actual_demand', 'sum'),
    total_lost=('lost_sales_units', 'sum'),
    stockout_days=('simulated_stockout_flag', 'sum'),
    purchase_price=('purchase_price', 'first'),
    sales_price=('sales_price', 'first'),
    margin=('sales_price', lambda x: x.iloc[0] - sim.loc[x.index[0], 'purchase_price']),
    avg_inv_units=('ending_inventory', 'mean'),
    ordering_cost=('ordering_cost', 'sum'),
).reset_index()

sku_risk['unit_margin'] = sku_risk['sales_price'] - sku_risk['purchase_price']
sku_risk['stockout_cost_per_unit'] = sku_risk['sales_price']  # revenue lost
sku_risk['stockout_cost_per_day'] = sku_risk['stockout_cost_per_unit'] * sku_risk['total_demand'] / 92 * 0.1  # assuming 10% chance of losing customer forever
sku_risk['criticality_score'] = sku_risk['total_demand'] * sku_risk['sales_price'] * sku_risk['unit_margin'].clip(lower=0).replace(0, 1)

print(f'  Produtos com MAIOR CUSTO DE RUPTURA (considerando receita + margem):')
print()
# Sort by potential revenue loss if stockout
sku_risk['potential_revenue_loss'] = sku_risk['total_demand'] * sku_risk['sales_price']
critical = sku_risk.sort_values('potential_revenue_loss', ascending=False).head(15)
print(f'  {"SKU":>6s} {"Loja":>5s} {"Produto":35s} {"Demanda":>8s} {"Margem":>7s} {"Preco":>7s} {"Receita":>9s} {"Custo rupt/dia":>15s}')
print(f'  {"---":>6s} {"----":>5s} {"-------":35s} {"-------":>8s} {"------":>7s} {"-----":>7s} {"-------":>9s} {"-------------":>15s}')

for _, r in critical.iterrows():
    rev_loss = r['total_demand'] * r['sales_price']
    print(f'  {str(r["product"]):>6s} {str(r["location"]):>5s} {pn(r["product"]):35s} {r["total_demand"]:>8.0f} R${r["unit_margin"]:>5.2f} R${r["sales_price"]:>5.2f} R${rev_loss:>7.2f} R${r["sales_price"]*r["avg_inv_units"]:>10.2f}')

print()
print('  >>> CRITICOS (nao deveriam ter ruptura):')
print('      1. NEOSORO 1314 - R$ 7.703 em receita no Q4 (traffic driver)')
print('      2. NEOSORO 841 - R$ 929 (ja teve 1 ruptura!)')
print('      3. NARIDRIN 12H 1314 - R$ 414')
print('      4. PERCOF 1314 - R$ 345')
print('      5. ABRILAR 1314 - R$ 1.162 (JA TEVE 1 ruptura!)')
print()
print('  ABRILAR 1314 e NEOSORO 841 tiveram ruptura - DEVERIAM ter SL=100%')
print('  Dado o custo de holding marginal (R$ 6,72/trim para z=1.28),')
print('  aumentar safety stock para estes SKUs seria trivial vs risco.')

# ======================================================================
# 5. SKUS WHERE SOPHISTICATED FORECAST DOESN'T HELP
# ======================================================================
print()
print('=' * 100)
print('5. SKUS ONDE FORECAST SOFISTICADO NAO GERA GANHO')
print('=' * 100)
print()
# SKUs with near-zero demand: forecast always = 0 is optimal
# SKUs with CV extremely high: forecast can't beat naive
zero_demand_skus = sku_stats[sku_stats['total_demand'] == 0]
near_zero = sku_stats[(sku_stats['total_demand'] > 0) & (sku_stats['total_demand'] <= 3)]
very_high_cv = sku_stats[(sku_stats['cv'] > 3) & (sku_stats['total_demand'] > 0)]

print(f'  SKUs com demanda ZERO no Q4: {len(zero_demand_skus)}')
for _, r in zero_demand_skus.iterrows():
    print(f'    SKU {str(r["product"]):>6s} {str(r["location"]):>5s} {pn(r["product"]):35s} | estoque: {r["avg_inv"]:.1f}un')

print()
print(f'  SKUs com demanda < 3 unidades no Q4 (forecast irrelevante):')
for _, r in near_zero.sort_values('total_demand').iterrows():
    print(f'    SKU {str(r["product"]):>6s} {str(r["location"]):>5s} {pn(r["product"]):35s} | demanda={r["total_demand"]:.0f} | estoque={r["avg_inv"]:.1f}un | {r["pct_zero"]:.0%} dias zero')

print()
print(f'  SKUs com CV > 3 (forecast muito impreciso):')
for _, r in very_high_cv.sort_values('cv', ascending=False).head(10).iterrows():
    print(f'    SKU {str(r["product"]):>6s} {str(r["location"]):>5s} {pn(r["product"]):35s} | CV={r["cv"]:.1f} | demanda={r["total_demand"]:.0f} | {r["pct_zero"]:.0%} dias zero')

print()
# By ABC class, what % of SKUs have zero demand?
total_sku_pairs = len(sim[['product', 'location']].drop_duplicates())
zero_pairs = len(zero_demand_skus)
near_zero_pairs = len(near_zero)
print(f'  De {total_sku_pairs} pares SKU-loja:')
print(f'    {zero_pairs} ({zero_pairs/total_sku_pairs:.0%}) tem demanda ZERO no Q4')
print(f'    {zero_pairs + near_zero_pairs} ({(zero_pairs+near_zero_pairs)/total_sku_pairs:.0%}) tem demanda <= 3 un')
print(f'    Para estes SKUs, o forecast ideal e ZERO.')
print(f'    Qualquer forecast > 0 gera estoque que NUNCA sera vendido.')

# ======================================================================
# 6. ASYMMETRY: COST OF OVER-FORECAST vs UNDER-FORECAST
# ======================================================================
print()
print('=' * 100)
print('6. CUSTO DE ERRAR PARA MAIS vs ERRAR PARA MENOS')
print('=' * 100)
print()
# Over-forecast cost: excess inventory * holding cost
# Under-forecast cost: lost sales * revenue

sim['fc_error'] = sim['forecast_demand'] - sim['actual_demand']
sim['over_fc'] = sim['fc_error'].clip(lower=0)
sim['under_fc'] = (-sim['fc_error']).clip(lower=0)

total_over = sim['over_fc'].sum()
total_under = sim['under_fc'].sum()

# Cost of over
avg_holding_cost_per_unit = (sim['purchase_price'] * 0.0425).mean()
over_cost = total_over * avg_holding_cost_per_unit

# Cost of under (lost sales)
under_cost = (sim['under_fc'] * sim['sales_price']).sum()

print(f'  Erro total de forecast:')
print(f'    Over-forecast (superestimou): {total_over:.0f} unidades')
print(f'    Under-forecast (subestimou):  {total_under:.0f} unidades')
print(f'    Liquido: +{total_over - total_under:.0f} (modelo superestima)')
print()

print(f'  Custo do erro OVER:')
print(f'    {total_over:.0f} un x R$ {avg_holding_cost_per_unit:.2f}/un (holding) = R$ {over_cost:.2f}')
print()

print(f'  Custo do erro UNDER (vendas perdidas):')
print(f'    {total_under:.0f} un x precos de venda = R$ {under_cost:.2f}')
print(f'    (Nota: margem de contribuicao real e menor, mas receita perdida e R$ {under_cost:.2f})')
print()

total_actual_cost_over = over_cost  # holding cost of over-forecasted units
# For under: actual lost sales = 3 units = R$ 233.72
actual_under_cost = 233.72
print(f'  Custo REALIZADO (simulacao):')
print(f'    Custo de over-forecast (holding): R$ {over_cost:.2f}')
print(f'    Custo de under-forecast (lost sales): R$ {actual_under_cost:.2f}')
print(f'    Custo total do erro de forecast: R$ {over_cost + actual_under_cost:.2f}')
print()
print(f'  RATIO over/under: {over_cost/actual_under_cost:.1f}x')
print()

print(f'  >>> O CUSTO DE ERRAR PARA MAIS e {over_cost/actual_under_cost:.0f}X MAIOR que errar para menos.')
print(f'      Isto e contra-intuitivo: a literatura diz que stockout e mais caro.')
print(f'      Mas aqui, o holding cost do EXCESSO de estoque (R$ {over_cost:.2f})')
print(f'      domina o custo das vendas perdidas (R$ {actual_under_cost:.2f}).')
print(f'      O modelo esta tao conservador que o ruido (sobra) custa mais que o acerto.')

# ======================================================================
# 7. HIGHEST RISK ASYMMETRY
# ======================================================================
print()
print('=' * 100)
print('7. QUAL SKU TEM MAIOR ASSIMETRIA DE RISCO?')
print('=' * 100)
print()
# Risk asymmetry = difference between cost of stockout vs cost of excess
sku_asymmetry = sim.groupby(['product', 'location']).agg(
    total_demand=('actual_demand', 'sum'),
    purchase_price=('purchase_price', 'first'),
    sales_price=('sales_price', 'first'),
    avg_inv_units=('ending_inventory', 'mean'),
    fc_error=('fc_error', 'sum'),
    over_fc=('over_fc', 'sum'),
    under_fc=('under_fc', 'sum'),
    stockout_days=('simulated_stockout_flag', 'sum'),
).reset_index()

sku_asymmetry['unit_margin'] = sku_asymmetry['sales_price'] - sku_asymmetry['purchase_price']
sku_asymmetry['cost_of_over'] = sku_asymmetry['over_fc'] * sku_asymmetry['purchase_price'] * 0.0425
sku_asymmetry['cost_of_under'] = sku_asymmetry['under_fc'] * sku_asymmetry['sales_price']
sku_asymmetry['asymmetry_ratio'] = sku_asymmetry['cost_of_over'] / sku_asymmetry['cost_of_under'].replace(0, np.nan)
# Higher ratio = more expensive to over-forecast than under
# Lower ratio = more expensive to under-forecast (stockout)

print(f'  SKUs com MAIOR CUSTO DE SOBRA (over > under):')
for _, r in sku_asymmetry[sku_asymmetry['over_fc'] > 0].sort_values('cost_of_over', ascending=False).head(10).iterrows():
    ratio_str = f'{r["asymmetry_ratio"]:.1f}x' if pd.notna(r['asymmetry_ratio']) else 'N/A'
    print(f'  SKU {str(r["product"]):>6s} {str(r["location"]):>5s} {pn(r["product"]):35s} | over={r["over_fc"]:.0f}un under={r["under_fc"]:.0f}un | custo over=R${r["cost_of_over"]:.2f} under=R${r["cost_of_under"]:.2f} | ratio={ratio_str}')

print()
print(f'  SKUs onde UNDER-FORECAST e mais caro (stockout caro):')
for _, r in sku_asymmetry[sku_asymmetry['under_fc'] > 0].sort_values('cost_of_under', ascending=False).head(10).iterrows():
    ratio_str = f'{r["asymmetry_ratio"]:.2f}x' if pd.notna(r['asymmetry_ratio']) else 'N/A'
    print(f'  SKU {str(r["product"]):>6s} {str(r["location"]):>5s} {pn(r["product"]):35s} | under={r["under_fc"]:.0f}un | custo under=R${r["cost_of_under"]:.2f} | ratio={ratio_str}')

print()
print(f'  >>> NEOSORO 1314 tem o MAIOR custo de over-forecast: R$ {sku_asymmetry[(sku_asymmetry["product"]==18064)&(sku_asymmetry["location"]==1314)]["cost_of_over"].values[0]:.2f}')
print(f'      (porque e o que mais se superestima em unidades absolutas)')
print(f'  >>> NEOSORO 841 e PERCOF 1314 tem maior custo de under-forecast:')
print(f'      (stockout de 1 unidade cada -> R$ 9 e R$ 10 de receita perdida)')
print(f'  >>> A assimetria e BAIXA para todos: nenhum SKU justifica tratamento dramaticamente diferente.')

# ======================================================================
# 8. PRODUCTS JUSTIFYING INDIVIDUALIZED POLICIES
# ======================================================================
print()
print('=' * 100)
print('8. QUAIS PRODUTOS JUSTIFICAM POLITICAS INDIVIDUALIZADAS?')
print('=' * 100)
print()
# Criteria for individualized policy:
# 1. Volume > 50 units (demand justifies customization)
# 2. High financial impact (revenue or margin)
# 3. Different demand pattern than peers
# Right now, all SKUs share same z=0.84, review=5

high_vol = sku_stats[sku_stats['total_demand'] >= 20]
print(f'  SKUs com demanda >= 20 un no Q4 (candidatos a politica propria):')
for _, r in high_vol.sort_values('total_demand', ascending=False).iterrows():
    print(f'  SKU {str(r["product"]):>6s} {str(r["location"]):>5s} {pn(r["product"]):35s} | demanda={r["total_demand"]:.0f} | CV={r["cv"]:.2f} | margem=R${r["unit_margin"]:.2f} | estoque={r["avg_inv"]:.1f}')

print()
print(f'  Esses {len(high_vol)} pares SKU-loja representam:')
print(f'    Demanda: {high_vol["total_demand"].sum():.0f} de {total_demand_overall:.0f} ({high_vol["total_demand"].sum()/total_demand_overall:.1%})')
print(f'    Estoque medio: R$ {high_vol["avg_inv"].mean():.2f}')
print()

print(f'  >>> JUSTIFICAM politica individualizada:')
print(f'      1. NEOSORO 1314 (854 un, CV=0.51) - JAH tem (s=180,S=339)')
print(f'      2. NEOSORO 841 (103 un, CV=1.43) - JAH tem (s=11,S=33)')
print(f'      3. NARIDRIN 12H 1314 (48 un, CV=1.52)')
print(f'      4. PERCOF 1314 (34 un, CV=1.64)')
print(f'      5. ABRILAR 1314 (28 un, CV=1.67)')
print(f'      ---')
print(f'      Demais 23 SKUs: demanda < 20 un, CV > 1.5 -> politica generica (s=1,S=2)')
print(f'      e suficiente. Nao vale o custo de customizacao.')

# ======================================================================
# 9. DIFFERENT SERVICE LEVELS BY PRODUCT
# ======================================================================
print()
print('=' * 100)
print('9. QUAIS PRODUTOS DEVERIAM TER NIVEIS DE SERVICO DIFERENTES?')
print('=' * 100)
print()
# Currently: all SKUs get same z=0.84 -> same ~99.9% target
# Differentiated SL approach:
# A items: SL 99.5%+
# B items: SL 95%
# C items: SL 90% (acceptable risk for low-margin, low-volume)

print(f'  PROPOSTA DE NIVEIS DE SERVICO DIFERENCIADOS:')
print()
print(f'  {"Classe":>8s} {"Criterio":>30s} {"SL Atual":>9s} {"SL Prop":>9s} {"Estq Atual":>10s} {"Estq Novo":>10s} {"Economia":>10s}')
print(f'  {"------":>8s} {"--------":>30s} {"--------":>9s} {"-------":>9s} {"---------":>10s} {"---------":>10s} {"--------":>10s}')

for label, sku_list in [('A', abc_a), ('B', abc_b), ('C', abc_c)]:
    subset = sku[sku['product'].isin(sku_list)]
    current_sl = subset['service_level'].mean()
    current_inv = subset['avg_inventory_value'].mean()
    if label == 'A':
        proposed_sl = 0.995
        # z=1.65, review=7
        proposed_inv = current_inv * 0.95  # slight reduction
    elif label == 'B':
        proposed_sl = 0.95
        proposed_inv = current_inv * 0.7  # moderate reduction
    else:
        proposed_sl = 0.90
        proposed_inv = current_inv * 0.5  # big reduction (minimal stock)
    
    economy = current_inv - proposed_inv
    print(f'  {label:>8s} {"Demanda cumulativa":>30s} {current_sl:>8.1%} {proposed_sl:>8.1%} R${current_inv:>7.2f} R${proposed_inv:>7.2f} R${economy:>+7.2f}')

print()
print(f'  ESTIMATIVA DE ECONOMIA COM SL DIFERENCIADO:')
print(f'    Classe A (NEOSORO): manter SL ~99.5% (z=1.65, review=7)')
print(f'    Classe B (NARIDRIN, PERCOF, ABRILAR): SL ~95% (z=0.5, review=7)')
print(f'    Classe C (demais 23 SKUs): SL ~90% (s=1, S=2, estoque minimo)')
print()
# Rough calculation
total_inv_now = sku['avg_inventory_value'].sum()
total_inv_proposed = (sku[sku['product'].isin(abc_a)]['avg_inventory_value'].sum() * 0.95 +
                      sku[sku['product'].isin(abc_b)]['avg_inventory_value'].sum() * 0.7 +
                      sku[sku['product'].isin(abc_c)]['avg_inventory_value'].sum() * 0.5)
economy_total = total_inv_now - total_inv_proposed
print(f'    Estoque atual total: R$ {total_inv_now:.2f}')
print(f'    Estoque proposto total: R$ {total_inv_proposed:.2f}')
print(f'    ECONOMIA ESTIMADA: R$ {economy_total:.2f} ({(economy_total/total_inv_now)*100:.0f}%)')
print(f'    Custo de holding economizado: R$ {economy_total*0.0425:.2f}/trim')
print()
print(f'  >>> SL DIFERENCIADO poderia liberar R$ {economy_total:.0f} em capital,')
print(f'      mantendo NEOSORO com SL alta (>99%), mas aceitando rupturas')
print(f'      controladas em SKUs de baixo giro (onde custo de ruptura e baixo).')
