from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

STORE_CODES = {"LOJA 841": "841", "LOJA 1314": "1314"}


@dataclass(frozen=True)
class Horizon:
    name: str
    train_end: pd.Timestamp
    start: pd.Timestamp
    end: pd.Timestamp


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


def load_products(data_dir: Path) -> pd.DataFrame:
    products = pd.read_csv(data_dir / "2_produtos_locais.csv", sep=";")
    products = products[products["location"].isin(STORE_CODES)].copy()
    products["location"] = products["location"].map(STORE_CODES)
    products["product"] = products["product"].astype(str)
    products["purchase_price"] = pd.to_numeric(products["purchase_price"], errors="coerce")
    products["sales_price"] = pd.to_numeric(products["sales_price"], errors="coerce")
    products["cost_of_ordering"] = pd.to_numeric(products["cost_of_ordering"], errors="coerce")
    products["minimum_delivery_batch"] = pd.to_numeric(
        products["minimum_delivery_batch"], errors="coerce"
    ).fillna(1)
    return products[
        [
            "product",
            "location",
            "supplier",
            "product_name",
            "product_group",
            "purchase_price",
            "sales_price",
            "minimum_delivery_batch",
            "cost_of_ordering",
        ]
    ]


def load_lead_times(data_dir: Path) -> pd.DataFrame:
    locations = pd.read_csv(data_dir / "3_locais.csv", sep=";")
    locations["location"] = locations["location"].astype(str)
    locations["leadtime_dc_store"] = pd.to_numeric(locations["leadtime_dc_store"], errors="coerce")
    return locations[["location", "name", "city", "state", "leadtime_dc_store"]].rename(
        columns={
            "name": "location_name",
            "leadtime_dc_store": "lead_time_days",
        }
    )


def load_sales(data_dir: Path) -> pd.DataFrame:
    sales = pd.read_csv(data_dir / "8_inventario_venda.csv", sep=";")
    sales = sales[sales["type"] == "SALE"].copy()
    sales["date"] = pd.to_datetime(sales["date"])
    sales["product"] = sales["product"].astype(str)
    sales["location"] = sales["location"].astype(str)
    sales["quantity"] = pd.to_numeric(sales["quantity"], errors="coerce")
    sales["value"] = pd.to_numeric(sales["value"], errors="coerce")
    sales["demand"] = -sales["quantity"]
    sales["sales_value"] = -sales["value"]
    sales = (
        sales.groupby(["date", "location", "product"], as_index=False)[["demand", "sales_value"]]
        .sum()
        .sort_values(["location", "product", "date"])
    )
    return sales


def load_balances(data_dir: Path) -> pd.DataFrame:
    balances = pd.read_csv(data_dir / "7_saldo.csv", sep=";")
    balances["date"] = pd.to_datetime(balances["date"])
    balances["product"] = balances["product"].astype(str)
    balances["location"] = balances["location"].astype(str)
    balances["balance"] = pd.to_numeric(balances["balance"], errors="coerce")
    balances["balance_value"] = pd.to_numeric(balances["value"], errors="coerce")
    balances["actual_stockout_flag"] = (balances["balance"].fillna(0) <= 0).astype(int)
    return balances[
        ["date", "location", "product", "balance", "balance_value", "actual_stockout_flag"]
    ]


def load_promotions(data_dir: Path) -> pd.DataFrame:
    campaigns = pd.read_csv(data_dir / "4_campanhas.csv", sep=";")
    links = pd.read_csv(data_dir / "5_produtos_locais_campanhas.csv", sep=";")

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
                    "campaign_type": row.type,
                }
            )

    if not promo_rows:
        return pd.DataFrame(columns=["date", "location", "product", "is_promo", "campaign_type"])

    promo = pd.DataFrame(promo_rows).drop_duplicates()
    return promo


def build_daily_panel(data_dir: Path, calendar_end: pd.Timestamp) -> pd.DataFrame:
    products = load_products(data_dir)
    lead_times = load_lead_times(data_dir)
    sales = load_sales(data_dir)
    balances = load_balances(data_dir)
    promotions = load_promotions(data_dir)

    calendar = pd.date_range(sales["date"].min(), calendar_end, freq="D")
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
    panel["sales_value"] = panel["sales_value"].fillna(0.0)
    panel["balance"] = panel["balance"].fillna(np.nan)
    panel["balance_value"] = panel["balance_value"].fillna(np.nan)
    panel["actual_stockout_flag"] = panel["actual_stockout_flag"].fillna(0).astype(int)
    panel["is_promo"] = panel["is_promo"].fillna(0).astype(int)
    panel["campaign_type"] = panel["campaign_type"].fillna("")
    panel["weekday"] = panel["date"].dt.weekday
    return panel.sort_values(["location", "product", "date"]).reset_index(drop=True)


