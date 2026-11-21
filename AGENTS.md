# AGENTS.md

Guidance for agents working in this repository.

## Project

`image-workflow` is a Python package for importing camera photos into a
date-based archive and finding duplicate copies.

- `src/image_workflow/importer.py` — Python port of the original `import.sh`
- `src/image_workflow/duplicates.py` — duplicate finder
- `src/image_workflow/fix_times.py` — EXIF date shifting + re-import
- `src/image_workflow/cli.py` — `image-workflow` command-line interface
- `tests/` — pytest suite; fake images with EXIF data are created with Pillow
- `legacy/` — original shell/Python scripts, kept for reference

## Setup and checks

Use `uv`:

```sh
uv run --extra test pytest
uvx ruff check src tests
uvx ruff format --check src tests
uv build --no-sources
```

The import and duplicate tests must not depend on real photos, real videos, or
`exiftool`. Video tests build synthetic ISO-BMFF fixtures in
`tests/conftest.py`. The optional `fix-times` command requires `exiftool` on
`PATH` for date shifting.

Tagged `vX.Y.Z` pushes are built and published to PyPI by `.gitlab-ci.yml`
using `uv publish`. The publish job expects a protected, masked CI/CD variable
named `UV_PUBLISH_TOKEN`.

## Code guidelines

- Keep changes consistent with the existing `src/` package layout.
- Add or update tests for behaviour changes. Import tests should continue to
  generate fake images locally rather than relying on external fixtures.
- Preserve the import naming rules and exiftool-compatible behaviour unless the
  task explicitly asks to change them.
- Do not edit files in `legacy/` unless the task is specifically about them.
- Run the tests and linter before considering work complete.

## Commit convention

This project uses **Conventional Commits**. Every commit message must follow:

```text
<type>(<optional scope>): <short description>
```

Allowed types:

- `feat` — new feature
- `fix` — bug fix
- `docs` — documentation
- `test` — tests only
- `refactor` — code change that neither fixes a bug nor adds a feature
- `chore` — maintenance
- `build` — build system or dependencies
- `ci` — CI configuration
- `perf` — performance improvement

Examples:

```text
feat(importer): add collision-safe copy numbering
fix(duplicates): preserve trash directory layout
test(importer): cover subsecond and timezone handling
docs: document the image-workflow CLI
```

Rules:

- Use the imperative mood and a lowercase description.
- Keep the subject line short; put details in the commit body if needed.
- Mark breaking changes with `!` after the type/scope and explain them in the
  footer, e.g. `feat(cli)!: rename the import subcommand`.
- One logical change per commit.
