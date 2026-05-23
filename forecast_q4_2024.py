from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

TRAIN_END = pd.Timestamp("2024-09-30")
Q4_START = pd.Timestamp("2024-10-01")
Q4_END = pd.Timestamp("2024-12-31")
STORE_CODES = {"LOJA 841": "841", "LOJA 1314": "1314"}


def resolve_data_dir(base_dir: Path) -> Path:
    direct_file = base_dir / "2_produtos_locais.csv"
    nested_file = base_dir / "data" / "2_produtos_locais.csv"
    if direct_file.exists():
        return base_dir
    if nested_file.exists():
        return base_dir / "data"
    raise FileNotFoundError(
        f"Could not find 2_produtos_locais.csv in {base_dir} or {base_dir / 'data'}"
    )


def load_products(base_dir: Path) -> pd.DataFrame:
    products = pd.read_csv(base_dir / "2_produtos_locais.csv", sep=";")
    products = products[products["location"].isin(STORE_CODES)].copy()
    products["location_code"] = products["location"].map(STORE_CODES)
    products["product"] = products["product"].astype(str)
    products["purchase_price"] = pd.to_numeric(products["purchase_price"], errors="coerce")
    products["cost_of_ordering"] = pd.to_numeric(products["cost_of_ordering"], errors="coerce")
    return products[
        [
            "product",
            "location_code",
            "product_name",
            "purchase_price",
            "cost_of_ordering",
            "minimum_delivery_batch",
        ]
    ].rename(columns={"location_code": "location"})


def load_lead_times(base_dir: Path) -> pd.DataFrame:
    locations = pd.read_csv(base_dir / "3_locais.csv", sep=";")
    locations["location"] = locations["location"].astype(str)
    locations["leadtime_dc_store"] = pd.to_numeric(locations["leadtime_dc_store"], errors="coerce")
    return locations[["location", "leadtime_dc_store"]].rename(
        columns={"leadtime_dc_store": "lead_time_days"}
    )


def load_sales(base_dir: Path) -> pd.DataFrame:
    sales = pd.read_csv(base_dir / "8_inventario_venda.csv", sep=";")
    sales = sales[sales["type"] == "SALE"].copy()
    sales["date"] = pd.to_datetime(sales["date"])
    sales["product"] = sales["product"].astype(str)
    sales["location"] = sales["location"].astype(str)
    sales["quantity"] = pd.to_numeric(sales["quantity"], errors="coerce")
    sales["demand"] = -sales["quantity"]
    sales = (
        sales.groupby(["date", "location", "product"], as_index=False)["demand"]
        .sum()
        .sort_values(["location", "product", "date"])
    )
    return sales


def load_balances(base_dir: Path) -> pd.DataFrame:
    balances = pd.read_csv(base_dir / "7_saldo.csv", sep=";")
    balances["date"] = pd.to_datetime(balances["date"])
    balances["product"] = balances["product"].astype(str)
    balances["location"] = balances["location"].astype(str)
    balances["balance"] = pd.to_numeric(balances["balance"], errors="coerce")
    balances["stockout"] = (balances["balance"].fillna(0) <= 0).astype(int)
    return balances[["date", "location", "product", "balance", "stockout"]]


def load_promotions(base_dir: Path) -> pd.DataFrame:
    campaigns = pd.read_csv(base_dir / "4_campanhas.csv", sep=";")
    links = pd.read_csv(base_dir / "5_produtos_locais_campanhas.csv", sep=";")

    campaigns["start_date"] = pd.to_datetime(campaigns["start_date"])
    campaigns["end_date"] = pd.to_datetime(campaigns["end_date"])
    campaigns["campaign"] = campaigns["campaign"].astype(str)

    links["campaign"] = links["campaign"].astype(str)
    links["product"] = links["product"].astype(str)
    links["location"] = links["location"].astype(str)

    promo_rows: list[dict[str, object]] = []
    merged = links.merge(campaigns, on="campaign", how="left")
    for row in merged.itertuples(index=False):
        if pd.isna(row.start_date) or pd.isna(row.end_date):
            continue
        for date in pd.date_range(row.start_date, row.end_date, freq="D"):
            promo_rows.append(
                {
                    "date": date,
                    "location": str(row.location),
                    "product": str(row.product),
                    "is_promo": 1,
                }
            )

    if not promo_rows:
        return pd.DataFrame(columns=["date", "location", "product", "is_promo"])

    promo = pd.DataFrame(promo_rows).drop_duplicates()
    return promo


