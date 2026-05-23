# AGENTS — Hackathon Previsão de Estoque (Q4/2024)

## Contexto do Projeto

Hackathon de otimização de inventário para rede farmacêutica. Propor política de reposição (s, S) para 29 SKUs da categoria **Gripe e Resfriado** em 2 lojas, validada via simulação dia a dia no **Q4/2024**.

- **Loja 841** (Ceres, GO): lead time = 3 dias, ~174 unidades vendidas no Q4
- **Loja 1314** (Corumbá, MS): lead time = 9 dias, ~1051 unidades vendidas no Q4
- **CD 2 GO** (Hidrolândia, GO): centro de distribuição único
- SKU **18064 (NEOSORO)** domina 78% da demanda
- `minimum_delivery_batch` = 1 para lojas (não é restrição)

## Dados

8 CSVs em `data/`, relacionados por `product`, `location`, `campaign`.

**Atenção:** Vendas (`SALE`) têm `quantity` negativo — inverter sinal para forecast.

## Períodos

- **Treino:** 02/01/2023 a 30/09/2024
- **Avaliação (backtest):** 01/10/2024 a 31/12/2024

## Status Atual da Análise

### ✅ Concluído

| Etapa | Arquivo | Principais Descobertas |
|-------|---------|----------------------|
| Análise exploratória | análises/analise_exploratoria.py | NEOSORO domina 78% demanda + CV; +44,8% promo uplift; sábado +22% |
| Erro de forecast | analyze_forecast_errors.py | Modelo superestima 51% (1.845 vs 1.225); promo tem 104% erro |
| Validação do simulador | validate_simulation.py | 100% lead time OK; zero estoque negativo; lost sales corretas |
| Stress test | stress_test.py | Forecast é o problema principal; review_days 5→7 economiza R$ 770/trim |
| Análise profunda SKU | sku_deep_analysis.py | 27 SKUs alta var+baixo vol; NEOSORO mascara resultados; 64% SKUs não precisam de forecast |
| Conclusões compiladas | CONCLUSOES_E_PROXIMOS_PASSOS.md | Documento consolidado com 26 perguntas respondidas e priorização |

### 📄 Entregas Geradas

- `stock_policy_product_output/policy.csv` — política final (58 pares SKU-loja)
- `stock_policy_product_output/simulation_daily.csv` — simulação dia a dia (5.336 linhas)
- `stock_policy_product_output/tuning_search.csv` — grid search z x review_days
- `CONCLUSOES_E_PROXIMOS_PASSOS.md` — conclusões e próximos objetivos

### 📊 Resultado da Simulação

| Métrica | Atual | Target |
|---------|-------|--------|
| Nível de serviço | 99,94% | ≥ 92% ✅ |
| Estoque médio | R$ 169,78 | — |
| Custo total de reposição | R$ 2.629,55 | — |
| Total de pedidos | 113 | — |
| Vendas perdidas | 3 unidades (R$ 233,72) | — |
| Parâmetros | z=0.84, review=5d, piso empírico 75% | — |

## Recomendação Técnica

- Política **(s, S)**: `s = ceil(mu * L + z * sigma * sqrt(L))`, `S = ceil(s + mu * review_cover_days)`
- Loja 841: L=3; Loja 1314: L=9
- Forecast simples (média móvel / dia da semana) + uplift promocional + correção de censura
- Calibrar `z` e `review_cover_days` via grid search no simulador

## Convenções

- `cost_of_ordering` é incorrido por pedido, não por unidade
- Estoque valorado a `purchase_price`
- Ruptura: demanda > saldo → estoque = 0, diferença = venda perdida
- Pedido no dia `d` chega em `d + lead_time`
- Decidir pedido ao amanhecer (com posição de estoque), consumir demanda, fechar saldo

## Entregas

1. `policy.csv` — política (s,S) por SKU-loja ✅
2. Simulador funcional ✅
3. Pitch (slides) — pendente

## Próximos Objetivos (Prioridade)

| Fase | Ação | Impacto |
|------|------|---------|
| **1** | review_days 5→7 | -R$ 770/trim |
| **1** | z 0,84→1,28 | ROI 34,8x (zero ruptura) |
| **1** | Customizar ABRILAR 1314 e NEOSORO 841 | Proteger R$ 2.091 receita |
| **2** | Corrigir uplift promocional | -R$ 432/trim |
| **2** | Forecast ZERO para SKUs <5 un/Q4 | Elimina estoque parado |
| **2** | Regra para novos SKUs | Evita ruptura na 1ª venda |
| **3** | SL diferenciado ABC | Libera R$ 3.839 capital |
| **3** | Correção de censura na demanda | Melhora forecast |
| **4** | Prontidão produção (DB, testes, CI/CD, dashboard) | MVP utilizável |

## Observações

- NEOSORO (SKU 18064) domina 78% da demanda -> KPIs globais são KPIs do NEOSORO
- 64% dos SKUs têm demanda ≤3 un no Q4; forecast sofisticado não gera ganho
- Custo de errar para mais é 8x maior que errar para menos (realizado)
- Política de 3 camadas (A: 99,5%, B: 95%, C: 90%) liberaria R$ 3.839 de capital
- Documento completo de conclusões: `CONCLUSOES_E_PROXIMOS_PASSOS.md`
