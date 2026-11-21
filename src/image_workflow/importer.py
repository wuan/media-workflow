"""Import camera photos and videos into a ``YYYY/MM`` archive tree.

This is a Python port of the original ``import.sh`` exiftool one-liner.  The
original command was::

    exiftool -v -fast2 \
      -if '$Make and $Model and $DateTimeOriginal' \
      -m -d '%Y/%m/%Y%m%d_%H%M%S' -P \
      '-filename<${DateTimeOriginal}${SubSecTimeOriginal;$_ = $_ ? "." . $_ : ""}_${Make;tr/ /-/;s/--+/-/g}_${Model;tr/ /-/;s/--+/-/g}%+c.${FileTypeExtension}' \
      "$SOURCE"

The port keeps the same naming rules:

* files must contain ``Make``, ``Model`` and ``DateTimeOriginal``;
* the destination is ``<destination>/<year>/<month>/``;
* the name is ``YYYYMMDD_HHMMSS[.SubSec]_Make_Model.ext``;
* spaces in make/model become ``-`` and runs of ``-`` are collapsed;
* the extension is exiftool's ``FileTypeExtension`` (``JPEG`` -> ``jpg``);
* collisions get exiftool's copy-number suffix: ``_1``, ``_2``, ...;
* an existing file that already has the computed name is left untouched;
* the original bytes and file modification time are preserved.

Videos in ISO base media containers (``.mp4``, ``.mov``, ``.m4v``, ``.3gp``)
are also supported.  Their make/model metadata comes from Android or Apple
QuickTime keys, while the timestamp is read from a camera filename segment
such as ``PXL_20250809_194948618`` when present, falling back to the
QuickTime movie-header creation time.

Unlike exiftool's relative ``-filename`` path, the destination is explicit and
defaults to the current working directory, matching the usual invocation from
the archive root (``image-workflow import ../photos_incoming``).
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import BinaryIO, Iterable, Iterator, Literal

from PIL import ExifTags, Image, UnidentifiedImageError

MAKE_TAG = 271
MODEL_TAG = 272
DATETIME_ORIGINAL_TAG = 36867
SUBSEC_TIME_ORIGINAL_TAG = 37521

EXIF_IFD = ExifTags.IFD.Exif

# exiftool's FileTypeExtension is lower-case and uses "jpg"/"tif" for
# JPEG/TIFF, regardless of the source file suffix.
_EXTENSION_BY_FORMAT = {
    "JPEG": "jpg",
    "TIFF": "tif",
}

_DATETIME_RE = re.compile(
    r"^(?P<year>\d{4}):(?P<month>\d{2}):(?P<day>\d{2})[ T]"
    r"(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})"
)

_FILENAME_TIMESTAMP_RE = re.compile(
    r"(?<!\d)(?P<date>\d{8})_(?P<time>\d{6})(?P<milliseconds>\d{3})?(?!\d)"
)

VIDEO_SUFFIXES = frozenset({".mp4", ".mov", ".m4v", ".3gp"})
UNSUPPORTED_VIDEO_SUFFIXES = frozenset(
    {".avi", ".flv", ".m2ts", ".mkv", ".mpg", ".mpeg", ".mts", ".ts", ".webm", ".wmv"}
)

_ISO_BMFF_EPOCH = datetime(1904, 1, 1)
_MAX_METADATA_BOX_SIZE = 4 * 1024 * 1024

_ANDROID_MAKE_KEY = "com.android.manufacturer"
_ANDROID_MODEL_KEY = "com.android.model"
_APPLE_MAKE_KEY = "com.apple.quicktime.make"
_APPLE_MODEL_KEY = "com.apple.quicktime.model"

ImportStatus = Literal["moved", "would_move", "unchanged", "skipped", "failed"]


@dataclass(frozen=True)
class ExifMetadata:
    """The metadata needed to build an archive filename.

    The name is historical: the same structure now carries video metadata as
    well as photo EXIF metadata.
    """

    make: str
    model: str
    datetime_original: datetime
    subsec_time_original: str | None
    file_type_extension: str


@dataclass(frozen=True)
class ImportResult:
    """Outcome of attempting to import one source file."""

    source: Path
    destination: Path | None
    status: ImportStatus
    reason: str | None = None


class NotAnImageError(Exception):
    """The file is not an image format that Pillow can read."""


class NotASupportedVideoError(Exception):
    """The file is not a video container this importer can read."""


class MetadataError(Exception):
    """The image or video could not be read, or its metadata is unusable."""


@dataclass(frozen=True)
class _Box:
    """An ISO-BMFF box, with offsets relative to the containing stream."""

    type: bytes
    body_start: int
    end: int


class _BoxError(Exception):
    """The ISO-BMFF structure is truncated or malformed."""


@dataclass
class _VideoInfo:
    """Metadata collected from an ISO-BMFF video."""

    has_ftyp: bool = False
    has_video_track: bool = False
    creation_time: datetime | None = None
    make: str | None = None
    model: str | None = None


def _as_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    text = str(value).strip().strip("\x00")
    return text or None


def _exif_value(exif: Image.Exif, tag: int) -> object | None:
    """Read a tag from IFD0, falling back to the Exif sub-IFD.

    Cameras usually store ``DateTimeOriginal`` and ``SubSecTimeOriginal`` in
    the Exif sub-IFD while Pillow's ``getexif()`` only exposes IFD0 directly.
    Some test images (and some tools) put those tags in IFD0 instead, so both
    locations are checked.
    """

    value = exif.get(tag)
    if value is not None:
        return value
    try:
        return exif.get_ifd(EXIF_IFD).get(tag)
    except Exception:
        # Malformed sub-IFDs are treated as missing metadata.  Date/time tags
        # are also accepted from IFD0, so a broken sub-IFD is not fatal.
        return None


def _file_type_extension(image_format: str | None, suffix: str) -> str:
    if image_format:
        return _EXTENSION_BY_FORMAT.get(image_format.upper(), image_format.lower())
    return suffix.lower().lstrip(".")


def _read_box_header(stream: BinaryIO, limit: int) -> _Box | None:
    start = stream.tell()
    header = stream.read(8)
    if len(header) < 8:
        return None

    size = int.from_bytes(header[:4], "big")
    box_type = header[4:8]
    header_size = 8

    if size == 1:
        extended = stream.read(8)
        if len(extended) < 8:
            raise _BoxError("truncated extended box size")
        size = int.from_bytes(extended, "big")
        header_size = 16
    elif size == 0:
        size = limit - start

    if size < header_size or start + size > limit:
        raise _BoxError(f"invalid {box_type!r} box size")

    stream.seek(start + header_size)
    return _Box(box_type, start + header_size, start + size)


def _iter_boxes(stream: BinaryIO, start: int, end: int) -> Iterator[_Box]:
    stream.seek(start)
    while stream.tell() + 8 <= end:
        box = _read_box_header(stream, end)
        if box is None:
            break
        yield box
        stream.seek(box.end)


def _iter_boxes_bytes(
    data: bytes, start: int = 0, end: int | None = None
) -> Iterator[_Box]:
    limit = len(data) if end is None else end
    offset = start
    while offset + 8 <= limit:
        size = int.from_bytes(data[offset : offset + 4], "big")
        box_type = data[offset + 4 : offset + 8]
        header_size = 8

        if size == 1:
            if offset + 16 > limit:
                raise _BoxError("truncated extended box size")
            size = int.from_bytes(data[offset + 8 : offset + 16], "big")
            header_size = 16
        elif size == 0:
            size = limit - offset

        if size < header_size or offset + size > limit:
            raise _BoxError(f"invalid {box_type!r} box size")

        yield _Box(box_type, offset + header_size, offset + size)
        offset += size


def _read_box_body(
    stream: BinaryIO, box: _Box, *, max_size: int = _MAX_METADATA_BOX_SIZE
) -> bytes:
    size = box.end - box.body_start
    if size > max_size:
        raise _BoxError(f"{box.type!r} box is too large")
    stream.seek(box.body_start)
    body = stream.read(size)
    if len(body) != size:
        raise _BoxError(f"truncated {box.type!r} box")
    return body


def _slice_box_body(data: bytes, box: _Box) -> bytes:
    return data[box.body_start : box.end]


def _decode_text(value: bytes) -> str | None:
    text = value.decode("utf-8", "replace").strip().strip("\x00")
    return text or None


def _parse_data_box(body: bytes) -> str | None:
    """Return the UTF-8 payload from a QuickTime ``data`` box body."""

    if len(body) < 8:
        return None
    data_type = int.from_bytes(body[:4], "big")
    if data_type != 1:
        return None
    return _decode_text(body[8:])


def _parse_text_box(body: bytes) -> str | None:
    """Read a text tag that may be raw text or contain a ``data`` child."""

    try:
        for box in _iter_boxes_bytes(body, 0, len(body)):
            if box.type == b"data":
                return _parse_data_box(_slice_box_body(body, box))
    except _BoxError:
        pass
    return _decode_text(body)


def _parse_keys(body: bytes) -> list[str]:
    if len(body) < 8:
        raise _BoxError("truncated keys box")

    count = int.from_bytes(body[4:8], "big")
    offset = 8
    keys: list[str] = []
    for _ in range(count):
        if offset + 8 > len(body):
            raise _BoxError("truncated keys entry")
        size = int.from_bytes(body[offset : offset + 4], "big")
        if size < 8 or offset + size > len(body):
            raise _BoxError("invalid keys entry size")
        keys.append(body[offset + 8 : offset + size].decode("utf-8", "replace"))
        offset += size
    return keys


def _apply_metadata_keys(keys: list[str], ilst_body: bytes, info: _VideoInfo) -> None:
    for box in _iter_boxes_bytes(ilst_body, 0, len(ilst_body)):
        index = int.from_bytes(box.type, "big")
        if index < 1 or index > len(keys):
            continue

        value = None
        for data_box in _iter_boxes_bytes(ilst_body, box.body_start, box.end):
            if data_box.type == b"data":
                value = _parse_data_box(_slice_box_body(ilst_body, data_box))
                break
        if value is None:
            continue

        key = keys[index - 1]
        if key == _ANDROID_MAKE_KEY:
            info.make = value
        elif key == _ANDROID_MODEL_KEY:
            info.model = value
        elif key == _APPLE_MAKE_KEY:
            info.make = info.make or value
        elif key == _APPLE_MODEL_KEY:
            info.model = info.model or value


def _parse_meta(stream: BinaryIO, meta_box: _Box, info: _VideoInfo) -> None:
    keys: list[str] = []
    ilst_body: bytes | None = None

    # The meta box is a full box: four bytes of version/flags before children.
    for box in _iter_boxes(stream, meta_box.body_start + 4, meta_box.end):
        if box.type == b"keys":
            keys = _parse_keys(_read_box_body(stream, box))
        elif box.type == b"ilst":
            ilst_body = _read_box_body(stream, box)

    if keys and ilst_body is not None:
        _apply_metadata_keys(keys, ilst_body, info)


def _parse_udta(stream: BinaryIO, udta_box: _Box, info: _VideoInfo) -> None:
    for box in _iter_boxes(stream, udta_box.body_start, udta_box.end):
        if box.type == b"\xa9mak":
            info.make = info.make or _parse_text_box(_read_box_body(stream, box))
        elif box.type == b"\xa9mod":
            info.model = info.model or _parse_text_box(_read_box_body(stream, box))
        elif box.type == b"meta":
            _parse_meta(stream, box, info)


def _parse_mvhd(stream: BinaryIO, mvhd_box: _Box) -> datetime | None:
    body = _read_box_body(stream, mvhd_box, max_size=128)
    if len(body) < 20:
        raise _BoxError("truncated mvhd box")

    version = body[0]
    if version == 0:
        creation_seconds = int.from_bytes(body[4:8], "big")
    elif version == 1:
        if len(body) < 24:
            raise _BoxError("truncated mvhd version 1 box")
        creation_seconds = int.from_bytes(body[4:12], "big")
    else:
        raise _BoxError(f"unsupported mvhd version {version}")

    if creation_seconds == 0:
        return None
    try:
        return _ISO_BMFF_EPOCH + timedelta(seconds=creation_seconds)
    except (OverflowError, ValueError):
        return None


def _trak_has_video(stream: BinaryIO, trak_box: _Box) -> bool:
    for mdia in _iter_boxes(stream, trak_box.body_start, trak_box.end):
        if mdia.type != b"mdia":
            continue
        for box in _iter_boxes(stream, mdia.body_start, mdia.end):
            if box.type != b"hdlr":
                continue
            body = _read_box_body(stream, box, max_size=64)
            if len(body) >= 12 and body[8:12] == b"vide":
                return True
    return False


def _parse_video_info(path: Path) -> _VideoInfo:
    info = _VideoInfo()
    file_size = path.stat().st_size

    with path.open("rb") as stream:
        moov: _Box | None = None
        for box in _iter_boxes(stream, 0, file_size):
            if box.type == b"ftyp":
                if box.end - box.body_start < 8:
                    raise _BoxError("invalid ftyp box")
                info.has_ftyp = True
            elif box.type == b"moov":
                moov = box

        if moov is None:
            raise _BoxError("missing moov box")

        for box in _iter_boxes(stream, moov.body_start, moov.end):
            if box.type == b"mvhd":
                info.creation_time = _parse_mvhd(stream, box)
            elif box.type == b"trak":
                if _trak_has_video(stream, box):
                    info.has_video_track = True
            elif box.type == b"meta":
                _parse_meta(stream, box, info)
            elif box.type == b"udta":
                _parse_udta(stream, box, info)

    return info


def _parse_filename_timestamp(stem: str) -> tuple[datetime, str | None] | None:
    for match in _FILENAME_TIMESTAMP_RE.finditer(stem):
        try:
            timestamp = datetime.strptime(
                match.group("date") + match.group("time"), "%Y%m%d%H%M%S"
            )
        except ValueError:
            continue
        return timestamp, match.group("milliseconds")
    return None


def _read_image_metadata(path: Path) -> ExifMetadata:
    try:
        with Image.open(path) as image:
            image_format = image.format
            exif = image.getexif()

            make = _as_text(_exif_value(exif, MAKE_TAG))
            model = _as_text(_exif_value(exif, MODEL_TAG))
            raw_datetime = _as_text(_exif_value(exif, DATETIME_ORIGINAL_TAG))
            subsec = _as_text(_exif_value(exif, SUBSEC_TIME_ORIGINAL_TAG))
    except UnidentifiedImageError as exc:
        raise NotAnImageError(f"not a supported image: {exc}") from exc
    except Exception as exc:
        # Pillow can raise a variety of errors for corrupt EXIF data
        # (OSError, ValueError, SyntaxError, struct.error, ...).
        raise MetadataError(f"cannot read image: {exc}") from exc

    missing = [
        name
        for name, value in (
            ("Make", make),
            ("Model", model),
            ("DateTimeOriginal", raw_datetime),
        )
        if value is None
    ]
    if missing:
        raise MetadataError("missing " + ", ".join(missing))

    assert raw_datetime is not None
    match = _DATETIME_RE.match(raw_datetime)
    if not match:
        raise MetadataError(f"invalid DateTimeOriginal: {raw_datetime!r}")
    try:
        datetime_original = datetime(*(int(part) for part in match.groups()))
    except ValueError as exc:
        raise MetadataError(f"invalid DateTimeOriginal: {raw_datetime!r}") from exc

    assert make is not None and model is not None
    return ExifMetadata(
        make=make,
        model=model,
        datetime_original=datetime_original,
        subsec_time_original=subsec,
        file_type_extension=_file_type_extension(image_format, path.suffix),
    )


def _read_video_metadata(path: Path) -> ExifMetadata:
    try:
        info = _parse_video_info(path)
    except _BoxError as exc:
        raise NotASupportedVideoError(f"not a supported video: {exc}") from exc
    except OSError as exc:
        raise MetadataError(f"cannot read video: {exc}") from exc

    if not info.has_ftyp or not info.has_video_track:
        raise NotASupportedVideoError("not a supported video container")

    filename_timestamp = _parse_filename_timestamp(path.stem)
    if filename_timestamp is not None:
        datetime_original, subsec = filename_timestamp
    else:
        datetime_original, subsec = info.creation_time, None

    missing = [
        name
        for name, value in (
            ("Make", info.make),
            ("Model", info.model),
            ("video timestamp", datetime_original),
        )
        if value is None
    ]
    if missing:
        raise MetadataError("missing " + ", ".join(missing))

    assert datetime_original is not None
    assert info.make is not None and info.model is not None
    return ExifMetadata(
        make=info.make,
        model=info.model,
        datetime_original=datetime_original,
        subsec_time_original=subsec,
        file_type_extension=path.suffix.lower().lstrip("."),
    )


def read_metadata(path: Path) -> ExifMetadata:
    """Read the metadata required for importing *path*.

    Raises :class:`NotAnImageError` for unsupported/non-image files,
    :class:`NotASupportedVideoError` for unsupported video containers, and
    :class:`MetadataError` when required metadata is missing or malformed.
    """

    suffix = path.suffix.lower()
    if suffix in VIDEO_SUFFIXES:
        return _read_video_metadata(path)
    if suffix in UNSUPPORTED_VIDEO_SUFFIXES:
        raise NotASupportedVideoError(f"not a supported video container: {suffix}")
    return _read_image_metadata(path)


def sanitize_component(value: str) -> str:
    """Apply exiftool's ``tr/ /-/;s/--+/-/g`` transformation.

    Path separators are also replaced so metadata cannot escape the archive
    directory.
    """

    value = value.replace(" ", "-").replace("/", "-").replace("\\", "-")
    return re.sub(r"-{2,}", "-", value)


def build_filename(metadata: ExifMetadata, *, include_subseconds: bool = True) -> str:
    timestamp = metadata.datetime_original.strftime("%Y%m%d_%H%M%S")
    if include_subseconds and metadata.subsec_time_original:
        timestamp += "." + metadata.subsec_time_original

    make = sanitize_component(metadata.make)
    model = sanitize_component(metadata.model)
    return f"{timestamp}_{make}_{model}.{metadata.file_type_extension}"


def build_relative_path(
    metadata: ExifMetadata, *, include_subseconds: bool = True
) -> Path:
    date = metadata.datetime_original
    return (
        Path(f"{date.year:04d}")
        / f"{date.month:02d}"
        / build_filename(metadata, include_subseconds=include_subseconds)
    )


def _iter_source_files(source: Path, recursive: bool) -> Iterable[Path]:
    if source.is_file():
        yield source
        return
    iterator = source.rglob("*") if recursive else source.iterdir()
    for path in iterator:
        if path.is_file():
            yield path


def _unique_target(target: Path, reserved: set[Path]) -> Path:
    """Return *target*, adding ``_1``/``_2``/... when it is already taken."""

    if not target.exists() and target not in reserved:
        return target

    counter = 1
    while True:
        candidate = target.with_name(f"{target.stem}_{counter}{target.suffix}")
        if not candidate.exists() and candidate not in reserved:
            return candidate
        counter += 1


def _same_path(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return a.absolute() == b.absolute()


def import_images(
    source: str | Path,
    destination: str | Path = ".",
    *,
    recursive: bool = False,
    dry_run: bool = False,
    include_subseconds: bool = True,
) -> list[ImportResult]:
    """Import photos and videos into the ``YYYY/MM`` tree under *destination*.

    The source directory itself is not recursive by default, matching
    ``exiftool`` without ``-r``.  ``dry_run`` computes all destinations
    without creating directories or moving files.

    Returns one :class:`ImportResult` per source file, in sorted path order.
    """

    source_path = Path(source).expanduser().resolve()
    destination_path = Path(destination).expanduser().resolve()

    if not source_path.exists():
        raise FileNotFoundError(f"source does not exist: {source_path}")

    results: list[ImportResult] = []
    reserved: set[Path] = set()

    files = sorted(_iter_source_files(source_path, recursive), key=lambda p: str(p))
    for path in files:
        try:
            metadata = read_metadata(path)
        except (NotAnImageError, NotASupportedVideoError, MetadataError) as exc:
            results.append(ImportResult(path, None, "skipped", str(exc)))
            continue

        target = destination_path / build_relative_path(
            metadata, include_subseconds=include_subseconds
        )

        if _same_path(path, target):
            reserved.add(target)
            results.append(
                ImportResult(path, target, "unchanged", "already at destination")
            )
            continue

        target = _unique_target(target, reserved)

        if dry_run:
            reserved.add(target)
            results.append(ImportResult(path, target, "would_move"))
            continue

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(target))
        except OSError as exc:
            results.append(ImportResult(path, target, "failed", str(exc)))
            continue

        reserved.add(target)
        results.append(ImportResult(path, target, "moved"))

    return results
