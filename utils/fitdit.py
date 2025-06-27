from fastapi import FastAPI
from httpx import AsyncClient

import os

FITDIT_URL = os.getenv("FITDIT_URL")


async def execute_fitdit(body_image_path: str, clothes_image_path: str, clothes_type: str):
    async with AsyncClient(timeout=50) as client:
        response = await client.post(
            FITDIT_URL,
            json={
                "body_image_path": body_image_path,
                "clothes_image_path": clothes_image_path,
                "clothes_type": clothes_type
            }
        )
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"HTTP Error: {response.status_code}")

