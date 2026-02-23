# src/client_input.py
import csv

def load_client_data(csv_path: str) -> dict:
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        row = next(reader)  # берём первую заявку

    return {
        "city": row["city"],
        "annual_kwh": float(row["annual_kwh"]),
        "pv_kwp": float(row["pv_kwp"]),
        "battery_kwh": float(row["battery_kwh"]),
        "profile": row["profile"],
    }