def add_censored_demand_adjustment(panel: pd.DataFrame, train_end: pd.Timestamp) -> pd.DataFrame:
    train = panel[panel["date"] <= train_end].copy()
    non_stockout = train[train["actual_stockout_flag"] == 0].copy()

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

    # Global fallback: if all baselines are NaN (e.g. 100% stockout in training),
    # use the overall median demand from the entire train set
    if baseline.isna().all():
        global_baseline = train["demand"].median()
        if pd.isna(global_baseline) or global_baseline <= 0:
            global_baseline = train["demand"].mean()
        baseline = baseline.fillna(global_baseline)

    baseline = baseline.fillna(0.0)

    panel["corrected_demand"] = panel["demand"]
    stockout_mask = panel["actual_stockout_flag"] == 1
    panel.loc[stockout_mask, "corrected_demand"] = np.maximum(
        panel.loc[stockout_mask, "demand"],
        baseline.loc[stockout_mask],
    )
    return panel


def compute_promo_uplift(panel: pd.DataFrame, train_end: pd.Timestamp) -> pd.DataFrame:
    train = panel[panel["date"] <= train_end].copy()

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
    if not sku_pivot.empty:
        uplift = uplift.merge(sku_pivot, on=["location", "product"], how="left")
    if not store_pivot.empty:
        uplift = uplift.merge(store_pivot, on="location", how="left")

    uplift["promo_uplift"] = 1.0

    if "mean_demand_1" in uplift.columns and "mean_demand_0" in uplift.columns:
        sku_ratio = uplift["mean_demand_1"] / uplift["mean_demand_0"]
        sku_valid = (uplift.get("days_1", pd.Series(0)) >= 3) & (uplift.get("days_0", pd.Series(0)) >= 20) & np.isfinite(sku_ratio)
        uplift.loc[sku_valid, "promo_uplift"] = sku_ratio[sku_valid]

    if "store_mean_demand_1" in uplift.columns and "store_mean_demand_0" in uplift.columns:
        store_ratio = uplift["store_mean_demand_1"] / uplift["store_mean_demand_0"]
        store_valid = (
            (uplift.get("store_days_1", pd.Series(0)) >= 10)
            & (uplift.get("store_days_0", pd.Series(0)) >= 40)
            & np.isfinite(store_ratio)
        )
        uplift.loc[(uplift["promo_uplift"] == 1.0) & store_valid, "promo_uplift"] = store_ratio[store_valid]

    uplift["promo_uplift"] = uplift["promo_uplift"].clip(lower=1.0, upper=2.5).fillna(1.0)
    return uplift[["location", "product", "promo_uplift"]]


def prepare_enriched_panel(data_dir: Path, horizon_end: pd.Timestamp, train_end: pd.Timestamp) -> pd.DataFrame:
    panel = build_daily_panel(data_dir, calendar_end=horizon_end)
    panel = add_censored_demand_adjustment(panel, train_end=train_end)
    uplift = compute_promo_uplift(panel, train_end=train_end)
    panel = panel.merge(uplift, on=["location", "product"], how="left")
    panel["promo_uplift"] = panel["promo_uplift"].fillna(1.0)
    return panel


def weighted_component_mean(components: list[tuple[float, float]]) -> float:
    usable = [(weight, value) for weight, value in components if pd.notna(value)]
    if not usable:
        return 0.0
    total_weight = sum(weight for weight, _ in usable)
    if total_weight == 0.0:
        return 0.0
    return float(sum(weight * value for weight, value in usable) / total_weight)


def forecast_group(group: pd.DataFrame, horizon: Horizon, mode: str) -> pd.DataFrame:
    group = group.sort_values("date").copy()
    forecasts: list[dict[str, object]] = []
    static_history = group[group["date"] <= horizon.train_end].copy()

    period = group[(group["date"] >= horizon.start) & (group["date"] <= horizon.end)]
    for row in period.itertuples(index=False):
        if mode == "rolling":
            hist = group[group["date"] < row.date].copy()
        else:
            hist = static_history

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
            demand_std = float(overall_recent["corrected_demand"].std(ddof=1))
            if np.isnan(demand_std):
                demand_std = 0.0

        promo_adjusted = base_forecast * row.promo_uplift if row.is_promo else base_forecast
        promo_adjusted = max(float(promo_adjusted), 0.0)

        forecasts.append(
            {
                "horizon_name": horizon.name,
                "date": row.date,
                "location": row.location,
                "location_name": row.location_name,
                "product": row.product,
                "product_name": row.product_name,
                "supplier": row.supplier,
                "is_promo": row.is_promo,
                "campaign_type": row.campaign_type,
                "promo_uplift": float(row.promo_uplift),
                "lead_time_days": float(row.lead_time_days) if pd.notna(row.lead_time_days) else np.nan,
                "purchase_price": float(row.purchase_price) if pd.notna(row.purchase_price) else np.nan,
                "sales_price": float(row.sales_price) if pd.notna(row.sales_price) else np.nan,
                "cost_of_ordering": float(row.cost_of_ordering)
                if pd.notna(row.cost_of_ordering)
                else np.nan,
                "minimum_delivery_batch": float(row.minimum_delivery_batch)
                if pd.notna(row.minimum_delivery_batch)
                else 1.0,
                "forecast_demand": round(promo_adjusted, 4),
                "forecast_std": round(demand_std, 4),
                "observed_demand": round(float(row.demand), 4),
                "corrected_observed_demand": round(float(row.corrected_demand), 4),
                "actual_balance": float(row.balance) if pd.notna(row.balance) else np.nan,
                "actual_balance_value": float(row.balance_value) if pd.notna(row.balance_value) else np.nan,
                "actual_stockout_flag": int(row.actual_stockout_flag),
                "mode": mode,
            }
        )

    return pd.DataFrame(forecasts)


