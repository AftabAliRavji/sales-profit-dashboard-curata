# supabase_client.py

import json
import streamlit as st
from supabase import create_client, Client

@st.cache_resource
def get_supabase_client() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_ANON_KEY"]
    return create_client(url, key)

def load_session_from_supabase(user_id: str):
    """
    Load the latest session JSON for a given user_id from Supabase.
    Returns a dict or None.
    """
    if not user_id:
        return None

    supabase = get_supabase_client()
    try:
        resp = (
            supabase
            .table("curata_sessions")
            .select("session_json")
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        data = resp.data
        if not data:
            return None
        session_json = data.get("session_json", {})
        if isinstance(session_json, dict):
            return session_json
        # If stored as string for any reason
        return json.loads(session_json)
    except Exception:
        return None

def save_session_to_supabase(user_id: str, session_dict: dict):
    """
    Upsert the session JSON for a given user_id into Supabase.
    """
    if not user_id:
        return

    supabase = get_supabase_client()
    payload = {
        "user_id": user_id,
        "session_json": session_dict,
    }

    try:
        supabase.table("curata_sessions").upsert(payload).execute()
    except Exception:
        # Silent fail in UI; you can add logging later if you want
        pass
