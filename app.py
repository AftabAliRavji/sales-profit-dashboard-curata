import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import requests

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
# Session State Helpers
# --------------------------
if "initialized_days" not in st.session_state:
    st.session_state.initialized_days = 0

def init_day_state(day_index):
    key_orders = f"orders_day_{day_index}"
    if key_orders not in st.session_state:
        st.session_state[key_orders] = 1  # start with 1 order per day

# --------------------------
# Inputs: Date Range & Days
# --------------------------
st.subheader("📅 Date Range Setup")

days = st.number_input("Number of Days", min_value=1, step=1)
start_date = st.date_input("Select Start Date")

# Ensure session state for each day
for i in range(int(days)):
    init_day_state(i)

order_values_daily = []
order_profits_daily = []
ad_spend_daily = []
dates_labels = []
dates_dt = []
profit_after_ads_daily = []
percent_profit_daily = []

st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)
st.subheader("📝 Daily Inputs")

# --------------------------
# Per-Day Orders (Collapsible) + Daily Totals
# --------------------------
for i in range(int(days)):
    current_date = start_date + timedelta(days=i)
    weekday = current_date.strftime("%A")
    date_label = f"{weekday} — {current_date.strftime('%d %b %Y')}"

    key_orders = f"orders_day_{i}"
    num_orders = st.session_state[key_orders]

    with st.expander(f"Orders for {date_label}", expanded=False):
        st.write(f"Enter each order's sales and profit for {date_label}:")
        day_sales = 0.0
        day_profit = 0.0

        for j in range(num_orders):
            col1, col2 = st.columns(2)
            with col1:
                sales = st.number_input(
                    f"Order {j+1} Sales ($) — {date_label}",
                    min_value=0.0,
                    step=0.01,
                    key=f"day_{i}_order_{j}_sales"
                )
            with col2:
                profit = st.number_input(
                    f"Order {j+1} Profit ($) — {date_label}",
                    min_value=0.0,
                    step=0.01,
                    key=f"day_{i}_order_{j}_profit"
                )
            day_sales += sales
            day_profit += profit

        add_order = st.button(
            f"➕ Add Order for {date_label}",
            key=f"add_order_day_{i}"
        )
        if add_order:
            st.session_state[key_orders] += 1

    # Daily ad spend (default 64)
    ad_spend = st.number_input(
        f"Ad Spend ($) for {date_label}",
        min_value=0.0,
        step=0.01,
        value=64.00,
        key=f"ad_spend_day_{i}"
    )

    # Profit after ads
    profit_after_ads = day_profit - ad_spend

    # Percentage profit (profit / sales * 100)
    if day_sales > 0:
        percent_profit = (day_profit / day_sales) * 100
    else:
        percent_profit = 0.0

    # Show daily summary
    st.markdown(f"### 📌 Daily Summary — {date_label}")
    col_a, col_b = st.columns(2)
    col_a.metric("Daily Total Sales", f"${day_sales:,.2f}")
    col_b.metric("Daily Total Profit", f"${day_profit:,.2f}")

    col_c, col_d = st.columns(2)
    col_c.metric("Daily Ad Spend", f"${ad_spend:,.2f}")
    col_d.metric("Daily Profit After Ads", f"${profit_after_ads:,.2f}")

    st.metric("Daily Percentage Profit", f"{percent_profit:.2f}%")

    # Collect for overall analysis
    order_values_daily.append(day_sales)
    order_profits_daily.append(day_profit)
    ad_spend_daily.append(ad_spend)
    dates_labels.append(date_label)
    dates_dt.append(current_date)
    profit_after_ads_daily.append(profit_after_ads)
    percent_profit_daily.append(percent_profit)

# Daily DataFrame (core dataset)
df = pd.DataFrame({
    "Date": dates_labels,
    "Date_dt": dates_dt,
    "Sales ($)": order_values_daily,
    "Profit ($)": order_profits_daily,
    "Ad Spend ($)": ad_spend_daily,
    "Profit After Ads ($)": profit_after_ads_daily,
    "Profit %": percent_profit_daily
})

# --------------------------
# KPI Section (Overall)
# --------------------------
st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)
st.subheader("📌 Overall Key Metrics")

total_sales = df["Sales ($)"].sum()
total_profit = df["Profit ($)"].sum()
total_ad_spend = df["Ad Spend ($)"].sum()
total_profit_after_ads = df["Profit After Ads ($)"].sum()

col1, col2 = st.columns(2)
col1.metric("Total Sales", f"${total_sales:,.2f}")
col2.metric("Total Profit", f"${total_profit:,.2f}")

