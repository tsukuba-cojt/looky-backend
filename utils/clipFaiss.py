import faiss
import torch
import os
import numpy as np

S3_CLOTHES_BUCKET_NAME = os.getenv("AWS_S3_CLOTHES_BUCKET_NAME")

def load_faiss_index(index_path):
    """
    faissのインデックスをロードする
    args:
        index_path: str
    returns:
        index: faiss.Index
    """
    if not os.path.exists(index_path):
        raise FileNotFoundError(f"Index file not found: {index_path}")
    index = faiss.read_index(index_path)
    print(f"Index loaded from {index_path}")
    return index


def retrieve_similar_images_by_vector(vector, index, top_k=10):
    """
    ベクトルを受け取って、類似するベクトルを返す
    args:
        vector: torch.Tensor
        index: faiss.Index
        top_k: int
    returns:
        indices: list[int]
    """
    if isinstance(vector, torch.Tensor):
        query_features = (
            vector.detach().cpu().numpy().astype(np.float32).reshape(1, -1)
        )
    else:
        query_features = np.asarray(vector, dtype=np.float32).reshape(1, -1)

    # 類似検索
    distances, indices = index.search(query_features, top_k)
    
    return indices[0]

def mean_vector_from_ids(ids: list[int], faiss_index: faiss.Index) -> np.ndarray:
    # 空のリストが渡された場合の処理
    if not ids:
        raise ValueError("空のIDリストが渡されました")
    
    index = faiss_index  # ← IndexIDMap が返る

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


