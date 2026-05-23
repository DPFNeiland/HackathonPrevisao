# CONCLUSÕES CONSOLIDADAS — Hackathon Previsão de Estoque

> **Data:** 23/05/2026
> **Escopo:** 29 SKUs | 2 lojas (841 LT=3d, 1314 LT=9d) | Categoria Gripe e Resfriado
> **Política atual:** (s,S) com z=0.84, review=5d, piso empírico 75%
> **Resultado:** SL 99,94% | Estoque médio R$ 169,78 | 113 pedidos | 3 unidades perdidas

---

## Sumário Executivo

O modelo atual **atinge o requisito de SL ≥ 92%** (99,94%), mas com custos ocultos:
- **Forecast inflado em 51%** — gera R$ 1.927/trim em holding cost de excesso
- **NEOSORO domina 78% da demanda** — resultados globais são resultados do NEOSORO
- **64% dos SKUs têm demanda ≤ 3 unidades** — qualquer forecast >0 para eles é desperdício
- **Custo de errar para mais é 8x maior que errar para menos** (realizado)
- **Política única para todos** — SL 100% para SKUs que vendem 1 unidade no trimestre

---

## 1. Conclusões por Pergunta Analisada

### 1.1 Qual o problema principal: forecast ou política de estoque?

**Conclusão:** Forecast inflado é o problema raiz. A política (s,S) conservadora **compensa** o forecast ruim com safety stock generoso, mas o custo do excesso é alto.

| Evidência | Valor |
|-----------|-------|
| Forecast vs Real | 1.845 vs 1.225 un (+51%) |
| Custo do excesso (holding) | R$ 1.927/trim |
| Custo das vendas perdidas (realizado) | R$ 234/trim |
| SL obtida (apesar do forecast ruim) | 99,94% |

A política mascara o problema. Consertar o forecast reduziria estoque em R$ 432-864/trim sem perder SL.

---

### 1.2 O gargalo está no lead time ou na previsão?

**Conclusão:** São problemas **complementares**. LT=9d amplifica o erro de forecast em 3x (vs 1,7x para LT=3d). O safety stock do NEOSORO 1314 é 12,7x maior que o da Loja 841 — muito além do proporcional.

| Loja | LT | Demanda NEOSORO | s | Safety stock | Amplificação do erro |
|------|----|-----------------|---|-------------|---------------------|
| 841 | 3d | 103 un | 11 | 7,6 un | 1,7x (√3) |
| 1314 | 9d | 854 un | 180 | 96,5 un | 3x (√9) |

Resolve o forecast → reduz o impacto do LT sem mudar logística.

---

### 1.3 Quais melhorias geram maior impacto?

**Conclusão:** Três melhorias prioritárias, em ordem decrescente de impacto:

| # | Melhoria | Impacto financeiro | Complexidade |
|---|----------|-------------------|-------------|
| 1 | review_days 5→7 | **-R$ 770/trim** (menos pedidos) | Baixa (mudar 1 parâmetro) |
| 2 | Corrigir uplift promocional | **-R$ 432/trim** (menos excesso) | Média (revisar modelo) |
| 3 | z 0,84→1,28 | **ROI 34,8x** (+R$ 6,72 estoque, 0 rupturas) | Baixa (mudar 1 parâmetro) |

**review_days=7** é o ponto ótimo: estoque sobe R$ 8, mas custo de pedido cai R$ 778 — benefício líquido de R$ 770/trim.

---

### 1.4 Vale mais melhorar forecast ou aumentar safety stock?

**Conclusão:** Forecast melhor > aumentar safety stock. São complementares, mas:

| Ação | Efeito no estoque | Retorno |
|------|------------------|---------|
| Aumentar safety stock (z 0,84→1,28) | **+R$ 6,72/trim** | Reduz 3 lost sales |
| Melhorar forecast (corrigir promo uplift) | **-R$ 432/trim** | Libera capital |

Forecast melhor **reduz** estoque. Safety stock adicional **aumenta**. O primeiro tem retorno 64x maior.

---

### 1.5 O sistema é robusto a mudanças de demanda?

**Conclusão:** Robustez **moderada**. Funciona para variações de ±30%. Demanda 2x ou LT+50% exige recalibração imediata.

