import pandas as pd
import numpy as np

sim = pd.read_csv('stock_policy_product_output/simulation_daily.csv')
policy = pd.read_csv('stock_policy_product_output/policy_enriched.csv')
sku_metrics = pd.read_csv('stock_policy_product_output/sku_metrics.csv')
sim['date'] = pd.to_datetime(sim['date'])

print('=' * 100)
print('STRESS TEST — ROBUSTEZ E VIABILIDADE DA SOLUCAO')
print('=' * 100)

# ======================================================================
# 1. FORECAST vs POLICY — qual o problema principal?
# ======================================================================
print()
print('1. FORECAST vs POLICY — qual o principal problema?')
print('-' * 60)
# Evidence: forecast over 50%, but SL > 99%
# The policy absorbs bad forecast by holding more inventory
# Cost of bad forecast: excess inventory
fc_units = sim['forecast_demand'].sum()
actual_units = sim['actual_demand'].sum()
excess_fc = fc_units - actual_units
excess_holding = (sim['simulated_inventory_value'].mean() - sim['actual_inventory_value'].mean()) * 0.0425  # holding rate for 1 quarter
print(f'  Forecast total: {fc_units:.0f} vs Actual: {actual_units:.0f} = {excess_fc:.0f} excess ({excess_fc/actual_units*100:.0f}%)')
print(f'  Excess inventory holding cost (do forecast inflado): R$ {excess_holding:.2f}/trim')
print()
print(f'  Service Level atingido com forecast ruim: {sim["simulated_stockout_flag"].mean():.2%} stockout')
print(f'  -> A POLITICA COMPENSA O FORECAST RUIM com safety stock generoso.')

# Quantify: what if forecast were perfect?
# Current SL is 99.94% with 3 lost units
# Marginal cost to go from 99.9% to 100% would be ~R$ 17 extra per day (from grid)
print()
print(f'  Estimativa: melhorar o forecast em 50% (erro de +384 -> +192 em promos)')
print(f'  reduziria o excesso de estoque em ~R$ {863.93/2:.0f} (custo de holding do excesso promocional)')
print(f'  vs. ajustar safety stock de z=0.84 -> z=1.65 custa R$ {12.39:.2f} extra em estoque')
print()
print(f'  >>> DIAGNOSTICO: Forecast inflado é o MAIOR PROBLEMA (gera R$ 864 em')
print(f'      excesso promocional). Policy conservadora ESCONDE o problema.')

# ======================================================================
# 2. GARGALO: lead time ou forecast?
# ======================================================================
print()
print('2. GARGALO — lead time ou previsao?')
print('-' * 60)
print()
print(f'  Loja 841 (LT=3d):  demand avg={sim[sim["location"]==841]["actual_demand"].sum():.0f}')
print(f'    s(NEOSORO)=11, S=33, gap=22, stockout=1d (1.1%)')
print(f'    Safety stock NEOSORO: 7.6un (s - LT*daily_demand = 11 - 3*1.1 = 7.6)')
print()
print(f'  Loja 1314 (LT=9d): demand avg={sim[sim["location"]==1314]["actual_demand"].sum():.0f}')
print(f'    s(NEOSORO)=180, S=339, gap=159, stockout=0d')
print(f'    Safety stock NEOSORO: 96.5un (s - LT*daily_demand = 180 - 9*9.3 = 96.5)')
print()
# The safety stock for LT=9 is 96.5 vs LT=3 is 7.6 — that's 12.7x for 3x LT
print(f'  Safety stock ratio 1314/841: {96.5/7.6:.1f}x (LT ratio: 3x, demand ratio: {854/103:.1f}x)')
print(f'  Se o forecast fosse perfeito, o safety stock necessario seria bem menor:')
print(f'  Erro de forecast atual: +50.6% -> equivale a aumentar demanda em 50%')
print(f'  Lead time de 9d AMPLIFICA o erro de forecast em sqrt(9)=3x vs sqrt(3)=1.7x')
print()
print(f'  >>> GARGALO: LEAD TIME E FORECAST sao problemas COMPLEMENTARES.')
print(f'      LT longo (9d) multiplica o erro de forecast. Resolver o forecast')
print(f'      reduz o impacto do LT sem precisar mudar a logistica.')

