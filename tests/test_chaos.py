# CHAOS TESTS - Adversarial scenarios for the inventory policy engine
#
# Each scenario:
#   1. Creates a minimal synthetic input designed to trigger a specific failure mode
#   2. Runs the engine function
#   3. Asserts what SHOULD happen based on business logic
#   4. Reports what ACTUALLY happens (so you can see silent failures)
#
# Usage: python -m pytest tests/test_chaos.py -v  (or just run directly)

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from stock_policy_product.engine import (
    Horizon,
    add_censored_demand_adjustment,
    build_daily_panel,
    build_forecast,
    build_overall_metrics,
    build_policy,
    build_sku_metrics,
    build_summary_from_forecast,
    compute_policy_objective,
    compute_promo_uplift,
    get_initial_balances,
    prepare_enriched_panel,
    round_up_to_batch,
    search_policy_parameters,
    simulate_policy,
    tune_local_sku_overrides,
)

# Shared helpers -----------------------------------------------------------

TRAIN_END = pd.Timestamp("2024-09-30")
HORIZON = Horizon(
    name="test",
    train_end=TRAIN_END,
    start=pd.Timestamp("2024-10-01"),
    end=pd.Timestamp("2024-12-31"),
)


def make_dates(start: str, days: int) -> list[pd.Timestamp]:
    return list(pd.date_range(start, periods=days, freq="D"))


def _build_simple_panel(
    dates: list[pd.Timestamp],
    locations: list[str],
    products: list[str],
    demand: list[float] | float,
    *,
    balances_before: float = np.nan,
    lead_time: int = 3,
) -> pd.DataFrame:
    if isinstance(demand, (float, int)):
        demand = [float(demand)] * len(dates)
    panel_rows = []
    for loc in locations:
        for prod in products:
            for i, d in enumerate(dates):
                dv = demand[i]
                bal = float(balances_before) if not np.isnan(balances_before) and d < pd.Timestamp("2024-10-01") else np.nan
                stockout = int(bal <= 0) if not pd.isna(bal) else 0
                panel_rows.append(
                    {
                        "date": d,
                        "location": loc,
                        "product": prod,
                        "location_name": f"LOJA {loc}",
                        "product_name": "PROD",
                        "supplier": "99999",
                        "purchase_price": 10.0,
                        "sales_price": 25.0,
                        "minimum_delivery_batch": 1,
                        "cost_of_ordering": 5.0,
                        "lead_time_days": lead_time,
                        "demand": dv,
                        "sales_value": dv * 25.0,
                        "balance": bal,
                        "balance_value": bal * 10.0 if pd.notna(bal) else np.nan,
                        "actual_stockout_flag": stockout,
                        "is_promo": 0,
                        "campaign_type": "",
                        "weekday": d.weekday(),
                        "corrected_demand": dv,
                        "promo_uplift": 1.0,
                        "dow_baseline": float(np.mean(demand)),
                        "sku_baseline": float(np.mean(demand)),
                        "store_weekday_baseline": float(np.mean(demand)),
                    }
                )
    df = pd.DataFrame(panel_rows)
    return df.sort_values(["location", "product", "date"]).reset_index(drop=True)


def _make_forecast_stub(
    panel: pd.DataFrame, horizon: Horizon, demand_val: float = 0.0, std_val: float = 0.0
) -> pd.DataFrame:
    """Build a minimal forecast without calling the full build_forecast engine."""
    rows = panel[
        (panel["date"] >= horizon.start) & (panel["date"] <= horizon.end)
    ][["date", "location", "product"]].drop_duplicates().copy()
    rows["forecast_demand"] = demand_val
    rows["forecast_std"] = std_val
    rows["promo_uplift"] = 1.0
    return rows


def _assert_no_crash(sim: pd.DataFrame) -> None:
    assert sim is not None, "simulador retornou None"
    assert len(sim) > 0, "simulador retornou dataframe vazio"


# === SCENARIO 1: DEMANDA EXPLOSIVA =========================================
# O que testa: pico de demanda muito acima da media historica

def test_demanda_explosiva():
    dates = make_dates("2024-07-01", 184)
    locs, prods = ["841"], ["18064"]
    demand = [5.0] * 150 + [500.0] * 5 + [5.0] * 29

    panel = _build_simple_panel(dates, locs, prods, demand, balances_before=30.0, lead_time=3)
    # Trocar corrigida para os dias de pico
    for i, d in enumerate(dates):
        if d >= HORIZON.start:
            idx = panel[panel["date"] == d].index
            panel.loc[idx, "corrected_demand"] = demand[i]

    forecast = build_forecast(panel, horizon=HORIZON, mode="static")
    summary = build_summary_from_forecast(forecast)
    policy = build_policy(summary, z_value=1.65, review_days=7)

    sim = simulate_policy(panel, forecast=forecast, policy=policy, horizon=HORIZON, warmup_days=45)
    _assert_no_crash(sim)

    # Os dias de pico devem ter vendas perdidas
    spike = sim[(sim["date"] >= "2024-11-27") & (sim["date"] <= "2024-12-01")]
    lost = spike["lost_sales_units"].sum()
    stockouts = spike["simulated_stockout_flag"].sum()
    print(f"\n  [explosiva] lost_sales={lost:.0f}, stockouts={stockouts}")
    print(f"  [explosiva] SL total={1 - sim['simulated_stockout_flag'].mean():.4f}")

    if lost == 0:
        print("  AVISO: estoque inicial alto demais ou previsao superestimando demanda")


