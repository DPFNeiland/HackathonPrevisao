import pandas as pd
import numpy as np
from datetime import datetime, timedelta

base = 'data'
prod = pd.read_csv(f'{base}/2_produtos_locais.csv', sep=';')
vendas = pd.read_csv(f'{base}/8_inventario_venda.csv', sep=';')
campanhas = pd.read_csv(f'{base}/4_campanhas.csv', sep=';', dtype={'start_date': str, 'end_date': str})
prod_camp = pd.read_csv(f'{base}/5_produtos_locais_campanhas.csv', sep=';')

# Clean campaign dates (remove tabs)
campanhas['start_date'] = campanhas['start_date'].str.strip()
campanhas['end_date'] = campanhas['end_date'].str.strip()

# Filter SALES
sales = vendas[vendas['type'] == 'SALE'].copy()
sales['qty_pos'] = -sales['quantity']
sales['date'] = pd.to_datetime(sales['date'])

# Store-level products
lojas = prod[prod['location'].str.contains('LOJA')].copy()
lojas['location_code'] = lojas['location'].str.extract(r'(\d+)').astype(int)

# Build daily sales per product-location
daily = sales.groupby(['product', 'location', 'date']).agg(daily_qty=('qty_pos', 'sum')).reset_index()
daily['location'] = daily['location'].astype(int)
daily['dow'] = daily['date'].dt.dayofweek  # 0=Mon, 6=Sun
daily['month'] = daily['date'].dt.month
daily['week'] = daily['date'].dt.isocalendar().week.astype(int)
daily['year'] = daily['date'].dt.year

# ---- Load campaign data ----
# product_campaign links product+location to campaign
prod_camp['location'] = prod_camp['location'].fillna('0').astype(str).str.strip()
campanhas['start_date'] = pd.to_datetime(campanhas['start_date'], errors='coerce')
campanhas['end_date'] = pd.to_datetime(campanhas['end_date'], errors='coerce')

# For each sale, flag if it was during a campaign for that product+location
# Merge product_campaign with campaign dates
pc = prod_camp.merge(campanhas, on='campaign', how='left')
pc['location'] = pc['location'].astype(int)

# Join to daily sales
daily['is_promo'] = 0
daily['campaign_type'] = ''

for _, row in pc.iterrows():
    mask = (
        (daily['product'] == row['product']) &
        (daily['location'] == row['location']) &
        (daily['date'] >= row['start_date']) &
        (daily['date'] <= row['end_date'])
    )
    daily.loc[mask, 'is_promo'] = 1
    daily.loc[mask & (daily['campaign_type'] == ''), 'campaign_type'] = str(row.get('type', ''))

# ---- 1. UPLIFT MEDIO DURANTE CAMPANHAS ----
print('='*80)
print('1. UPLIFT MEDIO DURANTE CAMPANHAS (por SKU)')
print('='*80)

def calc_uplift(df):
    """Compare avg daily sales in promo vs non-promo"""
    promo = df[df['is_promo'] == 1]['daily_qty'].mean()
    normal = df[df['is_promo'] == 0]['daily_qty'].mean()
    if normal > 0 and promo > 0:
        uplift = (promo - normal) / normal * 100
    else:
        uplift = 0
    return pd.Series({
        'avg_promo': promo,
        'avg_normal': normal,
        'uplift_pct': uplift,
        'promo_days': df['is_promo'].sum(),
        'normal_days': (df['is_promo'] == 0).sum()
    })

uplift = daily.groupby('product').apply(calc_uplift).reset_index()

# Add product names
names = lojas[['product', 'product_name']].drop_duplicates('product')
uplift = uplift.merge(names, on='product')

uplift_sorted = uplift.sort_values('uplift_pct', ascending=False)
for _, r in uplift_sorted.head(15).iterrows():
    if r['promo_days'] >= 5:
        print(f'  SKU {r["product"]:>6} ({str(r["product_name"])[:40]:40s}) | Uplift: {r["uplift_pct"]:>+6.1f}% | Promo: {r["avg_promo"]:>5.2f}/d | Normal: {r["avg_normal"]:>5.2f}/d | {r["promo_days"]}d promocao')

