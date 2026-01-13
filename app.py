import streamlit as st
import pandas as pd
from datetime import date, timedelta
import json
import os

SESSION_FILE = "curata_session.json"

# ---------------------- Page config ---------------------- #
st.set_page_config(
    page_title="Curata Daily Performance Dashboard",
    layout="wide",
)


# ---------------------- Styling (dark mode + mobile) ---------------------- #
st.markdown(
    """
<style>
    /* Global app background + text */
    .main, .block-container {
        background-color: #0d0d0d !important;
        color: #ffffff !important;
    }

    /* Make almost all text white by default */
    .main * {
        color: #ffffff !important;
    }

    /* Header */
    .curata-header {
        text-align: center;
        padding: 12px 0 20px 0;
        border-bottom: 1px solid #333333;
    }
    .curata-title {
        font-size: 28px;
        font-weight: 800;
    }
    .curata-tagline {
        font-size: 15px;
        opacity: 0.85;
    }

    /* Headings */
    h1, h2, h3, h4, h5 {
        font-weight: 700 !important;
    }

    /* Metrics (KPI cards) */
    [data-testid="stMetric"], .stMetric {
        background-color: #1a1a1a !important;
        border-radius: 10px !important;
        padding: 10px !important;
    }
    [data-testid="stMetric"] * {
        color: #ffffff !important;
        font-weight: 600;
    }

    /* Dividers */
    .curata-divider {
        margin: 18px 0;
        border-top: 1px solid #2e2e2e;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.4rem;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #1a1a1a !important;
        padding: 8px 14px !important;
        border-radius: 20px !important;
        color: #cccccc !important;
        font-weight: 600 !important;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2563eb !important;
        color: #ffffff !important;
        font-weight: 700 !important;
    }

    /* Expanders */
    .streamlit-expanderHeader {
        font-weight: 700 !important;
    }
    .streamlit-expanderContent {
        background-color: #111111 !important;
    }

    /* Inputs (number, text, date, selects, sliders) */
    input, textarea, select {
        background-color: #1a1a1a !important;
        color: #ffffff !important;
        border: 1px solid #333333 !important;
        font-weight: 500 !important;
    }

    /* Explicit widget labels to bright white + bold */
    .stTextInput label,
    .stNumberInput label,
    .stDateInput label,
    .stSelectbox label,
    .stSlider label,
    .stMultiSelect label,
    .stRadio label,
    .stCheckbox label,
    .stTextArea label {
        color: #ffffff !important;
        font-weight: 700 !important;
    }

    /* Some internal label classes (for safety across layouts) */
    .css-1p3j8v5, .css-16idsys, .css-1kyxreq {
        color: #ffffff !important;
        font-weight: 700 !important;
    }

    /* Tables */
    .stDataFrame, .stTable {
        color: #ffffff !important;
    }

    /* Buttons */
    .stButton>button {
        background-color: #2563eb !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        border-radius: 8px !important;
        padding: 8px 14px !important;
        border: none !important;
    }
    .stButton>button:hover {
        background-color: #1d4ed8 !important;
    }

    @media (max-width: 768px) {
        .curata-title {
            font-size: 22px;
        }
        .curata-tagline {
            font-size: 13px;
        }
    }
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------- Session helpers ---------------------- #
def get_app_state_keys():
    """Return the keys we consider part of the 'clean app state'."""
    keys = []
    for k in st.session_state.keys():
        if (
            k.startswith("orders_day_")
            or k.startswith("day_")
            or k.startswith("ad_spend_day_")
            or k in ["days", "start_date", "fx_rate"]
        ):
            keys.append(k)
    return keys


def export_session_state_dict():
    """Export only clean app-related keys as a dict."""
    data = {}
    for k in get_app_state_keys():
        v = st.session_state.get(k)
        if isinstance(v, (pd.Timestamp,)):
            data[k] = v.isoformat()
        elif isinstance(v, (date,)):
            data[k] = v.isoformat()
        else:
            data[k] = v
    return data


def save_session_to_file():
    """Save session state to a local JSON file (best effort, may not persist on Streamlit Cloud)."""
    data = export_session_state_dict()
    try:
        with open(SESSION_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        st.warning(f"Could not save session to file: {e}")


def load_session_from_file():
    """Load session state from the local JSON file if it exists."""
    if not os.path.exists(SESSION_FILE):
        st.warning("No saved session found on the server (file missing).")
        return
    try:
        with open(SESSION_FILE, "r") as f:
            data = json.load(f)
        for k, v in data.items():
            if k == "start_date":
                try:
                    st.session_state[k] = pd.to_datetime(v).date()
                except Exception:
                    st.session_state[k] = v
            else:
                st.session_state[k] = v
        st.success("Session loaded from file. Rerunning app...")
        st.experimental_rerun()
    except Exception as e:
        st.warning(f"Could not load session from file: {e}")


def load_session_from_uploaded_json(uploaded_file):
    """Load session state from an uploaded JSON backup."""
    try:
        data = json.load(uploaded_file)
    except Exception:
        st.warning("Invalid JSON file. Please upload a valid backup.")
        return

    if not isinstance(data, dict):
        st.warning("Uploaded JSON does not look like a valid session backup.")
        return

    try:
        for k, v in data.items():
            if k == "start_date":
                try:
                    st.session_state[k] = pd.to_datetime(v).date()
                except Exception:
                    st.session_state[k] = v
            else:
                st.session_state[k] = v
        st.success("Session loaded from uploaded JSON. Rerunning app...")
        st.experimental_rerun()
    except Exception as e:
        st.warning(f"Could not apply uploaded session: {e}")


def init_default_state():
    """Initialize core defaults if not present."""
    if "days" not in st.session_state:
        st.session_state["days"] = 7
    if "start_date" not in st.session_state:
        st.session_state["start_date"] = date.today()
    if "fx_rate" not in st.session_state:
        st.session_state["fx_rate"] = 0.79  # default USD->GBP rate


def init_day_state(day_index: int):
    key_orders = f"orders_day_{day_index}"
    if key_orders not in st.session_state:
        st.session_state[key_orders] = 1


# ---------------------- App header ---------------------- #
init_default_state()

st.markdown(
    """
<div class="curata-header">
    <div class="curata-title">Curata Daily Performance Dashboard</div>
    <div class="curata-tagline">
        Track daily sales, profit, ad spend and margins with quick export and restore options.
    </div>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)