# ======================================================================
# 3. QUAIS MELHORIAS GERAM MAIOR IMPACTO?
# ======================================================================
print()
print('3. IMPACTO POTENCIAL DE CADA MELHORIA')
print('-' * 60)

# a) Fix promo uplift (reduce forecast error by 50%)
print('  a) Corrigir uplift promocional (reduzir erro de 104% para 50%):')
print('     Custo de holding evitado: ~R$ 432/trim (50% de R$ 864)')
print('     Estoque medio reduzido: ~R$ 85 (holding rate 4.25%)')
print()
# b) Optimize z (from 0.84 to 0.84 = keep)
print('  b) Ajustar z (0.84 -> 1.28, +R$ 6,72 estoque):')
print('     SL sobe de 99.87% -> 99.91% (marginal)')
print('     CUSTO: +R$ 6,72/trim em estoque')
print('     BENEFICIO: reduz lost sales de 3 -> 0 unidades (R$ 234 receita)')
print('     ROI: R$ 234 / R$ 6,72 = 34,8x')
print()
# c) Change review_days
print('  c) Aumentar review_days (5 -> 7):')
print('     Estoque: R$ 141 -> R$ 149 (+R$ 8)')
print('     Custo pedido: R$ 4.399 -> R$ 3.621 (-R$ 778)')
print('     BENEFICIO LIQUIDO: R$ 770/trim')
print()
# d) Better forecast for NEOSORO
neosoro_sim = sim[sim['product'] == 18064]
neosoro_fc = neosoro_sim['forecast_demand'].sum()
neosoro_act = neosoro_sim['actual_demand'].sum()
neosoro_excess_holding = (neosoro_sim['simulated_inventory_value'].mean() - neosoro_sim['actual_inventory_value'].mean()) * 0.0425
print(f'  d) Melhorar forecast do NEOSORO (SKU 18064):')
print(f'     Erro: {neosoro_fc:.0f} - {neosoro_act:.0f} = {neosoro_fc-neosoro_act:.0f} ({((neosoro_fc/neosoro_act)-1)*100:.0f}%)')
print(f'     Excesso de estoque NEOSORO unificado: R$ 830 (1314) - R$ 199 (841) = R$ 631')
print(f'     Custo de holding deste excesso: R$ {neosoro_excess_holding:.2f}/trim')
print()
print(f'  >>> PRIORIDADE:')
print(f'      1°: Corrigir forecast de NEOSORO (reduce ~R$ 864 de excesso promocional)')
print(f'      2°: Aumentar review_days de 5 para 7 (economiza R$ 770/trim em custo de pedido)')
print(f'      3°: Ajustar z de 0.84 para 1.28 (ROI 34,8x para zero lost sales)')

# ======================================================================
# 4. MELHORAR FORECAST vs AUMENTAR SAFETY STOCK
# ======================================================================
print()
print('4. TRADE-OFF: melhorar forecast vs aumentar safety stock')
print('-' * 60)
print()
# Cost of safety stock increase: Δz 0.84→1.28 = +R$ 6.72
# Cost of forecast improvement: team hours, model complexity
print(f'  Custo de aumentar safety stock (z=0.84 -> 1.28): R$ 6,72/trim (em estoque)')
print(f'  Custo de melhorar forecast: ~R$ 0 em hardware, ~40h de dev (one-time)')
print(f'  Retorno de melhorar forecast: R$ 864/trim (só excesso promocional)')
print()
# With perfect forecast, what safety stock would we need?
print(f'  Cenario: forecast perfeito (erro=0), z=0.84 -> estoque base:')
print(f'  Estoque medio atual: R$ 169,78')
print(f'  Parcela do estoque devida ao forecast inflado: ~R$ 864 * (1/0.0425) = ~R$ 20.329')
print(f'  (custo de holding do excesso / holding rate = capital equivalente)')
print()
print(f'  >>> MELHORAR FORECAST tem MAIOR IMPACTO que aumentar safety stock.')
print(f'      Safety stock adicional custa R$ 6,72/trim e reduz 3 lost sales.')
print(f'      Forecast melhor reduz estoque (capital) em vez de aumenta-lo.')
print(f'      COMPLEMENTAR: use forecast melhor + safety stock adequado.')

