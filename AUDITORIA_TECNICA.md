# Auditoria Técnica — Hackathon Previsão de Estoque (Q4/2024)

> **Data:** 23/05/2026
> **Auditor:** Revisão exaustiva de todo o código-fonte (`simulator.py`, `forecast_q4_2024.py`, `run_stock_policy_product.py`, `stock_policy_product/engine.py`, `stock_policy_product/reporting.py`) e dados (`data/*.csv`).

---

## Legenda de Severidade

| Selo | Significado |
|------|-------------|
| 🔴 **CRÍTICO** | Quebra o resultado, invalida KPIs ou gera decisões erradas. Deve ser corrigido antes de qualquer entrega. |
| 🟠 **ALTO** | Distorce métricas relevantes ou introduz risco operacional significativo. |
| 🟡 **MÉDIO** | Problema real com impacto limitado no contexto ou que afeta casos específicos. |
| ⚪ **BAIXO** | Questão de qualidade, boas práticas ou documentação. |

---

## 🔴 CRÍTICO 01 — `simulated_stockout_flag` marca falso stockout em dias sem demanda

### Localização
`stock_policy_product/engine.py:739`

```python
simulated_stockout_flag = int(ending_inventory <= 0)
```

### Problema
Se `ending_inventory = 0` e `demand = 0`, o flag é `1` (stockout), mesmo sem demanda a atender. Isso acontece quando o estoque zerou em algum dia anterior e não houve demanda no dia atual — o saldo continua zero, mas não há ruptura porque não há cliente para atender.

### Cenário real (confirmado nos dados)
SKU `13315` (BROMELIN SUSP 100ML) na Loja 1314. Entre 7-nov e 15-nov o estoque simulado ficou em zero. A demanda nesses dias foi zero. O simulador marcou todos como ruptura. Resultado no `sku_metrics.csv`:

```
service_level = 0.8913  (89.13%)
```

Mas a política atendeu TODA a demanda que existia. O nível de serviço verdadeiro deveria ser 100% nesse bloco.

### Impacto
- SKUs de **baixo giro** (muitos dias com demanda = 0) são sistematicamente penalizados
- O `service_level` agregado (`99.53%`) está artificialmente reduzido — o valor real deve ser mais próximo de 100%
- SKUs que aparentam estar abaixo da meta de 92% podem na verdade estar perfeitamente calibrados
- Decisões de calibração (aumentar `z`, aumentar estoque de segurança) são tomadas para resolver um problema que não existe, aumentando capital desnecessariamente

### Solução proposta
A definição correta de ruptura (stockout) é: **houve demanda que não pôde ser atendida**. Portanto o flag deve considerar apenas dias com demanda positiva:

```python
simulated_stockout_flag = int(lost_sales_units > 0)
```

Ou, equivalentemente:

```python
simulated_stockout_flag = int(ending_inventory <= 0 and demand > 0)
```

### Efeito colateral previsto
O `service_level` vai subir. SKUs de giro zero ou próximo de zero podem ir para 100%. O capital médio pode se tornar o principal diferenciador entre políticas na calibração, já que praticamente todas atingirão 92%+ de serviço com menos estoque do que o calibrado atualmente.

---

## 🔴 CRÍTICO 02 — Simulador consome demanda censurada, não a demanda corrigida

### Localização
`stock_policy_product/engine.py:696-699`

```python
demand = float(row.demand or 0.0)
fulfilled_units = min(opening_inventory, demand)
lost_sales_units = max(demand - opening_inventory, 0.0)
```

### Problema
O campo `row.demand` é a demanda **observada** (vendas reais registradas no CSV). Em dias históricos de ruptura (`actual_stockout_flag = 1`), a demanda observada é **menor que a demanda real** porque faltou produto — é o fenômeno de **demanda censurada**. O código criou `row.corrected_demand` exatamente para corrigir isso, mas o simulador nunca a utiliza.

### Cenário
Dia histórico com estoque zerado às 10h da manhã. Venda observada = 3 unidades. Demanda real estimada = 8 unidades. O simulador consome apenas `demand = 3`:

- `fulfilled_units = min(opening_inventory, 3) = 3`
- `lost_sales_units = max(3 - inventory, 0)`

Se a política tivesse estoque, atenderia 8, não 3. O simulador subestima a demanda que a política realmente enfrentaria.

### Impacto
- **Viés otimista**: a política parece funcionar melhor do que funcionaria na realidade
- A calibração encontra parâmetros (`z`, `review_days`) que são insuficientes para a demanda real, mas parecem adequados porque a demanda de teste é censurada
- O forecast também é afetado: treina em dados censurados (embora `corrected_demand` seja usado no forecast, a demanda real consumida na simulação é a observada)
- A diferença entre o `service_level` simulado e o real (`service_level_delta_vs_actual = 0.0039`) pode ser artificialmente pequena porque ambos usam demanda censurada

### Solução proposta
Substituir o consumo de demanda observada por demanda corrigida:

