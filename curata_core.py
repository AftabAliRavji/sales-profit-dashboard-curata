import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime, timezone
import json
import requests

from curata_db import (
    upsert_daily_row,
    upsert_order_row,
    load_all_daily_rows,
    load_orders_for_day,
    delete_daily_row,
    get_daily_row,
    delete_single_order,
)

from supabase_client import load_global_state, save_global_state

# ============================================================
#  Curata Dashboard — Core Logic (Supabase-native)
# ============================================================

# ---------------------- Auth state init ---------------------- #
def init_auth_state():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if "user_id" not in st.session_state:
        st.session_state["user_id"] = None


# --------------------- timestamp helpers -------------------- #
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


# ---------------------- Session helpers (UI prefs only) ---------------------- #

_UI_PREF_KEYS = [
    "start_date",
    "fx_rate",
    "default_ad_spend",
    "visitors_per_day",
]


def export_session_state_dict():
    """
    Export ONLY UI-level preferences and global knobs.
    Daily data now lives in Supabase and is NOT exported here.
    """
    data = {}
    for k in _UI_PREF_KEYS:
        if k not in st.session_state:
            continue
        v = st.session_state.get(k)
        if isinstance(v, pd.Timestamp):
            data[k] = v.isoformat()
        elif isinstance(v, date):
            data[k] = v.isoformat()
        else:
            data[k] = v
    return data


def apply_session_dict(data: dict):
    """
    Apply a session dict (from Supabase or uploaded JSON) into st.session_state,
    but ONLY for UI-level preferences. Daily data is restored from Supabase.
    """
    if not isinstance(data, dict):
        return

    for k, v in data.items():
        if k not in _UI_PREF_KEYS:
            continue

        if k == "start_date":
            try:
                st.session_state[k] = pd.to_datetime(v).date()
            except Exception:
                st.session_state[k] = v
        else:
            st.session_state[k] = v


def load_session_from_uploaded_json(uploaded_file):
    """
    Legacy/advanced: restore UI prefs from a JSON file.
    Daily data is NOT restored from this; Supabase is the source of truth.
    """
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
        st.success("Session UI preferences restored from uploaded file. Rerunning…")
        st.rerun()
    except Exception as e:
        st.warning(f"Could not apply uploaded session: {e}")


def init_default_state():
    if "start_date" not in st.session_state:
        st.session_state["start_date"] = date.today()
    if "fx_rate" not in st.session_state:
        live_rate = fetch_live_fx_rate()
        st.session_state["fx_rate"] = live_rate if live_rate is not None else 0.79
    if "default_ad_spend" not in st.session_state:
        st.session_state["default_ad_spend"] = 64.0
    if "visitors_per_day" not in st.session_state:
        st.session_state["visitors_per_day"] = 1


# ============================================================
#  Main app — header, sidebar, tabs, and Tab 1 (Inputs)
# ============================================================

