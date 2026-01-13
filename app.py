import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import requests
import base64

# --------------------------
# Curata.shop Branding Styles
# --------------------------
st.markdown("""
    <style>
        .main { background-color: #ffffff; }
        .curata-header {
            text-align: center;
            padding: 20px 0;
            border-bottom: 2px solid #f2f2f2;
        }
        .curata-title {
            font-size: 32px;
            font-weight: 700;
            color: #000000;
        }
        .curata-tagline {
            font-size: 16px;
            color: #777777;
            margin-top: -5px;
        }
        h2, h3 { color: #000000 !important; }
        .stMetric {
            background-color: #fafafa;
            border-radius: 10px;
            padding: 10px;
        }
        .curata-divider {
            margin: 25px 0;
            border-top: 1px solid #e6e6e6;
        }
    </style>
""", unsafe_allow_html=True)

# --------------------------
# Header
# --------------------------
st.markdown("""
    <div class="curata-header">
        <div class="curata-title">Curata.shop Dashboard</div>
        <div class="curata-tagline">Daily Sales • Profit • Performance</div>
    </div>
""", unsafe_allow_html=True)

st.write("")

# --------------------------
# App Logic
# --------------------------

st.subheader("📅 Date Range Setup")

days = st.number_input("Number of Days", min_value=1, step=1)
start_date = st.date_input("Select Start Date")

order_values = []
order_profits = []
dates = []

st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)

st.subheader("📝 Daily Inputs")

for i in range(days):
    current_date = start_date + timedelta(days=i)
    weekday = current_date.strftime("%A")
    date_label = f"{weekday} — {current_date.strftime('%d %b %Y')}"

    with st.container():
        st.markdown(f"### {date_label}")
        order_value = st.number_input(
            f"Order Value ($) — {date_label}",
            min_value=0.0,
            step=0.01,
            key=f"value_{i}"
        )
        order_profit = st.number_input(
            f"Profit ($) — {date_label}",
            min_value=0.0,
            step=0.01,
            key=f"profit_{i}"
        )

        order_values.append(order_value)
        order_profits.append(order_profit)
        dates.append(date_label)

df = pd.DataFrame({
    "Date": dates,
    "Sales ($)": order_values,
    "Profit ($)": order_profits
})

# --------------------------
# KPI Section
# --------------------------

st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)
st.subheader("📌 Key Metrics")

total_sales = df["Sales ($)"].sum()
total_profit = df["Profit ($)"].sum()

col1, col2 = st.columns(2)
col1.metric("Total Sales", f"${total_sales:,.2f}")
col2.metric("Total Profit", f"${total_profit:,.2f}")

ad_spend = st.number_input("Ad Spend ($)", min_value=0.0, step=0.01)
profit_after_ads = total_profit - ad_spend

st.metric("Profit After Ad Spend", f"${profit_after_ads:,.2f}")

profit_percentage = (total_profit / total_sales * 100) if total_sales > 0 else 0
st.metric("Profit %", f"{profit_percentage:.2f}%")

# --------------------------
# ROAS (Return on Ad Spend)
# --------------------------

st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)
st.subheader("📈 ROAS (Return on Ad Spend)")

if ad_spend > 0:
    roas = total_sales / ad_spend
else:
    roas = 0

st.metric("ROAS", f"{roas:.2f}x")

# --------------------------
# USD → GBP Live Conversion
# --------------------------

st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)
st.subheader("💱 Live Currency Conversion (USD → GBP)")

def get_live_rate():
    try:
        response = requests.get("https://api.exchangerate.host/latest?base=USD&symbols=GBP")
        data = response.json()
        return data["rates"]["GBP"]
    except:
        return None

live_rate = get_live_rate()

if live_rate:
    st.success(f"Live USD → GBP Rate: {live_rate:.4f}")
else:
    st.error("Unable to fetch live rate. Using fallback rate 0.79.")
    live_rate = 0.79

converted_profit = profit_after_ads * live_rate

