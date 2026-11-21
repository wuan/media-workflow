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

## Defaults from environment

The commands accept two optional environment variables as defaults:

| Variable | Used by | CLI argument |
| --- | --- | --- |
| `IMAGE_WORKFLOW_SOURCE` | `import` only | `SOURCE` (the incoming images folder) |
| `IMAGE_WORKFLOW_ROOT` | `import`, `duplicates`, `fix-times` | archive/library root: `--destination` and `ROOT` |

```sh
export IMAGE_WORKFLOW_ROOT="$HOME/photos/library"
export IMAGE_WORKFLOW_SOURCE="$HOME/photos/incoming"

image-workflow import                 # env source -> env archive root
image-workflow duplicates             # scans the env archive root
image-workflow fix-times              # fixes and re-imports the env archive root
```

Explicit command-line values always win, then the environment, then the
built-in default:

```text
explicit argument > environment variable > built-in default
```

An empty environment variable is treated as unset. When a required source or
root cannot be resolved, the command exits with an error that names the
relevant variable.

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

## Publishing to PyPI

Build and publish with uv:

```sh
uv build --no-sources
uv publish
```

`uv publish` reads the PyPI token from `UV_PUBLISH_TOKEN` or accepts `--token`.
Tagged releases are published automatically by the GitLab pipeline:

```sh
git tag -a v0.1.0 -m v0.1.0
git push origin v0.1.0
```

The `publish` job runs only for tags matching `vX.Y.Z` (including common
pre-release suffixes), checks the built wheel and source distribution, and then
runs:

```sh
uv publish --check-url https://pypi.org/simple/
```

Before releasing:

1. Add a masked, protected CI/CD variable named `UV_PUBLISH_TOKEN` containing a
   PyPI API token for the `image-workflow` project.
2. Optionally protect the `pypi` environment so releases require approval.
3. Update the version in `pyproject.toml` (for example with
   `uv version 0.1.0`) and push the matching tag.

Trusted publishing for self-managed GitLab is available as a PyPI beta but
requires onboarding by PyPI staff, so this pipeline uses `UV_PUBLISH_TOKEN`. If
the instance is onboarded later, or the project moves to gitlab.com/GitHub,
trusted publishing can replace the token.

## Layout

```text
.gitlab-ci.yml     # test and PyPI release pipeline
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
  smoke_test.py   # checks the built wheel/sdist
legacy/
  import.sh       # original scripts, kept for reference
  fix_times.sh
  duplicates.py
```