# ---------------------- Tabs ---------------------- #
tabs = st.tabs(
    [
        "Inputs",
        "KPIs",
        "Summaries",
        "Export",
        "Session JSON",
    ]
)

daily_rows = []  # will hold daily calculations; stored in session for use in other tabs


# ---------------------- Tab 1: Inputs ---------------------- #
with tabs[0]:
    st.subheader("📥 Inputs")

    col_a, col_b, col_c = st.columns([1, 1, 1])
    with col_a:
        days = st.number_input(
            "Number of days",
            min_value=1,
            max_value=31,
            step=1,
            key="days",
        )
    with col_b:
        start_date = st.date_input(
            "Select start date",
            key="start_date",
        )
    with col_c:
        fx_rate = st.number_input(
            "FX rate (USD → GBP)",
            min_value=0.0,
            step=0.01,
            key="fx_rate",
        )

    st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)

    # Inputs per day
    for day_index in range(int(days)):
        init_day_state(day_index)
        day_date = start_date + timedelta(days=day_index)
        day_label = day_date.strftime("%A — %d %b %Y")

        st.markdown(f"### Day {day_index + 1}: {day_label}")

        # Ad spend for this day
        ad_spend_key = f"ad_spend_day_{day_index}"
        ad_spend = st.number_input(
            f"Ad spend ($) for {day_label}",
            min_value=0.0,
            step=1.0,
            key=ad_spend_key,
        )

        # Orders expander
        orders_key = f"orders_day_{day_index}"
        current_orders = st.session_state[orders_key]

        with st.expander(f"Orders for {day_label} (Total: {current_orders})", expanded=False):
            c1, c2, c3 = st.columns([1, 1, 1])
            with c1:
                if st.button(f"➕ Add order (Day {day_index + 1})"):
                    st.session_state[orders_key] += 1
                    st.experimental_rerun()
            with c2:
                if st.button(f"➖ Remove last order (Day {day_index + 1})"):
                    if st.session_state[orders_key] > 1:
                        st.session_state[orders_key] -= 1
                        st.experimental_rerun()
            with c3:
                st.write("")

            day_sales = 0.0
            day_profit = 0.0

            for order_index in range(1, st.session_state[orders_key] + 1):
                st.markdown(f"**Order {order_index}**")
                col1, col2 = st.columns(2)

                sales_key = f"day_{day_index}_order_{order_index}_sales"
                profit_key = f"day_{day_index}_order_{order_index}_profit"

                with col1:
                    sales_val = st.number_input(
                        f"Sales ($) — Order {order_index}",
                        min_value=0.0,
                        step=1.0,
                        key=sales_key,
                    )
                with col2:
                    profit_val = st.number_input(
                        f"Profit ($) — Order {order_index}",
                        min_value=0.0,
                        step=1.0,
                        key=profit_key,
                    )

                day_sales += sales_val
                day_profit += profit_val

        # Calculations for the day
        profit_after_ads = day_profit - ad_spend
        profit_after_ads_gbp = profit_after_ads * (fx_rate if fx_rate else 0.0)
        # Corrected formula: (profit - ad_spend) / total sales * 100
        percent_profit = ((day_profit - ad_spend) / day_sales * 100) if day_sales > 0 else 0.0

        daily_rows.append(
            {
                "Date": day_date,
                "Sales ($)": round(day_sales, 2),
                "Profit ($)": round(day_profit, 2),
                "Ad Spend ($)": round(ad_spend, 2),
                "Profit After Ads ($)": round(profit_after_ads, 2),
                "Profit After Ads (£)": round(profit_after_ads_gbp, 2),
                "Profit %": round(percent_profit, 2),
            }
        )

    # Build daily dataframe and store in session for other tabs
    if daily_rows:
        df = pd.DataFrame(daily_rows)
    else:
        df = pd.DataFrame(
            columns=[
                "Date",
                "Sales ($)",
                "Profit ($)",
                "Ad Spend ($)",
                "Profit After Ads ($)",
                "Profit After Ads (£)",
                "Profit %",
            ]
        )

    st.session_state["daily_df"] = df

    st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)
    st.subheader("📅 Daily overview (table)")
    st.dataframe(df, use_container_width=True)