col3, col4 = st.columns(2)
col3.metric("Total Ad Spend", f"${total_ad_spend:,.2f}")
col4.metric("Total Profit After Ads", f"${total_profit_after_ads:,.2f}")

overall_profit_percentage = (total_profit / total_sales * 100) if total_sales > 0 else 0
st.metric("Overall Profit %", f"{overall_profit_percentage:.2f}%")

# --------------------------
# ROAS (Return on Ad Spend)
# --------------------------
st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)
st.subheader("📈 ROAS (Return on Ad Spend)")

if total_ad_spend > 0:
    roas = total_sales / total_ad_spend
else:
    roas = 0.0

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

converted_profit_total = total_profit_after_ads * live_rate
st.metric("Total Profit After Ads (Converted to £)", f"£{converted_profit_total:,.2f}")

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
st.dataframe(
    df[["Date", "Sales ($)", "Profit ($)", "Ad Spend ($)", "Profit After Ads ($)", "Profit %"]]
    .style.format({
        "Sales ($)": "${:,.2f}",
        "Profit ($)": "${:,.2f}",
        "Ad Spend ($)": "${:,.2f}",
        "Profit After Ads ($)": "${:,.2f}",
        "Profit %": "{:.2f}%"
    })
)

# --------------------------
# Weekly, Monthly, Yearly Summaries
# --------------------------
st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)
st.subheader("📅 Weekly Summary")

df_summary = df.copy()
df_summary["Week"] = df_summary["Date_dt"].dt.isocalendar().week
df_summary["Month"] = df_summary["Date_dt"].dt.month
df_summary["Year"] = df_summary["Date_dt"].dt.year

# Weekly
weekly = df_summary.groupby("Week").agg({
    "Sales ($)": "sum",
    "Profit ($)": "sum",
    "Ad Spend ($)": "sum",
    "Profit After Ads ($)": "sum"
}).reset_index()

weekly["Profit %"] = (weekly["Profit ($)"] / weekly["Sales ($)"] * 100).fillna(0)
weekly["Profit (£)"] = weekly["Profit After Ads ($)"] * live_rate

st.dataframe(weekly.style.format({
    "Sales ($)": "${:,.2f}",
    "Profit ($)": "${:,.2f}",
    "Ad Spend ($)": "${:,.2f}",
    "Profit After Ads ($)": "${:,.2f}",
    "Profit (£)": "£{:,.2f}",
    "Profit %": "{:.2f}%"
}))

# Monthly
st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)
st.subheader("🗓 Monthly Summary")

monthly = df_summary.groupby("Month").agg({
    "Sales ($)": "sum",
    "Profit ($)": "sum",
    "Ad Spend ($)": "sum",
    "Profit After Ads ($)": "sum"
}).reset_index()

monthly["Profit %"] = (monthly["Profit ($)"] / monthly["Sales ($)"] * 100).fillna(0)
monthly["Profit (£)"] = monthly["Profit After Ads ($)"] * live_rate

st.dataframe(monthly.style.format({
    "Sales ($)": "${:,.2f}",
    "Profit ($)": "${:,.2f}",
    "Ad Spend ($)": "${:,.2f}",
    "Profit After Ads ($)": "${:,.2f}",
    "Profit (£)": "£{:,.2f}",
    "Profit %": "{:.2f}%"
}))

# Yearly
st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)
st.subheader("📆 Yearly Summary")

yearly = df_summary.groupby("Year").agg({
    "Sales ($)": "sum",
    "Profit ($)": "sum",
    "Ad Spend ($)": "sum",
    "Profit After Ads ($)": "sum"
}).reset_index()

yearly["Profit %"] = (yearly["Profit ($)"] / yearly["Sales ($)"] * 100).fillna(0)
yearly["Profit (£)"] = yearly["Profit After Ads ($)"] * live_rate

st.dataframe(yearly.style.format({
    "Sales ($)": "${:,.2f}",
    "Profit ($)": "${:,.2f}",
    "Ad Spend ($)": "${:,.2f}",
    "Profit After Ads ($)": "${:,.2f}",
    "Profit (£)": "£{:,.2f}",
    "Profit %": "{:.2f}%"
}))

# --------------------------
# CSV Export
# --------------------------
st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)
st.subheader("📤 Export Data")

csv = df[[
    "Date", "Sales ($)", "Profit ($)", "Ad Spend ($)", "Profit After Ads ($)", "Profit %"
]].to_csv(index=False).encode("utf-8")

st.download_button(
    label="Download Daily Data as CSV",
    data=csv,
    file_name="curata_daily_data.csv",
    mime="text/csv"
)
