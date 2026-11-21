# Proposal

## Why

Camera libraries contain videos alongside stills, but `image-workflow import`
only understands Pillow-readable images. Pixel/Android videos such as
`PXL_20250809_194948618.TS.mp4` are currently skipped, so the archive and the
duplicate cleanup miss a significant part of a camera roll.

## What Changes

- Recognize ISO-BMFF video containers (`.mp4`, `.mov`, `.m4v`, `.3gp`) by
  content and read make, model, and date without `exiftool` or a real media
  fixture.
- Derive video timestamps from a validated `_YYYYMMDD_HHMMSS[mmm]` filename
  segment, falling back to the `mvhd` creation time.
- Rename videos with the same
  `YYYYMMDD_HHMMSS[.mmm]_Make_Model.ext` archive scheme used for photos, and
  drop the Google Photos `.TS` Top Shot marker from the name.
- Skip unsupported containers and videos without usable make, model, or date
  metadata.
- Extend `duplicates` exact-hash matching to the same video extensions while
  keeping `--fuzzy` photo-only.
- Add synthetic MP4 fixtures and update the user documentation.
- Out of scope: MKV/AVI/WebM/raw MPEG-TS containers, perceptual video matching,
  and video date shifting in `fix-times`.

## Capabilities

### New Capabilities

- `video-import`: selecting ISO-BMFF videos, extracting Android/Apple metadata,
  choosing the archive timestamp, naming, and skip rules.
- `video-duplicates`: exact-hash duplicate detection and cleanup for video
  copies, while fuzzy matching stays photo-only.

### Modified Capabilities

- None.

## Impact

- `src/image_workflow/importer.py`: media dispatch, ISO-BMFF metadata reader,
  and video naming.
- `src/image_workflow/duplicates.py`: candidate pattern and fuzzy guard.
- `src/image_workflow/cli.py`: help and documentation only; no new flags.
- `tests/`: new synthetic MP4 fixture; extended importer and duplicates tests.
- `README.md` and `AGENTS.md`: document video behaviour and test strategy.
- Dependencies: none new; Pillow remains the only runtime metadata dependency.
  `fix-times` is unchanged.
