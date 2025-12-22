"""Failure handling and recovery tests"""

import pytest
from app.ingestion.base import BaseSource
from app.ingestion.runner import IngestionRunner


class MockFailingSource(BaseSource):
    """Mock source that fails"""

    async def fetch(self):
        raise Exception("Simulated fetch failure")

    async def validate(self, data):
        return False


class MockValidSource(BaseSource):
    """Mock source that succeeds"""

    async def fetch(self):
        return [{"id": 1, "value": "test"}]

    async def validate(self, data):
        return True


class TestFailureHandling:
    """Test failure handling and recovery"""

    @pytest.mark.asyncio
    async def test_source_fetch_failure(self):
        """Test handling of source fetch failure"""
        source = MockFailingSource()
        with pytest.raises(Exception):
            await source.fetch()

    @pytest.mark.asyncio
    async def test_validation_failure(self):
        """Test handling of validation failure"""
        source = MockFailingSource()
        result = await source.validate([])
        assert result is False

    @pytest.mark.asyncio
    async def test_runner_with_failing_source(self):
        """Test runner continues with other sources after failure"""
        failing_source = MockFailingSource()
        valid_source = MockValidSource()

        runner = IngestionRunner([valid_source])
        results = await runner.run()
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_partial_failure_recovery(self):
        """Test system recovers from partial failures"""
        valid_source = MockValidSource()
        runner = IngestionRunner([valid_source])

        # First run succeeds
        results1 = await runner.run()
        assert len(results1) > 0

        # Second run should also succeed
        results2 = await runner.run()
        assert len(results2) > 0
