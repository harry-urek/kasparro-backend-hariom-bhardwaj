"""ETL checkpoint management"""

from datetime import datetime
from typing import Optional
import json
from pathlib import Path


class CheckpointManager:
    """Manages ETL checkpoints for incremental processing"""

    def __init__(self, checkpoint_dir: str = "checkpoints"):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(exist_ok=True)

    def save_checkpoint(self, source: str, checkpoint_data: dict):
        """Save checkpoint for a source"""
        checkpoint_file = self.checkpoint_dir / f"{source}.json"
        data = {"timestamp": datetime.utcnow().isoformat(), "data": checkpoint_data}
        with open(checkpoint_file, "w") as f:
            json.dump(data, f, indent=2)

    def load_checkpoint(self, source: str) -> Optional[dict]:
        """Load checkpoint for a source"""
        checkpoint_file = self.checkpoint_dir / f"{source}.json"
        if not checkpoint_file.exists():
            return None

        with open(checkpoint_file, "r") as f:
            data = json.load(f)
            return data.get("data")

    def get_last_run_time(self, source: str) -> Optional[datetime]:
        """Get last successful run time for a source"""
        checkpoint_file = self.checkpoint_dir / f"{source}.json"
        if not checkpoint_file.exists():
            return None

        with open(checkpoint_file, "r") as f:
            data = json.load(f)
            timestamp_str = data.get("timestamp")
            if timestamp_str:
                return datetime.fromisoformat(timestamp_str)
        return None

    def delete_checkpoint(self, source: str):
        """Delete checkpoint for a source"""
        checkpoint_file = self.checkpoint_dir / f"{source}.json"
        if checkpoint_file.exists():
            checkpoint_file.unlink()
