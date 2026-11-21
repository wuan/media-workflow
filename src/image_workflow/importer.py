"""Import camera photos into a ``YYYY/MM`` archive tree.

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

Unlike exiftool's relative ``-filename`` path, the destination is explicit and
defaults to the current working directory, matching the usual invocation from
the archive root (``image-workflow import ../photos_incoming``).
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Literal

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

ImportStatus = Literal["moved", "would_move", "unchanged", "skipped", "failed"]


@dataclass(frozen=True)
class ExifMetadata:
    """The metadata needed to build an archive filename."""

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


class MetadataError(Exception):
    """The image could not be read, or its metadata is unusable."""


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


def read_metadata(path: Path) -> ExifMetadata:
    """Read the metadata required for importing *path*.

    Raises :class:`NotAnImageError` for unsupported/non-image files and
    :class:`MetadataError` when required metadata is missing or malformed.
    """

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
    """Import photos from *source* into the ``YYYY/MM`` tree under *destination*.

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
        except NotAnImageError as exc:
            results.append(ImportResult(path, None, "skipped", str(exc)))
            continue
        except MetadataError as exc:
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
