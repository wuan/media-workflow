"""Command-line interface for the image-workflow package."""

from __future__ import annotations

import argparse
import os
import sys

from . import duplicates, fix_times
from .importer import ImportResult, import_images

SOURCE_ENV = "IMAGE_WORKFLOW_SOURCE"
ROOT_ENV = "IMAGE_WORKFLOW_ROOT"


def _env_default(name: str) -> str | None:
    """Return a non-empty environment value, or ``None`` when unset/empty."""

    return os.environ.get(name) or None


def _print_import_results(results: list[ImportResult], *, quiet: bool = False) -> None:
    for result in results:
        if result.status == "moved":
            print(f"moved: {result.source} -> {result.destination}")
        elif result.status == "would_move":
            print(f"[dry run] would move: {result.source} -> {result.destination}")
        elif result.status == "unchanged":
            print(f"unchanged: {result.source}")
        elif result.status == "failed":
            print(f"error: {result.source}: {result.reason}", file=sys.stderr)
        elif result.status == "skipped" and not quiet:
            print(f"skipped: {result.source} ({result.reason})")


def _cmd_import(args: argparse.Namespace) -> int:
    try:
        results = import_images(
            args.source,
            args.destination,
            recursive=args.recursive,
            dry_run=args.dry_run,
            include_subseconds=not args.no_subseconds,
        )
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    _print_import_results(results, quiet=args.quiet)

    moved = sum(r.status in ("moved", "would_move") for r in results)
    skipped = sum(r.status in ("skipped", "failed") for r in results)
    if not args.quiet:
        print(
            f"{moved} file(s) {'would be ' if args.dry_run else ''}moved, {skipped} skipped"
        )
    return 1 if any(r.status == "failed" for r in results) else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="image-workflow",
        description="Import, organize, and de-duplicate photo and video collections.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    importer = subparsers.add_parser(
        "import",
        help="rename camera photos and videos into a YYYY/MM archive tree",
        description=(
            "Rename photos and videos into "
            "YYYY/MM/YYYYMMDD_HHMMSS[.subsec]_Make_Model.ext."
        ),
    )
    importer.add_argument(
        "source",
        nargs="?",
        default=_env_default(SOURCE_ENV),
        help=f"directory (or one file) to import (or set {SOURCE_ENV})",
    )
    importer.add_argument(
        "--destination",
        "-d",
        default=_env_default(ROOT_ENV) or ".",
        help=f"archive root for the YYYY/MM tree (default: ${ROOT_ENV} or current directory)",
    )
    importer.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        help="also import files in subdirectories of SOURCE",
    )
    importer.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="show what would happen without moving files",
    )
    importer.add_argument(
        "--no-subseconds",
        action="store_true",
        help="omit SubSecTimeOriginal from filenames",
    )
    importer.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="do not report skipped files or the summary",
    )
    importer.set_defaults(func=_cmd_import)

    duplicate_parser = subparsers.add_parser(
        "duplicates",
        help="find/remove duplicate copies such as beach_1.jpg",
    )
    duplicate_parser.add_argument(
        "root",
        nargs="?",
        default=_env_default(ROOT_ENV) or ".",
        help=f"directory to scan (default: ${ROOT_ENV} or current directory)",
    )
    duplicate_parser.add_argument(
        "--apply",
        action="store_true",
        help="actually delete/move files (default is dry run)",
    )
    duplicate_parser.add_argument(
        "--trash",
        action="store_true",
        help="move duplicates into .dtrash instead of deleting",
    )
    duplicate_parser.add_argument(
        "--fuzzy",
        action="store_true",
        help="match images that differ in resolution or JPEG quality",
    )
    duplicate_parser.add_argument(
        "--threshold",
        type=int,
        default=6,
        metavar="BITS",
        help="Hamming distance for --fuzzy matches (default: 6 of 64 bits)",
    )
    duplicate_parser.add_argument(
        "--verbose",
        action="store_true",
        help="log fuzzy pairs that were considered but not flagged",
    )

    def _cmd_duplicates(args: argparse.Namespace) -> int:
        forwarded = [args.root]
        for flag in ("apply", "trash", "fuzzy", "verbose"):
            if getattr(args, flag):
                forwarded.append("--" + flag)
        if args.threshold != 6:
            forwarded.extend(["--threshold", str(args.threshold)])
        return duplicates.main(forwarded)

    duplicate_parser.set_defaults(func=_cmd_duplicates)

    fix_parser = subparsers.add_parser(
        "fix-times",
        help="shift EXIF dates and re-import JPEGs",
    )
    fix_parser.add_argument(
        "root",
        nargs="?",
        default=_env_default(ROOT_ENV),
        help=f"directory containing JPEGs to fix (or set {ROOT_ENV})",
    )
    fix_parser.add_argument(
        "--destination",
        "-d",
        default=_env_default(ROOT_ENV) or ".",
        help=f"archive root for renamed files (default: ${ROOT_ENV} or current directory)",
    )
    fix_parser.add_argument(
        "--hours",
        type=float,
        default=1.0,
        help="hours to add to all EXIF dates (default: 1)",
    )
    fix_parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="only process JPEGs directly inside ROOT",
    )
    fix_parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="report what would happen without shifting or moving files",
    )
    fix_parser.add_argument(
        "--exiftool",
        default="exiftool",
        help="exiftool executable name/path (default: exiftool)",
    )

    def _cmd_fix_times(args: argparse.Namespace) -> int:
        forwarded = [
            args.root,
            "--destination",
            args.destination,
            "--hours",
            str(args.hours),
            "--exiftool",
            args.exiftool,
        ]
        if args.no_recursive:
            forwarded.append("--no-recursive")
        if args.dry_run:
            forwarded.append("--dry-run")
        return fix_times.main(forwarded)

    fix_parser.set_defaults(func=_cmd_fix_times)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "import" and args.source is None:
        parser.error(f"source is required: pass SOURCE or set {SOURCE_ENV}")
    if args.command == "fix-times" and args.root is None:
        parser.error(f"root is required: pass ROOT or set {ROOT_ENV}")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