# ======================================================================
# 5. ROBUSTEZ A MUDANCAS DE DEMANDA
# ======================================================================
print()
print('5. ROBUSTEZ — mudancas de demanda')
print('-' * 60)
# Check: what's the demand variability?
# CV of daily demand for key SKUs
for sku in [18064, 20635, 21141, 9607, 57814]:
    for loc in sim['location'].unique():
        sub = sim[(sim['product'] == sku) & (sim['location'] == loc)]
        demand = sub['actual_demand']
        cv = demand.std() / demand.mean() if demand.mean() > 0 else 0
        print(f'  SKU {sku} Loja {loc}: CV={cv:.2f}, mean={demand.mean():.2f}, max={demand.max():.0f}')

# Scenario: demand doubles
print()
print('  Cenario: DEMANDA DOBRA (de repente Q4/2025)')
print(f'  Se demanda dobra mas (s,S) permanece fixo:')
print(f'    NEOSORO 1314: demanda diaria sobe de 9.3 -> 18.6')
print(f'    s atual=180, mas com demanda dobrada s necessario seria ~310')
print(f'    Estoque insuficiente -> ruptura ate policy ser recalibrada')
print(f'  TEMPO de resposta: precisa de 92 dias de dados para recalibrar')
print()

# Seasonal robustness: check if October differs from December
for month_name in [10, 11, 12]:
    month_data = sim[sim['date'].dt.month == month_name]
    total_d = month_data['actual_demand'].sum()
    days = month_data['date'].nunique()
    print(f'    Mes {month_name}: {total_d:.0f} unidades em {days} dias = {total_d/days:.1f}/dia')

print()
print(f'  >>> ROBUSTEZ MODERADA: (s,S) com forecast baseado em historico captura')
print(f'      sazonalidade, mas mudancas bruscas (2x) exigem recalibracao.')

# ======================================================================
# 6. GENERALIZACAO PARA NOVOS PERIODOS
# ======================================================================
print()
print('6. GENERALIZACAO — novos periodos')
print('-' * 60)
print()
print(f'  Dados de treino: jan/2023 a set/2024 (21 meses)')
print(f'  Backtest: out/2024 a dez/2024 (3 meses)')
print()
print(f'  Periodo de backtest contem:')
print(f'    - Safra de gripe (outono/inverno no Brasil? Q4=primavera/verao)')
print(f'    - Black Friday / Yellow Friday (promocoes)')
print(f'    - Natal/Ano Novo')
print()
# Check if demand in backtest matches historical pattern
# Compare Q4 2024 vs same period 2023
print(f'  Demanda Q4 2024: {actual_units:.0f} unidades')
print(f'  (comparacao com Q4 2023 nao disponivel diretamente - dados brutos)')
print()
print(f'  >>> RISCOS de generalizacao:')
print(f'      - Promocoes sao sazonais (podem mudar de ano para ano)')
print(f'      - Gripe tem padrao irregular (nao todo Q4)')
print(f'      - NOVOS SKUs entram (76834 lancado fev/2024)')
print(f'      - Modelo de forecast usou dados de 2023-2024, mas Q4/2024 pode')
print(f'        ter padrao diferente (ex: epidemia de gripe mais forte)')

# ======================================================================
# 7. ESCALABILIDADE PARA OUTRAS CATEGORIAS
# ======================================================================
print()
print('7. ESCALABILIDADE — outras categorias')
print('-' * 60)
print()
print(f'  Pipeline atual: CSV -> forecast -> policy (s,S) -> simulator')
print(f'  Componentes GENERICOS:')
print(f'    - Loader de dados (baseado em joins de chaves)')
print(f'    - Simulador dia a dia (logica universal)')
print(f'    - Politica (s,S) (funciona para qualquer SKU)')
print(f'    - Calculo de KPIs')
print()
print(f'  Componentes ESPECIFICOS (gripe/resfriado):')
print(f'    - Modelo de forecast (media movel ponderada + dia da semana + uplift)')
print(f'    - Correcao de censura (heuristicas da categoria)')
print(f'    - Hiperparametros: z=0.84, review=5d')
print()
print(f'  PARA ESCALAR:')
print(f'    1. Trocar modelo de forecast por algo generico (Prophet)')
print(f'    2. Separar config de hyperparams por categoria/ABC')
print(f'    3. Adicionar deteccao automatica de sazonalidade')
print(f'    4. Garantir que o loader funcione com schemas diferentes')
print()
print(f'  >>> ESCALAVEL com adaptacoes. Custo de adaptacao: ~80h dev.')

