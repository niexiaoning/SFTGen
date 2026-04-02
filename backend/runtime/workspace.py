"""Workspace utilities for background task execution."""

from __future__ import annotations

import os
import shutil
import uuid


def setup_workspace(folder: str) -> tuple[str, str]:
    """Create an isolated working directory and its log file."""
    request_id = str(uuid.uuid4())
    os.makedirs(folder, exist_ok=True)

    working_dir = os.path.join(folder, request_id)
    os.makedirs(working_dir, exist_ok=True)

    log_dir = os.path.join(folder, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{request_id}.log")

    return log_file, working_dir


def cleanup_workspace(folder: str) -> None:
    """Remove a temporary working directory if it exists."""
    if os.path.exists(folder):
        shutil.rmtree(folder)
