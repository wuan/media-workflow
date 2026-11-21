# Tasks

## 1. Photo fallback

- [x] 1.1 Add a single fallback helper or constant for missing make/model in
  `src/media_workflow/importer.py`, apply it independently to photo `Make` and
  `Model` after text normalization, and verify with a focused test that absent,
  empty, and whitespace-only values return `unknown`
- [x] 1.2 Update `tests/test_importer.py` so photos missing make and/or model
  are expected to move to archive names containing `unknown`, while photos
  missing `DateTimeOriginal` remain skipped; verify with
  `uv run --extra test pytest tests/test_importer.py`

## 2. Video fallback

- [x] 2.1 Apply the same independent make/model fallback to video metadata
  before the missing-metadata check, keeping the timestamp requirement and skip
  path unchanged; verify with focused video metadata tests
- [x] 2.2 Update video importer tests so missing make/model produces `unknown`
  archive components and missing timestamps still skip; verify with
  `uv run --extra test pytest tests/test_importer.py`

## 3. Documentation and integration

- [x] 3.1 Update the README metadata rules to state that missing or blank make
  and model become `unknown` for both photos and videos, and that timestamps
  remain required; verify the documented examples match the implemented naming
- [x] 3.2 Run `uv run --extra test pytest`, `uvx ruff check src tests`, and
  `uvx ruff format --check src tests`; verify every command passes

## Workflow follow-up

- Archive the change after review and implementation are complete.