# Also show negative/small uplift
print()
print('  --- SKUs com menor uplift ou efeito negativo ---')
uplift_neg = uplift.sort_values('uplift_pct')
for _, r in uplift_neg.head(10).iterrows():
    if r['promo_days'] >= 5:
        print(f'  SKU {r["product"]:>6} ({str(r["product_name"])[:40]:40s}) | Uplift: {r["uplift_pct"]:>+6.1f}% | Promo: {r["avg_promo"]:>5.2f}/d | Normal: {r["avg_normal"]:>5.2f}/d')

# Aggregate overall
overall_normal = daily[daily['is_promo'] == 0]['daily_qty'].mean()
overall_promo = daily[daily['is_promo'] == 1]['daily_qty'].mean()
overall_uplift = (overall_promo - overall_normal) / overall_normal * 100
print(f'\n  >> UPLIFT MEDIO GERAL: {overall_uplift:+.1f}% (promo: {overall_promo:.2f}/d vs normal: {overall_normal:.2f}/d)')

# Uplift by campaign type
print()
print('  --- Uplift por tipo de campanha ---')
for ctype in daily['campaign_type'].unique():
    if ctype == '':
        continue
    p = daily[daily['campaign_type'] == ctype]['daily_qty'].mean()
    n = daily[daily['is_promo'] == 0]['daily_qty'].mean()
    if n > 0:
        print(f'  {ctype:20s} | Media: {p:>5.2f}/d | Uplift vs normal: {((p-n)/n*100):+.1f}%')

# ---- 2. EFETO POS-PROMOCAO ----
print()
print('='*80)
print('2. EFEITO POS-PROMOCAO (demanda nos dias apos campanha)')
print('='*80)

# We need to identify periods: before, during, after each campaign
# For simplicity, let's look at windows around promotions for top SKUs
# Check if sales drop after promotions end (borrowing effect)

# For SKUs with strong promo activity, compare sales 7 days before, during, 7 days after
# First, find campaign periods for each product
camp_periods = pc.groupby(['product', 'start_date', 'end_date']).size().reset_index()

for sku in [18064, 9607, 15589, 57814, 20635, 21141]:
    sku_name = names[names['product'] == sku]['product_name'].values[0] if sku in names['product'].values else ''
    sku_camps = camp_periods[camp_periods['product'] == sku]
    if len(sku_camps) == 0:
        continue
    
    before_after = []
    for _, cp in sku_camps.iterrows():
        start = cp['start_date']
        end = cp['end_date']
        # 7 days before
        before_start = start - timedelta(days=7)
        before_end = start - timedelta(days=1)
        # 7 days after
        after_start = end + timedelta(days=1)
        after_end = end + timedelta(days=7)
        
        sku_daily = daily[daily['product'] == sku]
        
        before_avg = sku_daily[(sku_daily['date'] >= before_start) & (sku_daily['date'] <= before_end)]['daily_qty'].mean()
        during_avg = sku_daily[(sku_daily['date'] >= start) & (sku_daily['date'] <= end)]['daily_qty'].mean()
        after_avg = sku_daily[(sku_daily['date'] >= after_start) & (sku_daily['date'] <= after_end)]['daily_qty'].mean()
        
        before_after.append({'before': before_avg, 'during': during_avg, 'after': after_avg})
    
    if before_after:
        df_ba = pd.DataFrame(before_after)
        avg_b = df_ba['before'].mean()
        avg_d = df_ba['during'].mean()
        avg_a = df_ba['after'].mean()
        if avg_b > 0 and avg_d > 0:
            print(f'  SKU {sku} ({str(sku_name)[:35]:35s}) Antes: {avg_b:>5.2f} | Durante: {avg_d:>5.2f} | Depois: {avg_a:>5.2f} | Drop pos: {((avg_a-avg_b)/avg_b*100):+.1f}%')

# ---- 3. SAZONALIDADE (variacao mensal) ----
print()
print('='*80)
print('3. COMPORTAMENTO SAZONAL (demanda media por mes, top SKUs)')
print('='*80)

