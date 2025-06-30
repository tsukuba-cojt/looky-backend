import boto3
from botocore.exceptions import ClientError, BotoCoreError, NoCredentialsError
import logging
import os
import requests
from config import settings

logger = logging.getLogger(__name__)

# 設定クラスからAWS設定を取得
s3_client = boto3.client(
    "s3", 
    region_name=settings.aws_region_name, 
    aws_access_key_id=settings.aws_iam_access_key, 
    aws_secret_access_key=settings.aws_iam_secret_key
)

def get_image_from_s3(bucket_name: str, object_key: str) -> bytes:
    """
    S3バケットから指定されたキーの画像を取得する
    
    Args:
        bucket_name (str): S3バケット名
        object_key (str): オブジェクトのキー
    
    Returns:
        bytes: 画像データ
    
    Raises:
        ClientError: S3からの取得に失敗した場合
    """
    try:
        url = generate_presigned_url_for_get(bucket_name=bucket_name, object_key=object_key)
        response = requests.get(url)
        image_data = response.content
        logger.info(
            "Successfully retrieved image '%s' from bucket '%s'.",
            object_key,
            bucket_name
        )
        return image_data
    except ClientError as e:
        logger.exception(
            "Failed to retrieve image '%s' from bucket '%s'.",
            object_key,
            bucket_name
        )

# presigned urlを生成する.
# object_keyの例は`images/${new Date().toISOString().split('T')[0].replace(/-/g, '/')}/${timestamp}_${randomString}.${extension}`;
def generate_presigned_url_for_get(bucket_name: str, object_key: str, expiration: int = 3600) -> str:
    s3_client = boto3.client(
        "s3", 
        region_name=settings.aws_region_name, 
        aws_access_key_id=settings.aws_iam_access_key, 
        aws_secret_access_key=settings.aws_iam_secret_key
    )

    url = s3_client.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket_name, "Key": object_key},
        ExpiresIn=expiration
    )
    return url

def generate_presigned_url_for_upload(bucket_name: str, object_key: str, expiration: int = 3600) -> str:
    s3_client = boto3.client(
        "s3", 
        region_name=settings.aws_region_name, 
        aws_access_key_id=settings.aws_iam_access_key, 
        aws_secret_access_key=settings.aws_iam_secret_key
    )
    
    url = s3_client.generate_presigned_url(
        ClientMethod="put_object",
        Params={"Bucket": bucket_name, "Key": object_key},
        ExpiresIn=expiration
    )
    return url

# ファイルをアップロードする.
def upload_file_to_s3(presigned_url: str, image_data: bytes):
    """
    S3に画像データをアップロードする
    
    Args:
        presigned_url (str): アップロード用の署名付きURL
        image_data (bytes): アップロードする画像データ
    
    Returns:
        bytes: アップロード結果のレスポンス
    """
    try:
        response = requests.put(presigned_url, data=image_data)
        print("response in upload_file_to_s3", response)
    except Exception as e:
        raise Exception(f"Failed to upload file to S3: {e}")
    if response.status_code != 200:
        raise Exception(f"Failed to upload file to S3: {response.status_code}")
    else:
        return response.content

def download_if_needed(bucket_name: str, object_key: str, local_path: str) -> None:
    """ローカルに index が無ければ S3 から持ってくる"""
    if os.path.exists(local_path):
        print(f"[startup] {local_path} already exists")
        return
    session = boto3.Session(
        aws_access_key_id=settings.aws_iam_access_key,
        aws_secret_access_key=settings.aws_iam_secret_key,
        region_name=settings.aws_region_name,
    )
    s3 = session.resource("s3")
    try:
        print(f"[startup] downloading {bucket_name}/{object_key} -> {local_path}")
        s3.Bucket(bucket_name).download_file(object_key, local_path)
        
        # ダウンロード完了を確認
        if os.path.exists(local_path):
            file_size = os.path.getsize(local_path)
            print(f"[startup] download completed: {bucket_name}/{object_key} -> {local_path} (size: {file_size} bytes)")
        else:
            raise RuntimeError(f"Download failed: {local_path} does not exist after download")
            
    except (BotoCoreError, NoCredentialsError) as e:
        raise RuntimeError(f"failed to download index: {e}") from e