| Cenário | Impacto | Resposta |
|---------|---------|----------|
| Variação sazonal normal (out: 14,6/d → nov: 11,8/d) | ✅ Absorvido | Safety stock cobre |
| Demanda dobra (9,3→18,6 un/d) | ⚠️ Perda de ~13 un no LT | Recalibrar em 92 dias |
| LT aumenta 50% (3→5d, 9→14d) | ✅ Estoque +25-29% | Recalibrar |
| Pico 5x média (46 un/d) | ❌ Ruptura em 3 dias | Emergencial |

---

### 1.6 O modelo generaliza para novos períodos?

**Conclusão:** Risco **médio**. O backtest cobre apenas Q4/2024. Promoções e gripes são sazonais e irregulares. SKUs com `introduction_date` recente (ex: 76834 — fev/2024) têm séries curtas.

Riscos de generalização:
- Promoções do Q4/2024 podem não se repetir (YELLOW FRIDAY, etc.)
- Gripe tem padrão irregular interanual
- Modelo não foi testado em Q1-Q3 (inverno brasileiro)
- Único período de backtest: 92 dias

---

### 1.7 A solução escala para outras categorias?

**Conclusão:** Sim, com ~80h de adaptação. Componentes genéricos (loader, simulador, política (s,S), KPIs) funcionam para qualquer categoria. Componentes específicos (forecast, correção de censura, hiperparâmetros) precisam ser reparametrizados.

Para escalar:
1. Trocar forecast por modelo genérico (Prophet)
2. Parametrizar z e review_days por categoria/ABC
3. Detecção automática de sazonalidade
4. Loader adaptável a diferentes schemas

---

### 1.8 A política é operacionalmente simples?

**Conclusão:** Sim, alta simplicidade operacional. Regra: *"estoque ≤ s? Peça S − estoque"*. 58 pares com parâmetros fixos. Sem lote mínimo, sem janela de pedido. Operador de loja executa sem cálculo.

---

### 1.9 A solução seria utilizável em produção?

**Conclusão:** Não no estado atual. Pipeline batch em Python com CSVs, sem testes, sem container, sem monitoria. Precisa de 2-3 semanas para MVP de produção:

1. Conectar a fonte de dados real (API/DB)
2. Validação de entrada + logging + alertas
3. Testes automatizados (backtest semanal)
4. Dashboard de KPIs (Streamlit/Grafana)
5. CI/CD (GitHub Actions)
6. Container Docker

---

### 1.10 O que acontece se a demanda dobrar?

**Conclusão:** O sistema não quebra, mas perde ~13 unidades no lead time. O safety stock empírico (96 unidades para NEOSORO 1314) absorve o choque inicial, mas após 92 dias sem recalibrar, ruptura se torna frequente.

| Métrica | Atual | Demanda 2x |
|---------|-------|-----------|
| s NEOSORO 1314 | 180 | ~184 (necessário) |
| Cobertura (dias) | 18d | ~9d |
| Perda estimada no LT | 0 | ~13 un |

---

### 1.11 O que acontece se o lead time aumentar?

**Conclusão:** Suportável com recalibração. LT 3→5d: safety stock +29%. LT 9→14d: safety stock +25%. Custo adicional marginal (R$ 9,31/trim para NEOSORO 1314).

---

### 1.12 O modelo suporta dados faltantes?

**Conclusão:** Tratamento heurístico, sem imputação avançada. Snapshots irregulares → usa último disponível. Gaps → demanda=0. SKUs sem histórico → s=1,S=2. Funciona mas performance de SKUs novos é ruim.

---

### 1.13 O sistema quebra com SKUs novos?

**Conclusão:** Não quebra, mas performa mal. Sem histórico: s=1,S=2. Ruptura na primeira venda. Precisa de regra de negócio para novos SKUs (similaridade, estoque inicial baseado em introdução).

---

### 1.14 A solução depende demais de hiperparâmetros?

**Conclusão:** Baixa dependência para z, média para review_days. z (0,84-2,05): estoque varia 27%, SL >99,8% sempre. review_days (3-14): estoque varia 38%, custo de pedido varia 53%. Função objetivo é plana — baixo risco de overfitting.