# ---------------------- Tab 2: KPIs ---------------------- #
with tabs[1]:
    st.subheader("📊 KPIs")

    df = st.session_state.get("daily_df", pd.DataFrame())
    if df.empty:
        st.info("No data yet. Fill in the Inputs tab first.")
    else:
        total_sales = float(df["Sales ($)"].sum())
        total_profit = float(df["Profit ($)"].sum())
        total_ad_spend = float(df["Ad Spend ($)"].sum())
        total_profit_after_ads = float(df["Profit After Ads ($)"].sum())
        total_profit_after_ads_gbp = float(df["Profit After Ads (£)"].sum())

        # Corrected overall profit % = (Profit - Ad Spend) / Sales * 100
        overall_profit_percent = (
            (total_profit - total_ad_spend) / total_sales * 100 if total_sales > 0 else 0.0
        )

        roas = total_sales / total_ad_spend if total_ad_spend > 0 else 0.0

        c1, c2, c3, c4, c5 = st.columns(5)

        with c1:
            st.metric("Total sales ($)", f"${total_sales:,.2f}")
        with c2:
            st.metric("Total profit ($)", f"${total_profit:,.2f}")
        with c3:
            st.metric("Total ad spend ($)", f"${total_ad_spend:,.2f}")
        with c4:
            st.metric("Profit after ads ($)", f"${total_profit_after_ads:,.2f}")
        with c5:
            st.metric("Profit after ads (£)", f"£{total_profit_after_ads_gbp:,.2f}")

        st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)

        c6, c7 = st.columns(2)
        with c6:
            st.metric("Overall profit % (after ads)", f"{overall_profit_percent:,.2f}%")
        with c7:
            st.metric("ROAS (sales ÷ ad spend)", f"{roas:,.2f}x")


