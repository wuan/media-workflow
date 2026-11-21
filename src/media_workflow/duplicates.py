"""Find and remove duplicate copies of photos and videos.

This is the Python package port of the original ``duplicates.py`` script.
Behaviour is preserved:

* dry-run by default; pass ``--apply`` to change files;
* ``--trash`` moves duplicates into ``.dtrash`` instead of deleting them;
* byte-identical JPEGs and videos (same SHA-256) are duplicates by default;
* ``--fuzzy`` adds a perceptual dHash gate and a pixel-MAE verification for
  photos; videos stay exact-hash only;
* differing extended-XMP digests veto a fuzzy match.

Run through the package CLI::

    media-workflow duplicates [ROOT] --apply --trash
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import sys

from PIL import Image

TRASH_DIR = ".dtrash"

# Second-stage fuzzy verification: mean absolute pixel difference (0-255
# scale) after normalizing both images to 64x64 grayscale. Re-exports of the
# same image measure well under 1; distinct photos of the same scene measure
# far above 3.
MAE_THRESHOLD = 3

IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg"})
VIDEO_SUFFIXES = frozenset({".mp4", ".mov", ".m4v", ".3gp"})

# A filename like "beach_1.jpg", "Beach_02.jpeg", or "clip_1.mp4" triggers
# the duplicate check.
COPY_RE = re.compile(
    r"^(?P<base>.+?)_?\d+(\.(?:jpe?g|mp4|mov|m4v|3gp))$", re.IGNORECASE
)


def _extension_pattern(suffix):
    suffix = suffix.lower()
    if suffix in IMAGE_SUFFIXES:
        return r"(?:jpe?g)"
    return re.escape(suffix.lstrip("."))


def candidates(files, base, suffix):
    """Files in one directory that could be the original or copies of *base*.

    Anchored to exactly ``base.jpg``, ``base.jpeg``, ``base_N.jpg/jpeg``, or
    the video equivalents (case-insensitive) so unrelated files that merely
    share a prefix are never touched.  Photos treat ``.jpg`` and ``.jpeg`` as
    the same extension; videos require the exact extension.
    """

    pattern = re.compile(
        r"^" + re.escape(base) + r"(_\d+)?\." + _extension_pattern(suffix) + r"$",
        re.IGNORECASE,
    )
    return [f for f in files if pattern.match(f)]


def _is_image_name(name):
    return os.path.splitext(name)[1].lower() in IMAGE_SUFFIXES


def sha256sum(filename):
    try:
        with open(filename, "rb", buffering=0) as f:
            return hashlib.file_digest(f, "sha256").hexdigest()
    except OSError as exc:
        print(f"warning: cannot read {filename}: {exc}", file=sys.stderr)
        return None


def dhash(filename, size=8):
    """Perceptual hash: robust against rescaling and JPEG recompression."""

    try:
        with Image.open(filename) as img:
            img = img.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
            pixels = img.tobytes()
    except Exception as exc:
        print(f"warning: cannot read image {filename}: {exc}", file=sys.stderr)
        return None

    bits = 0
    for row in range(size):
        for col in range(size):
            left = pixels[row * (size + 1) + col]
            right = pixels[row * (size + 1) + col + 1]
            bits = (bits << 1) | (left > right)
    return bits


def hamming(a, b):
    return (a ^ b).bit_count()


def normalized_mae(path1, path2, size=64):
    """Mean absolute pixel difference (0-255) between two normalized images.

    Robust against rescaling and JPEG recompression: re-exports of the same
    image score near 0, distinct images score much higher.
    """

    pixels = []
    for path in (path1, path2):
        with Image.open(path) as img:
            pixels.append(
                img.convert("L")
                .resize((size, size), Image.Resampling.LANCZOS)
                .tobytes()
            )
    total = sum(abs(a - b) for a, b in zip(*pixels))
    return total / (size * size)


# xmpNote:HasExtendedXMP holds an MD5 over the extended XMP payload. Camera
# apps (e.g. Google HDR+) store depth maps / gain maps there, so differing
# digests mean the files carry different auxiliary data: distinct photos.
XMP_DIGEST_RE = re.compile(r'xmpNote:HasExtendedXMP="([^"]+)"')


def extended_xmp_digest(path):
    """Extended-XMP payload digest, or ``None`` if absent/unreadable."""

    try:
        with Image.open(path) as img:
            xmp = img.info.get("xmp")
    except Exception as exc:
        print(f"warning: cannot read metadata {path}: {exc}", file=sys.stderr)
        return None
    if not xmp:
        return None
    match = XMP_DIGEST_RE.search(xmp.decode("utf-8", "replace"))
    return match.group(1) if match else None


def discard(path, use_trash, trash_dir):
    if use_trash:
        # Mirror the subdirectory layout so files can be restored to their
        # original location unambiguously.
        rel = os.path.relpath(path, os.path.dirname(trash_dir))
        dest = os.path.join(trash_dir, rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        n = 1
        while os.path.exists(dest):
            stem, ext = os.path.splitext(dest)
            dest = f"{stem}_{n}{ext}"
            n += 1
        shutil.move(path, dest)
        return f"moved to {dest}"
    os.remove(path)
    return "deleted"


def process_dir(
    root,
    files,
    apply_changes,
    use_trash,
    trash_dir,
    fuzzy,
    threshold,
    top,
    verbose,
):
    def display(path):
        # Skip the part of the path already given by the scan root.
        return os.path.relpath(path, top)

    copies = [f for f in files if COPY_RE.match(f)]
    if not copies:
        return

    seen_bases = set()
    for copy in copies:
        base = COPY_RE.match(copy).group("base")
        if base in seen_bases:
            continue
        seen_bases.add(base)

        matches = candidates(files, base, os.path.splitext(copy)[1])
        if len(matches) < 2:
            continue

        # Highest quality survives: largest file first; ties broken by
        # preferring the original name, then alphabetical.
        def size_of(name):
            try:
                return os.path.getsize(os.path.join(root, name))
            except OSError:
                return -1

        # Successive stable sorts: last key (size) dominates, earlier keys
        # only break ties.
        matches.sort(key=lambda f: f.lower())
        matches.sort(key=lambda f: COPY_RE.match(f) is not None)
        matches.sort(key=size_of, reverse=True)

        kept = []  # (path, sha256, dhash)
        dupes = []  # (path, kept_path, reason)
        for name in matches:
            path = os.path.join(root, name)
            file_hash = sha256sum(path)
            if file_hash is None:
                continue
            phash = dhash(path) if fuzzy and _is_image_name(name) else None
            dup_of = None
            for kept_path, kept_hash, kept_phash in kept:
                if file_hash == kept_hash:
                    dup_of = (kept_path, "same hash (identical files)")
                    break
                if phash is not None and kept_phash is not None:
                    dist = hamming(phash, kept_phash)
                    mae = normalized_mae(path, kept_path)
                    if dist <= threshold and mae <= MAE_THRESHOLD:
                        xa = extended_xmp_digest(path)
                        xb = extended_xmp_digest(kept_path)
                        if xa is not None and xb is not None and xa != xb:
                            if verbose:
                                kept_suffix = os.path.basename(kept_path)[len(base) :]
                                print(
                                    f"[no match] {display(path)} vs "
                                    f"{kept_suffix}: extended XMP differs "
                                    f"({xa[:8]}\u2026 vs {xb[:8]}\u2026), pixel "
                                    f"difference {mae:.1f}/255"
                                )
                        else:
                            dup_of = (
                                kept_path,
                                f"perceptual match (dHash distance "
                                f"{dist}/{64} bits, pixel difference "
                                f"{mae:.1f}/255)",
                            )
                            break
                    elif verbose:
                        kept_suffix = os.path.basename(kept_path)[len(base) :]
                        print(
                            f"[no match] {display(path)} vs {kept_suffix}: "
                            f"dHash distance {dist}/{64} bits "
                            f"(threshold {threshold}), pixel difference "
                            f"{mae:.1f}/255 (limit {MAE_THRESHOLD:.1f})"
                        )
            if dup_of:
                dupes.append((path, *dup_of))
            else:
                kept.append((path, file_hash, phash))

        for path, dup_of, reason in dupes:
            # Both names share the directory and the base; show only the
            # survivor's differing suffix (e.g. "_1.jpg" or plain ".jpg").
            dup_suffix = os.path.basename(dup_of)[len(base) :]
            if apply_changes:
                try:
                    result = discard(path, use_trash, trash_dir)
                    print(
                        f"removed: {display(path)} (duplicate of {dup_suffix}, "
                        f"{reason}; {result})"
                    )
                except OSError as exc:
                    print(f"error: failed to remove {path}: {exc}", file=sys.stderr)
            else:
                print(
                    f"[dry run] would delete: {display(path)} (duplicate of "
                    f"{dup_suffix}, {reason})"
                )


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="media-workflow duplicates",
        description=__doc__,
    )
    parser.add_argument("root", nargs="?", default=".", help="directory to scan")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually delete/move files (default is dry run)",
    )
    parser.add_argument(
        "--trash",
        action="store_true",
        help="move duplicates into .dtrash instead of deleting",
    )
    parser.add_argument(
        "--fuzzy",
        action="store_true",
        help="also match images that differ in resolution or JPEG quality "
        "(perceptual hash)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=6,
        metavar="BITS",
        help="Hamming distance for --fuzzy matches (default: 6 of 64 bits)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="log fuzzy candidate pairs that were considered but not flagged, "
        "with their similarity values",
    )
    args = parser.parse_args(argv)

    if not args.fuzzy and args.threshold != 6:
        print("warning: --threshold ignored without --fuzzy", file=sys.stderr)

    top = os.path.abspath(args.root)
    trash_dir = os.path.join(top, TRASH_DIR)

    for root, dirs, files in os.walk(top):
        dirs[:] = [d for d in dirs if d != TRASH_DIR]
        process_dir(
            root,
            files,
            args.apply,
            args.trash,
            trash_dir,
            args.fuzzy,
            args.threshold,
            top,
            args.verbose,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