def build_forecast(panel: pd.DataFrame, horizon: Horizon, mode: str) -> pd.DataFrame:
    result = []
    for _, group in panel.groupby(["location", "product"], sort=True):
        result.append(forecast_group(group, horizon=horizon, mode=mode))
    return pd.concat(result, ignore_index=True)


def assign_abc_class(summary: pd.DataFrame) -> pd.DataFrame:
    summary = summary.sort_values("forecast_value_period", ascending=False).copy()
    total_value = summary["forecast_value_period"].sum()
    if total_value <= 0:
        summary["abc_class"] = "C"
        return summary

    summary["cumulative_share"] = summary["forecast_value_period"].cumsum() / total_value
    summary["abc_class"] = np.where(
        summary["cumulative_share"] <= 0.80,
        "A",
        np.where(summary["cumulative_share"] <= 0.95, "B", "C"),
    )
    # Garantia: o SKU de maior valor (primeiro na ordem decrescente) e sempre A
    # Isso cobre o caso de unico SKU com cumulative_share=1.0 (>0.95)
    if len(summary) > 0:
        summary.loc[summary.index[0], "abc_class"] = "A"
    return summary.drop(columns=["cumulative_share"])


def build_summary_from_forecast(forecast: pd.DataFrame) -> pd.DataFrame:
    summary = (
        forecast.groupby(
            ["location", "location_name", "product", "product_name", "supplier"], as_index=False
        )
        .agg(
            mean_daily_forecast=("forecast_demand", "mean"),
            std_daily_forecast=("forecast_std", "mean"),
            total_forecast_period=("forecast_demand", "sum"),
            total_observed_period=("observed_demand", "sum"),
            promo_days_period=("is_promo", "sum"),
            lead_time_days=("lead_time_days", "max"),
            purchase_price=("purchase_price", "max"),
            sales_price=("sales_price", "max"),
            cost_of_ordering=("cost_of_ordering", "max"),
            minimum_delivery_batch=("minimum_delivery_batch", "max"),
        )
        .sort_values(["location", "product"])
    )
    summary["forecast_value_period"] = (
        summary["total_forecast_period"] * summary["purchase_price"].fillna(0)
    )
    summary = assign_abc_class(summary)
    return summary


def round_up_to_batch(quantity: float, batch_size: float) -> int:
    if quantity <= 0 or not np.isfinite(quantity):
        return 0
    if pd.isna(batch_size) or batch_size <= 1:
        return int(np.ceil(quantity))
    return int(np.ceil(quantity / batch_size) * batch_size)


