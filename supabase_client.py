import json
import streamlit as st
from supabase import create_client

@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_ANON_KEY"]
    return create_client(url, key)

# ============================================================
#  PER-USER SESSION FUNCTIONS (kept for rollback safety)
# ============================================================

def load_session_from_supabase(user_id: str):
    if not user_id:
        return None

    supabase = get_supabase()
    try:
        resp = (
            supabase.table("curata_sessions")
            .select("session_json")
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        if resp.data:
            return resp.data.get("session_json", {})
        return None
    except Exception:
        return None


def save_session_to_supabase(user_id: str, session_dict: dict):
    if not user_id:
        return

    supabase = get_supabase()
    payload = {
        "user_id": user_id,
        "session_json": session_dict,
    }

    try:
        supabase.table("curata_sessions").upsert(payload).execute()
    except Exception:
        pass


# ============================================================
#  GLOBAL SESSION FUNCTIONS (NEW — used by the whole dashboard)
# ============================================================

GLOBAL_KEY = "global"   # single row ID for the entire dashboard


def load_global_state():
    supabase = get_supabase()
    try:
        resp = (
            supabase.table("curata_global_state")
            .select("session_json")
            .eq("id", GLOBAL_KEY)
            .single()
            .execute()
        )
        if resp.data:
            return resp.data.get("session_json", {})
        return None
    except Exception:
        return None


def save_global_state(session_dict: dict):
    supabase = get_supabase()
    payload = {
        "id": GLOBAL_KEY,
        "session_json": session_dict,
    }

    try:
        supabase.table("curata_global_state").upsert(payload).execute()
    except Exception:
        pass
