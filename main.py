from fastapi import FastAPI, HTTPException
from typing import List
import asyncio
from utils.s3 import get_image_from_s3
import os
from PIL import Image
import io
import time
import torch
import open_clip
from utils.clipFaiss import (
    retrieve_similar_images_by_vector,
    load_faiss_index,
    # create_faiss_index,
    # generate_clip_embeddings_list,
    mean_vector_from_ids
)
from utils.s3 import download_if_needed
from utils.fitdit import execute_fitdit
from utils.supabase_util import create_client, Client
from pydantic import BaseModel
from fastapi.responses import StreamingResponse

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)



S3_CLOTHES_BUCKET_NAME = os.getenv("AWS_S3_CLOTHES_BUCKET_NAME")
S3_VTON_BUCKET_NAME = os.getenv("AWS_S3_VTON_BUCKET_NAME")
INDEX_BUCKET_NAME = os.getenv("AWS_S3_INDEX_BUCKET_NAME")
BODY_IMAGE_BUCKET_NAME = os.getenv("AWS_S3_BODY_IMAGE_BUCKET_NAME")
INDEX_KEY = os.getenv("AWS_S3_INDEX_KEY_NAME")
LOCAL_INDEX_PATH = f"../tmp/{INDEX_KEY}"
MODEL_NAME = "patrickjohncyh/fashion-clip"

app = FastAPI()
device = "cuda" if torch.cuda.is_available() else "cpu"

# モデルとプロセッサのロード
model = None
preprocess_train = None
preprocess_val = None
tokenizer = None
index = None

@app.on_event("startup")
async def startup_event():
    start = time.time()
    print(f"STARTUP: S3ダウンロード開始 {time.time() - start:.2f}s")
    global model, preprocess_train, preprocess_val, tokenizer, index
    download_if_needed(INDEX_BUCKET_NAME, INDEX_KEY, LOCAL_INDEX_PATH)
    print(f"STARTUP: S3ダウンロード完了 {time.time() - start:.2f}s")
    print(f"STARTUP: モデルロード開始 {time.time() - start:.2f}s")

    # モデル・前処理・トークナイザーを並列でロード
    model_and_preprocess, tokenizer = await asyncio.gather(
        asyncio.to_thread(open_clip.create_model_and_transforms, 'hf-hub:Marqo/marqo-fashionSigLIP'),
        asyncio.to_thread(open_clip.get_tokenizer, 'hf-hub:Marqo/marqo-fashionSigLIP')
    )
    model, preprocess_train, preprocess_val = model_and_preprocess
    model = model.to(device)
    model.eval()
    print(f"STARTUP: モデルロード完了 {time.time() - start:.2f}s")

    print(f"{LOCAL_INDEX_PATH}のインデックスのロードを開始します...")
    try:
        index = await asyncio.to_thread(load_faiss_index, LOCAL_INDEX_PATH)
        print("既存のインデックスをロードしました")
    except FileNotFoundError:
        # print("インデックスが見つかりません。新規作成を開始します...")
        # # 初回はインデックスを作成
        # embeddings, image_paths = await asyncio.to_thread(
        #     generate_clip_embeddings_list,
        #     IMAGES_PATH,
        #     model,
        #     preprocess_train  # ここでpreprocess_trainを渡す
        # )
        # index = await asyncio.to_thread(
        #     create_faiss_index,
        #     embeddings,
        #     image_paths,
        #     LOCAL_INDEX_PATH
        # )
        # print("新しいインデックスを作成しました")
        print("インデックスが見つかりません。終了してください。")
    print(f"STARTUP: インデックスロード完了 {time.time() - start:.2f}s")

#--------------------
# test API
#--------------------

@app.get("/")
def read_root():
    return {"message": "Hello, Docker + FastAPI!"}

@app.get("/watch")
def watch():
    image = get_image_from_s3(bucket_name=S3_VTON_BUCKET_NAME, object_key="5df1144a-cd73-4a18-ab3d-66d699e3fa1a_20250627")
    return StreamingResponse(io.BytesIO(image), media_type="image/png")

#--------------------
# MVP(Minimum Viable Product)
#--------------------

class UserIdRequest(BaseModel):
    user_id: str