def build_policy(
    summary: pd.DataFrame,
    z_value: float,
    review_days: int,
    *,
    min_active_stock: int = 1,
    minimum_presentation_stock: int = 1,
    overrides: pd.DataFrame | None = None,
) -> pd.DataFrame:
    policy = summary.copy()
    policy["z_value"] = float(z_value)
    policy["review_days"] = int(review_days)

    if overrides is not None and not overrides.empty:
        override_cols = ["location", "product", "z_value", "review_days"]
        available_cols = [col for col in override_cols if col in overrides.columns]
        policy = policy.merge(
            overrides[available_cols].rename(
                columns={
                    "z_value": "z_value_override",
                    "review_days": "review_days_override",
                }
            ),
            on=["location", "product"],
            how="left",
        )
        policy["z_value"] = policy["z_value_override"].fillna(policy["z_value"])
        policy["review_days"] = (
            policy["review_days_override"].fillna(policy["review_days"]).astype(int)
        )
        policy = policy.drop(columns=["z_value_override", "review_days_override"], errors="ignore")

    lead_time = policy["lead_time_days"].fillna(0)
    mean_daily = policy["mean_daily_forecast"].fillna(0)
    std_daily = policy["std_daily_forecast"].fillna(0)

    policy["reorder_point_s"] = np.ceil(
        mean_daily * lead_time
        + policy["z_value"].fillna(0) * std_daily * np.sqrt(np.maximum(lead_time, 1))
    )
    policy["order_up_to_S"] = np.ceil(
        policy["reorder_point_s"] + mean_daily * policy["review_days"].fillna(0)
    )

    active_mask = policy["total_forecast_period"] > 0
    policy.loc[active_mask, "order_up_to_S"] = np.maximum(
        policy.loc[active_mask, "order_up_to_S"],
        policy.loc[active_mask, "reorder_point_s"] + min_active_stock,
    )

    if minimum_presentation_stock > 0:
        policy["reorder_point_s"] = np.maximum(policy["reorder_point_s"], minimum_presentation_stock)
        policy["order_up_to_S"] = np.maximum(
            policy["order_up_to_S"],
            policy["reorder_point_s"] + 1,
        )
    else:
        policy.loc[~active_mask, ["reorder_point_s", "order_up_to_S"]] = 0

    policy["reorder_point_s"] = policy["reorder_point_s"].fillna(0).astype(int)
    policy["order_up_to_S"] = policy["order_up_to_S"].fillna(0).astype(int)
    policy["z_value"] = policy["z_value"].fillna(float(z_value))
    policy["review_days"] = policy["review_days"].fillna(int(review_days)).astype(int)
    policy["lead_time_days"] = policy["lead_time_days"].fillna(0).astype(int)
    policy["minimum_delivery_batch"] = policy["minimum_delivery_batch"].fillna(1).astype(int)
    return policy


def apply_empirical_demand_floors(
    policy: pd.DataFrame,
    panel: pd.DataFrame,
    *,
    train_end: pd.Timestamp,
    reorder_quantile: float = 0.75,
    order_up_to_quantile: float = 0.90,
    seasonal_reference_start: pd.Timestamp | None = None,
    seasonal_reference_end: pd.Timestamp | None = None,
) -> pd.DataFrame:
    adjusted = policy.copy()
    adjusted["statistical_reorder_point_s"] = adjusted["reorder_point_s"]
    adjusted["statistical_order_up_to_S"] = adjusted["order_up_to_S"]
    adjusted["empirical_floor_s"] = 0
    adjusted["empirical_floor_S"] = 0
    adjusted["seasonal_floor_s"] = 0
    adjusted["seasonal_floor_S"] = 0

    train = panel[panel["date"] <= train_end].copy()
    floor_rows: list[dict[str, object]] = []

    for row in adjusted.itertuples(index=False):
        group = train[
            (train["location"] == row.location) & (train["product"] == row.product)
        ].sort_values("date")
        demand = group["corrected_demand"].fillna(0.0)
        lead = max(int(row.lead_time_days or 0), 1)
        cycle = max(lead + int(row.review_days or 0), 1)

        lead_windows = demand.rolling(lead, min_periods=1).sum()
        cycle_windows = demand.rolling(cycle, min_periods=1).sum()
        lead_windows = lead_windows[lead_windows > 0]
        cycle_windows = cycle_windows[cycle_windows > 0]

        floor_s = int(np.ceil(lead_windows.quantile(reorder_quantile))) if not lead_windows.empty else 0
        floor_S = (
            int(np.ceil(cycle_windows.quantile(order_up_to_quantile))) if not cycle_windows.empty else 0
        )

        seasonal_floor_s = 0
        seasonal_floor_S = 0
        if seasonal_reference_start is not None and seasonal_reference_end is not None:
            seasonal_group = group[
                (group["date"] >= seasonal_reference_start) & (group["date"] <= seasonal_reference_end)
            ]
            seasonal_demand = seasonal_group["corrected_demand"].fillna(0.0)
            seasonal_lead_windows = seasonal_demand.rolling(lead, min_periods=1).sum()
            seasonal_cycle_windows = seasonal_demand.rolling(cycle, min_periods=1).sum()
            seasonal_lead_windows = seasonal_lead_windows[seasonal_lead_windows > 0]
            seasonal_cycle_windows = seasonal_cycle_windows[seasonal_cycle_windows > 0]
            if not seasonal_lead_windows.empty:
                seasonal_floor_s = int(np.ceil(seasonal_lead_windows.quantile(reorder_quantile)))
            if not seasonal_cycle_windows.empty:
                seasonal_floor_S = int(
                    np.ceil(seasonal_cycle_windows.quantile(order_up_to_quantile))
                )

        if demand.sum() > 0:
            floor_s = max(floor_s, 1)
            floor_S = max(floor_S, floor_s + 1)
            seasonal_floor_s = max(seasonal_floor_s, 0)
            seasonal_floor_S = max(seasonal_floor_S, seasonal_floor_s + 1) if seasonal_floor_s > 0 else seasonal_floor_S

        floor_rows.append(
            {
                "location": row.location,
                "product": row.product,
                "empirical_floor_s": floor_s,
                "empirical_floor_S": floor_S,
                "seasonal_floor_s": seasonal_floor_s,
                "seasonal_floor_S": seasonal_floor_S,
            }
        )

    floor_df = pd.DataFrame(floor_rows)
    adjusted = adjusted.drop(
        columns=["empirical_floor_s", "empirical_floor_S", "seasonal_floor_s", "seasonal_floor_S"],
        errors="ignore",
    )
    adjusted = adjusted.merge(floor_df, on=["location", "product"], how="left")
    adjusted["empirical_floor_s"] = adjusted["empirical_floor_s"].fillna(0).astype(int)
    adjusted["empirical_floor_S"] = adjusted["empirical_floor_S"].fillna(0).astype(int)
    adjusted["seasonal_floor_s"] = adjusted["seasonal_floor_s"].fillna(0).astype(int)
    adjusted["seasonal_floor_S"] = adjusted["seasonal_floor_S"].fillna(0).astype(int)
    adjusted["reorder_point_s"] = np.maximum(
        adjusted["reorder_point_s"],
        np.maximum(adjusted["empirical_floor_s"], adjusted["seasonal_floor_s"]),
    ).astype(int)
    adjusted["order_up_to_S"] = np.maximum(
        adjusted["order_up_to_S"],
        np.maximum(
            np.maximum(adjusted["empirical_floor_S"], adjusted["seasonal_floor_S"]),
            adjusted["reorder_point_s"] + 1,
        ),
    ).astype(int)
    return adjusted


