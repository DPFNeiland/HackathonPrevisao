
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUT_DIR = BASE_DIR / "outputs" / "graficos"
OUT_DIR.mkdir(parents=True, exist_ok=True)

sns.set_theme(style="whitegrid", context="talk")
plt.rcParams["figure.figsize"] = (14, 7)
plt.rcParams["axes.titlesize"] = 16
plt.rcParams["axes.labelsize"] = 12


def read_csv(name):
    return pd.read_csv(DATA_DIR / name, sep=";")


def savefig(name):
    path = OUT_DIR / name
    plt.tight_layout()
    plt.savefig(path, dpi=160, bbox_inches="tight")
    plt.close()
    print(f"salvo: {path}")


def load_data():
    produtos = read_csv("2_produtos_locais.csv")
    locais = read_csv("3_locais.csv")
    campanhas = read_csv("4_campanhas.csv")
    prod_campanhas = read_csv("5_produtos_locais_campanhas.csv")
    fornecedores = read_csv("6_fornecedores.csv")
    saldo = read_csv("7_saldo.csv")
    movimentos = read_csv("8_inventario_venda.csv")

    saldo["date"] = pd.to_datetime(saldo["date"])
    movimentos["date"] = pd.to_datetime(movimentos["date"])
    campanhas["start_date"] = pd.to_datetime(campanhas["start_date"])
    campanhas["end_date"] = pd.to_datetime(campanhas["end_date"])

    vendas = movimentos[movimentos["type"].eq("SALE")].copy()
    vendas["demand"] = -vendas["quantity"]

    return produtos, locais, campanhas, prod_campanhas, fornecedores, saldo, movimentos, vendas


def plot_demanda_diaria_por_loja(vendas):
    daily = vendas.groupby(["date", "location"], as_index=False)["demand"].sum()
    sns.lineplot(data=daily, x="date", y="demand", hue="location", marker="o")
    plt.title("Demanda diaria por loja")
    plt.xlabel("Data")
    plt.ylabel("Unidades vendidas")
    savefig("01_demanda_diaria_por_loja.png")


def plot_demanda_q4_por_loja(vendas):
    q4 = vendas[vendas["date"].between("2024-10-01", "2024-12-31")]
    total = q4.groupby("location", as_index=False)["demand"].sum()
    sns.barplot(data=total, x="location", y="demand", hue="location", palette="Set2", legend=False)
    plt.title("Demanda total no Q4/2024 por loja")
    plt.xlabel("Loja")
    plt.ylabel("Unidades vendidas")
    savefig("02_demanda_q4_por_loja.png")


def plot_top_skus_q4(vendas, produtos):
    q4 = vendas[vendas["date"].between("2024-10-01", "2024-12-31")]
    top = (
        q4.groupby(["location", "product"], as_index=False)["demand"].sum()
        .sort_values("demand", ascending=False)
        .head(15)
        .merge(produtos[["product", "product_name"]].drop_duplicates(), on="product", how="left")
    )
    top["sku_label"] = top["product"].astype(str) + " - " + top["product_name"].fillna("").str.slice(0, 28)
    sns.barplot(data=top, y="sku_label", x="demand", hue="location", palette="Set1")
    plt.title("Top SKU-loja por demanda no Q4/2024")
    plt.xlabel("Unidades vendidas")
    plt.ylabel("SKU")
    savefig("03_top_skus_q4.png")


def plot_estoque_vs_venda_item(vendas, saldo, produto=18064, loja=1314):
    vend = vendas[(vendas["product"].eq(produto)) & (vendas["location"].eq(loja))]
    vend = vend.groupby("date", as_index=False)["demand"].sum()
    est = saldo[(saldo["product"].eq(produto)) & (saldo["location"].eq(loja))][["date", "balance"]]
    df = est.merge(vend, on="date", how="left").fillna({"demand": 0})

    fig, ax1 = plt.subplots(figsize=(14, 7))
    ax1.plot(df["date"], df["balance"], color="#2c7fb8", label="Saldo")
    ax1.set_ylabel("Saldo em estoque", color="#2c7fb8")
    ax1.tick_params(axis="y", labelcolor="#2c7fb8")

    ax2 = ax1.twinx()
    ax2.bar(df["date"], df["demand"], color="#fdae61", alpha=0.45, label="Venda")
    ax2.set_ylabel("Unidades vendidas", color="#b35806")
    ax2.tick_params(axis="y", labelcolor="#b35806")

    plt.title(f"Saldo x vendas - produto {produto} na loja {loja}")
    fig.autofmt_xdate()
    savefig(f"04_saldo_vs_venda_produto_{produto}_loja_{loja}.png")


