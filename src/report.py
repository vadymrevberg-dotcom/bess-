from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
import matplotlib.pyplot as plt
import os


def generate_pdf_report(
    output_path: str,
    client: dict,
    date: str,
    cost_no_battery: float,
    cost_with_battery: float,
    profit_daily: float,
    prices_df,
    waiting_cost: float = 0.0,
):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # ---------- PRICE CHART ----------
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.plot(prices_df.index, prices_df["price_pln_mwh"])
    ax.set_xlabel("Hour")
    ax.set_ylabel("PLN / MWh")
    ax.set_title("Day-Ahead Electricity Prices")
    ax.grid(True)

    chart_path = "data/tmp_price_chart.png"
    plt.tight_layout()
    plt.savefig(chart_path)
    plt.close()

    # ---------- PDF ----------
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4

    # Title
    c.setFont("Helvetica-Bold", 18)
    c.drawString(2 * cm, height - 2 * cm, "Energy Storage Business Case")

    # Client info
    c.setFont("Helvetica", 11)
    c.drawString(2 * cm, height - 3.6 * cm, f"Location: {client['city']}")
    c.drawString(2 * cm, height - 4.3 * cm, f"Annual electricity consumption: {client['annual_kwh']} kWh")
    c.drawString(2 * cm, height - 5.0 * cm, f"Battery capacity considered: {client['battery_kwh']} kWh")
    c.drawString(2 * cm, height - 5.7 * cm, f"Consumption profile: {client['profile']}")
    c.drawString(2 * cm, height - 6.4 * cm, f"Market reference date: {date}")

    # ---------- KEY MESSAGE ----------
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, height - 8.0 * cm, "Cost of Waiting")

    c.setFont("Helvetica-Bold", 22)
    c.drawString(
        2 * cm,
        height - 9.4 * cm,
        f"{abs(waiting_cost):,.0f} PLN / 6 months"
    )

    c.setFont("Helvetica", 11)
    c.drawString(
        2 * cm,
        height - 10.3 * cm,
        "Estimated financial loss caused by postponing battery installation"
    )

    # ---------- INTERPRETATION ----------
    c.setFont("Helvetica-Bold", 14)
    c.drawString(2 * cm, height - 11.6 * cm, "What does this mean?")

    c.setFont("Helvetica", 11)
    text = c.beginText(2 * cm, height - 12.4 * cm)
    text.textLine(
        "Without an energy storage system, surplus solar energy is sold to the grid at low prices,"
    )
    text.textLine(
        "while electricity is repurchased later at higher tariffs during evening peak hours."
    )
    text.textLine(
        "This price difference creates a recurring financial loss referred to as the 'cost of waiting'."
    )
    c.drawText(text)

    # ---------- COMPARISON ----------
    c.setFont("Helvetica-Bold", 14)
    c.drawString(2 * cm, height - 14.6 * cm, "Scenario Comparison (Daily Net Grid Balance)")

    c.setFont("Helvetica", 11)
    c.drawString(
        2 * cm,
        height - 15.8 * cm,
        f"Without battery (PV only): {abs(cost_no_battery):.2f} PLN"
    )
    c.drawString(
        2 * cm,
        height - 16.6 * cm,
        f"With battery (PV + storage): {abs(cost_with_battery):.2f} PLN"
    )

    # ---------- ASSUMPTIONS ----------
    c.setFont("Helvetica-Bold", 14)
    c.drawString(2 * cm, 7.5 * cm, "Model Assumptions")

    c.setFont("Helvetica", 9)
    assumptions = [
        "• Analysis based on real day-ahead electricity market prices.",
        "• Distribution and grid fees are included in electricity costs.",
        "• PV generation and self-consumption are modeled using simplified annual averages.",
        "• Battery operation is simplified and intended for decision-support purposes.",
        "• Results represent avoided losses, not guaranteed investment returns.",
    ]

    text = c.beginText(2 * cm, 6.8 * cm)
    for a in assumptions:
        text.textLine(a)
    c.drawText(text)

    # Chart
    c.drawImage(chart_path, 2 * cm, 8.8 * cm, width=17 * cm, height=5.5 * cm)

    c.showPage()
    c.save()

    os.remove(chart_path)


