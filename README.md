# Stock Policy Product

Produto local para planejamento de politica de estoque com base nos CSVs do desafio.

## O que ele faz

- lê os arquivos em `data/`
- monta a serie diaria por `SKU x loja`
- corrige demanda censurada em dias de ruptura
- ajusta forecast em dias de campanha
- calibra parametros globais `z` e `review_days` em uma janela de validacao
- aplica uma segunda camada de calibracao local por `SKU x loja`
- adiciona pisos empiricos e sazonais para itens intermitentes
- gera uma politica `(s, S)` final para o Q4/2024
- roda um backtest com aquecimento antes do periodo avaliado
- cria um painel HTML com analise por produto

## Como rodar

```powershell
& "C:\Users\rodrigo.neiland\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" run_stock_policy_product.py --output-dir "C:\Users\rodrigo.neiland\OneDrive - ESPM\Documentos\3sem\Github\HackathonPrevisao\stock_policy_product_output"
```

## Notebook para Jupyter e Colab

- `stock_policy_product_colab.ipynb`

Esse notebook roda o pipeline fim a fim, gera os mesmos artefatos do produto e ainda deixa uma secao pronta para analisar um `SKU x loja` especifico com graficos.

## Saidas principais

- `stock_policy_product_output/policy.csv`
- `stock_policy_product_output/local_overrides.csv`
- `stock_policy_product_output/sku_metrics.csv`
- `stock_policy_product_output/simulation_daily.csv`
- `stock_policy_product_output/overall_metrics.json`
- `stock_policy_product_output/index.html`
- `stock_policy_product_output/products/product_<loja>_<sku>.html`

## Como analisar um produto

1. Abra `stock_policy_product_output/index.html`.
2. Clique no produto desejado na tabela da carteira.
3. Veja na pagina do item:
   - forecast diario vs demanda real
   - saldo real vs estoque simulado
   - parametros `s` e `S`
   - pedidos simulados
   - leitura rapida de risco e capital

Exemplo direto:

- `stock_policy_product_output/products/product_1314_18064.html`
- no notebook: configure `LOCATION = "1314"` e `PRODUCT = "18064"`

## Observacoes

- a politica final usa forecast `static` para evitar vazamento temporal
- os relatorios usam forecast `rolling` para mostrar a leitura operacional diaria
- o simulador usa aquecimento antes do horizonte para nao punir a politica por herdar o saldo real exatamente no primeiro dia