# Monthly averages for high-volume SKUs
for sku in [18064, 9607, 15589, 20635, 21141, 57814]:
    sku_daily = daily[daily['product'] == sku]
    monthly = sku_daily.groupby('month').agg(avg_qty=('daily_qty', 'mean')).reset_index()
    if len(monthly) < 4:
        continue
    max_m = monthly.loc[monthly['avg_qty'].idxmax()]
    min_m = monthly.loc[monthly['avg_qty'].idxmin()]
    cv = monthly['avg_qty'].std() / monthly['avg_qty'].mean() if monthly['avg_qty'].mean() > 0 else 0
    sku_name = names[names['product'] == sku]['product_name'].values[0] if sku in names['product'].values else ''
    print(f'  SKU {sku} ({str(sku_name)[:35]:35s}) | CV mensal: {cv:.2f} | Pico: mes {int(max_m["month"]):>2} ({max_m["avg_qty"]:>5.2f}/d) | Vale: mes {int(min_m["month"]):>2} ({min_m["avg_qty"]:>5.2f}/d) | Amplitude: {(max_m["avg_qty"]/min_m["avg_qty"]-1)*100:+>5.0f}%')

# Find most seasonal SKUs (highest monthly CV)
all_monthly = daily.groupby(['product', 'month']).agg(avg_qty=('daily_qty', 'mean')).reset_index()
seasonality = all_monthly.groupby('product').agg(
    monthly_cv=('avg_qty', lambda x: np.std(x)/np.mean(x) if np.mean(x) > 0 else 0),
    max_monthly=('avg_qty', 'max'),
    min_monthly=('avg_qty', 'min')
).reset_index()
seasonality = seasonality.merge(names, on='product')
seasonality = seasonality.sort_values('monthly_cv', ascending=False)
print()
print('  --- SKUs MAIS SAZONAIS (maior CV mensal) ---')
for _, r in seasonality.head(10).iterrows():
    print(f'  SKU {r["product"]:>6} ({str(r["product_name"])[:40]:40s}) | CV mensal: {r["monthly_cv"]:>5.2f} | Max: {r["max_monthly"]:>5.2f} | Min: {r["min_monthly"]:>5.2f}')

# ---- 4. VARIABILIDADE DE DEMANDA (CV diario) ----
print()
print('='*80)
print('4. VARIABILIDADE DE DEMANDA (CV do daily_qty)')
print('='*80)

variability = daily.groupby('product').agg(
    avg_daily=('daily_qty', 'mean'),
    std_daily=('daily_qty', 'std'),
    cv_daily=('daily_qty', lambda x: np.std(x)/np.mean(x) if np.mean(x) > 0 else 99),
    max_daily=('daily_qty', 'max'),
    pct_zero=('daily_qty', lambda x: (x == 0).mean() * 100)
).reset_index()
variability = variability.merge(names, on='product')
variability = variability.sort_values('cv_daily', ascending=False)
print('  --- SKUs MAIS VARIAVEIS (maior CV diario) ---')
for _, r in variability.head(10).iterrows():
    print(f'  SKU {r["product"]:>6} ({str(r["product_name"])[:40]:40s}) | CV: {r["cv_daily"]:>5.2f} | Media: {r["avg_daily"]:>5.2f} | Max: {r["max_daily"]:>5.2f} | %Zero: {r["pct_zero"]:>5.1f}%')
print()
print('  --- SKUs MAIS PREVISIVEIS (menor CV diario) ---')
for _, r in variability.tail(10).iterrows():
    if r['avg_daily'] > 0.1:
        print(f'  SKU {r["product"]:>6} ({str(r["product_name"])[:40]:40s}) | CV: {r["cv_daily"]:>5.2f} | Media: {r["avg_daily"]:>5.2f} | Max: {r["max_daily"]:>5.2f} | %Zero: {r["pct_zero"]:>5.1f}%')

# ---- 5. PADRAO SEMANAL ----
print()
print('='*80)
print('5. PADRAO SEMANAL (demanda por dia da semana)')
print('='*80)

dow_names = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab', 'Dom']
dow_pattern = daily.groupby('dow').agg(avg_qty=('daily_qty', 'mean')).reset_index()
dow_pattern['dow_name'] = dow_pattern['dow'].map({i: n for i, n in enumerate(dow_names)})
base_dow = dow_pattern[dow_pattern['dow'] == 0]['avg_qty'].values[0] if 0 in dow_pattern['dow'].values else 1
dow_pattern['index'] = dow_pattern['avg_qty'] / base_dow * 100
print('  Dia da semana | Media/dia | Indice (Seg=100)')
for _, r in dow_pattern.iterrows():
    print(f'  {r["dow_name"]:12s} | {r["avg_qty"]:>8.2f} | {r["index"]:>5.1f}%')

