# Proposal

## Why

Apple QuickTime videos often carry an accurate creation date in metadata, but
the importer currently ignores it and falls back to the `mvhd` movie header
when the filename has no timestamp segment. `mvhd` can be zero, stale, or
rewritten by editing tools, so iPhone `.MOV` files without a timestamp in the
name may be archived under the wrong month or skipped entirely.

## What Changes

- Read the Apple `com.apple.quicktime.creationdate` metadata key alongside the
  existing Android/Apple make and model keys.
- Read the legacy Apple `©day` user-data creation date as a fallback when the
  QuickTime metadata key is absent.
- Select the video timestamp as: valid filename timestamp, then Apple metadata
  creation date, then `mvhd` creation time.
- Parse ISO 8601 creation dates with optional UTC offsets and fractional
  seconds, normalizing them to wall-clock time without timezone conversion,
  matching the existing `mvhd` behavior.
- Keep the existing Apple make/model fallback and document it in the
  `video-import` capability.
- Add synthetic ISO-BMFF fixtures and tests; no real media or `exiftool`
  dependency.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `video-import`: video timestamp selection gains Apple creation-date metadata
  between the filename timestamp and `mvhd`, and Apple make/model fallback
  requirements are clarified.

## Impact

- `src/image_workflow/importer.py`: ISO-BMFF metadata parsing and timestamp
  selection.
- `tests/conftest.py`: synthetic video fixture gains Apple creation-date keys.
- `tests/test_importer.py`: new precedence and parsing tests.
- No CLI, archive layout, naming, or duplicate-detection changes.