# === SCENARIO 2: DEMANDA ZERADA ============================================
# BUG #02 da auditoria: stockout_flag=1 quando ending_inventory=0 e demand=0

def test_demanda_zerada():
    dates = make_dates("2024-07-01", 184)
    locs, prods = ["841"], ["18064"]
    demand = [3.0] * 92 + [0.0] * 92

    panel = _build_simple_panel(dates, locs, prods, demand, balances_before=30.0, lead_time=3)

    forecast = build_forecast(panel, horizon=HORIZON, mode="static")
    summary = build_summary_from_forecast(forecast)
    policy = build_policy(summary, z_value=1.65, review_days=7)

    sim = simulate_policy(panel, forecast=forecast, policy=policy, horizon=HORIZON, warmup_days=45)
    _assert_no_crash(sim)

    oct_dec = sim[sim["date"] >= "2024-10-01"]
    false_rupture = oct_dec[
        (oct_dec["ending_inventory"] <= 0) & (oct_dec["actual_demand"] == 0)
        & (oct_dec["simulated_stockout_flag"] == 1)
    ]
    print(f"\n  [zerada] false_stockout_days={len(false_rupture)} (deve ser 0)")
    if len(false_rupture) > 0:
        print(f"  BUG CONFIRMADO: simulated_stockout_flag=1 quando ending_inventory=0 e demand=0")


# === SCENARIO 3: S < s DEADLOCK ============================================
# Politica invalida: order_up_to_S < reorder_point_s

def test_order_up_to_abaixo_reorder_point():
    dates = make_dates("2024-07-01", 184)
    locs, prods = ["841"], ["18064"]
    panel = _build_simple_panel(dates, locs, prods, demand=5.0, balances_before=100.0, lead_time=3)

    forecast = build_forecast(panel, horizon=HORIZON, mode="static")
    summary = build_summary_from_forecast(forecast)
    policy = build_policy(summary, z_value=1.65, review_days=7)

    policy.loc[0, "reorder_point_s"] = 50
    policy.loc[0, "order_up_to_S"] = 1

    sim = simulate_policy(panel, forecast=forecast, policy=policy, horizon=HORIZON, warmup_days=45)
    _assert_no_crash(sim)

    oct_dec = sim[sim["date"] >= "2024-10-01"]
    orders = oct_dec[oct_dec["order_qty"] > 0]
    ns = 1 - oct_dec["simulated_stockout_flag"].mean()

    print(f"\n  [S<s] orders={len(orders)}, SL={ns:.4f}")
    if len(orders) == 0:
        print("  DEADLOCK CONFIRMADO: S < s impede qualquer pedido")
    if ns > 0.5:
        print("  Estoque inicial alto mascarou o deadlock")


# === SCENARIO 4: ESTOQUE INICIAL NEGATIVO ==================================

def test_estoque_inicial_negativo():
    dates = make_dates("2024-07-01", 184)
    locs, prods = ["841"], ["18064"]

    panel_rows = []
    for loc in locs:
        for prod in prods:
            for i, d in enumerate(dates):
                bal = -50.0 if d < HORIZON.start else np.nan
                panel_rows.append({
                    "date": d, "location": loc, "product": prod,
                    "location_name": f"LOJA {loc}", "product_name": "PROD",
                    "supplier": "99999", "purchase_price": 10.0, "sales_price": 25.0,
                    "minimum_delivery_batch": 1, "cost_of_ordering": 5.0, "lead_time_days": 3,
                    "demand": 5.0, "sales_value": 125.0, "balance": bal,
                    "balance_value": bal * 10.0 if pd.notna(bal) else np.nan,
                    "actual_stockout_flag": 1 if pd.notna(bal) and bal <= 0 else 0,
                    "is_promo": 0, "campaign_type": "", "weekday": d.weekday(),
                    "corrected_demand": 5.0, "promo_uplift": 1.0,
                    "dow_baseline": 5.0, "sku_baseline": 5.0, "store_weekday_baseline": 5.0,
                })
    panel = pd.DataFrame(panel_rows).sort_values(["location", "product", "date"]).reset_index(drop=True)

    initial = get_initial_balances(panel, HORIZON.start)
    init_val = initial.loc[
        (initial["location"] == "841") & (initial["product"] == "18064"), "initial_balance"
    ].values[0]

    forecast = build_forecast(panel, horizon=HORIZON, mode="static")
    summary = build_summary_from_forecast(forecast)
    policy = build_policy(summary, z_value=1.65, review_days=7)

    sim = simulate_policy(panel, forecast=forecast, policy=policy, horizon=HORIZON, warmup_days=45)
    _assert_no_crash(sim)

    neg_ending = sim[sim["ending_inventory"] < 0]
    neg_fulfilled = sim[sim["fulfilled_units"] < 0]

    print(f"\n  [estoque_negativo] initial_balance={init_val}")
    print(f"  [estoque_negativo] days with negative ending_inventory: {len(neg_ending)}")
    print(f"  [estoque_negativo] days with negative fulfilled_units: {len(neg_fulfilled)}")

    if len(neg_ending) > 0:
        print("  BUG: ending_inventory negativo - estoque nunca deve ficar negativo")
    if len(neg_fulfilled) > 0:
        print("  BUG: fulfilled_units negativo - venda de estoque inexistente")


