from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware import Middleware
import asyncio
import logging
import os
import time
import torch
import random
import open_clip
import faiss
from utils.clipFaiss import (
    retrieve_similar_images_by_vector,
    load_faiss_index,
    get_preference_vector
)
from utils.s3 import download_if_needed
from utils.fitdit import execute_fitdit
from pydantic import BaseModel
from middlewares.middleware import verify_secret_key
from config import settings
from utils.database import db

# ログレベルの設定（環境変数から取得、デフォルトはWARNING. INFO, DEBUG, ERROR, CRITICAL, NOTSET）
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

origins = [
    "*"
]

app = FastAPI(
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    ]
)

device = "cuda" if torch.cuda.is_available() else "cpu"

# モデルとプロセッサのロード
model = None
preprocess_train = None
preprocess_val = None
tokenizer = None
index = None

@app.on_event("startup")
async def startup_event():
    """
    アプリケーションの起動時に実行される関数
    モデル、トークナイザー、faissのインデックスをロードする
    """
    try:
        start = time.time()
        logger.info("STARTUP: S3ダウンロード開始")
        global model, preprocess_train, preprocess_val, tokenizer, index
        download_if_needed(
            settings.aws_s3_index_bucket_name,
            settings.aws_s3_index_key_name,
            settings.local_index_path
        )
        logger.info("STARTUP: S3ダウンロード完了、モデルロード開始")

        # モデル・前処理・トークナイザーを並列でロード
        model_and_preprocess, tokenizer = await asyncio.gather(
            asyncio.to_thread(open_clip.create_model_and_transforms, 'hf-hub:Marqo/marqo-fashionSigLIP'),
            asyncio.to_thread(open_clip.get_tokenizer, 'hf-hub:Marqo/marqo-fashionSigLIP')
        )
        model, preprocess_train, preprocess_val = model_and_preprocess
        model = model.to(device)
        model.eval()
        logger.info("STARTUP: モデルロード完了")

        logger.info(f"{settings.local_index_path}のインデックスのロードを開始します...")
        try:
            index = await asyncio.to_thread(load_faiss_index, settings.local_index_path)
            logger.info("既存のインデックスをロードしました")
        except FileNotFoundError:
            logger.error("faissのインデックスが見つかりません。終了します。")

        logger.info("STARTUP: インデックスロード完了")
        logger.info(f"STARTUP: 全体の初期化完了 - 処理時間: {time.time() - start:.2f}秒")
    except Exception as e:
        logger.error(f"STARTUP: エラーが発生しました: {e}")
        import sys
        sys.exit(1)

#--------------------
# test API
#--------------------

@app.get("/")
def read_root():
    """
    テスト用のAPI
    """
    return {"message": "Hello, looky!"}

#--------------------
# MVP(Minimum Viable Product)
#--------------------

class UserIdRequest(BaseModel):
    user_id: str

@app.post("/user/clothes/recommend")
async def get_recommendation_clothes(
    request: UserIdRequest,
    # シークレットキーの検証(middleware.py)
    _: None = Depends(verify_secret_key)
):
    """
    リクエストからユーザの好みに合った洋服を推薦し、VTONの画像を生成する
    args:
        request: UserIdRequest{
            user_id: str
        }
    returns:
        object_key: str
    """
    clothes_category = "Upper-body" # "Upper-body" / "Dressed" / "Lower-body"
    
    try:
        clothes_ids = db.get_clothes_ids_about_category(category=clothes_category)
        if not clothes_ids:
            raise HTTPException(status_code=500, detail="指定されたカテゴリの洋服が見つかりません")
        faiss_selector = faiss.IDSelectorArray(clothes_ids)
    except Exception as e:
        logger.error(f"カテゴリ別洋服ID取得エラー: {e}")
        raise HTTPException(status_code=500, detail="洋服カテゴリの取得に失敗しました")
    
    user = db.get_user_by_id(request.user_id)
    if not user.data:
        raise HTTPException(status_code=400, detail="ユーザーが見つかりません")
    
    body_object_key = user.data[0]["body_url"]
    if not body_object_key:
        raise HTTPException(status_code=400, detail="body_urlがありません")
    
    # ユーザーの好みデータを取得
    like_ids, love_ids, hate_ids, generated_full_ids = db.get_preference_clothes_ids_by_category(request.user_id, clothes_category)
    
    # フィードバックが不足している場合のログ
    total_feedback = len(like_ids) + len(love_ids) + len(hate_ids)
    if total_feedback < 3:
        logger.info(f"ユーザー {request.user_id} のフィードバックが不足しています (総数: {total_feedback})")
    
    # 生成済みの洋服を除外
    if generated_full_ids:
        exclude_selector = faiss.IDSelectorNot(generated_full_ids)
        faiss_selector = faiss.IDSelectorAnd([faiss_selector, exclude_selector])
    
    # 性別によって洋服を選ぶ
    try:
        if user.data[0]["gender"] == "male":
            exclude_clothes_ids_about_gender = db.get_clothes_ids_about_gender(gender="female")
            if exclude_clothes_ids_about_gender:
                exclude_selector_by_gender = faiss.IDSelectorNot(exclude_clothes_ids_about_gender)
                faiss_selector = faiss.IDSelectorAnd([faiss_selector, exclude_selector_by_gender])
        elif user.data[0]["gender"] == "female":
            exclude_clothes_ids_about_gender = db.get_clothes_ids_about_gender(gender="male")
            if exclude_clothes_ids_about_gender:
                exclude_selector_by_gender = faiss.IDSelectorNot(exclude_clothes_ids_about_gender)
                faiss_selector = faiss.IDSelectorAnd([faiss_selector, exclude_selector_by_gender])
        else:
            logger.info(f"ユーザー {request.user_id} の性別が設定されていません")
    except Exception as e:
        logger.warning(f"性別フィルタリングでエラーが発生しました: {e}")
        # 性別フィルタリングに失敗しても処理を続行
    
    preference_vector = get_preference_vector(like_ids, love_ids, hate_ids, index)

    # 類似画像を検索
    try:
        indices = retrieve_similar_images_by_vector(vector=preference_vector, index=index, top_k=10, exclude_selector=faiss_selector)
        if len(indices) == 0:
            raise HTTPException(status_code=500, detail="類似する洋服が見つかりません")
        
        num_rand = random.randint(0, min(9, len(indices) - 1))
        indice = indices[num_rand]
    except ValueError as e:
        logger.error(f"類似画像検索エラー: {e}")
        raise HTTPException(status_code=500, detail="類似する洋服が見つかりません")
    except Exception as e:
        logger.error(f"類似画像検索エラー: {e}")
        raise HTTPException(status_code=500, detail="類似画像の検索に失敗しました")

    clothes = db.get_clothes_by_id(indice)
    if not clothes.data:
        raise HTTPException(status_code=400, detail="洋服が見つかりません")
    clothes_key = clothes.data[0]["image_url"]
    actual_clothes_id = clothes.data[0]["id"]
    
    try:
        fitdit_response = await execute_fitdit(
            body_image_path=body_object_key,
            clothes_image_path=clothes_key,
            clothes_type="Upper-body"
        )
        object_key = fitdit_response["object_key"]
        vton_result = db.create_vton(
            tops_id=actual_clothes_id,
            object_key=object_key
        )
        vton_id = vton_result.data[0]["id"]
        db.create_user_vton(
            user_id=request.user_id,
            vton_id=vton_id
        )
    except Exception as e:
        logger.error(f"VTON生成エラー: {e}")
        raise HTTPException(status_code=500, detail=f"VTONの生成に失敗しました: {str(e)}")
    
    return {"status": "success"}