"""Abstract source interface"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseSource(ABC):
    """Abstract base class for data sources"""

    @abstractmethod
    async def fetch(self) -> List[Dict[str, Any]]:
        """Fetch data from source"""
        pass

    @abstractmethod
    async def validate(self, data: List[Dict[str, Any]]) -> bool:
        """Validate fetched data"""
        pass