# === SCENARIO 5: SKU SEM HISTORICO =========================================

def test_sku_sem_historico():
    dates = make_dates("2024-07-01", 184)
    locs, prods = ["841"], ["18064", "NOVO_SKU"]

    panel_rows = []
    for loc in locs:
        for prod in prods:
            for i, d in enumerate(dates):
                if prod == "NOVO_SKU":
                    dv = 0.0
                    bal = np.nan
                else:
                    dv = 5.0
                    bal = 100.0 if d < HORIZON.start else np.nan
                panel_rows.append({
                    "date": d, "location": loc, "product": prod,
                    "location_name": f"LOJA {loc}", "product_name": f"PROD_{prod}",
                    "supplier": "99999", "purchase_price": 10.0, "sales_price": 25.0,
                    "minimum_delivery_batch": 1, "cost_of_ordering": 5.0, "lead_time_days": 3,
                    "demand": dv, "sales_value": dv * 25.0, "balance": bal,
                    "balance_value": bal * 10.0 if pd.notna(bal) else np.nan,
                    "actual_stockout_flag": 0 if prod != "NOVO_SKU" else (0 if d < HORIZON.start else 1),
                    "is_promo": 0, "campaign_type": "", "weekday": d.weekday(),
                    "corrected_demand": dv, "promo_uplift": 1.0,
                    "dow_baseline": 5.0 if prod != "NOVO_SKU" else 0.0,
                    "sku_baseline": 5.0 if prod != "NOVO_SKU" else 0.0,
                    "store_weekday_baseline": 5.0,
                })
    panel = pd.DataFrame(panel_rows).sort_values(["location", "product", "date"]).reset_index(drop=True)

    forecast = build_forecast(panel, horizon=HORIZON, mode="static")
    summary = build_summary_from_forecast(forecast)
    policy = build_policy(summary, z_value=1.65, review_days=7)

    novo_sku_pol = policy[policy["product"] == "NOVO_SKU"]
    s_val = novo_sku_pol["reorder_point_s"].values[0]
    S_val = novo_sku_pol["order_up_to_S"].values[0]
    print(f"\n  [sem_historico] NOVO_SKU: s={s_val}, S={S_val}")
    assert s_val >= 1, "SKU sem historico deveria ter s >= 1 (minimum_presentation_stock)"

    sim = simulate_policy(panel, forecast=forecast, policy=policy, horizon=HORIZON, warmup_days=45)
    _assert_no_crash(sim)

    novo_sim = sim[sim["product"] == "NOVO_SKU"]
    print(f"  [sem_historico] NOVO_SKU sim rows={len(novo_sim)}, orders={novo_sim['order_qty'].sum()}")
    assert len(novo_sim) > 0


# === SCENARIO 6: LEAD TIME EXTREMO =========================================

def test_lead_time_extremo():
    dates = make_dates("2024-07-01", 184)
    locs, prods = ["1314"], ["18064"]

    panel = _build_simple_panel(dates, locs, prods, demand=5.0, balances_before=100.0, lead_time=9)
    # Override LT no painel
    panel["lead_time_days"] = 30

    forecast = build_forecast(panel, horizon=HORIZON, mode="static")
    summary = build_summary_from_forecast(forecast)
    policy = build_policy(summary, z_value=1.65, review_days=7)
    policy["lead_time_days"] = 30

    sim = simulate_policy(panel, forecast=forecast, policy=policy, horizon=HORIZON, warmup_days=45)
    _assert_no_crash(sim)

    arrivals = sim[sim["received_qty"] > 0]["date"].unique()
    print(f"\n  [lead_time_extremo] first arrival dates: {sorted(arrivals)[:5]}")
    print(f"  [lead_time_extremo] SL={1 - sim['simulated_stockout_flag'].mean():.4f}")


# === SCENARIO 7: z INVALIDO ================================================

