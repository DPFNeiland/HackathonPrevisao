import pandas as pd
import numpy as np

base = 'data'
prod = pd.read_csv(f'{base}/2_produtos_locais.csv', sep=';')
vendas = pd.read_csv(f'{base}/8_inventario_venda.csv', sep=';')
saldo = pd.read_csv(f'{base}/7_saldo.csv', sep=';')

lojas = prod[prod['location'].str.contains('LOJA')].copy()
sales = vendas[vendas['type'] == 'SALE'].copy()
sales['qty_pos'] = -sales['quantity']
sales['revenue'] = -sales['value']

total_days = pd.to_datetime(vendas['date']).nunique()

sku_sales = sales.groupby('product').agg(
    total_qty=('qty_pos', 'sum'),
    total_revenue=('revenue', 'sum'),
    days_with_sale=('date', 'nunique')
).reset_index()

sku_loja_sales = sales.groupby(['product', 'location']).agg(
    total_qty=('qty_pos', 'sum'),
    total_revenue=('revenue', 'sum')
).reset_index()
sku_loja_sales['location'] = sku_loja_sales['location'].astype(int)

loja_prod = lojas[['product', 'product_name', 'purchase_price', 'sales_price', 'cost_of_ordering']].copy()
loja_prod['location_code'] = lojas['location'].str.extract(r'(\d+)').astype(int)

sku_loja_full = sku_loja_sales.merge(
    loja_prod, left_on=['product', 'location'], right_on=['product', 'location_code'], how='left'
)
sku_loja_full['unit_margin'] = (sku_loja_full['sales_price'] - sku_loja_full['purchase_price']).clip(lower=0)
sku_loja_full['total_margin'] = sku_loja_full['unit_margin'] * sku_loja_full['total_qty']

sku_tot = sku_loja_full.groupby(['product', 'product_name']).agg(
    total_qty=('total_qty', 'sum'),
    total_revenue=('total_revenue', 'sum')
).reset_index()
sku_tot['pct_qty'] = sku_tot['total_qty'] / sku_tot['total_qty'].sum() * 100
sku_tot['pct_rev'] = sku_tot['total_revenue'] / sku_tot['total_revenue'].sum() * 100
sku_tot = sku_tot.sort_values('total_qty', ascending=False)

print('=' * 80)
print('1. SKU QUE DOMINA O VOLUME TOTAL DA CATEGORIA')
print('=' * 80)
for _, r in sku_tot.head(10).iterrows():
    print(f'  SKU {r["product"]:>6} ({str(r["product_name"])[:40]:40s}) | Qtd: {r["total_qty"]:>5} ({r["pct_qty"]:5.1f}%) | Rec: R$ {r["total_revenue"]:>8.2f} ({r["pct_rev"]:5.1f}%)')
neosoro = sku_tot[sku_tot['product'] == 18064]
print(f'\n  >> SKU 18064 (NEOSORO) = {neosoro["pct_qty"].values[0]:.1f}% do volume, {neosoro["pct_rev"].values[0]:.1f}% da receita')

print()
print('=' * 80)
print('2. FREQUENCIA DE VENDAS (dias com venda)')
print('=' * 80)
freq = sku_sales.merge(sku_tot[['product', 'product_name']], on='product').sort_values('days_with_sale', ascending=False)
freq['pct_days'] = freq['days_with_sale'] / total_days * 100
for _, r in freq.head(10).iterrows():
    print(f'  SKU {r["product"]:>6} ({str(r["product_name"])[:40]:40s}) | {r["days_with_sale"]:>4}d ({r["pct_days"]:4.1f}%) | {r["total_qty"]:>5} un vendidas')

print()
print('=' * 80)
print('3. PERCENTUAL DO FATURAMENTO (RECEITA)')
print('=' * 80)
sku_rev = sku_tot.sort_values('total_revenue', ascending=False)
sku_rev['cum_pct'] = sku_rev['total_revenue'].cumsum() / sku_rev['total_revenue'].sum() * 100
for _, r in sku_rev.head(10).iterrows():
    print(f'  SKU {r["product"]:>6} ({str(r["product_name"])[:40]:40s}) | R$ {r["total_revenue"]:>8.2f} ({r["pct_rev"]:5.1f}%) | Acum: {r["cum_pct"]:5.1f}%')

print()
print('=' * 80)
print('4. CONCENTRACAO DE MARGEM BRUTA')
print('=' * 80)
sku_marg = sku_loja_full.groupby(['product', 'product_name']).agg(
    total_margin=('total_margin', 'sum'),
    avg_unit_margin=('unit_margin', 'mean'),
    total_qty=('total_qty', 'sum')
).reset_index().sort_values('total_margin', ascending=False)
sku_marg['pct_m'] = sku_marg['total_margin'] / sku_marg['total_margin'].sum() * 100
sku_marg['cum_m'] = sku_marg['pct_m'].cumsum()
for _, r in sku_marg.head(10).iterrows():
    print(f'  SKU {r["product"]:>6} ({str(r["product_name"])[:40]:40s}) | Margem tot: R$ {r["total_margin"]:>8.2f} ({r["pct_m"]:5.1f}%) | Margem un: R$ {r["avg_unit_margin"]:>5.2f}')

