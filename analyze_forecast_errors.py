import pandas as pd
import numpy as np

fc = pd.read_csv('q4_2024_daily_forecast_static.csv')
fc['date'] = pd.to_datetime(fc['date'])

# Forecast errors
fc['error'] = fc['observed_demand'] - fc['forecast_demand']
fc['abs_error'] = fc['error'].abs()
fc['squared_error'] = fc['error'] ** 2
fc['pct_error'] = np.where(fc['observed_demand'] > 0,
                            fc['error'] / fc['observed_demand'] * 100, 0)
fc['abs_pct_error'] = fc['abs_error'] / fc['observed_demand'].replace(0, np.nan) * 100
fc['bias_flag'] = np.where(fc['error'] > 0, 1, np.where(fc['error'] < 0, -1, 0))
fc['actual_zero'] = (fc['observed_demand'] == 0).astype(int)

# --- 1. ERRO POR SKU ---
print('=' * 80)
print('1. MAIOR ERRO DE PREVISAO POR SKU (MAPE, MAE, vies)')
print('=' * 80)

sku_err = fc.groupby(['product', 'product_name']).agg(
    mae=('abs_error', 'mean'),
    rmse=('squared_error', lambda x: np.sqrt(x.mean())),
    mape=('abs_pct_error', lambda x: np.nanmean(x) if x.notna().any() else 0),
    bias=('error', 'mean'),
    bias_pct=('error', lambda x: x.sum() / fc[fc['product'] == x.name[0]]['observed_demand'].sum() * 100 if fc[fc['product'] == x.name[0]]['observed_demand'].sum() > 0 else 0),
    avg_obs=('observed_demand', 'mean'),
    avg_fc=('forecast_demand', 'mean'),
    total_obs=('observed_demand', 'sum'),
    total_fc=('forecast_demand', 'sum'),
    pct_zero=('actual_zero', 'mean'),
    days=('date', 'nunique')
).reset_index()
sku_err = sku_err.sort_values('mae', ascending=False)

print('  --- MAIOR MAE (erro absoluto medio) ---')
for _, r in sku_err.head(10).iterrows():
    print(f'  SKU {r["product"]:>6} ({str(r["product_name"])[:35]:35s}) | MAE: {r["mae"]:>5.2f} | RMSE: {r["rmse"]:>5.2f} | Bias: {r["bias"]:>+5.2f}/d | MAPE: {r["mape"]:>5.1f}%')

print()
print('  --- MAIOR MAPE (erro percentual) ---')
sku_err_mape = sku_err[sku_err['avg_obs'] >= 0.3].sort_values('mape', ascending=False)
for _, r in sku_err_mape.head(10).iterrows():
    print(f'  SKU {r["product"]:>6} ({str(r["product_name"])[:35]:35s}) | MAPE: {r["mape"]:>6.1f}% | MAE: {r["mae"]:>5.2f} | Media obs: {r["avg_obs"]:>4.2f} | %Zero: {r["pct_zero"]*100:>4.1f}%')

print()
print('  --- MENOR MAPE (melhor previsao) ---')
sku_err_mape_low = sku_err[sku_err['avg_obs'] >= 0.3].sort_values('mape')
for _, r in sku_err_mape_low.head(10).iterrows():
    print(f'  SKU {r["product"]:>6} ({str(r["product_name"])[:35]:35s}) | MAPE: {r["mape"]:>6.1f}% | MAE: {r["mae"]:>5.2f} | Media obs: {r["avg_obs"]:>4.2f} | Bias: {r["bias"]:>+5.2f}/d')

# --- 2. DESEMPENHO POR NIVEL DE DEMANDA ---
print()
print('=' * 80)
print('2. FORECAST PERFORMA PIOR EM BAIXA DEMANDA?')
print('=' * 80)

fc['demand_bucket'] = pd.cut(fc['observed_demand'],
                              bins=[-1, 0, 1, 3, 5, 10, 20, 50, 1000],
                              labels=['0', '0-1', '1-3', '3-5', '5-10', '10-20', '20-50', '50+'])
