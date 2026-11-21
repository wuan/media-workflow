# Design

## Context

See `proposal.md` for motivation. The CLI lives in `src/image_workflow/cli.py`,
which builds three argparse parsers. `duplicates` and `fix-times` also expose
their own `main(argv)` parsers and the top-level CLI forwards already-resolved
values to them. The library functions take explicit arguments and never read
the environment.

Current defaults:

```text
import      SOURCE required,      --destination "."
duplicates  ROOT ".",             no destination
fix-times   ROOT required,        --destination "."
```

## Goals / Non-Goals

**Goals:**

- Supply `IMAGE_WORKFLOW_SOURCE` and `IMAGE_WORKFLOW_ROOT` defaults from the CLI
  layer only.
- Preserve the precedence in the spec: explicit argument, then environment, then
  built-in default.
- Produce actionable missing-argument errors that name the environment variable.
- Keep the Python API behavior unchanged.

**Non-Goals:**

- Adding config files, dotenv loading, or per-subcommand variables.
- Changing import naming rules, duplicate detection, or timestamp shifting.
- Making direct module invocation (`python -m image_workflow.fix_times`) read the
  environment; the shipped entry point is `image-workflow`.
- Reading environment variables inside the library functions.

## Decisions

### Environment lookup stays in `cli.py`

Add a small helper such as `_env_default(name)` returning
`os.environ.get(name) or None`. Alternatives:

- **Read env in the library functions** — rejected: hidden coupling, surprising
  for API callers, and makes tests depend on ambient state.
- **Add env defaults to `duplicates.main` and `fix_times.main` parsers too** —
  rejected: duplicates the logic and only matters for direct module invocation,
  which is outside the documented CLI contract.

### Optional positionals plus explicit validation

argparse cannot mark a positional required while also giving it a default from
the environment. Use `nargs="?"` and set the default from `_env_default(...)`,
then validate after parsing:

- `import`: if `SOURCE` is `None`, call `parser.error(...)` naming
  `IMAGE_WORKFLOW_SOURCE`.
- `fix-times`: if `ROOT` is `None`, call `parser.error(...)` naming
  `IMAGE_WORKFLOW_ROOT`.
- `duplicates`: keeps `.` when `IMAGE_WORKFLOW_ROOT` is unset, so it never
  needs the missing-value check.

Alternatives considered: a custom argparse `Action` or `type` callable. Both add
more code for the same observable behavior.

### One root variable for all library-root arguments

`IMAGE_WORKFLOW_ROOT` feeds `import --destination`, `duplicates ROOT`,
`fix-times ROOT`, and `fix-times --destination`. This matches the user model
that the archive/library root is a single location, and avoids two variables
that must be kept in sync.

Consequence: `IMAGE_WORKFLOW_ROOT=/photos/library image-workflow fix-times`
uses the library both as the folder to fix and as the destination. That is
intentional under the agreed model; explicit `ROOT` or `--destination` can
override either side.

### Empty means unset

`os.environ.get(name) or None` treats `""` as unset. Whitespace-only values are
preserved because they could theoretically be path characters; documentation
only promises empty-string behavior.

### Static help text, not resolved defaults

Help strings will name the environment variable and the fallback, for example
`(default: $IMAGE_WORKFLOW_ROOT or current directory)`. Using
`ArgumentDefaultsHelpFormatter` would print the value captured when the parser
was built, which can be misleading if the environment changes or if the value
is a long path.

### Path resolution reuses existing behavior

Env values flow through the same `Path(...).expanduser().resolve()` code as
command-line values, so `~` expansion, relative paths, and validation stay
consistent. No new path handling is introduced.

## Risks / Trade-offs

- **In-place `fix-times` via `IMAGE_WORKFLOW_ROOT`** → Documented explicitly;
  users can pass an explicit `ROOT` or `--destination`, and dry-run remains
  available.
- **Ambient env values surprise users** → Help text, README precedence table,
  and explicit-overrides-env tests make the behavior visible.
- **Direct module invocation ignores env** → Accepted non-goal; the supported
  entry point is `image-workflow`.
- **Empty-string ambiguity** → Documented as unset; only empty strings are
  treated specially, not whitespace.

## Migration Plan

Additive change with no data migration. Existing invocations keep working
unchanged. Rollback is removing the env lookup and restoring required
positionals; unsetting the variables is enough to disable the new defaults at
runtime.