def build_daily_panel(base_dir: Path) -> pd.DataFrame:
    products = load_products(base_dir)
    sales = load_sales(base_dir)
    balances = load_balances(base_dir)
    promotions = load_promotions(base_dir)
    lead_times = load_lead_times(base_dir)

    calendar = pd.date_range(sales["date"].min(), Q4_END, freq="D")
    sku_store = products[["product", "location"]].drop_duplicates()
    base = sku_store.merge(pd.DataFrame({"date": calendar}), how="cross")

    panel = (
        base.merge(products, on=["product", "location"], how="left")
        .merge(lead_times, on="location", how="left")
        .merge(sales, on=["date", "location", "product"], how="left")
        .merge(balances, on=["date", "location", "product"], how="left")
        .merge(promotions, on=["date", "location", "product"], how="left")
    )

    panel["demand"] = panel["demand"].fillna(0.0)
    panel["stockout"] = panel["stockout"].fillna(0).astype(int)
    panel["balance"] = panel["balance"].fillna(np.nan)
    panel["is_promo"] = panel["is_promo"].fillna(0).astype(int)
    panel["weekday"] = panel["date"].dt.weekday
    return panel.sort_values(["location", "product", "date"]).reset_index(drop=True)


def add_censored_demand_adjustment(panel: pd.DataFrame) -> pd.DataFrame:
    train = panel[panel["date"] <= TRAIN_END].copy()
    non_stockout = train[train["stockout"] == 0].copy()

    dow_baseline = (
        non_stockout.groupby(["location", "product", "weekday"], as_index=False)["demand"]
        .median()
        .rename(columns={"demand": "dow_baseline"})
    )
    sku_baseline = (
        non_stockout.groupby(["location", "product"], as_index=False)["demand"]
        .mean()
        .rename(columns={"demand": "sku_baseline"})
    )
    store_baseline = (
        non_stockout.groupby(["location", "weekday"], as_index=False)["demand"]
        .median()
        .rename(columns={"demand": "store_weekday_baseline"})
    )

    panel = panel.merge(dow_baseline, on=["location", "product", "weekday"], how="left")
    panel = panel.merge(sku_baseline, on=["location", "product"], how="left")
    panel = panel.merge(store_baseline, on=["location", "weekday"], how="left")

    baseline = panel["dow_baseline"]
    baseline = baseline.fillna(panel["sku_baseline"])
    baseline = baseline.fillna(panel["store_weekday_baseline"])
    baseline = baseline.fillna(0.0)

    panel["corrected_demand"] = panel["demand"]
    stockout_mask = panel["stockout"] == 1
    panel.loc[stockout_mask, "corrected_demand"] = np.maximum(
        panel.loc[stockout_mask, "demand"],
        baseline.loc[stockout_mask],
    )
    return panel


