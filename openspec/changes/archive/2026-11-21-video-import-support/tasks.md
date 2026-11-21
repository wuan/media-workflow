# Tasks

## 1. Synthetic video fixture and metadata reader

- [x] 1.1 Add a `make_video` fixture in `tests/conftest.py` that writes a minimal ISO-BMFF MP4 with `ftyp`, `mvhd`, a `vide` track, and optional Android or Apple metadata; verify a smoke test confirms the fixture contains an `ftyp` box and a video track.
- [x] 1.2 Implement a seek-based ISO-BMFF box reader with bounds checks and video detection (`ftyp` plus a `vide` handler); verify tests for a valid fixture, a truncated file, and a malformed box size.
- [x] 1.3 Parse `mvhd` version 0 and version 1 creation times into naive wall-clock datetimes; verify tests for both versions and an out-of-range value.
- [x] 1.4 Parse Android `keys`/`ilst` metadata for `com.android.manufacturer` and `com.android.model`; verify the Pixel fixture maps to `Google`/`Pixel 6`.
- [x] 1.5 Add Apple `com.apple.quicktime.make/model` keys and `udta` `mak`/`mod` fallback; verify a MOV fixture resolves make and model through both paths.
- [x] 1.6 Add a validated `_YYYYMMDD_HHMMSS[mmm]` filename parser with `mvhd` fallback; verify valid, invalid-date, invalid-time, and no-match cases.
- [x] 1.7 Dispatch `.mp4`, `.mov`, `.m4v`, and `.3gp` files to the video reader while leaving the Pillow path unchanged; verify existing image tests pass and an `.mp4` with invalid content is skipped as unsupported.
- [x] 1.8 Document in `AGENTS.md` that video tests use synthetic ISO-BMFF fixtures and require neither real media nor `exiftool`; verify the note is present.

## 2. Video naming and import behavior

- [x] 2.1 Build video metadata from the filename timestamp, optional milliseconds, make/model, and lowercased suffix; verify `PXL_20250809_194948618.TS.mp4` imports as `2025/08/20250809_194948.618_Google_Pixel-6.mp4`.
- [x] 2.2 Apply the existing make/model sanitization and collision numbering, and drop the `.TS` marker; verify uppercase suffixes, repeated hyphens, and `_1`/`_2` collisions.
- [x] 2.3 Add skip handling and reasons for unsupported containers, missing make/model, and missing timestamps; verify skipped videos keep their bytes and report the specific reason.
- [x] 2.4 Verify dry-run reports `would_move` without creating directories, and a real move preserves video bytes and modification time.
- [x] 2.5 Update the README import section with supported video containers, timestamp precedence, `.TS` handling, and skip rules; verify the documented examples match the tests.
- [x] 2.6 Update the CLI `import` help text to say photos and videos; verify `image-workflow import --help` reflects the broader scope.

## 3. Video duplicate support

- [x] 3.1 Extend the copy-number pattern and candidate matching to `.mp4`, `.mov`, `.m4v`, and `.3gp`, requiring the same base and extension; verify copy candidates and unrelated-prefix exclusion tests.
- [x] 3.2 Verify exact SHA-256 video duplicates use the existing survivor ordering and are reported correctly.
- [x] 3.3 Guard perceptual matching to image suffixes so video candidates do not emit Pillow warnings; verify `--fuzzy` still removes exact-hash video duplicates without attempting pixel comparison.
- [x] 3.4 Verify `--apply` deletes video duplicates and `--apply --trash` mirrors the directory layout under `.dtrash`.
- [x] 3.5 Update the README duplicates section to explain video scope and the photo-only fuzzy limitation; verify the documentation matches the tests.

## 4. Integration verification

- [x] 4.1 Run `uv run --extra test pytest` and verify the full suite passes.
- [x] 4.2 Run `uvx ruff check src tests` and `uvx ruff format --check src tests`; verify both are clean.
- [x] 4.3 Run `uv build --no-sources`; verify the build succeeds.
- [x] 4.4 Run the CLI import dry-run against a synthetic video fixture and verify it reports the expected archive destination.

## Workflow follow-up

- Archive the change after implementation and review.
- Verify the archived specs and implementation result.
