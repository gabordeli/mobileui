"""Minimal Deluge stubs for running unit tests without Deluge installed."""

import sys
from pathlib import Path

try:
    import deluge  # noqa: F401
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).parent / "stubs"))