def get_initial_balances(panel: pd.DataFrame, simulation_start: pd.Timestamp) -> pd.DataFrame:
    prior = (
        panel[panel["date"] < simulation_start]
        .sort_values(["location", "product", "date"])
        .groupby(["location", "product"], as_index=False)
        .tail(1)
    )
    # Remove rows where balance is NaN — they indicate missing snapshots
    prior = prior.dropna(subset=["balance"])
    initial = prior[["location", "product", "balance"]].rename(columns={"balance": "initial_balance"})

    missing_pairs = panel[["location", "product"]].drop_duplicates().merge(
        initial[["location", "product"]],
        on=["location", "product"],
        how="left",
        indicator=True,
    )
    missing_pairs = missing_pairs[missing_pairs["_merge"] == "left_only"].drop(columns="_merge")
    if not missing_pairs.empty:
        fallback = (
            panel[panel["date"] == simulation_start]
            .sort_values(["location", "product"])
            .merge(missing_pairs, on=["location", "product"], how="inner")
        )
        fallback = fallback[["location", "product", "balance"]].rename(
            columns={"balance": "initial_balance"}
        )
        initial = pd.concat([initial, fallback], ignore_index=True)

    initial["initial_balance"] = initial["initial_balance"].fillna(0)
    return initial.drop_duplicates(subset=["location", "product"], keep="last")


