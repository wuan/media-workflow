# Spec Delta

## Purpose

Provides environment-variable defaults for `image-workflow` CLI paths so repeated
commands can omit the incoming source and archive/library root while explicit
arguments remain authoritative.

## ADDED Requirements

### Requirement: Incoming source default

The `image-workflow import` command SHALL use `IMAGE_WORKFLOW_SOURCE` as the
default for its `SOURCE` positional when the positional is omitted.
`IMAGE_WORKFLOW_SOURCE` SHALL NOT supply defaults for the `duplicates` or
`fix-times` root positionals.

#### Scenario: Source from environment

- **WHEN** `IMAGE_WORKFLOW_SOURCE` is set and `image-workflow import` is run
  without a `SOURCE` positional
- **THEN** the command imports from the path in `IMAGE_WORKFLOW_SOURCE`

#### Scenario: Explicit source overrides environment

- **WHEN** `IMAGE_WORKFLOW_SOURCE` is set and a `SOURCE` positional is supplied
- **THEN** the command imports from the explicit `SOURCE`, not the environment
  value

#### Scenario: Source does not affect other commands

- **WHEN** `IMAGE_WORKFLOW_SOURCE` is set and `image-workflow duplicates` or
  `image-workflow fix-times` is run without a root positional
- **THEN** the command does not use `IMAGE_WORKFLOW_SOURCE` as its root

### Requirement: Library root default

The CLI SHALL use `IMAGE_WORKFLOW_ROOT` as the default for the archive/library
root: `import --destination`, `duplicates ROOT`, `fix-times ROOT`, and
`fix-times --destination`.

#### Scenario: Import destination from environment

- **WHEN** `IMAGE_WORKFLOW_ROOT` is set and `image-workflow import SOURCE` is
  run without `--destination`
- **THEN** the archive tree is written under `IMAGE_WORKFLOW_ROOT`

#### Scenario: Duplicates root from environment

- **WHEN** `IMAGE_WORKFLOW_ROOT` is set and `image-workflow duplicates` is run
  without a `ROOT` positional
- **THEN** the command scans `IMAGE_WORKFLOW_ROOT`

#### Scenario: Fix-times root and destination from environment

- **WHEN** `IMAGE_WORKFLOW_ROOT` is set and `image-workflow fix-times` is run
  without a `ROOT` positional or `--destination`
- **THEN** the command uses `IMAGE_WORKFLOW_ROOT` for both the folder to fix and
  the archive root

### Requirement: Argument precedence

Explicit command-line values SHALL take precedence over environment variables,
and environment variables SHALL take precedence over built-in defaults.

#### Scenario: Explicit destination overrides root environment

- **WHEN** `IMAGE_WORKFLOW_ROOT` is set and `--destination DIR` is supplied
- **THEN** the command uses `DIR`

#### Scenario: Explicit root overrides root environment

- **WHEN** `IMAGE_WORKFLOW_ROOT` is set and a `ROOT` positional is supplied
- **THEN** the command uses the explicit `ROOT`

#### Scenario: Built-in default when environment is unset

- **WHEN** `IMAGE_WORKFLOW_ROOT` is unset and an optional destination or root is
  omitted
- **THEN** the command uses its built-in default of the current directory

### Requirement: Empty environment values

An environment variable that is set to an empty value SHALL be treated as unset.

#### Scenario: Empty source falls through

- **WHEN** `IMAGE_WORKFLOW_SOURCE` is set to an empty string and
  `image-workflow import` is run without a `SOURCE` positional
- **THEN** the command reports that a source is required

#### Scenario: Empty root falls through

- **WHEN** `IMAGE_WORKFLOW_ROOT` is set to an empty string and an optional
  destination or root is omitted
- **THEN** the command uses its built-in current-directory default

### Requirement: Missing source and root errors

When a required source or root cannot be resolved from an argument or an
environment variable, the CLI SHALL exit with an error that names the relevant
environment variable.

#### Scenario: Missing import source

- **WHEN** `IMAGE_WORKFLOW_SOURCE` is unset and `image-workflow import` is run
  without a `SOURCE` positional
- **THEN** the command exits with an error mentioning `IMAGE_WORKFLOW_SOURCE`

#### Scenario: Missing fix-times root

- **WHEN** `IMAGE_WORKFLOW_ROOT` is unset and `image-workflow fix-times` is run
  without a `ROOT` positional
- **THEN** the command exits with an error mentioning `IMAGE_WORKFLOW_ROOT`

### Requirement: Python API independence

The Python API SHALL continue to use only explicit arguments and SHALL NOT read
`IMAGE_WORKFLOW_SOURCE` or `IMAGE_WORKFLOW_ROOT`.

#### Scenario: API ignores environment

- **WHEN** either environment variable is set and `import_images`, `fix_times`,
  or `duplicates` is called without the corresponding argument
- **THEN** the function uses its normal default or required-argument behaviour
  and does not read the environment
