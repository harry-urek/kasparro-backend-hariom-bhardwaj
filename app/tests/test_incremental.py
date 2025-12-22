"""Incremental loading tests"""

import pytest
from datetime import datetime
from app.core.checkpoints import CheckpointManager


class TestIncrementalLoading:
    """Test incremental data loading functionality"""

    @pytest.fixture
    def checkpoint_manager(self, tmp_path):
        """Create checkpoint manager with temp directory"""
        return CheckpointManager(str(tmp_path))

    def test_save_checkpoint(self, checkpoint_manager):
        """Test saving checkpoint"""
        checkpoint_data = {"last_id": 100, "last_timestamp": datetime.utcnow().isoformat()}
        checkpoint_manager.save_checkpoint("api", checkpoint_data)

        loaded = checkpoint_manager.load_checkpoint("api")
        assert loaded is not None
        assert loaded["last_id"] == 100

    def test_load_nonexistent_checkpoint(self, checkpoint_manager):
        """Test loading non-existent checkpoint"""
        result = checkpoint_manager.load_checkpoint("nonexistent")
        assert result is None

    def test_get_last_run_time(self, checkpoint_manager):
        """Test getting last run time"""
        checkpoint_data = {"last_id": 100}
        checkpoint_manager.save_checkpoint("api", checkpoint_data)

        last_run = checkpoint_manager.get_last_run_time("api")
        assert isinstance(last_run, datetime)

    def test_delete_checkpoint(self, checkpoint_manager):
        """Test deleting checkpoint"""
        checkpoint_data = {"last_id": 100}
        checkpoint_manager.save_checkpoint("api", checkpoint_data)

        checkpoint_manager.delete_checkpoint("api")
        result = checkpoint_manager.load_checkpoint("api")
        assert result is None
