from pydantic_settings import BaseSettings
from pydantic import Field, computed_field


class Settings(BaseSettings):
    """アプリケーション設定管理クラス"""
    
    # Supabase設定
    supabase_url: str = Field(..., env="SUPABASE_URL")
    supabase_key: str = Field(..., env="SUPABASE_KEY")
    
    # AWS設定
    aws_region_name: str = Field(default="us-east-1", env="AWS_REGION_NAME")
    aws_access_key: str = Field(..., env="AWS_ACCESS_KEY")
    aws_secret_key: str = Field(..., env="AWS_SECRET_KEY")
    
    # S3設定
    aws_clothes_bucket_name: str = Field(..., env="AWS_CLOTHES_BUCKET_NAME")
    aws_vton_bucket_name: str = Field(..., env="AWS_VTON_BUCKET_NAME")
    aws_index_bucket_name: str = Field(..., env="AWS_INDEX_BUCKET_NAME")
    aws_body_bucket_name: str = Field(..., env="AWS_BODY_BUCKET_NAME")
    aws_faiss_index_name: str = Field(..., env="AWS_FAISS_INDEX_NAME")
    
    # アプリケーション設定
    log_level: str = Field(default="WARNING", env="LOG_LEVEL")
    internal_api_secret: str = Field(..., env="INTERNAL_API_SECRET")
    
    # FitDit設定
    fitdit_url: str = Field(..., env="FITDIT_URL")
    
    # モデル設定
    model_name: str = Field(default="patrickjohncyh/fashion-clip")
    
    # デフォルト設定
    default_tops_id: int = Field(default=1)
    
    @computed_field
    @property
    def local_index_path(self) -> str:
        """ローカルインデックスパスを計算"""
        return f"../tmp/{self.aws_faiss_index_name}"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# グローバル設定インスタンス
settings = Settings()