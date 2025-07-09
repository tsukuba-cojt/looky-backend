from fastapi import Header, HTTPException, status
from core.config import settings

async def verify_secret_key(x_internal_secret: str = Header(...)):
    """
    リクエストヘッダーのシークレットキーを検証する依存関係
    """
    if not settings.internal_api_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal API secret not configured on the server.",
        )

    if x_internal_secret != settings.internal_api_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid secret key.",
        )
    return True