# Pitch de 5 Slides — Política de Reposição (s, S)

---

## Slide 1 — Problema e Objetivo

**Problema:** 29 SKUs de Gripe e Resfriado em 2 lojas com lead times diferentes (3 vs 9 dias). Decidir quanto e quando pedir para cada par SKU × loja no Q4/2024.

**Objetivo:** Nível de serviço ≥ 92% com mínimo capital parado em estoque.

**Restrições:**
- Sem olhar o futuro (backtest temporal — treino até 30/09/2024)
- Lead time CD→loja: 841=Ceres/GO (3d), 1314=Corumbá/MS (9d)
- Pedido no dia d chega em d+LT; usar posição de estoque (físico + trânsito)

---

## Slide 2 — Estratégia

**Pipeline:** 8 CSVs → Painel Diário → Forecast → Política (s,S) → Simulação → KPIs

**Forecast por SKU × loja:**
- Média ponderada 3 pesos (7d, 28d, sazonal Q4/2023) + ajuste dia da semana
- Uplift promocional por campanha
- Correção de censura (dias com estoque=0)

**Política (s, S):**
- `s = ceil(μ × LT + z × σ × √LT)` — ponto de pedido
- `S = ceil(s + μ × review_cover_days)` — nível-alvo
- Calibração: grid search z × review_days no simulador
- **Parâmetros finais:** z=0,84, review=7d (vs 5d inicial), piso empírico 75%

---

## Slide 3 — Resultados Consolidados

| Métrica | Real (loja) | Simulado | Δ |
|---------|:----------:|:--------:|:-:|
| Nível de serviço | 99,14% | **99,94%** | +0,8 pp |
| Estoque médio | R$ 163,27 | **R$ 169,78** | +R$ 6,51 |
| Custo total de reposição | — | **R$ 2.629,55** | — |
| Pedidos emitidos | — | **113** | — |
| Vendas perdidas | — | **3 un (R$ 233,72)** | — |

NS ≥ 92% ✅ — 3 rupturas em 5.336 dias-operacionais (todas em SKUs de alto valor: NEOSORO 841, ABRILAR 1314)

**Diagnóstico-chave:** Forecast 51% acima do real (1.845 vs 1.225 un). Custo do excesso: R$ 1.927/trim — 8× maior que o custo da ruptura (R$ 234).

---

## Slide 4 — Caso NEOSORO (SKU 18064) — 78% da Demanda

**Loja 841 (Ceres, LT=3d):**
- Demanda Q4: 103 un | s=11 | S=33
- 1 ruptura simulada (dia 19/10 — estoque zerou, 1 un perdida)
- Capital médio: R$ 169,52 (vs real R$ 177,81)

**Loja 1314 (Corumbá, LT=9d):**
- Demanda Q4: 854 un | s=180 | S=339
- 0 rupturas, 5 pedidos no trimestre
- Capital médio: R$ 1.495 (vs real R$ 665)
- Safety stock elevado (96,5 un) devido a LT=9d + forecast inflado em +57%

**Insight:** NEOSORO dita KPIs globais. Melhorar seu forecast reduz estoque em R$ 432-864/trim sem perder SL.

---

## Slide 5 — Conclusão e Próximos Passos

**O que funciona:**
- Política (s,S) atinge 99,94% SL com abordagem defensável e explicável
- Grid search + simulador validado (100% lead time, 0 estoque negativo)
- Dashboard interativo com animação dia a dia

**O que fazer agora (ganhos rápidos):**

| Fase | Ação | Impacto |
|:----:|------|:-------:|
| 1 | review_days 5→7 (já feito) | −R$ 770/trim |
| 1 | z 0,84→1,28 | ROI 34,8× (zero ruptura) |
| 1 | Customizar ABRILAR 1314 + NEOSORO 841 | Protege R$ 2.091 receita |
| 2 | Corrigir uplift promocional | −R$ 432/trim |
| 2 | Forecast = 0 para 64% SKUs (≤3 un/Q4) | Elimina estoque parado |
| 3 | SL diferenciado ABC (A:99,5% B:95% C:90%) | Libera R$ 3.839 capital |

**Fechamento:** O melhor resultado vem de combinar forecast defensável com política operacional consistente — não de modelos complexos.