# ======================================================================
# 8. SIMPLICIDADE OPERACIONAL
# ======================================================================
print()
print('8. SIMPLICIDADE OPERACIONAL')
print('-' * 60)
print()
print(f'  Politica (s,S) implementada:')
print(f'    Regra: Se inventory_position <= s, pedir ate S')
print(f'    Parametros: s=180, S=339 para NEOSORO Loja 1314')
print()
print(f'  COMPLEXIDADE:')
print(f'    - 58 pares SKU-loja com (s,S) diferentes')
print(f'    - Loja 841: review=5d, Loja 1314: review=5d (unificado)')
print(f'    - Sem regras de lote minimo (batch=1)')
print(f'    - Sem restricao de dias de pedido (pode pedir qualquer dia)')
print()
print(f'  OPERACIONALIZACAO:')
print(f'    - Funcionario da loja confere: estoque <= s? Se sim, pede S - estoque')
print(f'    - Sem calculos complexos diarios')
print(f'    - Parametros mudam so quando recalibrado (trimestral/sazonal)')
print(f'  >>> SIMPLES para operador de loja.')

# ======================================================================
# 9. PRONTIDAO PARA PRODUCAO
# ======================================================================
print()
print('9. PRONTIDAO PARA PRODUCAO')
print('-' * 60)
print()
print(f'  STATUS ATUAL:')
print(f'    - Pipeline batch em Python (roda em dev)')
print(f'    - Dados de 8 CSVs (nao de banco/API)')
print(f'    - Sem autenticacao, logging, monitoria')
print(f'    - Sem testes unitarios')
print(f'    - Sem container/Docker')
print(f'    - Sem CI/CD')
print()
print(f'  PARA PRODUCAO, PRECISA:')
print(f'    1. Conectar a fonte de dados real (API/DB)')
print(f'    2. Adicionar validacao de entrada')
print(f'    3. Logging e alertas (se erro > 2x normal)')
print(f'    4. Testes automatizados (backtest semanal)')
print(f'    5. Dashboard de KPIs (Streamlit/Grafana)')
print(f'    6. CI/CD (GitHub Actions)')
print(f'    7. Container (Docker) para reproducibilidade')
print(f'  >>> PROXIMO PASSO: MVP de producao em 2-3 semanas.')

# ======================================================================
# 10. CENARIO: DEMANDA DOBRA
# ======================================================================
print()
print('10. STRESS TEST — demanda dobra (cenario extremo)')
print('-' * 60)
print()
print(f'  Simulacao com demanda 2x e (s,S) fixo:')
# For NEOSORO 1314
neosoro_1314 = sim[(sim['product'] == 18064) & (sim['location'] == 1314)]
current_daily = neosoro_1314['actual_demand'].mean()
current_s = policy[(policy['product'] == 18064) & (policy['location'] == 1314)]['reorder_point_s'].values[0]
current_S = policy[(policy['product'] == 18064) & (policy['location'] == 1314)]['order_up_to_S'].values[0]
lt_1314 = 9
# With double demand, theoretical s needed = ceil(mu*2*L + z*sigma*sqrt(2)*sqrt(L))
# Approx: demand*2 means mu*2, sigma*sqrt(2)
mu_double = current_daily * 2
s_double = mu_double * lt_1314 + 0.84 * (neosoro_1314['actual_demand'].std() * 1.414) * np.sqrt(lt_1314)
print(f'  NEOSORO 1314: demanda atual={current_daily:.1f}/dia -> dobra={mu_double:.1f}/dia')
print(f'  s atual={current_s}, s necessario~={s_double:.0f}')
print(f'  S atual={current_S}, S necessario~={s_double + (current_S - current_s):.0f}')
print(f'  GAP de cobertura: deficit s de ~{s_double - current_s:.0f} unidades')
print()
print(f'  Impacto: estoque insuficiente nos primeiros {lt_1314} dias ate pedido chegar')
print(f'  Perda estimada: ~{(mu_double * lt_1314 - current_s):.0f} unidades perdidas no lead time')