bucket = fc.groupby('demand_bucket', observed=True).agg(
    mape=('abs_pct_error', lambda x: np.nanmean(x)),
    mae=('abs_error', 'mean'),
    bias=('error', 'mean'),
    n=('date', 'size'),
    total_demand=('observed_demand', 'sum')
).reset_index()
print(f'  {"Bucket":>12s} | {"N":>6s} | {"MAPE":>6s} | {"MAE":>8s} | {"Bias":>8s} | {"Demanda tot":>12s}')
for _, r in bucket.iterrows():
    print(f'  {str(r["demand_bucket"]):>12s} | {r["n"]:>6.0f} | {r["mape"]:>5.1f}% | {r["mae"]:>8.4f} | {r["bias"]:>+8.4f} | {r["total_demand"]:>12.0f}')

# --- 3. DEMANDA INTERMITENTE ---
print()
print('=' * 80)
print('3. PRODUTOS COM DEMANDA INTERMITENTE (% zeros elevado)')
print('=' * 80)
intermit = sku_err[sku_err['pct_zero'] > 0.5].sort_values('pct_zero', ascending=False)
for _, r in intermit.iterrows():
    print(f'  SKU {r["product"]:>6} ({str(r["product_name"])[:40]:40s}) | %Zero: {r["pct_zero"]*100:>5.1f}% | Media: {r["avg_obs"]:>4.2f} | MAPE: {r["mape"]:>5.1f}% | MAE: {r["mae"]:>4.2f}')

print()
print('  --- PRODUTOS COM DEMANDA REGULAR (% zeros baixo) ---')
regular = sku_err[sku_err['pct_zero'] < 0.1][sku_err['total_obs'] > 10].sort_values('pct_zero')
for _, r in regular.head(10).iterrows():
    print(f'  SKU {r["product"]:>6} ({str(r["product_name"])[:40]:40s}) | %Zero: {r["pct_zero"]*100:>5.1f}% | Media: {r["avg_obs"]:>4.2f} | MAPE: {r["mape"]:>5.1f}%')

# --- 4. SKUs IMPOSSIVEIS DE PREVER ---
print()
print('=' * 80)
print('4. PRODUTOS COM BAIXA PREVISIBILIDADE (MAPE > 100% + %Zero alto)')
print('=' * 80)
unpredictable = sku_err[(sku_err['mape'] > 80) | (sku_err['pct_zero'] > 0.7)].sort_values('mape', ascending=False)
for _, r in unpredictable.head(10).iterrows():
    print(f'  SKU {r["product"]:>6} ({str(r["product_name"])[:40]:40s}) | MAPE: {r["mape"]:>6.1f}% | %Zero: {r["pct_zero"]*100:>5.1f}% | MAE: {r["mae"]:>5.2f} | Media obs: {r["avg_obs"]:>4.2f}')

# --- 5. SINAL VS RUIDO ---
print()
print('=' * 80)
print('5. O MODELO APRENDE SINAL OU APENAS RUIDO?')
print('=' * 80)

# Compare: forecast vs naive persistence (yesterday = today)
fc['persistence_fc'] = fc.groupby(['location', 'product'])['observed_demand'].shift(1)
fc['persistence_error'] = fc['observed_demand'] - fc['persistence_fc']

model_mae = fc['abs_error'].mean()
persist_mae = fc['persistence_error'].abs().mean()
model_rmse = np.sqrt(fc['squared_error'].mean())
persist_rmse = np.sqrt((fc['persistence_error'] ** 2).mean())

print(f'  Modelo MAE:  {model_mae:.4f}')
print(f'  Persistence MAE: {persist_mae:.4f}')
print(f'  Melhoria vs Persistence: {(1 - model_mae/persist_mae)*100:+.1f}%' if persist_mae > 0 else '')
print(f'  Modelo RMSE: {model_rmse:.4f}')
print(f'  Persistence RMSE: {persist_rmse:.4f}')
print()

# Compare with simple historical average
fc['hist_avg_fc'] = fc.groupby(['location', 'product'])['observed_demand'].transform('mean')
fc['hist_avg_error'] = fc['observed_demand'] - fc['hist_avg_fc']
hist_avg_mae = fc['hist_avg_error'].abs().mean()
print(f'  Media historica simples MAE: {hist_avg_mae:.4f}')
print(f'  Melhoria vs Media historica: {(1 - model_mae/hist_avg_mae)*100:+.1f}%' if hist_avg_mae > 0 else '')

