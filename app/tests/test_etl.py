"""ETL service tests"""

import pytest
from app.services.etl_service import ETLService


class TestETLService:
    """Test ETL service functionality"""

    @pytest.fixture
    def etl_service(self):
        """Create ETL service instance"""
        return ETLService()

    @pytest.mark.asyncio
    async def test_extract(self, etl_service):
        """Test data extraction"""
        data = await etl_service.extract("api")
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_transform(self, etl_service):
        """Test data transformation"""
        sample_data = [{"id": 1, "value": "test"}]
        result = await etl_service.transform(sample_data)
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_load(self, etl_service):
        """Test data loading"""
        sample_data = [{"id": 1, "value": "test"}]
        success = await etl_service.load(sample_data)
        assert isinstance(success, bool)

    @pytest.mark.asyncio
    async def test_run_etl(self, etl_service):
        """Test complete ETL pipeline"""
        result = await etl_service.run_etl("api")
        assert "success" in result
        assert "records_processed" in result