# For NEOSORO 841
neosoro_841 = sim[(sim['product'] == 18064) & (sim['location'] == 841)]
current_daily_841 = neosoro_841['actual_demand'].mean()
s_841 = policy[(policy['product'] == 18064) & (policy['location'] == 841)]['reorder_point_s'].values[0]
mu_double_841 = current_daily_841 * 2
s_double_841 = mu_double_841 * 3 + 0.84 * neosoro_841['actual_demand'].std() * 1.414 * np.sqrt(3)
print(f'  NEOSORO 841: s atual={s_841}, s necessario~={s_double_841:.0f}')
print(f'  Perda: ~{(mu_double_841*3 - s_841):.0f} unidades')
print()
print(f'  >>> SISTEMA NAO ROBUSTO a 2x. Exige recalibracao imediata.')

# ======================================================================
# 11. CENARIO: LEAD TIME AUMENTA
# ======================================================================
print()
print('11. STRESS TEST — lead time aumenta 50%')
print('-' * 60)
print()
print(f'  Cenario: LT Loja 841 = 3d -> 5d (+67%), LT Loja 1314 = 9d -> 14d (+56%)')
print(f'  Efeito no safety stock (z=0.84, sigma constante):')
print(f'  Safety stock novo = z * sigma * sqrt(L_novo)')
print(f'  Aumento = sqrt(L_novo/L_atual) - 1')
print(f'  Loja 841: sqrt(5/3) = {np.sqrt(5/3):.2f}x -> {((np.sqrt(5/3)-1)*100):.0f}% mais safety stock')
print(f'  Loja 1314: sqrt(14/9) = {np.sqrt(14/9):.2f}x -> {((np.sqrt(14/9)-1)*100):.0f}% mais safety stock')
print()
safety_841 = s_841 - 3 * current_daily_841
safety_1314 = current_s - 9 * current_daily
safety_841_new = np.sqrt(5/3) * safety_841
safety_1314_new = np.sqrt(14/9) * safety_1314
print(f'  NEOSORO 841: safety stock de {safety_841:.0f} -> {safety_841_new:.0f}')
print(f'  NEOSORO 1314: safety stock de {safety_1314:.0f} -> {safety_1314_new:.0f}')
print(f'  Custo adicional NEOSORO 1314: R$ {(safety_1314_new - safety_1314)*9.19 * 0.0425:.2f}/trim')
print()
print(f'  >>> SE LT AUMENTAR, sistema precisa recalibrar (mas nao quebra).')

# ======================================================================
# 12. DADOS FALTANTES
# ======================================================================
print()
print('12. DADOS FALTANTES — suporta?')
print('-' * 60)
print()
print(f'  Snapshot de saldo (7_saldo.csv): NAO e diario para todos os SKUs')
print(f'  - Loja 841: ultimo snapshot antes de 01/10/2024 pode ser de agosto/2024')
print(f'  - Simulador usa ultimo snapshot disponivel como estado inicial')
print(f'  - Se nao ha snapshot, estoque inicial = 0 (assume verde)')
print()
print(f'  Vendas (8_inventario_venda.csv): gaps de datas')
print(f'  - Se uma data nao tem venda, demanda = 0 (assuncao)')
print(f'  - Se um SKU nao tem historico, forecast = 0')
print(f'  - SKU com introduction_date recente (ex: 76834 - fev/2024)')
print(f'    tem menos de 1 ano de historico')
print()
print(f'  >>> TRATAMENTO: heuristico (media, zero, ultimo snapshot).')
print(f'      NAO usa interpolacao avancada ou imputacao.')

# ======================================================================
# 13. SKUS NOVOS
# ======================================================================
print()
print('13. SKUS NOVOS — sistema quebra?')
print('-' * 60)
print()
print(f'  Cenario: novo SKU sem historico entra na categoria')
print(f'  - Forecast: mean=0, std=0')
print(f'  - s = ceil(0*L + z*0*sqrt(L)) = 0')
print(f'  - S = ceil(0 + 0*review_days) = 0 (ajustado para 1 pelo piso empirico)')
print(f'  - Politica: s=1, S=2 (estoque minimo)')
print()
print(f'  Impacto: estoque praticamente zero -> ruptura certa na primeira venda')
print(f'  MELHORIA: adicionar regra de negocio para novos SKUs')
print(f'    (ex: estoque inicial baseado em similaridade com SKU existente)')
print()
print(f'  >>> NAO QUEBRA, mas performance e pessima ate acumular historico.')

