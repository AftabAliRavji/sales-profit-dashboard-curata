import streamlit as st
import pandas as pd
from datetime import date, timedelta
import json
import requests
import plotly.express as px

from supabase_client import (
    load_session_from_supabase,
    save_session_to_supabase,
    load_global_state,  # ← now valid again
    save_global_state,
    get_supabase,
)


# ============================================================
#  Curata Dashboard — Core Logic (Rebuilt & Polished)
#  Supabase-integrated version (login handled in app.py)
# ============================================================

# ---------------------- Auth state init ---------------------- #
def init_auth_state():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if "user_id" not in st.session_state:
        st.session_state["user_id"] = None


# --------------------- timestamp helpers -------------------- #
from datetime import datetime, timezone


def pretty_time(ts):
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "")).replace(tzinfo=timezone.utc)
        diff = datetime.now(timezone.utc) - dt
        minutes = int(diff.total_seconds() // 60)

        if minutes < 1:
            return "just now"
        if minutes == 1:
            return "1 minute ago"
        if minutes < 60:
            return f"{minutes} minutes ago"
        hours = minutes // 60
        if hours == 1:
            return "1 hour ago"
        return f"{hours} hours ago"
    except:
        return ts


# ---------------------- Live FX rate ---------------------- #
@st.cache_data(ttl=60 * 60)
def fetch_live_fx_rate():
    """
    Fetches USD→GBP FX rate from a stable, free, reliable API.
    """
    url = "https://open.er-api.com/v6/latest/USD"
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
        # skip auth/meta flags
        if k in ["authenticated", "user_id", "session_restored"]:
            continue
        if (
                k.startswith("orders_day_")
                or k.startswith("day_")
                or k.startswith("ad_spend_day_")
                or k.startswith("expander_open_day_")
                or k
                in [
            "days",
            "start_date",
            "fx_rate",
            "default_ad_spend",
            "visitors_per_day",
            "daily_df",
            "import_start_date",
            "import_days",
            "import_visitors_per_day",
            "import_sync",
            "uploaded_bulk_file",
            "json_preview_raw",
            "csv_preview",
        ]
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


def apply_session_dict(data: dict):
    """
    Apply a session dict (from Supabase or uploaded JSON) into st.session_state,
    safely handling dates and skipping auth flags.
    """
    if not isinstance(data, dict):
        return

    for k, v in data.items():
        if k in ["authenticated", "user_id", "session_restored"]:
            continue

        if k == "start_date":
            try:
                st.session_state[k] = pd.to_datetime(v).date()
            except Exception:
                st.session_state[k] = v
        else:
            st.session_state[k] = v


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
        apply_session_dict(data)
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
    if (
            "start_date" not in st.session_state
            and "import_start_date" not in st.session_state
    ):
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
    Populates import_* keys and per‑day/per‑order keys.
    """

    if not day_data_list:
        st.warning("No valid data found in uploaded file.")
        return

    # Sort by date
    day_data_list = sorted(day_data_list, key=lambda d: d["date"])

    # -----------------------------
    # IMPORT LAYER
    # -----------------------------
    st.session_state["import_start_date"] = day_data_list[0]["date"]
    st.session_state["imported_days_count"] = len(day_data_list)

    imported_days = []
    imported_visitors = []

    # Clear old dynamic state
    clear_day_state()

    # Populate per‑day and per‑order keys
    for idx, day_info in enumerate(day_data_list):
        day_date = day_info["date"]
        ad_spend = float(day_info.get("ad_spend", 0.0) or 0.0)
        visitors = int(day_info.get("visitors", 1) or 1)
        orders = day_info.get("orders", [])

        imported_days.append(day_date)
        imported_visitors.append(visitors)

        st.session_state[f"ad_spend_day_{idx}"] = ad_spend
        st.session_state[f"orders_day_{idx}"] = max(1, len(orders))

        num_orders = st.session_state[f"orders_day_{idx}"]
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

    # Store import lists
    st.session_state["imported_days"] = imported_days
    st.session_state["imported_visitors"] = imported_visitors

    # Signal UI to sync on next render
    st.session_state["import_sync"] = True

    st.success("Bulk data imported successfully.")




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


# ============================================================
#  Main app — header, sidebar, tabs, and Tab 1 (Inputs)
# ============================================================


def main_app():
    # Debug line to confirm user_id
    st.write("Logged in as:", st.session_state.get("user_id"))

    init_default_state()

    # Load GLOBAL state on first run after login
    if (
            st.session_state.get("authenticated")
            and "session_restored" not in st.session_state
    ):
        loaded = load_global_state()
        if loaded:
            apply_session_dict(loaded["session_json"])
            st.session_state["last_updated"] = loaded["last_updated"]
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
        /* Make the uploader label look like plain text instead of a button */
        .stFileUploader label {
            background: none !important;
            border: none !important;
            padding: 0 !important;
            margin-bottom: 0.4rem !important;
            box-shadow: none !important;
            cursor: default !important;
            font-size: 1rem !important;
            font-weight: 600 !important;
            color: #374151 !important; /* slate-700 */
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
    st.sidebar.markdown(
        f"**Logged in as:** {st.session_state.get('user_id', 'Unknown')}"
    )
    # Show last updated timestamp
    if "last_updated" in st.session_state and st.session_state["last_updated"]:
        pretty = pretty_time(st.session_state["last_updated"])
        st.sidebar.markdown(f"**Last updated:** {pretty}")

    if st.sidebar.button("Refresh FX rate (USD → GBP)"):
        new_rate = fetch_live_fx_rate()
        if new_rate is not None:
            st.session_state["fx_rate"] = new_rate
            st.sidebar.success(f"Updated FX rate: {new_rate:.4f}")
        else:
            st.sidebar.warning("Could not fetch live FX rate. Keeping existing value.")

    # --- FX rate display box in sidebar ---
    fx_rate_display = st.session_state.get("fx_rate", 0.0)

    st.sidebar.markdown(
        f"""
        <div style="
            margin-top: 0.8rem;
            padding: 0.75rem 1rem;
            background-color: #eef2ff;
            border-radius: 8px;
            border: 1px solid #c7d2fe;
            font-weight: 600;
            font-size: 1rem;
            color: #1e3a8a;
        ">
            💱 FX rate:<br>
            <span style="color: #2563eb;">1 USD = {fx_rate_display:.4f} GBP</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Sidebar logout (Option B)
    if st.sidebar.button("Log out"):
        if st.session_state.get("authenticated"):
            session_dict = export_session_state_dict()
            save_global_state(session_dict)

        st.session_state["authenticated"] = False
        st.session_state["user_id"] = None
        st.session_state.pop("session_restored", None)
        st.rerun()

    # ---------------------- Tabs ---------------------- #
    tabs = st.tabs(
        [
            "Inputs",
            "Bulk Import",
            "KPIs",
            "Summaries",
            "Export",
            "Session JSON",
            "Summary Charts",
            "Admin",  # 👈 Add this line
        ]
    )

    daily_rows = []
    # ---------------------- IMPORT SYNC (must run BEFORE widgets) ---------------------- #
    if st.session_state.get("import_sync"):
        # Ensure all required import keys exist before syncing
        if (
                "import_start_date" in st.session_state
                and "imported_days_count" in st.session_state
                and "imported_visitors" in st.session_state
        ):
            st.session_state["start_date"] = st.session_state["import_start_date"]
            st.session_state["days"] = st.session_state["imported_days_count"]

            # 🔥 FIX: visitors_per_day must be a SINGLE NUMBER, not a list
            imported_visitors = st.session_state["imported_visitors"]
            if isinstance(imported_visitors, list) and len(imported_visitors) > 0:
                st.session_state["visitors_per_day"] = imported_visitors[0]
            else:
                st.session_state["visitors_per_day"] = 1

            st.session_state["import_sync"] = False
            st.rerun()
        else:
            # Keys missing → disable sync safely
            st.session_state["import_sync"] = False

    # ---------------------- VISITORS PER DAY NORMALISER ---------------------- #
    raw_visitors = st.session_state.get("visitors_per_day", 1)

    if isinstance(raw_visitors, list):
        # If it's a list (from old state/import/whatever), normalise to first element
        st.session_state["visitors_per_day"] = raw_visitors[0] if raw_visitors else 1
    elif not isinstance(raw_visitors, (int, float)):
        # Any other weird type → reset to 1
        st.session_state["visitors_per_day"] = 1

    # ---------------------- Tab 1: Inputs ---------------------- #
    with tabs[0]:
        st.subheader("📥 Inputs")

        # Show success message after rerun
        if st.session_state.get("import_success"):
            st.success("Import complete! 🎉")
            st.session_state["import_success"] = False

        # ---------------------- INITIALISE DYNAMIC DAYS LIST ---------------------- #
        if "manual_days" not in st.session_state:
            st.session_state["manual_days"] = []

        # ---------------------- GLOBAL INPUTS ---------------------- #
        col_a, col_b, col_c, col_d = st.columns([1, 1, 1, 1])

        with col_a:
            start_date = st.date_input("Select start date", key="start_date")

        with col_b:
            fx_rate = st.number_input(
                "FX rate (USD → GBP)",
                min_value=0.0,
                step=0.0001,
                key="fx_rate",
            )

        with col_c:
            visitors_per_day = st.number_input(
                "Visitors per day",
                min_value=1,
                step=1,
                key="visitors_per_day",
            )

        with col_d:
            default_ad_spend = st.number_input(
                "Default ad spend ($) for all days",
                min_value=0.0,
                step=1.0,
                key="default_ad_spend",
            )

        st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)

        # ---------------------- ADD DAY BUTTON ---------------------- #
        if st.button("➕ Add Day"):
            st.session_state["manual_days"].append(
                {
                    "date": None,
                    "ad_spend": st.session_state.get("default_ad_spend", 0.0),
                    "orders": 1,
                }
            )
            st.rerun()

        # ---------------------- RENDER ALL DAYS ---------------------- #
        daily_rows = []

        for day_index, day in enumerate(st.session_state["manual_days"]):

            # Initialise order state
            orders_key = f"orders_day_{day_index}"
            if orders_key not in st.session_state:
                st.session_state[orders_key] = day.get("orders", 1)

            # Day date
            default_date = (
                day["date"]
                if day["date"] is not None
                else start_date + timedelta(days=day_index)
            )

            day_date = st.date_input(
                f"Date for Day {day_index + 1}",
                value=default_date,
                key=f"date_{day_index}",
            )
            st.session_state["manual_days"][day_index]["date"] = day_date

            st.markdown(f"### Day {day_index + 1}: {day_date.strftime('%A — %d %b %Y')}")

            # Ad spend
            ad_spend_key = f"ad_spend_day_{day_index}"
            ad_spend = st.number_input(
                f"Ad spend ($) for Day {day_index + 1}",
                min_value=0.0,
                step=1.0,
                value=day.get("ad_spend", st.session_state.get("default_ad_spend", 0.0)),
                key=ad_spend_key,
            )
            st.session_state["manual_days"][day_index]["ad_spend"] = ad_spend

            # Orders section
            current_orders = st.session_state[orders_key]

            with st.expander(f"Orders for Day {day_index + 1} (Total: {current_orders})"):

                c1, c2, _ = st.columns([1, 1, 1])

                with c1:
                    if st.button(f"➕ Add order (Day {day_index + 1})"):
                        st.session_state[orders_key] += 1
                        st.rerun()

                with c2:
                    if st.button(f"➖ Remove last order (Day {day_index + 1})"):
                        if st.session_state[orders_key] > 1:
                            st.session_state[orders_key] -= 1
                            st.rerun()

                day_sales = 0.0
                day_profit = 0.0

                # Render each order
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

            # Calculations
            profit_after_ads = day_profit - ad_spend
            profit_after_ads_gbp = profit_after_ads * (fx_rate if fx_rate else 0.0)
            percent_profit = (
                (day_profit - ad_spend) / day_sales * 100 if day_sales > 0 else 0.0
            )

            visitors = st.session_state.get("visitors_per_day", 1)

            daily_rows.append(
                {
                    "Date": day_date,
                    "Sales ($)": round(day_sales, 2),
                    "Profit ($)": round(day_profit, 2),
                    "Ad Spend ($)": round(ad_spend, 2),
                    "Profit After Ads ($)": round(profit_after_ads, 2),
                    "Profit After Ads (£)": round(profit_after_ads_gbp, 2),
                    "Profit %": round(percent_profit, 2),
                    "Orders": current_orders,
                    "Visitors": visitors,
                }
            )

        # ---------------------- BUILD DATAFRAME ---------------------- #
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

        # --- Styling fixes ---
        st.markdown(
            """
        <style>
        .stFileUploader label { background: none !important; border: none !important; padding: 0 !important; margin-bottom: 0.4rem !important; box-shadow: none !important; cursor: default !important; font-size: 1rem !important; font-weight: 700 !important; color: #ffffff !important; }
        .stFileUploader label div[data-testid="stFileUploaderDropzone"] {
            border: 2px dashed #9ca3af !important;
            padding: 1.2rem !important;
            background-color: #f9fafb !important;
        }
        .stFileUploader label div[data-testid="stFileUploaderDropzone"]::before {
            opacity: 1 !important;
        }
        .stFileUploader span button {
            visibility: visible !important;
            opacity: 1 !important;
            display: inline-block !important;
            background-color: #2563eb !important;
            color: #ffffff !important;
            font-weight: 600 !important;
            padding: 0.35rem 0.9rem !important;
            border-radius: 6px !important;
            border: none !important;
        }
        div[data-testid="stFileUploader"] > div > div > span {
            color: #ffffff !important;
            font-weight: 700 !important;
            font-size: 1rem !important;
        }
        div[data-testid="stFileUploader"] > div > div:nth-of-type(2) {
            display: none !important;
        }
        div[data-testid="stFileUploaderFileName"] {
            color: #ffffff !important;
            font-weight: 700 !important;
            font-size: 1rem !important;
        }
        div.stFileUploaderFileData small {
            color: #ffffff !important;
            font-weight: 500 !important;
            font-size: 0.9rem !important;
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
            "Upload bulk data file", type=["json", "csv"], key="bulk_import_uploader"
        )

        # Store file in session
        if uploaded_bulk is not None:
            st.session_state["uploaded_bulk_file"] = uploaded_bulk
        else:
            st.session_state["uploaded_bulk_file"] = None

        file_obj = st.session_state.get("uploaded_bulk_file", None)

        # ---------------------- RESET PREVIEW WHEN FILE CLEARED ---------------------- #
        if file_obj is None:
            st.session_state["json_preview_raw"] = None
            st.session_state["json_preview_triggered"] = False
            st.session_state["parsed_structured_data"] = None
            st.session_state["csv_preview"] = None

        # If file exists, show name + size
        if file_obj:
            file_name = file_obj.name.lower()
            file_size_kb = round(len(file_obj.getvalue()) / 1024, 1)

            st.markdown(
                f"""
            <div style="margin-top: 0.4rem; font-weight: 700; color: #ffffff;">
                {file_obj.name} &nbsp; <span style="font-weight: 500;">{file_size_kb}KB</span>
            </div>
            """,
                unsafe_allow_html=True,
            )

            # ---------------------- JSON IMPORT ---------------------- #
            if file_name.endswith(".json"):

                # Preview button
                if st.button("Preview JSON data"):
                    try:
                        raw_bytes = file_obj.getvalue()
                        data = json.loads(raw_bytes.decode("utf-8"))

                        if not isinstance(data, dict):
                            st.error("JSON must be an object with dates as keys.")
                        else:
                            st.session_state["json_preview_raw"] = data
                            st.session_state["json_preview_triggered"] = True
                            st.success("Preview generated successfully.")
                    except Exception as e:
                        st.error(f"❌ Could not parse JSON: {e}")

                # Show preview
                if st.session_state.get("json_preview_triggered") and st.session_state.get("json_preview_raw"):
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
                            validation_messages.append(f"⚠️ {date_key} missing fields: {', '.join(missing)}")

                        if "orders" in day_data and not isinstance(day_data["orders"], list):
                            validation_messages.append(f"❌ {date_key} orders must be a list.")

                    if validation_messages:
                        for msg in validation_messages:
                            st.warning(msg)
                    else:
                        st.success("All dates validated successfully.")

                # ---------------------- IMPORT BUTTON (FIXED) ---------------------- #
                if st.button("📥 Import JSON data"):
                    raw_data = st.session_state.get("json_preview_raw", None)

                    if not raw_data:
                        st.error("❌ Please generate a preview before importing.")
                    else:
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
                        st.session_state["import_success"] = True
                        st.rerun()

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

                if st.session_state.get("csv_preview") is not None:
                    st.markdown("### 🔍 Preview of CSV")
                    st.dataframe(st.session_state["csv_preview"], use_container_width=True)

                    st.markdown("### 🧪 Validation report")
                    required_cols = {"date", "order_index", "sales", "profit", "ad_spend", "visitors"}
                    missing_cols = required_cols - set(st.session_state["csv_preview"].columns)

                    if missing_cols:
                        st.error(f"❌ Missing columns: {', '.join(missing_cols)}")
                    else:
                        st.success("All required columns present.")

                # ---------------------- IMPORT CSV BUTTON ---------------------- #
                if st.button("📥 Import CSV data"):
                    df_test = st.session_state.get("csv_preview", None)

                    if df_test is None:
                        st.error("❌ Please generate a preview before importing.")
                    else:
                        parse_csv_bulk(pd.io.common.BytesIO(file_obj.getvalue()))
                        st.session_state["import_success"] = True
                        st.rerun()

            else:
                st.warning("⚠️ Unsupported file type. Please upload a .json or .csv file.")

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
            st.session_state["profit_after_spend"] = total_profit_after_ads_gbp

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
                    df_summary["Date"]
                    .dt.to_period("W")
                    .apply(lambda r: r.start_time.date())
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

        session_json = json.dumps(export_session_state_dict(), indent=2, default=str)

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

    # ---------------------- Tab 7: Summary Charts ---------------------- #
    with tabs[6]:
        st.subheader("📊 Summary charts")

        df = st.session_state.get("daily_df", pd.DataFrame())
        fx_rate = st.session_state.get("fx_rate", 0.0)

        # ============================
        # Chart 1 — Daily Sales & Profit ($)
        # ============================

        if not df.empty:
            df_daily = df.copy()
            df_daily["Date"] = pd.to_datetime(df_daily["Date"])

            fig_daily = px.bar(
                df_daily,
                x="Date",
                y=["Sales ($)", "Profit ($)"],
                barmode="group",
                title="Daily Sales & Profit ($)",
                color_discrete_map={"Sales ($)": "#2563eb", "Profit ($)": "#16a34a"},
            )

            fig_daily.update_traces(texttemplate="%{y:.2f}", textposition="outside")
            fig_daily.update_layout(
                xaxis_title="Date", yaxis_title="Amount ($)", bargap=0.25, height=450
            )

            st.plotly_chart(fig_daily, use_container_width=True)
        else:
            st.info("No data available to generate daily sales/profit chart.")

        # ============================
        # Chart 2 — Daily Profit After Ads (£)
        # ============================

        if not df.empty and fx_rate:
            df_daily_gbp = df.copy()
            df_daily_gbp["Profit After Ads (£)"] = (
                    df_daily_gbp["Profit After Ads ($)"] * fx_rate
            )

            fig2 = px.bar(
                df_daily_gbp,
                x="Date",
                y="Profit After Ads (£)",
                text="Profit After Ads (£)",
                color_discrete_sequence=["#7c3aed"],
            )

            fig2.update_traces(texttemplate="%{text:.2f}", textposition="outside")
            fig2.update_layout(
                title="Daily Profit After Ads (£)",
                xaxis_title="Date",
                yaxis_title="Profit After Ads (£)",
                bargap=0.3,
                height=450,
            )

            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No data available or FX rate missing for GBP chart.")

        # ============================
        # Orders vs Visitors (Grouped Bar Chart)
        # ============================

        if not df.empty:
            df_chart = df.copy()
            df_chart["Date"] = pd.to_datetime(df_chart["Date"])

            st.markdown("### Orders vs Visitors")

            fig_orders_visitors = px.bar(
                df_chart,
                x="Date",
                y=["Orders", "Visitors"],
                barmode="group",
                title="Orders vs Visitors",
                color_discrete_sequence=["#2563eb", "#4b5563"],
            )

            fig_orders_visitors.update_traces(
                texttemplate="%{y}", textposition="outside"
            )

            fig_orders_visitors.update_layout(
                xaxis_title="Date", yaxis_title="Count", bargap=0.25, height=450
            )

            st.plotly_chart(fig_orders_visitors, use_container_width=True)

            st.subheader("💸 Withdrawals Over Time")

            try:
                withdrawals = (
                    supabase.table("curata_withdrawals")
                    .select("date, amount")
                    .order("date", desc=False)
                    .execute()
                )

                if withdrawals.data:
                    df_w = pd.DataFrame(withdrawals.data)
                    df_w["date"] = pd.to_datetime(df_w["date"])

                    st.bar_chart(
                        df_w.set_index("date")["amount"],
                        use_container_width=True,
                    )
                else:
                    st.info("No withdrawals recorded yet.")
            except Exception:
                st.error("Could not load withdrawals.")

    # ---------------------- Tab 8: Admin ---------------------- #
    with tabs[7]:
        st.header("Admin Tools")

        supabase = get_supabase()

        # ---------------------- Withdraw KPI Section ---------------------- #

        # ---------------------- Withdraw KPI Section ---------------------- #

        st.markdown("### 💸 Withdrawable Amount (minus Sellvia fees)")

        # 1. Read your existing profit-after-ad-spend value
        profit_after_spend = st.session_state.get("profit_after_spend", 0.0)

        # 2. Calculate Sellvia fee and net withdrawable
        sellvia_fee = profit_after_spend * 0.07
        net_withdrawable = profit_after_spend - sellvia_fee

        # Display full breakdown
        st.markdown(
            f"""
            <div style="
                margin-top: 0.5rem;
                padding: 0.8rem 1rem;
                background-color: #f3f4f6;
                border-radius: 8px;
                border: 1px solid #d1d5db;
                font-weight: 600;
                font-size: 1.05rem;
                color: #111827;
            ">
                <div>💰 <strong>Total Profit After Ad Spend:</strong> £{profit_after_spend:,.2f}</div>
                <div>🧾 <strong>Sellvia Fee (7%):</strong> £{sellvia_fee:,.2f}</div>
                <div>✅ <strong>Net Withdrawable Amount:</strong> <span style="color:#2563eb;">£{net_withdrawable:,.2f}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ---------------------- Load persisted withdrawn amount ---------------------- #
        persisted_withdrawn = 0.0
        try:
            row = (
                supabase.table("curata_global_state")
                .select("withdrawn_amount")
                .eq("id", 1)
                .single()
                .execute()
            )
            persisted_withdrawn = row.data.get("withdrawn_amount", 0.0)
        except Exception:
            pass

        # Input box
        withdrawn = st.number_input(
            "Withdrawn amount (£)",
            min_value=0.0,
            step=1.0,
            value=persisted_withdrawn,
            key="withdrawn_amount",
        )

        # ---------------------- Persist withdrawn amount ---------------------- #
        try:
            supabase.table("curata_global_state").update(
                {"withdrawn_amount": withdrawn}
            ).eq("id", 1).execute()
        except Exception:
            pass

        # Remaining profit after withdrawal (from net withdrawable)
        remaining_profit = net_withdrawable - withdrawn

        st.markdown(
            f"""
            <div style="
                margin-top: 0.8rem;
                padding: 0.8rem 1rem;
                background-color: #ecfdf5;
                border-radius: 8px;
                border: 1px solid #a7f3d0;
                font-weight: 600;
                font-size: 1.1rem;
                color: #065f46;
            ">
                Remaining Profit After Withdrawal:  
                <span style="color:#059669;">£{remaining_profit:,.2f}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ---------------------- Record Withdrawal Event ---------------------- #
        st.markdown("### 📝 Record Withdrawal Event")

        if st.button("Record Withdrawal"):
            try:
                supabase.table("curata_withdrawals").insert(
                    {
                        "date": datetime.date.today().isoformat(),
                        "amount": withdrawn,
                    }
                ).execute()
                st.success("Withdrawal recorded.")
            except Exception as e:
                st.error("Failed to record withdrawal.")

        # ============================
        # VERSION HISTORY
        # ============================
        st.subheader("📜 Version History")
        st.caption("View the last 10 saved versions of the global state.")

        try:
            versions = (
                supabase.table("curata_global_versions")
                .select("version_id, created_at, saved_by, locked")
                .order("created_at", desc=True)
                .limit(10)
                .execute()
            )

            for v in versions.data:
                lock_status = "🔒 Locked" if v.get("locked") else "🔓 Unlocked"
                st.markdown(
                    f"- **Version {v['version_id']}** — {v['created_at']} by `{v['saved_by']}` — {lock_status}"
                )
        except Exception as e:
            st.error("Failed to load version history.")

        st.markdown("---")

        # ============================
        # AUDIT LOG
        # ============================
        st.subheader("🔍 Audit Log")
        st.caption("See who saved what and when.")

        try:
            logs = (
                supabase.table("curata_global_audit")
                .select("timestamp, user_id, action")
                .order("timestamp", desc=True)
                .limit(10)
                .execute()
            )

            for log in logs.data:
                st.markdown(
                    f"- `{log['user_id']}` performed **{log['action']}** at {log['timestamp']}"
                )
        except Exception as e:
            st.error("Failed to load audit log.")

        st.markdown("---")

        # ============================
        # RESTORE LATEST BACKUP
        # ============================
        st.subheader("🧩 Restore Latest Backup")
        st.caption("Restore the most recent JSON backup from Supabase Storage.")

        if st.button("Restore Latest Backup"):
            try:
                files = supabase.storage.from_("curata_backups").list()

                if files:
                    sorted_files = sorted(files, key=lambda f: f["name"], reverse=True)
                    latest = sorted_files[0]["name"]

                    content = supabase.storage.from_("curata_backups").download(latest)
                    restored = json.loads(content)

                    apply_session_dict(restored)
                    st.session_state["restored_from_backup"] = latest
                    st.success(f"Restored from backup: {latest}")
                else:
                    st.warning("No backups found.")
            except Exception as e:
                st.error("Restore failed.")

        st.markdown("---")

        # ============================
        # RESTORE FROM SPECIFIC VERSION
        # ============================
        st.subheader("🗂 Restore From Version")
        st.caption("Pick a version and restore its state.")

        try:
            version_list = (
                supabase.table("curata_global_versions")
                .select("version_id, created_at, locked")
                .order("created_at", desc=True)
                .limit(20)
                .execute()
            )

            version_options = {
                f"Version {v['version_id']} — {v['created_at']} {'🔒' if v.get('locked') else ''}": v[
                    "version_id"
                ]
                for v in version_list.data
            }

            selected_version = st.selectbox(
                "Choose version to restore:", list(version_options.keys())
            )

            if st.button("Restore Selected Version"):
                version_id = version_options[selected_version]

                version_data = (
                    supabase.table("curata_global_versions")
                    .select("session_json")
                    .eq("version_id", version_id)
                    .single()
                    .execute()
                )

                apply_session_dict(version_data.data["session_json"])
                st.success(f"Restored Version {version_id}")
        except Exception as e:
            st.error("Failed to load versions.")

        st.markdown("---")

        # ============================
        # LOCK VERSION
        # ============================
        st.subheader("🔒 Lock Version")
        st.caption("Lock a version to prevent overwrites or deletion.")

        try:
            lock_options = {
                f"Version {v['version_id']} — {v['created_at']}": v["version_id"]
                for v in version_list.data
                if not v.get("locked")
            }

            version_to_lock = st.selectbox(
                "Choose version to lock:", list(lock_options.keys())
            )

            if st.button("Lock Selected Version"):
                version_id = lock_options[version_to_lock]

                supabase.table("curata_global_versions").update({"locked": True}).eq(
                    "version_id", version_id
                ).execute()

                st.success(f"Version {version_id} is now locked.")
        except Exception as e:
            st.error("Failed to lock version.")

        st.markdown("---")

        # ============================
        # DOWNLOAD LATEST BACKUP
        # ============================
        st.subheader("⬇️ Download Latest Backup")
        st.caption("Download the most recent JSON backup file.")

        if st.button("Download Backup"):
            try:
                files = supabase.storage.from_("curata_backups").list()

                if files:
                    sorted_files = sorted(files, key=lambda f: f["name"], reverse=True)
                    latest = sorted_files[0]["name"]

                    content = supabase.storage.from_("curata_backups").download(latest)

                    st.download_button(
                        label="Download Backup JSON",
                        data=content,
                        file_name=latest,
                        mime="application/json",
                    )
                else:
                    st.warning("No backups found.")
            except Exception as e:
                st.error("Download failed.")

    # ---------------------- Auto-save to Supabase ---------------------- #
    # Auto-save after every interaction
    if st.session_state.get("authenticated"):
        session_dict = export_session_state_dict()
        save_global_state(session_dict)
        st.sidebar.success("✅ Global state saved.")

# ============================================================
#  END OF FILE — Curata Dashboard (Supabase-integrated)
#  (Entry point is app.py)
# ============================================================