# Pattern for specific products
print()
print('  --- Padrao semanal por SKU top-5 ---')
for sku in [18064, 9607, 15589, 20635, 21141]:
    sku_daily = daily[daily['product'] == sku]
    dw = sku_daily.groupby('dow').agg(avg_qty=('daily_qty', 'mean')).reset_index()
    dw['dow_name'] = dw['dow'].map({i: n for i, n in enumerate(dow_names)})
    b = dw[dw['dow'] == 0]['avg_qty'].values[0] if 0 in dw['dow'].values else 1
    dw['idx'] = dw['avg_qty'] / b * 100 if b > 0 else 0
    sku_name = names[names['product'] == sku]['product_name'].values[0][:30] if sku in names['product'].values else ''
    line = f'  SKU {sku} ({str(sku_name):30s}): '
    line += ' | '.join([f'{r["dow_name"]}:{r["idx"]:>5.1f}%' for _, r in dw.iterrows()])
    print(line)

# ---- 6. DEPENDENCIA DE CAMPANHAS ----
print()
print('='*80)
print('6. SKUs COM MAIOR DEPENDENCIA DE CAMPANHAS')
print('='*80)

# % of sales that happen during promo periods
dep = daily.groupby('product').apply(
    lambda df: pd.Series({
        'pct_sales_in_promo': (df[df['is_promo'] == 1]['daily_qty'].sum() / df['daily_qty'].sum() * 100) if df['daily_qty'].sum() > 0 else 0,
        'total_qty': df['daily_qty'].sum(),
        'pct_promo_days': (df['is_promo'].sum() / len(df) * 100)
    })
).reset_index()
dep = dep.merge(names, on='product')
dep = dep.sort_values('pct_sales_in_promo', ascending=False)
for _, r in dep.head(15).iterrows():
    if r['total_qty'] >= 5:
        print(f'  SKU {r["product"]:>6} ({str(r["product_name"])[:40]:40s}) | % vendas em promocao: {r["pct_sales_in_promo"]:>5.1f}% | % dias promocao: {r["pct_promo_days"]:>5.1f}% | Vendas: {r["total_qty"]}')

# ---- 7. AUMENTO REAL OU ANTECIPACAO? ----
print()
print('='*80)
print('7. AUMENTO REAL VS ANTECIPACAO (demanda acumulada pre+pos+promo)')
print('='*80)
# Hypothesis: if promo just shifts demand (borrowing), demand in window before+after should be lower
# If promo generates real demand, total before+after+promo > before+after without promo
# We already computed before/after above. Let's check the overall effect.

# For key promo SKUs, compare: demand during promo window vs (demand in same-length window before + after)
print('  SKU | Acumulado em janela 7d-antes + 7d-depois vs 14d-durante')
for sku in [18064, 9607, 15589, 20635, 21141, 57814]:
    sku_daily = daily[daily['product'] == sku]
    sku_camps = camp_periods[camp_periods['product'] == sku]
    if len(sku_camps) == 0:
        continue
    
    total_before = 0
    total_during = 0
    total_after = 0
    n_camps = 0
    
    for _, cp in sku_camps.iterrows():
        start = cp['start_date']
        end = cp['end_date']
        window_days = (end - start).days + 1
        if window_days < 2 or window_days > 30:
            continue
            
        before_start = start - timedelta(days=window_days)
        before_end = start - timedelta(days=1)
        after_start = end + timedelta(days=1)
        after_end = end + timedelta(days=window_days)
        
        b = sku_daily[(sku_daily['date'] >= before_start) & (sku_daily['date'] <= before_end)]['daily_qty'].sum()
        d = sku_daily[(sku_daily['date'] >= start) & (sku_daily['date'] <= end)]['daily_qty'].sum()
        a = sku_daily[(sku_daily['date'] >= after_start) & (sku_daily['date'] <= after_end)]['daily_qty'].sum()
        
        if d > 0:
            total_before += b
            total_during += d
            total_after += a
            n_camps += 1
    
    if n_camps > 0 and total_during > 0:
        expected_without_promo = total_before + total_after
        realized = total_during + total_after
        extra = realized - expected_without_promo
        sku_name = names[names['product'] == sku]['product_name'].values[0][:30] if sku in names['product'].values else ''
        print(f'  SKU {sku} ({str(sku_name):30s}) | Durante: {total_during:>4} | Antes: {total_before:>4} | Depois: {total_after:>4} | Efeito liquido: {extra:+>4} ({extra/total_during*100:+>+5.0f}% do promo) | {n_camps} campanhas')
