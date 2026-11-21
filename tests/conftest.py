"""Shared fixtures for the image-workflow tests."""

from __future__ import annotations

import struct
from datetime import datetime
from pathlib import Path
from typing import Callable

import pytest
from PIL import ExifTags, Image

MAKE_TAG = 271
MODEL_TAG = 272
DATETIME_ORIGINAL_TAG = 36867
SUBSEC_TIME_ORIGINAL_TAG = 37521

ISO_BMFF_EPOCH = datetime(1904, 1, 1)


def _box(box_type: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body) + 8) + box_type + body


def _mvhd(creation_seconds: int, version: int) -> bytes:
    rest = (
        struct.pack(">I", 0x00010000)
        + b"\x01\x00"
        + b"\x00\x00"
        + b"\x00" * 8
        + struct.pack(
            ">9I",
            0x00010000,
            0,
            0,
            0,
            0x00010000,
            0,
            0,
            0,
            0x40000000,
        )
        + b"\x00" * 24
        + struct.pack(">I", 2)
    )
    if version == 1:
        body = (
            b"\x01\x00\x00\x00"
            + struct.pack(">QQIQ", creation_seconds, creation_seconds, 1000, 1000)
            + rest
        )
    else:
        body = (
            b"\x00\x00\x00\x00"
            + struct.pack(">IIII", creation_seconds, creation_seconds, 1000, 1000)
            + rest
        )
    return _box(b"mvhd", body)


def _hdlr(handler_type: bytes) -> bytes:
    body = b"\x00" * 4 + b"\x00" * 4 + handler_type + b"\x00" * 12 + b"\x00"
    return _box(b"hdlr", body)


def _meta(entries: list[tuple[str, str]]) -> bytes:
    if not entries:
        return b""

    keys_body = b"\x00" * 4 + struct.pack(">I", len(entries))
    ilst_body = b""
    for index, (key, value) in enumerate(entries, start=1):
        key_bytes = key.encode("utf-8")
        keys_body += struct.pack(">I", 8 + len(key_bytes)) + b"mdta" + key_bytes
        data_body = b"\x00\x00\x00\x01" + b"\x00\x00\x00\x00" + value.encode("utf-8")
        ilst_body += _box(index.to_bytes(4, "big"), _box(b"data", data_body))

    return _box(
        b"meta", b"\x00" * 4 + _box(b"keys", keys_body) + _box(b"ilst", ilst_body)
    )


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


@pytest.fixture
def make_video(tmp_path: Path) -> Callable[..., Path]:
    """Create a minimal ISO-BMFF video at ``tmp_path / relative_path``."""

    def _make(
        relative_path: str,
        *,
        creation_time: datetime | None = datetime(2025, 8, 9, 19, 51, 21),
        creation_seconds: int | None = None,
        version: int = 0,
        android_make: str | None = "Google",
        android_model: str | None = "Pixel 6",
        apple_make: str | None = None,
        apple_model: str | None = None,
        apple_creation_date: str | None = None,
        udta_make: str | None = None,
        udta_model: str | None = None,
        udta_day: str | None = None,
        video_track: bool = True,
        ftyp: bool = True,
    ) -> Path:
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)

        if creation_seconds is None:
            if creation_time is None:
                creation_seconds = 0
            else:
                creation_seconds = int((creation_time - ISO_BMFF_EPOCH).total_seconds())

        entries: list[tuple[str, str]] = []
        if android_make is not None:
            entries.append(("com.android.manufacturer", android_make))
        if android_model is not None:
            entries.append(("com.android.model", android_model))
        if apple_make is not None:
            entries.append(("com.apple.quicktime.make", apple_make))
        if apple_model is not None:
            entries.append(("com.apple.quicktime.model", apple_model))
        if apple_creation_date is not None:
            entries.append(("com.apple.quicktime.creationdate", apple_creation_date))

        udta_body = b""
        if udta_make is not None:
            udta_body += _box(b"\xa9mak", udta_make.encode("utf-8"))
        if udta_model is not None:
            udta_body += _box(b"\xa9mod", udta_model.encode("utf-8"))
        if udta_day is not None:
            udta_body += _box(b"\xa9day", udta_day.encode("utf-8"))

        moov_body = _mvhd(creation_seconds, version)
        moov_body += _box(
            b"trak",
            _box(b"mdia", _hdlr(b"vide" if video_track else b"soun")),
        )
        moov_body += _meta(entries)
        if udta_body:
            moov_body += _box(b"udta", udta_body)

        data = b""
        if ftyp:
            data += _box(
                b"ftyp",
                b"isom" + struct.pack(">I", 0x200) + b"isomiso2mp41",
            )
        data += _box(b"moov", moov_body)
        data += _box(b"mdat", b"\x00" * 8)

        path.write_bytes(data)
        return path

    return _make