---

### 1.15 O modelo é sensível a pequenas mudanças?

**Conclusão:** Baixa sensibilidade para alto giro (z+0,2 = +1,2% estoque). Alta sensibilidade **relativa** para baixo giro (1 unidade em s=1,S=2 = 50% do estoque), mas impacto absoluto é irrelevante.

---

### 1.16 Existe risco de overfitting no backtest?

**Conclusão:** Baixo risco. Apenas 1 hiperparâmetro otimizado (z). Performance plana em todo o grid (objetivo 188-232, diferença <0,3%). Forecast sem vazamento temporal. O risco real é o backtest cobrir apenas 92 dias de um trimestre específico.

---

### 1.17 Os resultados permanecem bons em cenários extremos?

**Conclusão:** Pior dia do Q4 (NEOSORO 1314, 25 un) foi atendido sem ruptura (estoque 118). Pico 5x média (46 un/d) causaria ruptura em 3 dias (LT=9d). Cenário 100% promo: demanda ~1.592 un — ainda dentro do forecast (1.845). Sistema é robusto para extremos moderados, mas vulnerável a choques sustentados.

---

### 1.18 Quais SKUs possuem alta variabilidade e baixo volume?

**Conclusão:** **27 SKUs** (47% dos pares) têm CV >1,5 e demanda <10 un no Q4. Média de 3,4 un/Q4, 97% dos dias com zero demanda. Estoques com cobertura média de **146 dias** — capital parado sem benefício.

---

### 1.19 Quais produtos estão mascarando os resultados globais?

**Conclusão:** **NEOSORO (SKU 18064)** domina 78% da demanda, 490% do estoque médio, mas apenas 1,2% do custo de pedido. Os KPIs globais são KPIs do NEOSORO. Custo de pedido é dominado por PERCOF (17%), ABRILAR 200ml (15%), OSELTAMIVIR 841 (12%).

---

### 1.20 O modelo melhora os produtos importantes ou apenas os fáceis?

**Conclusão:** O modelo **superprotege a classe A** (NEOSORO: estoque +35% vs real) e **melhora a classe B** (estoque -13% vs real). Classe C tem estoque mínimo (s=1,S=2). O problema não é "fácil vs difícil" — é "NEOSORO vs todo o resto".

---

### 1.21 Existe produto que nunca deveria entrar em ruptura?

**Conclusão:** Sim — **ABRILAR 1314** (R$ 1.162 receita, 1 ruptura) e **NEOSORO 841** (R$ 929, 1 ruptura). O custo de aumentar z de 0,84 para 1,28 é R$ 6,72/trim — trivial vs proteger R$ 1.162-929 de receita.

---

### 1.22 Existe SKU onde forecast sofisticado não gera ganho operacional?

**Conclusão:** **37 dos 58 pares (64%)** têm demanda ≤3 un no Q4. Para estes, o forecast ideal é ZERO. Média móvel, Prophet, ARIMA, LightGBM: todos produzem o mesmo resultado (previsão ≈0). Forecast sofisticado só faz sentido para SKUs com demanda >20 un/Q4 (= 5 SKUs).

---

### 1.23 O custo de errar para mais é maior ou menor que errar para menos?

**Conclusão:** O custo **realizado** de errar PARA MAIS é **8,2x maior** (R$ 1.927 vs R$ 234). Isso é contra-intuitivo vs literatura clássica, mas ocorre porque:
1. O modelo é tão conservador que o under-forecast raramente vira lost sales
2. O over-forecast gera 911 unidades de sobra que pagam holding o trimestre inteiro

| Tipo | Unidades | Custo realizado |
|------|---------|----------------|
| Over-forecast (superestimou) | 911 un | R$ 1.927 (holding) |
| Under-forecast (subestimou) | 290 un | R$ 234 (lost sales) |

---

### 1.24 Qual SKU possui maior assimetria de risco?

**Conclusão:** Para todos os SKUs com demanda relevante, **under-forecast é mais caro que over-forecast em receita potencial**, mas o over domina no realizado. NEOSORO 1314 tem a maior assimetria absoluta (R$ 183 over vs R$ 469 under em custo potencial).

---

### 1.25 Quais produtos justificam políticas individualizadas?