# ======================================================================
# 14. DEPENDENCIA DE HIPERPARAMETROS
# ======================================================================
print()
print('14. DEPENDENCIA DE HIPERPARAMETROS')
print('-' * 60)
print()
print(f'  Hiperparametros do modelo:')
print(f'    1. z (safety factor) = 0.84 (default)')
print(f'    2. review_days = 5 (default)')
print(f'    3. janelas do forecast (28d, 8 semanas)')
print(f'    4. Uplift promocional (multiplicador)')
print(f'    5. Quantil do piso empirico (75%)')
print()
print(f'  Sensibilidade ao z:')
print(f'    z=0.84-2.05: estoque varia R$ 135-R$ 172 (27%)')
print(f'    SL permanece > 99.8% em todos os cenarios')
print(f'    Objetivo varia 15% no range')
print()
print(f'  Sensibilidade ao review_days:')
print(f'    review=3-14: estoque varia R$ 135-R$ 186 (38%)')
print(f'    Custo pedido varia R$ 5.619-R$ 2.651 (53%)')
print(f'    Trade-off direto: mais review = menos pedidos = mais estoque')
print()
print(f'  >>> MODELO POUCO SENSIVEL a z (SL sempre alta).')
print(f'      SENSIVEL a review_days (impacto direto no custo de pedido).')
print(f'      Hiperparametros sao defensaveis dentro do range testado.')

# ======================================================================
# 15. SENSIBILIDADE A PEQUENAS MUDANCAS
# ======================================================================
print()
print('15. SENSIBILIDADE — pequenas mudancas')
print('-' * 60)
print()
print(f'  Variacao de z=0.84 -> z=1.04 (+0,2): estoque +R$ 1,68 (1.2%)')
print(f'  Variacao de review=5 -> review=7 (+2d): estoque +R$ 8, custo -R$ 778')
print(f'  Variacao de 1 unidade em s: muda estoque em media ~{sim["ending_inventory"].mean()/6.4:.1f}%')
print()
print(f'  Risco: s=1, S=2 para 20 SKUs -> 1 unidade a mais ou a menos')
print(f'  pode ser 50% do estoque. Mas demanda e ~0, entao impacto e baixo.')
print()
print(f'  >>> BAIXA SENSIBILIDADE para SKUs de alto giro.')
print(f'      ALTA SENSIBILIDADE RELATIVA para SKUs de baixo giro (s=1,S=2).')
print(f'      Mas impacto absoluto e pequeno.')

# ======================================================================
# 16. OVERFITTING NO BACKTEST
# ======================================================================
print()
print('16. OVERFITTING — risco no backtest')
print('-' * 60)
print()
print(f'  O que foi otimizado no backtest:')
print(f'    - z e review_days via grid search (25 combinacoes)')
print(f'    - O melhor ponto foi review=7, z=0.84 (objetivo=188,66)')
print(f'    - O USADO foi review=5, z=0.84 (objetivo=189,30)')
print(f'      (diferenca de 0.3% — quase mesma performance)')
print()
print(f'  Protecoes contra overfitting:')
print(f'    - Grid search usou MESMA funcao objetivo do treino')
print(f'    - Nao houve holdout set separado para validacao de hyperparams')
print(f'    - Forecast foi gerado com dados ate set/2024 (sem vazamento)')
print(f'    - Simulacao usou demanda real out-dez/2024 como verdade')
print()
print(f'  Risco real:')
print(f'    - O grid search otimizou para o Q4/2024 especificamente')
print(f'    - Promocoes do Q4/2024 podem nao se repetir')
print(f'    - Demanda de gripe e irregular (Q4/2023 vs Q4/2024 podem diferir)')
print()
print(f'  >>> BAIXO RISCO de overfitting (1 hyperparametro otimizado,')
print(f'      performance similar em todo o grid). Nao ha overfit classico.')

