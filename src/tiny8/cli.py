"""Backward-compatibility wrapper forwarding to tiny8.tui."""

from .tui import *  # noqa: F401, F403
from .tui import main, run_cli

__all__ = ["main", "run_cli"]
