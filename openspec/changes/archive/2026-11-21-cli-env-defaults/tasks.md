# Tasks

## 1. CLI environment defaults

- [x] 1.1 Add an `_env_default(name)` helper in `src/image_workflow/cli.py` and make the `import` `SOURCE` positional default to `IMAGE_WORKFLOW_SOURCE`; verify a CLI test proves bare `import` uses the env source and an explicit `SOURCE` overrides it.
- [x] 1.2 Wire `IMAGE_WORKFLOW_ROOT` into `import --destination`; verify a CLI test proves the env root is used when `--destination` is omitted and that an explicit `-d`/`--destination` wins.
- [x] 1.3 Wire `IMAGE_WORKFLOW_ROOT` into the `duplicates` `ROOT` positional; verify a CLI test proves the env root is scanned by default and an explicit `ROOT` overrides it.
- [x] 1.4 Wire `IMAGE_WORKFLOW_ROOT` into both `fix-times ROOT` and `fix-times --destination`; verify a CLI test proves both default to the env root and explicit values override either side.
- [x] 1.5 Add post-parse validation so a missing `import SOURCE` or `fix-times ROOT` exits with an error naming `IMAGE_WORKFLOW_SOURCE` or `IMAGE_WORKFLOW_ROOT`; verify tests assert the messages.
- [x] 1.6 Treat an empty environment value as unset; verify tests show empty `IMAGE_WORKFLOW_SOURCE` still reports a required source and empty `IMAGE_WORKFLOW_ROOT` falls back to the current directory.
- [x] 1.7 Confirm the library API remains environment-independent; verify tests call `import_images`, `fix_times`, and `duplicates` directly with env vars set and observe no env-driven behavior.

## 2. Documentation

- [x] 2.1 Add a README section documenting `IMAGE_WORKFLOW_SOURCE`, `IMAGE_WORKFLOW_ROOT`, the argument-to-variable mapping, precedence, and the empty-value rule; verify the documented env-only examples match actual `image-workflow` behavior with test fixtures.
- [x] 2.2 Update the `import`, `duplicates`, and `fix-times` help text to name the relevant environment variable and fallback; verify each `--help` output shows the variable names.

## 3. Integration verification

- [x] 3.1 Run `uv run --extra test pytest` and verify the full suite passes.
- [x] 3.2 Run `uvx ruff check src tests` and `uvx ruff format --check src tests`; verify both are clean.
- [x] 3.3 Run `uv build --no-sources`; verify the wheel and source distribution build successfully.

## Workflow follow-up

- Archive the change after review requirements are satisfied.
- Verify the archived spec and removed change directory.
