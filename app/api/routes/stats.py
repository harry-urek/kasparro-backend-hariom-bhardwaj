"""Statistics API routes"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/stats")
async def get_stats():
    """Get statistics endpoint"""
    return {"message": "Stats endpoint"}
