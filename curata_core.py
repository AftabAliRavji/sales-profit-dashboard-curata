import streamlit as st
import pandas as pd
from datetime import date, timedelta
import json
import os
import requests
import plotly.express as px

# ============================================================
#  Curata Dashboard — Core Logic (Rebuilt & Polished)
#  Part 1 of 6
# ============================================================

SESSION_FILE = "curata_session.json"

# ---------------------- Auth config ---------------------- #
USERS = {
    st.secrets["auth"]["user1"]: st.secrets["auth"]["pass1"],
    st.secrets["auth"]["user2"]: st.secrets["auth"]["pass2"],
}

# ---------------------- Live FX rate ---------------------- #
@st.cache_data(ttl=60 * 60)
def fetch_live_fx_rate():
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
        st.success("Session loaded from server. Rerunning…")
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
        st.success("Session restored from uploaded file. Rerunning…")
        st.rerun()
    except Exception as e:
        st.warning(f"Could not apply uploaded session: {e}")


def reset_session_state():
    for k in get_app_state_keys():
        st.session_state.pop(k, None)
    for meta_key in ["session_restored"]:
        st.session_state.pop(meta_key, None)
    st.success("Session state reset. Rerunning…")
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

# ---------------------- Bulk import helpers ---------------------- #
def clear_day_state():
    """
    Removes all dynamic per-day and per-order keys from session_state.
    Ensures a clean slate before importing new bulk data.
    """
    for k in list(st.session_state.keys()):
        if (
            k.startswith("orders_day_")
            or k.startswith("day_")
            or k.startswith("ad_spend_day_")
            or k.startswith("expander_open_day_")
        ):
            st.session_state.pop(k, None)


def populate_from_structured_data(day_data_list):
    """
    Accepts a list of dicts in the format:
    {
        "date": python date,
        "ad_spend": float,
        "visitors": int,
        "orders": [
            {"sales": float, "profit": float},
            ...
        ]
    }
    Populates Streamlit session_state accordingly.
    """

    if not day_data_list:
        st.warning("No valid data found in uploaded file.")
        return

    # Sort by date
    day_data_list = sorted(day_data_list, key=lambda d: d["date"])

    # Set global controls
    st.session_state["start_date"] = day_data_list[0]["date"]
    st.session_state["days"] = len(day_data_list)

    # Clear old dynamic state
    clear_day_state()

    # Populate each day
    for idx, day_info in enumerate(day_data_list):
        ad_spend = float(day_info.get("ad_spend", 0.0) or 0.0)
        visitors = int(day_info.get("visitors", 1) or 1)
        orders = day_info.get("orders", [])

        st.session_state[f"ad_spend_day_{idx}"] = ad_spend
        st.session_state["visitors_per_day"] = visitors

        orders_key = f"orders_day_{idx}"
        num_orders = max(1, len(orders))
        st.session_state[orders_key] = num_orders

        for order_index in range(1, num_orders + 1):
            sales_key = f"day_{idx}_order_{order_index}_sales"
            profit_key = f"day_{idx}_order_{order_index}_profit"

            if order_index <= len(orders):
                o = orders[order_index - 1]
                st.session_state[sales_key] = float(o.get("sales", 0.0) or 0.0)
                st.session_state[profit_key] = float(o.get("profit", 0.0) or 0.0)
            else:
                st.session_state[sales_key] = 0.0
                st.session_state[profit_key] = 0.0

    st.success("Bulk data imported successfully. Reloading…")
    st.rerun()
# ============================================================
#  Curata Dashboard — Core Logic (Rebuilt & Polished)
#  Part 2 of 6
# ============================================================