```python
demand = float(row.corrected_demand or 0.0)
```

### Observações importantes
- A correção de censura em `add_censored_demand_adjustment` usa `max(observado, baseline)` que é uma heurística. Em dias sem ruptura, `corrected_demand = demand`, então não há impacto para a maioria dos dias.
- Implementar essa correção pode fazer o `service_level` cair ou o capital subir (porque a demanda a atender é maior). É esperado e desejável — é o trade-off real.
- Uma abordagem mais robusta seria usar modelos de correção de censura (ex: imputação por regressão ou distribuição truncada), mas o `max(obs, baseline)` é aceitável para o escopo do hackathon.

---

## 🔴 CRÍTICO 03 — `get_initial_balances` retorna NaN e silenciosamente vira zero

### Localização
`stock_policy_product/engine.py:577-605`

### Problema
O `balance` no painel diário é `NaN` na maioria dos dias (dado de snapshot esparso — o CSV `7_saldo.csv` tem apenas algumas datas). A função `get_initial_balances` busca a **última linha antes de `simulation_start`** usando `.tail(1)`. Se essa última linha (que pode ser de uma data com venda mas sem snapshot) tiver `balance = NaN`, o `initial_balance` vira `NaN`. Depois, `initial["initial_balance"].fillna(0)` silenciosamente transforma em `0`.

### Caminho crítico
1. `simulation_start = 2024-10-01 - 45 dias = 2024-08-17` (para warmup=45)
2. `panel[panel["date"] < "2024-08-17"]` encontra todas as linhas antes de 17-ago
3. `.tail(1)` pega a última linha (mais recente antes de 17-ago)
4. Se essa linha não tem snapshot de saldo (comum, pois `7_saldo.csv` é esparso), `balance = NaN`
5. `fallback` tenta buscar `balance` em `2024-08-17` exato — igualmente sem snapshot
6. `initial_balance = 0`

### Cenário real
SKU `62782` (HEDERA CIMED CEREJA) na Loja 841. Último snapshot conhecido em `7_saldo.csv` é de julho/2024 com `balance = 2`. O snapshot mais recente no painel antes de 2024-08-17 é de uma data de julho que TEM snapshot, então funciona. Mas para SKUs cujo último snapshot foi em junho e a última linha do painel antes de simulation_start é de agosto (sem snapshot), o initial_balance vira 0. SKU `42076` na Loja 1314 — último snapshot conhecido pode estar distante; risco alto.

### Impacto
- SKU começa simulação com estoque 0 quando na verdade tinha estoque real
- Primeiros dias de simulação podem ter ruptura artificial (estoque 0 + demanda > 0)
- O primeiro pedido é emitido imediatamente (posição = 0 ≤ s), potencialmente superdimensionado
- O capital médio simulado nos primeiros dias é subestimado (estoque 0 → valor 0)

### Solução proposta
Garantir que `initial_balance` use apenas linhas com `balance` não-NaN:

```python
valid_prior = panel[
    (panel["date"] < simulation_start) & (panel["balance"].notna())
].sort_values(["location", "product", "date"])
prior = valid_prior.groupby(["location", "product"], as_index=False).tail(1)
```

E no fallback, também filtrar por `balance.notna()`:

```python
fallback = (
    panel[panel["date"] == simulation_start & panel["balance"].notna()]
    .merge(missing_pairs, on=["location", "product"], how="inner")
)
```

---

## 🔴 CRÍTICO 04 — `actual_avg_inventory_value` e `avg_inventory_value` são incomparáveis

### Localização
`stock_policy_product/engine.py:767-773`

```python
avg_inventory_value = float(simulation["simulated_inventory_value"].mean())
actual_avg_inventory_value = float(simulation["actual_inventory_value"].mean())
```

### Problema
- `simulated_inventory_value` existe para **todos os 92 dias** do Q4 (é calculado dia a dia no simulador)
- `actual_inventory_value` existe **apenas nos dias com snapshot de saldo** (~15-30 dias por SKU)
- `pandas.Series.mean()` por padrão **exclui NaN**
- `avg_inventory_value` = média de 92 dias
- `actual_avg_inventory_value` = média de ~20 dias (apenas com snapshot)

As duas métricas estão em bases amostrais completamente diferentes. O delta reportado (`inventory_value_delta_vs_actual = R$ 8,14`) é enganoso — pode ser positivo ou negativo dependendo de quais dias têm snapshot.

### Cenário verificado
Para SKU `18064` (NEOSORO) na Loja 841:
- `avg_inventory_value` (simulado, 92 dias) = R$ 169,52
- `actual_avg_inventory_value` (real, ~15-30 dias) = R$ 368,41
- Delta = **-R$ 198,90** (a política parece reduzir capital em 54%)

Mas esse delta pode ser inteiramente explicado pelo fato de que os dias com snapshot de saldo real são diferentes dos dias simulados. Se os snapshots reais ocorrem em dias de pico de estoque (após entrega), a média real artificialmente sobe.

