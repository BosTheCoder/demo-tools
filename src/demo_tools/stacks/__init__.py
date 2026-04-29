from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class StackScaffolder(Protocol):
    def scaffold(self, target: Path, name: str) -> dict[str, Any]: ...


def get_scaffolder(stack: str) -> StackScaffolder:
    """Return the scaffolder module for the given stack name."""
    import importlib

    module_names = {
        "bare": "bare",
        "nextjs": "nextjs",
        "static": "static",
        "fastapi": "fastapi",
        "streamlit": "streamlit",
        "nextjs-fastapi": "nextjs_fastapi",
    }
    if stack not in module_names:
        raise ValueError(f"Unknown stack: {stack}")
    return importlib.import_module(f".{module_names[stack]}", package=__name__)