def parse_json_bulk(file):
    """
    Parses a JSON file in the format:
    {
        "2026-01-08": {
            "ad_spend": 64,
            "visitors": 120,
            "orders": [
                {"sales": 87.48, "profit": 26.98},
                {"sales": 45.00, "profit": 12.00}
            ]
        },
        ...
    }
    """
    try:
        data = json.load(file)
    except Exception:
        st.error("Invalid JSON file.")
        return

    if not isinstance(data, dict):
        st.error("JSON must be an object with dates as keys.")
        return

    day_data_list = []

    for date_str, day_info in data.items():
        try:
            day_date = pd.to_datetime(date_str).date()
        except Exception:
            st.warning(f"Skipping invalid date key: {date_str}")
            continue

        if not isinstance(day_info, dict):
            st.warning(f"Skipping invalid entry for {date_str}.")
            continue

        ad_spend = day_info.get("ad_spend", 0.0)
        visitors = day_info.get("visitors", 1)
        orders_raw = day_info.get("orders", [])

        orders = []
        if isinstance(orders_raw, list):
            for o in orders_raw:
                if isinstance(o, dict):
                    orders.append(
                        {
                            "sales": float(o.get("sales", 0.0) or 0.0),
                            "profit": float(o.get("profit", 0.0) or 0.0),
                        }
                    )

        day_data_list.append(
            {
                "date": day_date,
                "ad_spend": ad_spend,
                "visitors": visitors,
                "orders": orders,
            }
        )

    populate_from_structured_data(day_data_list)


def parse_csv_bulk(file):
    """
    Parses a CSV file in the format:
    date,order_index,sales,profit,ad_spend,visitors
    2026-01-08,1,87.48,26.98,64,120
    2026-01-08,2,45.00,12.00,64,120
    """
    try:
        df = pd.read_csv(file)
    except Exception:
        st.error("Invalid CSV file.")
        return

    required_cols = {"date", "order_index", "sales", "profit"}
    if not required_cols.issubset(df.columns):
        st.error(
            "CSV must contain at least: date, order_index, sales, profit. "
            "Optional: ad_spend, visitors."
        )
        return

    df["date"] = pd.to_datetime(df["date"]).dt.date

    if "ad_spend" not in df.columns:
        df["ad_spend"] = 0.0
    if "visitors" not in df.columns:
        df["visitors"] = 1

    day_data_list = []

    for day_date, group in df.groupby("date"):
        first_row = group.iloc[0]
        ad_spend = float(first_row.get("ad_spend", 0.0) or 0.0)
        visitors = int(first_row.get("visitors", 1) or 1)

        orders = []
        group_sorted = group.sort_values(by="order_index")

        for _, row in group_sorted.iterrows():
            orders.append(
                {
                    "sales": float(row.get("sales", 0.0) or 0.0),
                    "profit": float(row.get("profit", 0.0) or 0.0),
                }
            )

        day_data_list.append(
            {
                "date": day_date,
                "ad_spend": ad_spend,
                "visitors": visitors,
                "orders": orders,
            }
        )

    populate_from_structured_data(day_data_list)

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
            st.success(f"Welcome, {username}. Loading dashboard…")
            st.rerun()
        else:
            st.error("Invalid username or password.")


def logout_button():
    if st.sidebar.button("Log out"):
        st.session_state["authenticated"] = False
        st.session_state["auth_user"] = None
        st.rerun()