print()
print('=' * 80)
print('5. GIRO DE ESTOQUE (demanda / estoque medio)')
print('=' * 80)
avg_bal = saldo.groupby('product').agg(avg_balance=('balance', 'mean')).reset_index()
turn = sku_tot[['product', 'product_name', 'total_qty']].merge(avg_bal, on='product')
turn['turnover'] = turn['total_qty'] / turn['avg_balance'].replace(0, np.nan)
turn = turn.sort_values('turnover', ascending=False)
for _, r in turn.head(10).iterrows():
    print(f'  SKU {r["product"]:>6} ({str(r["product_name"])[:40]:40s}) | Giro: {r["turnover"]:>5.1f}x | Vendas: {r["total_qty"]:>5} un | Estq medio: {r["avg_balance"]:>5.1f}')

print()
print('=' * 80)
print('6. IMPACTO FINANCEIRO EM CASO DE RUPTURA (R$/dia perdido)')
print('=' * 80)
sku_loja_full['avg_daily_demand'] = sku_loja_full['total_qty'] / total_days
sku_loja_full['rupture_cost_per_day'] = sku_loja_full['sales_price'].fillna(0) * sku_loja_full['avg_daily_demand']
impact = sku_loja_full.groupby(['product', 'product_name']).agg(
    rupture_cost_per_day=('rupture_cost_per_day', 'sum'),
    total_revenue=('total_revenue', 'sum')
).reset_index().sort_values('rupture_cost_per_day', ascending=False)
for _, r in impact.head(10).iterrows():
    print(f'  SKU {r["product"]:>6} ({str(r["product_name"])[:40]:40s}) | R$ {r["rupture_cost_per_day"]:>6.2f}/dia | Receita total: R$ {r["total_revenue"]:>8.2f}')

print()
print('=' * 80)
print('7. RELEVANCIA OPERACIONAL (custo ruptura + custo pedido)')
print('=' * 80)
op = impact.merge(
    loja_prod.groupby('product').agg(avg_ordering=('cost_of_ordering', 'mean')).reset_index(),
    on='product'
)
op['op_score'] = op['rupture_cost_per_day'] + op['avg_ordering']
op = op.sort_values('op_score', ascending=False)
for _, r in op.head(10).iterrows():
    print(f'  SKU {r["product"]:>6} ({str(r["product_name"])[:40]:40s}) | Score: {r["op_score"]:>6.2f} | Custo ped: R$ {r["avg_ordering"]:>5.2f} | Custo rupt: R$ {r["rupture_cost_per_day"]:>6.2f}')

print()
print('=' * 80)
print('8. SENSIBILIDADE A INDISPONIBILIDADE (cobertura em dias)')
print('=' * 80)
cov = turn.merge(impact[['product']], on='product')
cov = cov.merge(
    sku_loja_full.groupby('product').agg(avg_daily_demand=('avg_daily_demand', 'sum')).reset_index(),
    on='product'
)
cov['coverage_days'] = cov['avg_balance'] / cov['avg_daily_demand'].replace(0, np.nan)
cov = cov.sort_values('coverage_days')
for _, r in cov.head(10).iterrows():
    print(f'  SKU {r["product"]:>6} ({str(r["product_name"])[:40]:40s}) | Cobertura: {r["coverage_days"]:>5.1f}d | Estq medio: {r["avg_balance"]:>5.1f} | Dem dia: {r["avg_daily_demand"]:>4.2f}')

print()
print('=' * 80)
print('9. CUSTO DE RUPTURA IMPLICITO (top 10)')
print('=' * 80)
for _, r in impact.head(10).iterrows():
    print(f'  SKU {r["product"]:>6} ({str(r["product_name"])[:40]:40s}) | R$ {r["rupture_cost_per_day"]:>6.2f}/dia de ruptura')

print()
print('=' * 80)
print('10. RECOMENDACAO: POLITICAS MAIS CONSERVADORAS')
print('=' * 80)
print('''
Criterios (ponderados):
  - 30%: Custo de ruptura/dia (perda financeira)
  - 25%: Margem total (produto estrategico)
  - 20%: Cobertura baixa = risco alto (invertido)
  - 10%: Custo de pedido (repor e caro)
  - 15%: Frequencia de vendas (giro)
''')

comp = impact[['product', 'product_name', 'rupture_cost_per_day', 'total_revenue']].copy()
comp = comp.merge(sku_marg[['product', 'total_margin']], on='product')
comp = comp.merge(cov[['product', 'coverage_days']], on='product')
comp = comp.merge(op[['product', 'avg_ordering']], on='product')
comp = comp.merge(freq[['product', 'days_with_sale']], on='product')

# Manual z-score
for col in ['rupture_cost_per_day', 'total_margin', 'avg_ordering', 'days_with_sale']:
    m, s = comp[col].mean(), comp[col].std()
    comp[col + '_z'] = (comp[col] - m) / s if s > 0 else 0
m_cov, s_cov = comp['coverage_days'].mean(), comp['coverage_days'].std()
comp['coverage_days_z'] = -(comp['coverage_days'] - m_cov) / s_cov if s_cov > 0 else 0
comp['score'] = (comp['rupture_cost_per_day_z'] * 0.30 + comp['total_margin_z'] * 0.25 +
                  comp['coverage_days_z'] * 0.20 + comp['avg_ordering_z'] * 0.10 + comp['days_with_sale_z'] * 0.15)
comp = comp.sort_values('score', ascending=False)
for i, (_, r) in enumerate(comp.head(10).iterrows()):
    print(f'  #{i + 1:>2} SKU {r["product"]:>6} ({str(r["product_name"])[:40]:40s}) | Score: {r["score"]:>5.2f}')