**Conclusão:** **5 pares (de 58) representam 87% da demanda e justificam customização:**

| SKU | Loja | Demanda | Política atual | Precisa de customização? |
|-----|------|---------|---------------|-------------------------|
| NEOSORO | 1314 | 854 un | s=180,S=339 ✅ | Já tem |
| NEOSORO | 841 | 103 un | s=11,S=33 ✅ | Já tem |
| NARIDRIN 12H | 1314 | 48 un | genérica (z=0,84) | Sim |
| PERCOF | 1314 | 34 un | genérica (z=0,84) | Sim |
| ABRILAR 100ml | 1314 | 28 un | genérica (z=0,84) | Sim |

Os demais 53 pares têm demanda <20 un — política genérica s=1,S=2 é suficiente.

---

### 1.26 Quais produtos deveriam ter níveis de serviço diferentes?

**Conclusão:** **Todos deveriam.** Proposta de SL diferenciado por classe ABC liberaria **R$ 3.839 de capital (39%)**:

| Classe | Critério | SL Atual | SL Proposto | Estratégia |
|--------|----------|---------|------------|------------|
| A (NEOSORO) | 80% demanda | 99,5% | 99,5% | z=1,65, review=7 |
| B (médio) | 15% demanda | 99,9% | 95% | z=0,5, review=7 |
| C (baixo) | 5% demanda | 100% | 90% | s=1,S=2 mínimo |

Economia: R$ 3.839 de capital liberado + R$ 163/trim em holding.

---

## 2. Avaliação das Conclusões Mais Importantes

### 2.1 Matriz de Priorização (Impacto x Esforço)

```
                    ALTO IMPACTO
                        │
     review_days 5→7    │   Corrigir forecast NEOSORO
     (-R$ 770/trim)     │   (-R$ 432-864/trim)
         ╱              │              ╱
    BAIXO ◄─────────────┼──────────────► ALTO ESFORÇO
     ESFORÇO            │
                        │
     z 0,84→1.28        │   SL diferenciado ABC
     (ROI 34,8x)        │   (-R$ 3.839 capital)
         ╲              │
                        │
                    BAIXO IMPACTO
```

### 2.2 Top 5 Ações com Maior Retorno

| # | Ação | Impacto | Esforço | Retorno sobre Investimento |
|---|------|---------|---------|---------------------------|
| 1 | **review_days 5→7** | -R$ 770/trim | 10 min (mudar parâmetro) | ROI ∞ (custo zero) |
| 2 | **z 0,84→1,28** | Eliminar 3 rupturas | 10 min (mudar parâmetro) | 34,8x (R$ 234/R$ 6,72) |
| 3 | **Política NEOSORO 841 e ABRILAR 1314** | Proteger R$ 2.091 receita | 30 min (customizar 2 SKUs) | 311x (R$ 2.091/R$ 6,72) |
| 4 | **Corrigir uplift promocional** | -R$ 432/trim | 4-8h (revisar modelo) | ∞ (custo único, benefício perpétuo) |
| 5 | **SL diferenciado ABC** | Liberar R$ 3.839 capital | 4h (implementar classes) | 23,5x/trim (R$ 163/R$ 7) |

### 2.3 Ações que NÃO valem a pena

| Ação | Motivo |
|------|--------|
| Forecast sofisticado para SKUs <20 un/Q4 | 64% dos SKUs — qualquer modelo produz previsão ≈0 |
| Aumentar z acima de 1,28 | SL já é 99,9%; custo marginal cresce (z 1,65→2,05 = +R$ 18) |
| Modelagem do elo fornecedor-CD | Fornecedores têm lead times de 5-38 dias, mas a simulação atual já atinge SL 99,9% |
| Política individualizada para 53 pares de baixo giro | Demanda <20 un/Q4; s=1,S=2 é a política ótima |

---

## 3. Próximos Objetivos (Ordem de Execução)

### Fase 1: Quick Wins (Dia 1) — Zero esforço de desenvolvimento

- [ ] **1.1.** Alterar `review_days` de 5 para 7 → economia de R$ 770/trim
- [ ] **1.2.** Alterar `z` de 0,84 para 1,28 → zero rupturas (ROI 34,8x)
- [ ] **1.3.** Customizar política de ABRILAR 1314 (aumentar s de 5 para 6) e NEOSORO 841 (aumentar s de 11 para 12) → proteger R$ 2.091 de receita