def test_z_invalido():
    dates = make_dates("2024-07-01", 184)
    locs, prods = ["841"], ["18064"]
    panel = _build_simple_panel(dates, locs, prods, demand=5.0, balances_before=100.0)
    forecast = build_forecast(panel, horizon=HORIZON, mode="static")
    summary = build_summary_from_forecast(forecast)

    for bad_z in [-999, -100, -1.0, 0.0]:
        policy = build_policy(summary, z_value=bad_z, review_days=7)
        s = policy["reorder_point_s"].values[0]
        S = policy["order_up_to_S"].values[0]
        print(f"\n  [z_invalido] z={bad_z:6.1f} -> s={s}, S={S}")
        assert s >= 1, f"z={bad_z} gerou s={s} < 1"


# === SCENARIO 8: ROUND_UP_TO_BATCH =========================================

def test_round_up_to_batch_edges():
    cases = [
        (0, 1, 0, "qty=0 -> 0"),
        (-5, 1, 0, "qty<0 -> 0"),
        (10, 3, 12, "10 up to batch 3 -> 12"),
        (9, 3, 9, "9 fits batch 3 -> 9"),
        (1, np.nan, 1, "batch=NaN -> ceil"),
        (1, 0, 1, "batch=0 -> ceil"),
        (1, -1, 1, "batch<0 -> ceil"),
        (float("inf"), 1, 0, "inf -> 0 (crash?)"),
    ]
    for qty, batch, expected, label in cases:
        try:
            result = round_up_to_batch(qty, batch)
            status = "OK" if result == expected else "FAIL"
            print(f"  [round_up] {status} {label}: got {result}, expected {expected}")
        except Exception as e:
            print(f"  [round_up] CRASH {label}: {e}")


# === SCENARIO 9: POLICY VAZIA ==============================================

def test_simulator_policy_vazia():
    dates = make_dates("2024-07-01", 184)
    locs, prods = ["841"], ["18064"]
    panel = _build_simple_panel(dates, locs, prods, demand=5.0, balances_before=50.0)
    forecast = build_forecast(panel, horizon=HORIZON, mode="static")
    summary = build_summary_from_forecast(forecast)

    empty_policy = summary[["location", "product", "location_name", "product_name", "supplier"]].copy()

    try:
        sim = simulate_policy(panel, forecast=forecast, policy=empty_policy, horizon=HORIZON, warmup_days=45)
        print(f"\n  [policy_vazia] sim rows={len(sim)}, orders={sim['order_qty'].sum()}")
        _assert_no_crash(sim)
    except ValueError as e:
        print(f"\n  [policy_vazia] ERROR BEM DEFINIDO: {e}")
        # This is the expected behavior - clear error instead of KeyError


# === SCENARIO 10: CENSURA 100% =============================================

def test_censura_cem_porcento():
    dates = make_dates("2023-01-01", 365)
    locs, prods = ["1314"], ["18064"]

    panel_rows = []
    for loc in locs:
        for prod in prods:
            for d in dates:
                panel_rows.append({
                    "date": d, "location": loc, "product": prod,
                    "location_name": f"LOJA {loc}", "product_name": "PROD",
                    "supplier": "99999", "purchase_price": 10.0, "sales_price": 25.0,
                    "minimum_delivery_batch": 1, "cost_of_ordering": 5.0, "lead_time_days": 9,
                    "demand": 0.0, "sales_value": 0.0, "balance": 0.0,
                    "balance_value": 0.0, "actual_stockout_flag": 1,
                    "is_promo": 0, "campaign_type": "", "weekday": d.weekday(),
                    "corrected_demand": np.nan, "promo_uplift": 1.0,
                })
    panel = pd.DataFrame(panel_rows).sort_values(["location", "product", "date"]).reset_index(drop=True)

    panel_censored = add_censored_demand_adjustment(panel, pd.Timestamp("2024-09-30"))

    corrected = panel_censored["corrected_demand"]
    na_count = panel_censored["dow_baseline"].isna().sum()
    print(f"\n  [censura_100] corrected_demand sum={corrected.sum():.2f}, nunique={corrected.nunique()}")
    print(f"  [censura_100] dow_baseline NaN: {na_count}/{len(panel_censored)}")

    if corrected.sum() == 0:
        print("  BUG SILENCIOSO: correcao de censura falha quando 100% dos dias estao em ruptura")
        print("  corrected_demand = demand (0) em todos os dias - demanda censurada nao recuperada")

    assert len(panel_censored) > 0


# === SCENARIO 11: POLICY OBJECTIVE EXTREMOS ================================