def simulate_policy(
    panel: pd.DataFrame,
    forecast: pd.DataFrame,
    policy: pd.DataFrame,
    horizon: Horizon,
    *,
    warmup_days: int = 45,
) -> pd.DataFrame:
    required_forecast_cols = {"date", "location", "product", "forecast_demand", "forecast_std", "promo_uplift"}
    missing_forecast = required_forecast_cols - set(forecast.columns)
    if missing_forecast:
        raise ValueError(f"forecast missing required columns: {missing_forecast}")

    required_policy_cols = {
        "location", "product", "reorder_point_s", "order_up_to_S",
        "lead_time_days", "purchase_price", "cost_of_ordering", "minimum_delivery_batch",
    }
    missing_policy = required_policy_cols - set(policy.columns)
    if missing_policy:
        raise ValueError(f"policy missing required columns: {missing_policy}")

    simulation_start = horizon.start - pd.Timedelta(days=warmup_days)
    simulation_panel = panel[
        (panel["date"] >= simulation_start) & (panel["date"] <= horizon.end)
    ].copy()
    simulation_panel = simulation_panel.merge(
        forecast[
            [
                "date",
                "location",
                "product",
                "forecast_demand",
                "forecast_std",
                "promo_uplift",
            ]
        ].rename(columns={"promo_uplift": "forecast_promo_uplift"}),
        on=["date", "location", "product"],
        how="left",
    )
    simulation_panel = simulation_panel.merge(
        policy[
            [
                "location",
                "location_name",
                "product",
                "product_name",
                "supplier",
                "abc_class",
                "reorder_point_s",
                "order_up_to_S",
                "z_value",
                "review_days",
                "lead_time_days",
                "purchase_price",
                "sales_price",
                "cost_of_ordering",
                "minimum_delivery_batch",
            ]
        ],
        on=["location", "product"],
        how="left",
        suffixes=("", "_policy"),
    )
    initial_balances = get_initial_balances(panel, simulation_start)
    simulation_panel = simulation_panel.merge(
        initial_balances, on=["location", "product"], how="left"
    )

    simulation_rows: list[dict[str, object]] = []
    for _, group in simulation_panel.groupby(["location", "product"], sort=True):
        group = group.sort_values("date").copy()
        opening_inventory = float(group["initial_balance"].iloc[0] or 0)
        pending_orders: list[tuple[pd.Timestamp, int]] = []

        for row in group.itertuples(index=False):
            received_qty = sum(qty for arrival, qty in pending_orders if arrival == row.date)
            pending_orders = [(arrival, qty) for arrival, qty in pending_orders if arrival != row.date]
            opening_inventory += received_qty

            on_order_before = sum(qty for _, qty in pending_orders)
            inventory_position_before_order = opening_inventory + on_order_before

            reorder_point = int(row.reorder_point_s or 0)
            order_up_to = int(row.order_up_to_S or 0)
            batch_size = int(row.minimum_delivery_batch or 1)
            pref_lt = getattr(row, "lead_time_days_policy", None)
            if pref_lt is not None and not (isinstance(pref_lt, float) and np.isnan(pref_lt)):
                lead_time_days = int(pref_lt or 0)
            else:
                lead_time_days = int(row.lead_time_days or 0)

            order_qty = 0
            arrival_date = pd.NaT
            ordering_cost = 0.0
            if inventory_position_before_order <= reorder_point and order_up_to > inventory_position_before_order:
                raw_qty = order_up_to - inventory_position_before_order
                order_qty = round_up_to_batch(raw_qty, batch_size)
                if order_qty > 0:
                    ordering_cost = float(row.cost_of_ordering or 0.0)
                    if lead_time_days == 0:
                        # LT=0: entrega imediata, disponivel para venda no mesmo dia
                        received_qty += order_qty
                        opening_inventory += order_qty
                        arrival_date = row.date
                    else:
                        arrival_date = row.date + pd.Timedelta(days=lead_time_days)
                        pending_orders.append((arrival_date, order_qty))

            on_order_after = sum(qty for _, qty in pending_orders)
            inventory_position_after_order = opening_inventory + on_order_after

            demand = float(row.corrected_demand or 0.0)
            fulfilled_units = min(opening_inventory, demand)
            lost_sales_units = max(demand - opening_inventory, 0.0)
            ending_inventory = opening_inventory - fulfilled_units
            is_stockout = lost_sales_units > 0

            purchase_price = float(row.purchase_price or 0.0)
            simulated_inventory_value = ending_inventory * purchase_price
            actual_balance = float(row.balance) if pd.notna(row.balance) else np.nan
            actual_inventory_value = (
                actual_balance * purchase_price if pd.notna(actual_balance) else np.nan
            )

            simulation_rows.append(
                {
                    "horizon_name": horizon.name,
                    "date": row.date,
                    "location": row.location,
                    "location_name": row.location_name,
                    "product": row.product,
                    "product_name": row.product_name,
                    "supplier": row.supplier,
                    "abc_class": row.abc_class,
                    "lead_time_days": lead_time_days,
                    "reorder_point_s": reorder_point,
                    "order_up_to_S": order_up_to,
                    "z_value": float(row.z_value or 0.0),
                    "review_days": int(row.review_days or 0),
                    "opening_inventory": round(opening_inventory, 4),
                    "received_qty": received_qty,
                    "inventory_position_before_order": round(
                        inventory_position_before_order, 4
                    ),
                    "order_qty": order_qty,
                    "arrival_date": arrival_date,
                    "inventory_position_after_order": round(inventory_position_after_order, 4),
                    "on_order_after": on_order_after,
                    "forecast_demand": float(row.forecast_demand or 0.0),
                    "forecast_std": float(row.forecast_std or 0.0),
                    "promo_uplift": float(row.forecast_promo_uplift or 1.0),
                    "actual_demand": demand,
                    "fulfilled_units": round(fulfilled_units, 4),
                    "lost_sales_units": round(lost_sales_units, 4),
                    "ending_inventory": round(ending_inventory, 4),
                    "simulated_stockout_flag": int(is_stockout),
                    "purchase_price": purchase_price,
                    "sales_price": float(row.sales_price or 0.0),
                    "simulated_inventory_value": round(simulated_inventory_value, 4),
                    "ordering_cost": round(ordering_cost, 4),
                    "actual_balance": actual_balance,
                    "actual_inventory_value": actual_inventory_value,
                    "actual_stockout_flag": int(row.actual_stockout_flag),
                    "is_promo": int(row.is_promo),
                    "campaign_type": row.campaign_type,
                    "in_evaluation_window": int(row.date >= horizon.start),
                }
            )

            opening_inventory = ending_inventory

    simulation = pd.DataFrame(simulation_rows)
    simulation = simulation[simulation["in_evaluation_window"] == 1].drop(
        columns=["in_evaluation_window"]
    )
    return simulation.reset_index(drop=True)