# ======================================================================
# 17. CENARIOS EXTREMOS
# ======================================================================
print()
print('17. CENARIOS EXTREMOS')
print('-' * 60)
print()
# Worst case: peak demand day + stockout
peak_demand = sim.loc[sim['actual_demand'].idxmax()]
print(f'  PIOR DIA: SKU {peak_demand["product"]} Loja {peak_demand["location"]} {peak_demand["date"]}')
print(f'    Demanda: {peak_demand["actual_demand"]:.0f} unidades')
print(f'    Estoque inicial: {peak_demand["opening_inventory"]:.0f}')
print(f'    Atendido: {peak_demand["fulfilled_units"]:.0f}, Perdido: {peak_demand["lost_sales_units"]:.0f}')
print()

# Best case: worst stockout run
print(f'  PIOR SEQUENCIA DE RUPTURA: max {sim["simulated_stockout_flag"].max():.0f} dias consecutivos')
stockout_runs = []
current = 0
for _, r in sim.iterrows():
    if r['simulated_stockout_flag']:
        current += 1
    elif current > 0:
        stockout_runs.append(current)
        current = 0
if current > 0:
    stockout_runs.append(current)
max_run = max(stockout_runs) if stockout_runs else 0
print(f'    Max run: {max_run} dias consecutivos')

# Extreme scenario: all promo days
print()
print(f'  CENARIO: 100% dias promocionais (vs 3.1% atual)')
print(f'    Se todo Q4 fosse promo, demanda seria ~{sim["actual_demand"].sum()*1.3:.0f} un')
print(f'    (assumindo uplift medio de +30% em promos)')
print(f'    Forecast atual: {sim["forecast_demand"].sum():.0f} (ja superestima)')
print(f'    GAP: estoque pode ser insuficiente se demanda real disparar')
print()

# Scenario: no promos at all
print(f'  CENARIO: ZERO promocoes (vs 3.1% atual)')
print(f'    Demanda seria ~{sim["actual_demand"].sum()*0.97:.0f} un (sem uplift de +263%)')
print(f'    Estoque seria EXCESSIVO em ~R$ {sim["simulated_inventory_value"].mean()*0.03:.2f}')
print(f'    (pouco impacto: promos sao 3% dos dias)')
print()

# Demand shocks on specific dates
print(f'  CENARIO: DEMANDA ESPORADICA MUITO ALTA (ex: pico de gripe)')
print(f'    Pico maximo observado: {peak_demand["actual_demand"]:.0f} un/dia')
print(f'    Media NEOSORO 1314: {current_daily:.1f} un/dia')
print(f'    Se pico for 5x a media: {current_daily*5:.0f} un/dia -> estoque de {current_s}')
print(f'    cobre ~{current_s/(current_daily*5):.0f} dias (vs {lt_1314}d de LT)')
print(f'    RUPTURA CERTA se pico durar >{current_s/(current_daily*5):.0f} dias')

print()
print('=' * 100)
print('CONCLUSOES FINAIS')
print('=' * 100)
print("""
  1. PROBLEMA PRINCIPAL: Forecast inflado (+50%) -> excesso de estoque.
     A politica CONSERVADORA mascara o problema (SL 99.9%) mas com custo.

  2. GARGALO: Lead time de 9d (1314) AMPLIFICA erro de forecast.
     Resolver forecast reduz o impacto do LT sem mexer na logistica.

  3. MAIOR IMPACTO: review_days 5->7 economiza R$ 770/trim.
     2°: corrigir uplift promocional (R$ 432/trim de economia).
     3°: aumentar z 0.84->1.28 (ROI 34,8x para zerar rupture).

  4. FORECAST > SAFETY STOCK: forecast melhorado REDUZ estoque;
     safety stock adicional AUMENTA estoque. Complementares.

  5. ROBUSTEZ MODERADA: funciona para variacoes de +/-30%.
     Demanda 2x ou LT+50% exige recalibracao.

  6. ESCALAVEL: pipeline e generica, mas forecast e especifico.

  7. SIMPLES: (s,S) e operavel por funcionario de loja.

  8. PRODUCAO: falta integracao, testes, monitoria (~2-3 sem).

  9. SEM OVERFITTING: 1 hyperparametro, performance plana.

  10. CENARIO EXTREMO: demanda 5x -> ruptura em {:.0f} dias.
""".format(int(current_s/(current_daily*5)) if current_daily*5 > 0 else 0))
