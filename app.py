import streamlit as st
import pandas as pd

st.set_page_config(page_title="Sales & Profit Dashboard", layout="centered")

st.title("📱 Sales & Profit Dashboard")

st.markdown("Track your daily sales, profit, ad spend, and performance trends.")

# Number of days
days = st.number_input("Number of Days", min_value=1, step=1)

order_values = []
order_profits = []

st.subheader("Daily Inputs")

for i in range(days):
    with st.container():
        st.markdown(f"### Day {i+1}")
        order_value = st.number_input(
            f"Order Value (£) — Day {i+1}",
            min_value=0.0,
            step=0.01,
            key=f"value_{i}"
        )
        order_profit = st.number_input(
            f"Profit (£) — Day {i+1}",
            min_value=0.0,
            step=0.01,
            key=f"profit_{i}"
        )
        order_values.append(order_value)
        order_profits.append(order_profit)

# Create DataFrame
df = pd.DataFrame({
    "Day": [f"Day {i+1}" for i in range(days)],
    "Sales (£)": order_values,
    "Profit (£)": order_profits
})

# Totals
total_sales = df["Sales (£)"].sum()
total_profit = df["Profit (£)"].sum()

st.subheader("📌 Key Metrics")

col1, col2 = st.columns(2)
col1.metric("Total Sales", f"£{total_sales:,.2f}")
col2.metric("Total Profit", f"£{total_profit:,.2f}")

# Ad spend
ad_spend = st.number_input("Ad Spend (£)", min_value=0.0, step=0.01)
profit_after_ads = total_profit - ad_spend

st.metric("Profit After Ad Spend", f"£{profit_after_ads:,.2f}")

# Profit percentage
profit_percentage = (total_profit / total_sales * 100) if total_sales > 0 else 0
st.metric("Profit %", f"{profit_percentage:.2f}%")

# Dashboard Section
st.subheader("📊 Dashboard")

# Line charts
st.markdown("### 📈 Sales Trend")
st.line_chart(df.set_index("Day")["Sales (£)"])

st.markdown("### 💰 Profit Trend")
st.line_chart(df.set_index("Day")["Profit (£)"])

# Table
st.markdown("### 📋 Daily Breakdown")
st.dataframe(df.style.format({"Sales (£)": "£{:.2f}", "Profit (£)": "£{:.2f}"}))