### Impacto
- Relatórios e pitch podem usar métricas incomparáveis para "provar" redução de capital
- A tomada de decisão olha para o delta e interpreta como ganho quando pode não ser
- SKUs com poucos snapshots (ex: loja 1314) têm diferenças ainda maiores

### Solução proposta
Calcular ambos os valores **apenas nos dias com snapshot disponível**:

```python
has_actual = simulation["actual_balance"].notna()
comparable_avg_sim = simulation.loc[has_actual, "simulated_inventory_value"].mean()
comparable_avg_actual = simulation.loc[has_actual, "actual_inventory_value"].mean()
```

E reportar ambas as versões: (a) média completa simulada, (b) média comparável nos dias com snapshot. Adicionar nota explicativa.

---

## 🔴 CRÍTICO 05 — Duplicação completa do pipeline de forecast (2 codebases independentes)

### Localização
- `forecast_q4_2024.py` (398 linhas, funções: `resolve_data_dir`, `load_products`, `load_sales`, `load_balances`, `load_promotions`, `build_daily_panel`, `add_censored_demand_adjustment`, `compute_promo_uplift`, `weighted_component_mean`, `forecast_group`, `build_forecast`, `build_policy_inputs`)
- `stock_policy_product/engine.py` (as mesmas funções reimplementadas)

### Problema
As funções acima existem em AMBOS os arquivos com lógica similar mas implementações independentes. Diferenças identificadas:

| Aspecto | `engine.py` | `forecast_q4_2024.py` |
|---------|-------------|----------------------|
| Horizonte | Objeto `Horizon` (parametrizável) | Constantes globais (`TRAIN_END`, `Q4_START`, `Q4_END`) |
| Colunas extras | `sales_value`, `balance_value`, `campaign_type`, `location_name`, `supplier` | Não tem |
| Agrupamento forecast | `groupby(["location", "product"], sort=True)` | `groupby(["location", "product"], sort=True)` (igual) |
| `load_products` output | Inclui `supplier`, `product_group`, `sales_price` | Apenas básico |

### Impacto
- **Deriva garantida**: um bug corrigido em um arquivo não se propaga ao outro
- `forecast_q4_2024.py` não pode ser usado como biblioteca — só roda via CLI
- Diferenças podem gerar resultados inconsistentes entre os dois pipelines
- Custo de manutenção dobra sem benefício

### Solução proposta
**Eliminar `forecast_q4_2024.py` e refatorar para ser um wrapper CLI sobre `engine.py`:**

```python
# forecast_q4_2024.py → script fino que chama engine
from stock_policy_product.engine import (
    Horizon, prepare_enriched_panel, build_forecast, build_policy_inputs
)

def main():
    # CLI args apenas, toda lógica delega para engine
    panel = prepare_enriched_panel(data_dir, horizon_end, train_end)
    forecast = build_forecast(panel, horizon, mode)
    policy_inputs = build_policy_inputs(forecast)
    ...
```

---

## 🟠 ALTO 06 — Validador de submissão (`simulator.py`) usa forecast stub com zeros

### Localização
`simulator.py:86-93,155-157`

```python
def build_forecast_stub(panel, horizon):
    stub = panel[(panel["date"] >= horizon.start) & (panel["date"] <= horizon.end)][
        ["date", "location", "product"]
    ].copy()
    stub["forecast_demand"] = 0.0
    stub["forecast_std"] = 0.0
    stub["promo_uplift"] = 1.0
    return stub

# ...
forecast_stub = build_forecast_stub(panel, q4_horizon)
simulation = simulate_policy(panel=panel, forecast=forecast_stub, ...)
```

### Problema
Quando `simulator.py` é usado para validar uma submissão externa de `policy.csv`, ele injeta forecast zero no simulador. O `overall_metrics.json` resultante reporta:

```json
"total_forecast_units": 0.0,
"total_actual_units": 1225.0
```

A simulação funciona porque o `forecast_demand` não é usado para decisões de pedido (apenas como campo informativo). Mas quem lê o relatório vê `forecast = 0` vs `demanda = 1225` e pode concluir que o forecast é péssimo — quando na verdade é que o forecast não foi gerado.

### Impacto
- Relatório de validação enganoso
- Se o `simulator.py` for usado para debugging, dados de forecast não ajudam
- Difícil saber se o erro está no forecast ou no simulador

### Solução proposta
**Opção A (recomendada):** Gerar forecast de verdade dentro do validador, usando as mesmas funções de `engine.py`.

```python
from stock_policy_product.engine import build_forecast, Horizon
real_forecast = build_forecast(panel, horizon=q4_horizon, mode="static")
simulation = simulate_policy(panel=panel, forecast=real_forecast, ...)
```

**Opção B (mínima):** Remover `total_forecast_units` e `total_actual_units` dos outputs quando forecast é stub, ou marcar como "não disponível".

---

## 🟠 ALTO 07 — Agregações com `max` mascaram dados corrompidos

