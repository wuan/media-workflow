# Proposal

## Why

Users who run `image-workflow` repeatedly against the same incoming folder and
archive library must retype the same paths on every invocation. Letting the
environment supply those defaults makes shell aliases, scheduled jobs, and CI
runs shorter while keeping explicit command-line arguments authoritative.

## What Changes

- Add `IMAGE_WORKFLOW_SOURCE` as the default for the `import` `SOURCE`
  positional only (the incoming images folder).
- Add `IMAGE_WORKFLOW_ROOT` as the default for the archive/library root
  everywhere it applies:
  - `import --destination`
  - `duplicates ROOT`
  - `fix-times ROOT`
  - `fix-times --destination`
- Apply a fixed precedence: explicit positional or flag, then environment
  variable, then the existing built-in default (`.`, or a required argument).
- Treat an empty environment value as unset.
- When a required source/root is missing, report an error that names the
  relevant environment variable.
- Keep environment lookup in the CLI layer only. The Python API
  (`import_images`, `fix_times`, `duplicates`) continues to take explicit
  arguments and does not read the environment.
- Document the variables, precedence, and examples in the command help and
  README.

## Capabilities

### New Capabilities

- `cli-environment-defaults`: environment-variable defaults for the
  `image-workflow` command-line interface, including variable names,
  command-to-argument mapping, precedence, and unset/empty handling.

### Modified Capabilities

- None. No existing capability specs cover CLI argument defaults.

## Impact

- `src/image_workflow/cli.py` gains environment lookup and positional
  defaults plus missing-value validation.
- `tests/test_cli.py` gains coverage for env-only invocation, explicit
  overrides, empty values, and error messages.
- `README.md` documents the environment variables and precedence.
- No dependency or packaging changes. The library API stays unchanged.