def compute_promo_uplift(panel: pd.DataFrame) -> pd.DataFrame:
    train = panel[panel["date"] <= TRAIN_END].copy()

    sku_stats = (
        train.groupby(["location", "product", "is_promo"])
        .agg(mean_demand=("corrected_demand", "mean"), days=("date", "size"))
        .reset_index()
    )
    sku_pivot = sku_stats.pivot_table(
        index=["location", "product"],
        columns="is_promo",
        values=["mean_demand", "days"],
        fill_value=np.nan,
    )
    sku_pivot.columns = [f"{a}_{b}" for a, b in sku_pivot.columns]
    sku_pivot = sku_pivot.reset_index()

    store_stats = (
        train.groupby(["location", "is_promo"])
        .agg(mean_demand=("corrected_demand", "mean"), days=("date", "size"))
        .reset_index()
    )
    store_pivot = store_stats.pivot_table(
        index=["location"],
        columns="is_promo",
        values=["mean_demand", "days"],
        fill_value=np.nan,
    )
    store_pivot.columns = [f"store_{a}_{b}" for a, b in store_pivot.columns]
    store_pivot = store_pivot.reset_index()

    uplift = panel[["location", "product"]].drop_duplicates()
    uplift = uplift.merge(sku_pivot, on=["location", "product"], how="left")
    uplift = uplift.merge(store_pivot, on="location", how="left")

    sku_ratio = uplift["mean_demand_1"] / uplift["mean_demand_0"]
    sku_valid = (uplift["days_1"] >= 3) & (uplift["days_0"] >= 20) & np.isfinite(sku_ratio)

    store_ratio = uplift["store_mean_demand_1"] / uplift["store_mean_demand_0"]
    store_valid = (
        (uplift["store_days_1"] >= 10)
        & (uplift["store_days_0"] >= 40)
        & np.isfinite(store_ratio)
    )

    uplift["promo_uplift"] = 1.0
    uplift.loc[sku_valid, "promo_uplift"] = sku_ratio[sku_valid]
    uplift.loc[~sku_valid & store_valid, "promo_uplift"] = store_ratio[~sku_valid & store_valid]
    uplift["promo_uplift"] = uplift["promo_uplift"].clip(lower=1.0, upper=2.5).fillna(1.0)
    return uplift[["location", "product", "promo_uplift"]]


def weighted_component_mean(components: list[tuple[float, float]]) -> float:
    usable = [(weight, value) for weight, value in components if pd.notna(value)]
    if not usable:
        return 0.0
    total_weight = sum(weight for weight, _ in usable)
    return float(sum(weight * value for weight, value in usable) / total_weight)


def forecast_group(group: pd.DataFrame, mode: str) -> pd.DataFrame:
    group = group.sort_values("date").copy()
    history_end = TRAIN_END

    forecasts: list[dict[str, object]] = []
    static_history = group[group["date"] <= TRAIN_END].copy()

    for row in group[(group["date"] >= Q4_START) & (group["date"] <= Q4_END)].itertuples(index=False):
        if mode == "rolling":
            hist = group[group["date"] < row.date].copy()
        else:
            hist = static_history

        hist = hist[hist["date"] <= history_end if mode == "static" else hist["date"] < row.date]
        if hist.empty:
            base_forecast = 0.0
            demand_std = 0.0
        else:
            recent_28 = hist.tail(28)
            same_weekday = hist[hist["weekday"] == row.weekday].tail(8)
            last_year_window = hist[
                (hist["date"] >= row.date - pd.Timedelta(days=372))
                & (hist["date"] <= row.date - pd.Timedelta(days=358))
            ]
            overall_recent = hist.tail(56)

            base_forecast = weighted_component_mean(
                [
                    (0.45, recent_28["corrected_demand"].mean() if not recent_28.empty else np.nan),
                    (
                        0.35,
                        same_weekday["corrected_demand"].mean() if not same_weekday.empty else np.nan,
                    ),
                    (
                        0.20,
                        last_year_window["corrected_demand"].mean()
                        if not last_year_window.empty
                        else np.nan,
                    ),
                ]
            )
            demand_std = float(overall_recent["corrected_demand"].std(ddof=0))
            if np.isnan(demand_std):
                demand_std = 0.0

        promo_adjusted = base_forecast * row.promo_uplift if row.is_promo else base_forecast
        promo_adjusted = max(float(promo_adjusted), 0.0)

        forecasts.append(
            {
                "date": row.date,
                "location": row.location,
                "product": row.product,
                "product_name": row.product_name,
                "is_promo": row.is_promo,
                "promo_uplift": float(row.promo_uplift),
                "lead_time_days": row.lead_time_days,
                "purchase_price": row.purchase_price,
                "cost_of_ordering": row.cost_of_ordering,
                "forecast_demand": round(promo_adjusted, 4),
                "forecast_std": round(demand_std, 4),
                "observed_demand": round(float(row.demand), 4),
                "corrected_observed_demand": round(float(row.corrected_demand), 4),
                "stockout_flag": int(row.stockout),
                "mode": mode,
            }
        )

    return pd.DataFrame(forecasts)