# Theil's U statistic (compare to naive)
theil_u = np.sqrt((fc['error'] ** 2).sum()) / np.sqrt((fc['persistence_error'] ** 2).sum())
print(f'  Theil U: {theil_u:.4f} ({"<1 = modelo > naive" if theil_u < 1 else ">1 = naive > modelo"})')

# R-squared-like: variance explained
ss_res = (fc['error'] ** 2).sum()
ss_tot = ((fc['observed_demand'] - fc['observed_demand'].mean()) ** 2).sum()
r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
print(f'  R²-like (variancia explicada): {r2:.4f}')

# --- 6. FEATURE IMPORTANCE (via decomposicao de variancia) ---
print()
print('=' * 80)
print('6. DECOMPOSICAO DO MODELO: QUAL COMPONENTE MAIS INFLUENCIA?')
print('=' * 80)
print('''
  O modelo usa 3 componentes + ajuste promocional:
    - 45%: Media ultimos 28 dias (recente)
    - 35%: Media mesmo dia da semana (8 ultimas ocorrencias)
    - 20%: Mesma janela do ano anterior (D-372 a D-358)
    - Ajuste: promo_uplift (x1.0 a x2.5) em dias promocionais
''')

# Correlation between components
print('  Correlacao entre forecast e observed_demand:')
corr = fc['forecast_demand'].corr(fc['observed_demand'])
print(f'    r = {corr:.4f}')

print()
print('  Erro medio em dias PROMO vs NAO-PROMO:')
promo_err = fc[fc['is_promo'] == 1]['abs_error'].mean()
nopromo_err = fc[fc['is_promo'] == 0]['abs_error'].mean()
print(f'    Dia PROMO:     MAE = {promo_err:.4f}')
print(f'    Dia NAO-PROMO: MAE = {nopromo_err:.4f}')
print(f'    Diferenca: {(promo_err/nopromo_err - 1)*100:+.1f}%')

# --- 7. PROMOCOES ESTAO SENDO CORRETAMENTE CAPTURADAS? ---
print()
print('=' * 80)
print('7. PROMOCOES ESTAO SENDO CAPTURADAS? (erro em dias promo vs nao-promo)')
print('=' * 80)

promo_detail = fc.groupby(['product', 'product_name', 'is_promo']).agg(
    mae=('abs_error', 'mean'),
    bias=('error', 'mean'),
    avg_fc=('forecast_demand', 'mean'),
    avg_obs=('observed_demand', 'mean'),
    n=('date', 'size')
).reset_index()

promo_pivot = promo_detail.pivot_table(
    index=['product', 'product_name'],
    columns='is_promo',
    values=['mae', 'bias', 'avg_fc', 'avg_obs', 'n'],
    fill_value=0
)

print('  SKUs com maior diferenca de erro em PROMO vs NAO-PROMO:')
# Only SKUs with promo days
sku_promo_err = fc[fc['is_promo'] == 1].groupby(['product', 'product_name']).agg(
    promo_mae=('abs_error', 'mean'),
    promo_bias=('error', 'mean'),
    promo_n=('date', 'size')
).reset_index()
sku_nopromo_err = fc[fc['is_promo'] == 0].groupby(['product', 'product_name']).agg(
    nopromo_mae=('abs_error', 'mean'),
    nopromo_bias=('error', 'mean'),
    nopromo_n=('date', 'size')
).reset_index()
comp = sku_promo_err.merge(sku_nopromo_err, on=['product', 'product_name'])
comp = comp[comp['promo_n'] >= 3]
comp['error_ratio'] = comp['promo_mae'] / comp['nopromo_mae'].replace(0, np.nan)
comp = comp.sort_values('error_ratio', ascending=False)
for _, r in comp.head(10).iterrows():
    print(f'  SKU {r["product"]:>6} ({str(r["product_name"])[:35]:35s}) | Erro PROMO: {r["promo_mae"]:>5.2f} | Erro NORMAL: {r["nopromo_mae"]:>5.2f} | Ratio: {r["error_ratio"]:>4.1f}x | Bias promo: {r["promo_bias"]:>+5.2f}')

