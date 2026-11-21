# image-workflow

Tools for importing camera photos into a date-based archive and cleaning up
duplicate copies.

The repository started as a small collection of shell/Python scripts. It is now
a Python package with a single CLI and a test suite that builds fake JPEGs with
EXIF metadata to verify the import rules.

## Install

```sh
pip install -e .
```

For development and tests:

```sh
pip install -e '.[test]'
pytest
```

Or, with `uv`:

```sh
uv run --extra test pytest
```

The package depends on [Pillow](https://python-pillow.org/) for reading image
metadata. The optional `fix-times` command also needs `exiftool` on `PATH` to
rewrite EXIF dates without re-encoding JPEGs.

## Import photos

The import command is a Python port of the original `import.sh` exiftool
command. It requires `Make`, `Model`, and `DateTimeOriginal` in each photo and
moves it into a `YYYY/MM` archive tree:

```sh
image-workflow import ../photos_incoming --destination .
```

The resulting name is:

```text
YYYYMMDD_HHMMSS[.SubSecTimeOriginal]_Make_Model.<FileTypeExtension>
```

For example:

```text
photos_incoming/IMG_0001.JPG
  -> 2024/07/20240715_123456.123_Canon_EOS-5D.jpg
```

Rules preserved from exiftool:

| Detail | Behaviour |
| --- | --- |
| Required metadata | Files without `Make`, `Model`, or `DateTimeOriginal` are skipped. |
| Date tree | Files go to `<destination>/<year>/<month>/`. |
| Timestamp | `DateTimeOriginal` is formatted as `YYYYMMDD_HHMMSS`. |
| Subseconds | `SubSecTimeOriginal` is appended as `.123` when present. |
| Make/model | Spaces become `-`; runs of `-` collapse to one `-`. |
| Extension | Exiftool's `FileTypeExtension`: JPEG becomes `.jpg`, TIFF `.tif`, etc. |
| Collisions | Existing names get `_1`, `_2`, ... before the extension. |
| Already imported | A file already at its computed destination is left unchanged. |
| File data | Bytes and modification time are preserved (it is a move/rename). |

By default only files directly in `SOURCE` are imported, matching `exiftool`
without `-r`. Use `--recursive` (or `-r`) to include subdirectories. Use
`--dry-run` (`-n`) to see what would happen without creating directories or
moving files.

The destination defaults to the current directory, which matches running the
original script from the archive root with `SOURCE=../photos_incoming`.

### Python API

```python
from image_workflow import import_images

results = import_images("../photos_incoming", destination=".", recursive=True)
for result in results:
    print(result.status, result.source, "->", result.destination)
```

Each result has one of the statuses `moved`, `would_move`, `unchanged`,
`skipped`, or `failed`.

## Remove duplicates

The duplicate finder is dry-run by default:

```sh
image-workflow duplicates ~/Pictures
image-workflow duplicates ~/Pictures --apply
image-workflow duplicates ~/Pictures --apply --trash
```

- `--apply` actually deletes/moves files.
- `--trash` moves duplicates into a mirrored `.dtrash` tree instead of deleting.
- `--fuzzy` also matches re-exports that differ in resolution or JPEG quality.
- `--threshold BITS` controls the dHash Hamming distance (default 6/64).
- `--verbose` logs near matches that were considered but not flagged.

Fuzzy matching uses a perceptual dHash gate followed by a pixel-difference
check, and differing extended-XMP digests veto a match.

## Fix timestamps and re-import

The `fix-times` command is a port of `fix_times.sh`:

```sh
image-workflow fix-times 2025/09_fix --destination .
```

It adds one hour to all EXIF dates (configurable with `--hours`) and then
re-imports the JPEGs using the import naming rules, without
`SubSecTimeOriginal` (matching the original script). Date shifting requires
`exiftool`.

## Layout

```text
src/image_workflow/
  importer.py     # Python import port and naming rules
  duplicates.py   # duplicate finder
  fix_times.py    # timestamp shifting + re-import
  cli.py          # `image-workflow` entry point
tests/
  conftest.py     # fixtures that create fake images with EXIF data
  test_importer.py
  test_duplicates.py
  test_cli.py
legacy/
  import.sh       # original scripts, kept for reference
  fix_times.sh
  duplicates.py
```