def build_overall_metrics(simulation: pd.DataFrame) -> dict[str, float]:
    total_rows = len(simulation)
    horizon_days = int(simulation["date"].nunique()) if total_rows else 0

    service_level = 1 - float(simulation["simulated_stockout_flag"].mean()) if total_rows else 0.0
    actual_service_level = 1 - float(simulation["actual_stockout_flag"].mean()) if total_rows else 0.0
    avg_inventory_value = (
        float(simulation["simulated_inventory_value"].mean()) if total_rows else 0.0
    )
    actual_avg_inventory_value = (
        float(simulation["actual_inventory_value"].mean()) if total_rows else 0.0
    )
    total_ordering_cost = float(simulation["ordering_cost"].sum()) if total_rows else 0.0
    total_lost_sales_units = float(simulation["lost_sales_units"].sum()) if total_rows else 0.0
    total_orders = int((simulation["order_qty"] > 0).sum()) if total_rows else 0
    total_forecast_units = float(simulation["forecast_demand"].sum()) if total_rows else 0.0
    total_actual_units = float(simulation["actual_demand"].sum()) if total_rows else 0.0

    return {
        "service_level": round(service_level, 6),
        "actual_service_level": round(actual_service_level, 6),
        "service_level_delta_vs_actual": round(service_level - actual_service_level, 6),
        "avg_inventory_value": round(avg_inventory_value, 4),
        "actual_avg_inventory_value": round(actual_avg_inventory_value, 4),
        "inventory_value_delta_vs_actual": round(
            avg_inventory_value - actual_avg_inventory_value, 4
        ),
        "total_ordering_cost": round(total_ordering_cost, 4),
        "total_lost_sales_units": round(total_lost_sales_units, 4),
        "total_orders": total_orders,
        "total_forecast_units": round(total_forecast_units, 4),
        "total_actual_units": round(total_actual_units, 4),
        "horizon_days": horizon_days,
        "series_days": total_rows,
    }


def build_sku_metrics(simulation: pd.DataFrame, policy: pd.DataFrame) -> pd.DataFrame:
    metrics = (
        simulation.groupby(
            ["location", "location_name", "product", "product_name", "supplier"], as_index=False
        )
        .agg(
            abc_class=("abc_class", "max"),
            service_level=("simulated_stockout_flag", lambda s: 1 - float(np.mean(s))),
            actual_service_level=("actual_stockout_flag", lambda s: 1 - float(np.mean(s))),
            avg_inventory_value=("simulated_inventory_value", "mean"),
            actual_avg_inventory_value=("actual_inventory_value", "mean"),
            avg_inventory_units=("ending_inventory", "mean"),
            actual_avg_inventory_units=("actual_balance", "mean"),
            total_orders=("order_qty", lambda s: int(np.sum(s > 0))),
            total_order_units=("order_qty", "sum"),
            total_ordering_cost=("ordering_cost", "sum"),
            total_actual_demand=("actual_demand", "sum"),
            total_fulfilled_units=("fulfilled_units", "sum"),
            total_lost_sales_units=("lost_sales_units", "sum"),
            promo_days=("is_promo", "sum"),
            forecast_units=("forecast_demand", "sum"),
            stockout_days=("simulated_stockout_flag", "sum"),
            actual_stockout_days=("actual_stockout_flag", "sum"),
        )
        .sort_values(["location", "product"])
    )
    metrics["fill_rate"] = np.where(
        metrics["total_actual_demand"] > 0,
        metrics["total_fulfilled_units"] / metrics["total_actual_demand"],
        1.0,
    )
    metrics["service_level_delta_vs_actual"] = (
        metrics["service_level"] - metrics["actual_service_level"]
    )
    metrics["inventory_value_delta_vs_actual"] = (
        metrics["avg_inventory_value"] - metrics["actual_avg_inventory_value"]
    )
    metrics = metrics.merge(
        policy[
            [
                "location",
                "product",
                "reorder_point_s",
                "order_up_to_S",
                "lead_time_days",
                "z_value",
                "review_days",
                "purchase_price",
                "sales_price",
                "minimum_delivery_batch",
            ]
        ],
        on=["location", "product"],
        how="left",
    )
    return metrics