@app.post("/user/clothes/recommend")
async def get_recommendation_clothes(request: UserIdRequest):
    start = time.time()
    print(f"get_recommendation_clothes: 開始 {time.time() - start:.2f}s")
    request.user_id
    # 本番ではユーザーのidを取得して使用
    user = supabase.table("t_user").select().eq("id", request.user_id).execute()
    body_object_key = user.data[0]["body_url"]
    if not body_object_key:
        return {"message": "body_urlがありません"}
    preference_list = supabase.table("t_user_vton").select().eq("feedback_flag", 1).eq("user_id", request.user_id).execute()
    if not preference_list.data:
        print("いいねしたデータがありません。ランダムな洋服を推薦します")
        # ランダムな洋服を推薦する処理
        preference_vector = mean_vector_from_ids(index_path=LOCAL_INDEX_PATH, ids=[129,130])
    else:
        vton_ids = [item["vton_id"] for item in preference_list.data]
        clothes_ids = []
        for vton_id in vton_ids:
            clothes_ids.append(supabase.table("t_vton").select().eq("id", vton_id).execute().data[0]["tops_id"])
        preference_vector = mean_vector_from_ids(index_path=LOCAL_INDEX_PATH, ids=clothes_ids)
    indices = retrieve_similar_images_by_vector(vector=preference_vector, index=index, top_k=3)
    retrieved_images = supabase.table("t_clothes").select().in_("id", indices).execute().data
    retrieved_images_keys = [item["image_url"] for item in retrieved_images]
    print("洋服(retrieved_images)と全身画像(body_image)を組み合わせて画像を作成します")
    object_key_list = []
    print(f"get_recommendation_clothes: 洋服(retrieved_images)と全身画像(body_image)を組み合わせて画像を作成します {time.time() - start:.2f}s")
    for image_path in retrieved_images_keys:
        try:
            object_key = await execute_fitdit(
                body_image_path=body_object_key,
                clothes_image_path=image_path,
                clothes_type="Upper-body"
            )
            result = supabase.table("t_vton").insert({
                "tops_id": 1,
                "image_url": object_key,
                }).execute()
            vton_id = result.data[0]["id"]
            supabase.table("t_user_vton").insert({
                "user_id": request.user_id,
                "vton_id": vton_id,
                "feedback_flag": 0
            })
            object_key_list.append(object_key)
        except Exception as e:
            print(f"洋服の画像の保存に失敗しました: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"洋服の画像の保存に失敗しました: {str(e)}")
    print(f"get_recommendation_clothes: 組み合わせ結果の画像を取得しました.アプリに送信します {time.time() - start:.2f}s")
    return {"object_key_list": object_key_list}

#--------------------
# 今後追加予定のAPI
#--------------------

# @app.get("/user/save_clothes_vector")
# def save_clothes_vector(object_key: str):
#     """
#     ユーザーの持つ洋服をベクトル化して保存するAPI

#     テスト用に現在は画像を表示させてる
#     """
#     texts=["a photo of a hoodie", "a photo of a white clothes", "a photo of a long sleeve shirt"]
#     print("urlから洋服の画像を取得します")
#     image_data = get_image_from_s3(bucket_name=S3_CLOTHES_BUCKET_NAME, object_key=object_key)
#     image = Image.open(io.BytesIO(image_data))
#     # 入力データの準備
#     inputs = tokenizer(text=texts, images=image, return_tensors="pt", padding=True)
    
#     # モデルによる推論
#     outputs = model(**inputs)
    
#     # 特徴ベクトルの取得
#     image_features = outputs.image_embeds
#     text_features = outputs.text_embeds
#     # 洋服画像のベクトル化
#     # image_vector, text_vector = get_image_vector(
#     #     image_data=image_data,
#     #     texts=["a photo of a hoodie", "a photo of a white clothes", "a photo of a long sleeve shirt"]
#     # )
    
#     print("画像ベクトルの形状:", image_features.shape)
#     print("テキストベクトルの形状:", text_features.shape)
    
#     print("ベクトル化した値とurlを保存します")
#     return {"message": f"洋服画像のベクトル形状: {image_features.shape}, 洋服画像のurl: {object_key}"}


# @app.post("/user/init_preference_data")
# def save_preference_data(preference_data: List[str], user_id: str):
#     """
#     洋服の好みのデータを初期化して保存するAPI
#     """
#     print("洋服の好みのデータをベクトル化")
#     print("ユーザーidと洋服の好みのデータを保存")
#     return {"message": f"洋服の好みのデータをベクトル化して保存しました: {preference_data}"}