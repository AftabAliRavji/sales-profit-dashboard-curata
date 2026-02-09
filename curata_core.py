import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime, timezone
import json
import requests
import plotly.express as px


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
#  Curata Dashboard — Core Logic (Supabase-native, UI Restored)
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


# ---------------------- UI Preference Keys ---------------------- #
_UI_PREF_KEYS = [
    "start_date",
    "fx_rate",
    "default_ad_spend",
    "visitors_per_day",
]


def export_session_state_dict():
    """
    Export ONLY UI-level preferences.
    Daily data is stored in Supabase and not exported here.
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
    Apply UI preferences from Supabase or uploaded JSON.
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
#  Main App — Header, Sidebar, Tabs
# ============================================================

def main_app():
    st.write("Logged in as:", st.session_state.get("user_id"))

    init_default_state()

    # Load global UI prefs once after login
    if st.session_state.get("authenticated") and "session_restored" not in st.session_state:
        loaded = load_global_state()
        if loaded:
            apply_session_dict(loaded["session_json"])
            st.session_state["last_updated"] = loaded["last_updated"]
        st.session_state["session_restored"] = True

    # ---------------------- Header (Light Theme) ---------------------- #
    st.markdown(
        """
        <div style="
            padding: 0.75rem 1rem 0.25rem 1rem;
            background-color: #ffffff;
            border-radius: 6px;
        ">
            <div style="
                font-size: 1.8rem;
                font-weight: 900;
                color: #000000;
                line-height: 1.2;
            ">
                Curata Daily Performance Dashboard
            </div>
            <div style="
                font-size: 1.05rem;
                font-weight: 600;
                color: #333333;
            ">
                Track daily sales, profit, ad spend and margins with quick export and restore options.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div style="border-bottom: 2px solid #d1d5db; margin: 1rem 0 1.25rem 0;"></div>', unsafe_allow_html=True)

    # ---------------------- Sidebar (Collapsible) ---------------------- #
    st.sidebar.markdown(f"**Logged in as:** {st.session_state.get('user_id', 'Unknown')}")

    if "last_updated" in st.session_state and st.session_state["last_updated"]:
        pretty = pretty_time(st.session_state["last_updated"])
        st.sidebar.markdown(f"**Last updated:** {pretty}")

    if st.sidebar.button("Refresh FX rate (USD → GBP)"):
        new_rate = fetch_live_fx_rate()
        if new_rate is not None:
            st.session_state["fx_rate"] = new_rate
            st.sidebar.success(f"Updated FX rate: {new_rate:.4f}")
        else:
            st.sidebar.warning("Could not fetch live FX rate.")

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
            "Admin",
            "Migration",
        ]
    )

    # ---------------------- Visitors Normalization ---------------------- #
    raw_visitors = st.session_state.get("visitors_per_day", 1)

    if isinstance(raw_visitors, list):
        st.session_state["visitors_per_day"] = raw_visitors[0] if raw_visitors else 1
    elif not isinstance(raw_visitors, (int, float)):
        st.session_state["visitors_per_day"] = 1
    # ============================================================
    #  TAB 1 — INPUTS (Supabase-native)
    # ============================================================
    with tabs[0]:
        st.subheader("📥 Inputs")

        # Load all daily rows from Supabase
        daily_rows_db = load_all_daily_rows()

        # If no data exists yet → create first day
        if not daily_rows_db:
            st.info("No daily data found. Add your first day below.")

            start_date = st.date_input("Select start date", key="start_date")
            fx_rate = st.number_input("FX rate (USD → GBP)", min_value=0.0, step=0.0001, key="fx_rate")
            visitors_per_day = st.number_input("Visitors per day", min_value=1, step=1, key="visitors_per_day")
            default_ad_spend = st.number_input("Default ad spend ($)", min_value=0.0, step=1.0, key="default_ad_spend")

            if st.button("Create first day"):
                upsert_daily_row(start_date, default_ad_spend, visitors_per_day, 1, 0, 0, 0, 0, 0)
                new_row = get_daily_row(start_date)
                upsert_order_row(new_row["id"], 1, 0, 0)
                st.rerun()

            st.stop()

        # Existing data found → render editable UI
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

        st.markdown('<div style="border-bottom: 2px solid #d1d5db; margin: 1rem 0;"></div>', unsafe_allow_html=True)

        daily_rows_display = []

        # Loop through each day from Supabase
        for day_index, daily_row in enumerate(daily_rows_db):
            day_date = pd.to_datetime(daily_row["date"]).date()
            day_label = day_date.strftime("%A — %d %b %Y")
            day_id = daily_row["id"]

            st.markdown(f"### Day {day_index + 1}: {day_label}")

            # Editable ad spend
            ad_spend = st.number_input(
                f"Ad spend ($) for {day_label}",
                min_value=0.0,
                step=1.0,
                value=float(daily_row["ad_spend_usd"]),
                key=f"ad_spend_{day_index}",
            )

            # Editable order count
            orders_count = st.number_input(
                f"Number of orders for {day_label}",
                min_value=1,
                step=1,
                value=int(daily_row["orders"]),
                key=f"orders_{day_index}",
            )

            # Load existing orders
            order_rows = load_orders_for_day(day_id)

            # Sync order count with DB
            if len(order_rows) < orders_count:
                for idx in range(len(order_rows) + 1, orders_count + 1):
                    upsert_order_row(day_id, idx, 0, 0)
            elif len(order_rows) > orders_count:
                for idx in range(orders_count + 1, len(order_rows) + 1):
                    delete_single_order(day_id, idx)

            order_rows = load_orders_for_day(day_id)

            # Orders expander
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

            # Recalculate daily totals
            profit_after_ads = day_profit - ad_spend
            profit_after_ads_gbp = profit_after_ads * fx_rate
            percent_profit = (profit_after_ads / day_sales * 100) if day_sales > 0 else 0

            # Update daily row in Supabase
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

        # Add Day button
        st.markdown('<div style="border-bottom: 2px solid #d1d5db; margin: 1rem 0;"></div>', unsafe_allow_html=True)

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

        # Display table
        df = pd.DataFrame(daily_rows_display)
        st.session_state["daily_df"] = df

        st.subheader("📅 Daily overview (table)")
        st.dataframe(df, use_container_width=True)

    # ============================================================
    #  TAB 2 — BULK IMPORT
    # ============================================================
    with tabs[1]:
        st.subheader("📥 Bulk import daily data (JSON or CSV)")

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

        st.markdown('<div style="border-bottom: 2px solid #d1d5db; margin: 1rem 0;"></div>', unsafe_allow_html=True)

        uploaded_bulk = st.file_uploader(
            "Upload bulk data file", type=["json", "csv"], key="bulk_import_uploader"
        )

        if uploaded_bulk:
            file_name = uploaded_bulk.name.lower()

            # ---------------------- JSON IMPORT ---------------------- #
            if file_name.endswith(".json"):
                try:
                    raw = json.loads(uploaded_bulk.getvalue().decode("utf-8"))
                except Exception as e:
                    st.error(f"Invalid JSON: {e}")
                    st.stop()

                st.markdown("### 🔍 Preview JSON")
                st.json(raw)

                if st.button("📥 Import JSON into Supabase"):
                    fx_rate = st.session_state.get("fx_rate", 0.0)

                    for date_key, day_info in raw.items():
                        try:
                            day_date = pd.to_datetime(date_key).date()
                        except:
                            continue

                        ad_spend = float(day_info.get("ad_spend", 0.0))
                        visitors = int(day_info.get("visitors", 1))
                        orders_raw = day_info.get("orders", [])

                        orders = []
                        for o in orders_raw:
                            if isinstance(o, dict):
                                orders.append({
                                    "sales": float(o.get("sales", 0.0)),
                                    "profit": float(o.get("profit", 0.0)),
                                })

                        delete_daily_row(day_date)

                        total_sales = sum(o["sales"] for o in orders)
                        total_profit = sum(o["profit"] for o in orders)
                        profit_after_ads = total_profit - ad_spend
                        profit_after_ads_gbp = profit_after_ads * fx_rate
                        percent_profit = (profit_after_ads / total_sales * 100) if total_sales > 0 else 0

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

                        daily_row = get_daily_row(day_date)
                        day_id = daily_row["id"]

                        for idx, o in enumerate(orders, start=1):
                            upsert_order_row(day_id, idx, o["sales"], o["profit"])

                    st.success("Bulk JSON import complete.")
                    st.rerun()

            # ---------------------- CSV IMPORT ---------------------- #
            elif file_name.endswith(".csv"):
                try:
                    df_csv = pd.read_csv(uploaded_bulk)
                except Exception as e:
                    st.error(f"Invalid CSV: {e}")
                    st.stop()

                st.markdown("### 🔍 Preview CSV")
                st.dataframe(df_csv, use_container_width=True)

                if st.button("📥 Import CSV into Supabase"):
                    fx_rate = st.session_state.get("fx_rate", 0.0)

                    df_csv["date"] = pd.to_datetime(df_csv["date"]).dt.date

                    for day_date, group in df_csv.groupby("date"):
                        first = group.iloc[0]
                        ad_spend = float(first.get("ad_spend", 0.0))
                        visitors = int(first.get("visitors", 1))

                        orders = []
                        for _, row in group.sort_values("order_index").iterrows():
                            orders.append({
                                "sales": float(row["sales"]),
                                "profit": float(row["profit"]),
                            })

                        delete_daily_row(day_date)

                        total_sales = sum(o["sales"] for o in orders)
                        total_profit = sum(o["profit"] for o in orders)
                        profit_after_ads = total_profit - ad_spend
                        profit_after_ads_gbp = profit_after_ads * fx_rate
                        percent_profit = (profit_after_ads / total_sales * 100) if total_sales > 0 else 0

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

                        daily_row = get_daily_row(day_date)
                        day_id = daily_row["id"]

                        for idx, o in enumerate(orders, start=1):
                            upsert_order_row(day_id, idx, o["sales"], o["profit"])

                    st.success("Bulk CSV import complete.")
                    st.rerun()

    # ============================================================
    #  TAB 3 — KPIs
    # ============================================================
    with tabs[2]:
        st.subheader("📊 KPIs")

        df = st.session_state.get("daily_df", pd.DataFrame())

        if df.empty:
            st.info("No data yet.")
        else:
            total_sales = float(df["Sales ($)"].sum())
            total_profit = float(df["Profit ($)"].sum())
            total_ad_spend = float(df["Ad Spend ($)"].sum())
            total_profit_after_ads = float(df["Profit After Ads ($)"].sum())
            total_profit_after_ads_gbp = float(df["Profit After Ads (£)"].sum())

            overall_profit_percent = (
                (total_profit - total_ad_spend) / total_sales * 100
                if total_sales > 0 else 0.0
            )

            roas = total_sales / total_ad_spend if total_ad_spend > 0 else 0.0

            c1, c2, c3, c4, c5 = st.columns(5)

            c1.metric("Total sales ($)", f"${total_sales:,.2f}")
            c2.metric("Total profit ($)", f"${total_profit:,.2f}")
            c3.metric("Total ad spend ($)", f"${total_ad_spend:,.2f}")
            c4.metric("Profit after ads ($)", f"${total_profit_after_ads:,.2f}")
            c5.metric("Profit after ads (£)", f"£{total_profit_after_ads_gbp:,.2f}")

            st.markdown('<div style="border-bottom: 2px solid #d1d5db; margin: 1rem 0;"></div>', unsafe_allow_html=True)

            c6, c7 = st.columns(2)
            c6.metric("Overall profit %", f"{overall_profit_percent:,.2f}%")
            c7.metric("ROAS", f"{roas:,.2f}x")

    # ============================================================
    #  TAB 4 — SUMMARIES
    # ============================================================
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
                .agg({
                    "Sales ($)": "sum",
                    "Profit ($)": "sum",
                    "Ad Spend ($)": "sum",
                    "Profit After Ads ($)": "sum",
                    "Profit After Ads (£)": "sum",
                    "Orders": "sum",
                    "Visitors": "sum",
                })
                .reset_index()
                .rename(columns={"Date": "Week Start"})
            )
            st.dataframe(weekly, use_container_width=True)

            st.markdown('<div style="border-bottom: 2px solid #d1d5db; margin: 1rem 0;"></div>', unsafe_allow_html=True)

            # Monthly summary
            st.markdown("### Monthly summary")
            monthly = (
                df_summary.groupby(df_summary["Date"].dt.to_period("M"))
                .agg({
                    "Sales ($)": "sum",
                    "Profit ($)": "sum",
                    "Ad Spend ($)": "sum",
                    "Profit After Ads ($)": "sum",
                    "Profit After Ads (£)": "sum",
                    "Orders": "sum",
                    "Visitors": "sum",
                })
                .reset_index()
            )
            monthly["Date"] = monthly["Date"].astype(str)
            st.dataframe(monthly, use_container_width=True)

            st.markdown('<div style="border-bottom: 2px solid #d1d5db; margin: 1rem 0;"></div>', unsafe_allow_html=True)

            # Yearly summary
            st.markdown("### Yearly summary")
            yearly = (
                df_summary.groupby(df_summary["Date"].dt.year)
                .agg({
                    "Sales ($)": "sum",
                    "Profit ($)": "sum",
                    "Ad Spend ($)": "sum",
                    "Profit After Ads ($)": "sum",
                    "Profit After Ads (£)": "sum",
                    "Orders": "sum",
                    "Visitors": "sum",
                })
                .reset_index()
                .rename(columns={"Date": "Year"})
            )
            st.dataframe(yearly, use_container_width=True)
    # ============================================================
    #  TAB 5 — EXPORT
    # ============================================================
    with tabs[4]:
        st.subheader("📤 Export data")

        df = st.session_state.get("daily_df", pd.DataFrame())

        if df.empty:
            st.info("No data to export.")
        else:
            # CSV Export
            csv_data = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download CSV (daily overview)",
                csv_data,
                "curata_daily_overview.csv",
                "text/csv",
            )

        st.markdown('<div style="border-bottom: 2px solid #d1d5db; margin: 1rem 0;"></div>', unsafe_allow_html=True)

        # Full Supabase backup (daily_data + orders)
        if st.button("📦 Export full Supabase backup (JSON)"):
            all_days = load_all_daily_rows()
            export_blob = {}

            for row in all_days:
                day_date = pd.to_datetime(row["date"]).date().isoformat()
                orders = load_orders_for_day(row["id"])

                export_blob[day_date] = {
                    "ad_spend": float(row["ad_spend_usd"]),
                    "visitors": int(row["visitors"]),
                    "orders": [
                        {"sales": float(o["sales_usd"]), "profit": float(o["profit_usd"])}
                        for o in orders
                    ],
                }

            st.download_button(
                "⬇️ Download Supabase backup JSON",
                json.dumps(export_blob, indent=2).encode("utf-8"),
                "curata_supabase_backup.json",
                "application/json",
            )

        st.markdown('<div style="border-bottom: 2px solid #d1d5db; margin: 1rem 0;"></div>', unsafe_allow_html=True)

        # Export UI preferences only
        if st.button("⬇️ Export UI preferences (JSON)"):
            prefs = export_session_state_dict()
            st.download_button(
                "Download UI preferences JSON",
                json.dumps(prefs, indent=2).encode("utf-8"),
                "curata_ui_prefs.json",
                "application/json",
            )

    # ============================================================
    #  TAB 6 — SESSION JSON (UI prefs only)
    # ============================================================
    with tabs[5]:
        st.subheader("🧩 Session JSON (UI preferences only)")

        st.markdown("Upload a JSON file containing UI preferences (start_date, fx_rate, etc.).")

        uploaded_json = st.file_uploader("Upload UI preferences JSON", type=["json"])

        if uploaded_json:
            try:
                data = json.load(uploaded_json)
                apply_session_dict(data)
                st.success("UI preferences restored. Rerunning…")
                st.rerun()
            except Exception as e:
                st.error(f"Invalid JSON: {e}")

        st.markdown('<div style="border-bottom: 2px solid #d1d5db; margin: 1rem 0;"></div>', unsafe_allow_html=True)

        st.subheader("Current UI preferences")
        st.json(export_session_state_dict())

    # ============================================================
    #  TAB 7 — SUMMARY CHARTS
    # ============================================================
    with tabs[6]:
        st.subheader("📊 Summary Charts")

        df = st.session_state.get("daily_df", pd.DataFrame())

        if df.empty:
            st.info("No data yet.")
        else:
            df_chart = df.copy()
            df_chart["Date"] = pd.to_datetime(df_chart["Date"])

            # Sales chart
            st.markdown("### Sales ($) over time")
            fig_sales = px.line(df_chart, x="Date", y="Sales ($)", markers=True)
            st.plotly_chart(fig_sales, use_container_width=True)

            # Profit chart
            st.markdown("### Profit ($) over time")
            fig_profit = px.line(df_chart, x="Date", y="Profit ($)", markers=True)
            st.plotly_chart(fig_profit, use_container_width=True)

            # Profit After Ads chart
            st.markdown("### Profit After Ads (£) over time")
            fig_paa = px.line(df_chart, x="Date", y="Profit After Ads (£)", markers=True)
            st.plotly_chart(fig_paa, use_container_width=True)

    # ============================================================
    #  TAB 8 — ADMIN
    # ============================================================
    with tabs[7]:
        st.subheader("🛠 Admin Tools")

        st.markdown("### Withdrawals")
        from curata_db import load_withdrawals, add_withdrawal

        withdrawals = load_withdrawals()

        if withdrawals:
            st.dataframe(pd.DataFrame(withdrawals), use_container_width=True)
        else:
            st.info("No withdrawals recorded.")

        st.markdown("### Add new withdrawal")
        w_date = st.date_input("Withdrawal date", value=date.today())
        w_amount = st.number_input("Amount (£)", min_value=0.0, step=1.0)

        if st.button("Add withdrawal"):
            add_withdrawal(w_date, w_amount)
            st.success("Withdrawal added.")
            st.rerun()

        st.markdown('<div style="border-bottom: 2px solid #d1d5db; margin: 1rem 0;"></div>', unsafe_allow_html=True)

        st.markdown("### Save global UI state")
        if st.button("Save UI preferences to Supabase"):
            prefs = export_session_state_dict()
            save_global_state(prefs)
            st.success("Global UI state saved.")

    # ============================================================
    #  TAB 9 — MIGRATION (Old JSON → Supabase)
    # ============================================================
    with tabs[8]:
        st.subheader("📦 Migration Tool (Old JSON → Supabase)")

        st.markdown("Upload your old Curata session JSON to migrate it into Supabase.")

        uploaded_old = st.file_uploader("Upload old session JSON", type=["json"])

        if uploaded_old:
            try:
                raw = json.load(uploaded_old)
            except Exception as e:
                st.error(f"Invalid JSON: {e}")
                st.stop()

            st.markdown("### Preview")
            st.json(raw)

            if st.button("🚀 Migrate to Supabase"):
                fx_rate = st.session_state.get("fx_rate", 0.0)

                for date_key, day_info in raw.items():
                    try:
                        day_date = pd.to_datetime(date_key).date()
                    except:
                        continue

                    ad_spend = float(day_info.get("ad_spend", 0.0))
                    visitors = int(day_info.get("visitors", 1))
                    orders_raw = day_info.get("orders", [])

                    orders = []
                    for o in orders_raw:
                        if isinstance(o, dict):
                            orders.append({
                                "sales": float(o.get("sales", 0.0)),
                                "profit": float(o.get("profit", 0.0)),
                            })

                    delete_daily_row(day_date)

                    total_sales = sum(o["sales"] for o in orders)
                    total_profit = sum(o["profit"] for o in orders)
                    profit_after_ads = total_profit - ad_spend
                    profit_after_ads_gbp = profit_after_ads * fx_rate
                    percent_profit = (profit_after_ads / total_sales * 100) if total_sales > 0 else 0

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

                    daily_row = get_daily_row(day_date)
                    day_id = daily_row["id"]

                    for idx, o in enumerate(orders, start=1):
                        upsert_order_row(day_id, idx, o["sales"], o["profit"])

                st.success("Migration complete. Reloading…")
                st.rerun()

# END OF FILE