def test_policy_objective_extremos():
    metrics_normal = {
        "service_level": 0.95,
        "avg_inventory_value": 5000.0,
        "total_ordering_cost": 200.0,
        "horizon_days": 92,
    }
    metrics_ruim = {
        "service_level": 0.0,
        "avg_inventory_value": 0.0,
        "total_ordering_cost": 0.0,
        "horizon_days": 92,
    }
    metrics_caro = {
        "service_level": 1.0,
        "avg_inventory_value": 500_000.0,
        "total_ordering_cost": 50_000.0,
        "horizon_days": 92,
    }

    obj_normal = compute_policy_objective(metrics_normal, 0.92)
    obj_ruim = compute_policy_objective(metrics_ruim, 0.92)
    obj_caro = compute_policy_objective(metrics_caro, 0.92)

    print(f"\n  [objective] normal (SL=0.95, cap=5k):  objective={obj_normal:.2f}")
    print(f"  [objective] ruim   (SL=0.00, cap=0):    objective={obj_ruim:.2f}")
    print(f"  [objective] caro   (SL=1.00, cap=500k): objective={obj_caro:.2f}")

    assert obj_ruim > obj_normal, f"SL=0 deveria ter objective MAIOR que SL=0.95"
    assert obj_ruim > 900_000, f"SL=0 objective={obj_ruim} deveria ser > 900k"
    assert obj_caro > obj_normal, f"Capital 500k deveria ter objective maior"


# === SCENARIO 12: PROMO_UPLIFT SEM PROMO ===================================

def test_promo_uplift_sem_promo():
    dates = make_dates("2024-07-01", 90)
    locs, prods = ["841"], ["18064"]
    panel = _build_simple_panel(dates, locs, prods, demand=5.0, balances_before=50.0)
    panel["is_promo"] = 0
    panel["campaign_type"] = ""

    uplift = compute_promo_uplift(panel, TRAIN_END)
    sku_uplift = uplift[(uplift["location"] == "841") & (uplift["product"] == "18064")]["promo_uplift"].values[0]
    print(f"\n  [promo_sem_promo] promo_uplift={sku_uplift} (expected 1.0)")
    assert sku_uplift == 1.0, f"FAUNA: SKU sem promo deveria ter uplift=1.0, mas tem {sku_uplift}"


# === SCENARIO 13: GET_INITIAL_BALANCES SEM SNAPSHOT ========================

def test_get_initial_balances_sem_snapshot():
    dates = make_dates("2024-10-01", 92)
    locs, prods = ["841"], ["18064"]

    panel_rows = []
    for loc in locs:
        for prod in prods:
            for d in dates:
                panel_rows.append({
                    "date": d, "location": loc, "product": prod,
                    "location_name": f"LOJA {loc}", "product_name": "PROD",
                    "supplier": "99999", "purchase_price": 10.0, "sales_price": 25.0,
                    "minimum_delivery_batch": 1, "cost_of_ordering": 5.0, "lead_time_days": 3,
                    "demand": 5.0, "sales_value": 125.0, "balance": np.nan,
                    "balance_value": np.nan, "actual_stockout_flag": 0,
                    "is_promo": 0, "campaign_type": "", "weekday": d.weekday(),
                    "corrected_demand": 5.0, "promo_uplift": 1.0,
                    "dow_baseline": 5.0, "sku_baseline": 5.0, "store_weekday_baseline": 5.0,
                })
    panel = pd.DataFrame(panel_rows).sort_values(["location", "product", "date"]).reset_index(drop=True)

    initial = get_initial_balances(panel, HORIZON.start)
    print(f"\n  [sem_snapshot] initial_balance rows: {len(initial)}")
    if len(initial) > 0:
        print(f"  [sem_snapshot] value: {initial['initial_balance'].values}")
    else:
        print(f"  [sem_snapshot] DATAFRAME VAZIO")

    forecast = build_forecast(panel, horizon=HORIZON, mode="static")
    summary = build_summary_from_forecast(forecast)
    policy = build_policy(summary, z_value=1.65, review_days=7)

    sim = simulate_policy(panel, forecast=forecast, policy=policy, horizon=HORIZON, warmup_days=0)
    print(f"  [sem_snapshot] SIMULATED OK, rows={len(sim)}")
    _assert_no_crash(sim)


# === SCENARIO 14: POLICY.CSV S > s =========================================

def test_policy_garante_S_maior_s():
    policy_path = PROJECT_ROOT / "policy.csv"
    if not policy_path.exists():
        print(f"\n  [policy_S>s] policy.csv nao encontrado - pulando")
        return

    policy = pd.read_csv(policy_path)
    policy["reorder_point_s"] = pd.to_numeric(policy["reorder_point_s"], errors="coerce")
    policy["order_up_to_S"] = pd.to_numeric(policy["order_up_to_S"], errors="coerce")

    violations = policy[policy["order_up_to_S"] <= policy["reorder_point_s"]]
    if len(violations) > 0:
        print(f"\n  [policy_S>s] VIOLACOES: {len(violations)} SKUs com S <= s:")
        for _, row in violations.iterrows():
            print(f"    product={row['product']}, location={row['location']}: s={row['reorder_point_s']}, S={row['order_up_to_S']}")
    else:
        print(f"\n  [policy_S>s] Todas as {len(policy)} linhas tem S > s")

    assert len(violations) == 0, f"{len(violations)} SKUs com S <= s na politica final"


