"""Shift photo timestamps and re-import the affected JPEGs.

Python port of ``fix_times.sh``.  The original script did, for every
``*.jpg`` below ``2025/09_fix``::

    exiftool -overwrite_original "-alldates+=0:0:0 1:0:0" "$file"
    exiftool -if '$Make and $Model and $DateTimeOriginal' \
      -m -d '%Y/%m/%Y%m%d_%H%M%S' -P \
      '-filename<${DateTimeOriginal}_${Make;tr/ /-/;s/--+/-/g}_'
      '${Model;tr/ /-/;s/--+/-/g}%+c.${FileTypeExtension}' "$file"

The date shift is delegated to ``exiftool`` because rewriting EXIF metadata
without re-encoding the JPEG requires a metadata-aware writer.  The rename
step is handled by :func:`media_workflow.importer.import_images` and (like the
original shell script) omits the sub-second component.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

from .importer import ImportResult, import_images


def _format_delta(delta: timedelta) -> str:
    seconds = int(delta.total_seconds())
    sign = "-" if seconds < 0 else "+"
    seconds = abs(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    # exiftool accepts "-alldates+=H:M:S"; for a negative shift the operator
    # becomes "-".
    return f"-alldates{sign}={hours}:{minutes}:{secs}"


def find_jpegs(root: str | Path, *, recursive: bool = True) -> list[Path]:
    root_path = Path(root)
    iterator = root_path.rglob("*") if recursive else root_path.iterdir()
    return sorted(
        (path for path in iterator if path.is_file() and path.suffix.lower() == ".jpg"),
        key=lambda path: str(path),
    )


def shift_dates(
    files: list[Path],
    delta: timedelta = timedelta(hours=1),
    *,
    exiftool: str = "exiftool",
    batch_size: int = 100,
    dry_run: bool = False,
) -> None:
    """Add *delta* to all EXIF date tags in *files* using exiftool."""

    if dry_run or not files:
        return

    executable = shutil.which(exiftool)
    if executable is None:
        raise RuntimeError(
            f"{exiftool!r} is required for date shifting but was not found in PATH"
        )

    offset = _format_delta(delta)
    for start in range(0, len(files), batch_size):
        batch = files[start : start + batch_size]
        command = [executable, "-overwrite_original", offset, *map(str, batch)]
        completed = subprocess.run(command, text=True, capture_output=True)
        if completed.returncode != 0:
            raise RuntimeError(
                "exiftool failed to shift dates:\n"
                f"{completed.stdout}{completed.stderr}".strip()
            )


def fix_times(
    root: str | Path,
    destination: str | Path = ".",
    *,
    delta: timedelta = timedelta(hours=1),
    recursive: bool = True,
    dry_run: bool = False,
    exiftool: str = "exiftool",
) -> list[ImportResult]:
    """Shift dates in JPEGs below *root* and import them into *destination*."""

    root_path = Path(root).expanduser().resolve()
    if not root_path.exists():
        raise FileNotFoundError(f"root does not exist: {root_path}")

    files = find_jpegs(root_path, recursive=recursive)

    if dry_run:
        print(
            f"[dry run] would shift all EXIF dates by {delta} in "
            f"{len(files)} JPEG file(s), then import them",
            file=sys.stderr,
        )
        return []

    shift_dates(files, delta, exiftool=exiftool)

    return import_images(
        root_path,
        destination,
        recursive=recursive,
        include_subseconds=False,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="media-workflow fix-times",
        description=__doc__,
    )
    parser.add_argument("root", help="directory containing the JPEGs to fix")
    parser.add_argument(
        "--destination",
        default=".",
        help="archive root for renamed files (default: current directory)",
    )
    parser.add_argument(
        "--hours",
        type=float,
        default=1.0,
        help="hours to add to all EXIF dates (default: 1)",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="only process JPEGs directly inside ROOT",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report what would happen without shifting or moving files",
    )
    parser.add_argument(
        "--exiftool",
        default="exiftool",
        help="exiftool executable name/path (default: exiftool)",
    )
    args = parser.parse_args(argv)

    try:
        results = fix_times(
            args.root,
            args.destination,
            delta=timedelta(hours=args.hours),
            recursive=not args.no_recursive,
            dry_run=args.dry_run,
            exiftool=args.exiftool,
        )
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    for result in results:
        if result.status == "moved":
            print(f"moved: {result.source} -> {result.destination}")
        elif result.status == "failed":
            print(f"error: {result.source}: {result.reason}", file=sys.stderr)
        elif result.status == "skipped":
            print(f"skipped: {result.source} ({result.reason})")
        elif result.status == "unchanged":
            print(f"unchanged: {result.source}")
    return 1 if any(r.status == "failed" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
