from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Protocol, cast


class StackScaffolder(Protocol):
    def scaffold(self, target: Path, name: str) -> dict[str, Any]: ...


_MODULE_NAMES = {
    "bare": "bare",
    "nextjs": "nextjs",
    "static": "static",
    "fastapi": "fastapi",
    "streamlit": "streamlit",
    "nextjs-fastapi": "nextjs_fastapi",
}


def get_scaffolder(stack: str) -> StackScaffolder:
    """Return the scaffolder module for the given stack name.

    Lazily imports the requested stack module so missing siblings don't fail
    package-level imports during incremental development (Phase 4 builds these
    modules one at a time).
    """
    if stack not in _MODULE_NAMES:
        raise ValueError(f"Unknown stack: {stack}")
    module = importlib.import_module(f".{_MODULE_NAMES[stack]}", package=__name__)
    return cast("StackScaffolder", module)
