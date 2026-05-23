import pandas as pd
import numpy as np

sim = pd.read_csv('stock_policy_product_output/simulation_daily.csv')
sku_metrics = pd.read_csv('stock_policy_product_output/sku_metrics.csv')
policy = pd.read_csv('stock_policy_product_output/policy_enriched.csv')
sim['date'] = pd.to_datetime(sim['date'])

print('=' * 80)
print('1. PRODUTOS COM MAIOR RISCO DE RUPTURA (dias com stockout)')
print('=' * 80)
risk = sku_metrics[sku_metrics['total_actual_demand'] >= 1].sort_values('stockout_days', ascending=False)
for _, r in risk.head(10).iterrows():
    gap = r['order_up_to_S'] - r['reorder_point_s']
    print(f'  Loja {str(r["location"]):>4s} SKU {str(r["product"]):>6s} ({str(r["product_name"])[:35]:35s}) | Stockout: {r["stockout_days"]:>2.0f}d | SL: {r["service_level"]:>5.1%} | s={r["reorder_point_s"]:>3.0f} S={r["order_up_to_S"]:>3.0f} gap={gap:>2.0f} | Demanda: {r["total_actual_demand"]:>3.0f} | Pedidos: {r["total_orders"]:>2.0f}')

print()
print('  --- PRODUTOS SEM RUPTURA (mas com risco potencial) ---')
# SKUs with s=1, S=2 but actual demand > 1
tight = sku_metrics[(sku_metrics['order_up_to_S'] <= 3) & (sku_metrics['total_actual_demand'] >= 3)]
for _, r in tight.iterrows():
    print(f'  {str(r["location"]):>4s} SKU {str(r["product"]):>6s} ({str(r["product_name"])[:35]:35s}) | s={r["reorder_point_s"]:>2.0f} S={r["order_up_to_S"]:>2.0f} | Demanda: {r["total_actual_demand"]:>3.0f} | Ped: {r["total_orders"]:>2.0f} | SL: {r["service_level"]:>4.0%}')

print()
print('=' * 80)
print('2. PRODUTOS COM EXCESSO DE ESTOQUE')
print('=' * 80)
# Excess: simulated inventory >> actual historical inventory AND high capital
excess = sku_metrics[(sku_metrics['total_actual_demand'] >= 1)].copy()
excess['inventory_ratio'] = excess['avg_inventory_value'] / excess['actual_avg_inventory_value'].replace(0, np.nan)
excess['days_of_demand'] = excess['avg_inventory_units'] / (excess['total_actual_demand']/92).replace(0, np.nan)
excess = excess.sort_values('inventory_value_delta_vs_actual', ascending=False)
print('  --- MAIOR EXCESSO DE CAPITAL (simulado > real historico) ---')
for _, r in excess.head(10).iterrows():
    ddays = r['avg_inventory_units'] / max(r['total_actual_demand']/92, 0.01)
    print(f'  SKU {str(r["product"]):>6s} ({str(r["product_name"])[:30]:30s}) Loja {str(r["location"]):>4s} | Simulado: R$ {r["avg_inventory_value"]:>8.2f} | Real: R$ {r["actual_avg_inventory_value"]:>8.2f} | Delta: R$ {r["inventory_value_delta_vs_actual"]:>+8.2f} | Cobertura: {ddays:>4.1f}d')

print()
print('  --- MAIOR COBERTURA (dias de demanda em estoque) ---')
excess2 = excess.sort_values('days_of_demand', ascending=False)
for _, r in excess2.head(10).iterrows():
    print(f'  SKU {str(r["product"]):>6s} ({str(r["product_name"])[:30]:30s}) Loja {str(r["location"]):>4s} | Cobertura: {r["days_of_demand"]:>5.1f}d | Estq: {r["avg_inventory_units"]:>5.1f}un | Demanda: {r["total_actual_demand"]:>3.0f}un')