def build_forecast(panel: pd.DataFrame, mode: str) -> pd.DataFrame:
    result = []
    for (_, _), group in panel.groupby(["location", "product"], sort=True):
        result.append(forecast_group(group, mode=mode))
    return pd.concat(result, ignore_index=True)


def build_policy_inputs(forecast: pd.DataFrame) -> pd.DataFrame:
    summary = (
        forecast.groupby(["location", "product", "product_name"], as_index=False)
        .agg(
            mean_daily_forecast=("forecast_demand", "mean"),
            std_daily_forecast=("forecast_std", "mean"),
            total_forecast_q4=("forecast_demand", "sum"),
            promo_days_q4=("is_promo", "sum"),
            lead_time_days=("lead_time_days", "max"),
            purchase_price=("purchase_price", "max"),
            cost_of_ordering=("cost_of_ordering", "max"),
        )
        .sort_values(["location", "product"])
    )
    summary["suggested_reorder_point_s"] = np.ceil(
        summary["mean_daily_forecast"] * summary["lead_time_days"]
        + 1.65 * summary["std_daily_forecast"] * np.sqrt(summary["lead_time_days"])
    )
    summary["suggested_order_up_to_S"] = np.ceil(
        summary["suggested_reorder_point_s"] + summary["mean_daily_forecast"] * 7
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Forecast daily demand for Q4 2024.")
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=Path.cwd(),
        help="Directory that contains the CSV files.",
    )
    parser.add_argument(
        "--mode",
        choices=["static", "rolling"],
        default="rolling",
        help="Use only history up to 2024-09-30 (static) or update with realized past days in Q4 (rolling).",
    )
    parser.add_argument(
        "--forecast-output",
        type=Path,
        default=None,
        help="Optional output path for the daily Q4 forecast CSV.",
    )
    parser.add_argument(
        "--policy-output",
        type=Path,
        default=None,
        help="Optional output path for the summarized policy input CSV.",
    )
    args = parser.parse_args()

    project_dir = args.base_dir
    data_dir = resolve_data_dir(project_dir)
    panel = build_daily_panel(data_dir)
    panel = add_censored_demand_adjustment(panel)
    uplift = compute_promo_uplift(panel)
    panel = panel.merge(uplift, on=["location", "product"], how="left")
    panel["promo_uplift"] = panel["promo_uplift"].fillna(1.0)

    forecast = build_forecast(panel, mode=args.mode)
    policy_inputs = build_policy_inputs(forecast)

    forecast_output = args.forecast_output or (
        project_dir / f"q4_2024_daily_forecast_{args.mode}.csv"
    )
    policy_output = args.policy_output or (
        project_dir / f"q4_2024_policy_inputs_{args.mode}.csv"
    )

    forecast.to_csv(forecast_output, index=False)
    policy_inputs.to_csv(policy_output, index=False)

    print(f"forecast_rows={len(forecast)}")
    print(f"policy_rows={len(policy_inputs)}")
    print(f"forecast_output={forecast_output}")
    print(f"policy_output={policy_output}")


if __name__ == "__main__":
    main()
