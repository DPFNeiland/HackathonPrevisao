# Relatorio de Correcoes — Bugs, Brechas e Melhorias

## Resumo

| # | Arquivo | Severidade | Tipo | Status |
|---|---------|------------|------|--------|
| 1 | `engine.py:284` | **Critico** | Runtime crash | Corrigido |
| 2 | `engine.py:383-387` | **Alto** | Logica incorreta | Corrigido |
| 3 | `engine.py:714-720` | **Alto** | Comportamento operacional | Corrigido |
| 4 | `engine.py:326` | **Medio** | Vies estatistico | Corrigido |
| 5 | `forecast_q4_2024.py:281` | **Medio** | Vies estatistico (duplicado) | Corrigido |
| 6 | `engine.py:706-709` | **Medio** | Inconsistencia de dado | Corrigido |
| 7 | `tests/test_comprehensive.py` | — | Testes atualizados | Ajustado |

---

## Correcao 1: ZeroDivisionError em `weighted_component_mean`

**Arquivo:** `stock_policy_product/engine.py:284`

**Problema:** Quando todos os componentes com valor nao-NaN tinham peso zero, `total_weight = 0.0`, causando `ZeroDivisionError` no forecast.

**Cenario minimo reprodutivel:**
```python
weighted_component_mean([(0.0, 100.0), (1.0, np.nan)])
# -> ZeroDivisionError: float division by zero
```

**Correcao aplicada:**
```python
def weighted_component_mean(components: list[tuple[float, float]]) -> float:
    usable = [(w, v) for w, v in components if pd.notna(v)]
    if not usable:
        return 0.0
    total_weight = sum(w for w, _ in usable)
    if total_weight == 0.0:   # <-- NOVO: guarda contra peso zero
        return 0.0
    return float(sum(w * v for w, v in usable) / total_weight)
```

**Impacto:** Previne crash do forecast quando todos os componentes de data (ultimos 28d, mesmo dia semana, ano anterior) sao NaN ou tem peso zero.

---

## Correcao 2: ABC Classification — SKU Unico Classificado como 'C'

**Arquivo:** `stock_policy_product/engine.py:383-387`

**Problema:** A funcao `assign_abc_class` classifica um SKU unico com 100% do valor como 'C' porque `cumulative_share = 1.0 > 0.95`, falhando em ambos os thresholds (`<= 0.80` e `<= 0.95`).

**Logica anterior (errada):**
```
cumulative_share = 1.0
1.0 <= 0.80? False  -> nao e A
1.0 <= 0.95? False  -> nao e B
-> C (WRONG)
```

**Correcao aplicada:** Garantia que o SKU de maior valor (primeiro na ordenacao decrescente) recebe sempre classe 'A', independentemente do cumulative_share:
```python
if len(summary) > 0:
    summary.loc[summary.index[0], "abc_class"] = "A"
```

**Impacto:** SKU unico ou SKU dominante (>80% do valor) nao e mais erroneamente classificado como 'C'.

---

## Correcao 3: LT=0 — Pedido com Lead Time Zero Chegava Apenas em D+1

**Arquivo:** `stock_policy_product/engine.py:714-720`

**Problema:** No simulador, quando `lead_time_days = 0`, um pedido feito no dia D tinha `arrival_date = D + 0 = D`. Porem, a logica de recebimento roda ANTES da decisao de pedido no loop diario:

```
Loop do dia D:
  1. Receber pedidos pendentes com arrival == D (nenhum)
  2. Decidir novo pedido -> arrival = D (adiciona a pending_orders)
  3. Consumir demanda
  -> Pedido com LT=0 so sera recebido no dia D+1
```

**Correcao aplicada:** Pedidos com LT=0 sao processados imediatamente — adicionados ao `received_qty` e `opening_inventory` no mesmo dia, sem passar por `pending_orders`:

```python
if order_qty > 0:
    ordering_cost = float(row.cost_of_ordering or 0.0)
    if lead_time_days == 0:
        received_qty += order_qty
        opening_inventory += order_qty
        arrival_date = row.date
    else:
        arrival_date = row.date + pd.Timedelta(days=lead_time_days)
        pending_orders.append((arrival_date, order_qty))
```

**Impacto:** LT=0 agora funciona corretamente: pedido feito no dia D esta disponivel para venda no mesmo dia D. O teste `test_lead_time_zero_same_day_delivery` confirma que as datas de pedido e entrega coincidem.

---

## Correcao 4: `forecast_std` Usava Desvio-Padrao Populacional (ddof=0)

**Arquivos:** `stock_policy_product/engine.py:326` e `forecast_q4_2024.py:281`

**Problema:** O calculo do desvio-padrao da demanda usava `ddof=0` (desvio populacional), que e um estimador viesado para amostras. O correto para forecasting e `ddof=1` (desvio amostral), que e o estimador nao-viesado.

**Antes:**
```python
demand_std = float(overall_recent["corrected_demand"].std(ddof=0))
```

**Depois:**
```python
demand_std = float(overall_recent["corrected_demand"].std(ddof=1))
```

**Impacto:** O desvio-padrao do forecast agora usa o estimador amostral (n-1), resultando em valores ligeiramente maiores (fator ~sqrt(n/(n-1))) que refletem melhor a incerteza real da amostra. O estoque de segurança calculado a partir deste desvio sera marginalmente mais preciso.

---

## Correcao 5: Uso do Lead Time da Politica no Simulador

**Arquivo:** `stock_policy_product/engine.py:706-709`

**Problema:** O simulador usava o `lead_time_days` do painel (dado bruto) em vez do valor da politica, que foi usado no calculo dos parametros (s,S). Se houvesse divergencia entre os dois (e.g., devido a agregacao diferente), o simulador usaria o LT errado para decidir a data de chegada dos pedidos.

**Antes:**
```python
lead_time_days = int(row.lead_time_days or 0)
```

**Depois:**
```python
pref_lt = getattr(row, "lead_time_days_policy", None)
if pref_lt is not None and not (isinstance(pref_lt, float) and np.isnan(pref_lt)):
    lead_time_days = int(pref_lt or 0)
else:
    lead_time_days = int(row.lead_time_days or 0)
```

**Impacto:** O simulador agora prefere o LT da politica (que foi usado em `build_policy` para calcular s e S), garantindo consistencia entre a decisao de reposicao e os parametros. Se o LT da politica nao estiver disponivel, faz fallback para o LT do painel.

---

## Testes Atualizados

| Teste | Antes | Depois |
|-------|-------|--------|
| `test_zero_weight_then_nan_bug` | Documentava crash com `try/except` | Verifica retorno 0.0 sem erro |
| `test_single_sku_bug` | Documentava classificacao 'C' como bug | Verifica classificacao 'A' (corrigida) |
| `test_lead_time_zero_arrival_delayed_bug` | Verificava atraso e imprimia warning | Verifica entrega no mesmo dia (corrigida) |

---

## Test Suite Final

- `tests/test_comprehensive.py` — **85 testes, 0 falhas**
- `tests/test_chaos.py` — **23 testes, 0 falhas**
- Cobertura: unitarios, integracao, regressao, temporais, adversariais
