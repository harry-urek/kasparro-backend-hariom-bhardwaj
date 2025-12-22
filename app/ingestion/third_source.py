"""Third party source implementation"""

from typing import List, Dict, Any
from .base import BaseSource


class ThirdSource(BaseSource):
    """Third party data source"""

    def __init__(self, config: dict):
        self.config = config

    async def fetch(self) -> List[Dict[str, Any]]:
        """Fetch data from third party source"""
        # TODO: Implement third party data fetching
        return []

    async def validate(self, data: List[Dict[str, Any]]) -> bool:
        """Validate third party data"""
        # TODO: Implement validation logic
        return True