st.metric("Profit After Ads (Converted to £)", f"£{converted_profit:,.2f}")

# --------------------------
# Dashboard Section
# --------------------------

st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)
st.subheader("📊 Dashboard")

st.markdown("### 📈 Sales Trend")
st.line_chart(df.set_index("Date")["Sales ($)"])

st.markdown("### 💰 Profit Trend")
st.line_chart(df.set_index("Date")["Profit ($)"])

st.markdown("### 📋 Daily Breakdown")
st.dataframe(df.style.format({"Sales ($)": "${:.2f}", "Profit ($)": "${:.2f}"}))

# --------------------------
# Weekly, Monthly, Yearly Summaries
# --------------------------

st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)
st.subheader("📅 Weekly Summary")

df_summary = df.copy()
df_summary["Date_dt"] = pd.to_datetime(df_summary["Date"].str.extract(r'— (.*)')[0])
df_summary["Week"] = df_summary["Date_dt"].dt.isocalendar().week
df_summary["Month"] = df_summary["Date_dt"].dt.month
df_summary["Year"] = df_summary["Date_dt"].dt.year

weekly = df_summary.groupby("Week").agg({
    "Sales ($)": "sum",
    "Profit ($)": "sum"
}).reset_index()

weekly["Profit After Ads ($)"] = weekly["Profit ($)"] - (ad_spend / days * weekly["Profit ($)"] / total_profit if total_profit > 0 else 0)
weekly["Profit %"] = (weekly["Profit ($)"] / weekly["Sales ($)"] * 100).fillna(0)
weekly["Profit (£)"] = weekly["Profit After Ads ($)"] * live_rate

st.dataframe(weekly.style.format({
    "Sales ($)": "${:,.2f}",
    "Profit ($)": "${:,.2f}",
    "Profit After Ads ($)": "${:,.2f}",
    "Profit (£)": "£{:,.2f}",
    "Profit %": "{:.2f}%"
}))

# --------------------------
# Monthly Summary
# --------------------------

st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)
st.subheader("🗓 Monthly Summary")

monthly = df_summary.groupby("Month").agg({
    "Sales ($)": "sum",
    "Profit ($)": "sum"
}).reset_index()

monthly["Profit After Ads ($)"] = monthly["Profit ($)"] - (ad_spend / days * monthly["Profit ($)"] / total_profit if total_profit > 0 else 0)
monthly["Profit %"] = (monthly["Profit ($)"] / monthly["Sales ($)"] * 100).fillna(0)
monthly["Profit (£)"] = monthly["Profit After Ads ($)"] * live_rate

st.dataframe(monthly.style.format({
    "Sales ($)": "${:,.2f}",
    "Profit ($)": "${:,.2f}",
    "Profit After Ads ($)": "${:,.2f}",
    "Profit (£)": "£{:,.2f}",
    "Profit %": "{:.2f}%"
}))

# --------------------------
# Yearly Summary
# --------------------------

st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)
st.subheader("📆 Yearly Summary")

yearly = df_summary.groupby("Year").agg({
    "Sales ($)": "sum",
    "Profit ($)": "sum"
}).reset_index()

yearly["Profit After Ads ($)"] = yearly["Profit ($)"] - (ad_spend / days * yearly["Profit ($)"] / total_profit if total_profit > 0 else 0)
yearly["Profit %"] = (yearly["Profit ($)"] / yearly["Sales ($)"] * 100).fillna(0)
yearly["Profit (£)"] = yearly["Profit After Ads ($)"] * live_rate

st.dataframe(yearly.style.format({
    "Sales ($)": "${:,.2f}",
    "Profit ($)": "${:,.2f}",
    "Profit After Ads ($)": "${:,.2f}",
    "Profit (£)": "£{:,.2f}",
    "Profit %": "{:.2f}%"
}))

# --------------------------
# CSV Export
# --------------------------

st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)
st.subheader("📤 Export Data")

csv = df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="Download Daily Data as CSV",
    data=csv,
    file_name="curata_daily_data.csv",
    mime="text/csv"
)
