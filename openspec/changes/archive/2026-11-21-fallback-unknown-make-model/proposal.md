# Proposal

## Why

Photos and videos missing `Make` or `Model` metadata are currently skipped even
when their timestamp is usable. Such files cannot enter the date-based archive,
so their bytes stay in the incoming tree and are effectively invisible to the
rest of the workflow. A predictable fallback keeps them imported without
inventing metadata that does not exist.

## What Changes

- Use `unknown` as the archive-name component when `Make` cannot be extracted,
  and independently when `Model` cannot be extracted.
- Treat absent, empty, and whitespace-only make/model values as missing and
  apply the fallback.
- Apply the fallback to both photos and videos.
- Continue to skip files whose timestamp cannot be extracted; the timestamp
  remains required.
- Update tests and documentation for the new naming outcome.

## Capabilities

### New Capabilities

- `photo-import`: photo metadata requirements and archive naming, including the
  `unknown` fallback for missing EXIF make/model.

### Modified Capabilities

- `video-import`: videos with missing make/model are imported with `unknown`
  components instead of being skipped; only a missing timestamp causes a skip.

## Impact

- `src/media_workflow/importer.py`: photo and video metadata readers normalize
  missing make/model to `unknown` before building the archive name.
- `tests/test_importer.py`: replace missing-make/model skip expectations with
  imported `unknown` names; keep timestamp-missing skip coverage.
- `README.md`: document the fallback in the import metadata rules.
- `src/media_workflow/cli.py`: help text unchanged; `Make`/`Model` are no longer
  required for import success.
- No new dependencies or API changes.