### Localização
`stock_policy_product/engine.py:389-393`

```python
.agg(
    lead_time_days=("lead_time_days", "max"),
    purchase_price=("purchase_price", "max"),
    sales_price=("sales_price", "max"),
    cost_of_ordering=("cost_of_ordering", "max"),
    minimum_delivery_batch=("minimum_delivery_batch", "max"),
)
```

### Problema
Se houver duas linhas no forecast com preços DIFERENTES para o mesmo SKU-loja (por erro de merge, dados corrompidos, inconsistência no CSV fonte), o `max` escolhe o maior preço **silenciosamente**. Nenhum aviso, nenhum erro, nenhum rastro.

### Cenário hipotético
Se `2_produtos_locais.csv` tiver dois registros conflitantes para o mesmo produto-loja (ex: preço de compra diferente por data de introdução), o `max` pega o maior. O `reorder_point_s` e `order_up_to_S` são calculados com o preço errado, e o capital médio reportado fica incorreto.

### Impacto
- Fragilidade silenciosa — dados corrompidos passam despercebidos
- Impacto financeiro: capital médio pode ser superestimado ou subestimado
- Difícil de debugar porque não há log

### Solução proposta
Adicionar validação explícita de consistência:

```python
def validate_constant(series, col_name):
    unique = series.dropna().unique()
    if len(unique) > 1:
        warnings.warn(f"{col_name} has {len(unique)} distinct values for group: {unique}")
    return unique[0] if len(unique) > 0 else np.nan
```

Ou usar `first` em vez de `max` (assume que são iguais):

```python
purchase_price=("purchase_price", "first"),
```

---

## 🟠 ALTO 08 — Rolling forecast no Q4 tem vazamento temporal (dados do período de avaliação)

### Localização
`run_stock_policy_product.py:132,154-158`

```python
final_forecast_rolling = build_forecast(final_panel, horizon=final_horizon, mode="rolling")
# ...
simulation = simulate_policy(
    panel=final_panel,
    forecast=final_forecast_rolling,  # vazamento
    ...
)
```

### Problema
O forecast em modo `rolling` para o dia D (ex: 15-nov-2024) do Q4 usa dados de **dias anteriores do próprio Q4** (out-nov 2024). Por exemplo:

```
Forecast 15-nov = f(vendas de 01-out a 14-nov)
```

Isso é vazamento temporal porque o avaliador está usando dados do período de avaliação para fazer previsões dentro do mesmo período. Na vida real, em 15-nov você não teria os dados de out-nov completos (depende da latência dos dados, mas no mínimo não teria os dados de novembro).

### Mitigação atual (e por que é insuficiente)
O código usa **política estática** (determinada antes do Q4) e o forecast rolling é apenas informativo nos outputs da simulação. A política em si não se beneficia do vazamento. Mas:

- O `forecast_demand` no CSV de saída parece ser um forecast legítimo (sem ressalvas claras)
- Alguém analisando os resultados pode pensar que o modelo é melhor do que realmente é
- Métricas como `total_forecast_units = 1623.68` vs `total_actual_units = 1225.0` estão contaminadas

### Solução proposta
**Usar `final_forecast_static` na simulação do Q4.** O forecast rolling pode ser gerado apenas para relatórios internos (análise de como o forecast teria evoluído), mas não deve ser o forecast oficial da simulação.

```python
simulation = simulate_policy(
    panel=final_panel,
    forecast=final_forecast_static,  # sem vazamento
    ...
)
```

E gerar o rolling apenas para análise exploratória, não para o pipeline principal.

---

## 🟠 ALTO 09 — Piso empírico instável para SKUs com poucas observações

### Localização
`stock_policy_product/engine.py:497-516`

```python
lead_windows = demand.rolling(lead, min_periods=1).sum()
lead_windows = lead_windows[lead_windows > 0]
floor_s = int(np.ceil(lead_windows.quantile(reorder_quantile))) if not lead_windows.empty else 0
```

### Problema
Para SKUs com vendas esparsas (ex: 5 dias de venda no período de treino), `lead_windows` tem apenas 5 valores. O quantil 75% de 5 valores é extremamente sensível:

- 5 valores ordenados: `[0, 0, 2, 0, 3]`
- Quantil 75% ≈ 2,25 → ceil = 3
- Se um dos valores mudar de 0 para 1: quantil 75% ≈ 2,5 → ceil = 3 (ou 2)
- Alta variância, nenhuma estabilidade

### Cenário real
SKU `42076` (HEDRA EXPECT XAROPE) na Loja 1314. Demanda total no Q4 = 0. Piso empírico pode sugerir `s = 1` ou `s = 0` dependendo de pequenas flutuações nos dados de treino. A política final tem `s = 1, S = 2` — pode ser excessivo para um item com demanda zero.

### Impacto
- SKUs de baixíssimo giro recebem pisos arbitrários
- Capital desnecessário imobilizado para itens que talvez nunca vendam
- Instabilidade: reexecutar o pipeline pode gerar políticas diferentes para os mesmos SKUs