# ---------------------- Tab 3: Summaries ---------------------- #
with tabs[2]:
    st.subheader("📈 Summaries (weekly, monthly, yearly)")

    df = st.session_state.get("daily_df", pd.DataFrame())
    if df.empty:
        st.info("No data yet. Fill in the Inputs tab first.")
    else:
        df_summary = df.copy()
        df_summary["Date"] = pd.to_datetime(df_summary["Date"])

        # Weekly summary
        st.markdown("### Weekly summary")
        weekly = (
            df_summary
            .groupby(df_summary["Date"].dt.to_period("W").apply(lambda r: r.start_time.date()))
            .agg(
                {
                    "Sales ($)": "sum",
                    "Profit ($)": "sum",
                    "Ad Spend ($)": "sum",
                    "Profit After Ads ($)": "sum",
                    "Profit After Ads (£)": "sum",
                }
            )
            .reset_index()
            .rename(columns={"Date": "Week starting"})
        )

        if not weekly.empty:
            weekly["Profit %"] = (
                (weekly["Profit ($)"] - weekly["Ad Spend ($)"]) / weekly["Sales ($)"] * 100
            ).fillna(0)
            st.dataframe(weekly, use_container_width=True)
        else:
            st.write("No weekly data to display.")

        st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)

        # Monthly summary
        st.markdown("### Monthly summary")
        monthly = (
            df_summary
            .groupby(df_summary["Date"].dt.to_period("M"))
            .agg(
                {
                    "Sales ($)": "sum",
                    "Profit ($)": "sum",
                    "Ad Spend ($)": "sum",
                    "Profit After Ads ($)": "sum",
                    "Profit After Ads (£)": "sum",
                }
            )
            .reset_index()
        )
        monthly["Month"] = monthly["Date"].dt.strftime("%Y-%m")
        monthly = monthly.drop(columns=["Date"])

        if not monthly.empty:
            monthly["Profit %"] = (
                (monthly["Profit ($)"] - monthly["Ad Spend ($)"]) / monthly["Sales ($)"] * 100
            ).fillna(0)
            st.dataframe(monthly, use_container_width=True)
        else:
            st.write("No monthly data to display.")

        st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)

        # Yearly summary
        st.markdown("### Yearly summary")
        yearly = (
            df_summary
            .groupby(df_summary["Date"].dt.year)
            .agg(
                {
                    "Sales ($)": "sum",
                    "Profit ($)": "sum",
                    "Ad Spend ($)": "sum",
                    "Profit After Ads ($)": "sum",
                    "Profit After Ads (£)": "sum",
                }
            )
            .reset_index()
            .rename(columns={"Date": "Year"})
        )

        if not yearly.empty:
            yearly["Profit %"] = (
                (yearly["Profit ($)"] - yearly["Ad Spend ($)"]) / yearly["Sales ($)"] * 100
            ).fillna(0)
            st.dataframe(yearly, use_container_width=True)
        else:
            st.write("No yearly data to display.")


# ---------------------- Tab 4: Export ---------------------- #
with tabs[3]:
    st.subheader("📤 Export")

    df = st.session_state.get("daily_df", pd.DataFrame())
    if df.empty:
        st.info("No data yet. Fill in the Inputs tab first.")
    else:
        csv = df[
            [
                "Date",
                "Sales ($)",
                "Profit ($)",
                "Ad Spend ($)",
                "Profit After Ads ($)",
                "Profit After Ads (£)",
                "Profit %",
            ]
        ].to_csv(index=False).encode("utf-8")

        st.download_button(
            label="Download daily data as CSV",
            data=csv,
            file_name="curata_daily_data.csv",
            mime="text/csv",
        )

    st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)
    st.subheader("💾 Session controls")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Save session (to server file)"):
            save_session_to_file()
            st.success("Session saved to server file (if environment allows).")
    with c2:
        if st.button("Load last session (from server file)"):
            load_session_from_file()


# ---------------------- Tab 5: Session JSON backup ---------------------- #
with tabs[4]:
    st.subheader("🧾 Session JSON backup")

    st.markdown("**Live JSON preview (clean app state only)**")
    session_dict = export_session_state_dict()
    st.json(session_dict)

    st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)

    # Download JSON backup
    json_bytes = json.dumps(session_dict, indent=2, default=str).encode("utf-8")
    st.download_button(
        label="Download JSON backup",
        data=json_bytes,
        file_name="curata_session_backup.json",
        mime="application/json",
    )

    st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)

    # Upload JSON backup and restore
    uploaded = st.file_uploader("Upload JSON backup to restore session", type="json")
    if uploaded is not None:
        if st.button("Restore session from uploaded JSON"):
            load_session_from_uploaded_json(uploaded)


# ---------------------- Autosave on each run ---------------------- #
# Best-effort autosave: on Streamlit Cloud this persists only while the container lives.
try:
    save_session_to_file()
except Exception:
    pass