def search_policy_parameters(
    panel: pd.DataFrame,
    horizon: Horizon,
    forecast_mode: str,
    service_level_target: float,
    z_grid: list[float],
    cover_days_grid: list[int],
    *,
    warmup_days: int = 45,
) -> tuple[dict[str, float | int], pd.DataFrame]:
    forecast = build_forecast(panel, horizon=horizon, mode=forecast_mode)
    summary = build_summary_from_forecast(forecast)

    search_rows: list[dict[str, float | int]] = []
    best_choice: dict[str, float | int] | None = None
    best_objective = float("inf")

    for z_value in z_grid:
        for review_days in cover_days_grid:
            policy = build_policy(summary, z_value=z_value, review_days=review_days)
            simulation = simulate_policy(
                panel,
                forecast=forecast,
                policy=policy,
                horizon=horizon,
                warmup_days=warmup_days,
            )
            metrics = build_overall_metrics(simulation)
            objective = compute_policy_objective(metrics, service_level_target)
            row = {
                "z_value": z_value,
                "review_days": review_days,
                "objective": round(objective, 4),
                **metrics,
            }
            search_rows.append(row)
            if objective < best_objective:
                best_objective = objective
                best_choice = row

    if best_choice is None:
        raise RuntimeError("Could not tune policy parameters.")

    return best_choice, pd.DataFrame(search_rows).sort_values("objective")


def compute_policy_objective(
    metrics: dict[str, float],
    service_level_target: float,
    *,
    service_penalty_scale: float = 1_000_000,
) -> float:
    return (
        metrics["avg_inventory_value"]
        + metrics["total_ordering_cost"] / max(metrics["horizon_days"], 1)
        + max(0.0, service_level_target - metrics["service_level"]) * service_penalty_scale
    )


def tune_local_sku_overrides(
    panel: pd.DataFrame,
    horizon: Horizon,
    static_summary: pd.DataFrame,
    validation_forecast: pd.DataFrame,
    *,
    global_z_value: float,
    global_review_days: int,
    service_level_target: float,
    z_grid: list[float],
    cover_days_grid: list[int],
    warmup_days: int = 45,
    apply_only_if_changed: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    override_rows: list[dict[str, object]] = []
    search_rows: list[dict[str, object]] = []

    for summary_row in static_summary.itertuples(index=False):
        sku_summary = static_summary[
            (static_summary["location"] == summary_row.location)
            & (static_summary["product"] == summary_row.product)
        ].copy()
        item_panel = panel[
            (panel["location"] == summary_row.location) & (panel["product"] == summary_row.product)
        ].copy()
        item_forecast = validation_forecast[
            (validation_forecast["location"] == summary_row.location)
            & (validation_forecast["product"] == summary_row.product)
        ].copy()

        best_metrics: dict[str, float] | None = None
        best_choice: dict[str, object] | None = None
        best_objective = float("inf")

        for z_value in z_grid:
            for review_days in cover_days_grid:
                item_policy = build_policy(
                    sku_summary,
                    z_value=z_value,
                    review_days=review_days,
                )
                item_simulation = simulate_policy(
                    item_panel,
                    forecast=item_forecast,
                    policy=item_policy,
                    horizon=horizon,
                    warmup_days=warmup_days,
                )
                metrics = build_overall_metrics(item_simulation)
                objective = compute_policy_objective(metrics, service_level_target)
                search_row = {
                    "location": summary_row.location,
                    "product": summary_row.product,
                    "product_name": summary_row.product_name,
                    "z_value": z_value,
                    "review_days": review_days,
                    "objective": round(objective, 4),
                    **metrics,
                }
                search_rows.append(search_row)

                if objective < best_objective:
                    best_objective = objective
                    best_metrics = metrics
                    best_choice = search_row

        if best_choice is None or best_metrics is None:
            continue

        changed = (
            float(best_choice["z_value"]) != float(global_z_value)
            or int(best_choice["review_days"]) != int(global_review_days)
        )

        if changed or not apply_only_if_changed:
            override_rows.append(
                {
                    "location": summary_row.location,
                    "product": summary_row.product,
                    "product_name": summary_row.product_name,
                    "z_value": float(best_choice["z_value"]),
                    "review_days": int(best_choice["review_days"]),
                    "validation_service_level": round(best_metrics["service_level"], 6),
                    "validation_avg_inventory_value": round(
                        best_metrics["avg_inventory_value"], 4
                    ),
                    "validation_total_ordering_cost": round(
                        best_metrics["total_ordering_cost"], 4
                    ),
                }
            )

    return (
        pd.DataFrame(override_rows).sort_values(["location", "product"])
        if override_rows
        else pd.DataFrame(
            columns=[
                "location",
                "product",
                "product_name",
                "z_value",
                "review_days",
                "validation_service_level",
                "validation_avg_inventory_value",
                "validation_total_ordering_cost",
            ]
        ),
        pd.DataFrame(search_rows).sort_values(["location", "product", "objective"]),
    )
