import streamlit as st
from supabase import create_client
from datetime import date
from typing import List, Dict, Optional

# ============================================================
#  SUPABASE CLIENT
# ============================================================

@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_ANON_KEY"]
    return create_client(url, key)


# ============================================================
#  DAILY DATA HELPERS
# ============================================================

def upsert_daily_row(
    day_date: date,
    ad_spend_usd: float,
    visitors: int,
    orders: int,
    sales_usd: float,
    profit_usd: float,
    profit_after_ads_usd: float,
    profit_after_ads_gbp: float,
    profit_percent: float,
):
    """
    Insert or update a single daily row in curata_daily_data.
    """
    supabase = get_supabase()

    payload = {
        "date": day_date.isoformat(),
        "ad_spend_usd": ad_spend_usd,
        "visitors": visitors,
        "orders": orders,
        "sales_usd": sales_usd,
        "profit_usd": profit_usd,
        "profit_after_ads_usd": profit_after_ads_usd,
        "profit_after_ads_gbp": profit_after_ads_gbp,
        "profit_percent": profit_percent,
    }

    return supabase.table("curata_daily_data").upsert(payload).execute()


def get_daily_row(day_date: date) -> Optional[Dict]:
    """
    Fetch a single daily row by date.
    """
    supabase = get_supabase()
    resp = (
        supabase.table("curata_daily_data")
        .select("*")
        .eq("date", day_date.isoformat())
        .single()
        .execute()
    )
    return resp.data if resp.data else None


def load_all_daily_rows() -> List[Dict]:
    """
    Load all daily rows sorted by date.
    """
    supabase = get_supabase()
    resp = (
        supabase.table("curata_daily_data")
        .select("*")
        .order("date", desc=False)
        .execute()
    )
    return resp.data or []


def delete_daily_row(day_date: date):
    """
    Delete a daily row (orders cascade automatically).
    """
    supabase = get_supabase()
    return (
        supabase.table("curata_daily_data")
        .delete()
        .eq("date", day_date.isoformat())
        .execute()
    )


# ============================================================
#  ORDER HELPERS
# ============================================================

def upsert_order_row(
    day_id: int,
    order_index: int,
    sales_usd: float,
    profit_usd: float,
):
    """
    Insert or update a single order row.
    """
    supabase = get_supabase()

    payload = {
        "day_id": day_id,
        "order_index": order_index,
        "sales_usd": sales_usd,
        "profit_usd": profit_usd,
    }

    return supabase.table("curata_daily_orders").upsert(payload).execute()


def load_orders_for_day(day_id: int) -> List[Dict]:
    """
    Load all orders for a given day_id.
    """
    supabase = get_supabase()
    resp = (
        supabase.table("curata_daily_orders")
        .select("*")
        .eq("day_id", day_id)
        .order("order_index", desc=False)
        .execute()
    )
    return resp.data or []


def delete_orders_for_day(day_id: int):
    """
    Delete all orders for a given day.
    """
    supabase = get_supabase()
    return (
        supabase.table("curata_daily_orders")
        .delete()
        .eq("day_id", day_id)
        .execute()
    )


def delete_single_order(day_id: int, order_index: int):
    """
    Delete a single order row.
    """
    supabase = get_supabase()
    return (
        supabase.table("curata_daily_orders")
        .delete()
        .eq("day_id", day_id)
        .eq("order_index", order_index)
        .execute()
    )