# --- 8. VIES SISTEMATICO ---
print()
print('=' * 80)
print('8. VIES SISTEMATICO (o modelo superestima ou subestima?)')
print('=' * 80)

overall_bias = fc['error'].mean()
overall_bias_pct = fc['error'].sum() / fc['observed_demand'].sum() * 100 if fc['observed_demand'].sum() > 0 else 0
overall_mae = fc['abs_error'].mean()
total_fc = fc['forecast_demand'].sum()
total_obs = fc['observed_demand'].sum()

print(f'  Forecast total:    {total_fc:>8.2f} unidades')
print(f'  Observado total:   {total_obs:>8.2f} unidades')
print(f'  Diferenca:         {total_fc - total_obs:>+8.2f} unidades ({((total_fc/total_obs)-1)*100:+.1f}%)')
print(f'  Bias medio diario: {overall_bias:>+8.4f} unidade/dia')
print(f'  Bias percentual:   {overall_bias_pct:>+8.2f}%')
print()
if overall_bias > 0:
    print('  >> MODELO SUBESTIMA (erro > 0: observado > forecast)')
else:
    print('  >> MODELO SUPERESTIMA (erro < 0: forecast > observado)')

# Bias by day of week
dow_bias = fc.groupby(fc['date'].dt.dayofweek).agg(
    bias=('error', 'mean'),
    mae=('abs_error', 'mean'),
    n=('date', 'size')
).reset_index()
dow_names = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab', 'Dom']
print()
print('  Vies por dia da semana:')
for _, r in dow_bias.iterrows():
    print(f'    {dow_names[int(r["date"])]:>8s} | Bias: {r["bias"]:>+6.3f} | MAE: {r["mae"]:>6.3f} | N: {r["n"]:>4.0f}')

# Bias by week
fc['week'] = fc['date'].dt.isocalendar().week.astype(int)
week_bias = fc.groupby('week').agg(
    bias=('error', 'mean'),
    mae=('abs_error', 'mean'),
    total_obs=('observed_demand', 'sum'),
    total_fc=('forecast_demand', 'sum'),
    n=('date', 'size')
).reset_index()
print()
print('  Vies por semana do Q4:')
for _, r in week_bias.iterrows():
    print(f'    Semana {int(r["week"]):>2d} | Bias: {r["bias"]:>+6.3f} | MAE: {r["mae"]:>6.3f} | FC: {r["total_fc"]:>5.0f} | Obs: {r["total_obs"]:>5.0f}')

# --- 9. RESUMO POR SKU: super vs sub estimativa ---
print()
print('=' * 80)
print('9. SKUs MAIS SUBESTIMADOS E SUPERESTIMADOS')
print('=' * 80)
sku_bias_pct = sku_err.copy()
sku_bias_pct['bias_pct_of_obs'] = np.where(sku_bias_pct['total_obs'] > 0,
    (sku_bias_pct['total_fc'] - sku_bias_pct['total_obs']) / sku_bias_pct['total_obs'] * 100, 0)
sku_bias_pct = sku_bias_pct[sku_bias_pct['total_obs'] >= 5].sort_values('bias_pct_of_obs')
print('  --- SUPERESTIMADOS (forecast > observado) ---')
for _, r in sku_bias_pct.head(5).iterrows():
    print(f'  SKU {r["product"]:>6} ({str(r["product_name"])[:40]:40s}) | FC: {r["total_fc"]:>5.0f} | Obs: {r["total_obs"]:>5.0f} | Diferenca: {r["bias_pct_of_obs"]:+>6.1f}%')
print()
print('  --- SUBESTIMADOS (observado > forecast) ---')
for _, r in sku_bias_pct.tail(5).iloc[::-1].iterrows():
    print(f'  SKU {r["product"]:>6} ({str(r["product_name"])[:40]:40s}) | FC: {r["total_fc"]:>5.0f} | Obs: {r["total_obs"]:>5.0f} | Diferenca: {r["bias_pct_of_obs"]:+>6.1f}%')