### Solução proposta
Requerir um número mínimo de observações para calcular o quantil:

```python
MIN_OBS = 10
if len(lead_windows) >= MIN_OBS:
    floor_s = int(np.ceil(lead_windows.quantile(reorder_quantile)))
else:
    floor_s = 0  # ou usar regra simplificada: max observado no lead time
```

E documentar nos relatórios quais SKUs usaram piso empírico vs. piso zero.

---

## 🟠 ALTO 10 — Thresholds arbitrários no uplift promocional

### Localização
`stock_policy_product/engine.py:240-247`

```python
sku_valid = (uplift["days_1"] >= 3) & (uplift["days_0"] >= 20) & np.isfinite(sku_ratio)
store_valid = (
    (uplift["store_days_1"] >= 10)
    & (uplift["store_days_0"] >= 40)
    & np.isfinite(store_ratio)
)
```

### Problema
Os thresholds `days_1 >= 3` e `days_0 >= 20` são valores fixos sem justificativa estatística:

- SKU com **2 dias** de promoção que mostram uplift de 3x não recebe ajuste (não passa do threshold)
- SKU com **3 dias** de promoção que mostram uplift de 1.1x recebe ajuste (passa do threshold)
- Loja 841 tem menos promoções vinculadas que loja 1314 — mais SKUs da loja 841 caem no fallback `store_valid`, que por sua vez tem thresholds ainda mais altos (`store_days_1 >= 10`)
- SKUs com `mean_demand_0 = 0` geram `sku_ratio = inf`, que é corretamente filtrado por `np.isfinite`
- SKUs com `mean_demand_1 = 0` geram `sku_ratio = 0`, que É finito e pode passar no threshold se tiver dias suficientes — resultado: uplift = 0, que depois é `clip(lower=1.0)` → 1.0 (sem efeito). OK, mas confuso.

### Cenário verificado
SKU `18064` (NEOSORO) — 31 dias de promoção no Q4. `promo_uplift` calculado corretamente porque tem muitos dias de histórico promocional. Mas SKU `76834` (introduzido em 2024) tem menos de 8 meses de dados — provavelmente `days_1 < 3` e cai no fallback genérico.

### Solução proposta
- Usar intervalo de confiança ou teste t para determinar se o uplift é estatisticamente significativo, em vez de thresholds fixos
- Ou usar thresholds relativos ao total de dias do SKU (ex: `days_1 >= 10%` dos dias de treino)
- Documentar claramente o fallback e quantos SKUs usam cada nível (SKU-level vs store-level vs 1.0)

---

## 🟡 MÉDIO 11 — SKU 76834 (introduzido em 2024) com série histórica insuficiente

### Localização
`data/2_produtos_locais.csv:87` + todo o pipeline de forecast

### Problema
SKU `76834` (SORINAN ADULTO 0,5MG SOL NASAL 30ML) foi introduzido em **2024-02-08**. Até a data de treino (2024-09-30), tem menos de 8 meses de histórico.

Componentes do forecast afetados:

| Componente | Problema |
|------------|----------|
| `dow_baseline` (mediana por dia da semana) | < 8 observações por dia da semana — instável |
| `last_year_window` (date - 372 a -358 dias) | **Não existe** — produto não existia em 2023 |
| `same_weekday.tail(8)` | Pode funcionar com <8 se houver dados |
| `promo_uplift` | `days_1` provavelmente < 3 → fallback store-level |

### Impacto
- Forecast para esse SKU é de baixíssima confiança
- Política pode ser muito conservadora (estoque alto) ou muito agressiva (estoque baixo)
- Piso empírico e sazonal não funcionam (poucos dados históricos)

### Solução proposta
- Identificar SKUs com `introduction_date` > 12 meses antes de `train_end`
- Para esses SKUs, usar abordagem alternativa:
  - Forecast baseado em store average (pooling entre SKUs similares)
  - Política com `z` mais conservador (maior estoque de segurança)
  - Marcar explicitamente nos relatórios como "baixa confiança"

---

## 🟡 MÉDIO 12 — `std(ddof=0)` em vez de `ddof=1` para desvio padrão

### Localização
`stock_policy_product/engine.py:312`

```python
demand_std = float(overall_recent["corrected_demand"].std(ddof=0))
```

### Problema
`ddof=0` calcula desvio padrão **populacional** (divide por N). O correto para uma amostra de 56 dias seria `ddof=1` (divisão por N-1), que é o estimador não-viesado da variância populacional.

Diferença: `σ_pop = σ_amostral * √(55/56) ≈ σ_amostral * 0.991`. O estoque de segurança é `z * σ * √L`. Com `z = 0.84` e `L = 9`:

- `σ_pop * √9 = σ_pop * 3`
- `σ_amostral * √9 = σ_amostral * 3`
- Diferença relativa: 0.9%