# === SCENARIO 15: RUPTURA PROLONGADA =======================================

def test_ruptura_prolongada():
    dates = make_dates("2024-07-01", 184)
    locs, prods = ["841"], ["18064"]

    panel_rows = []
    for loc in locs:
        for prod in prods:
            for i, d in enumerate(dates):
                bal = 0.0 if d >= pd.Timestamp("2024-08-01") else 100.0
                panel_rows.append({
                    "date": d, "location": loc, "product": prod,
                    "location_name": f"LOJA {loc}", "product_name": "PROD",
                    "supplier": "99999", "purchase_price": 10.0, "sales_price": 25.0,
                    "minimum_delivery_batch": 1, "cost_of_ordering": 5.0, "lead_time_days": 3,
                    "demand": 5.0, "sales_value": 125.0, "balance": bal,
                    "balance_value": bal * 10.0, "actual_stockout_flag": int(bal <= 0),
                    "is_promo": 0, "campaign_type": "", "weekday": d.weekday(),
                    "corrected_demand": 5.0, "promo_uplift": 1.0,
                    "dow_baseline": 5.0, "sku_baseline": 5.0, "store_weekday_baseline": 5.0,
                })
    panel = pd.DataFrame(panel_rows).sort_values(["location", "product", "date"]).reset_index(drop=True)

    forecast = build_forecast(panel, horizon=HORIZON, mode="static")
    summary = build_summary_from_forecast(forecast)
    policy = build_policy(summary, z_value=1.65, review_days=7)

    # Zera saldo inicial para forcar ruptura
    panel.loc[panel["date"] < HORIZON.start, "balance"] = 0.0
    panel.loc[panel["date"] < HORIZON.start, "actual_stockout_flag"] = 1

    sim = simulate_policy(panel, forecast=forecast, policy=policy, horizon=HORIZON, warmup_days=45)
    _assert_no_crash(sim)

    oct_dec = sim[sim["date"] >= "2024-10-01"]
    ns = 1 - oct_dec["simulated_stockout_flag"].mean()
    lost = oct_dec["lost_sales_units"].sum()
    print(f"\n  [ruptura_prolongada] SL={ns:.4f}, lost_sales={lost:.1f}")
    print(f"  [ruptura_prolongada] stockout days={oct_dec['simulated_stockout_flag'].sum()}/{len(oct_dec)}")


# === SCENARIO 16: WARMUP INSUFICIENTE ======================================

def test_warmup_insuficiente():
    dates = make_dates("2024-09-28", 100)
    locs, prods = ["1314"], ["18064"]
    panel = _build_simple_panel(dates, locs, prods, demand=5.0, balances_before=100.0, lead_time=9)
    forecast = build_forecast(panel, horizon=HORIZON, mode="static")
    summary = build_summary_from_forecast(forecast)
    policy = build_policy(summary, z_value=1.65, review_days=7)

    for warmup in [1, 3, 10, 30, 45]:
        sim = simulate_policy(panel, forecast=forecast, policy=policy, horizon=HORIZON, warmup_days=warmup)
        first_order = sim[sim["order_qty"] > 0]
        ns = 1 - sim["simulated_stockout_flag"].mean()
        print(f"\n  [warmup] warmup={warmup:2d}: first_order={first_order['date'].min() if len(first_order) > 0 else 'N/A'}, SL={ns:.4f}")
        _assert_no_crash(sim)


# === SCENARIO 17: LEAD TIME ZERO ===========================================

def test_lead_time_zero():
    dates = make_dates("2024-07-01", 184)
    locs, prods = ["841"], ["18064"]
    panel = _build_simple_panel(dates, locs, prods, demand=5.0, balances_before=500.0, lead_time=0)
    panel["lead_time_days"] = 0

    forecast = build_forecast(panel, horizon=HORIZON, mode="static")
    summary = build_summary_from_forecast(forecast)
    policy = build_policy(summary, z_value=1.65, review_days=7)
    policy["lead_time_days"] = 0

    sim = simulate_policy(panel, forecast=forecast, policy=policy, horizon=HORIZON, warmup_days=45)
    _assert_no_crash(sim)

    oct_days = sim[sim["date"] >= "2024-10-01"]
    print(f"\n  [lead_time_zero] SL={1 - oct_days['simulated_stockout_flag'].mean():.4f}")
    if len(oct_days[oct_days["order_qty"] > 0]) > 0:
        order_dates = oct_days[oct_days["order_qty"] > 0]["date"].unique()
        arrival_dates = oct_days[oct_days["received_qty"] > 0]["date"].unique()
        print(f"  [lead_time_zero] order_dates={sorted(order_dates)[:5]}")
        print(f"  [lead_time_zero] arrival_dates={sorted(arrival_dates)[:5]}")


