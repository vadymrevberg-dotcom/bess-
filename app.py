# app.py
import os
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

# Импорт основных расчетных модулей
from src.analytics import simulate_without_battery_30d, simulate_with_battery_30d, compute_waiting_cost
from src.report import generate_pdf_report
from src.load_profile import load_consumption_profile

CSV_PATH = "data/output.csv"
EFFICIENCY = 0.9
PV_KWH_PER_KWP_DAY = 3.0

PV_PROFILE = pd.Series(
    [0, 0, 0, 0, 0, 0.02, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.32, 0.30, 0.25, 0.20, 0.15, 0.10, 0.05, 0.02, 0, 0, 0, 0],
    index=range(24)
)

st.set_page_config(page_title="Generator Audytów BESS (PL)", layout="wide")
st.title("⚡ System Analityczny TGE: Audyty BESS + PV")
st.markdown("Narzędzie dla Instalatorów OZE. Generuj twarde dowody finansowe dla klientów i zamykaj sprzedaż szybciej.")

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
    # Берем последние 30 дней для достоверной аналитики
    last_30_dates = available_dates[-30:] if len(available_dates) >= 30 else available_dates
    df_30d = df[df["date"].isin(last_30_dates)]
    target_date = last_30_dates[-1]
    day_prices = df[df["date"] == target_date].set_index("hour").sort_index()
except FileNotFoundError:
    st.error("Błąd: Brak pliku data/output.csv. System wymaga inicjalizacji danych rynkowych.")
    st.stop()

# ---------- SIDEBAR: PARAMETRY KLIENTA ----------
st.sidebar.header("Parametry Klienta")
city = st.sidebar.text_input("Miasto (do raportu)", value="Warszawa")
profile_name = st.sidebar.selectbox("Profil zużycia", ["G11", "G12", "Office"])
distribution_cost = st.sidebar.number_input("Koszt dystrybucji (PLN/kWh)", value=0.45, step=0.05)

st.sidebar.subheader("Dane techniczne")
annual_kwh = st.sidebar.number_input("Roczne zużycie (kWh)", value=5000, step=500)
pv_kwp = st.sidebar.number_input("Moc instalacji PV (kWp)", value=6.0, step=0.5)
battery_kwh = st.sidebar.number_input("Pojemność magazynu (kWh)", value=10.0, step=1.0)

# ---------- LOGIKA OBLICZEŃ ----------
try:
    consumption = load_consumption_profile(profile_name=profile_name, annual_kwh=annual_kwh).loc[day_prices.index]
except ValueError as e:
    st.error(f"Błąd profilu: {e}")
    st.stop()

pv_generation = PV_PROFILE * pv_kwp * PV_KWH_PER_KWP_DAY
pv_generation = pv_generation.loc[day_prices.index]

self_consumed = consumption.clip(upper=pv_generation)
remaining_consumption = consumption - self_consumed
pv_excess = pv_generation - self_consumed

battery_charge_from_pv = min(pv_excess.sum(), battery_kwh)

if remaining_consumption.sum() > 0 and battery_charge_from_pv > 0:
    battery_used = (remaining_consumption / remaining_consumption.sum()) * battery_charge_from_pv
    grid_consumption = remaining_consumption - battery_used
else:
    grid_consumption = remaining_consumption

num_days = len(last_30_dates)

# Symulacja finansowa na bazie ostatnich 30 dni RCE
cost_no_battery_period = simulate_without_battery_30d(df_30d, remaining_consumption, distribution_cost)
cost_pv_battery_period = simulate_without_battery_30d(df_30d, grid_consumption, distribution_cost)

available_for_arbitrage = max(0, battery_kwh - battery_charge_from_pv)
arbitrage_profit_period = simulate_with_battery_30d(df_30d, grid_consumption, available_for_arbitrage, EFFICIENCY, distribution_cost)

cost_with_battery_period = cost_pv_battery_period - arbitrage_profit_period
profit_battery_period = cost_no_battery_period - cost_with_battery_period

cost_no_battery_daily = cost_no_battery_period / num_days
cost_with_battery_daily = cost_with_battery_period / num_days
profit_battery_daily = profit_battery_period / num_days
waiting_cost = compute_waiting_cost(profit_battery_daily, 6)

# ---------- WYNIKI (DASHBOARD) ----------
st.subheader(f"Średnie wyniki operacyjne (baza: ostatnie {num_days} dni)")
col1, col2, col3 = st.columns(3)
col1.metric("Dzienny koszt (Tylko PV)", f"{cost_no_battery_daily:.2f} PLN")
col2.metric("Dzienny koszt (PV + BESS)", f"{cost_with_battery_daily:.2f} PLN")
col3.metric("Dzienny zysk z BESS", f"{profit_battery_daily:.2f} PLN", delta=f"+{profit_battery_daily:.2f}")

if waiting_cost > 0:
    st.error(f"### 🛑 Koszt zwłoki (Cost of Waiting / 6 m-cy): {waiting_cost:.2f} PLN")

# ---------- LEAD GEN I GENERACJA PDF ----------
st.markdown("---")
st.subheader("Generowanie Raportu PDF dla Klienta")
st.markdown("Wprowadź dane autoryzacyjne instalatora, aby wygenerować audyt do druku.")

col_a, col_b = st.columns(2)
installer_email = col_a.text_input("Twój Email B2B")
installer_company = col_b.text_input("Nazwa Twojej Firmy")

if installer_email and installer_company:
    if st.button("Generuj Audyt BESS (PDF)"):
        client_data = {
            "city": city,
            "annual_kwh": annual_kwh,
            "battery_kwh": battery_kwh,
            "profile": profile_name,
            "pv_kwp": pv_kwp
        }
        
        # Передача правильного формата данных в report.py
        chart_data = {
            "hours": list(range(24)),
            "pv_kw": pv_generation.tolist(),
            "cons_kw": consumption.tolist(),
            "prices": day_prices["price_pln_mwh"].tolist(),
            "cheap_hours": day_prices["price_pln_mwh"].nsmallest(3).index.tolist(),
            "expensive_hours": day_prices["price_pln_mwh"].nlargest(3).index.tolist()
        }

        output_pdf = "data/oferta_bess.pdf"
        generate_pdf_report(
            output_path=output_pdf,
            client=client_data,
            date=target_date,
            cost_no_battery=cost_no_battery_daily,
            cost_with_battery=cost_with_battery_daily,
            profit_daily=profit_battery_daily,
            waiting_cost=waiting_cost,
            chart_data=chart_data
        )
        
        with open(output_pdf, "rb") as f:
            st.download_button("📥 Pobierz Wygenerowany Audyt PDF", f, file_name=f"Audyt_BESS_{city}.pdf", mime="application/pdf")
        
        # Сбор базы лидов
        with open("data/leads.csv", "a", encoding="utf-8") as f:
            f.write(f"{installer_email},{installer_company},{city},{battery_kwh}\n")
        
        st.success("Raport gotowy do wysyłki do klienta.")
else:
    st.info("Wymagana autoryzacja (Email i Firma), aby odblokować generowanie PDF.")