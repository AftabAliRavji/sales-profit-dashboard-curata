import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import requests

st.set_page_config(page_title="Curata.shop Dashboard", page_icon="📊", layout="centered")

st.markdown("""
    <style>
        .main { background-color: #050505; color: #f5f5f5; }
        .block-container { padding-top: 1rem; padding-bottom: 2rem; }
        .curata-header {
            text-align: center;
            padding: 10px 0 18px 0;
            border-bottom: 1px solid #333333;
        }
        .curata-title {
            font-size: 26px;
            font-weight: 700;
            color: #ffffff;
        }
        .curata-tagline {
            font-size: 14px;
            color: #bbbbbb;
            margin-top: -4px;
        }
        h2, h3, h4 { color: #ffffff !important; }
        .stMetric {
            background-color: #121212 !important;
            border-radius: 10px;
            padding: 6px !important;
        }
        .curata-divider {
            margin: 15px 0;
            border-top: 1px solid #262626;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.3rem;
        }
        .stTabs [data-baseweb="tab"] {
            background-color: #121212;
            padding: 6px 12px;
            border-radius: 20px;
            color: #cccccc;
        }
        .stTabs [aria-selected="true"] {
            background-color: #1f6feb !important;
            color: #ffffff !important;
        }
        .stDataFrame, .stTable {
            color: #e5e5e5;
        }
        .stSlider, .stNumberInput, .stDateInput, .stTextInput {
            color: #e5e5e5;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <div class="curata-header">
        <div class="curata-title">Curata.shop Dashboard</div>
        <div class="curata-tagline">Daily Sales • Profit • Performance</div>
    </div>
""", unsafe_allow_html=True)

if "initialized_days" not in st.session_state:
    st.session_state.initialized_days = 0

def init_day_state(day_index: int):
    key_orders = f"orders_day_{day_index}"
    if key_orders not in st.session_state:
        st.session_state[key_orders] = 1

tabs = st.tabs(["Inputs & FX", "KPIs & Charts", "Summaries", "Export"])

with tabs[0]:
    st.subheader("📅 Date range")
    days = st.number_input("Number of days", min_value=1, step=1)
    start_date = st.date_input("Select start date")

    for i in range(int(days)):
        init_day_state(i)

    st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)
    st.subheader("💱 Live FX (USD → GBP)")

    def get_live_rate():
        try:
            r = requests.get("https://api.exchangerate.host/latest?base=USD&symbols=GBP")
            d = r.json()
            return d["rates"]["GBP"]
        except Exception:
            return None

    live_rate = get_live_rate()
    if live_rate:
        st.success(f"Live USD → GBP Rate: {live_rate:.4f}")
    else:
        st.error("Unable to fetch live rate. Using fallback rate 0.79.")
        live_rate = 0.79

    st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)
    st.subheader("📝 Daily inputs")

    order_values_daily = []
    order_profits_daily = []
    ad_spend_daily = []
    dates_labels = []
    dates_dt = []
    profit_after_ads_daily = []
    profit_after_ads_gbp_daily = []
    percent_profit_daily = []

    for i in range(int(days)):
        current_date = start_date + timedelta(days=i)
        weekday = current_date.strftime("%A")
        date_label = f"{weekday} — {current_date.strftime('%d %b %Y')}"
        key_orders = f"orders_day_{i}"

        with st.expander(f"Orders for {date_label}", expanded=False):
            st.write(f"Enter each order's sales and profit for {date_label}:")
            add_order = st.button(f"➕ Add order for {date_label}", key=f"add_order_day_{i}")
            if add_order:
                st.session_state[key_orders] += 1

            num_orders = st.session_state[key_orders]
            day_sales = 0.0
            day_profit = 0.0

            for j in range(num_orders):
                c1, c2 = st.columns(2)
                with c1:
                    sales = st.number_input(
                        f"Order {j+1} sales ($) — {date_label}",
                        min_value=0.0,
                        step=0.01,
                        key=f"day_{i}_order_{j}_sales"
                    )
                with c2:
                    profit = st.number_input(
                        f"Order {j+1} profit ($) — {date_label}",
                        min_value=0.0,
                        step=0.01,
                        key=f"day_{i}_order_{j}_profit"
                    )
                day_sales += sales
                day_profit += profit

        ad_spend = st.number_input(
            f"Ad spend ($) for {date_label}",
            min_value=0.0,
            step=0.01,
            value=64.00,
            key=f"ad_spend_day_{i}"
        )

        profit_after_ads = day_profit - ad_spend
        percent_profit = (day_profit / day_sales * 100) if day_sales > 0 else 0.0
        profit_after_ads_gbp = profit_after_ads * live_rate

        st.markdown(f"#### 📌 Daily summary — {date_label}")
        ca, cb = st.columns(2)
        ca.metric("Daily total sales", f"${day_sales:,.2f}")
        cb.metric("Daily total profit", f"${day_profit:,.2f}")

        cc, cd = st.columns(2)
        cc.metric("Daily ad spend", f"${ad_spend:,.2f}")
        cd.metric("Daily profit after ads", f"${profit_after_ads:,.2f}")

        ce, _ = st.columns(2)
        ce.metric("Daily profit after ads (£)", f"£{profit_after_ads_gbp:,.2f}")
        st.metric("Daily percentage profit", f"{percent_profit:.2f}%")

        order_values_daily.append(day_sales)
        order_profits_daily.append(day_profit)
        ad_spend_daily.append(ad_spend)
        dates_labels.append(date_label)
        dates_dt.append(current_date)
        profit_after_ads_daily.append(profit_after_ads)
        profit_after_ads_gbp_daily.append(profit_after_ads_gbp)
        percent_profit_daily.append(percent_profit)

