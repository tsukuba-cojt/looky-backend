from supabase import create_client, Client
from typing import Optional
from config import settings


class Database:
    """Supabaseクライアントのシングルトン管理クラス"""
    
    _instance: Optional['Database'] = None
    _client: Optional[Client] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            self._client = create_client(
                settings.supabase_url,
                settings.supabase_key
            )
    
    @property
    def client(self) -> Client:
        """Supabaseクライアントを取得"""
        return self._client
    
    def get_user_by_id(self, user_id: str):
        """ユーザーIDでユーザー情報を取得"""
        return self._client.table("t_user").select().eq("id", user_id).execute()
    
    def get_user_preferences(self, user_id: str):
        """ユーザーの好みデータを取得"""
        return self._client.table("t_user_vton").select().eq("feedback_flag", 1).eq("user_id", user_id).execute()
    
    def get_vton_by_id(self, vton_id: str):
        """VTON IDでVTON情報を取得"""
        return self._client.table("t_vton").select().eq("id", vton_id).execute()
    
    def get_clothes_by_id(self, clothes_id: int):
        """洋服IDで洋服情報を取得"""
        return self._client.table("t_clothes").select().eq("id", clothes_id).execute()
    
    def get_clothes_by_ids(self, clothes_ids: list):
        """洋服IDリストで洋服情報を取得"""
        return self._client.table("t_clothes").select().in_("id", clothes_ids).execute()
    
    def create_vton(self, tops_id: int, object_key: str):
        """VTONレコードを作成"""
        return self._client.table("t_vton").insert({
            "tops_id": tops_id,
            "object_key": object_key,
        }).execute()
    
    def create_user_vton(self, user_id: str, vton_id: str, feedback_flag: int = 0):
        """ユーザーVTONレコードを作成"""
        return self._client.table("t_user_vton").insert({
            "user_id": user_id,
            "vton_id": vton_id,
            "feedback_flag": feedback_flag
        }).execute()


# グローバルデータベースインスタンス
db = Database()