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
from utils.clipFaiss import (
    retrieve_similar_images_by_vector,
    load_faiss_index,
    mean_vector_from_ids
)
from utils.s3 import download_if_needed
from utils.fitdit import execute_fitdit
from pydantic import BaseModel
from middlewares.middleware import verify_secret_key
from config import settings
from utils.database import db

# ログレベルの設定（環境変数から取得、デフォルトはWARNING）
log_level = os.getenv("LOG_LEVEL", "WARNING").upper()
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
    
    
    user_result = db.get_user_by_id(request.user_id)
    if not user_result.data:
        raise HTTPException(status_code=400, detail="ユーザーが見つかりません")
    
    body_object_key = user_result.data[0]["body_url"]
    if not body_object_key:
        raise HTTPException(status_code=400, detail="body_urlがありません")
    
    preference_result = db.get_user_preferences(request.user_id)
    if not preference_result:
        logger.info("いいねしたデータがありません。ランダムな洋服を推薦します")
        preference_vector = mean_vector_from_ids(
            faiss_index=index,
            ids=settings.default_preference_ids
        )
    else:
        vton_ids = [item["vton_id"] for item in preference_result.data]
        clothes_ids = []
        for vton_id in vton_ids:
            vton_result = db.get_vton_by_id(vton_id)
            if vton_result.data:
                clothes_ids.append(vton_result.data[0]["tops_id"])
        
        # clothes_idsが空の場合はデフォルトの洋服を使用
        if not clothes_ids:
            logger.info("clothes_idsが空のため、デフォルトの洋服を使用します")
            preference_vector = mean_vector_from_ids(
                faiss_index=index,
                ids=[129, 130, 131, 132, 133, 134, 135, 136, 137, 138]
            )
        else:
            preference_vector = mean_vector_from_ids(
                faiss_index=index,
                ids=clothes_ids
            )

    indices = retrieve_similar_images_by_vector(vector=preference_vector, index=index, top_k=10)
    num_rand = random.randint(1, 9) #最も近いものは除く
    indice = indices[num_rand]
    clothes_id = db.get_clothes_by_id(indice)
    if not clothes_id:
        raise HTTPException(status_code=404, detail="洋服が見つかりません")
    clothes_key = clothes_id.data[0]["image_url"]
    actual_clothes_id = clothes_id.data[0]["id"]  # 実際のIDを取得
    try:
        fitdit_response = await execute_fitdit(
            body_image_path=body_object_key,
            clothes_image_path=clothes_key,
            clothes_type="Upper-body"
        )
        object_key = fitdit_response["object_key"]
        vton_result = db.create_vton(
            tops_id=actual_clothes_id,  # 実際のIDを使用
            object_key=object_key
        )
        vton_id = vton_result.data[0]["id"]
        db.create_user_vton(
            user_id=request.user_id,
            vton_id=vton_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"VTONの生成に失敗しました: {str(e)}")

    # indices = retrieve_similar_images_by_vector(vector=preference_vector, index=index, top_k=3)
    # retrieved_images_result = db.get_clothes_by_ids(indices.tolist())
    # retrieved_images_keys = [item["image_url"] for item in retrieved_images_result.data]
    # object_key_list = []
        
    # for image_path in retrieved_images_keys:
    #     # VTONサーバへのリクエスト
    #     try:
    #         fitdit_response = await execute_fitdit(
    #                 body_image_path=body_object_key,
    #                 clothes_image_path=image_path,
    #                 clothes_type="Upper-body"
    #             )
                
    #         object_key = fitdit_response["object_key"]
    #         # VTONレコード作成
    #         vton_result = db.create_vton(
    #             tops_id=settings.default_tops_id,
    #             image_url=object_key
    #         )
    #         vton_id = vton_result.data[0]["id"]
            
    #         # ユーザーVTONレコード作成
    #         db.create_user_vton(
    #             user_id=request.user_id,
    #             vton_id=vton_id
    #         )
    #         object_key_list.append(object_key)
    #     except Exception as e:
    #         logger.error(f"リクエストの失敗: {e}")
    #         raise HTTPException(
    #             status_code=500,
    #             detail=f"VTONの生成に失敗しました: {str(e)}")
    
    return {"status": "success"}