df = pd.DataFrame({
    "Date": dates_labels,
    "Date_dt": dates_dt,
    "Sales ($)": order_values_daily,
    "Profit ($)": order_profits_daily,
    "Ad Spend ($)": ad_spend_daily,
    "Profit After Ads ($)": profit_after_ads_daily,
    "Profit After Ads (£)": profit_after_ads_gbp_daily,
    "Profit %": percent_profit_daily
})
with tabs[1]:
    st.subheader("📌 Overall KPIs")

    total_sales = df["Sales ($)"].sum()
    total_profit = df["Profit ($)"].sum()
    total_ad_spend = df["Ad Spend ($)"].sum()
    total_profit_after_ads = df["Profit After Ads ($)"].sum()
    total_profit_after_ads_gbp = df["Profit After Ads (£)"].sum()

    k1, k2 = st.columns(2)
    k1.metric("Total sales", f"${total_sales:,.2f}")
    k2.metric("Total profit", f"${total_profit:,.2f}")

    k3, k4 = st.columns(2)
    k3.metric("Total ad spend", f"${total_ad_spend:,.2f}")
    k4.metric("Total profit after ads", f"${total_profit_after_ads:,.2f}")

    overall_profit_percentage = (total_profit / total_sales * 100) if total_sales > 0 else 0
    st.metric("Overall profit %", f"{overall_profit_percentage:.2f}%")

    st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)
    st.subheader("📈 ROAS")

    roas = (total_sales / total_ad_spend) if total_ad_spend > 0 else 0
    st.metric("ROAS", f"{roas:.2f}x")

    st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)
    st.subheader("💷 Total profit after ads (USD → GBP)")
    st.metric("Total profit after ads (£)", f"£{total_profit_after_ads_gbp:,.2f}")

    st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)
    st.subheader("📊 Charts")

    st.markdown("##### Sales trend")
    st.line_chart(df.set_index("Date")["Sales ($)"])

    st.markdown("##### Profit trend")
    st.line_chart(df.set_index("Date")["Profit ($)"])

    st.markdown("##### Daily breakdown")
    st.dataframe(
        df[[
            "Date",
            "Sales ($)",
            "Profit ($)",
            "Ad Spend ($)",
            "Profit After Ads ($)",
            "Profit After Ads (£)",
            "Profit %"
        ]].style.format({
            "Sales ($)": "${:,.2f}",
            "Profit ($)": "${:,.2f}",
            "Ad Spend ($)": "${:,.2f}",
            "Profit After Ads ($)": "${:,.2f}",
            "Profit After Ads (£)": "£{:,.2f}",
            "Profit %": "{:.2f}%"
        })
    )