### Impacto
- Estoque de segurança sistematicamente 0.9% menor que o teoricamente correto
- Desprezível na prática (~0.2 unidades para NEOSORO)
- Mas conceitualmente incorreto e facilmente corrigível

### Solução proposta
```python
demand_std = float(overall_recent["corrected_demand"].std(ddof=1))
```

---

## 🟡 MÉDIO 13 — Capital em trânsito não incluído no valor do estoque

### Localização
`stock_policy_product/engine.py:702`

```python
simulated_inventory_value = ending_inventory * purchase_price
```

### Problema
O capital imobilizado em estoque inclui não apenas o que está na prateleira, mas também o que foi pago e está em trânsito. Se um pedido de R$ 1.000 foi feito mas ainda não chegou, a empresa já comprometeu R$ 1.000.

A métrica atual contabiliza apenas `ending_inventory * purchase_price`. O `on_order_after` (unidades em trânsito) não é valorado.

### Cenário
SKU `18064` (NEOSORO) na Loja 1314. `cost_of_ordering = R$ 4,28`, `purchase_price = R$ 8,93`. Um pedido de 200 unidades (R$ 1.786 em trânsito) não aparece no capital médio. Com lead time de 9 dias, esse valor fica "invisível" por mais de uma semana.

### Impacto
- `avg_inventory_value` subestima o capital real imobilizado
- A otimização pode tender a pedidos maiores (economiza `cost_of_ordering`) sem ver o custo de capital dos itens em trânsito
- O trade-off serviço vs capital é distorcido

### Solução proposta
Incluir o valor do estoque em trânsito:

```python
total_inventory_value = (ending_inventory + on_order_after) * purchase_price
```

E reportar ambas as métricas (`physical_inventory_value` e `total_inventory_value`) para comparação.

---

## 🟡 MÉDIO 14 — Uplift promocional usa `corrected_demand` que pode estar inflado por censura

### Localização
`stock_policy_product/engine.py:208-209`

```python
sku_stats = train.groupby(["location", "product", "is_promo"]).agg(
    mean_demand=("corrected_demand", "mean"), days=("date", "size")
)
```

### Problema
O `corrected_demand` substitui demanda censurada por `max(observado, baseline)`. Se um dia de promoção teve ruptura (estoque zerou, demanda censurada), a correção pode inflar a demanda naquele dia. Isso afeta o cálculo do uplift promocional:

- Demanda real no dia de promoção com ruptura: 10
- Demanda observada: 5
- Baseline: 7
- `corrected_demand = max(5, 7) = 7` (ainda subestima os 10 reais)
- Média de promoção com correção: 7 (vs. 10 real)

O uplift fica artificialmente baixo porque a correção de censura é imperfeita.

### Solução proposta
Separar os dois tratamentos:

1. Calcular **uplift** apenas em dias SEM ruptura (`actual_stockout_flag = 0`)
2. Aplicar **correção de censura** apenas para o forecast de dias futuros

```python
clean_train = train[train["actual_stockout_flag"] == 0]
sku_stats = clean_train.groupby(["location", "product", "is_promo"]).agg(...)
```

---

## ⚪ BAIXO 15 — Condicional redundante na filtragem de histórico do forecast

### Localização
`stock_policy_product/engine.py:280-283`

```python
if mode == "rolling":
    hist = group[group["date"] < row.date].copy()
else:
    hist = static_history

hist = hist[hist["date"] <= history_end if mode == "static" else hist["date"] < row.date]
```

### Problema
A segunda filtragem é redundante em ambos os modos:

- **`mode == "rolling"`**: `hist` já é `group[group["date"] < row.date]`, e a segunda linha aplica `hist["date"] < row.date` novamente — mesma condição
- **`mode == "static"`**: `hist` já é `static_history = group[group["date"] <= horizon.train_end]`, e a segunda linha aplica `hist["date"] <= history_end` onde `history_end == horizon.train_end` — mesma condição

Código confuso, sem impacto funcional.

### Solução proposta
Simplificar:

```python
if mode == "rolling":
    hist = group[group["date"] < row.date].copy()
else:
    hist = static_history.copy()
```

---

## ⚪ BAIXO 16 — Tabulação não sanitizada em campanhas promocionais

### Localização
`data/4_campanhas.csv:19`

```
2024-09-28;2024-10-01;\t(MAIS É MENOS) GENERICO 30% ...;183589;PAGUE E LEVE
```

### Problema
Caractere tab (`\t`) no início do nome da campanha. É propagado para `campaign_type` e `name` no painel diário.

### Impacto
- Não afeta cálculos (separador CSV é `;`, tab está dentro de campo)
- Polui relatórios HTML com nomes "sujos"
- Pode afetar agrupamentos se `campaign_type` for usado como chave

### Solução proposta
Sanitizar ao carregar:

```python
campaigns["name"] = campaigns["name"].str.strip()
campaigns["type"] = campaigns["type"].str.strip()
```

---

## ⚪ BAIXO 17 — `stock_policy_product/__init__.py` incompleto