### Fase 2: Melhoria do Modelo (Semanas 1-2)

- [ ] **2.1.** Revisar o multiplicador de uplift promocional: o modelo atual superestima em 104% nos dias de promo. Calibrar com base no uplift real observado (+44,8% para NEOSORO, não +263% genérico).
- [ ] **2.2.** Implementar forecast ZERO para SKUs com demanda <5 un/Q4 no período de treino (estes SKUs: s=1, S=2, sem forecast).
- [ ] **2.3.** Adicionar regra de negócio para novos SKUs: estoque inicial baseado em similaridade com SKU existente ou forecast = média da categoria no primeiro mês.

### Fase 3: Otimização Estrutural (Semanas 2-4)

- [ ] **3.1.** Implementar níveis de serviço diferenciados por classe ABC:
  - Classe A (NEOSORO): z=1,65, review=7 → SL 99,5%
  - Classe B (NARIDRIN, PERCOF, ABRILAR, etc.): z=0,5, review=7 → SL 95%
  - Classe C (demais 23 SKUs): s=1, S=2 → SL ~90%
  - **Economia estimada: R$ 3.839 de capital liberado**
- [ ] **3.2.** Adicionar correção de censura de demanda: substituir demanda observada em dias de ruptura histórica pelo max(venda observada, média de dias equivalentes sem ruptura).
- [ ] **3.3.** Implementar validação temporal cruzada (backtest em múltiplos trimestres, não apenas Q4/2024).

### Fase 4: Prontidão para Produção (Semanas 4-6)

- [ ] **4.1.** Conectar pipeline a fonte de dados real (API/banco de dados)
- [ ] **4.2.** Adicionar testes unitários e de integração
- [ ] **4.3.** Container Docker + CI/CD
- [ ] **4.4.** Dashboard de KPIs (Streamlit ou Grafana)
- [ ] **4.5.** Sistema de alertas: se forecast error > 2x normal, notificar

### Fase 5: Escalabilidade (Mês 2+)

- [ ] **5.1.** Generalizar forecast para Prophet (suporta múltiplas categorias automaticamente)
- [ ] **5.2.** Parametrizar configurações por categoria/classe ABC (arquivo YAML)
- [ ] **5.3.** Adicionar suporte a simulação estocástica (Monte Carlo) para quantificar incerteza
- [ ] **5.4.** Pipeline de recalibração automática (retreinar a cada 30 dias)

---

## 4. Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| Forecast continua inflado mesmo após correção | Média | Alto | Validar com dados de Q1/2025 (próximo trimestre) |
| SL diferenciado gera rupturas inaceitáveis em classe C | Baixa | Baixo | Monitorar; custo da ruptura é 1 un/trimestre |
| Review_days=7 atrasa pedidos em loja de alto giro | Baixa | Médio | Pilotar em 1 SKU antes de rollout completo |
| Dados de 2024 não representam 2025 | Média | Alto | Retreinar modelo com dados mais recentes a cada 30 dias |
| Equipe não tem acesso a dados em tempo real em produção | Alta | Crítico | MVP offline com atualização diária via CSV/API batch |

---

## 5. Métricas de Sucesso para Próxima Iteração

| Métrica | Atual | Alvo | Prazo |
|---------|-------|------|-------|
| Nível de serviço | 99,94% | ≥ 99,5% (classe A) / ≥ 95% (B) / ≥ 90% (C) | Fase 3 |
| Estoque médio | R$ 169,78 | R$ 140,00 (-18%) | Fase 3 |
| Custo total de reposição | R$ 2.629,55 | R$ 2.150,00 (-18%) | Fase 2 |
| Capital em excesso | R$ 2.184,59 | R$ 800,00 (-63%) | Fase 3 |
| Forecast error (NEOSORO) | +57% | +20% | Fase 2 |
| Forecast error (promo) | +104% | +30% | Fase 2 |
| Número de rupturas | 3 | 0 | Fase 1 |
| SKUs com política customizada | 2 | 5 | Fase 2 |
