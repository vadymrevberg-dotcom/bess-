"""
Main entry point for Energy Arbitrage MVP.

Includes:
- manual clients (home / business)
- market data
- PV generation + self-consumption
- battery charged from PV excess
- PDF report per client
"""

from client_manual import CLIENT_HOME, CLIENT_BUSINESS
from load_profile import load_consumption_profile
from report import generate_pdf_report
from analytics import (
    simulate_without_battery,
    simulate_with_battery,
    compute_waiting_cost,
)

import pandas as pd


DATA_CSV = "data/output.csv"
EFFICIENCY = 0.9
SOLAR_MULTIPLIER = 2.5

# Simplified normalized PV profile (sum ≈ 1)
PV_PROFILE = pd.Series(
    [
        0, 0, 0, 0, 0,
        0.02, 0.05, 0.10, 0.15, 0.20,
        0.25, 0.30, 0.32, 0.30, 0.25,
        0.20, 0.15, 0.10, 0.05, 0.02,
        0, 0, 0, 0
    ],
    index=range(24)
)

PV_KWH_PER_KWP_DAY = 3.0  # Poland average


def main():
    clients = [
        ("home", CLIENT_HOME),
        ("business", CLIENT_BUSINESS),
    ]

    df = pd.read_csv(DATA_CSV)

    df["hour"] = df["hour"] - 1
    df = df[df["hour"].between(0, 23)]

    target_date = sorted(df["date"].unique())[-1]

    day_prices = (
        df[df["date"] == target_date]
        .set_index("hour")
        .sort_index()
    )

    if len(day_prices) != 24:
        raise ValueError(f"Incomplete day: {target_date}")

    print(f"▶ Using market date: {target_date}\n")

    for label, client in clients:
        print("▶ Client:")
        print(client)

        annual_kwh = client["annual_kwh"]
        battery_kwh = client["battery_kwh"]
        profile = client["profile"]
        pv_kwp = client.get("pv_kwp", 0)

        consumption = load_consumption_profile(
            profile_name=profile,
            annual_kwh=annual_kwh,
        ).loc[day_prices.index]

        if consumption.isna().any():
            raise ValueError("NaN in consumption profile")

        # ---- PV generation ----
        pv_generation = PV_PROFILE * pv_kwp * PV_KWH_PER_KWP_DAY
        pv_generation = pv_generation.loc[day_prices.index]

        # ---- Self-consumption ----
        self_consumed = consumption.clip(upper=pv_generation)
        remaining_consumption = consumption - self_consumed
        pv_excess = pv_generation - self_consumed

        # ---- Battery charged from PV excess ----
        battery_charge_from_pv = min(pv_excess.sum(), battery_kwh)

        if remaining_consumption.sum() > 0 and battery_charge_from_pv > 0:
            battery_used = (
                remaining_consumption / remaining_consumption.sum()
            ) * battery_charge_from_pv
            grid_consumption = remaining_consumption - battery_used
        else:
            grid_consumption = remaining_consumption

        # ---- Cost without battery (PV only) ----
        cost_no_battery = simulate_without_battery(
            prices_df=day_prices,
            consumption_series=grid_consumption,
        )

        # ---- Battery effect (avoided grid purchase) ----
        profit_battery = simulate_with_battery(
            prices_df=day_prices,
            consumption_series=grid_consumption,
            battery_kwh=battery_kwh,
            efficiency=EFFICIENCY,
        )

        profit_battery *= SOLAR_MULTIPLIER

        cost_with_battery = cost_no_battery - profit_battery
        waiting_cost = compute_waiting_cost(profit_battery, 6)

        output_path = f"data/report_{label}.pdf"

        generate_pdf_report(
            output_path=output_path,
            client=client,
            date=target_date,
            cost_no_battery=cost_no_battery,
            cost_with_battery=cost_with_battery,
            profit_daily=profit_battery,
            waiting_cost=waiting_cost,
            prices_df=day_prices,
        )

        print(f"📄 PDF generated: {output_path}")
        print("=== RESULTS ===")
        print(f"Daily cost WITHOUT battery: {cost_no_battery:.2f} PLN")
        print(f"Daily cost WITH battery:    {cost_with_battery:.2f} PLN")
        print(f"Daily avoided cost:         {profit_battery:.2f} PLN")
        print(f"Waiting cost (6 months):    {waiting_cost:.2f} PLN\n")


if __name__ == "__main__":
    main()