# === SCENARIO 18: DEMANDA FRACIONARIA ======================================

def test_demanda_fracionaria():
    dates = make_dates("2024-07-01", 184)
    locs, prods = ["841"], ["18064"]
    demand = ([2.5, 0.0, 1.3, 0.7, 3.1, 0.0, 1.8] * 27)[:184]

    panel = _build_simple_panel(dates, locs, prods, demand, balances_before=30.0, lead_time=3)
    for i, d in enumerate(dates):
        if d >= HORIZON.start:
            panel.loc[panel["date"] == d, "corrected_demand"] = demand[i]

    forecast = build_forecast(panel, horizon=HORIZON, mode="static")
    summary = build_summary_from_forecast(forecast)
    policy = build_policy(summary, z_value=1.65, review_days=7)

    sim = simulate_policy(panel, forecast=forecast, policy=policy, horizon=HORIZON, warmup_days=45)
    _assert_no_crash(sim)

    print(f"\n  [fracionaria] rows={len(sim)}, fulfilled={sim['fulfilled_units'].sum():.2f}")


# === SCENARIO 19: DATAS NAO CONSECUTIVAS ===================================

def test_datas_nao_consecutivas():
    dates = make_dates("2024-09-01", 122)
    biz_dates = [d for d in dates if d.weekday() < 5]
    biz_dates = [d for d in biz_dates if d <= HORIZON.end]

    locs, prods = ["841"], ["18064"]
    panel = _build_simple_panel(biz_dates, locs, prods, demand=3.0, balances_before=50.0)

    forecast = build_forecast(panel, horizon=HORIZON, mode="static")
    summary = build_summary_from_forecast(forecast)
    policy = build_policy(summary, z_value=1.65, review_days=7)

    sim = simulate_policy(panel, forecast=forecast, policy=policy, horizon=HORIZON, warmup_days=45)
    _assert_no_crash(sim)

    sim_dates = sorted(sim["date"].unique())
    print(f"\n  [datas_desalinhadas] input biz_days={len(biz_dates)}, sim_days={len(sim_dates)}")


# === SCENARIO 20: PROMOCOES CONSECUTIVAS ===================================

def test_promocoes_consecutivas():
    dates = make_dates("2024-07-01", 184)
    locs, prods = ["841"], ["18064"]
    panel = _build_simple_panel(dates, locs, prods, demand=8.0, balances_before=50.0)

    panel.loc[panel["date"] >= pd.Timestamp("2024-08-01"), "is_promo"] = 1
    panel.loc[panel["date"] >= pd.Timestamp("2024-08-01"), "campaign_type"] = "PAGUE E LEVE"

    uplift = compute_promo_uplift(panel, TRAIN_END)
    sku_uplift = uplift[(uplift["location"] == "841") & (uplift["product"] == "18064")]["promo_uplift"].values[0]

    print(f"\n  [promocoes] promo_uplift={sku_uplift:.4f} (expected ~1.0)")
    assert 0.9 <= sku_uplift <= 2.5, f"Uplift {sku_uplift} fora do range"


# === SCENARIO 21: ESTOQUE INICIAL NaN ======================================

def test_estoque_inicial_nan():
    dates = make_dates("2024-09-25", 100)
    locs, prods = ["841"], ["18064"]

    panel_rows = []
    for loc in locs:
        for prod in prods:
            for i, d in enumerate(dates):
                panel_rows.append({
                    "date": d, "location": loc, "product": prod,
                    "location_name": f"LOJA {loc}", "product_name": "PROD",
                    "supplier": "99999", "purchase_price": 10.0, "sales_price": 25.0,
                    "minimum_delivery_batch": 1, "cost_of_ordering": 5.0, "lead_time_days": 3,
                    "demand": 5.0, "sales_value": 125.0, "balance": np.nan,
                    "balance_value": np.nan, "actual_stockout_flag": 0,
                    "is_promo": 0, "campaign_type": "", "weekday": d.weekday(),
                    "corrected_demand": 5.0, "promo_uplift": 1.0,
                    "dow_baseline": 5.0, "sku_baseline": 5.0, "store_weekday_baseline": 5.0,
                })
    panel = pd.DataFrame(panel_rows).sort_values(["location", "product", "date"]).reset_index(drop=True)

    initial = get_initial_balances(panel, pd.Timestamp("2024-10-01"))
    init_val = initial.loc[
        (initial["location"] == "841") & (initial["product"] == "18064"), "initial_balance"
    ].values[0]

    print(f"\n  [estoque_inicial_nan] initial_balance={init_val} (NaN -> {init_val})")
    assert init_val == 0, f"NaN deveria virar 0, mas virou {init_val}"
    assert not pd.isna(init_val), "initial_balance ainda e NaN!"


