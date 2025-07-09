import faiss
import torch
import os
import numpy as np
import logging
logger = logging.getLogger(__name__)

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
    logger.info(f"Index loaded from {index_path}")
    return index


def retrieve_similar_images_by_vector(vector, index, top_k=10, exclude_selector=None):
    """
    ベクトルを受け取って、類似するベクトルを返す
    args:
        vector: torch.Tensor
        index: faiss.Index
        top_k: int
        exclude_selector: faiss.IDSelector
    returns:
        indices: list[int]
    """
    if isinstance(vector, torch.Tensor):
        query_features = (
            vector.detach().cpu().numpy().astype(np.float32).reshape(1, -1)
        )
    else:
        query_features = np.asarray(vector, dtype=np.float32).reshape(1, -1)
        
    params = faiss.SearchParametersIVF()
    params.sel = exclude_selector

    # 類似検索
    distances, indices = index.search(query_features, top_k, params=params)
    
    # 検索結果が空の場合の処理
    if len(indices[0]) == 0:
        raise ValueError("検索条件に一致する画像が見つかりませんでした")
    
    return indices[0]

def sum_vector_from_ids(ids: list[int], faiss_index: faiss.Index) -> np.ndarray:
    """
    洋服IDリストでベクトルを合計する
    args:
        ids: list[int]
        faiss_index: faiss.Index
    returns:
        vector: np.ndarray
    """
    if not ids:
        # 空のリストの場合はゼロベクトルを返す
        return np.zeros(faiss_index.d)
    
    index = faiss_index

    # ① IndexIDMap だったら中身を取り出す
    if isinstance(index, (faiss.IndexIDMap, faiss.IndexIDMap2)):
        base_index = index.index          # ← IndexFlatIP など実体
        stored_ids = faiss.vector_to_array(index.id_map)  # 外部ID一覧
    else:
        base_index = index
        stored_ids = np.arange(index.ntotal)

    # ② 外部ID → 内部連番のマップを作る
    id2internal = {int(id_): pos for pos, id_ in enumerate(stored_ids)}

    # ③ 目的ベクトルを reconstruct して合計
    d = base_index.d
    buf = np.empty((len(ids), d), dtype="float32")

    for i, ext_id in enumerate(ids):
        try:
            base_index.reconstruct(id2internal[ext_id], buf[i])
        except KeyError:
            raise ValueError(f"id {ext_id} がインデックスに存在しません")

    return buf.sum(axis=0)

def get_preference_vector(like_ids: list[int], love_ids: list[int], hate_ids: list[int], index: faiss.Index):
    """
    フィードバックによる好みベクトルを生成
    args:
        like_ids: list[int]
        love_ids: list[int]
        hate_ids: list[int]
        index: faiss.Index
    returns:
        vector: np.ndarray
    """
    # like, love, hateそれぞれのベクトル和を計算
    like_vector = sum_vector_from_ids(faiss_index=index, ids=like_ids)
    love_vector = sum_vector_from_ids(faiss_index=index, ids=love_ids)
    hate_vector = sum_vector_from_ids(faiss_index=index, ids=hate_ids)
    
    # ベクトルは正規化されているので重みづけ和を取る
    # like: 等倍(1倍), love: 2倍, hate: -1倍
    vector = like_vector + (2 * love_vector) - hate_vector
    
    # ゼロベクトルの場合はランダムベクトルを生成
    vector_norm = np.linalg.norm(vector)
    if vector_norm == 0:
        # すべてのフィードバックが空の場合、ランダムベクトルを生成
        vector = np.random.randn(index.d).astype(np.float32)
        vector = vector / np.linalg.norm(vector)
    else:
        # ベクトルを正規化
        vector = vector / vector_norm
    
    return vector