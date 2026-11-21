# cli-environment-defaults Specification

## Purpose

Provides environment-variable defaults for `media-workflow` CLI paths so repeated
commands can omit the incoming source and archive/library root while explicit
arguments remain authoritative.

## Requirements

### Requirement: Incoming source default

The `media-workflow import` command SHALL use `MEDIA_WORKFLOW_SOURCE` as the
default for its `SOURCE` positional when the positional is omitted.
`MEDIA_WORKFLOW_SOURCE` SHALL NOT supply defaults for the `duplicates` or
`fix-times` root positionals.

#### Scenario: Source from environment

- **WHEN** `MEDIA_WORKFLOW_SOURCE` is set and `media-workflow import` is run
  without a `SOURCE` positional
- **THEN** the command imports from the path in `MEDIA_WORKFLOW_SOURCE`

#### Scenario: Explicit source overrides environment

- **WHEN** `MEDIA_WORKFLOW_SOURCE` is set and a `SOURCE` positional is supplied
- **THEN** the command imports from the explicit `SOURCE`, not the environment
  value

#### Scenario: Source does not affect other commands

- **WHEN** `MEDIA_WORKFLOW_SOURCE` is set and `media-workflow duplicates` or
  `media-workflow fix-times` is run without a root positional
- **THEN** the command does not use `MEDIA_WORKFLOW_SOURCE` as its root

### Requirement: Library root default

The CLI SHALL use `MEDIA_WORKFLOW_ROOT` as the default for the archive/library
root: `import --destination`, `duplicates ROOT`, `fix-times ROOT`, and
`fix-times --destination`.

#### Scenario: Import destination from environment

- **WHEN** `MEDIA_WORKFLOW_ROOT` is set and `media-workflow import SOURCE` is
  run without `--destination`
- **THEN** the archive tree is written under `MEDIA_WORKFLOW_ROOT`

#### Scenario: Duplicates root from environment

- **WHEN** `MEDIA_WORKFLOW_ROOT` is set and `media-workflow duplicates` is run
  without a `ROOT` positional
- **THEN** the command scans `MEDIA_WORKFLOW_ROOT`

#### Scenario: Fix-times root and destination from environment

- **WHEN** `MEDIA_WORKFLOW_ROOT` is set and `media-workflow fix-times` is run
  without a `ROOT` positional or `--destination`
- **THEN** the command uses `MEDIA_WORKFLOW_ROOT` for both the folder to fix and
  the archive root

### Requirement: Argument precedence

Explicit command-line values SHALL take precedence over environment variables,
and environment variables SHALL take precedence over built-in defaults.

#### Scenario: Explicit destination overrides root environment

- **WHEN** `MEDIA_WORKFLOW_ROOT` is set and `--destination DIR` is supplied
- **THEN** the command uses `DIR`

#### Scenario: Explicit root overrides root environment

- **WHEN** `MEDIA_WORKFLOW_ROOT` is set and a `ROOT` positional is supplied
- **THEN** the command uses the explicit `ROOT`

#### Scenario: Built-in default when environment is unset

- **WHEN** `MEDIA_WORKFLOW_ROOT` is unset and an optional destination or root is
  omitted
- **THEN** the command uses its built-in default of the current directory

### Requirement: Empty environment values

An environment variable that is set to an empty value SHALL be treated as unset.

#### Scenario: Empty source falls through

- **WHEN** `MEDIA_WORKFLOW_SOURCE` is set to an empty string and
  `media-workflow import` is run without a `SOURCE` positional
- **THEN** the command reports that a source is required

#### Scenario: Empty root falls through

- **WHEN** `MEDIA_WORKFLOW_ROOT` is set to an empty string and an optional
  destination or root is omitted
- **THEN** the command uses its built-in current-directory default

### Requirement: Missing source and root errors

When a required source or root cannot be resolved from an argument or an
environment variable, the CLI SHALL exit with an error that names the relevant
environment variable.

#### Scenario: Missing import source

- **WHEN** `MEDIA_WORKFLOW_SOURCE` is unset and `media-workflow import` is run
  without a `SOURCE` positional
- **THEN** the command exits with an error mentioning `MEDIA_WORKFLOW_SOURCE`

#### Scenario: Missing fix-times root

- **WHEN** `MEDIA_WORKFLOW_ROOT` is unset and `media-workflow fix-times` is run
  without a `ROOT` positional
- **THEN** the command exits with an error mentioning `MEDIA_WORKFLOW_ROOT`

### Requirement: Python API independence

The Python API SHALL continue to use only explicit arguments and SHALL NOT read
`MEDIA_WORKFLOW_SOURCE` or `MEDIA_WORKFLOW_ROOT`.

#### Scenario: API ignores environment

- **WHEN** either environment variable is set and `import_images`, `fix_times`,
  or `duplicates` is called without the corresponding argument
- **THEN** the function uses its normal default or required-argument behaviour
  and does not read the environment
