"""Shared fixtures for the image-workflow tests."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest
from PIL import ExifTags, Image

MAKE_TAG = 271
MODEL_TAG = 272
DATETIME_ORIGINAL_TAG = 36867
SUBSEC_TIME_ORIGINAL_TAG = 37521


@pytest.fixture
def source(tmp_path: Path) -> Path:
    """An empty incoming-photos directory."""

    path = tmp_path / "incoming"
    path.mkdir()
    return path


@pytest.fixture
def make_image(tmp_path: Path) -> Callable[..., Path]:
    """Create a fake image with EXIF metadata at ``tmp_path / relative_path``."""

    def _make(
        relative_path: str,
        *,
        make: str | None = "Canon",
        model: str | None = "EOS 5D",
        datetime_original: str | None = "2024:07:15 12:34:56",
        subsec: str | None = None,
        exif_ifd: bool = True,
        color: tuple[int, int, int] = (120, 40, 60),
    ) -> Path:
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)

        image = Image.new("RGB", (48, 32), color)
        exif = Image.Exif()
        if make is not None:
            exif[MAKE_TAG] = make
        if model is not None:
            exif[MODEL_TAG] = model

        nested: dict[int, str] = {}
        if datetime_original is not None:
            nested[DATETIME_ORIGINAL_TAG] = datetime_original
        if subsec is not None:
            nested[SUBSEC_TIME_ORIGINAL_TAG] = subsec

        if exif_ifd:
            if nested:
                # Real camera files put these tags in the Exif sub-IFD.
                exif[ExifTags.IFD.Exif] = nested
        else:
            # Some writers put the same tags directly in IFD0.
            for tag, value in nested.items():
                exif[tag] = value

        image.save(path, exif=exif)
        return path

    return _make