# ============================================================
#  Main app — header, sidebar, tabs, and Tab 1 (Inputs)
#  Part 2 continues into Part 3
# ============================================================

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

    # ---------------------- Global CSS ---------------------- #
    st.markdown(
        """
        <style>
        .curata-header {
            padding: 0.75rem 1rem 0.25rem 1rem !important;
            background-color: #ffffff !important; /* ensures contrast */
            border-radius: 6px !important;
        }

        .curata-title {
            font-size: 1.8rem !important;
            font-weight: 900 !important;
            color: #000000 !important;
            line-height: 1.2 !important;
        }

        .curata-tagline {
            font-size: 1.05rem !important;
            font-weight: 600 !important;
            color: #333333 !important;
        }

        .curata-divider {
            border-bottom: 2px solid #d1d5db !important;
            margin: 1rem 0 1.25rem 0 !important;
        }
    /* Add the Browse button fix here */
    .stFileUploader span button {
        visibility: visible !important;
        opacity: 1 !important;
        display: inline-block !important;
        background-color: #2563eb !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        padding: 0.4rem 1rem !important;
        border-radius: 6px !important;
        border: none !important;
    }        
        </style>
        """,
        unsafe_allow_html=True,
    )



    # ---------------------- Header ---------------------- #
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

    # ---------------------- Sidebar ---------------------- #
    st.sidebar.markdown(f"**Logged in as:** {st.session_state.get('auth_user', 'Unknown')}")

    if st.sidebar.button("Refresh FX rate (USD → GBP)"):
        new_rate = fetch_live_fx_rate()
        if new_rate is not None:
            st.session_state["fx_rate"] = new_rate
            st.sidebar.success(f"Updated FX rate: {new_rate:.4f}")
        else:
            st.sidebar.warning("Could not fetch live FX rate. Keeping existing value.")

    logout_button()

    # ---------------------- Tabs ---------------------- #
    tabs = st.tabs(
        [
            "Inputs",
            "Bulk Import",
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
                "Number of days",
                min_value=1,
                max_value=31,
                step=1,
                key="days",
            )

        with col_b:
            start_date = st.date_input("Select start date", key="start_date")

        with col_c:
            fx_rate = st.number_input(
                "FX rate (USD → GBP)",
                min_value=0.0,
                step=0.0001,
                key="fx_rate",
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

        # Start looping through days
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

            # Expander open/close state
            expander_key = f"expander_open_day_{day_index}"
            if expander_key not in st.session_state:
                st.session_state[expander_key] = False

            with st.expander(
                f"Orders for {day_label} (Total: {current_orders})",
                expanded=st.session_state[expander_key],
            ):
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

            # Daily calculations
            profit_after_ads = day_profit - ad_spend
            profit_after_ads_gbp = profit_after_ads * (fx_rate if fx_rate else 0.0)
            percent_profit = (
                (day_profit - ad_spend) / day_sales * 100 if day_sales > 0 else 0.0
            )

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

        # Build DataFrame
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
    # ---------------------- Tab 2: Bulk Import ---------------------- #
    with tabs[1]:
        st.subheader("📥 Bulk import daily data (JSON or CSV)")

        # --- Styling fixes: visible browse button + readable filename + button color ---
        st.markdown(
            """
            <style>
            .uploadedFileName, .stFileUploader label {
                color: #111 !important;
                font-weight: 600 !important;
            }
            .stFileUploader label div[data-testid="stFileUploaderDropzone"] {
                border: 2px dashed #9ca3af !important;
                padding: 1.2rem !important;
                background-color: #f9fafb !important;
            }
            .stFileUploader label div[data-testid="stFileUploaderDropzone"]::before {
                opacity: 1 !important;
            }
            .stFileUploader label span {
                background-color: #2563eb !important;
                color: #ffffff !important;
                font-weight: 600 !important;
                padding: 0.35rem 0.9rem !important;
                border-radius: 6px !important;
                border: none !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
**JSON example:**

{
  "2026-01-08": {
    "ad_spend": 64,
    "visitors": 120,
    "orders": [...]
  }
}

**CSV example:**

date,order_index,sales,profit,ad_spend,visitors
2026-01-08,1,87.48,26.98,64,120
"""
        )

        st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)

        # --- File uploader ---
        uploaded_bulk = st.file_uploader(
            "Upload bulk data file",
            type=["json", "csv"],
            key="bulk_import_uploader",
        )

        # Persist file across reruns
        if uploaded_bulk is not None:
            st.session_state["uploaded_bulk_file"] = uploaded_bulk

        file_obj = st.session_state.get("uploaded_bulk_file", None)

        if file_obj:
            file_name = file_obj.name.lower()
            st.write(f"**File loaded:** {file_obj.name}")

            # ---------------------- JSON IMPORT ---------------------- #
            if file_name.endswith(".json"):

                if st.button("Preview JSON data"):
                    try:
                        raw_bytes = file_obj.getvalue()
                        data = json.loads(raw_bytes.decode("utf-8"))

                        if not isinstance(data, dict):
                            st.error("JSON must be an object with dates as keys.")
                        else:
                            st.session_state["json_preview_raw"] = data
                            st.success("Preview generated successfully.")

                    except Exception as e:
                        st.error(f"❌ Could not parse JSON: {e}")

                # Show preview panel
                if "json_preview_raw" in st.session_state:
                    st.markdown("### 🔍 Preview of parsed JSON")

                    raw_data = st.session_state["json_preview_raw"]

                    for date_key, day_data in raw_data.items():
                        with st.expander(f"{date_key} — {len(day_data.get('orders', []))} orders"):
                            st.json(day_data)

                    # Validation
                    st.markdown("### 🧪 Validation report")
                    validation_messages = []

                    for date_key, day_data in raw_data.items():
                        if not isinstance(day_data, dict):
                            validation_messages.append(f"❌ {date_key} is not a valid object.")
                            continue

                        required_fields = ["ad_spend", "visitors", "orders"]
                        missing = [f for f in required_fields if f not in day_data]

                        if missing:
                            validation_messages.append(
                                f"⚠️ {date_key} missing fields: {', '.join(missing)}"
                            )

                        if "orders" in day_data and not isinstance(day_data["orders"], list):
                            validation_messages.append(
                                f"❌ {date_key} orders must be a list."
                            )

                    if validation_messages:
                        for msg in validation_messages:
                            st.warning(msg)
                    else:
                        st.success("All dates validated successfully.")

                # Import button
                if st.button("Import JSON data"):
                    try:
                        raw_data = st.session_state.get("json_preview_raw", None)
                        if not raw_data:
                            st.error("❌ Please generate a preview before importing.")
                        else:
                            total_days = len(raw_data)
                            total_orders = sum(
                                len(v.get("orders", []))
                                for v in raw_data.values()
                                if isinstance(v, dict)
                            )

                            # Convert raw_data into structured list
                            day_data_list = []
                            for date_key, day_info in raw_data.items():
                                try:
                                    day_date = pd.to_datetime(date_key).date()
                                except Exception:
                                    continue

                                orders = day_info.get("orders", [])
                                orders_clean = []
                                for o in orders:
                                    if isinstance(o, dict):
                                        orders_clean.append(
                                            {
                                                "sales": float(o.get("sales", 0.0) or 0.0),
                                                "profit": float(o.get("profit", 0.0) or 0.0),
                                            }
                                        )

                                day_data_list.append(
                                    {
                                        "date": day_date,
                                        "ad_spend": float(day_info.get("ad_spend", 0.0)),
                                        "visitors": int(day_info.get("visitors", 1)),
                                        "orders": orders_clean,
                                    }
                                )

                            populate_from_structured_data(day_data_list)

                            st.success(
                                f"✅ Imported {total_days} days and {total_orders} orders."
                            )

                    except Exception as e:
                        st.error(f"❌ Unexpected error while importing JSON: {e}")

            # ---------------------- CSV IMPORT ---------------------- #
            elif file_name.endswith(".csv"):

                if st.button("Preview CSV data"):
                    try:
                        raw_bytes = file_obj.getvalue()
                        df_test = pd.read_csv(pd.io.common.BytesIO(raw_bytes))
                        st.session_state["csv_preview"] = df_test
                        st.success("Preview generated successfully.")
                    except Exception as e:
                        st.error(f"❌ Could not read CSV: {e}")

                if "csv_preview" in st.session_state:
                    st.markdown("### 🔍 Preview of CSV")
                    st.dataframe(st.session_state["csv_preview"], use_container_width=True)

                    st.markdown("### 🧪 Validation report")
                    required_cols = {
                        "date",
                        "order_index",
                        "sales",
                        "profit",
                        "ad_spend",
                        "visitors",
                    }
                    missing_cols = required_cols - set(st.session_state["csv_preview"].columns)

                    if missing_cols:
                        st.error(f"❌ Missing columns: {', '.join(missing_cols)}")
                    else:
                        st.success("All required columns present.")

                if st.button("Import CSV data"):
                    try:
                        df_test = st.session_state.get("csv_preview", None)
                        if df_test is None:
                            st.error("❌ Please generate a preview before importing.")
                        else:
                            total_days = df_test["date"].nunique()
                            total_orders = len(df_test)

                            parse_csv_bulk(pd.io.common.BytesIO(file_obj.getvalue()))

                            st.success(
                                f"✅ Imported {total_days} days and {total_orders} orders."
                            )

                    except Exception as e:
                        st.error(f"❌ Could not import CSV: {e}")

            else:
                st.warning("⚠️ Unsupported file type. Please upload a .json or .csv file.")
        else:
            st.info("Upload a JSON or CSV file to begin bulk import.")

    # ---------------------- Tab 3: KPIs ---------------------- #
    with tabs[2]:
        st.subheader("📊 KPIs")

        df = st.session_state.get("daily_df", pd.DataFrame())

        if df.empty:
            st.info("No data yet. Fill in Inputs or Bulk Import.")
        else:
            total_sales = float(df["Sales ($)"].sum())
            total_profit = float(df["Profit ($)"].sum())
            total_ad_spend = float(df["Ad Spend ($)"].sum())
            total_profit_after_ads = float(df["Profit After Ads ($)"].sum())
            total_profit_after_ads_gbp = float(df["Profit After Ads (£)"].sum())

            overall_profit_percent = (
                (total_profit - total_ad_spend) / total_sales * 100
                if total_sales > 0
                else 0.0
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
                st.metric("Overall profit %", f"{overall_profit_percent:,.2f}%")
            with c7:
                st.metric("ROAS", f"{roas:,.2f}x")

    # ---------------------- Tab 4: Summaries ---------------------- #
    with tabs[3]:
        st.subheader("📈 Summaries (weekly, monthly, yearly)")

        df = st.session_state.get("daily_df", pd.DataFrame())

        if df.empty:
            st.info("No data yet.")
        else:
            df_summary = df.copy()
            df_summary["Date"] = pd.to_datetime(df_summary["Date"])

            # Weekly summary
            st.markdown("### Weekly summary")
            weekly = (
                df_summary.groupby(
                    df_summary["Date"].dt.to_period("W").apply(lambda r: r.start_time.date())
                )
                .agg(
                    {
                        "Sales ($)": "sum",
                        "Profit ($)": "sum",
                        "Ad Spend ($)": "sum",
                        "Profit After Ads ($)": "sum",
                        "Profit After Ads (£)": "sum",
                        "Orders": "sum",
                        "Visitors": "sum",
                    }
                )
                .reset_index()
                .rename(columns={"Date": "Week Start"})
            )
            st.dataframe(weekly, use_container_width=True)

            st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)

            # Monthly summary
            st.markdown("### Monthly summary")
            monthly = (
                df_summary.groupby(df_summary["Date"].dt.to_period("M"))
                .agg(
                    {
                        "Sales ($)": "sum",
                        "Profit ($)": "sum",
                        "Ad Spend ($)": "sum",
                        "Profit After Ads ($)": "sum",
                        "Profit After Ads (£)": "sum",
                        "Orders": "sum",
                        "Visitors": "sum",
                    }
                )
                .reset_index()
            )
            monthly["Date"] = monthly["Date"].astype(str)
            st.dataframe(monthly, use_container_width=True)

            st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)

            # Yearly summary
            st.markdown("### Yearly summary")
            yearly = (
                df_summary.groupby(df_summary["Date"].dt.year)
                .agg(
                    {
                        "Sales ($)": "sum",
                        "Profit ($)": "sum",
                        "Ad Spend ($)": "sum",
                        "Profit After Ads ($)": "sum",
                        "Profit After Ads (£)": "sum",
                        "Orders": "sum",
                        "Visitors": "sum",
                    }
                )
                .reset_index()
                .rename(columns={"Date": "Year"})
            )
            st.dataframe(yearly, use_container_width=True)
    # ---------------------- Tab 5: Export ---------------------- #
    with tabs[4]:
        st.subheader("📤 Export data")

        df = st.session_state.get("daily_df", pd.DataFrame())

        if df.empty:
            st.info("No data available to export.")
        else:
            st.markdown("Download your daily performance data as CSV.")

            csv_data = df.to_csv(index=False).encode("utf-8")

            st.download_button(
                label="Download CSV",
                data=csv_data,
                file_name="curata_daily_performance.csv",
                mime="text/csv",
                type="primary",
            )

        st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)

        st.markdown("### Export session state (JSON)")

        session_json = json.dumps(export_session_state_dict(), indent=2)
        st.download_button(
            label="Download session JSON",
            data=session_json,
            file_name="curata_session_backup.json",
            mime="application/json",
            type="primary",
        )

    # ---------------------- Tab 6: Session JSON ---------------------- #
    with tabs[5]:
        st.subheader("🧾 Session JSON (live view)")

        session_data = export_session_state_dict()
        st.json(session_data)

        st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)

        st.markdown("### Restore session from uploaded JSON")

        uploaded_session = st.file_uploader(
            "Upload session JSON",
            type=["json"],
            key="session_restore_uploader",
        )

        if uploaded_session is not None:
            if st.button("Restore session from uploaded file"):
                load_session_from_uploaded_json(uploaded_session)

    # ---------------------- Tab 7: Session Controls ---------------------- #
    with tabs[6]:
        st.subheader("🛠️ Session controls")

        st.markdown("Use these tools to manage your dashboard session.")

        col1, col2 = st.columns(2)

        with col1:
            if st.button("💾 Save session to server"):
                save_session_to_file()

        with col2:
            if st.button("📂 Load session from server"):
                load_session_from_file()

        st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)

        if st.button("🧹 Reset session state"):
            reset_session_state()
    # ---------------------- Tab 8: Summary Charts ---------------------- #
    with tabs[7]:
        st.subheader("📊 Summary charts")

        df = st.session_state.get("daily_df", pd.DataFrame())

        if df.empty:
            st.info("No data yet. Fill in Inputs or Bulk Import.")
        else:
            df_chart = df.copy()
            df_chart["Date"] = pd.to_datetime(df_chart["Date"])

            st.markdown("### Sales ($) over time")
            fig_sales = px.line(
                df_chart,
                x="Date",
                y="Sales ($)",
                markers=True,
                title="Daily Sales ($)",
                color_discrete_sequence=["#2563eb"],
            )
            st.plotly_chart(fig_sales, use_container_width=True)

            st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)

            st.markdown("### Profit ($) over time")
            fig_profit = px.line(
                df_chart,
                x="Date",
                y="Profit ($)",
                markers=True,
                title="Daily Profit ($)",
                color_discrete_sequence=["#2563eb"],
            )
            st.plotly_chart(fig_profit, use_container_width=True)

            st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)

            st.markdown("### Profit After Ads (£) over time")
            fig_profit_ads = px.line(
                df_chart,
                x="Date",
                y="Profit After Ads (£)",
                markers=True,
                title="Daily Profit After Ads (£)",
                color_discrete_sequence=["#2563eb"],
            )
            st.plotly_chart(fig_profit_ads, use_container_width=True)

            st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)

            st.markdown("### Orders vs Visitors")
            fig_orders_visitors = px.bar(
                df_chart,
                x="Date",
                y=["Orders", "Visitors"],
                barmode="group",
                title="Orders vs Visitors",
                color_discrete_sequence=["#2563eb", "#4b5563"],
            )
            st.plotly_chart(fig_orders_visitors, use_container_width=True)

# ============================================================
#  END OF FILE — Curata Dashboard (Rebuilt & Polished)
# ============================================================