### Localização
`stock_policy_product/__init__.py`

```python
from .engine import Horizon, build_policy, build_sku_metrics, build_summary_from_forecast
```

### Problema
O `__init__.py` exporta apenas 4 dos 14+ símbolos públicos de `engine.py`. Funções essenciais como `simulate_policy`, `build_forecast`, `build_overall_metrics`, `search_policy_parameters`, `tune_local_sku_overrides`, `apply_empirical_demand_floors`, `prepare_enriched_panel` não são exportadas.

### Impacto
- `from stock_policy_product import simulate_policy` → **ModuleNotFoundError** (não está em `__all__`)
- Todos os scripts importam diretamente de `stock_policy_product.engine`, ignorando o `__init__.py`
- O `__init__.py` engana quem espera que ele exponha a API pública

### Solução proposta
Exportar todos os símbolos públicos:

```python
from .engine import (
    Horizon, build_forecast, build_policy, build_sku_metrics,
    build_summary_from_forecast, build_overall_metrics,
    simulate_policy, search_policy_parameters, tune_local_sku_overrides,
    apply_empirical_demand_floors, prepare_enriched_panel,
    resolve_data_dir,
)
```

---

## ⚪ BAIXO 18 — Nomenclatura inconsistente: `cover_days_grid` vs `review_days`

### Localização
`run_stock_policy_product.py:102`

```python
z_grid=[...],
cover_days_grid=[3, 5, 7, 10, 14],
```

### Problema
O sistema usa `review_days` como nome do parâmetro em todo o pipeline. A variável do grid search se chama `cover_days_grid`. A nomenclatura inconsistente dificulta a leitura e manutenção.

---

## ⚪ BAIXO 19 — `policy.csv` gerado não usa ponto e vírgula como separador

### Localização
`stock_policy_product_output/policy.csv`

```
product,location,reorder_point_s,order_up_to_S
18064,1314,180,339
```

### Problema
O enunciado do desafio pode esperar separador `;` (como os CSVs de entrada). O arquivo atual usa `,`. Pode ser rejeitado na submissão.

### Solução proposta
Verificar o formato esperado da submissão. Se for `;`, alterar:

```python
final_policy_export.to_csv(output_dir / "policy.csv", index=False, sep=";")
```

---

## 🔴 CRÍTICO 20 — Pedidos emitidos no warmup podem ter `arrival_date` antes do Q4 mas `ordering_cost` contabilizado

### Localização
`stock_policy_product/engine.py:688-691,756-758`

### Fluxo
1. Durante warmup (ex: dia 2024-08-20), um pedido é emitido com `lead_time = 9`
2. `arrival_date = 2024-08-29` (ainda warmup)
3. `ordering_cost = R$ 50,00` registrado na linha
4. Filtro `simulation[simulation["in_evaluation_window"] == 1]` remove linhas do warmup
5. Esse pedido não aparece no output → custo NÃO contabilizado

### Problema
Pedidos feitos durante warmup que chegam também durante warmup **não aparecem** no output final (linhas removidas). Mas eles são parte do custo operacional para estabelecer o estoque inicial. Se o warmup é de 45 dias e o lead time é de 9 dias, os primeiros 9 dias de warmup podem gerar pedidos que chegam antes do Q4.

**Por que isso NÃO é um bug grave:** O warmup serve para estabilizar o estoque inicial. Os pedidos feitos durante warmup que chegam no Q4 TÊM `in_evaluation_window = 1` e são contabilizados. Apenas pedidos que começam E terminam durante warmup são excluídos.

**Mas:** O `total_ordering_cost` no Q4 não inclui o custo desses pedidos de warmup que foram necessários para atingir o nível de estoque inicial. O custo real de operação seria maior.

### Solução proposta
Mudar o filtro para incluir pedidos que chegam no período de avaliação, em vez de linhas no período de avaliação:

```python
# Incluir linhas onde o pedido foi feito e chega no período
in_period = (simulation["arrival_date"] >= horizon.start) & (simulation["arrival_date"] <= horizon.end)
```

Mas isso exigiria repensar o que é "período de avaliação". Alternativa mais simples: aceitar que o custo de warmup é desprezível para o backtest (45 dias vs 92 dias de avaliação ≈ 33% de custo adicional, mas diluído).

---

## 🔴 CRÍTICO 21 — `build_daily_panel` faz cross join que duplica dados em cada chamada

### Localização
`stock_policy_product/engine.py:143-145`

```python
calendar = pd.date_range(sales["date"].min(), calendar_end, freq="D")
sku_store = products[["product", "location"]].drop_duplicates()
base = sku_store.merge(pd.DataFrame({"date": calendar}), how="cross")
```

### Problema
Cada chamada a `build_daily_panel` recria o calendário completo. A função é chamada **3 vezes** no pipeline: uma para `validation_panel`, uma para `final_panel`, e uma dentro de `tune_local_sku_overrides` (indiretamente em cada `simulate_policy`).

