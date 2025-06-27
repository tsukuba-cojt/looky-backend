from supabase import create_client, Client
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

def get_user_by_id(user_id: str):
    return supabase.table("t_user").select().eq("id", user_id).execute()

def get_preference_by_user_id(user_id: str):
    return supabase.table("t_user_vton").select().eq("user_id", user_id).eq("feedback_flag", 1).execute()

def save_clothes_to_supabase(
    object_key: str,
    id: int
    ):
    supabase.table("t_clothes").insert({
        "id": id,
        "image_url": object_key,
    }).execute()

