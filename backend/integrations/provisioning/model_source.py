"""Resolves a trained model from the Dana training folder: var/training/<run_id>/mmm_model.nc."""

from __future__ import annotations

import re
from pathlib import Path

from integrations.provisioning.models import ModelArtifact
from integrations.training.mmm.run_folder import MODEL_FILE

_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


class ModelNotFoundError(FileNotFoundError):
    pass


class LocalTrainingModelSource:
    def __init__(self, training_root: Path) -> None:
        self.training_root = training_root

    def resolve(self, run_id: str) -> ModelArtifact:
        if not _SAFE_RUN_ID.match(run_id):
            raise ValueError(f"Invalid run id: {run_id!r}")
        path = self.training_root / run_id / MODEL_FILE
        if not path.is_file():
            raise ModelNotFoundError(f"No trained model at {path}")
        size = path.stat().st_size
        if size == 0:
            raise ModelNotFoundError(f"Model file is empty: {path}")
        return ModelArtifact(run_id=run_id, path=path, size_bytes=size)
