from httpx import AsyncClient
from config import settings
import logging

logger = logging.getLogger(__name__)

async def execute_fitdit(body_image_path: str, clothes_image_path: str, clothes_type: str):
    async with AsyncClient(timeout=50) as client:
        request_data = {
            "body_image_path": body_image_path,
            "clothes_image_path": clothes_image_path,
            "clothes_type": clothes_type
        }
        
        logger.info(f"FitDit API呼び出し: {settings.fitdit_url}")
        
        response = await client.post(
            f"{settings.fitdit_url}/vton",
            json=request_data
        )
        
        response.raise_for_status()
        response_data = response.json()
        logger.info(f"FitDit API レスポンス型: {type(response_data)}")
        logger.info(f"FitDit API レスポンス内容: {response_data}")
        return response_data