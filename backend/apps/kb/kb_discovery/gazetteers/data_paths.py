from __future__ import annotations

from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parents[1] / "data"


def data_file(*parts: str) -> Path:
    return DATA_ROOT.joinpath(*parts)


__all__ = ["DATA_ROOT", "data_file"]