# === SCENARIO 22: MULTIPLOS PEDIDOS SIMULTANEOS ============================

def test_multiplos_pedidos_simultaneos():
    dates = make_dates("2024-07-01", 184)
    locs, prods = ["841"], ["18064"]
    panel = _build_simple_panel(dates, locs, prods, demand=80.0, balances_before=200.0, lead_time=3)

    forecast = build_forecast(panel, horizon=HORIZON, mode="static")
    summary = build_summary_from_forecast(forecast)
    policy = build_policy(summary, z_value=2.33, review_days=3)

    sim = simulate_policy(panel, forecast=forecast, policy=policy, horizon=HORIZON, warmup_days=45)
    _assert_no_crash(sim)

    arrivals = sim[sim["received_qty"] > 0]
    max_received = arrivals["received_qty"].max() if len(arrivals) > 0 else 0
    print(f"\n  [multiplos_pedidos] max received in one day={max_received}")
    print(f"  [multiplos_pedidos] total orders={sim['order_qty'].sum()}")


# === SCENARIO 23: STOCKOUT FLAG C/ DEMANDA ZERO ============================
# BUG #02 direto: ending_inventory=0, demand=0

def test_stockout_flag_sem_demanda():
    dates = make_dates("2024-07-01", 184)
    locs, prods = ["841"], ["18064"]
    panel = _build_simple_panel(dates, locs, prods, demand=10.0, balances_before=20.0, lead_time=3)

    forecast = build_forecast(panel, horizon=HORIZON, mode="static")
    summary = build_summary_from_forecast(forecast)
    policy = build_policy(summary, z_value=0.0, review_days=14)

    sim = simulate_policy(panel, forecast=forecast, policy=policy, horizon=HORIZON, warmup_days=45)
    _assert_no_crash(sim)

    false_rupture = sim[
        (sim["ending_inventory"] <= 0) & (sim["actual_demand"] == 0)
        & (sim["simulated_stockout_flag"] == 1)
    ]
    print(f"\n  [stockout_flag] false rupture days: {len(false_rupture)} / {len(sim)}")
    if len(false_rupture) > 0:
        example = false_rupture[["date", "actual_demand", "ending_inventory", "simulated_stockout_flag"]].head(3)
        print(f"  BUG CONFIRMADO:\n{example.to_string()}")


# === RUNNER ================================================================

if __name__ == "__main__":
    tests = [
        ("demanda_explosiva", test_demanda_explosiva),
        ("demanda_zerada", test_demanda_zerada),
        ("order_up_to_abaixo_reorder_point", test_order_up_to_abaixo_reorder_point),
        ("estoque_inicial_negativo", test_estoque_inicial_negativo),
        ("sku_sem_historico", test_sku_sem_historico),
        ("lead_time_extremo", test_lead_time_extremo),
        ("z_invalido", test_z_invalido),
        ("round_up_to_batch", test_round_up_to_batch_edges),
        ("policy_vazia", test_simulator_policy_vazia),
        ("censura_100%", test_censura_cem_porcento),
        ("policy_objective_extremos", test_policy_objective_extremos),
        ("promo_sem_promo", test_promo_uplift_sem_promo),
        ("sem_snapshot", test_get_initial_balances_sem_snapshot),
        ("policy_S_maior_s", test_policy_garante_S_maior_s),
        ("ruptura_prolongada", test_ruptura_prolongada),
        ("warmup_insuficiente", test_warmup_insuficiente),
        ("lead_time_zero", test_lead_time_zero),
        ("demanda_fracionaria", test_demanda_fracionaria),
        ("datas_nao_consecutivas", test_datas_nao_consecutivas),
        ("promocoes_consecutivas", test_promocoes_consecutivas),
        ("estoque_inicial_nan", test_estoque_inicial_nan),
        ("multiplos_pedidos", test_multiplos_pedidos_simultaneos),
        ("stockout_flag_sem_demanda", test_stockout_flag_sem_demanda),
    ]

    passed = 0
    failed = 0
    errors = []

    for name, test_fn in tests:
        print(f"\n{'='*60}")
        print(f"CHAOS TEST: {name}")
        print(f"{'='*60}")
        try:
            test_fn()
            print(f"\n  RESULT: PASS: {name}")
            passed += 1
        except AssertionError as e:
            print(f"\n  RESULT: FAIL: {name}")
            print(f"     {e}")
            failed += 1
            errors.append((name, str(e)))
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"\n  RESULT: CRASH: {name}: {e}")
            failed += 1
            errors.append((name, f"CRASH: {e}"))

    print(f"\n{'='*60}")
    print(f"RESULTS: {passed} passed, {failed} failed, {len(tests)} total")
    if errors:
        print(f"\nFAILURES:")
        for name, msg in errors:
            short = msg[:160].replace("\n", " ")
            print(f"  - {name}: {short}")
    print(f"{'='*60}")

    if failed > 0:
        sys.exit(1)
