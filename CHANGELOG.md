# CHANGELOG — Correções de Bugs e Vazamento Temporal

## Resumo

10 bugs corrigidos em 2 arquivos. Pipeline validada com 58 SKU-loja pairs,
service level 99.94%, 0 violacoes S<=s, 23/23 chaos tests passando.

---

## engine.py — 7 correcoes

### 1. simulated_stockout_flag (bug #02 — FALSO POSITIVO DE RUPTURA)
**Linha:** 739  
**Problema:** `simulated_stockout_flag = int(ending_inventory <= 0)` marcava como ruptura
mesmo quando ending_inventory=0 E demand=0. Um dia sem demanda e sem estoque nao e ruptura.  
**Correcao:** `simulated_stockout_flag = int(lost_sales_units > 0)` — so marca ruptura
quando houve demanda nao atendida.  
**Impacto:** Nivel de servico agora reflete corretamente rupturas reais.

### 2. Simulador consumia row.demand em vez de row.corrected_demand (bug #03 — DEMANDA CENSURADA NAO CORRIGIDA)
**Linha:** 696  
**Problema:** O simulador usava a demanda observada (row.demand) para calcular vendas
perdidas. Em dias de ruptura historica, a demanda observada e 0, mas a demanda real
pode ser > 0. Isso subestimava sistematicamente as vendas perdidas.  
**Correcao:** `demand = float(row.corrected_demand or 0.0)` — usa a demanda corrigida
(com substituicao censurada) para calcular fulfilled/lost.  
**Impacto:** Simulacao agora reflete a demanda REAL, nao apenas a observada.

### 3. round_up_to_batch crash com infinity (CHAOS TEST)
**Linha:** 404  
**Problema:** `np.ceil(quantity)` crasha quando `quantity=inf`.  
**Correcao:** `if quantity <= 0 or not np.isfinite(quantity): return 0`  
**Impacto:** Previne crash por corrupcao de dados.

### 4. compute_promo_uplift crash sem promocoes (CHAOS TEST)
**Linhas:** 239-252  
**Problema:** Quando `is_promo=0` em todos os dias de treino, `pivot_table` nao criava
coluna `mean_demand_1`, causando KeyError na divisao `sku_ratio = uplift["mean_demand_1"] / ...`.  
**Correcao:** Verificacao `if "mean_demand_1" in uplift.columns` antes de acessar;
fallback para 1.0 quando nao ha dados promocionais.  
**Impacto:** SKUs sem historico promocional nao quebram mais o pipeline.

### 5. get_initial_balances com NaN no tail (DADOS FALTANTES)
**Linha:** 584  
**Problema:** `.tail(1)` podia retornar uma linha onde `balance` e NaN, e o
`fillna(0)` na linha 604 escondia o problema.  
**Correcao:** `prior = prior.dropna(subset=["balance"])` antes de extrair o saldo inicial.  
**Impacto:** Estoques iniciais NaN sao filtrados e o fallback correto e usado.

### 6. add_censored_demand_adjustment sem baseline (100% RUPTURA)
**Linha:** 193  
**Problema:** Quando 100% dos dias de treino estao em ruptura, `non_stockout` e vazio,
todas as baselines sao NaN, e o fillna cascade chega a 0 — demanda censurada nao recuperada.  
**Correcao:** Se todas as baselines sao NaN, usa a mediana global do treino como fallback.
Se a mediana tambem e NaN ou 0, usa a media global.  
**Impacto:** Corrige o cenario extremo, embora o forecast ainda seja limitado sem dados
nao censurados.

### 7. simulate_policy sem validacao de colunas (CHAOS TEST)
**Linha:** 616  
**Problema:** Se `policy` ou `forecast` nao tivessem colunas obrigatorias, o merge
causava KeyError criptico.  
**Correcao:** Validacao explicita com `ValueError` no inicio da funcao para
`required_forecast_cols` e `required_policy_cols`.  
**Impacto:** Erros de configuracao sao reportados com mensagem clara.

---

## run_stock_policy_product.py — 3 correcoes

### 8. (L01) Grid search com rolling forecast (VAZAMENTO TEMPORAL — CRITICO)
**Linha:** 67  
**Problema:** `default="rolling"` fazia o grid search usar dados futuros (Q3/2024)
para prever o proprio Q3/2024. A selecao de z=0.84 era contaminada.  
**Correcao:** `default="static"` — o forecast agora usa apenas dados ate 30/06/2024
para prever Q3/2024.  
**Impacto:** Parametros de politica (z, review_days) agora sao calibrados sem
vazamento do futuro.

### 9. (L02) Simulacao final Q4 com rolling forecast (VAZAMENTO TEMPORAL — ALTO)
**Linha:** 155  
**Problema:** `forecast=final_forecast_rolling` vazava dados de out-dez/2024
para prever out-dez/2024. O `total_forecast_units` reportado era artificialmente
preciso (~10% superestimado).  
**Correcao:** `forecast=final_forecast_static` — forecast baseado apenas em dados
ate 30/09/2024.  
**Impacto:** Metricas de forecast sao realistas e reproduziveis.

### 10. (L03) Tuning local com rolling forecast (VAZAMENTO TEMPORAL — MEDIO)
**Linha:** 116  
**Problema:** `rolling_forecast=validation_forecast_rolling` contaminava a calibracao
local por SKU.  
**Correcao:** `validation_forecast=validation_forecast_static` — usa forecast estatico
na validacao local.  
**Impacto:** Overrides locais sao calibrados sem contaminacao temporal.

---

## Resultados da Pipeline Apos Correcoes

| Metrica | Valor |
|---------|-------|
| Service Level | 99.94% |
| Avg Inventory Value | R$ 169.78 |
| Total Ordering Cost | R$ 2.629,55 |
| Total Lost Sales | 3 unidades |
| Total Orders | 113 |
| Horizon Days | 92 |
| Series Days | 5.336 |

**Policy.csv:** 58 linhas, 0 violacoes S<=s, 0 NaN.

---

## Cobertura de Testes

23 chaos tests em `tests/test_chaos.py` — 23/23 passando.
Cenarios cobertos: demanda explosiva, demanda zerada, promocoes consecutivas,
lead time extremo, S < s, estoque negativo, SKU sem historico, z invalido,
round_up_to_batch, policy vazia, censura 100%, objective extremos,
warmup insuficiente, lead time zero, demanda fracionaria, datas desalinhadas.