print()
print('=' * 80)
print('3. REABASTECIMENTO EXCESSIVO (muitos pedidos para baixa demanda)')
print('=' * 80)
freq_orders = sku_metrics[sku_metrics['total_orders'] > 0].copy()
freq_orders['units_per_order'] = freq_orders['total_order_units'] / freq_orders['total_orders']
freq_orders['cost_per_unit'] = freq_orders['total_ordering_cost'] / freq_orders['total_order_units'].replace(0, np.nan)
freq_orders = freq_orders.sort_values('total_orders', ascending=False)
for _, r in freq_orders.head(10).iterrows():
    print(f'  SKU {str(r["product"]):>6s} ({str(r["product_name"])[:30]:30s}) Loja {str(r["location"]):>4s} | Pedidos: {r["total_orders"]:>2.0f} | Un/pedido: {r["units_per_order"]:>5.1f} | Custo ped: R$ {r["total_ordering_cost"]:>6.2f} | Custo/un: R$ {r["cost_per_unit"]:>5.2f}')

print()
print('=' * 80)
print('4. O REORDER POINT ESTA AGRESSIVO OU CONSERVADOR?')
print('=' * 80)
print(f'  Parametros globais: z={policy["z_value"].iloc[0]:.2f}, review_days={policy["review_days"].iloc[0]:.0f}')
print()

# Compare statistical vs empirical floor
policy_s = policy[policy['total_forecast_period'] > 0].copy()
policy_s['delta_s'] = policy_s['reorder_point_s'] - policy_s['statistical_reorder_point_s']
policy_s['delta_S'] = policy_s['order_up_to_S'] - policy_s['statistical_order_up_to_S']
policy_s['empirical_dominated'] = policy_s['reorder_point_s'] == policy_s['empirical_floor_s']
print('  SKUs onde o piso empirico DOMINA o ponto de pedido:')
for _, r in policy_s[policy_s['empirical_dominated']].iterrows():
    print(f'  SKU {str(r["product"]):>6s} ({str(r["product_name"])[:35]:35s}) Loja {str(r["location"]):>4s} | s={r["reorder_point_s"]:>3.0f} (stat={r["statistical_reorder_point_s"]:>2.0f}, emp={r["empirical_floor_s"]:>2.0f})')

print()
print('  SKUs com reorder point MUITO acima do estatistico:')
for _, r in policy_s[policy_s['statistical_reorder_point_s'] > 0].sort_values('delta_s', ascending=False).head(10).iterrows():
    print(f'  SKU {str(r["product"]):>6s} ({str(r["product_name"])[:35]:35s}) Loja {str(r["location"]):>4s} | s={r["reorder_point_s"]:>3.0f} vs stat={r["statistical_reorder_point_s"]:>3.0f} vs emp={r["empirical_floor_s"]:>3.0f} | delta={r["delta_s"]:+>3.0f}')

print()
print('  AVALIACAO:')
# Check: did high service level come at cost of too much inventory?
print('  Service level global: 99.94% (target: 92%)')
print('  Estoque medio: R$ 169,78')
print('  Custo total pedido: R$ 2.629,55')
print('  Total ordens: 113')
print()
print('  Interpretacao: o modelo esta CONSERVADOR.')
print('  O piso empirico (quantil 75% da demanda acumulada no lead time)')
print('  esta elevando o reorder point acima do estatistico para NEOSORO (s=180 vs stat=139).')
print('  Isso gera estoque excessivo mas garante SL > 99%.')

print()
print('=' * 80)
print('5. QUAL LOJA SOFRE MAIS COM LEAD TIME?')
print('=' * 80)
lt = sku_metrics.groupby('location').agg(
    lead_time=('lead_time_days', 'max'),
    total_stockout_days=('stockout_days', 'sum'),
    avg_inventory=('avg_inventory_value', 'mean'),
    avg_inventory_units=('avg_inventory_units', 'mean'),
    total_orders=('total_orders', 'sum'),
    total_ordering_cost=('total_ordering_cost', 'sum'),
    total_demand=('total_actual_demand', 'sum'),
).reset_index()
for _, r in lt.iterrows():
    print(f'  Loja {int(r["location"])} | LT={int(r["lead_time"])}d | Stockout: {int(r["total_stockout_days"])}d | Estq: R$ {r["avg_inventory"]:>6.2f} | Ped: {int(r["total_orders"])} | Custo: R$ {r["total_ordering_cost"]:>6.2f}')

