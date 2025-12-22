"""Data API routes"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/data")
async def get_data():
    """Get data endpoint"""
    return {"message": "Data endpoint"}
