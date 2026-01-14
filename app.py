import streamlit as st
import pandas as pd
from datetime import date, timedelta
import json
import os
import requests
import plotly.express as px

SESSION_FILE = "curata_session.json"

# ---------------------- Auth config (multiple users from secrets) ---------------------- #
USERS = {
    st.secrets["auth"]["user1"]: st.secrets["auth"]["pass1"],
    st.secrets["auth"]["user2"]: st.secrets["auth"]["pass2"],
}

# ---------------------- Page config ---------------------- #
st.set_page_config(
    page_title="Curata Daily Performance Dashboard",
    layout="wide",
)

# ---------------------- Styling (dark mode + mobile) ---------------------- #
st.markdown(
    """
<style>
 /* ------------------------------
   GLOBAL DARK THEME
------------------------------ */
.main, .block-container {
    background-color: #0d0d0d !important;
    color: #ffffff !important;
}
.main * {
    color: #ffffff !important;
}

/* ------------------------------
   HEADER
------------------------------ */
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

/* ------------------------------
   HEADINGS
------------------------------ */
h1, h2, h3, h4, h5 {
    font-weight: 700 !important;
}

/* ------------------------------
   METRICS
------------------------------ */
[data-testid="stMetric"], .stMetric {
    background-color: #1a1a1a !important;
    border-radius: 10px !important;
    padding: 10px !important;
}
[data-testid="stMetric"] * {
    color: #ffffff !important;
    font-weight: 600;
}

/* ------------------------------
   DIVIDERS
------------------------------ */
.curata-divider {
    margin: 18px 0;
    border-top: 1px solid #2e2e2e;
}

/* ------------------------------
   TABS
------------------------------ */
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

/* ------------------------------
   INPUTS
------------------------------ */
input, textarea, select {
    background-color: #1a1a1a !important;
    color: #ffffff !important;
    border: 1px solid #333333 !important;
    font-weight: 500 !important;
}
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

/* ------------------------------
   TABLES
------------------------------ */
.stDataFrame, .stTable {
    color: #ffffff !important;
}

/* ------------------------------
   BUTTONS (GLOBAL + EXPORT)
------------------------------ */
div.stDownloadButton[data-testid="stDownloadButton"] > button[data-testid="stBaseButton-secondary"] {
    background-color: #2563eb !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    border-radius: 8px !important;
    padding: 8px 14px !important;
    border: none !important;
    box-shadow: none !important;
}
div.stDownloadButton[data-testid="stDownloadButton"] > button[data-testid="stBaseButton-secondary"]:hover {
    background-color: #1d4ed8 !important;
}

.stButton > button,
button[data-testid="formSubmitButton"] {
    background-color: #2563eb !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    border-radius: 8px !important;
    padding: 8px 14px !important;
    border: none !important;
    box-shadow: none !important;
}
.stButton > button:hover,
button[data-testid="formSubmitButton"]:hover {
    background-color: #1d4ed8 !important;
}

/* Remove white wrapper div around form submit buttons */
button[data-testid="formSubmitButton"] + div {
    background-color: transparent !important;
}
div.stButton {
    background-color: transparent !important;
}

/* ------------------------------
   EXPANDERS (MATCHING YOUR DOM)
------------------------------ */
div.stExpander[data-testid="stExpander"] {
    background-color: #111111 !important;
    border-radius: 6px !important;
}
div.stExpander[data-testid="stExpander"] > details > summary {
    background-color: #1a1a1a !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    border-radius: 6px !important;
    padding: 8px !important;
    list-style: none !important;
}
div.stExpander[data-testid="stExpander"] > details[open] > summary {
    background-color: #16a34a !important;
    color: #ffffff !important;
    font-weight: 800 !important;
}
div.stExpander[data-testid="stExpander"] > details[open] > summary:hover {
    background-color: #15803d !important;
}
div.stExpander[data-testid="stExpander"] > details > div[data-testid="stExpanderDetails"] {
    background-color: #111111 !important;
}

/* ------------------------------
   MOBILE
------------------------------ */
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

# ---------------------- Live FX rate ---------------------- #
@st.cache_data(ttl=60 * 60)
def fetch_live_fx_rate():
    """
    Fetch USD→GBP FX rate from exchangerate.host.
    Returns a float, or None if the call fails.
    """
    url = "https://api.exchangerate.host/latest?base=USD&symbols=GBP"
    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            rate = data.get("rates", {}).get("GBP", None)
            if isinstance(rate, (int, float)):
                return float(rate)
    except Exception:
        pass
    return None

# ---------------------- Session helpers ---------------------- #
def get_app_state_keys():
    keys = []
    for k in st.session_state.keys():
        if (
            k.startswith("orders_day_")
            or k.startswith("day_")
            or k.startswith("ad_spend_day_")
            or k in ["days", "start_date", "fx_rate", "default_ad_spend", "visitors_per_day"]
        ):
            keys.append(k)
    return keys

def export_session_state_dict():
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
    data = export_session_state_dict()
    try:
        with open(SESSION_FILE, "w") as f:
            json.dump(data, f)
        st.success("Session saved on server.")
    except Exception:
        st.warning("Could not save session to server.")

def load_session_from_file():
    if not os.path.exists(SESSION_FILE):
        st.warning("No saved session found on the server.")
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
        st.success("Session loaded from server. Rerunning...")
        st.rerun()
    except Exception as e:
        st.warning(f"Could not load session: {e}")

def load_session_from_uploaded_json(uploaded_file):
    try:
        data = json.load(uploaded_file)
    except Exception:
        st.warning("Invalid JSON file.")
        return
    if not isinstance(data, dict):
        st.warning("Uploaded JSON is not a valid session backup.")
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
        st.success("Session restored from uploaded file. Rerunning...")
        st.rerun()
    except Exception as e:
        st.warning(f"Could not apply uploaded session: {e}")

def reset_session_state():
    # Clear all app-related keys but keep auth
    for k in get_app_state_keys():
        st.session_state.pop(k, None)
    for meta_key in ["session_restored"]:
        st.session_state.pop(meta_key, None)
    st.success("Session state reset. Rerunning...")
    st.rerun()

def init_default_state():
    if "days" not in st.session_state:
        st.session_state["days"] = 7
    if "start_date" not in st.session_state:
        st.session_state["start_date"] = date.today()
    if "fx_rate" not in st.session_state:
        live_rate = fetch_live_fx_rate()
        st.session_state["fx_rate"] = live_rate if live_rate is not None else 0.79
    if "default_ad_spend" not in st.session_state:
        st.session_state["default_ad_spend"] = 64.0
    if "visitors_per_day" not in st.session_state:
        st.session_state["visitors_per_day"] = 1

def init_day_state(day_index: int):
    key_orders = f"orders_day_{day_index}"
    if key_orders not in st.session_state:
        st.session_state[key_orders] = 1

# ---------------------- Auth helpers ---------------------- #
def init_auth_state():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if "auth_user" not in st.session_state:
        st.session_state["auth_user"] = None

def login_screen():
    st.title("Curata Dashboard Login")
    st.write("Access is restricted. Please log in to continue.")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Log in", type="primary")

    if submit:
        if username in USERS and USERS[username] == password:
            st.session_state["authenticated"] = True
            st.session_state["auth_user"] = username
            st.success(f"Welcome, {username}. Loading dashboard...")
            st.rerun()
        else:
            st.error("Invalid username or password.")

def logout_button():
    if st.sidebar.button("Log out"):
        st.session_state["authenticated"] = False
        st.session_state["auth_user"] = None
        st.rerun()

# ---------------------- Main app ---------------------- #
def main_app():
    init_default_state()

    # Auto-restore session once after login
    if "session_restored" not in st.session_state:
        if os.path.exists(SESSION_FILE):
            try:
                load_session_from_file()
            except Exception:
                pass
        st.session_state["session_restored"] = True

    # Header
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

    # Sidebar: user + FX refresh + logout
    st.sidebar.markdown(f"**Logged in as:** {st.session_state.get('auth_user', 'Unknown')}")
    if st.sidebar.button("Refresh FX rate (USD → GBP)"):
        new_rate = fetch_live_fx_rate()
        if new_rate is not None:
            st.session_state["fx_rate"] = new_rate
            st.sidebar.success(f"Updated FX rate: {new_rate:.4f}")
        else:
            st.sidebar.warning("Could not fetch live FX rate. Keeping existing value.")
    logout_button()

    # Tabs
    tabs = st.tabs(
        [
            "Inputs",
            "KPIs",
            "Summaries",
            "Export",
            "Session JSON",
            "Session Controls",
            "Summary Charts",
        ]
    )

    daily_rows = []

    # ---------------------- Tab 1: Inputs ---------------------- #
    with tabs[0]:
        st.subheader("📥 Inputs")

        col_a, col_b, col_c, col_d = st.columns([1, 1, 1, 1])
        with col_a:
            days = st.number_input(
                "Number of days", min_value=1, max_value=31, step=1, key="days"
            )
        with col_b:
            start_date = st.date_input("Select start date", key="start_date")
        with col_c:
            fx_rate = st.number_input(
                "FX rate (USD → GBP)", min_value=0.0, step=0.0001, key="fx_rate"
            )
        with col_d:
            visitors_per_day = st.number_input(
                "Visitors per day",
                min_value=1,
                step=1,
                key="visitors_per_day",
            )

        default_ad_spend = st.number_input(
            "Default ad spend ($) for all days",
            min_value=0.0,
            step=1.0,
            key="default_ad_spend",
        )

        st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)

        for day_index in range(int(days)):
            init_day_state(day_index)
            day_date = start_date + timedelta(days=day_index)
            day_label = day_date.strftime("%A — %d %b %Y")

            ad_spend_key = f"ad_spend_day_{day_index}"

            if ad_spend_key in st.session_state:
                indicator = "(custom)"
            else:
                indicator = "(using default)"

            default_for_day = st.session_state.get(
                ad_spend_key,
                st.session_state.get("default_ad_spend", 64.0),
            )

            st.markdown(f"### Day {day_index + 1}: {day_label}")

            ad_spend = st.number_input(
                f"Ad spend ($) for {day_label} {indicator}",
                min_value=0.0,
                step=1.0,
                value=default_for_day,
                key=ad_spend_key,
            )

            orders_key = f"orders_day_{day_index}"
            current_orders = st.session_state[orders_key]

            expander_key = f"expander_open_day_{day_index}"
            if expander_key not in st.session_state:
              st.session_state[expander_key] = False

            with st.expander(f"Orders for {day_label} (Total: {current_orders})", expanded=st.session_state[expander_key]):

                c1, c2, _ = st.columns([1, 1, 1])
                with c1:
                    if st.button(f"➕ Add order (Day {day_index + 1})"):
                        st.session_state[orders_key] += 1
                        st.session_state[expander_key] = True
                        st.rerun()
                with c2:
                    if st.button(f"➖ Remove last order (Day {day_index + 1})"):
                        if st.session_state[orders_key] > 1:
                            st.session_state[orders_key] -= 1
                            st.session_state[expander_key] = True
                            st.rerun()

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

            profit_after_ads = day_profit - ad_spend
            profit_after_ads_gbp = profit_after_ads * (fx_rate if fx_rate else 0.0)
            percent_profit = ((day_profit - ad_spend) / day_sales * 100) if day_sales > 0 else 0.0

            visitors = st.session_state.get("visitors_per_day", 1)
            orders_count = current_orders

            daily_rows.append(
                {
                    "Date": day_date,
                    "Sales ($)": round(day_sales, 2),
                    "Profit ($)": round(day_profit, 2),
                    "Ad Spend ($)": round(ad_spend, 2),
                    "Profit After Ads ($)": round(profit_after_ads, 2),
                    "Profit After Ads (£)": round(profit_after_ads_gbp, 2),
                    "Profit %": round(percent_profit, 2),
                    "Orders": orders_count,
                    "Visitors": visitors,
                }
            )

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
                    "Orders",
                    "Visitors",
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
        st.subheader("📤 Export data")

        df = st.session_state.get("daily_df", pd.DataFrame())
        if df.empty:
            st.info("No data to export yet. Fill in the Inputs tab first.")
        else:
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download daily data as CSV",
                data=csv,
                file_name="curata_daily_data.csv",
                mime="text/csv",
            )

    # ---------------------- Tab 5: Session JSON ---------------------- #
    with tabs[4]:
        st.subheader("🧾 Session JSON view & download")

        sess_dict = export_session_state_dict()
        st.json(sess_dict)

        json_bytes = json.dumps(sess_dict, indent=2).encode("utf-8")
        st.download_button(
            label="Download session JSON",
            data=json_bytes,
            file_name="curata_session.json",
            mime="application/json",
        )

    # ---------------------- Tab 6: Session Controls ---------------------- #
    with tabs[5]:
        st.subheader("🧰 Session controls")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Save session to server"):
                save_session_to_file()
        with col2:
            if st.button("📂 Load session from server"):
                load_session_from_file()

        st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)

        uploaded = st.file_uploader("Upload session JSON to restore", type=["json"])
        if uploaded is not None:
            if st.button("Restore from uploaded JSON"):
                load_session_from_uploaded_json(uploaded)

        st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)

        if st.button("♻️ Reset session (keep login)"):
            reset_session_state()

    # ---------------------- Tab 7: Summary Charts ---------------------- #
    with tabs[6]:
        st.subheader("📉 Summary charts")

        df = st.session_state.get("daily_df", pd.DataFrame())
        if df.empty:
            st.info("No data yet. Fill in the Inputs tab first.")
        else:
            df_plot = df.copy()
            df_plot["Date"] = pd.to_datetime(df_plot["Date"])

            col1, col2 = st.columns(2)

            with col1:
                fig_sales = px.line(
                    df_plot,
                    x="Date",
                    y="Sales ($)",
                    title="Daily sales ($)",
                )
                st.plotly_chart(fig_sales, use_container_width=True)

                fig_profit = px.line(
                    df_plot,
                    x="Date",
                    y="Profit ($)",
                    title="Daily profit ($)",
                )
                st.plotly_chart(fig_profit, use_container_width=True)

            with col2:
                fig_ad = px.line(
                    df_plot,
                    x="Date",
                    y="Ad Spend ($)",
                    title="Daily ad spend ($)",
                )
                st.plotly_chart(fig_ad, use_container_width=True)

                fig_profit_after = px.line(
                    df_plot,
                    x="Date",
                    y="Profit After Ads ($)",
                    title="Profit after ads ($)",
                )
                st.plotly_chart(fig_profit_after, use_container_width=True)

            st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)

            if "Visitors" in df_plot.columns and "Orders" in df_plot.columns:
                df_plot["Conversion rate (%)"] = (
                    df_plot.apply(
                        lambda row: (row["Orders"] / row["Visitors"] * 100)
                        if row["Visitors"] > 0
                        else 0.0,
                        axis=1,
                    )
                )
                fig_conv = px.line(
                    df_plot,
                    x="Date",
                    y="Conversion rate (%)",
                    title="Conversion rate (%)",
                )
                st.plotly_chart(fig_conv, use_container_width=True)

# ---------------------- Run the app ---------------------- #
init_auth_state()

if not st.session_state["authenticated"]:
    login_screen()
else:
    main_app()