def build_campaign_calendar(campanhas, prod_campanhas):
    return prod_campanhas.merge(
        campanhas[["campaign", "start_date", "end_date", "type"]],
        on="campaign",
        how="left",
    )


def mark_campaign_days(vendas, campanhas, prod_campanhas):
    cal = build_campaign_calendar(campanhas, prod_campanhas)
    vendas = vendas.copy()
    vendas["campaign_day"] = False

    for row in cal.itertuples(index=False):
        mask = (
            vendas["product"].eq(row.product)
            & vendas["location"].eq(row.location)
            & vendas["date"].between(row.start_date, row.end_date)
        )
        vendas.loc[mask, "campaign_day"] = True

    return vendas


def plot_campanha_vs_sem_campanha(vendas, campanhas, prod_campanhas):
    marked = mark_campaign_days(vendas, campanhas, prod_campanhas)
    q4 = marked[marked["date"].between("2024-10-01", "2024-12-31")]
    comp = q4.groupby(["location", "campaign_day"], as_index=False)["demand"].sum()
    comp["periodo"] = comp["campaign_day"].map({True: "Com campanha", False: "Sem campanha"})
    sns.barplot(data=comp, x="location", y="demand", hue="periodo", palette="Set2")
    plt.title("Demanda no Q4/2024 em dias com e sem campanha")
    plt.xlabel("Loja")
    plt.ylabel("Unidades vendidas")
    savefig("05_demanda_campanha_vs_sem_campanha_q4.png")


def plot_lead_time_lojas(locais):
    stores = locais[locais["location_type"].eq("Store")].copy()
    stores["location"] = stores["location"].astype(str)
    sns.barplot(data=stores, x="location", y="leadtime_dc_store", hue="location", palette="Set3", legend=False)
    plt.title("Lead time CD-loja")
    plt.xlabel("Loja")
    plt.ylabel("Dias")
    savefig("06_lead_time_lojas.png")


def plot_lead_time_fornecedores(fornecedores):
    sns.histplot(data=fornecedores, x="lead_time", bins=10, color="#756bb1")
    plt.title("Distribuicao do lead time dos fornecedores")
    plt.xlabel("Lead time fornecedor-CD em dias")
    plt.ylabel("Quantidade de SKUs")
    savefig("07_lead_time_fornecedores.png")


def plot_movimentos_operacionais(movimentos):
    counts = movimentos["type"].value_counts().reset_index()
    counts.columns = ["type", "quantidade"]
    sns.barplot(data=counts, y="type", x="quantidade", hue="type", palette="Set2", legend=False)
    plt.title("Tipos de movimento no inventario")
    plt.xlabel("Quantidade de registros")
    plt.ylabel("Tipo")
    savefig("08_tipos_movimento.png")


def main():
    produtos, locais, campanhas, prod_campanhas, fornecedores, saldo, movimentos, vendas = load_data()

    plot_demanda_diaria_por_loja(vendas)
    plot_demanda_q4_por_loja(vendas)
    plot_top_skus_q4(vendas, produtos)
    plot_estoque_vs_venda_item(vendas, saldo, produto=18064, loja=1314)
    plot_campanha_vs_sem_campanha(vendas, campanhas, prod_campanhas)
    plot_lead_time_lojas(locais)
    plot_lead_time_fornecedores(fornecedores)
    plot_movimentos_operacionais(movimentos)


if __name__ == "__main__":
    main()