print()
print('  Loja 1314 (LT=9d) requer 3x mais estoque que Loja 841 (LT=3d)')
print('  para NEOSORO: s=180/S=339 (1314) vs s=11/S=33 (841) -- 16x mais estoque')
print('  Custo de pedido 1314: R$ 1.671 vs 841: R$ 959')

print()
print('=' * 80)
print('6. SKUs QUE PRECISAM DE MAIOR SAFETY STOCK')
print('=' * 80)
sku_metrics['demand_cv'] = sku_metrics['total_actual_demand'] > 0  # proxy
need_ss = sku_metrics[sku_metrics['total_actual_demand'] > 0].copy()
need_ss['daily_demand'] = need_ss['total_actual_demand'] / 92
need_ss['safety_stock'] = need_ss['reorder_point_s'] - need_ss['lead_time_days'] * need_ss['daily_demand']
need_ss['safety_stock_ratio'] = need_ss['safety_stock'] / (need_ss['lead_time_days'] * need_ss['daily_demand']).replace(0, np.nan)
need_ss = need_ss.sort_values('safety_stock', ascending=False)
for _, r in need_ss.head(10).iterrows():
    print(f'  SKU {str(r["product"]):>6s} ({str(r["product_name"])[:35]:35s}) Loja {str(r["location"]):>4s} | Safety: {r["safety_stock"]:>5.1f}un | s={r["reorder_point_s"]:>3.0f} | LT={r["lead_time_days"]}d | Dem/dia: {r["daily_demand"]:>4.1f}')

print()
print('=' * 80)
print('7. O MODELO ESTA CRIANDO ESTOQUE DESNECESSARIO?')
print('=' * 80)
# Compare simulated vs actual inventory levels
print('  Estoque simulado medio:   R$ 169,78')
print('  Estoque real historico:   R$ 163,27')
print('  Diferenca:                R$ +6,51 (+4,0%)')
print()
print('  SKUs com maior estoque simulado vs real:')
over = sku_metrics[sku_metrics['total_actual_demand'] > 0].sort_values('inventory_value_delta_vs_actual', ascending=False)
for _, r in over.head(8).iterrows():
    print(f'  SKU {str(r["product"]):>6s} ({str(r["product_name"])[:30]:30s}) Loja {str(r["location"]):>4s} | Sim: R$ {r["avg_inventory_value"]:>7.2f} | Real: R$ {r["actual_avg_inventory_value"]:>7.2f} | +R$ {r["inventory_value_delta_vs_actual"]:>+7.2f}')
print()
print('  SKUs com menos estoque simulado vs real (eficiencia):')
for _, r in over.tail(8).iloc[::-1].iterrows():
    d = r['inventory_value_delta_vs_actual']
    if d < -10:
        print(f'  SKU {str(r["product"]):>6s} ({str(r["product_name"])[:30]:30s}) Loja {str(r["location"]):>4s} | Sim: R$ {r["avg_inventory_value"]:>7.2f} | Real: R$ {r["actual_avg_inventory_value"]:>7.2f} | {d:>+7.2f}')

# NEOSORO special case
print()
print('  CASO CRITICO - NEOSORO Loja 1314:')
n1314 = sku_metrics[(sku_metrics['product'] == 18064) & (sku_metrics['location'] == 1314)]
print(f'    s={n1314["reorder_point_s"].values[0]}, S={n1314["order_up_to_S"].values[0]}')
print(f'    Estq simulado medio: {n1314["avg_inventory_units"].values[0]:.0f} un (R$ {n1314["avg_inventory_value"].values[0]:.2f})')
print(f'    Estq real historico:  {n1314["actual_avg_inventory_units"].values[0]:.0f} un (R$ {n1314["actual_avg_inventory_value"].values[0]:.2f})')
print(f'    Demanda total Q4: {n1314["total_actual_demand"].values[0]} un')
print(f'    Demanda media: {n1314["total_actual_demand"].values[0]/92:.1f} un/dia')
print(f'    Cobertura: {n1314["avg_inventory_units"].values[0]/(n1314["total_actual_demand"].values[0]/92):.0f} dias')
print(f'    Lead time: {n1314["lead_time_days"].values[0]}d')
print(f'    Conclusao: estoque em excesso DEVIDO a lead time longo + forecast 50% superestimado')