def main_app():
    st.write("Logged in as:", st.session_state.get("user_id"))

    init_default_state()

    # Load GLOBAL UI prefs on first run after login
    if st.session_state.get("authenticated") and "session_restored" not in st.session_state:
        loaded = load_global_state()
        if loaded:
            apply_session_dict(loaded["session_json"])
            st.session_state["last_updated"] = loaded["last_updated"]
        st.session_state["session_restored"] = True

    # --- Global CSS, header, sidebar, FX, logout --- (unchanged)
    # ... (keep your existing CSS, header, sidebar, FX box, logout logic here)

    tabs = st.tabs(
        [
            "Inputs",
            "Bulk Import",
            "KPIs",
            "Summaries",
            "Export",
            "Session JSON",
            "Summary Charts",
            "Admin",
            "Migration",
        ]
    )

    # ---------------------- Tab 1: Inputs (Supabase Live Sync) ---------------------- #
    with tabs[0]:
        st.subheader("📥 Inputs")

        if st.session_state.get("import_success"):
            st.success("Import complete! 🎉")
            st.session_state["import_success"] = False

        daily_rows_db = load_all_daily_rows()

        if not daily_rows_db:
            st.info("No daily data found. Add your first day below.")
            st.session_state["days"] = 1
            start_date = st.date_input("Select start date", key="start_date")
            fx_rate = st.number_input("FX rate (USD → GBP)", min_value=0.0, step=0.0001, key="fx_rate")
            visitors_per_day = st.number_input("Visitors per day", min_value=1, step=1, key="visitors_per_day")
            default_ad_spend = st.number_input("Default ad spend ($)", min_value=0.0, step=1.0, key="default_ad_spend")

            if st.button("Create first day"):
                day_date = start_date
                upsert_daily_row(day_date, default_ad_spend, visitors_per_day, 1, 0, 0, 0, 0, 0)
                new_row = get_daily_row(day_date)
                upsert_order_row(new_row["id"], 1, 0, 0)
                st.rerun()

            st.stop()

        start_date = min([pd.to_datetime(r["date"]).date() for r in daily_rows_db])
        st.session_state["start_date"] = start_date
        st.session_state["days"] = len(daily_rows_db)

        col_a, col_b, col_c, col_d = st.columns([1, 1, 1, 1])

        with col_a:
            st.number_input(
                "Number of days",
                min_value=1,
                max_value=31,
                step=1,
                value=len(daily_rows_db),
                key="days",
                disabled=True,
            )

        with col_b:
            st.date_input("Select start date", value=start_date, key="start_date")

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

        daily_rows_display = []

        for day_index, daily_row in enumerate(daily_rows_db):
            day_date = pd.to_datetime(daily_row["date"]).date()
            day_label = day_date.strftime("%A — %d %b %Y")
            day_id = daily_row["id"]

            st.markdown(f"### Day {day_index + 1}: {day_label}")

            ad_spend = st.number_input(
                f"Ad spend ($) for {day_label}",
                min_value=0.0,
                step=1.0,
                value=float(daily_row["ad_spend_usd"]),
                key=f"ad_spend_{day_index}",
            )

            orders_count = st.number_input(
                f"Number of orders for {day_label}",
                min_value=1,
                step=1,
                value=int(daily_row["orders"]),
                key=f"orders_{day_index}",
            )

            order_rows = load_orders_for_day(day_id)

            if len(order_rows) < orders_count:
                for idx in range(len(order_rows) + 1, orders_count + 1):
                    upsert_order_row(day_id, idx, 0, 0)
            elif len(order_rows) > orders_count:
                for idx in range(orders_count + 1, len(order_rows) + 1):
                    delete_single_order(day_id, idx)

            order_rows = load_orders_for_day(day_id)

            with st.expander(f"Orders for {day_label} (Total: {orders_count})", expanded=False):
                day_sales = 0
                day_profit = 0

                for order in order_rows:
                    idx = order["order_index"]

                    col1, col2 = st.columns(2)

                    sales_val = col1.number_input(
                        f"Sales ($) — Order {idx}",
                        min_value=0.0,
                        step=1.0,
                        value=float(order["sales_usd"]),
                        key=f"sales_{day_index}_{idx}",
                    )

                    profit_val = col2.number_input(
                        f"Profit ($) — Order {idx}",
                        min_value=0.0,
                        step=1.0,
                        value=float(order["profit_usd"]),
                        key=f"profit_{day_index}_{idx}",
                    )

                    upsert_order_row(day_id, idx, sales_val, profit_val)

                    day_sales += sales_val
                    day_profit += profit_val

            profit_after_ads = day_profit - ad_spend
            profit_after_ads_gbp = profit_after_ads * fx_rate
            percent_profit = (profit_after_ads / day_sales * 100) if day_sales > 0 else 0

            upsert_daily_row(
                day_date,
                ad_spend,
                visitors_per_day,
                orders_count,
                day_sales,
                day_profit,
                profit_after_ads,
                profit_after_ads_gbp,
                percent_profit,
            )

            daily_rows_display.append(
                {
                    "Date": day_date,
                    "Sales ($)": round(day_sales, 2),
                    "Profit ($)": round(day_profit, 2),
                    "Ad Spend ($)": round(ad_spend, 2),
                    "Profit After Ads ($)": round(profit_after_ads, 2),
                    "Profit After Ads (£)": round(profit_after_ads_gbp, 2),
                    "Profit %": round(percent_profit, 2),
                    "Orders": orders_count,
                    "Visitors": visitors_per_day,
                }
            )

        st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)

        if st.button("➕ Add Day"):
            last_date = max([pd.to_datetime(r["date"]).date() for r in daily_rows_db])
            new_date = last_date + timedelta(days=1)

            upsert_daily_row(
                new_date,
                default_ad_spend,
                visitors_per_day,
                1,
                0,
                0,
                0,
                0,
                0,
            )

            new_row = get_daily_row(new_date)
            upsert_order_row(new_row["id"], 1, 0, 0)

            st.rerun()

        df = pd.DataFrame(daily_rows_display)
        st.session_state["daily_df"] = df  # kept for downstream tabs that still read it
        st.subheader("📅 Daily overview (table)")
        st.dataframe(df, use_container_width=True)

    # ---------------------- Tab 2: Bulk Import (Supabase-backed) ---------------------- #
    with tabs[1]:
        st.subheader("📥 Bulk import daily data (JSON or CSV)")

        # --- Styling fixes (unchanged) ---
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

        # --- Examples (unchanged) ---
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

        # --- File uploader (unchanged) ---
        uploaded_bulk = st.file_uploader(
            "Upload bulk data file", type=["json", "csv"], key="bulk_import_uploader"
        )

        if uploaded_bulk is not None:
            st.session_state["uploaded_bulk_file"] = uploaded_bulk
        else:
            st.session_state["uploaded_bulk_file"] = None

        file_obj = st.session_state.get("uploaded_bulk_file", None)

        # Reset preview when file cleared
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

                # ---------------------- IMPORT JSON BUTTON (Supabase-backed) ---------------------- #
                if st.button("📥 Import JSON data"):
                    raw_data = st.session_state.get("json_preview_raw", None)

                    if not raw_data:
                        st.error("❌ Please generate a preview before importing.")
                    else:
                        fx_rate = st.session_state.get("fx_rate", 0.0)

                        for date_key, day_info in raw_data.items():
                            try:
                                day_date = pd.to_datetime(date_key).date()
                            except Exception:
                                continue

                            ad_spend = float(day_info.get("ad_spend", 0.0))
                            visitors = int(day_info.get("visitors", 1))
                            orders_raw = day_info.get("orders", [])

                            # Clean orders
                            orders = []
                            for o in orders_raw:
                                if isinstance(o, dict):
                                    orders.append({
                                        "sales": float(o.get("sales", 0.0)),
                                        "profit": float(o.get("profit", 0.0)),
                                    })

                            # Delete existing day (cascade deletes orders)
                            delete_daily_row(day_date)

                            # Compute totals
                            total_sales = sum(o["sales"] for o in orders)
                            total_profit = sum(o["profit"] for o in orders)
                            profit_after_ads = total_profit - ad_spend
                            profit_after_ads_gbp = profit_after_ads * fx_rate
                            percent_profit = (profit_after_ads / total_sales * 100) if total_sales > 0 else 0

                            # Insert daily row
                            upsert_daily_row(
                                day_date,
                                ad_spend,
                                visitors,
                                len(orders),
                                total_sales,
                                total_profit,
                                profit_after_ads,
                                profit_after_ads_gbp,
                                percent_profit,
                            )

                            # Fetch day_id
                            daily_row = get_daily_row(day_date)
                            day_id = daily_row["id"]

                            # Insert orders
                            for idx, o in enumerate(orders, start=1):
                                upsert_order_row(day_id, idx, o["sales"], o["profit"])

                        st.success("Bulk import complete. Reloading…")
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

                # ---------------------- IMPORT CSV BUTTON (Supabase-backed) ---------------------- #
                if st.button("📥 Import CSV data"):
                    df_test = st.session_state.get("csv_preview", None)

                    if df_test is None:
                        st.error("❌ Please generate a preview before importing.")
                    else:
                        fx_rate = st.session_state.get("fx_rate", 0.0)

                        df = df_test.copy()
                        df["date"] = pd.to_datetime(df["date"]).dt.date

                        for day_date, group in df.groupby("date"):
                            first = group.iloc[0]
                            ad_spend = float(first.get("ad_spend", 0.0))
                            visitors = int(first.get("visitors", 1))

                            orders = []
                            for _, row in group.sort_values("order_index").iterrows():
                                orders.append({
                                    "sales": float(row["sales"]),
                                    "profit": float(row["profit"]),
                                })

                            # Delete existing day
                            delete_daily_row(day_date)

                            # Compute totals
                            total_sales = sum(o["sales"] for o in orders)
                            total_profit = sum(o["profit"] for o in orders)
                            profit_after_ads = total_profit - ad_spend
                            profit_after_ads_gbp = profit_after_ads * fx_rate
                            percent_profit = (profit_after_ads / total_sales * 100) if total_sales > 0 else 0

                            # Insert daily row
                            upsert_daily_row(
                                day_date,
                                ad_spend,
                                visitors,
                                len(orders),
                                total_sales,
                                total_profit,
                                profit_after_ads,
                                profit_after_ads_gbp,
                                percent_profit,
                            )

                            # Fetch day_id
                            daily_row = get_daily_row(day_date)
                            day_id = daily_row["id"]

                            # Insert orders
                            for idx, o in enumerate(orders, start=1):
                                upsert_order_row(day_id, idx, o["sales"], o["profit"])

                        st.success("Bulk import complete. Reloading…")
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

        # Load fresh data from Supabase instead of relying on session_state
        daily_rows = load_all_daily_rows()

        if not daily_rows:
            st.info("No data available to export.")
        else:
            # Build DataFrame from Supabase rows
            export_rows = []
            for row in daily_rows:
                export_rows.append({
                    "Date": pd.to_datetime(row["date"]).date(),
                    "Sales ($)": float(row["sales_usd"]),
                    "Profit ($)": float(row["profit_usd"]),
                    "Ad Spend ($)": float(row["ad_spend_usd"]),
                    "Profit After Ads ($)": float(row["profit_after_ads_usd"]),
                    "Profit After Ads (£)": float(row["profit_after_ads_gbp"]),
                    "Profit %": float(row["profit_percent"]),
                    "Orders": int(row["orders"]),
                    "Visitors": int(row["visitors"]),
                })

            df_export = pd.DataFrame(export_rows)

            st.markdown("Download your daily performance data as CSV.")

            csv_data = df_export.to_csv(index=False).encode("utf-8")

            st.download_button(
                label="Download CSV",
                data=csv_data,
                file_name="curata_daily_performance.csv",
                mime="text/csv",
                type="primary",
            )

        st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)

        # ============================================================
        # NEW FEATURE: Full Supabase Backup (JSON)
        # ============================================================
        st.markdown("### Download full Supabase backup (JSON)")

        if daily_rows:
            # Build full backup structure
            full_backup = []

            for row in daily_rows:
                day_date = pd.to_datetime(row["date"]).date()
                day_id = row["id"]

                # Load orders for this day
                orders = load_orders_for_day(day_id)

                full_backup.append({
                    "date": day_date.isoformat(),
                    "ad_spend": float(row["ad_spend_usd"]),
                    "visitors": int(row["visitors"]),
                    "orders": [
                        {
                            "order_index": o["order_index"],
                            "sales": float(o["sales_usd"]),
                            "profit": float(o["profit_usd"]),
                        }
                        for o in orders
                    ],
                    "totals": {
                        "sales_usd": float(row["sales_usd"]),
                        "profit_usd": float(row["profit_usd"]),
                        "profit_after_ads_usd": float(row["profit_after_ads_usd"]),
                        "profit_after_ads_gbp": float(row["profit_after_ads_gbp"]),
                        "profit_percent": float(row["profit_percent"]),
                    },
                })

            backup_json = json.dumps(full_backup, indent=2)

            st.download_button(
                label="Download full Supabase backup (JSON)",
                data=backup_json,
                file_name="curata_supabase_backup.json",
                mime="application/json",
                type="primary",
            )
        else:
            st.info("No Supabase data available to export.")

        st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)

        # ============================================================
        # Existing: Export session JSON (unchanged)
        # ============================================================
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

        # ============================================================
        # NEW: Restore from Supabase (Primary Restore Method)
        # ============================================================
        st.markdown("### 🔄 Restore dashboard from Supabase daily data")

        if st.button("Restore from Supabase"):
            daily_rows = load_all_daily_rows()

            if not daily_rows:
                st.warning("No daily data found in Supabase.")
                st.stop()

            # Reset UI state to match Supabase exactly
            start_date = min([pd.to_datetime(r["date"]).date() for r in daily_rows])
            st.session_state["start_date"] = start_date
            st.session_state["days"] = len(daily_rows)

            daily_df_rows = []

            for row in daily_rows:
                day_date = pd.to_datetime(row["date"]).date()
                day_id = row["id"]

                # Load orders
                orders = load_orders_for_day(day_id)

                # Compute day index relative to start_date
                day_index = (day_date - start_date).days

                # Rebuild UI helper keys
                st.session_state[f"orders_{day_index}"] = row["orders"]
                st.session_state[f"ad_spend_{day_index}"] = float(row["ad_spend_usd"])

                # Rebuild order UI keys
                for order in orders:
                    idx = order["order_index"]
                    st.session_state[f"sales_{day_index}_{idx}"] = float(order["sales_usd"])
                    st.session_state[f"profit_{day_index}_{idx}"] = float(order["profit_usd"])

                # Add to DataFrame reconstruction
                daily_df_rows.append({
                    "Date": day_date,
                    "Sales ($)": round(float(row["sales_usd"]), 2),
                    "Profit ($)": round(float(row["profit_usd"]), 2),
                    "Ad Spend ($)": round(float(row["ad_spend_usd"]), 2),
                    "Profit After Ads ($)": round(float(row["profit_after_ads_usd"]), 2),
                    "Profit After Ads (£)": round(float(row["profit_after_ads_gbp"]), 2),
                    "Profit %": round(float(row["profit_percent"]), 2),
                    "Orders": int(row["orders"]),
                    "Visitors": int(row["visitors"]),
                })

            # Rebuild daily_df
            st.session_state["daily_df"] = pd.DataFrame(daily_df_rows)

            st.success("Dashboard restored from Supabase. Reloading…")
            st.rerun()

        st.markdown('<div class="curata-divider"></div>', unsafe_allow_html=True)

        # ============================================================
        # LEGACY: Restore from uploaded JSON (kept because you chose A)
        # ============================================================
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

    # ---------------------- Tab 9: Migration ---------------------- #
    with tabs[8]:
        st.header("🛠 Migration Tool")
        st.caption("Convert old session-state data into the new Supabase schema.")

        st.markdown(
            """
            This tool migrates your **old session-based data** into the new  
            **Supabase-backed daily data + orders** structure.

            - Reads your old session JSON  
            - Extracts days, orders, sales, profit, ad spend  
            - Computes dates using: `start_date + day_index`  
            - Inserts into `curata_daily_data`  
            - Inserts into `curata_daily_orders`  
            - Safe to run once  
            """
        )

        uploaded_old_json = st.file_uploader(
            "Upload OLD session JSON (pre‑Supabase version)",
            type=["json"],
            key="migration_json_uploader",
        )

        if uploaded_old_json is not None:
            if st.button("Run Migration"):
                try:
                    old_data = json.load(uploaded_old_json)
                except Exception:
                    st.error("Invalid JSON file.")
                    st.stop()

                # ----------------------
                # Extract global fields
                # ----------------------
                try:
                    start_date = pd.to_datetime(old_data.get("start_date")).date()
                    days = int(old_data.get("days", 0))
                    visitors_per_day = int(old_data.get("visitors_per_day", 1))
                    fx_rate = float(old_data.get("fx_rate", 0.0))
                    default_ad_spend = float(old_data.get("default_ad_spend", 0.0))
                except Exception as e:
                    st.error(f"Missing or invalid global fields: {e}")
                    st.stop()

                if days <= 0:
                    st.error("No days found in old session JSON.")
                    st.stop()

                # ----------------------
                # MIGRATE EACH DAY
                # ----------------------
                for day_index in range(days):
                    day_date = start_date + timedelta(days=day_index)

                    # Extract ad spend
                    ad_spend = float(
                        old_data.get(f"ad_spend_day_{day_index}", default_ad_spend)
                    )

                    # Extract number of orders
                    orders_count = int(old_data.get(f"orders_day_{day_index}", 0))

                    # Extract orders
                    orders = []
                    for order_index in range(1, orders_count + 1):
                        sales_key = f"day_{day_index}_order_{order_index}_sales"
                        profit_key = f"day_{day_index}_order_{order_index}_profit"

                        sales_val = float(old_data.get(sales_key, 0.0))
                        profit_val = float(old_data.get(profit_key, 0.0))

                        orders.append({
                            "order_index": order_index,
                            "sales": sales_val,
                            "profit": profit_val,
                        })

                    # Compute totals
                    total_sales = sum(o["sales"] for o in orders)
                    total_profit = sum(o["profit"] for o in orders)
                    profit_after_ads = total_profit - ad_spend
                    profit_after_ads_gbp = profit_after_ads * fx_rate
                    percent_profit = (profit_after_ads / total_sales * 100) if total_sales > 0 else 0

                    # Delete existing day (if any)
                    delete_daily_row(day_date)

                    # Insert daily row
                    upsert_daily_row(
                        day_date,
                        ad_spend,
                        visitors_per_day,
                        orders_count,
                        total_sales,
                        total_profit,
                        profit_after_ads,
                        profit_after_ads_gbp,
                        percent_profit,
                    )

                    # Fetch day_id
                    daily_row = get_daily_row(day_date)
                    day_id = daily_row["id"]

                    # Insert orders
                    for o in orders:
                        upsert_order_row(
                            day_id,
                            o["order_index"],
                            o["sales"],
                            o["profit"],
                        )

                st.success("Migration complete! Your data is now stored in Supabase.")
                st.rerun()

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