- Cada chamada gera ~42.340 linhas (29 SKUs × 2 lojas × 730 dias)
- O pipeline completo pode gerar 10+ painéis em memória simultaneamente
- Para 58 SKU-loja × 7 z × 4 review_days × 92 dias de validação local ≈ 1.500 simulações, cada uma com seu próprio subset dos dados

### Impacto
- Performance aceitável para o escopo (dados cabem em RAM)
- Mas é ineficiente e não escala para mais lojas/SKUs
- Risco de memory leak em máquinas com pouca RAM (Colab free tier)

### Solução proposta
Criar o painel uma vez e passá-lo como referência, em vez de recriá-lo. Ou usar `merge` incremental em vez de cross join para SKUs sem dados de venda.

---

# Análise de Risco Agregado

## Risco 1 — Viés otimista combinado (CRÍTICO 01 + 02 + 04)

Os três bugs críticos formam um **padrão de otimismo sistemático**:

| Bug | Efeito | Direção |
|-----|--------|---------|
| 01 — Stockout flag conta dias sem demanda | Service level menor que o real | ⬇️ (pessimista) |
| 02 — Demanda censurada no simulador | Demanda enfrentada menor que a real | ⬆️ (otimista) |
| 04 — Capital médio em bases diferentes | Comparação enganosa | ⬆️⬇️ (imprevisível) |

O **BUG 02** é o mais perigoso: ele faz a política parecer mais eficiente do que é, porque enfrenta menos demanda. Combinado com o BUG 01 (que reduz service level artificialmente), o efeito líquido é imprevisível.

**Recomendação:** Corrigir BUG 02 primeiro (demanda censurada), depois BUG 01 (stockout flag), e depois reavaliar o desempenho.

## Risco 2 — Instabilidade de resultados (CRÍTICO 03 + ALTO 09 + MÉDIO 11)

Três bugs criam **instabilidade** nos resultados entre execuções:

| Bug | Efeito |
|-----|--------|
| 03 — Initial balance NaN → 0 | Depende de quais datas têm snapshot |
| 09 — Piso empírico com poucos dados | Sensível a pequenas mudanças nos dados |
| 11 — SKUs com série curta | Forecast varia conforme o período de treino |

Se o pipeline for reexecutado com os mesmos dados, o resultado deve ser determinístico. Mas se os dados de entrada mudarem (ex: novos snapshots de saldo adicionados), os resultados podem mudar drasticamente para SKUs específicos.

**Recomendação:** Corrigir BUG 03 (initial balance) como prioridade, depois BUG 09 (piso empírico).

# Roadmap de Correção Recomendado

## Fase 1 — Correções críticas (impacto imediato nos KPIs)

| Ordem | Bug | Esforço estimado | Impacto |
|-------|-----|------------------|---------|
| 1 | 02 — Demanda censurada no simulador | 1 linha de código | 🔴 |
| 2 | 01 — Stockout flag errado | 1 linha de código | 🔴 |
| 3 | 03 — Initial balance com NaN | 3-5 linhas | 🔴 |
| 4 | 04 — Capital médio incomparável | 5-10 linhas | 🔴 |

## Fase 2 — Correções de integridade

| Ordem | Bug | Esforço estimado | Impacto |
|-------|-----|------------------|---------|
| 5 | 05 — Duplicação de pipeline | Refatoração moderada | 🔴 |
| 6 | 06 — Forecast stub no validador | 3-5 linhas | 🟠 |
| 7 | 07 — Agregações com max | 5-10 linhas | 🟠 |
| 8 | 08 — Vazamento temporal rolling | 1 linha de código | 🟠 |

## Fase 3 — Correções de qualidade

| Ordem | Bug | Esforço estimado | Impacto |
|-------|-----|------------------|---------|
| 9 | 09 — Piso empírico instável | 5 linhas | 🟠 |
| 10 | 10 — Thresholds uplift | 10-15 linhas | 🟠 |
| 11 | 13 — Capital em trânsito | 2 linhas | 🟡 |
| 12 | 14 — Uplift com demanda corrigida | 3 linhas | 🟡 |
| 13 | 12 — ddof=1 no std | 1 linha | 🟡 |
| 14 | 20 — Custo de warmup | 5-10 linhas | 🔴 |

## Fase 4 — Cosméticos e boas práticas

| Ordem | Bug | Esforço estimado |
|-------|-----|------------------|
| 15 | 15 — Condicional redundante | 2 linhas |
| 16 | 16 — Tab sanitization | 2 linhas |
| 17 | 17 — `__init__.py` incompleto | 5 linhas |
| 18 | 18 — Nomenclatura inconsistente | 1 linha |
| 19 | 19 — Separador policy.csv | 1 linha |
| 20 | 21 — Cross join ineficiente | Refatoração média |

---

*Documento gerado em 23/05/2026. Revisão exaustiva de 8 arquivos-fonte, 8 CSVs e múltiplos arquivos de saída.*
