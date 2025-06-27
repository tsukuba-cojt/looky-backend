import faiss
import torch
import glob
import os
import io
from PIL import Image
import numpy as np
from utils.s3 import get_image_from_s3

S3_CLOTHES_BUCKET_NAME = os.getenv("AWS_S3_CLOTHES_BUCKET_NAME")

# データベース画像の特徴ベクトルを抽出
# def generate_clip_embeddings_list(images_path, model, processor):
#     # 画像のあるフォルダへのパス
#     image_paths = glob.glob(os.path.join(images_path, '**/*.jpg'), recursive=True)
#     embeddings = []
#     for img_path in image_paths:
#         image = Image.open(img_path)
#         inputs = processor(text="", images=image, return_tensors="pt", padding=True)
#         outputs = model(**inputs)
#         embedding = outputs.image_embeds
#         embeddings.append(embedding)
#     return embeddings, image_paths

# def generate_clip_embedding(object_key, model, processor):
#     image = get_image_from_s3(bucket_name=S3_CLOTHES_BUCKET_NAME, object_key=object_key)
#     # 画像の前処理
#     image = Image.open(io.BytesIO(image)).convert("RGB")  # PIL.Imageに変換
#     inputs = processor(text="", images=image, return_tensors="pt", padding=True)
#     outputs = model(**inputs)
#     embedding = outputs.image_embeds
#     return embedding

# def create_faiss_index(embeddings, image_paths, output_path):
#     vectors = np.vstack([emb.squeeze(0).detach().cpu().numpy() for emb in embeddings]).astype(np.float32)
#     dimension = len(vectors[0])
#     index = faiss.IndexFlatIP(dimension) #内積類似とFlatインデックスの初期化
#     index = faiss.IndexIDMap(index)
#     #IDと特徴ベクトルの関連付ける
#     index.add_with_ids(vectors, np.array(range(len(embeddings))))
#     # インデックスを保存
#     faiss.write_index(index, output_path)
#     print(f"Index created and saved to {output_path}")
#     with open(output_path + '.paths', 'w') as f:
#         for img_path in image_paths:
#             f.write(img_path + '\n')
#     return index

def load_faiss_index(index_path):
    if not os.path.exists(index_path):
        raise FileNotFoundError(f"Index file not found: {index_path}")
    index = faiss.read_index(index_path)
    print(f"Index loaded from {index_path}")
    return index

# def update_faiss_index(new_embedding, new_image_path, index_path, model, processor):
#     # 既存のインデックスを読み込む
#     index = load_faiss_index(index_path)
    
#     # 新しい画像の特徴ベクトルを生成
#     if isinstance(new_image_path, str):
#         new_embedding = generate_clip_embedding(new_image_path, model, processor)
    
#     # 新しいベクトルをNumPy配列に変換
#     new_vector = new_embedding.squeeze(0).detach().cpu().numpy().astype(np.float32)
    
#     # インデックスに新しいベクトルを追加
#     index.add_with_ids(new_vector.reshape(1, -1), np.array([len(image_paths)]))
    
#     # 画像パスを更新
#     image_paths.append(new_image_path)
    
#     # 更新されたインデックスを保存
#     faiss.write_index(index, index_path)
#     with open(index_path + '.paths', 'a') as f:
#         f.write(new_image_path + '\n')
    
#     print(f"Index updated with new image: {new_image_path}")
#     return index, image_paths

# def retrieve_similar_images(query_image_path, model, processor, index, image_paths, top_k=3):
#     # image_pathsはローカルでパス管理前提であるが、実際はs3にあり、uuid等の値で画像を管理する
#     # 入力が画像パスの場合、PIL.Image に変換
#     if isinstance(query_image_path, str) and query_image_path.endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif')):
#         query_image_path = Image.open(query_image_path).convert("RGB")
    
#     # 画像の前処理
#     inputs = processor(text="",images=query_image_path, return_tensors="pt").to(model.device)
    
#     with torch.no_grad():
#         outputs = model(**inputs)
#         embedding = outputs.image_embeds

#     # → NumPyへ変換（この手順が重要）
#     query_features = embedding.detach().cpu().numpy().astype(np.float32).reshape(1, -1)

#     # 類似検索
#     distances, indices = index.search(query_features, top_k)
#     retrieved_images = [image_paths[int(idx)] for idx in indices[0]]
#     # retrieved_imagesはs3のobject_keyのリスト
#     return retrieved_images

def retrieve_similar_images_by_vector(vector, index, top_k=3):
    # faiss.index内のインデックスを返す
    indices = []

    # → NumPyへ変換
    if isinstance(vector, torch.Tensor):
        query_features = (
            vector.detach().cpu().numpy().astype(np.float32).reshape(1, -1)
        )
    else:  # NumPy ならそのまま
        query_features = np.asarray(vector, dtype=np.float32).reshape(1, -1)

    # 類似検索
    distances, indices = index.search(query_features, top_k)
    return indices[0]

# def retrieve_similar_images_by_text(query_text, model,processor, index, top_k=3):
#     text_inputs = processor(text=[query_text], return_tensors="pt").to(model.device)
    
#     with torch.no_grad():
#         text_emb = model.get_text_features(**text_inputs)   # (1, 512)

#     query_vec = text_emb / np.linalg.norm(text_emb, axis=-1, keepdims=True)

#     # 類似検索
#     distances, indices = index.search(query_vec, top_k)
#     return indices[0]

# # テキストクエリ
# query_text = 'tshirt'
# # テキストクエリの類似画像を検索
# retrieved_images = retrieve_similar_images_by_text(query_text, model, index, image_paths, top_k=3)

def mean_vector_from_ids(index_path: str, ids: list[int]) -> np.ndarray:
    index = load_faiss_index(index_path)  # ← IndexIDMap が返る

    # ① IndexIDMap だったら中身を取り出す
    if isinstance(index, (faiss.IndexIDMap, faiss.IndexIDMap2)):
        base_index = index.index          # ← IndexFlatIP など実体
        stored_ids = faiss.vector_to_array(index.id_map)  # 外部ID一覧
    else:
        base_index = index
        stored_ids = np.arange(index.ntotal)

    # ② 外部ID → 内部連番のマップを作る
    id2internal = {int(id_): pos for pos, id_ in enumerate(stored_ids)}

    # ③ 目的ベクトルを reconstruct して平均
    d = base_index.d
    buf = np.empty((len(ids), d), dtype="float32")

    for i, ext_id in enumerate(ids):
        try:
            base_index.reconstruct(id2internal[ext_id], buf[i])
        except KeyError:
            raise ValueError(f"id {ext_id} がインデックスに存在しません")

    return buf.mean(axis=0)


