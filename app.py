# app.py
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

from src.analytics import compute_waiting_cost
from src.report import generate_pdf_report

CSV_PATH = "data/output.csv"
EFFICIENCY = 0.9
PV_KWH_PER_KWP_DAY = 3.0 

PV_PROFILE = pd.Series(
    [0, 0, 0, 0, 0, 0.02, 0.05, 0.10, 0.15, 0.20,
     0.25, 0.30, 0.32, 0.30, 0.25, 0.20, 0.15, 0.10, 0.05, 0.02,
     0, 0, 0, 0], index=range(24)
)

st.set_page_config(page_title="Kalkulator ROI BESS (PL)", layout="wide")
st.title("⚡ Kalkulator Opłacalności BESS + PV (Polska)")
st.markdown("Narzędzie B2B: analiza ekonomiczna magazynowania energii na podstawie cen Rynku Dnia Następnego (TGE/ENTSO-E).")

# ---------- LOAD DATA ----------
@st.cache_data
def load_data():
    df = pd.read_csv(CSV_PATH)
    if "hour" in df.columns and df["hour"].max() > 23:
        df["hour"] = df["hour"] - 1
    df = df[df["hour"].between(0, 23)]
    return df

try:
    df = load_data()
    available_dates = sorted(df["date"].unique())
except FileNotFoundError:
    st.error("Błąd: Plik data/output.csv nie został znaleziony.")
    st.stop()

# ---------- SIDEBAR: PARAMETRY KLIENTA ----------
st.sidebar.header("Parametry Klienta")
selected_date = st.sidebar.selectbox("Data notowań rynkowych", available_dates, index=len(available_dates)-1)
distribution_cost = st.sidebar.number_input("Koszt dystrybucji (PLN/kWh)", value=0.45, step=0.05)

st.sidebar.subheader("Dane techniczne")
annual_kwh = st.sidebar.number_input("Roczne zużycie (kWh)", value=4200, step=500)
pv_kwp = st.sidebar.number_input("Moc instalacji PV (kWp)", value=6.0, step=1.0)
battery_kwh = st.sidebar.number_input("Pojemność magazynu (kWh)", value=10.0, step=1.0)

# ---------- LOGIKA OBLICZEŃ ----------
day_df = df[df["date"] == selected_date].set_index("hour").sort_index()

hourly_consumption = annual_kwh / 365 / 24
consumption_series = pd.Series([hourly_consumption]*24, index=day_df.index)

pv_generation = PV_PROFILE * pv_kwp * PV_KWH_PER_KWP_DAY
pv_generation = pv_generation.loc[day_df.index]

self_consumed = consumption_series.clip(upper=pv_generation)
remaining_consumption = consumption_series - self_consumed 
pv_excess = pv_generation - self_consumed 

battery_charge_from_pv = min(pv_excess.sum() * EFFICIENCY, battery_kwh)

if remaining_consumption.sum() > 0 and battery_charge_from_pv > 0:
    battery_used = (remaining_consumption / remaining_consumption.sum()) * battery_charge_from_pv
    grid_consumption_with_battery = (remaining_consumption - battery_used).clip(lower=0)
else:
    grid_consumption_with_battery = remaining_consumption

# ---------- KALKULACJA FINANSOWA ----------
price_kwh = (day_df["price_pln_mwh"] / 1000) + distribution_cost

cost_no_battery = (remaining_consumption * price_kwh).sum()
cost_with_battery = (grid_consumption_with_battery * price_kwh).sum()

profit_daily = cost_no_battery - cost_with_battery
waiting_cost = compute_waiting_cost(profit_daily, 6)

# ---------- WYNIKI (DASHBOARD METRICS) ----------
st.subheader("Wyniki finansowe (Dla wybranego dnia)")
col1, col2, col3 = st.columns(3)
col1.metric("Koszty z sieci (Tylko PV)", f"{cost_no_battery:.2f} PLN")
col2.metric("Koszty z sieci (PV + BESS)", f"{cost_with_battery:.2f} PLN")
col3.metric("Oszczędność dzięki BESS", f"{profit_daily:.2f} PLN", delta=f"+{profit_daily:.2f}")

st.markdown("---")
if waiting_cost > 0:
    st.error(f"### 🛑 Koszt zwłoki (Cost of Waiting): {waiting_cost:.2f} PLN")
    st.markdown("*Kwota, którą klient traci w ciągu 6 miesięcy, odkładając instalację magazynu energii.*")
else:
    st.success("W tym dniu instalacja magazynu nie generuje istotnych oszczędności ze względu na brak nadwyżek PV.")

# ---------- WYKRESY ----------
st.subheader("Bilans energetyczny obiektu")
fig, ax = plt.subplots(figsize=(10, 4))
ax.plot(day_df.index, consumption_series, label="Zużycie domu", color="red", linestyle="--")
ax.plot(day_df.index, pv_generation, label="Produkcja PV", color="orange")
ax.fill_between(day_df.index, 0, pv_generation, color="orange", alpha=0.2)
ax.set_xlabel("Godzina (0-23)")
ax.set_ylabel("Energia (kWh)")
ax.legend()
ax.grid(True, linestyle=":", alpha=0.6)
st.pyplot(fig)

# ---------- PDF ----------
st.markdown("---")
if st.button("Generuj Ofertę PDF"):
    client_data = {
        "city": "Polska (Analiza lokalna)", 
        "annual_kwh": annual_kwh, 
        "battery_kwh": battery_kwh, 
        "profile": "Profil mieszany", 
        "pv_kwp": pv_kwp
    }
    output_pdf = "data/oferta_bess.pdf"
    generate_pdf_report(output_path=output_pdf, client=client_data, date=selected_date, 
                       cost_no_battery=cost_no_battery, cost_with_battery=cost_with_battery, 
                       profit_daily=profit_daily, prices_df=day_df, waiting_cost=waiting_cost)
    
    with open(output_pdf, "rb") as f:
        st.download_button("📥 Pobierz Ofertę PDF", f, "Oferta_BESS.pdf", "application/pdf")