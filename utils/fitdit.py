from httpx import AsyncClient, HTTPStatusError
from config import settings
import logging

logger = logging.getLogger(__name__)

async def execute_fitdit(body_image_path: str, clothes_image_path: str, clothes_type: str):
    async with AsyncClient(timeout=50) as client:
        try:
            request_data = {
                "body_image_path": body_image_path,
                "clothes_image_path": clothes_image_path,
                "clothes_type": clothes_type
            }
            logger.info(f"FitDit API呼び出し: {settings.fitdit_url}")
            logger.debug(f"FitDit API リクエスト内容: {request_data}")
            
            response = await client.post(
                settings.fitdit_url,
                json=request_data
            )
            
            logger.info(f"FitDit API レスポンス: {response.status_code}")
            logger.debug(f"FitDit API レスポンスヘッダー: {dict(response.headers)}")
            
            # レスポンスが空でないかチェック
            if not response.content:
                error_detail = f"HTTP Error: {response.status_code} - 空のレスポンス"
                logger.error(f"FitDit API エラー: {error_detail}")
                raise Exception(error_detail)
            
            try:
                response_data = response.json()
                logger.debug(f"FitDit API レスポンス内容: {response_data}")
            except ValueError as e:
                error_detail = f"HTTP Error: {response.status_code}"
                logger.error(f"FitDit API エラー: {error_detail}")
                raise Exception(error_detail)
            
            if response.status_code == 200:
                logger.info(f"FitDit API 成功: {response_data}")
                return response_data
            else:
                error_detail = f"HTTP Error: {response.status_code}"
                try:
                    error_data = response.json()
                    error_detail += f" - {error_data}"
                except:
                    error_detail += f" - {response.text}"
                
                logger.error(f"FitDit API エラー: {error_detail}")
                raise Exception(error_detail)
                
        except HTTPStatusError as e:
            logger.error(f"FitDit API HTTPStatusError: {e}")
            raise Exception(f"FitDit API接続エラー: {e}")
        except Exception as e:
            logger.error(f"FitDit API 予期しないエラー: {e}")
            if "timeout" in str(e).lower():
                raise Exception(f"FitDit API タイムアウトエラー: {e}")
            elif "connection" in str(e).lower():
                raise Exception(f"FitDit API 接続エラー: {e}")
            else:
                raise Exception(f"FitDit API エラー: {e}")