with tabs[2]:
    st.subheader("📅 Weekly / monthly / yearly summaries")

    df_summary = df.copy()
    df_summary["Date_dt"] = pd.to_datetime(df_summary["Date_dt"])
    df_summary["Week"] = df_summary["Date_dt"].dt.isocalendar().week
    df_summary["Month"] = df_summary["Date_dt"].dt.month
    df_summary["Year"] = df_summary["Date_dt"].dt.year

    st.markdown("##### Weekly summary")
    weekly = df_summary.groupby("Week").agg({
        "Sales ($)": "sum",
        "Profit ($)": "sum",
        "Ad Spend ($)": "sum",
        "Profit After Ads ($)": "sum",
        "Profit After Ads (£)": "sum"
    }).reset_index()
    weekly["Profit %"] = (weekly["Profit ($)"] / weekly["Sales ($)"] * 100).fillna(0)

    st.dataframe(weekly.style.format({
        "Sales ($)": "${:,.2f}",
        "Profit ($)": "${:,.2f}",
        "Ad Spend ($)": "${:,.2f}",
        "Profit After Ads ($)": "${:,.2f}",
        "Profit After Ads (£)": "£{:,.2f}",
        "Profit %": "{:.2f}%"
    }))

    st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)
    st.markdown("##### Monthly summary")
    monthly = df_summary.groupby("Month").agg({
        "Sales ($)": "sum",
        "Profit ($)": "sum",
        "Ad Spend ($)": "sum",
        "Profit After Ads ($)": "sum",
        "Profit After Ads (£)": "sum"
    }).reset_index()
    monthly["Profit %"] = (monthly["Profit ($)"] / monthly["Sales ($)"] * 100).fillna(0)

    st.dataframe(monthly.style.format({
        "Sales ($)": "${:,.2f}",
        "Profit ($)": "${:,.2f}",
        "Ad Spend ($)": "${:,.2f}",
        "Profit After Ads ($)": "${:,.2f}",
        "Profit After Ads (£)": "£{:,.2f}",
        "Profit %": "{:.2f}%"
    }))

    st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)
    st.markdown("##### Yearly summary")
    yearly = df_summary.groupby("Year").agg({
        "Sales ($)": "sum",
        "Profit ($)": "sum",
        "Ad Spend ($)": "sum",
        "Profit After Ads ($)": "sum",
        "Profit After Ads (£)": "sum"
    }).reset_index()
    yearly["Profit %"] = (yearly["Profit ($)"] / yearly["Sales ($)"] * 100).fillna(0)

    st.dataframe(yearly.style.format({
        "Sales ($)": "${:,.2f}",
        "Profit ($)": "${:,.2f}",
        "Ad Spend ($)": "${:,.2f}",
        "Profit After Ads ($)": "${:,.2f}",
        "Profit After Ads (£)": "£{:,.2f}",
        "Profit %": "{:.2f}%"
    }))

with tabs[3]:
    st.subheader("📤 Export")

    csv = df[[
        "Date",
        "Sales ($)",
        "Profit ($)",
        "Ad Spend ($)",
        "Profit After Ads ($)",
        "Profit After Ads (£)",
        "Profit %"
    ]].to_csv(index=False).encode("utf-8")

    st.download_button(
        label="Download daily data as CSV",
        data=csv,
        file_name="curata_daily_data.csv",
        mime="text/csv"
    )
