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
    
    def get_preferences_tops_ids(self, user_id: str):
        """ユーザーの好みデータを取得"""
        result = self._client.table("t_user_vton").select("t_vton(tops_id),feedback").eq("user_id", user_id).execute()
        
        # フィードバック別にtops_idを分類
        like_ids = []
        love_ids = []
        hate_ids = []
        full_ids = []
        
        for item in result.data:
            tops_id = item["t_vton"]["tops_id"]
            feedback = item["feedback"]
            
            if feedback == "like":
                like_ids.append(tops_id)
            elif feedback == "love":
                love_ids.append(tops_id)
            elif feedback == "hate":
                hate_ids.append(tops_id)
            
            # すべてのtops_idをfull_idsに追加
            full_ids.append(tops_id)
        
        return (like_ids, love_ids, hate_ids, full_ids)
    
    def get_preference_clothes_ids_by_category(self, user_id: str, category: str):
        """洋服IDリストを取得"""
        if category == "Upper-body":
            like_ids, love_ids, hate_ids, full_ids = self.get_preference_tops_ids(user_id)
        # elif category == "Dressed":
        #     like_ids, love_ids, hate_ids, full_ids = self.get_preference_dresses_ids(user_id)
        # elif category == "Lower-body":
        #     like_ids, love_ids, hate_ids, full_ids = self.get_preference_bottoms_ids(user_id)
        else:
            raise ValueError("Invalid category")
        return like_ids, love_ids, hate_ids, full_ids
    
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
    
    def create_user_vton(self, user_id: str, vton_id: str):
        """ユーザーVTONレコードを作成"""
        return self._client.table("t_user_vton").insert({
            "user_id": user_id,
            "vton_id": vton_id
        }).execute()

    def get_clothes_ids_about_gender(self, gender: str):
        """性別によって洋服を選ぶ"""
        result = self._client.table("t_clothes").select("id").eq("gender", gender).execute()
        return [item["id"] for item in result.data]
    
    def get_clothes_ids_about_category(self, category: str):
        """カテゴリによって洋服を選ぶ"""
        result = self._client.table("t_clothes").select("id").eq("category", category).execute()
        return [item["id"] for item in result.data]

# グローバルデータベースインスタンス
db = Database()