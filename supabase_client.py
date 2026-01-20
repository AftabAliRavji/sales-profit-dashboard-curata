import json
import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime

# ============================================================
#  SUPABASE CLIENT
# ============================================================

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
#  JSON-SAFE FILTER
# ============================================================

def make_json_safe(data: dict):
    safe = {}

    for key, value in data.items():

        # Skip Streamlit UploadedFile objects
        if hasattr(value, "read"):
            continue

        # Skip pandas DataFrames
        if isinstance(value, pd.DataFrame):
            continue

        # Skip any callable (functions, methods)
        if callable(value):
            continue

        # Skip any object that is clearly not JSON-safe
        if isinstance(value, (bytes, bytearray)):
            continue

        # Try to serialize — only keep if JSON-safe
        try:
            json.dumps(value)
            safe[key] = value
        except Exception:
            continue

    return safe


# ============================================================
#  GLOBAL SESSION FUNCTIONS
# ============================================================

GLOBAL_KEY = "global"


def load_global_state():
    supabase = get_supabase()
    try:
        resp = (
            supabase.table("curata_global_state")
            .select("session_json, last_updated")
            .eq("id", GLOBAL_KEY)
            .single()
            .execute()
        )
        if resp.data:
            return {
                "session_json": resp.data.get("session_json", {}),
                "last_updated": resp.data.get("last_updated")
            }
        return None
    except Exception:
        return None


def save_global_state(session_dict: dict):
    supabase = get_supabase()

    # Filter JSON-safe values
    safe_dict = make_json_safe(session_dict)

    payload = {
        "id": GLOBAL_KEY,
        "session_json": safe_dict
    }

    print("🔄 Saving global state to Supabase...")
    print("Payload keys:", list(payload["session_json"].keys()))

    # MAIN SAVE
    try:
        supabase.table("curata_global_state").upsert(payload).execute()
    except Exception as e:
        print("❌ Supabase save failed:", e)

    # VERSIONING
    try:
        supabase.table("curata_global_versions").insert({
            "saved_by": st.session_state.get("user_id", "unknown"),
            "session_json": safe_dict,
            "locked": False,
        }).execute()
    except Exception as e:
        print("❌ Version save failed:", e)

    # AUDIT LOG
    try:
        supabase.table("curata_global_audit").insert({
            "user_id": st.session_state.get("user_id", "unknown"),
            "action": "save_global_state",
            "details": {"keys_saved": list(safe_dict.keys())}
        }).execute()
    except Exception as e:
        print("❌ Audit log failed:", e)

    # AUTO-BACKUP TO STORAGE
    try:
        backup_name = f"backup_{datetime.utcnow().isoformat()}.json"
        supabase.storage.from_("curata_backups").upload(
            backup_name,
            json.dumps(safe_dict)
        )
    except Exception as e:
        print("❌ Backup failed:", e)
