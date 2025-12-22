"""Raw source schemas"""

from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime


class RawAPISchema(BaseModel):
    """Schema for raw API data"""

    id: Optional[str] = None
    data: dict
    timestamp: Optional[datetime] = None
    source: str = "api"


class RawCSVSchema(BaseModel):
    """Schema for raw CSV data"""

    row_number: Optional[int] = None
    data: dict
    source: str = "csv"


class RawThirdPartySchema(BaseModel):
    """Schema for raw third party data"""

    external_id: Optional[str] = None
    data: dict
    timestamp: Optional[datetime] = None
    source: str = "third_party"