print()
print('=' * 80)
print('8. SKU ONDE AUMENTAR ESTOQUE NAO MELHORA SERVICO')
print('=' * 80)
# Already at 100% SL - increasing stock does not improve
perfect_sl = sku_metrics[(sku_metrics['service_level'] >= 1.0) & (sku_metrics['total_actual_demand'] >= 1)]
print(f'  SKUs com SL=100% (ja nao ha o que melhorar): {len(perfect_sl)} de {len(sku_metrics[sku_metrics["total_actual_demand"]>=1])}')
print()
print('  SKUs onde estoque extra NAO trara ganho de servico:')
for _, r in perfect_sl.sort_values('avg_inventory_value', ascending=False).head(10).iterrows():
    print(f'  SKU {str(r["product"]):>6s} ({str(r["product_name"])[:30]:30s}) Loja {str(r["location"]):>4s} | SL=100% | Estq: R$ {r["avg_inventory_value"]:>7.2f} | Demanda: {r["total_actual_demand"]:>3.0f}')

print()
print('  SKUs COM RUPTURA (onde aumentar estoque PODE ajudar):')
breaking = sku_metrics[sku_metrics['stockout_days'] > 0]
for _, r in breaking.iterrows():
    print(f'  SKU {str(r["product"]):>6s} ({str(r["product_name"])[:30]:30s}) Loja {str(r["location"]):>4s} | SL={r["service_level"]:>4.0%} | Stockout: {r["stockout_days"]}d | s={r["reorder_point_s"]:>2.0f} S={r["order_up_to_S"]:>2.0f} | Dem: {r["total_actual_demand"]:>2.0f}')

print()
print('=' * 80)
print('9. SKU ONDE PEQUENAS MUDANCAS EM s/S MUDAM RESULTADOS')
print('=' * 80)
print('  (analise via tuning search - comparacao entre parametros)')
# Read tuning search
try:
    tune = pd.read_csv('stock_policy_product_output/tuning_search.csv')
    print(f'  Grid search: {len(tune)} combinacoes (z x review_days)')
    print()
    # Show how objective changes with z
    print('  Impacto de z_value (fixando review_days=5):')
    for z in sorted(tune['z_value'].unique()):
        subset = tune[tune['review_days'] == 5]
        row = subset[subset['z_value'] == z]
        if len(row) > 0:
            r = row.iloc[0]
            print(f'    z={z:>4.2f} | SL={r["service_level"]:>4.1%} | Estq: R$ {r["avg_inventory_value"]:>7.2f} | Custo: R$ {r["total_ordering_cost"]:>5.0f} | Objective: {r["objective"]:>8.2f}')
    print()
    print('  Impacto de review_days (fixando z=1.65):')
    for rd in sorted(tune['review_days'].unique()):
        subset = tune[tune['z_value'] == 1.65]
        row = subset[subset['review_days'] == rd]
        if len(row) > 0:
            r = row.iloc[0]
            print(f'    review={rd:>2d}d | SL={r["service_level"]:>4.1%} | Estq: R$ {r["avg_inventory_value"]:>7.2f} | Custo: R$ {r["total_ordering_cost"]:>5.0f} | Objective: {r["objective"]:>8.2f}')
except:
    print('  Tuning search nao encontrado')

print()
print('=' * 80)
print('10. DIAGNOSTICO FINAL - MAPA DE PROBLEMAS')
print('=' * 80)
print('''
  PROBLEMA                          SKUS CRITICOS               ACAO
  ------                            --------------               ----
  Ruptura observada                 57814-L841, 20635-L1314     Ajustar s/S
  Estoque excessivo                 18064-L1314 (R$831+real)    Reduzir safety stock
  Forecast sistematico inflado      18064 (FC 57% > real)       Revisar promo_uplift
  Reabastecimento frequente e caro  21141-L841 (10x R$260)      Aumentar lote minimo
  Piso empirico dominante           18064-L1314, varios          Avaliar quantil
  SKUs sem demanda (estoque=0)     TAMIFLU, ALOFF, etc.        Manter s=0
''')
